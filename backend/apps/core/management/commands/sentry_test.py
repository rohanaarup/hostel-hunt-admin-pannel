from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Send one synthetic test error to Sentry to prove the pipeline works. "
        "Run locally with SENTRY_DSN set (and SENTRY_ENVIRONMENT=test to keep it apart "
        "from production events). No web endpoint is involved."
    )

    def handle(self, *args, **options):
        if not settings.SENTRY_DSN:
            raise CommandError("SENTRY_DSN is not set. Set it in the environment, then run again.")
        import sentry_sdk

        sentry_sdk.set_tag('synthetic', 'true')
        event_id = sentry_sdk.capture_exception(Exception('Sentry test error (synthetic, safe to ignore)'))
        sentry_sdk.flush(timeout=5)
        self.stdout.write(f"Sent synthetic test error to Sentry (event id {event_id}). Check the project's Issues.")
