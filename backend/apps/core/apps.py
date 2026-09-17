from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'

    def ready(self):
        # Register the tenancy system checks (OWNER_LOOKUP/USER_LOOKUP
        # declared + every business-app model explicitly classified).
        # Fires at server startup via Django's check framework.
        import apps.core.tenancy.checks  # noqa: F401
