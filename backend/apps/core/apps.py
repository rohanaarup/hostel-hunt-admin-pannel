from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'

    def ready(self):
        # Register the tenancy system checks (OWNER_LOOKUP/USER_LOOKUP
        # declared + every business-app model explicitly classified).
        # Fires at server startup via Django's check framework.
        import apps.core.tenancy.checks  # noqa: F401

        # Optional per-statement time limit on the web process (DB_STATEMENT_TIMEOUT_MS).
        from django.db.backends.signals import connection_created

        from apps.core.db_options import apply_statement_timeout
        connection_created.connect(apply_statement_timeout, dispatch_uid='hh-statement-timeout')

        # One Sentry alert when a payment is flagged for a person (L4-07), without touching the payment code.
        import logging

        from apps.core.sentry_config import PaymentFlagHandler

        payments_logger = logging.getLogger('apps.payments')
        if not any(isinstance(h, PaymentFlagHandler) for h in payments_logger.handlers):
            payments_logger.addHandler(PaymentFlagHandler())
