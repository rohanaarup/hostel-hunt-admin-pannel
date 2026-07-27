from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'

    def ready(self):
        # Register the system check that verifies every TenantScopedModel
        # subclass has declared OWNER_LOOKUP. This fires at server startup
        # via Django's check framework.
        import apps.core.checks  # noqa: F401
