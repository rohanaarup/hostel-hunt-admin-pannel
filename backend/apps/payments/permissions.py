"""
apps/payments/permissions.py
-----------------------------
Custom DRF permission classes for the payments app.

Two distinct personas access payment data:
  - Student (IsPaymentOwner):
      Can only read/interact with Payment rows linked to their own Booking.
      Prevents cross-student payment access.

  - Hostel Owner (IsHostelOwnerOfPayment):
      Can view Payments for bookings on hostels they own.
      Follows the same tenant-scoping pattern as TenantScopedModel /
      TenantScopedQuerysetMixin used throughout the codebase.
      Used by AdminPaymentListView and RefundView (list-level scoping is
      handled by the view's get_queryset; this class provides object-level
      protection on detail/action views).
"""

from rest_framework.permissions import BasePermission


class IsPaymentOwner(BasePermission):
    """
    Object-level permission: student may only access Payment objects that are
    linked to a Booking whose student field matches request.user.

    Usage:
        permission_classes = [IsAuthenticated, IsPaymentOwner]
    """

    message = "You do not have permission to access this payment."

    def has_object_permission(self, request, view, obj):
        return obj.booking.student == request.user


class IsHostelOwnerOfPayment(BasePermission):
    """
    Object-level permission: hostel owner may only access Payment objects for
    bookings on hostels that they own (OWNER_LOOKUP = booking__hostel__owner).

    List-level scoping is handled by TenantScopedQuerysetMixin or a custom
    get_queryset(); this class provides an extra guard for detail-level views.

    Usage:
        permission_classes = [IsAuthenticated, IsHostelOwnerOfPayment]
    """

    message = "You do not have permission to access payments for this hostel."

    def has_object_permission(self, request, view, obj):
        return obj.booking.hostel.owner == request.user
