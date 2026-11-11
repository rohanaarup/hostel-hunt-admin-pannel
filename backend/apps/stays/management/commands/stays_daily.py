"""
stays_daily: the once-a-day job of the Stay and Rent engine (Render cron at 03:30 UTC, which is 09:00 IST).

  1. activate     UPCOMING stays whose join date has come become ACTIVE.
  2. dues and reminders
                  for every ACTIVE or NOTICE stay: create the next Due when the latest one is paid or its payable window has
                  opened (E9: from the anchor, never chained), and queue the reminder the ladder calls for today (7, 3, 1 days
                  before, the due day, 1, 3, 7 days after) as an outbox event. WAIVED and CANCELLED dues and ended stays are
                  skipped. process_outbox sends them (inbox, and email on the due day and when overdue).
  3. reconcile    create the stay of any RECENTLY paid booking that has none (self-healing; legacy backfill is a separate,
                  deliberate run of reconcile_stays, see KNOWN_GAPS G5-03).

Each step is isolated: a failure in one is reported and does not stop the others; the command then exits non-zero so the
heartbeat monitor alerts. Safe to run twice (unique constraints and ignore-conflicts inserts make a second run add nothing),
batched (stays are read in keyset pages of --batch-size, at most 1,000), resumable (--resume continues today's unfinished run
from its checkpoint) and --dry-run changes nothing. Counts only, never a name, an address or an amount.
"""
import logging
from datetime import date

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.notifications import services, templates
from apps.stays import billing, schedule
from apps.stays import services as stay_services
from apps.stays.dates import today_ist
from apps.stays.models import Due, OutboxEvent, Stay

logger = logging.getLogger('hh.stays_daily')

MAX_NEW_DUES_PER_STAY = 12
ACTIVE_STATUSES = (Stay.Status.ACTIVE, Stay.Status.NOTICE)


def activate(today, batch, dry_run):
    """UPCOMING to ACTIVE on the join date. The query shrinks as rows change, so no cursor is needed."""
    if dry_run:
        return Stay.objects.filter(status=Stay.Status.UPCOMING, join_date__lte=today).count()
    total = 0
    while True:
        rows = list(Stay.objects.filter(status=Stay.Status.UPCOMING, join_date__lte=today)
                    .order_by('pk').values_list('pk', 'student_id')[:batch])
        if not rows:
            return total
        total += len(rows)
        Stay.objects.filter(pk__in=[pk for pk, _ in rows], status=Stay.Status.UPCOMING).update(
            status=Stay.Status.ACTIVE, updated_at=timezone.now())
        for student_id in {s for _, s in rows}:
            stay_services.bump_home_cache(student_id)


def process_stay(stay, today, new_dues, events, now=None):
    """Plan the next dues and today's reminders of one stay (prefetched dues). Adds to `new_dues` and `events`."""
    window, grace = schedule.window_and_grace(stay)
    rows = schedule.stored_rows(stay, today)
    made = 0
    while rows and made < MAX_NEW_DUES_PER_STAY:
        latest = rows[-1]
        if not (latest.status in (billing.PAID, billing.WAIVED) or latest.status in schedule.PAYABLE_NOW):
            break  # the latest due is still waiting for its window (or was cancelled): nothing to add yet
        following = schedule.projected_rows(stay, today, rows, horizon=1)
        if not following:
            break
        nxt = following[0]
        payable = billing.is_payable(nxt.due_date, today, window)
        due = Due(stay=stay, period_start=nxt.period_start, period_end=nxt.period_end, due_date=nxt.due_date,
                  amount=nxt.amount, status=Due.Status.PAYABLE if payable else Due.Status.SCHEDULED, kind=Due.Kind.RENT)
        new_dues.append(due)
        nxt.id, nxt.projected, nxt.stored_status = due.id, False, due.status
        rows.append(nxt)
        made += 1

    for row in rows:
        if row.stored_status not in (Due.Status.SCHEDULED, Due.Status.PAYABLE):
            continue  # PAID, WAIVED and CANCELLED dues get no reminders
        offset = (row.due_date - today).days
        kind = templates.kind_for(offset)
        if kind is None:
            continue
        events.append(OutboxEvent(
            topic='rent.reminder', dedupe_key=f'reminder-{row.id}-{kind}', priority=templates.priority_for(offset),
            next_attempt_at=now or timezone.now(),
            payload={'due_id': str(row.id), 'kind': kind, 'offset': offset}))
    return made


def dues_and_reminders(today, batch, dry_run, run):
    """One keyset-paginated pass over the current stays. Returns the counts."""
    counts = {'stays': 0, 'dues_planned': 0, 'reminders_planned': 0}
    last = run.checkpoint or None
    while True:
        queryset = Stay.objects.filter(status__in=ACTIVE_STATUSES)
        if last:
            queryset = queryset.filter(pk__gt=last)
        stays = list(queryset.order_by('pk').prefetch_related('dues')[:batch])
        if not stays:
            return counts
        new_dues, events = [], []
        now = timezone.now()
        for stay in stays:
            process_stay(stay, today, new_dues, events, now)
        counts['stays'] += len(stays)
        counts['dues_planned'] += len(new_dues)
        counts['reminders_planned'] += len(events)
        if not dry_run:
            if new_dues:
                Due.objects.bulk_create(new_dues, ignore_conflicts=True)
            if events:
                OutboxEvent.objects.bulk_create(events, ignore_conflicts=True)
            for student_id in {d.stay.student_id for d in new_dues}:
                stay_services.bump_home_cache(student_id)
        last = str(stays[-1].pk)
        if not dry_run:
            run.checkpoint = last
            run.counts = {**run.counts, **counts}
            run.save(update_fields=['checkpoint', 'counts'])
        del stays, new_dues, events  # keep memory flat: nothing carries over between batches


class _NoRun:
    """Stands in for a JobRun in a dry run (nothing is written)."""
    checkpoint = ''
    counts = {}


class Command(BaseCommand):
    help = (
        "The daily stay job: activate stays on their join date, create the next dues, queue today's reminders (7, 3, 1 days "
        "before, due day, 1, 3, 7 days after), and heal recently paid bookings that have no stay. Safe to run twice; "
        "--dry-run changes nothing; --resume continues today's unfinished run from its checkpoint."
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Count what would be done and change nothing.')
        parser.add_argument('--batch-size', type=int, default=1000, help='Stays read per page (1 to 1000).')
        parser.add_argument('--resume', action='store_true', help="Continue today's unfinished run from its checkpoint.")
        parser.add_argument('--skip-reconcile', action='store_true', help='Do not run the reconcile_stays step.')
        parser.add_argument('--today', default='', help='Testing only: pretend today is this IST date (YYYY-MM-DD).')

    def handle(self, *args, **options):
        batch = options['batch_size']
        if not 1 <= batch <= 1000:
            raise CommandError('--batch-size must be from 1 to 1000.')
        dry = options['dry_run']
        today = date.fromisoformat(options['today']) if options['today'] else today_ist()
        failed = []

        def step(name, work):
            try:
                self.stdout.write(f'{name}: {work()}')
            except Exception as exc:  # one failing step must not stop the others
                failed.append(name)
                logger.exception('stays_daily step %s failed', name)
                self.stderr.write(self.style.ERROR(f'{name}: failed ({type(exc).__name__})'))

        if dry:
            run = _NoRun()
            step('activate', lambda: f'would activate {activate(today, batch, True)}')
            step('dues_and_reminders', lambda: dues_and_reminders(today, batch, True, run))
            step('reconcile', lambda: 'skipped in a dry run')
        else:
            with services.job_run('stays_daily', resume=options['resume']) as run:
                step('activate', lambda: f'activated {activate(today, batch, False)}')
                step('dues_and_reminders', lambda: dues_and_reminders(today, batch, False, run))
                if options['skip_reconcile']:
                    self.stdout.write('reconcile: skipped')
                else:
                    step('reconcile', self._reconcile)
                if failed:
                    run.counts = {**run.counts, 'failed_steps': failed}
                    raise SystemExit(f"stays_daily: these steps failed: {', '.join(failed)}")  # the run is recorded FAILED
        if failed:
            raise SystemExit(f"stays_daily: these steps failed: {', '.join(failed)}")
        self.stdout.write(self.style.SUCCESS('stays_daily: done'))

    def _reconcile(self):
        from io import StringIO
        out = StringIO()
        call_command('reconcile_stays', '--batch-size', '1000',
                     '--max-age-days', str(getattr(settings, 'RECONCILE_STAYS_MAX_AGE_DAYS', 3)), stdout=out)
        return out.getvalue().strip()
