import time

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Min, Q
from django.utils import timezone

from apps.notifications import engine, services
from apps.stays.models import OutboxEvent


class Command(BaseCommand):
    help = (
        "Drain the outbox: claim due OutboxEvent rows in batches (FOR UPDATE SKIP LOCKED, so two copies can run together), run "
        "their handlers, mark them DONE, retry failures with exponential backoff up to OUTBOX_MAX_ATTEMPTS. Run it from cron "
        "every 5 minutes; for a bigger backlog run it as a Render background worker with --loop. Reminders wait during quiet "
        "hours (21:00 to 08:00 IST). --dry-run only counts. Prints counts only, never a name or an address."
    )

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=200, help='Events claimed per batch (1 to 1000).')
        parser.add_argument('--max-seconds', type=int, default=240,
                            help='Stop starting new batches after this many seconds (0 = no limit). Default 240, under the 5-minute cron.')
        parser.add_argument('--max-batches', type=int, default=0, help='Stop after this many batches (0 = no limit).')
        parser.add_argument('--loop', action='store_true',
                            help='Keep running: when nothing is due, sleep and look again (for a background worker).')
        parser.add_argument('--sleep', type=float, default=5.0, help='Seconds to sleep between looks with --loop.')
        parser.add_argument('--dry-run', action='store_true', help='Count what is due and change nothing.')

    def handle(self, *args, **options):
        batch = options['batch_size']
        if not 1 <= batch <= 1000:
            raise CommandError('--batch-size must be from 1 to 1000.')
        now = timezone.now()

        if options['dry_run']:
            quiet = services.in_quiet_hours(now)
            due = engine.claimable(now, quiet).count()
            pending = OutboxEvent.objects.filter(Q(status='PENDING') | Q(status='FAILED')).count()
            self.stdout.write(f'process_outbox (dry run): {due} due now, {pending} not finished, quiet hours: {quiet}')
            return

        max_seconds = 0 if options['loop'] and options['max_seconds'] == 240 else options['max_seconds']
        with services.job_run('process_outbox') as job:
            total = engine.run(batch, loop=options['loop'], sleep=options['sleep'], max_seconds=max_seconds,
                               max_batches=options['max_batches'])
            job.counts = total
        self.stdout.write('process_outbox: ' + ', '.join(f'{k} {v}' for k, v in total.items()))
