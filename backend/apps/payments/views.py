"""
apps/payments/views.py
-----------------------
Nine API views covering the complete Razorpay payment lifecycle.

Student flow:
  1. CreateOrderView          POST  /payments/create-order/
  2a.InitiateUpiIntentView    POST  /payments/initiate-upi-intent/
  2b.InitiateCardCheckoutView POST  /payments/initiate-card-checkout/
  3. PaymentStatusPollView    GET   /payments/status/<id>/       ← Flutter polls after UPI handoff
  4. VerifyPaymentView        POST  /payments/verify/            ← card flow signature check
  5. WebhookView              POST  /payments/webhook/           ← Razorpay push (NO AUTH, intentional)

History & admin:
  6. PaymentListView          GET   /payments/list/
  7. AdminPaymentListView     GET   /payments/admin-list/
  8. RefundView               POST  /payments/refund/<id>/

KEY RULE: Amount is ALWAYS computed server-side from Room.price_per_month.
          Client-supplied amounts are IGNORED. See line marked '← server-side amount'.
"""

import hashlib
import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings as django_settings
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Booking
from apps.rooms.models import Bed
from apps.core.querysets import TenantScopedQuerysetMixin
from apps.core.utils import get_tenant_scoped_object_or_404

from . import holds
from .confirm import Outcome, confirm_payment
from .models import Payment, PaymentAttempt, PaymentRefund, PaymentWebhookEvent
from apps.core.tenancy.permissions import IsTenantOwner, IsResourceUser
from .serializers import PaymentSerializer, AdminPaymentSerializer
from .services import razorpay_client

logger = logging.getLogger('apps.payments')

# ─── Constants ─────────────────────────────────────────────────────────────────

BED_HOLD_MINUTES = holds.BED_HOLD_MINUTES

# Map Flutter-facing app names → PaymentAttempt.Method enum values
UPI_APP_TO_METHOD = {
    'gpay':    PaymentAttempt.Method.UPI_GPAY,
    'phonepe': PaymentAttempt.Method.UPI_PHONEPE,
    'paytm':   PaymentAttempt.Method.UPI_PAYTM,
}


# ─── Shared helpers ────────────────────────────────────────────────────────────
# Confirming a payment lives in confirm.py (one function, used by verify and the webhook).

def _flagged_reply():
    return Response(
        {'error': 'We received your payment, but this bed could not be reserved for you. '
                  'Our team has been told and will refund you. Please contact support if it takes long.'},
        status=status.HTTP_409_CONFLICT,
    )


def _session_expired_reply():
    return Response({'error': 'This payment session expired. Please start the booking again.'},
                    status=status.HTTP_409_CONFLICT)


def _open_attempt(payment, method):
    """The open attempt for this method, created if there is none: tapping Pay twice must not make two."""
    with transaction.atomic():
        locked = Payment.objects.select_for_update(of=('self',)).get(pk=payment.pk)
        attempt = locked.attempts.filter(
            method=method, status=PaymentAttempt.Status.INITIATED,
        ).order_by('-created_at').first()
        if attempt is None:
            attempt = PaymentAttempt.objects.create(
                payment=locked, method=method, status=PaymentAttempt.Status.INITIATED,
            )
        if locked.status == Payment.Status.CREATED:
            locked.status = Payment.Status.PENDING
            locked.save(update_fields=['status', 'updated_at'])
    return attempt


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CreateOrderView
# ═══════════════════════════════════════════════════════════════════════════════

class CreateOrderView(APIView):
    """
    POST /api/v1/payments/create-order/

    Body: {"booking_id": "<uuid>"}

    Creates a Razorpay order and atomically holds the bed.
    Amount is recomputed server-side from Room.price_per_month — the client
    never influences the amount charged.

    Returns:
        payment_id, razorpay_order_id, amount (INR), currency, razorpay_key_id (PUBLIC KEY ONLY)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        booking_id = request.data.get('booking_id')
        if not booking_id:
            return Response({'error': 'booking_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # ── Validate booking belongs to this student ──────────────────────────
        try:
            booking = Booking.objects.select_related('room', 'hostel').get(
                id=booking_id,
                student=request.user,
            )
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found or does not belong to you.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if booking.payment_mode != 'online':
            return Response({'error': 'This booking is not configured for online payment.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if booking.status in ('paid', 'cancelled', 'rejected'):
            return Response({'error': f'Booking is already {booking.status}.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if not booking.room:
            return Response(
                {'error': 'Booking has no room FK — cannot compute amount server-side.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Amount — server-side ONLY ─────────────────────────────────────────
        amount_inr   = booking.room.price_per_month   # ← server-side amount from Room model
        amount_paise = int(amount_inr * 100)

        # ── Idempotency guard — already-paid booking ──────────────────────────
        if Payment.objects.filter(booking=booking, status=Payment.Status.SUCCESS).exists():
            return Response({'error': 'A successful payment already exists for this booking.'},
                            status=status.HTTP_409_CONFLICT)

        # ── Resolve bed number ────────────────────────────────────────────────
        try:
            bed_number = int(booking.bed_number)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid bed_number on booking. Cannot place hold.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()

        # ── Idempotency guard — retry of an in-flight attempt ─────────────────
        # If this booking already has a live (non-terminal) Payment backed by
        # a bed hold that hasn't expired yet, this is almost certainly a
        # client-side retry (e.g. a timeout on their end even though the
        # first call succeeded) rather than a genuinely new attempt. Reuse
        # the existing Razorpay order instead of creating a second one.
        # NOTE: this narrows but does not eliminate the duplicate-order
        # window — two truly simultaneous requests can both pass this check
        # before either has written a hold; that residual race is caught by
        # the authoritative locked re-check below (one of them loses and
        # hits the compensation path).
        existing_payment = (
            Payment.objects
            .filter(booking=booking, status__in=[Payment.Status.CREATED, Payment.Status.PENDING])
            .order_by('-created_at')
            .first()
        )
        if existing_payment:
            existing_bed = Bed.objects.filter(room=booking.room, bed_number=bed_number).first()
            if (
                existing_bed and existing_bed.held_until and existing_bed.held_until > now
                and existing_bed.hold_payment_id in (None, existing_payment.id)
            ):
                return Response({
                    'payment_id':        str(existing_payment.id),
                    'razorpay_order_id': existing_payment.razorpay_order_id,
                    'amount':            str(existing_payment.amount),
                    'currency':          existing_payment.currency,
                    'razorpay_key_id':   django_settings.RAZORPAY_KEY_ID,
                }, status=status.HTTP_200_OK)

        # ── Step 1: fast, non-locking pre-check ───────────────────────────────
        # Fail fast on an obviously-unavailable bed before doing any external
        # work. This is NOT the authoritative check — no lock is held here,
        # so the result can be stale by the time we reach Step 3.
        bed = Bed.objects.filter(room=booking.room, bed_number=bed_number).first()
        if bed:
            if not bed.is_available:
                return Response(
                    {'error': 'This bed is no longer available.'},
                    status=status.HTTP_409_CONFLICT,
                )
            if bed.held_until and bed.held_until > now:
                return Response(
                    {'error': 'Bed is currently being reserved by another payment. Try again shortly.'},
                    status=status.HTTP_409_CONFLICT,
                )

        # ── Step 2: create the Razorpay order — OUTSIDE any lock/transaction ──
        # This is the slow external I/O call. No DB row lock is held while
        # we wait on it, so it can no longer block other booking attempts
        # on this bed (or hold a DB connection open) for the duration of the
        # Razorpay round-trip.
        try:
            order = razorpay_client.create_order(
                amount_paise=amount_paise,
                receipt_id=str(booking.id),
            )
        except razorpay_client.RazorpayAuthError as exc:
            logger.error(
                "CreateOrderView: Razorpay rejected credentials for booking %s: %s",
                booking.id, exc,
            )
            return Response(
                {'error': 'Payment gateway rejected the request — check API credentials.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as exc:
            logger.exception("Razorpay create_order failed: %s", exc)
            return Response(
                {'error': 'Failed to create payment order. Please try again.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # ── Step 3: short atomic block — authoritative locked re-check ───────
        # Time has passed since Step 1 (at minimum, the Razorpay round-trip);
        # another request may have taken this bed in the meantime. Re-verify
        # under lock before committing to this order. No external calls in
        # this block — it must stay short.
        with transaction.atomic():
            bed, _ = Bed.objects.select_for_update().get_or_create(
                room=booking.room,
                bed_number=bed_number,
                defaults={'is_available': True},
            )

            recheck_now = timezone.now()
            lost_race = (
                not bed.is_available
                or (bed.held_until and bed.held_until > recheck_now)
            )

            if not lost_race:
                payment = Payment.objects.create(
                    booking=booking,
                    razorpay_order_id=order['id'],
                    amount=amount_inr,
                    currency=order.get('currency', 'INR'),
                    status=Payment.Status.CREATED,
                )
                bed.held_until = recheck_now + timedelta(minutes=BED_HOLD_MINUTES)
                bed.hold_payment_id = payment.id
                bed.save(update_fields=['held_until', 'hold_payment_id'])

        # ── Step 4: compensation path — lost the race after the order was
        #    already created ───────────────────────────────────────────────
        if lost_race:
            # Razorpay's Orders API has no cancel/void endpoint — an unpaid
            # order simply sits unused on their side. On our side, record it
            # as FAILED (our existing terminal/non-payable state — see
            # InitiateUpiIntentView's status check) so it can never be
            # confirmed by a stray webhook: WebhookView looks up Payment by
            # razorpay_order_id, and this row now exists in a terminal state
            # rather than being entirely absent.
            Payment.objects.create(
                booking=booking,
                razorpay_order_id=order['id'],
                amount=amount_inr,
                currency=order.get('currency', 'INR'),
                status=Payment.Status.FAILED,
            )
            logger.warning(
                "CreateOrderView: lost bed-availability race for booking %s "
                "(bed %s) after Razorpay order %s was already created — "
                "order abandoned.",
                booking.id, bed_number, order['id'],
            )
            return Response(
                {'error': 'This bed was just booked by someone else. Please try again.'},
                status=status.HTTP_409_CONFLICT,
            )

        return Response({
            'payment_id':        str(payment.id),
            'razorpay_order_id': payment.razorpay_order_id,
            'amount':            str(payment.amount),
            'currency':          payment.currency,
            'razorpay_key_id':   django_settings.RAZORPAY_KEY_ID,  # Public key — safe to expose
        }, status=status.HTTP_201_CREATED)


# ═══════════════════════════════════════════════════════════════════════════════
# 2a. InitiateUpiIntentView
# ═══════════════════════════════════════════════════════════════════════════════

class InitiateUpiIntentView(APIView):
    """
    POST /api/v1/payments/initiate-upi-intent/

    Body: {"payment_id": "<uuid>", "app": "gpay"|"phonepe"|"paytm"}

    Creates a PaymentAttempt(status=INITIATED), calls the Razorpay UPI
    intent API, and returns the deep-link URL for Flutter to launch via
    url_launcher.  Flutter should push PaymentConfirmingScreen immediately
    after launching the URL, then poll PaymentStatusPollView.
    """
    permission_classes = [IsAuthenticated, IsResourceUser]

    def post(self, request):
        payment_id = request.data.get('payment_id')
        app        = (request.data.get('app') or '').lower()

        if not payment_id:
            return Response({'error': 'payment_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if app not in UPI_APP_TO_METHOD:
            return Response(
                {'error': f"app must be one of: {', '.join(UPI_APP_TO_METHOD.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment = Payment.objects.select_related(
                'booking__student', 'booking__room'
            ).get(id=payment_id, booking__student=request.user)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)
        # Redundant with the filter above by construction today, but a
        # separate defense-in-depth check that survives a future refactor
        # accidentally widening that query.
        self.check_object_permissions(request, payment)

        if payment.status == Payment.Status.SUCCESS:
            return Response({'error': 'Payment already successful.'}, status=status.HTTP_409_CONFLICT)
        if payment.status in (Payment.Status.FAILED, Payment.Status.REFUNDED):
            return Response({'error': f'Payment is {payment.status}. Cannot initiate new attempt.'},
                            status=status.HTTP_409_CONFLICT)

        if holds.expire_if_lapsed(payment.id):
            return _session_expired_reply()

        method       = UPI_APP_TO_METHOD[app]
        amount_paise = int(payment.amount * 100)

        # Customer contact details for Razorpay API
        contact = payment.booking.student_phone or '9000000000'
        email   = getattr(payment.booking.student, 'email', None) or 'student@hostelhunt.com'

        try:
            intent_url = razorpay_client.create_upi_intent(
                order_id     = payment.razorpay_order_id,
                amount_paise = amount_paise,
                upi_app      = app,
                contact      = contact,
                email        = email,
            )
        except Exception as exc:
            logger.exception("Razorpay create_upi_intent failed for payment %s: %s", payment_id, exc)
            return Response(
                {'error': 'Failed to initiate UPI payment. Please try again.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        attempt = _open_attempt(payment, method)

        return Response({
            'attempt_id': str(attempt.id),
            'intent_url': intent_url,
        }, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════════════════════
# 2b. InitiateCardCheckoutView
# ═══════════════════════════════════════════════════════════════════════════════

class InitiateCardCheckoutView(APIView):
    """
    POST /api/v1/payments/initiate-card-checkout/

    Body: {"payment_id": "<uuid>"}

    Returns the Razorpay hosted-checkout configuration dict.
    Flutter should pass this to the razorpay_flutter SDK's Razorpay.open()
    method.  After the SDK callback (success/failure), Flutter calls
    VerifyPaymentView to confirm on the server.
    """
    permission_classes = [IsAuthenticated, IsResourceUser]

    def post(self, request):
        payment_id = request.data.get('payment_id')
        if not payment_id:
            return Response({'error': 'payment_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = Payment.objects.get(id=payment_id, booking__student=request.user)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, payment)

        if payment.status == Payment.Status.SUCCESS:
            return Response({'error': 'Payment already successful.'}, status=status.HTTP_409_CONFLICT)

        if payment.status in (Payment.Status.FAILED, Payment.Status.REFUNDED):
            return Response({'error': f'Payment is {payment.status}. Cannot initiate new attempt.'},
                            status=status.HTTP_409_CONFLICT)
        if holds.expire_if_lapsed(payment.id):
            return _session_expired_reply()

        card_config = razorpay_client.get_card_checkout_session(payment.razorpay_order_id)
        attempt = _open_attempt(payment, PaymentAttempt.Method.CARD)

        return Response({
            'attempt_id':     str(attempt.id),
            'checkout_config': card_config,
        }, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PaymentStatusPollView
# ═══════════════════════════════════════════════════════════════════════════════

class PaymentStatusPollView(APIView):
    """
    GET /api/v1/payments/status/<uuid:payment_id>/

    Lightweight polling endpoint used by PaymentConfirmingScreen.
    Flutter calls this every few seconds after returning from the UPI app
    until status resolves to SUCCESS or FAILED.
    """
    permission_classes = [IsAuthenticated, IsResourceUser]

    def get(self, request, payment_id):
        try:
            payment = Payment.objects.get(id=payment_id, booking__student=request.user)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, payment)

        # A hold that lapsed reads as lapsed even if the clean-up job has not run.
        if payment.status in holds.OPEN_STATUSES and holds.peek_hold_has_lapsed(payment):
            if holds.expire_if_lapsed(payment.id):
                payment.refresh_from_db()

        return Response({
            'payment_id':        str(payment.id),
            'status':            payment.status,
            'razorpay_order_id': payment.razorpay_order_id,
        })


# ═══════════════════════════════════════════════════════════════════════════════
# 4. VerifyPaymentView
# ═══════════════════════════════════════════════════════════════════════════════

class VerifyPaymentView(APIView):
    """
    POST /api/v1/payments/verify/

    Used for the card flow: after Razorpay checkout completes in Flutter,
    the client sends the three Razorpay-provided values for server-side
    HMAC-SHA256 verification.

    Body: {
        "payment_id":          "<our Payment UUID>",
        "razorpay_payment_id": "pay_XXXX",
        "razorpay_signature":  "<hmac>"
    }

    On success: atomically marks Payment → SUCCESS, Booking → paid, etc.
    """
    permission_classes = [IsAuthenticated, IsResourceUser]

    def post(self, request):
        payment_id          = request.data.get('payment_id')
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_signature  = request.data.get('razorpay_signature')

        if not all([payment_id, razorpay_payment_id, razorpay_signature]):
            return Response(
                {'error': 'payment_id, razorpay_payment_id, and razorpay_signature are all required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment = Payment.objects.select_related(
                'booking__room', 'booking__student'
            ).get(id=payment_id, booking__student=request.user)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, payment)

        # Idempotency
        if payment.status == Payment.Status.SUCCESS:
            return Response({'success': True, 'message': 'Payment already verified.'})

        # Signature verification (HMAC-SHA256 with KEY_SECRET — server-side only)
        if not razorpay_client.verify_payment_signature(
            order_id   = payment.razorpay_order_id,
            payment_id = razorpay_payment_id,
            signature  = razorpay_signature,
        ):
            return Response({'error': 'Payment signature verification failed.'},
                            status=status.HTTP_400_BAD_REQUEST)

        outcome = confirm_payment(
            payment.id, razorpay_payment_id, razorpay_signature, method=PaymentAttempt.Method.CARD,
        )
        if outcome in (Outcome.CONFIRMED, Outcome.ALREADY_CONFIRMED):
            return Response({'success': True, 'status': Payment.Status.SUCCESS})
        if outcome == Outcome.IGNORED_REFUNDED:
            return Response({'error': 'This payment was refunded.'}, status=status.HTTP_409_CONFLICT)
        return _flagged_reply()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. WebhookView
# ═══════════════════════════════════════════════════════════════════════════════

class WebhookView(APIView):
    """
    POST /api/v1/payments/webhook/

    Razorpay webhook receiver.

    INTENTIONALLY has NO authentication classes applied (Rule 5).
    Security is provided by HMAC-SHA256 signature verification using
    RAZORPAY_WEBHOOK_SECRET — a secret distinct from RAZORPAY_KEY_SECRET.

    Handles:
      - payment.captured  → confirm payment (SUCCESS)
      - order.paid        → confirm payment (SUCCESS)
      - payment.failed    → mark FAILED, release bed hold

    Idempotency: if razorpay_payment_id already maps to a SUCCESS attempt,
    returns 200 immediately without further processing.
    """
    authentication_classes = []  # Rule 5 — webhook comes from Razorpay, not from a user session
    permission_classes     = []  # Rule 5 — do NOT add auth here

    def post(self, request):
        # ── Signature verification (HMAC with WEBHOOK_SECRET) ─────────────────
        signature_header = request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '')
        payload_bytes    = request.body  # Raw bytes needed for HMAC

        if not razorpay_client.verify_webhook_signature(payload_bytes, signature_header):
            logger.warning(
                "Webhook: invalid signature from %s", request.META.get('REMOTE_ADDR')
            )
            return Response({'error': 'Invalid webhook signature.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # ── Parse event ───────────────────────────────────────────────────────
        event            = request.data.get('event', '')
        payload          = request.data.get('payload', {})
        payment_entity   = payload.get('payment', {}).get('entity', {})
        razorpay_payment_id = payment_entity.get('id')
        razorpay_order_id   = payment_entity.get('order_id')

        if not razorpay_order_id:
            logger.info("Webhook event '%s' has no order_id — ignoring", event)
            return Response({'status': 'ignored'})

        # Razorpay sends a unique id with every event (and the same id again on a retry or replay).
        event_id = request.META.get('HTTP_X_RAZORPAY_EVENT_ID') or hashlib.sha256(payload_bytes).hexdigest()

        # The event row, the lookup and the processing are ONE transaction: a delivery that fails halfway leaves
        # no row, so Razorpay's retry is processed normally; a delivery that completed is never processed twice.
        with transaction.atomic():
            try:
                with transaction.atomic():
                    record = PaymentWebhookEvent.objects.create(
                        event_id=event_id[:100], event=str(event)[:60], razorpay_order_id=str(razorpay_order_id)[:100],
                    )
            except IntegrityError:
                logger.info("Webhook: event %s already processed — acknowledged", event_id[:40])
                return Response({'status': 'duplicate'})

            payment_id = Payment.objects.filter(razorpay_order_id=razorpay_order_id).values_list('id', flat=True).first()
            if payment_id is None:
                logger.warning("Webhook: no Payment found for order_id=%s", razorpay_order_id)
                record.outcome = 'unknown_order'
                record.save(update_fields=['outcome'])
                return Response({'status': 'unknown_order'})

            if event in ('payment.captured', 'order.paid'):
                outcome = confirm_payment(
                    payment_id, razorpay_payment_id, payment_entity.get('razorpay_signature', ''),
                    amount_paise=payment_entity.get('amount'), currency=payment_entity.get('currency'),
                    method=PaymentAttempt.Method.CARD,  # Best guess; the webhook lacks method info
                )
                record.outcome = outcome.value
                logger.info("Webhook: Payment %s %s via %s", payment_id, outcome.value, event)
            elif event == 'payment.failed':
                changed = holds.fail_payment(payment_id)
                record.outcome = 'failed' if changed else 'no_change'
            else:
                record.outcome = 'ignored'
                logger.info("Webhook: unhandled event '%s' — ignoring", event)
            record.save(update_fields=['outcome'])

        # Always 200 once handled, so Razorpay stops retrying (flagged cases are for a person, not for retries).
        return Response({'status': record.outcome})


# ═══════════════════════════════════════════════════════════════════════════════
# 6. PaymentListView
# ═══════════════════════════════════════════════════════════════════════════════

class PaymentListView(generics.ListAPIView):
    """
    GET /api/v1/payments/list/

    Returns the authenticated student's own payment history.
    Only payments where booking.student == request.user are returned.
    """
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Payment.objects
            .filter(booking__student=self.request.user)
            .select_related('booking')
            .prefetch_related('attempts')
            .order_by('-created_at')
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 7. AdminPaymentListView
# ═══════════════════════════════════════════════════════════════════════════════

class AdminPaymentListView(TenantScopedQuerysetMixin, generics.ListAPIView):
    """
    GET /api/v1/payments/admin-list/

    Returns payments for all bookings on hostels owned by the authenticated user.
    TenantScopedQuerysetMixin filters by Payment.OWNER_LOOKUP =
    'booking__hostel__owner', scoping to the requesting user's hostels only.

    Optional query params:
      ?status=CREATED|PENDING|SUCCESS|FAILED|REFUNDED
    """
    serializer_class = AdminPaymentSerializer
    permission_classes = [IsAuthenticated]
    queryset = (
        Payment.objects
        .select_related('booking__hostel', 'booking__student')
        .prefetch_related('attempts')
    )

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param.upper())
        return qs.order_by('-created_at')


# ═══════════════════════════════════════════════════════════════════════════════
# 8. RefundView
# ═══════════════════════════════════════════════════════════════════════════════

class RefundView(APIView):
    """
    POST /api/v1/payments/refund/<uuid:payment_id>/

    Hostel owner initiates a refund for a captured payment.
    Tenant-scoped via get_tenant_scoped_object_or_404 — owner can only
    refund payments on their own hostels. IsTenantOwner is then checked
    explicitly (APIView doesn't call check_object_permissions on its own
    the way a generic view's get_object() would) as defense-in-depth: a
    request that somehow bypassed the scoped fetch above would still be
    rejected here.

    Body: {"amount": <decimal INR>}  — optional; omit for full refund.

    Calls Razorpay Refunds API, then sets Payment.status = REFUNDED.
    """
    permission_classes = [IsAuthenticated, IsTenantOwner]

    def post(self, request, payment_id):
        # Tenant-scoped — returns 404 if payment belongs to a different owner
        payment = get_tenant_scoped_object_or_404(Payment, payment_id, request)
        self.check_object_permissions(request, payment)

        # Default to the full amount if none is given. Money is handled as Decimal, never float.
        try:
            amount = Decimal(str(request.data.get('amount', payment.amount))).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError, TypeError):
            return Response({'error': 'Invalid refund amount.'}, status=status.HTTP_400_BAD_REQUEST)
        if not amount.is_finite() or amount <= 0:
            return Response({'error': 'The refund amount must be more than zero.'}, status=status.HTTP_400_BAD_REQUEST)

        # Step 1 (locked, no outside calls): check what is left to refund and reserve it. A second request for
        # the same money finds it reserved and never reaches Razorpay.
        with transaction.atomic():
            locked = Payment.objects.select_for_update(of=('self',)).get(pk=payment.pk)
            if locked.status == Payment.Status.REFUNDED:
                return Response({'error': 'This payment was already refunded in full.'},
                                status=status.HTTP_409_CONFLICT)
            if locked.status != Payment.Status.SUCCESS:
                return Response({'error': 'Only successful payments can be refunded.'},
                                status=status.HTTP_400_BAD_REQUEST)

            success_attempt = locked.attempts.filter(status=PaymentAttempt.Status.SUCCESS).first()
            if not success_attempt or not success_attempt.razorpay_payment_id:
                return Response(
                    {'error': 'No captured Razorpay payment ID found. Cannot initiate refund.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            reserved = locked.refunds.filter(
                status__in=[PaymentRefund.Status.RESERVED, PaymentRefund.Status.PROCESSED],
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            remaining = locked.amount - reserved
            if amount > remaining:
                return Response({'error': f'Only Rs {remaining} can still be refunded on this payment.'},
                                status=status.HTTP_409_CONFLICT)
            refund = PaymentRefund.objects.create(payment=locked, amount=amount)
            razorpay_payment_id = success_attempt.razorpay_payment_id

        # Step 2: the Razorpay call, with no lock held.
        try:
            refund_response = razorpay_client.initiate_refund(
                payment_id   = razorpay_payment_id,
                amount_paise = int(amount * 100),
                reference    = str(refund.id),
            )
        except razorpay_client.RefundRejected:
            refund.status = PaymentRefund.Status.FAILED
            refund.save(update_fields=['status', 'updated_at'])
            logger.exception("Razorpay rejected refund %s for payment %s", refund.id, payment.id)
            return Response({'error': 'The payment gateway rejected the refund.'}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            # Unknown outcome (timeout, gateway error): Razorpay may or may not have refunded. The reservation
            # stays so nobody can refund the same money again, and a person checks the dashboard.
            logger.exception("Razorpay refund %s for payment %s: outcome unknown", refund.id, payment.id)
            Payment.objects.filter(pk=payment.pk).update(
                needs_review=True,
                review_note=f'Refund request {refund.id} has an unknown outcome. Check the Razorpay dashboard.'[:200],
            )
            return Response(
                {'error': 'The refund request could not be confirmed. Please check again before retrying.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Step 3: record the result.
        with transaction.atomic():
            locked = Payment.objects.select_for_update(of=('self',)).get(pk=payment.pk)
            refund.status = PaymentRefund.Status.PROCESSED
            refund.razorpay_refund_id = refund_response.get('id')
            refund.save(update_fields=['status', 'razorpay_refund_id', 'updated_at'])
            locked.refunded_amount = locked.refunds.filter(
                status=PaymentRefund.Status.PROCESSED,
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            if locked.refunded_amount >= locked.amount:
                locked.status = Payment.Status.REFUNDED
            locked.save(update_fields=['refunded_amount', 'status', 'updated_at'])

        return Response({
            'success':         True,
            'refund_id':       refund_response.get('id'),
            'amount_refunded': str(amount),
            'status':          locked.status,
        })
