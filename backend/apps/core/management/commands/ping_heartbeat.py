"""
Management command: ping_heartbeat

Runs another management command, then tells a heartbeat monitor (Healthchecks, Better Stack, Cronitor and the
like) whether it worked, so a cron job that stops, or fails, raises an alert (F2-02).

  python manage.py ping_heartbeat cleanup_expired            # the form the Render cron uses
  python manage.py ping_heartbeat cleanup_expired --dry-run  # everything after the name goes to that command

  HEARTBEAT_URL       GET after the command succeeds. The URL holds a secret token: it is never printed or logged.
  HEARTBEAT_FAIL_URL  GET after it fails. Default: HEARTBEAT_URL with "/fail" added (Healthchecks and Better Stack).

With no HEARTBEAT_URL the command is simply run. The monitor being down never changes the job's result, and a
failed job still fails (exit code, Render's own run history). The pings go through apps/core/outbound.py (6 s at most).
"""
import argparse
import logging

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.core import outbound

logger = logging.getLogger('apps.core.heartbeat')


def fail_url():
    explicit = getattr(settings, 'HEARTBEAT_FAIL_URL', '')
    if explicit:
        return explicit
    base, sep, query = settings.HEARTBEAT_URL.partition('?')
    return base.rstrip('/') + '/fail' + sep + query


def ping(url):
    """Never raises, never shows the URL (it carries the monitor's token, and requests puts it in error text)."""
    try:
        outbound.get(url)
    except Exception as exc:  # noqa: BLE001
        logger.warning('Heartbeat ping failed (%s)', type(exc).__name__)


class Command(BaseCommand):
    help = "Run a management command, then ping HEARTBEAT_URL (success) or its fail URL (failure)."

    def add_arguments(self, parser):
        parser.add_argument('command_name', help="The management command to run, e.g. cleanup_expired.")
        parser.add_argument('command_args', nargs=argparse.REMAINDER, help="Arguments passed on to that command.")

    def handle(self, *args, **options):
        monitored = bool(getattr(settings, 'HEARTBEAT_URL', ''))
        try:
            call_command(options['command_name'], *options['command_args'])
        except SystemExit as exc:
            # cleanup_expired ends with SystemExit("... steps failed") when one step failed.
            if exc.code in (None, 0):
                if monitored:
                    ping(settings.HEARTBEAT_URL)
                return
            if monitored:
                ping(fail_url())
            raise
        except Exception:
            if monitored:
                ping(fail_url())
            raise
        if monitored:
            ping(settings.HEARTBEAT_URL)
