"""
Management command: cleanup_expired

The one scheduled job (run it every 5 minutes; see render.yaml). Each step is idempotent, works in small
batches, and a failure in one step does not stop the others.

  1. expire_stale_holds      close payments whose bed hold lapsed, free beds with no live hold
  2. OTP records             delete records that expired more than 1 day ago (this also retires verified
                             tokens that were never used)
  3. webhook events          delete Razorpay event ids older than 30 days
  4. flushexpiredtokens      simplejwt's own command: delete expired blacklisted refresh tokens

  python manage.py cleanup_expired [--dry-run]
"""
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.owners.models import OTPRecord
from apps.payments import holds
from apps.payments.models import PaymentWebhookEvent

BATCH = 1000
OTP_KEEP = timedelta(days=1)
WEBHOOK_KEEP = timedelta(days=30)


def purge(queryset, dry_run):
    """Delete a queryset in batches of BATCH rows so no single statement holds locks for long."""
    if dry_run:
        return queryset.count()
    total = 0
    while True:
        ids = list(queryset.values_list('pk', flat=True)[:BATCH])
        if not ids:
            return total
        total += queryset.model.objects.filter(pk__in=ids).delete()[0]


class Command(BaseCommand):
    help = "Scheduled clean-up: lapsed bed holds, old OTP records, old webhook event ids, expired JWT tokens."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help="Count what would change; change nothing.")

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()
        failed = []

        def step(name, work):
            try:
                self.stdout.write(f"{name}: {work()}")
            except Exception as exc:  # one failing step must not stop the others
                failed.append(name)
                self.stderr.write(self.style.ERROR(f"{name}: failed ({type(exc).__name__})"))

        step('holds', lambda: holds.expire_stale(dry_run=dry_run))
        step('otp_records', lambda: purge(OTPRecord.objects.filter(expires_at__lt=now - OTP_KEEP), dry_run))
        step('webhook_events', lambda: purge(PaymentWebhookEvent.objects.filter(received_at__lt=now - WEBHOOK_KEEP), dry_run))
        if dry_run:
            self.stdout.write("tokens: skipped in a dry run")
        else:
            step('tokens', lambda: call_command('flushexpiredtokens') or 'done')

        if failed:
            raise SystemExit(f"cleanup_expired: these steps failed: {', '.join(failed)}")
        self.stdout.write(self.style.SUCCESS('cleanup_expired: done'))
