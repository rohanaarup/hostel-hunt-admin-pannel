"""
Decides whether the load test may run against a given server. Pure functions, no Locust import, so
the rules are unit-tested (backend/apps/core/test_f7.py).

The rule: run against STAGING (or this computer) only.
  * The production host is refused unless HH_LOADTEST_ALLOW_PRODUCTION=yes is set, and then a warning is printed.
  * Any other host must be on the staging allow-list AND its /healthz must say env == "staging".
    A server that cannot tell us what it is (an old build without /healthz, no answer) is refused.
"""
from urllib.parse import urlparse

PRODUCTION_HOSTS = {'hostel-hunt-backend.onrender.com'}
DEFAULT_STAGING_HOSTS = {'hostel-hunt-admin-pannel.onrender.com'}
LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1'}
ALLOW_PRODUCTION_VARIABLE = 'HH_LOADTEST_ALLOW_PRODUCTION'
STAGING_HOSTS_VARIABLE = 'HH_LOADTEST_STAGING_HOSTS'

PRODUCTION_WARNING = (
    "WARNING: HH_LOADTEST_ALLOW_PRODUCTION=yes. This run will send load to a PRODUCTION host. "
    "It will log in as test students, create bookings and may slow the real service. Stop now if that is not what you meant."
)


def host_of(url):
    return (urlparse(url if '//' in url else f'//{url}').hostname or '').lower()


def staging_hosts(environ):
    extra = {h.strip().lower() for h in environ.get(STAGING_HOSTS_VARIABLE, '').split(',') if h.strip()}
    return DEFAULT_STAGING_HOSTS | extra


def production_allowed(environ):
    return environ.get(ALLOW_PRODUCTION_VARIABLE, '').strip().lower() == 'yes'


def check_target(url, environ, reported_env=None):
    """Returns (allowed, message). `reported_env` is what the server's /healthz said (None if it did not say)."""
    host = host_of(url)
    if not host:
        return False, 'No target host. Pass --host https://<staging host>.'
    if host in PRODUCTION_HOSTS:
        if production_allowed(environ):
            return True, PRODUCTION_WARNING
        return False, (
            f'Refusing to load-test the PRODUCTION host {host}. Load tests run against staging only. '
            f'(To override on purpose, set {ALLOW_PRODUCTION_VARIABLE}=yes; a warning is printed.)'
        )
    if production_allowed(environ):
        return True, PRODUCTION_WARNING
    if host in LOCAL_HOSTS:
        return True, ''
    if host not in staging_hosts(environ):
        return False, (
            f'Refusing to run against {host}: it is not a known staging host. '
            f'Add it to {STAGING_HOSTS_VARIABLE} (comma separated) if it really is staging.'
        )
    if reported_env != 'staging':
        return False, (
            f'Refusing to run against {host}: its /healthz says env={reported_env!r}, not "staging" '
            '(an old build without /healthz also lands here).'
        )
    return True, ''
