"""
apps/payments/confirm.py
------------------------
THE one place a payment becomes SUCCESS. The card callback (VerifyPaymentView) and the Razorpay webhook both
call confirm_payment(), so they behave identically and can run at the same moment without confirming twice.

Inside one transaction, in this lock order (see holds.py): Payment -> Bed -> Booking.

  * Already confirmed with the same Razorpay payment id  -> ALREADY_CONFIRMED (no side effects: idempotent).
  * Already refunded                                      -> IGNORED_REFUNDED (a replay never revives it).
  * Webhook amount or currency differs from the order      -> AMOUNT_MISMATCH, flagged, NOT confirmed.
  * Booking was cancelled/rejected, the bed is already taken, or someone else is paying for it right now
    -> FLAGGED: the money was captured but cannot be honoured. Nothing is confirmed, the payment is closed and
       marked needs_review with a note, and an ERROR is logged (Sentry), so a person refunds it. No automatic
       refund: money never moves without a person.
  * Otherwise -> the attempt, payment, booking and bed are all updated together: CONFIRMED.
"""
import logging
from enum import Enum

from django.db import transaction
from django.utils import timezone

from apps.bookings.models import Booking
from apps.rooms.models import Bed

from . import holds
from .models import Payment, PaymentAttempt

logger = logging.getLogger('apps.payments')


class Outcome(str, Enum):
    CONFIRMED = 'confirmed'
    ALREADY_CONFIRMED = 'already_confirmed'
    IGNORED_REFUNDED = 'ignored_refunded'
    AMOUNT_MISMATCH = 'amount_mismatch'
    FLAGGED = 'flagged'


def _flag(payment, note, razorpay_payment_id):
    """Record that money was captured that we could not honour. Runs inside the caller's transaction."""
    payment.needs_review = True
    payment.review_note = note[:200]
    if payment.status in holds.OPEN_STATUSES:
        payment.status = Payment.Status.FAILED
    payment.save(update_fields=['needs_review', 'review_note', 'status', 'updated_at'])
    payment.attempts.filter(status=PaymentAttempt.Status.INITIATED).update(status=PaymentAttempt.Status.FAILED)
    if razorpay_payment_id and not payment.attempts.filter(razorpay_payment_id=razorpay_payment_id).exists():
        # keep the Razorpay id on record so the refund can be found
        PaymentAttempt.objects.create(
            payment=payment, method=PaymentAttempt.Method.CARD, status=PaymentAttempt.Status.FAILED,
            razorpay_payment_id=razorpay_payment_id,
        )
    logger.error('Payment %s needs a manual refund or review: %s', payment.id, note)


def confirm_payment(payment_id, razorpay_payment_id, signature='', *, amount_paise=None, currency=None,
                    method=PaymentAttempt.Method.CARD):
    with transaction.atomic():
        payment = Payment.objects.select_for_update(of=('self',)).select_related('booking').get(pk=payment_id)
        now = timezone.now()

        known = payment.attempts.filter(razorpay_payment_id=razorpay_payment_id).first() if razorpay_payment_id else None

        if payment.status == Payment.Status.SUCCESS:
            if known is not None and known.status == PaymentAttempt.Status.SUCCESS:
                return Outcome.ALREADY_CONFIRMED
            _flag(payment, f'A second payment ({razorpay_payment_id}) was captured for an order that was already '
                           'paid. Refund the duplicate in Razorpay.', razorpay_payment_id)
            return Outcome.FLAGGED

        if payment.status == Payment.Status.REFUNDED:
            logger.info('Payment %s is refunded; a repeated capture is ignored', payment.id)
            return Outcome.IGNORED_REFUNDED

        if known is not None and payment.needs_review:
            return Outcome.FLAGGED  # this capture was already seen and flagged

        if amount_paise is not None and (
            int(amount_paise) != int(payment.amount * 100) or (currency or payment.currency) != payment.currency
        ):
            _flag(payment, f'Razorpay reported {amount_paise} {currency or ""} but the order is for '
                           f'{int(payment.amount * 100)} {payment.currency}.', razorpay_payment_id)
            return Outcome.AMOUNT_MISMATCH

        key = holds.bed_key(payment.booking)
        bed = None
        if key is not None:
            bed, _ = Bed.objects.select_for_update().get_or_create(
                room_id=key[0], bed_number=key[1], defaults={'is_available': True},
            )
        booking = Booking.objects.select_for_update().get(pk=payment.booking_id)

        if booking.status in ('cancelled', 'rejected'):
            _flag(payment, f'The booking was {booking.status} before the payment arrived.', razorpay_payment_id)
            return Outcome.FLAGGED
        if bed is not None:
            if not bed.is_available:
                _flag(payment, 'The bed was already taken when the payment arrived.', razorpay_payment_id)
                return Outcome.FLAGGED
            other_holder = (
                bed.hold_payment_id is not None and bed.hold_payment_id != payment.id
                and bed.held_until is not None and bed.held_until > now
            )
            if other_holder:
                _flag(payment, 'Another student was paying for the same bed when the payment arrived.',
                      razorpay_payment_id)
                return Outcome.FLAGGED

        # The attempt this capture belongs to: the open one for this method, else any open one, else a new one.
        open_attempts = payment.attempts.select_for_update().filter(status=PaymentAttempt.Status.INITIATED)
        attempt = open_attempts.filter(method=method).order_by('-created_at').first() \
            or open_attempts.order_by('-created_at').first()
        if attempt is None:
            attempt = PaymentAttempt(payment=payment, method=method)
        open_attempts.exclude(pk=attempt.pk).update(status=PaymentAttempt.Status.FAILED)
        attempt.razorpay_payment_id = razorpay_payment_id
        attempt.razorpay_signature = signature or ''
        attempt.status = PaymentAttempt.Status.SUCCESS
        attempt.save()

        payment.status = Payment.Status.SUCCESS
        payment.verified_at = now
        payment.save(update_fields=['status', 'verified_at', 'updated_at'])

        booking.status = 'paid'
        booking.marked_paid_at = now
        booking.save(update_fields=['status', 'marked_paid_at', 'updated_at'])

        if bed is not None:
            bed.is_available = False
            bed.held_until = None
            bed.hold_payment_id = None
            bed.save(update_fields=['is_available', 'held_until', 'hold_payment_id'])
        else:
            logger.warning('Payment %s confirmed but booking %s has no usable bed number', payment.id, booking.id)

    logger.info('Payment %s confirmed SUCCESS', payment_id)
    return Outcome.CONFIRMED
