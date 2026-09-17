"""
apps/payments/management/commands/expire_stale_holds.py
--------------------------------------------------------
Management command: expire_stale_holds

Finds Payments stuck at CREATED or PENDING status whose associated bed hold
has expired (Bed.held_until < now()), marks them FAILED, and releases the
bed hold back to null so other students can book that bed.

Usage:
  python manage.py expire_stale_holds
  python manage.py expire_stale_holds --timeout 30   # custom minutes
  python manage.py expire_stale_holds --dry-run      # preview only

Intended to be run as a cron job (e.g. every 5 minutes) or via a task queue
such as Celery Beat.  There is no built-in scheduler here — wire it externally.

Example crontab:
  */5 * * * * /path/to/venv/bin/python /path/to/manage.py expire_stale_holds

Design notes:
  - Uses select_for_update() on Bed rows to prevent a race with CreateOrderView
    setting a fresh hold at the same moment this command runs.
  - The Bed → Payment link is traversed via Bed.room + bed_number matching
    Booking.room + Booking.bed_number (string).
  - Each bed is processed in its own atomic transaction so a failure on one
    row does not roll back the others.
"""

import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.payments.models import Payment, PaymentAttempt
from apps.rooms.models import Bed

logger = logging.getLogger('apps.payments')


class Command(BaseCommand):
    help = (
        "Mark stale CREATED/PENDING payments as FAILED and release their bed holds. "
        "Designed to run every few minutes as a cron job."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=15,
            help="Holds older than this many minutes are considered stale (default: 15).",
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Preview what would be expired without making any DB changes.",
        )

    def handle(self, *args, **options):
        timeout_minutes = options['timeout']
        dry_run         = options['dry_run']
        now             = timezone.now()

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"DRY RUN — no changes will be made (timeout={timeout_minutes} min)"
            ))

        # Find beds with an expired hold
        expired_beds = Bed.objects.filter(
            held_until__lt=now,
            held_until__isnull=False,
        )

        if not expired_beds.exists():
            self.stdout.write("No expired bed holds found.")
            return

        total_beds     = expired_beds.count()
        released_count = 0
        failed_count   = 0

        self.stdout.write(f"Found {total_beds} bed(s) with expired holds.")

        for bed in expired_beds:
            try:
                self._expire_bed(bed, dry_run, timeout_minutes, now)
                released_count += 1
            except Exception as exc:
                logger.exception(
                    "expire_stale_holds: error processing bed %s: %s", bed.id, exc
                )
                self.stderr.write(
                    self.style.ERROR(f"  Error on Bed {bed.id}: {exc}")
                )
                failed_count += 1

        summary = (
            f"Done: {released_count} bed hold(s) released, "
            f"{failed_count} error(s)."
        )
        if dry_run:
            summary = f"[DRY RUN] Would release: {released_count} bed hold(s)."

        self.stdout.write(self.style.SUCCESS(summary))
        logger.info("expire_stale_holds: %s", summary)

    def _expire_bed(self, bed, dry_run, timeout_minutes, now):
        """
        Release one expired bed hold and mark matching CREATED/PENDING payments
        as FAILED.  Runs in a per-bed atomic transaction.
        """
        room = bed.room

        self.stdout.write(
            f"  Bed {bed.bed_number} in Room '{room.room_name}' "
            f"(held_until={bed.held_until})"
        )

        # Find matching stale payments:
        #   Payment → booking.room == bed.room
        #   AND booking.bed_number (string) == str(bed.bed_number)
        #   AND payment.status in CREATED / PENDING
        stale_payments = Payment.objects.filter(
            status__in=[Payment.Status.CREATED, Payment.Status.PENDING],
            booking__room=room,
            booking__bed_number=str(bed.bed_number),
        )

        for payment in stale_payments:
            self.stdout.write(
                f"    → Expiring Payment {payment.id} "
                f"(status={payment.status}, created={payment.created_at})"
            )

        if dry_run:
            return

        with transaction.atomic():
            # Re-fetch the bed with a row lock to prevent a race with CreateOrderView
            locked_bed = Bed.objects.select_for_update().get(pk=bed.pk)

            # Double-check: if someone placed a NEW hold between our query and
            # this lock (held_until is now in the future), skip this bed.
            if locked_bed.held_until and locked_bed.held_until > now:
                self.stdout.write(
                    self.style.WARNING(
                        f"    Bed {bed.bed_number} hold was refreshed — skipping."
                    )
                )
                return

            # Mark all open attempts for these payments as FAILED
            PaymentAttempt.objects.filter(
                payment__in=stale_payments,
                status=PaymentAttempt.Status.INITIATED,
            ).update(status=PaymentAttempt.Status.FAILED)

            # Mark payments as FAILED
            expired_ids = list(stale_payments.values_list('id', flat=True))
            Payment.objects.filter(id__in=expired_ids).update(
                status=Payment.Status.FAILED
            )

            # Release bed hold
            locked_bed.held_until = None
            locked_bed.save(update_fields=['held_until'])

        if stale_payments.exists():
            logger.info(
                "expire_stale_holds: expired %d payment(s) for Bed %s (Room %s)",
                len(expired_ids), bed.bed_number, room.room_name,
            )
