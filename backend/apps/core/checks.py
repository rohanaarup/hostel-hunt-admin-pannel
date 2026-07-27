from django.apps import apps
from django.core.checks import Warning, register
from apps.core.models import TenantScopedModel


@register()
def check_tenant_scoped_models_declare_owner_lookup(app_configs, **kwargs):
    errors = []
    for model in apps.get_models():
        if issubclass(model, TenantScopedModel) and not getattr(model, "OWNER_LOOKUP", None):
            errors.append(
                Warning(
                    f"{model.__name__} inherits TenantScopedModel but has "
                    f"not declared OWNER_LOOKUP. Data for this model will "
                    f"NOT be scoped to its owner until this is fixed.",
                    id="core.W001",
                )
            )
    return errors
