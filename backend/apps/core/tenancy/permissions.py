from rest_framework.permissions import BasePermission

from ._lookups import scope_match


class IsTenantOwner(BasePermission):
    """
    Object-level permission: the requesting user must be the tenant
    (hostel owner) that the object's declared OWNER_LOOKUP resolves to.
    Consolidates what utils/permissions.py:IsOwner and
    apps/payments/permissions.py:IsHostelOwnerOfPayment used to do
    separately — this version walks the model's own OWNER_LOOKUP instead
    of duck-typing `obj.owner`/`obj.hostel.owner`, so it works at any
    relation depth (Bed, Payment, PaymentAttempt, ...) without a
    per-model fallback branch.

    This is always defense-in-depth, applied in addition to (never
    instead of) TenantScopedQuerysetMixin/get_scoped_object_or_404 —
    a request that somehow bypasses get_queryset() should still be
    rejected here.
    """

    message = "You do not have permission to access this resource."

    def has_object_permission(self, request, view, obj):
        owner_lookup = getattr(obj, "OWNER_LOOKUP", None)
        if not owner_lookup:
            return False
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return scope_match(obj, owner_lookup, user)


class IsResourceUser(BasePermission):
    """
    Object-level permission: the requesting user must be the user that
    the object's declared USER_LOOKUP resolves to. Consolidates what
    apps/payments/permissions.py:IsPaymentOwner used to do ad hoc — this
    version walks the model's own USER_LOOKUP instead of a hardcoded
    `obj.booking.student` comparison, so the same class works for
    Booking, Payment, Wishlist, and future models (Review) alike.

    Always defense-in-depth alongside
    UserScopedQuerysetMixin/get_scoped_object_or_404.
    """

    message = "You do not have permission to access this resource."

    def has_object_permission(self, request, view, obj):
        user_lookup = getattr(obj, "USER_LOOKUP", None)
        if not user_lookup:
            return False
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return scope_match(obj, user_lookup, user)
