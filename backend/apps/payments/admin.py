"""
apps/payments/admin.py
----------------------
Read-only Django Admin registration for Payment and PaymentAttempt.

Design decisions:
  - No add/delete permissions: payment records are created exclusively via the
    API (CreateOrderView) and Razorpay webhook.  Creating or deleting rows
    manually could desync the DB from Razorpay's state.
  - PaymentAttemptInline is nested inside PaymentAdmin for a full audit view.
  - Refunds must go through RefundView (which calls Razorpay's API); the admin
    does NOT expose a refund action to prevent bypassing the API.
"""

from django.contrib import admin
from .models import Payment, PaymentAttempt


class PaymentAttemptInline(admin.TabularInline):
    """Inline showing all method attempts for a given Payment."""
    model = PaymentAttempt
    extra = 0
    readonly_fields = (
        'id', 'method', 'razorpay_payment_id', 'razorpay_signature',
        'status', 'created_at',
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """
    Read-only admin for Razorpay Payment records.

    Provides full visibility into order status, amounts, and attempt history
    without allowing manual creation, deletion, or field edits — all state
    changes must flow through the API / webhook to stay in sync with Razorpay.
    """

    list_display = (
        'id', 'razorpay_order_id', 'booking', 'amount', 'currency',
        'status', 'verified_at', 'created_at',
    )
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('razorpay_order_id', 'booking__student_name', 'booking__student_phone')
    readonly_fields = (
        'id', 'booking', 'razorpay_order_id', 'amount', 'currency',
        'status', 'verified_at', 'created_at', 'updated_at',
    )
    inlines = [PaymentAttemptInline]
    ordering = ['-created_at']

    def has_add_permission(self, request):
        """Prevent manual creation — orders must be created via CreateOrderView."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion — records must be retained for audit and reconciliation."""
        return False


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    """
    Stand-alone read-only admin for PaymentAttempt records.
    Also accessible inline via PaymentAdmin above.
    """

    list_display = (
        'id', 'payment', 'method', 'razorpay_payment_id', 'status', 'created_at',
    )
    list_filter = ('status', 'method', 'created_at')
    search_fields = ('razorpay_payment_id', 'payment__razorpay_order_id')
    readonly_fields = (
        'id', 'payment', 'method', 'razorpay_payment_id',
        'razorpay_signature', 'status', 'created_at',
    )
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
