from django.apps import apps
from django.core.checks import Error, Warning, register

from .models import TenantScopedModel, UserScopedModel, GlobalModel

# Every app whose models represent hostel/booking/student business data.
# Every concrete (non-abstract, non-proxy) model in one of these apps must
# inherit TenantScopedModel, UserScopedModel, or GlobalModel (an explicit
# "reviewed, intentionally unscoped" marker) — this is what stops a new
# model from silently shipping unscoped. Extend this list as new
# tenancy-relevant apps are added (e.g. 'reviews' when that app exists).
BUSINESS_APP_LABELS = {
    "hostels",
    "rooms",
    "bookings",
    "residents",
    "notices",
    "payments",
    "media_uploads",
}


@register()
def check_scoped_models_declare_lookup(app_configs, **kwargs):
    """
    Every model that already opted in to TenantScopedModel/UserScopedModel
    must actually declare OWNER_LOOKUP/USER_LOOKUP — inheriting the base
    with no lookup set is silently unscoped (get_queryset()/permission
    checks raise ImproperlyConfigured at request time rather than at
    startup, which is too late to catch in review).
    """
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
        if issubclass(model, UserScopedModel) and not getattr(model, "USER_LOOKUP", None):
            errors.append(
                Warning(
                    f"{model.__name__} inherits UserScopedModel but has "
                    f"not declared USER_LOOKUP. Data for this model will "
                    f"NOT be scoped to its user until this is fixed.",
                    id="core.W002",
                )
            )
    return errors


@register()
def check_business_models_are_classified(app_configs, **kwargs):
    """
    Every concrete model in a BUSINESS_APP_LABELS app must inherit one of
    TenantScopedModel, UserScopedModel, or GlobalModel. This is the check
    that actually prevents the "new model, forgot to scope it" bug class
    from coming back: it fails startup (Error, not Warning) rather than
    relying on someone remembering to add scoping when they add a model.

    A model that is legitimately unscoped (e.g. a lookup/reference table)
    should inherit GlobalModel to document that it was reviewed on
    purpose, rather than being left off this check's radar entirely.
    """
    errors = []
    for model in apps.get_models():
        if model._meta.app_label not in BUSINESS_APP_LABELS:
            continue
        if model._meta.proxy or model._meta.abstract:
            continue
        if issubclass(model, (TenantScopedModel, UserScopedModel, GlobalModel)):
            continue
        errors.append(
            Error(
                f"{model.__name__} (app '{model._meta.app_label}') does not "
                f"inherit TenantScopedModel, UserScopedModel, or GlobalModel. "
                f"Every model in a tenancy-relevant app must be explicitly "
                f"classified — see apps/core/tenancy/models.py.",
                id="core.E001",
            )
        )
    return errors
