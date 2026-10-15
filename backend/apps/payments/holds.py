"""
apps/payments/holds.py
----------------------
Bed holds: who holds a bed, when a hold has lapsed, and how a lapsed payment is closed.

Lock order everywhere in the payments code (so two requests can never wait on each other):
    Payment row  ->  Bed row  ->  Booking row
`skip_locked` is used by the clean-up paths, so a payment that is being confirmed at this moment is simply
left for the next run instead of making the clean-up wait.

Expiry never depends on a schedule: the status poll and create-order call the same functions, so a hold that
lapsed 14 hours ago reads as lapsed even if the clean-up job has never run.
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.rooms.models import Bed

from .models import Payment, PaymentAttempt

logger = logging.getLogger('apps.payments')

BED_HOLD_MINUTES = 15
OPEN_STATUSES = (Payment.Status.CREATED, Payment.Status.PENDING)


class BedBusy(Exception):
    """Someone is in the middle of paying for this bed."""


def bed_key(booking):
    """(room id, bed number) of a booking, or None when it has no usable bed."""
    if not booking.room_id or not booking.bed_number:
        return None
    try:
        return booking.room_id, int(booking.bed_number)
    except (TypeError, ValueError):
        return None


def hold_has_lapsed(payment, bed, now):
    """True when the bed hold that backed `payment` is over (or was taken over by someone else)."""
    if bed is not None and bed.hold_payment_id == payment.id:
        return bed.held_until is None or bed.held_until <= now
    if bed is not None and bed.hold_payment_id is not None:
        return True  # another payment holds the bed now
    # A hold placed before holders were recorded: judge by the payment's age (the hold is 15 minutes long).
    return payment.created_at <= now - timedelta(minutes=BED_HOLD_MINUTES)


def _release_if_mine(bed, payment):
    """Clear the hold, but only when it is this payment's own (or too old to be anyone's)."""
    if bed is None:
        return
    mine = bed.hold_payment_id == payment.id
    legacy_and_over = bed.hold_payment_id is None and bed.held_until is not None and bed.held_until <= timezone.now()
    if mine or legacy_and_over:
        bed.held_until = None
        bed.hold_payment_id = None
        bed.save(update_fields=['held_until', 'hold_payment_id'])


def close_payment(payment, bed):
    """FAILED, open attempts FAILED, and the payment's own hold released. Caller holds the Payment and Bed locks."""
    payment.attempts.filter(status=PaymentAttempt.Status.INITIATED).update(status=PaymentAttempt.Status.FAILED)
    payment.status = Payment.Status.FAILED
    payment.save(update_fields=['status', 'updated_at'])
    _release_if_mine(bed, payment)


def _locked_open_payment(payment_id):
    return (
        Payment.objects.select_for_update(skip_locked=True, of=('self',))
        .select_related('booking')
        .filter(pk=payment_id, status__in=OPEN_STATUSES)
        .first()
    )


def _locked_bed(booking):
    key = bed_key(booking)
    if key is None:
        return None
    return Bed.objects.select_for_update().filter(room_id=key[0], bed_number=key[1]).first()


def peek_hold_has_lapsed(payment, now=None):
    """Read-only version for hot paths (status polling): no locks, one query."""
    now = now or timezone.now()
    key = bed_key(payment.booking)
    bed = Bed.objects.filter(room_id=key[0], bed_number=key[1]).first() if key else None
    return hold_has_lapsed(payment, bed, now)


def expire_if_lapsed(payment_id, now=None):
    """Close one open payment whose hold has lapsed. Returns True when it was closed."""
    now = now or timezone.now()
    with transaction.atomic():
        payment = _locked_open_payment(payment_id)
        if payment is None:
            return False
        bed = _locked_bed(payment.booking)
        if not hold_has_lapsed(payment, bed, now):
            return False
        close_payment(payment, bed)
    logger.info('Payment %s expired: its bed hold lapsed', payment_id)
    return True


def fail_payment(payment_id):
    """payment.failed from Razorpay: close the payment and release only its own hold."""
    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update(of=('self',)).select_related('booking').get(pk=payment_id)
        )
        if payment.status in (Payment.Status.SUCCESS, Payment.Status.REFUNDED, Payment.Status.FAILED):
            return False
        close_payment(payment, _locked_bed(payment.booking))
    return True


def expire_stale(dry_run=False, now=None):
    """Close every open payment with a lapsed hold, then free beds whose hold has no live payment behind it."""
    now = now or timezone.now()
    expired = 0
    for payment in Payment.objects.filter(status__in=OPEN_STATUSES).select_related('booking'):
        if dry_run:
            expired += peek_hold_has_lapsed(payment, now)
        else:
            expired += expire_if_lapsed(payment.pk, now)

    freed = 0
    stale_beds = Bed.objects.filter(held_until__isnull=False, held_until__lt=now)
    if dry_run:
        return {'payments_expired': expired, 'beds_freed': stale_beds.count()}
    for bed_id in list(stale_beds.values_list('pk', flat=True)):
        with transaction.atomic():
            bed = Bed.objects.select_for_update(skip_locked=True).filter(pk=bed_id, held_until__lt=now).first()
            if bed is not None:
                bed.held_until = None
                bed.hold_payment_id = None
                bed.save(update_fields=['held_until', 'hold_payment_id'])
                freed += 1
    return {'payments_expired': expired, 'beds_freed': freed}


def take_bed(booking):
    """
    A booking paid outside Razorpay (the owner marked it paid): the bed stops being offered.
    Refuses (BedBusy) while another student is in the middle of paying for the same bed.
    """
    key = bed_key(booking)
    if key is None:
        return
    now = timezone.now()
    with transaction.atomic():
        bed, _ = Bed.objects.select_for_update().get_or_create(
            room_id=key[0], bed_number=key[1], defaults={'is_available': True},
        )
        if bed.held_until and bed.held_until > now and bed.hold_payment_id is not None:
            if Payment.objects.filter(pk=bed.hold_payment_id, status__in=OPEN_STATUSES).exists():
                raise BedBusy()
        bed.is_available = False
        bed.held_until = None
        bed.hold_payment_id = None
        bed.save(update_fields=['is_available', 'held_until', 'hold_payment_id'])
