from django.core.management.base import BaseCommand, CommandError
from django.db.models import Exists, OuterRef, Q

from apps.bookings.models import Booking
from apps.payments.models import Payment
from apps.stays import services


class Command(BaseCommand):
    help = (
        "Create the Stay (and Due 1 and Due 2) for every PAID booking that has none, with the same service the paid "
        "paths use. It is the legacy backfill and the self-healing job. Safe to run twice: a booking with a stay is "
        "left alone. Batched (--batch-size, at most 1,000, oldest first): run it again for the next batch. "
        "--dry-run changes nothing. Prints counts only, never a name, phone number or email."
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show the counts and change nothing.')
        parser.add_argument('--batch-size', type=int, default=500, help='Bookings handled per run (1 to 1000).')

    def handle(self, *args, **options):
        batch = options['batch_size']
        if not 1 <= batch <= 1000:
            raise CommandError('--batch-size must be from 1 to 1000.')

        paid_without_stay = Booking.objects.filter(status='paid', stay__isnull=True)
        has_payment = Exists(Payment.objects.filter(booking=OuterRef('pk'), status=Payment.Status.SUCCESS))
        # A booking with no room and no successful payment has no known rent: it cannot be turned into a stay.
        priceable = paid_without_stay.annotate(has_payment=has_payment).filter(Q(room__isnull=False) | Q(has_payment=True))
        skipped = paid_without_stay.count() - priceable.count()
        ids = list(priceable.order_by('marked_paid_at', 'pk').values_list('pk', flat=True)[:batch])

        if options['dry_run']:
            self.stdout.write(f'reconcile_stays (dry run): would create {len(ids)}, skipped {skipped}')
            return

        created = failed = 0
        for pk in ids:
            booking = Booking.objects.get(pk=pk)
            try:
                _, was_created = services.create_stay_for_booking(booking)
            except Exception as exc:  # one bad booking must not stop the rest; ids only in the log
                failed += 1
                self.stderr.write(f'booking {pk}: {type(exc).__name__}')
                continue
            created += was_created
        remaining = priceable.count()
        self.stdout.write(f'reconcile_stays: created {created}, skipped {skipped}, failed {failed}, remaining {remaining}')
