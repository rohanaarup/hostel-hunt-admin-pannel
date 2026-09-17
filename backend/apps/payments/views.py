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

import logging
from datetime import timedelta

from django.conf import settings as django_settings
from django.db import transaction
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Booking
from apps.rooms.models import Bed
from apps.core.querysets import TenantScopedQuerysetMixin
from apps.core.utils import get_tenant_scoped_object_or_404

from .models import Payment, PaymentAttempt
from apps.core.tenancy.permissions import IsTenantOwner, IsResourceUser
from .serializers import PaymentSerializer, AdminPaymentSerializer
from .services import razorpay_client

logger = logging.getLogger('apps.payments')

# ─── Constants ─────────────────────────────────────────────────────────────────

BED_HOLD_MINUTES = 15

# Map Flutter-facing app names → PaymentAttempt.Method enum values
UPI_APP_TO_METHOD = {
    'gpay':    PaymentAttempt.Method.UPI_GPAY,
    'phonepe': PaymentAttempt.Method.UPI_PHONEPE,
    'paytm':   PaymentAttempt.Method.UPI_PAYTM,
}


# ─── Shared helper ─────────────────────────────────────────────────────────────

def _confirm_payment_atomic(payment, attempt, razorpay_payment_id, signature):
    """
    Single atomic transaction that confirms a payment as fully captured.

    Steps (all-or-nothing):
      1. PaymentAttempt → SUCCESS + set razorpay_payment_id + signature
      2. Payment        → SUCCESS + set verified_at
      3. Booking        → status='paid' + marked_paid_at
      4. Bed            → held_until=None, is_available=False

    Called by both VerifyPaymentView (card callback) and WebhookView
    (payment.captured / order.paid events) to ensure identical behaviour
    regardless of which path triggered the confirmation.
    """
    with transaction.atomic():
        now = timezone.now()

        # 1. Attempt
        attempt.razorpay_payment_id = razorpay_payment_id
        attempt.razorpay_signature  = signature or ''
        attempt.status = PaymentAttempt.Status.SUCCESS
        attempt.save(update_fields=['razorpay_payment_id', 'razorpay_signature', 'status'])

        # 2. Payment
        payment.status      = Payment.Status.SUCCESS
        payment.verified_at = now
        payment.save(update_fields=['status', 'verified_at', 'updated_at'])

        # 3. Booking
        booking = payment.booking
        booking.status         = 'paid'
        booking.marked_paid_at = now
        booking.save(update_fields=['status', 'marked_paid_at', 'updated_at'])

        # 4. Bed — release hold into a confirmed (unavailable) booking
        if booking.room and booking.bed_number:
            try:
                Bed.objects.filter(
                    room=booking.room,
                    bed_number=int(booking.bed_number),
                ).update(is_available=False, held_until=None)
            except (ValueError, TypeError):
                logger.warning(
                    "Could not update Bed for booking %s: invalid bed_number '%s'",
                    booking.id, booking.bed_number,
                )

    logger.info("Payment %s confirmed SUCCESS (razorpay_payment_id=%s)", payment.id, razorpay_payment_id)


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
            if existing_bed and existing_bed.held_until and existing_bed.held_until > now:
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
                bed.held_until = recheck_now + timedelta(minutes=BED_HOLD_MINUTES)
                bed.save(update_fields=['held_until'])

                payment = Payment.objects.create(
                    booking=booking,
                    razorpay_order_id=order['id'],
                    amount=amount_inr,
                    currency=order.get('currency', 'INR'),
                    status=Payment.Status.CREATED,
                )

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

        with transaction.atomic():
            attempt = PaymentAttempt.objects.create(
                payment=payment,
                method=method,
                status=PaymentAttempt.Status.INITIATED,
            )
            if payment.status == Payment.Status.CREATED:
                payment.status = Payment.Status.PENDING
                payment.save(update_fields=['status', 'updated_at'])

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

        card_config = razorpay_client.get_card_checkout_session(payment.razorpay_order_id)

        with transaction.atomic():
            attempt = PaymentAttempt.objects.create(
                payment=payment,
                method=PaymentAttempt.Method.CARD,
                status=PaymentAttempt.Status.INITIATED,
            )
            if payment.status == Payment.Status.CREATED:
                payment.status = Payment.Status.PENDING
                payment.save(update_fields=['status', 'updated_at'])

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

        # Find or create the CARD attempt to attach the ids to
        attempt, _ = PaymentAttempt.objects.get_or_create(
            payment=payment,
            method=PaymentAttempt.Method.CARD,
            status=PaymentAttempt.Status.INITIATED,
        )

        _confirm_payment_atomic(payment, attempt, razorpay_payment_id, razorpay_signature)

        return Response({'success': True, 'status': Payment.Status.SUCCESS})


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

        # ── Find our Payment ──────────────────────────────────────────────────
        try:
            payment = Payment.objects.select_related(
                'booking__room', 'booking__student'
            ).get(razorpay_order_id=razorpay_order_id)
        except Payment.DoesNotExist:
            logger.warning("Webhook: no Payment found for order_id=%s", razorpay_order_id)
            return Response({'status': 'unknown_order'})

        # ── Handle event ──────────────────────────────────────────────────────
        if event in ('payment.captured', 'order.paid'):
            # Idempotency check — if already SUCCESS, do nothing
            if payment.status == Payment.Status.SUCCESS:
                logger.info(
                    "Webhook: Payment %s already SUCCESS — idempotent 200", payment.id
                )
                return Response({'status': 'already_processed'})

            # Find an existing INITIATED attempt or create one
            # (the attempt may not exist yet if the webhook arrives before
            #  the client even calls InitiateUpiIntentView/InitiateCardCheckoutView)
            attempt = PaymentAttempt.objects.filter(
                payment=payment,
                status=PaymentAttempt.Status.INITIATED,
            ).first()

            if attempt is None:
                attempt = PaymentAttempt.objects.create(
                    payment=payment,
                    method=PaymentAttempt.Method.CARD,  # Best guess; webhook lacks method info
                    status=PaymentAttempt.Status.INITIATED,
                )

            signature = payment_entity.get('razorpay_signature', '')
            _confirm_payment_atomic(payment, attempt, razorpay_payment_id, signature)
            logger.info("Webhook: Payment %s → SUCCESS via %s", payment.id, event)

        elif event == 'payment.failed':
            if payment.status not in (Payment.Status.SUCCESS, Payment.Status.REFUNDED):
                with transaction.atomic():
                    # Mark all open attempts as FAILED
                    PaymentAttempt.objects.filter(
                        payment=payment,
                        status=PaymentAttempt.Status.INITIATED,
                    ).update(status=PaymentAttempt.Status.FAILED)

                    payment.status = Payment.Status.FAILED
                    payment.save(update_fields=['status', 'updated_at'])

                    # Release bed hold
                    booking = payment.booking
                    if booking.room and booking.bed_number:
                        try:
                            Bed.objects.filter(
                                room=booking.room,
                                bed_number=int(booking.bed_number),
                            ).update(held_until=None)
                        except (ValueError, TypeError):
                            pass

                logger.info("Webhook: Payment %s → FAILED via payment.failed event", payment.id)
        else:
            logger.info("Webhook: unhandled event '%s' — ignoring", event)

        return Response({'status': 'ok'})


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

        if payment.status != Payment.Status.SUCCESS:
            return Response(
                {'error': 'Only successful payments can be refunded.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Default to full refund if amount not specified
        amount_inr = request.data.get('amount', payment.amount)
        try:
            amount_paise = int(float(amount_inr) * 100)
        except (ValueError, TypeError):
            return Response({'error': 'Invalid refund amount.'}, status=status.HTTP_400_BAD_REQUEST)

        # Find the successful attempt to get the Razorpay payment ID
        success_attempt = payment.attempts.filter(
            status=PaymentAttempt.Status.SUCCESS
        ).first()

        if not success_attempt or not success_attempt.razorpay_payment_id:
            return Response(
                {'error': 'No captured Razorpay payment ID found. Cannot initiate refund.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            refund_response = razorpay_client.initiate_refund(
                payment_id   = success_attempt.razorpay_payment_id,
                amount_paise = amount_paise,
            )
        except Exception as exc:
            logger.exception("Razorpay refund failed for payment %s: %s", payment.id, exc)
            return Response(
                {'error': 'Refund initiation failed. Please try again.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        payment.status = Payment.Status.REFUNDED
        payment.save(update_fields=['status', 'updated_at'])

        return Response({
            'success':         True,
            'refund_id':       refund_response.get('id'),
            'amount_refunded': str(amount_inr),
            'status':          payment.status,
        })
