from django.core.exceptions import ImproperlyConfigured


class TenantScopedQuerysetMixin:
    """
    Mixin for DRF generic views / ViewSets whose model inherits
    TenantScopedModel. Automatically restricts get_queryset() — and
    therefore get_object() — to records owned by the requesting user,
    using the model's declared OWNER_LOOKUP. Add this as the leftmost
    base class on any view for a TenantScopedModel.
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
        return base_qs.filter(**{owner_lookup: self.request.user})
