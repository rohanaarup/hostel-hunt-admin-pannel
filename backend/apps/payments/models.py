"""
apps/payments/models.py
-----------------------
Razorpay payment data models for Hostel Hunt.

Role in the payment flow:
  1. Payment — one row per Razorpay order, created by CreateOrderView.
               Tracks the overall order lifecycle (CREATED → SUCCESS / FAILED / REFUNDED).
  2. PaymentAttempt — one row per payment-method tried within a single Payment.
                      A student may try GPay, then fall back to a card; each try
                      is a separate PaymentAttempt linked to the same Payment.

NOTE: The old offline-payment model (amount_due/amount_paid/mode) has been
      deliberately removed.  Offline payment tracking (cash/bank-transfer) is
      handled directly on the Booking model (payment_mode='offline', status='paid').
"""

import uuid
from django.db import models
from apps.bookings.models import Booking
from apps.core.models import TenantScopedModel, UserScopedModel


# ─────────────────────────────────────────────────────────────────────────────
# Payment
# ─────────────────────────────────────────────────────────────────────────────

class Payment(TenantScopedModel, UserScopedModel):
    """
    One Razorpay *order* created when a student initiates online payment.

    Lifecycle:
      CREATED  → order placed with Razorpay, bed hold set on Bed.held_until
      PENDING  → student has launched a UPI app / card flow (at least one attempt)
      SUCCESS  → payment captured and verified (signature check passed)
      FAILED   → all attempts failed or the order expired
      REFUNDED → successful payment later refunded by the hostel owner

    Dual-scope: the hostel owner sees payments for their hostel's bookings
    (OWNER_LOOKUP); the student who made the booking sees their own
    (USER_LOOKUP). See apps/core/tenancy/models.py.
    """

    OWNER_LOOKUP = "booking__hostel__owner"
    USER_LOOKUP = "booking__student"

    class Status(models.TextChoices):
        CREATED  = 'CREATED',  'Created'
        PENDING  = 'PENDING',  'Pending'
        SUCCESS  = 'SUCCESS',  'Success'
        FAILED   = 'FAILED',   'Failed'
        REFUNDED = 'REFUNDED', 'Refunded'

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_column='payment_id'
    )
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='payments',
    )
    razorpay_order_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Razorpay order ID returned by the Orders API (e.g. order_XXXX).",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount in INR (rupees, not paise). Computed server-side from Room.price_per_month.",
    )
    currency = models.CharField(max_length=10, default='INR')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CREATED,
        db_index=True,
    )
    verified_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Timestamp when signature verification succeeded.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.razorpay_order_id} [{self.status}] — Booking {self.booking_id}"


# ─────────────────────────────────────────────────────────────────────────────
# PaymentAttempt
# ─────────────────────────────────────────────────────────────────────────────

class PaymentAttempt(TenantScopedModel, UserScopedModel):
    """
    One row per payment *method* tried within a Payment.

    A student may try Google Pay (INITIATED, then FAILED), then try their card
    (INITIATED → SUCCESS).  Both attempts are linked to the same Payment row.

    razorpay_payment_id is set only once Razorpay confirms / fails the charge.
    razorpay_signature  is set only on SUCCESS.

    Not directly exposed by any view today — only ever touched via
    payment.attempts off an already-scoped Payment. Classified here (with
    the same dual-scope shape as Payment, one hop further out) so it's
    covered by the startup check the moment a direct view is ever added.
    """

    OWNER_LOOKUP = "payment__booking__hostel__owner"
    USER_LOOKUP = "payment__booking__student"

    class Method(models.TextChoices):
        UPI_GPAY    = 'UPI_GPAY',    'Google Pay'
        UPI_PHONEPE = 'UPI_PHONEPE', 'PhonePe'
        UPI_PAYTM   = 'UPI_PAYTM',   'Paytm'
        CARD        = 'CARD',        'Credit / Debit Card'

    class Status(models.TextChoices):
        INITIATED = 'INITIATED', 'Initiated'
        SUCCESS   = 'SUCCESS',   'Success'
        FAILED    = 'FAILED',    'Failed'

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='attempts',
    )
    method = models.CharField(
        max_length=20,
        choices=Method.choices,
    )
    razorpay_payment_id = models.CharField(
        max_length=100,
        null=True, blank=True,
        unique=True,
        help_text="Razorpay payment ID (pay_XXXX). Set once Razorpay processes the attempt.",
    )
    razorpay_signature = models.CharField(
        max_length=256,
        null=True, blank=True,
        help_text="HMAC-SHA256 signature from Razorpay. Set only on SUCCESS.",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INITIATED,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payment_attempts'
        ordering = ['-created_at']

    def __str__(self):
        return f"Attempt {self.method} [{self.status}] — {self.payment_id}"
