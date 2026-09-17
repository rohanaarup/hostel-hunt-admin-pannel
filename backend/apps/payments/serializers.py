"""
apps/payments/serializers.py
-----------------------------
Three serializer tiers for the payment flow:

  PaymentAttemptSerializer  — embeds into Payment serializers; read-only.
  PaymentSerializer         — student-facing; hides server-only fields (verified_at).
  AdminPaymentSerializer    — owner-facing; adds booking/student summary fields.

Design decisions:
  - razorpay_order_id is read-only on both serializers — never set by client.
  - razorpay_payment_id and razorpay_signature on PaymentAttempt are write-never
    (only set by VerifyPaymentView / WebhookView internals).
  - RAZORPAY_KEY_SECRET and RAZORPAY_WEBHOOK_SECRET are NOT referenced here.
    They must never appear in any serializer or API response.
"""

from rest_framework import serializers
from .models import Payment, PaymentAttempt


# ─── PaymentAttemptSerializer ─────────────────────────────────────────────────

class PaymentAttemptSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for individual payment method attempts.
    Embedded inside PaymentSerializer and AdminPaymentSerializer.

    Note: razorpay_signature is deliberately excluded — it is server-internal
    and has no value in any client-facing response.
    """

    class Meta:
        model = PaymentAttempt
        fields = [
            'id',
            'method',
            'razorpay_payment_id',
            'status',
            'created_at',
        ]
        read_only_fields = fields


# ─── PaymentSerializer (student-facing) ──────────────────────────────────────

class PaymentSerializer(serializers.ModelSerializer):
    """
    Student-facing read-only serializer for Payment.

    Includes:
      - All fields the Flutter app needs to display payment status and history.
      - Embedded attempts list.

    Excludes:
      - verified_at (internal audit field, not needed by the student UI).
      - updated_at  (not needed by the student UI).
    """

    attempts = PaymentAttemptSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id',
            'booking',
            'razorpay_order_id',
            'amount',
            'currency',
            'status',
            'created_at',
            'attempts',
        ]
        read_only_fields = fields


# ─── AdminPaymentSerializer (owner-facing) ────────────────────────────────────

class AdminPaymentSerializer(serializers.ModelSerializer):
    """
    Owner-facing serializer for Payment, used by AdminPaymentListView and
    RefundView.

    Adds booking/student summary fields so the admin panel can display
    who made the payment and for which hostel — without requiring the
    client to make additional API calls for each payment record.
    """

    attempts = PaymentAttemptSerializer(many=True, read_only=True)

    # Booking / student summary fields
    student_name  = serializers.CharField(source='booking.student_name',  read_only=True)
    student_phone = serializers.CharField(source='booking.student_phone', read_only=True)
    hostel_name   = serializers.CharField(source='booking.hostel.name',   read_only=True)
    room_number   = serializers.CharField(source='booking.room_number',   read_only=True)
    bed_number    = serializers.CharField(source='booking.bed_number',    read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id',
            'booking',
            'razorpay_order_id',
            'amount',
            'currency',
            'status',
            'verified_at',
            'created_at',
            'updated_at',
            # Booking summary
            'student_name',
            'student_phone',
            'hostel_name',
            'room_number',
            'bed_number',
            'attempts',
        ]
        read_only_fields = fields
