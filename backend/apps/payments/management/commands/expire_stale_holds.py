"""
Management command: expire_stale_holds

Closes payments (CREATED/PENDING) whose bed hold has lapsed and frees beds whose hold has no live payment
behind it. The work is done by apps/payments/holds.py, the same code the status poll and create-order use, so
the result never depends on this command having run: it is tidy-up, not correctness.

  python manage.py expire_stale_holds             # do it
  python manage.py expire_stale_holds --dry-run   # count only, change nothing

Safe to run twice, or at the same time as a payment: a payment being confirmed right now is skipped and picked
up by the next run. Normally run through `cleanup_expired` (see render.yaml).
"""
from django.core.management.base import BaseCommand

from apps.payments import holds


class Command(BaseCommand):
    help = "Close payments whose bed hold has lapsed and free beds with no live hold."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help="Count what would change; change nothing.")

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        result = holds.expire_stale(dry_run=dry_run)
        prefix = '[DRY RUN] would close' if dry_run else 'closed'
        self.stdout.write(self.style.SUCCESS(
            f"expire_stale_holds: {prefix} {result['payments_expired']} payment(s), "
            f"{'would free' if dry_run else 'freed'} {result['beds_freed']} bed hold(s)."
        ))
