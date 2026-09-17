from django.shortcuts import get_object_or_404
from django.core.exceptions import ImproperlyConfigured

from ._lookups import scope_q


def get_scoped_object_or_404(model, pk, request, kind="tenant"):
    """
    Fetch a single object by primary key, scoped to the requesting user —
    via the model's declared OWNER_LOOKUP (kind="tenant", the default) or
    USER_LOOKUP (kind="user"). Returns a standard Http404 if the object
    does not exist OR belongs to a different owner/user — the two cases
    are indistinguishable to the caller, which is intentional (do not
    leak existence of another tenant's/user's data).

    Use this inside any plain APIView's post()/patch()/delete() instead of
    hand-writing Model.objects.get(pk=pk) plus a manual ownership check.
    This is the single detail-view counterpart to
    TenantScopedQuerysetMixin/UserScopedQuerysetMixin — always use it (or
    those mixins) rather than an unscoped get_object_or_404, so list and
    detail access are checked the same way.
    """
    attr = "OWNER_LOOKUP" if kind == "tenant" else "USER_LOOKUP"
    lookup = getattr(model, attr, None)
    if not lookup:
        raise ImproperlyConfigured(
            f"{model.__name__} must declare {attr} to use "
            f"get_scoped_object_or_404(kind={kind!r})."
        )
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        from django.http import Http404
        raise Http404
    queryset = model.objects.filter(scope_q(lookup, user))
    return get_object_or_404(queryset, pk=pk)


def get_tenant_scoped_object_or_404(model, pk, request):
    """Back-compat wrapper — see get_scoped_object_or_404."""
    return get_scoped_object_or_404(model, pk, request, kind="tenant")


def get_user_scoped_object_or_404(model, pk, request):
    """Back-compat-shaped wrapper — see get_scoped_object_or_404."""
    return get_scoped_object_or_404(model, pk, request, kind="user")


def is_tenant_owner(obj, user):
    """
    True if `user` is the tenant (hostel owner) that `obj` (any
    TenantScopedModel instance) belongs to, per its own declared
    OWNER_LOOKUP. For validating a client-supplied *parent* object at
    create time — e.g. "does the hostel/room this MediaItem is being
    attached to belong to the requesting user?" — before the MediaItem
    itself exists to run a queryset/permission check against.
    """
    from ._lookups import scope_match
    owner_lookup = getattr(obj, "OWNER_LOOKUP", None)
    if not owner_lookup or user is None or not user.is_authenticated:
        return False
    return scope_match(obj, owner_lookup, user)


def is_resource_user(obj, user):
    """User-scope counterpart to is_tenant_owner — see its docstring."""
    from ._lookups import scope_match
    user_lookup = getattr(obj, "USER_LOOKUP", None)
    if not user_lookup or user is None or not user.is_authenticated:
        return False
    return scope_match(obj, user_lookup, user)
