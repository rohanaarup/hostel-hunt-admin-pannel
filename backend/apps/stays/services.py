"""
apps/stays/services.py
----------------------
The stay lifecycle: a paid booking becomes a Stay (with Due 1 paid and Due 2 coming), a student asks to vacate, an owner ends
the stay. Everything here is plain functions over the models in apps/stays/models.py and the pure arithmetic in billing.py.

Rules the callers rely on:

  * create_stay_for_booking is IDEMPOTENT: one Stay per booking, however many times and from however many paths it is called
    (card callback, webhook, owner verify, owner mark-paid, the reconcile_stays job). It takes the booking row lock, so two
    callers at the same moment queue up and the second finds the first one's stay.
  * ensure_stay_for_paid_booking is what the paid paths call. It runs the service in a SAVEPOINT and swallows (and logs) any
    failure: money already taken is never rolled back because the stay could not be built. reconcile_stays heals it later.
  * Rent and the billing rule come from the room price and the hostel's config, never from Booking.amount (client supplied,
    KNOWN_GAPS G1-04). The config is copied onto the stay, so later changes never touch it.
  * Logs and outbox payloads carry ids and codes only: no names, phone numbers or emails.
"""
import logging
import uuid

from django.db import transaction
from django.utils import timezone

from apps.bookings.models import Booking
from apps.core import cache as shared_cache
from apps.payments import holds
from apps.payments.models import Payment
from apps.residents.models import Resident
from apps.rooms.models import Bed

from . import billing
from .dates import today_ist
from .models import Due, HostelBillingConfig, OutboxEvent, Stay

logger = logging.getLogger('hh.stays')


def home_cache_name(user_id):
    return f'stays-home-{user_id}'


def bump_home_cache(user_id):
    """Make the student's cached Home answer unreachable (the version is per user). Called whenever money or stay state
    changes: a stay is created or ended, rent is paid, recorded or voided, a vacate request is sent. It bumps at once and
    again after the transaction commits, so a read in between can never leave a stale answer behind. Safe with the cache down."""
    if user_id is None:
        return
    name = home_cache_name(user_id)
    shared_cache.bump_version(name)
    transaction.on_commit(lambda: shared_cache.bump_version(name))


class StayError(Exception):
    """A refusal with a stable code, a plain message and the HTTP status a view should answer with."""

    def __init__(self, code, message, http_status=409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


# --------------------------------------------------------------------------------------------------------------- labels

def room_label(room, fallback_name=None):
    """'Room 204', the wording of the approved boards."""
    if room is not None and room.room_number:
        return f'Room {room.room_number}'
    if room is not None and room.room_name:
        return room.room_name
    return fallback_name or ''


def bed_label(bed_number):
    """Bed 1 is 'Bed A', 2 is 'Bed B' (the wording of the approved boards); anything else is shown as typed."""
    try:
        number = int(bed_number)
    except (TypeError, ValueError):
        return f'Bed {bed_number}' if bed_number else ''
    if 1 <= number <= 26:
        return f'Bed {chr(64 + number)}'
    return f'Bed {number}'


def paid_until(stay):
    """The last day covered by a paid due, or None when nothing is paid yet."""
    last = stay.dues.filter(status=Due.Status.PAID).order_by('-period_end').values_list('period_end', flat=True).first()
    return last


def current_stay_payload(stay):
    """What the 409 ACTIVE_STAY_EXISTS answer shows on the BookingBlocked board."""
    until = paid_until(stay)
    return {
        'id': str(stay.id),
        'hostel_name': stay.hostel.name,
        'locality': stay.hostel.locality,
        'room_label': room_label(stay.room),
        'bed_label': bed_label(stay.bed_number),
        'paid_until': until.isoformat() if until else None,
    }


def find_current_stay(user):
    """The signed-in student's current stay (UPCOMING, ACTIVE or NOTICE), or None (decision D2)."""
    if user is None or not user.is_authenticated:
        return None
    return (Stay.objects.select_related('hostel', 'room')
            .filter(student=user, status__in=Stay.CURRENT_STATUSES).order_by('-created_at').first())


# --------------------------------------------------------------------------------------------------------------- create

def _write_dues(stay, periods, payment, paid_at, today):
    """Due 1 (the period the booking paid for, PAID) and Due 2 (the next one, SCHEDULED or PAYABLE by the window)."""
    first, second = periods[0], periods[1]
    Due.objects.create(
        stay=stay, period_start=first.start, period_end=first.end, due_date=first.due_date, amount=first.amount,
        status=Due.Status.PAID, paid_at=paid_at, payment=payment, kind=Due.Kind.BOOKING_PERIOD,
    )
    window = stay.billing_snapshot['payable_window_days']
    payable = billing.is_payable(second.due_date, today, window)
    Due.objects.create(
        stay=stay, period_start=second.start, period_end=second.end, due_date=second.due_date, amount=second.amount,
        status=Due.Status.PAYABLE if payable else Due.Status.SCHEDULED, kind=Due.Kind.RENT,
    )


def _single_resident(booking):
    """E5: link a Resident only when exactly one points at this booking. Never create one."""
    ids = list(Resident.objects.filter(linked_booking=booking).values_list('pk', flat=True)[:2])
    return ids[0] if len(ids) == 1 else None


def create_stay_for_booking(booking, payment=None):
    """Create the booking's Stay, Due 1 and Due 2 (once). Returns (stay, created). Raises StayError when the booking is
    not paid or cannot be priced. Safe to call again and from several places at once."""
    with transaction.atomic():
        booking = Booking.objects.select_for_update(of=('self',)).select_related('room', 'hostel').get(pk=booking.pk)
        existing = Stay.objects.filter(booking=booking).first()
        if existing is not None:
            return existing, False
        if booking.status != 'paid':
            raise StayError('BOOKING_NOT_PAID', 'A stay is created only from a paid booking.')

        if payment is None:
            payment = booking.payments.filter(status=Payment.Status.SUCCESS, purpose=Payment.Purpose.BOOKING).order_by(
                '-verified_at', '-created_at').first()
        if booking.room is not None:
            rent = booking.room.price_per_month
        elif payment is not None:
            rent = payment.amount  # server-computed from the room price when the order was made
        else:
            raise StayError('NO_PRICE', 'The booking has no room and no payment, so its rent is unknown.')

        now = timezone.now()
        today = today_ist(now)
        paid_at = booking.marked_paid_at or now
        join_date = booking.check_in_date or today_ist(paid_at)
        config = HostelBillingConfig.effective_for(booking.hostel)
        periods = billing.build_periods(
            join_date, config.billing_mode, config.first_period_policy, rent, config.fixed_day_spec(), 2)

        other_current = False
        if booking.student_id is not None:
            other_current = Stay.objects.filter(
                student_id=booking.student_id, status__in=Stay.CURRENT_STATUSES).exists()
        # Due 1 must equal what the student really paid. A prorated first period (a hostel that chose PRORATE) would
        # differ, because create-order still charges a whole month: keep the truth and let a person look (G5-01).
        amount_differs = payment is not None and periods[0].amount != payment.amount
        needs_review = other_current or amount_differs

        stay = Stay.objects.create(
            student_id=booking.student_id, hostel=booking.hostel, room=booking.room, bed_number=booking.bed_number,
            booking=booking, resident_id=_single_resident(booking), join_date=join_date,
            status=Stay.Status.UPCOMING if join_date > today else Stay.Status.ACTIVE,
            rent_amount=rent, billing_snapshot=config.snapshot(), needs_review=needs_review,
        )
        _write_dues(stay, periods, payment, paid_at, today)
        OutboxEvent.objects.get_or_create(
            dedupe_key=f'stay-created-{booking.id}',
            defaults={'topic': 'stay.created', 'payload': {
                'stay_id': str(stay.id), 'booking_id': str(booking.id), 'hostel_id': str(booking.hostel_id)}},
        )
        bump_home_cache(booking.student_id)
        if needs_review:
            logger.warning('stay %s needs review (second current stay: %s, amount differs: %s)',
                           stay.id, other_current, amount_differs)
        return stay, True


def ensure_stay_for_paid_booking(booking, payment=None):
    """Called by the paid paths inside their own transaction. A failure here is logged and NEVER rolls the payment back:
    the work happens in a savepoint, and reconcile_stays creates the stay later. Returns the stay, or None."""
    try:
        with transaction.atomic():
            stay, _ = create_stay_for_booking(booking, payment)
            return stay
    except StayError as exc:
        logger.warning('no stay for booking %s: %s (%s)', booking.pk, exc.code, exc.message)
    except Exception:
        logger.exception('could not create the stay for booking %s; reconcile_stays will retry', booking.pk)
    return None


# -------------------------------------------------------------------------------------------------------------- vacate

def request_vacate(stay, planned_move_out_date, reason, now=None):
    """The student's request to move out: ACTIVE becomes NOTICE; the owner is told through the outbox."""
    now = now or timezone.now()
    if reason not in Stay.VacateReason.values:
        raise StayError('INVALID_REASON', 'Choose one of the listed reasons.', 400)
    if planned_move_out_date < today_ist(now):
        raise StayError('MOVE_OUT_IN_THE_PAST', 'The planned move-out date cannot be in the past.', 400)
    with transaction.atomic():
        stay = Stay.objects.select_for_update().get(pk=stay.pk)
        if stay.status == Stay.Status.NOTICE:
            raise StayError('VACATE_ALREADY_REQUESTED', 'A request to vacate has already been sent for this stay.')
        if stay.status != Stay.Status.ACTIVE:
            raise StayError('STAY_NOT_ACTIVE', 'Only an active stay can be vacated.')
        stay.status = Stay.Status.NOTICE
        stay.vacate_requested_at = now
        stay.planned_move_out_date = planned_move_out_date
        stay.vacate_reason = reason
        stay.save(update_fields=['status', 'vacate_requested_at', 'planned_move_out_date', 'vacate_reason', 'updated_at'])
        bump_home_cache(stay.student_id)
        OutboxEvent.objects.get_or_create(
            dedupe_key=f'stay-vacate-requested-{stay.id}',
            defaults={'topic': 'stay.vacate_requested', 'payload': {
                'stay_id': str(stay.id), 'hostel_id': str(stay.hostel_id), 'reason': reason,
                'planned_move_out_date': planned_move_out_date.isoformat()}},
        )
    return stay


# ----------------------------------------------------------------------------------------------------------------- end

def end_stay(stay, now=None):
    """The owner (or an admin) confirms check-out: ENDED, ended_at set, future unpaid dues cancelled, the bed released.
    Returns (stay, changed); ending an ended stay changes nothing.

    The bed is released the way the rest of the code takes it (a Bed row found by room and bed number, locked first, as
    in apps/payments/holds.py): is_available goes back to True, unless another current stay still holds the same bed.
    The booking stays 'paid': it is history. Room.available_beds is not touched, because nothing maintains it
    (KNOWN_GAPS G1-10)."""
    now = now or timezone.now()
    key = holds.bed_key(stay)
    with transaction.atomic():
        # Same order as the payment code: the bed row first, then the rest.
        bed = Bed.objects.select_for_update().filter(room_id=key[0], bed_number=key[1]).first() if key else None
        stay = Stay.objects.select_for_update().get(pk=stay.pk)
        if stay.status == Stay.Status.ENDED:
            return stay, False
        if stay.status == Stay.Status.CANCELLED:
            raise StayError('STAY_CANCELLED', 'This stay was cancelled.')
        stay.status = Stay.Status.ENDED
        stay.ended_at = now
        stay.save(update_fields=['status', 'ended_at', 'updated_at'])
        bump_home_cache(stay.student_id)

        today = today_ist(now)
        stay.dues.filter(status__in=(Due.Status.SCHEDULED, Due.Status.PAYABLE), period_start__gt=today).update(
            status=Due.Status.CANCELLED, updated_at=now)

        if bed is not None:
            shared = Stay.objects.filter(room_id=stay.room_id, bed_number=stay.bed_number,
                                         status__in=Stay.CURRENT_STATUSES).exclude(pk=stay.pk).exists()
            if shared:
                logger.warning('bed of stay %s stays taken: another current stay holds it', stay.id)
            elif not bed.is_available:
                bed.is_available = True
                bed.save(update_fields=['is_available'])
    return stay, True


# --------------------------------------------------------------------------------------------------- rent (Phase 6)

OFFLINE_METHODS = ('CASH', 'BANK_TRANSFER', 'UPI_DIRECT')
_OPEN_DUE_STATUSES = (Due.Status.SCHEDULED, Due.Status.PAYABLE)


def lock_due(due_id):
    """The Due row, locked (`FOR UPDATE` on the dues table only). In every rent path the order is Payment, then Due."""
    return Due.objects.select_for_update(of=('self',)).select_related('stay').get(pk=due_id)


def due_effective_status(due, today=None):
    """What the due is today: SCHEDULED, PAYABLE, OVERDUE, PAID, WAIVED or CANCELLED (overdue is derived, E8)."""
    snapshot = due.stay.billing_snapshot or {}
    return billing.effective_status(due.status, today or today_ist(), due.due_date,
                                    snapshot.get('payable_window_days', 7), snapshot.get('grace_days', 0))


def refuse_unless_open(due):
    """Raise the refusal a rent action gives for a due that is not open (PAID, WAIVED, CANCELLED)."""
    if due.status not in _OPEN_DUE_STATUSES:
        raise StayError(f'DUE_{due.status}', f'This rent is already {due.get_status_display().lower()}.')


def pay_due(due, payment, paid_at, source):
    """Mark a locked due PAID by `payment` and write the one event row both rent paths write (rent.paid, one per payment)."""
    due.status = Due.Status.PAID
    due.paid_at = paid_at
    due.payment = payment
    due.save(update_fields=['status', 'paid_at', 'payment', 'updated_at'])
    bump_home_cache(due.stay.student_id)
    OutboxEvent.objects.get_or_create(
        dedupe_key=f'rent-paid-{payment.id}',
        defaults={'topic': 'rent.paid', 'payload': {
            'payment_id': str(payment.id), 'due_id': str(due.id), 'stay_id': str(due.stay_id), 'source': source}},
    )


def record_offline_payment(due, user, paid_at, method, reference_note, now=None):
    """The owner (or an admin) records rent received outside the app (decision D3). One record per due: a second call is
    refused. Never touches the booking or the bed. Returns the Payment."""
    now = now or timezone.now()
    if method not in OFFLINE_METHODS:
        raise StayError('INVALID_METHOD', 'Choose cash, bank transfer or UPI direct.', 400)
    if paid_at > now:
        raise StayError('PAID_AT_IN_THE_FUTURE', 'The payment time cannot be in the future.', 400)
    with transaction.atomic():
        locked = lock_due(due.pk)
        refuse_unless_open(locked)
        payment = Payment.objects.create(
            booking_id=locked.stay.booking_id, purpose=Payment.Purpose.RENT, due=locked,
            source=Payment.Source.OFFLINE_OWNER, recorded_by=user, reference_note=reference_note, paid_via=method,
            amount=locked.amount, currency='INR', status=Payment.Status.SUCCESS, verified_at=paid_at,
            razorpay_order_id=f'offline_{uuid.uuid4().hex}',  # the column is unique and required; no Razorpay order exists
        )
        pay_due(locked, payment, paid_at, Payment.Source.OFFLINE_OWNER)
    logger.info('offline rent recorded: payment %s for due %s by user %s', payment.id, locked.id, getattr(user, 'pk', None))
    return payment


def void_offline_payment(due, user, reason, now=None):
    """Take back an offline rent record: the Payment row is kept and marked VOIDED, the due is open again. An online
    (Razorpay) payment can never be voided here: money that moved through the gateway goes back through a refund."""
    now = now or timezone.now()
    payment_id = Due.objects.filter(pk=due.pk).values_list('payment_id', flat=True).first()
    with transaction.atomic():
        # Same order as the payment code: the Payment first, then the Due.
        payment = (Payment.objects.select_for_update(of=('self',)).filter(pk=payment_id).first()
                   if payment_id else None)
        locked = lock_due(due.pk)
        if locked.status != Due.Status.PAID:
            raise StayError('DUE_NOT_PAID', 'Only a paid rent can be voided.')
        if payment is None or locked.payment_id != payment.id:
            raise StayError('NO_PAYMENT_TO_VOID', 'This rent has no payment record to void.')
        if payment.source != Payment.Source.OFFLINE_OWNER or payment.purpose != Payment.Purpose.RENT:
            raise StayError('ONLINE_PAYMENT_NEEDS_REFUND',
                            'This was paid online. Refund it from the payment instead of voiding it.')
        payment.status = Payment.Status.VOIDED
        payment.voided_at = now
        payment.voided_by = user
        payment.void_reason = reason
        payment.save(update_fields=['status', 'voided_at', 'voided_by', 'void_reason', 'updated_at'])

        snapshot = locked.stay.billing_snapshot or {}
        payable = billing.is_payable(locked.due_date, today_ist(now), snapshot.get('payable_window_days', 7))
        locked.status = Due.Status.PAYABLE if payable else Due.Status.SCHEDULED
        locked.paid_at = None
        locked.payment = None  # the Payment keeps its own `due` link, so the history stays readable
        locked.save(update_fields=['status', 'paid_at', 'payment', 'updated_at'])
        bump_home_cache(locked.stay.student_id)
        OutboxEvent.objects.get_or_create(
            dedupe_key=f'rent-voided-{payment.id}',
            defaults={'topic': 'rent.payment_voided', 'payload': {
                'payment_id': str(payment.id), 'due_id': str(locked.id), 'stay_id': str(locked.stay_id),
                'voided_by': str(getattr(user, 'pk', ''))}},
        )
    logger.info('offline rent voided: payment %s for due %s by user %s', payment.id, locked.id, getattr(user, 'pk', None))
    return payment

