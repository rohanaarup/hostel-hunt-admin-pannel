"""
apps/notifications/engine.py
----------------------------
The outbox engine: claims pending OutboxEvent rows in batches, runs their handlers, and records the result. Decision E1: a
Postgres table plus a cron job (or, later, the same command with --loop as a Render background worker). No Celery, no Redis queue.

How a batch works
  1. CLAIM (one short transaction): `SELECT ... FOR UPDATE SKIP LOCKED` the most urgent due rows (highest priority first, then
     oldest), and push their next_attempt_at forward by a lease (LEASE_MINUTES) and count the attempt. Two workers running at
     the same moment can never claim the same row (SKIP LOCKED), and a worker that crashes after claiming leaves rows that
     simply become due again when the lease ends.
  2. HANDLE (no transaction held): the handlers run outside any database transaction, because an email is an HTTP call
     (rule S4). One failing event never stops the others: each is isolated, its error is logged with the event id and the
     exception type only (no personal data; Sentry sees the log line) and the event is retried.
  3. RECORD: finished events become DONE; a failure becomes FAILED with an exponential backoff (60 s, 120 s, 240 s ... at most
     6 hours), retried until OUTBOX_MAX_ATTEMPTS, then left FAILED for a person; a deferral (quiet hours, the daily email cap, a
     provider outage) waits until its time.

Quiet hours (21:00 to 08:00 IST): reminder events are not claimed at all, so they wait for the morning.
"""
import logging
import time
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.stays.models import OutboxEvent

from . import handlers, services

logger = logging.getLogger('hh.outbox')

LEASE_MINUTES = 10
BACKOFF_SECONDS = 60
BACKOFF_CAP_SECONDS = 6 * 3600


def max_attempts():
    return int(getattr(settings, 'OUTBOX_MAX_ATTEMPTS', 8))


def backoff_seconds(attempts):
    """Seconds to wait after the `attempts`-th failure: 60, 120, 240 ... capped at 6 hours."""
    return min(BACKOFF_SECONDS * (2 ** max(0, attempts - 1)), BACKOFF_CAP_SECONDS)


def claimable(now, quiet):
    queryset = OutboxEvent.objects.filter(
        Q(status=OutboxEvent.Status.PENDING) | Q(status=OutboxEvent.Status.FAILED),
        attempts__lt=max_attempts(), next_attempt_at__lte=now)
    if quiet:
        queryset = queryset.exclude(topic__in=handlers.QUIET_TOPICS)
    return queryset


def _due(status, now, quiet):
    queryset = OutboxEvent.objects.filter(status=status, attempts__lt=max_attempts(), next_attempt_at__lte=now)
    return queryset.exclude(topic__in=handlers.QUIET_TOPICS) if quiet else queryset


def claim(batch_size, now):
    """Lock and lease up to `batch_size` due events. Returns them (their `attempts` already counts this try).

    PENDING rows are read on their own, in priority order, straight from the (status, -priority, next_attempt_at) index, so
    the cost of a claim does not depend on how big the backlog is (an OR across PENDING and FAILED forced a sort of the whole
    backlog on every batch: 100,000 rows took 6,465 s to drain, 15 events a second). Rows waiting to be retried (FAILED, with
    attempts left) are a small set and fill whatever room is left."""
    quiet = services.in_quiet_hours(now)
    with transaction.atomic():
        rows = list(_due(OutboxEvent.Status.PENDING, now, quiet).select_for_update(skip_locked=True)
                    .order_by('-priority', 'next_attempt_at', 'id')[:batch_size])
        if len(rows) < batch_size:
            rows += list(_due(OutboxEvent.Status.FAILED, now, quiet).select_for_update(skip_locked=True)
                         .order_by('next_attempt_at', 'id')[:batch_size - len(rows)])
        if rows:
            OutboxEvent.objects.filter(pk__in=[r.pk for r in rows]).update(
                next_attempt_at=now + timedelta(minutes=LEASE_MINUTES), attempts=F('attempts') + 1)
            for row in rows:
                row.attempts += 1
    return rows


def _handle_one(event):
    handler = handlers.HANDLERS.get(event.topic)
    if handler is None:
        if event.topic not in handlers.IGNORED_TOPICS:
            logger.warning('outbox event %s has no handler for topic %s; marked done', event.pk, event.topic)
        return None
    with transaction.atomic():  # the handler's own writes are all or nothing; no outside call happens in it
        return handler(event)


def dispatch(events):
    """Run the handlers. Returns {event.pk: None | Defer | Exception}."""
    results = {}
    by_topic = {}
    for event in events:
        by_topic.setdefault(event.topic, []).append(event)
    for topic, group in by_topic.items():
        batch_handler = handlers.BATCH_HANDLERS.get(topic)
        if batch_handler is not None:
            try:
                results.update(batch_handler(group))
            except Exception as exc:  # the whole group failed before any result: each event is retried
                logger.exception('outbox batch handler failed for topic %s (%s events)', topic, len(group))
                results.update({event.pk: exc for event in group})
            continue
        for event in group:
            try:
                results[event.pk] = _handle_one(event)
            except Exception as exc:
                logger.exception('outbox handler failed: event=%s topic=%s %s', event.pk, event.topic, type(exc).__name__)
                results[event.pk] = exc
    return results


def record(events, results, now):
    """Write the outcome of each event: DONE, a deferral, or FAILED with a backoff. Returns the counts."""
    done, counts = [], {'done': 0, 'deferred': 0, 'failed': 0}
    for event in events:
        result = results.get(event.pk)
        if result is None:
            done.append(event.pk)
        elif isinstance(result, handlers.Defer):
            fields = {'status': OutboxEvent.Status.PENDING, 'next_attempt_at': result.until}
            if not result.count_attempt:
                fields['attempts'] = F('attempts') - 1
            OutboxEvent.objects.filter(pk=event.pk).update(**fields)
            counts['deferred'] += 1
        else:
            OutboxEvent.objects.filter(pk=event.pk).update(
                status=OutboxEvent.Status.FAILED, next_attempt_at=now + timedelta(seconds=backoff_seconds(event.attempts)))
            if event.attempts >= max_attempts():
                logger.error('outbox event %s (%s) failed %s times and is left for a person', event.pk, event.topic,
                             event.attempts)
            counts['failed'] += 1
    if done:
        OutboxEvent.objects.filter(pk__in=done).update(status=OutboxEvent.Status.DONE, processed_at=now)
        counts['done'] = len(done)
    return counts


def process_batch(batch_size=200, now=None):
    """Claim, handle and record one batch. Returns the counts (claimed, done, deferred, failed)."""
    now = now or timezone.now()
    events = claim(batch_size, now)
    if not events:
        return {'claimed': 0, 'done': 0, 'deferred': 0, 'failed': 0}
    results = dispatch(events)
    counts = record(events, results, timezone.now())
    counts['claimed'] = len(events)
    return counts


def run(batch_size=200, *, loop=False, sleep=5.0, max_seconds=0, max_batches=0, now=None):
    """Drain the outbox. Without `loop`: batches until nothing is due (or max_batches / max_seconds is reached). With `loop`:
    the same, then sleep and look again until stopped (a Render background worker). Returns the summed counts."""
    started = time.monotonic()
    total = {'claimed': 0, 'done': 0, 'deferred': 0, 'failed': 0, 'batches': 0}
    while True:
        counts = process_batch(batch_size, now)
        for key, value in counts.items():
            total[key] += value
        if counts['claimed']:
            total['batches'] += 1
        if max_batches and total['batches'] >= max_batches:
            break
        if max_seconds and time.monotonic() - started >= max_seconds:
            break
        if counts['claimed'] == 0:
            if not loop:
                break
            time.sleep(sleep)
    return total
