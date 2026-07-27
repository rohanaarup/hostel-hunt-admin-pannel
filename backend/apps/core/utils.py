from django.shortcuts import get_object_or_404
from django.core.exceptions import ImproperlyConfigured


def get_tenant_scoped_object_or_404(model, pk, request):
    """
    Fetch a single object by primary key, scoped to the requesting user via
    the model's declared OWNER_LOOKUP. Returns a standard Http404 if the
    object does not exist OR belongs to a different owner — the two cases
    are indistinguishable to the caller, which is intentional (do not leak
    existence of another owner's data).

    Use this inside any plain APIView's post()/patch()/delete() instead of
    hand-writing Model.objects.get(pk=pk) plus a manual ownership check.
    """
    owner_lookup = getattr(model, "OWNER_LOOKUP", None)
    if not owner_lookup:
        raise ImproperlyConfigured(
            f"{model.__name__} must declare OWNER_LOOKUP to use "
            f"get_tenant_scoped_object_or_404."
        )
    queryset = model.objects.filter(**{owner_lookup: request.user})
    return get_object_or_404(queryset, pk=pk)
