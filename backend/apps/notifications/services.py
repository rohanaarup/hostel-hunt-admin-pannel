"""
apps/notifications/services.py
------------------------------
Shared helpers for the notification engine and its endpoints.

  * Quiet hours: nothing is sent between QUIET_HOURS_START (21:00) and QUIET_HOURS_END (08:00) IST.
  * Preferences: a user with no row has everything on.
  * The unread count, cached per user for 15 seconds through apps/core/cache.py (version per user, bumped on every change).
  * JobRun bookkeeping for the scheduled commands.

Logs carry ids and counts only: never a name, an email address or a phone number.
"""
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core import cache as shared_cache
from apps.stays.dates import IST, to_ist, today_ist

from .models import JobRun, Notification, NotificationPreference

logger = logging.getLogger('hh.notifications')

UNREAD_TTL_SECONDS = 15


# ------------------------------------------------------------------------------------------------------ quiet hours

def quiet_hours():
    return int(getattr(settings, 'QUIET_HOURS_START', 21)), int(getattr(settings, 'QUIET_HOURS_END', 8))


def in_quiet_hours(now=None):
    """True from QUIET_HOURS_START to QUIET_HOURS_END, India time (21:00 to 08:00 by default)."""
    start, end = quiet_hours()
    hour = to_ist(now or timezone.now()).hour
    return hour >= start or hour < end


def next_window_start(now=None):
    """The next moment sending is allowed again (08:00 IST by default), as an aware datetime. Now, outside quiet hours."""
    now = now or timezone.now()
    if not in_quiet_hours(now):
        return now
    _, end = quiet_hours()
    local = to_ist(now)
    opening = datetime(local.year, local.month, local.day, end, tzinfo=IST)
    if local >= opening:
        opening += timedelta(days=1)
    return opening


def ist_day_start(now=None):
    """The start (an aware datetime) of today in India."""
    local = to_ist(now or timezone.now())
    return datetime(local.year, local.month, local.day, tzinfo=IST)


# ------------------------------------------------------------------------------------------------------ preferences

class Channels:
    """What a user wants: inbox (in-app), push, email. Defaults are all on."""
    __slots__ = ('inbox', 'push', 'email')

    def __init__(self, inbox=True, push=True, email=True):
        self.inbox, self.push, self.email = inbox, push, email


def channels_of(user):
    """The user's preferences from an already loaded relation, or the defaults. Never runs a query when `user` was loaded with
    select_related('notification_preferences')."""
    if user is None:
        return Channels(False, False, False)
    try:
        row = user.notification_preferences
    except NotificationPreference.DoesNotExist:
        return Channels()
    return Channels(row.inbox, row.push, row.email)


# ------------------------------------------------------------------------------------------------------ unread count

def unread_cache_name(user_id):
    return f'notif-unread-{user_id}'


def bump_unread(user_id):
    """The unread count (and the Home answer that shows it) changed: drop the cached ones. Safe with the cache down."""
    if user_id is None:
        return
    name = unread_cache_name(user_id)
    shared_cache.bump_version(name)
    transaction.on_commit(lambda: shared_cache.bump_version(name))
    from apps.stays import services as stay_services
    stay_services.bump_home_cache(user_id)


def unread_count(user):
    """How many notifications the user has not read. Tiny query (user, read_at is null), cached 15 s per user."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return 0
    return shared_cache.get_or_set(
        unread_cache_name(user.id), UNREAD_TTL_SECONDS,
        lambda: Notification.objects.filter(user_id=user.id, read_at__isnull=True).count(),
        user_id=user.id, per_user=True)


# ------------------------------------------------------------------------------------------------- manual reminder

def request_manual_reminder(due, now=None):
    """The owner pressed 'Send reminder' (AdminDues). Allowed only for a due that is payable now or overdue, and at most once
    per due per IST day: a NotificationLog row with the date as its bucket is unique, so a second press is refused even when two
    arrive together. The reminder itself is an outbox event (process_outbox sends it, honouring quiet hours and the student
    preferences). Returns the OutboxEvent."""
    from django.db import IntegrityError

    from apps.stays import billing
    from apps.stays import services as stay_services
    from apps.stays.models import OutboxEvent
    from . import templates
    from .models import NotificationLog

    now = now or timezone.now()
    today = today_ist(now)
    if not due.stay.is_current:
        raise stay_services.StayError('STAY_NOT_CURRENT', 'This stay has ended, so there is nobody to remind.')
    effective = stay_services.due_effective_status(due, today)
    if effective not in (billing.PAYABLE, billing.OVERDUE):
        raise stay_services.StayError('DUE_NOT_REMINDABLE', 'A reminder can be sent only for a rent that is payable now or overdue.')
    bucket = today.isoformat()
    try:
        with transaction.atomic():
            NotificationLog.objects.create(due=due, kind='manual_reminder', channel='request', bucket=bucket, created_at=now)
    except IntegrityError:
        raise stay_services.StayError('REMINDER_ALREADY_SENT', 'A reminder was already sent for this rent today.', 429) from None
    offset = (due.due_date - today).days
    event, _ = OutboxEvent.objects.get_or_create(
        dedupe_key=f'reminder-manual-{due.id}-{bucket}',
        defaults={'topic': 'rent.reminder_manual', 'priority': templates.priority_for(offset), 'next_attempt_at': now,
                  'payload': {'due_id': str(due.id), 'bucket': bucket}})
    return event


# ------------------------------------------------------------------------------------------------------ job runs

@contextmanager
def job_run(name, *, resume=False, now=None):
    """Record one run of a scheduled command. With resume=True, continue today's unfinished run (same checkpoint).
    Yields the JobRun; marks it OK on a clean exit and FAILED when the block raises (the exception still propagates)."""
    day = today_ist(now)
    run = None
    if resume:
        run = JobRun.objects.filter(name=name, run_day=day).exclude(status=JobRun.Status.OK).order_by('-started_at').first()
        if run is not None:
            run.status = JobRun.Status.RUNNING
            run.save(update_fields=['status'])
    if run is None:
        run = JobRun.objects.create(name=name, run_day=day, started_at=now or timezone.now())
    try:
        yield run
    except BaseException:
        run.status = JobRun.Status.FAILED
        run.finished_at = timezone.now()
        run.save(update_fields=['status', 'finished_at', 'counts', 'checkpoint'])
        raise
    else:
        run.status = JobRun.Status.OK
        run.finished_at = timezone.now()
        run.save(update_fields=['status', 'finished_at', 'counts', 'checkpoint'])
