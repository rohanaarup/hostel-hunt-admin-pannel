from django.core.exceptions import ImproperlyConfigured

from ._lookups import scope_q


def tenant_scope_q(model, user):
    """
    Public helper for the rare view whose queryset can't simply inherit
    TenantScopedQuerysetMixin (e.g. it branches between a public/anonymous
    queryset and an owner-scoped one, like HostelViewSet). Returns the Q
    object TenantScopedQuerysetMixin would apply, built from the model's
    own declared OWNER_LOOKUP, so the relation path stays declared in
    exactly one place even when the mixin itself doesn't fit.
    """
    owner_lookup = getattr(model, "OWNER_LOOKUP", None)
    if not owner_lookup:
        raise ImproperlyConfigured(
            f"{model.__name__} must declare OWNER_LOOKUP to use tenant_scope_q."
        )
    return scope_q(owner_lookup, user)


def user_scope_q(model, user):
    """Same as tenant_scope_q, for the USER_LOOKUP/UserScopedModel side."""
    user_lookup = getattr(model, "USER_LOOKUP", None)
    if not user_lookup:
        raise ImproperlyConfigured(
            f"{model.__name__} must declare USER_LOOKUP to use user_scope_q."
        )
    return scope_q(user_lookup, user)


class TenantScopedQuerysetMixin:
    """
    Mixin for DRF generic views / ViewSets whose model inherits
    TenantScopedModel. Automatically restricts get_queryset() — and
    therefore get_object() — to records owned by the requesting user's
    tenant (hostel-owner) relationship, using the model's declared
    OWNER_LOOKUP. Add this as the leftmost base class on any view for a
    TenantScopedModel.

    Fail-closed: an unauthenticated request always gets an empty
    queryset, never an unscoped one.
    """

    def get_queryset(self):
        base_qs = super().get_queryset()
        model = base_qs.model
        owner_lookup = getattr(model, "OWNER_LOOKUP", None)
        if not owner_lookup:
            raise ImproperlyConfigured(
                f"{model.__name__} must declare OWNER_LOOKUP to use "
                f"TenantScopedQuerysetMixin."
            )
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            return base_qs.none()
        return base_qs.filter(scope_q(owner_lookup, user))


class UserScopedQuerysetMixin:
    """
    Mixin for DRF generic views / ViewSets whose model inherits
    UserScopedModel. Automatically restricts get_queryset() to records
    belonging to the requesting user directly (student-owned data), using
    the model's declared USER_LOOKUP.

    Fail-closed: an unauthenticated request always gets an empty
    queryset, never an unscoped one.
    """

    def get_queryset(self):
        base_qs = super().get_queryset()
        model = base_qs.model
        user_lookup = getattr(model, "USER_LOOKUP", None)
        if not user_lookup:
            raise ImproperlyConfigured(
                f"{model.__name__} must declare USER_LOOKUP to use "
                f"UserScopedQuerysetMixin."
            )
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            return base_qs.none()
        return base_qs.filter(scope_q(user_lookup, user))
