"""
Sentry setup and scrubbing.

Sentry is initialised only when SENTRY_DSN is set. Nothing personal may leave:
send_default_pii is off, request bodies and local variables are never sent, and
scrub_event() removes sensitive headers, bodies, query strings, user details and
masks emails and phone-like numbers in any text before an event is sent.
"""
import logging

from apps.core.privacy import mask_text  # noqa: F401  (re-exported)

FILTERED = '[Filtered]'

_DROP_HEADERS = frozenset({
    'authorization', 'proxy-authorization', 'cookie', 'set-cookie', 'x-forwarded-for',
    'x-real-ip', 'user-agent',
})
_SENSITIVE_EXACT = frozenset({
    'otp', 'otp_code', 'identifier', 'email', 'phone', 'phone_number', 'verification_token',
    'razorpay_signature', 'access', 'refresh', 'csrftoken', 'sessionid', 'api_key',
})
_SENSITIVE_PARTS = ('password', 'passwd', 'token', 'secret', 'authorization', 'signature')
EXTRA_DENYLIST = sorted(_SENSITIVE_EXACT)

_NOISY_LOGGERS = frozenset({'django.security.DisallowedHost'})


def _is_sensitive(key):
    key = str(key).lower()
    return key in _SENSITIVE_EXACT or any(part in key for part in _SENSITIVE_PARTS)


def _clean(value):
    """Filter sensitive keys and mask text, recursively."""
    if isinstance(value, dict):
        return {k: (FILTERED if _is_sensitive(k) else _clean(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, str):
        return mask_text(value)
    return value


def _is_noise(event, hint):
    from django.core.exceptions import DisallowedHost, PermissionDenied
    from django.http import Http404

    if event.get('logger') in _NOISY_LOGGERS:
        return True
    exc_info = (hint or {}).get('exc_info')
    return bool(exc_info and exc_info[0] and issubclass(exc_info[0], (Http404, PermissionDenied, DisallowedHost)))


def scrub_event(event, hint):
    if _is_noise(event, hint):
        return None

    request = event.get('request')
    if isinstance(request, dict):
        headers = request.get('headers')
        if isinstance(headers, dict):
            request['headers'] = {k: v for k, v in headers.items() if str(k).lower() not in _DROP_HEADERS}
        elif isinstance(headers, list):
            request['headers'] = [h for h in headers if str(h[0]).lower() not in _DROP_HEADERS]
        for key in ('cookies', 'data', 'query_string', 'env'):
            request.pop(key, None)
        if isinstance(request.get('url'), str):
            request['url'] = request['url'].split('?', 1)[0].split('#', 1)[0]

    user = event.get('user')
    if isinstance(user, dict):
        event['user'] = {'id': user['id']} if user.get('id') is not None else {}

    for key in ('extra', 'contexts'):
        if key in event:
            event[key] = _clean(event[key])

    for key in ('message', 'transaction'):
        if isinstance(event.get(key), str):
            event[key] = mask_text(event[key])
    logentry = event.get('logentry')
    if isinstance(logentry, dict):
        event['logentry'] = {k: _clean(v) for k, v in logentry.items()}
    exceptions = (event.get('exception') or {}).get('values') or []
    for exc in exceptions:
        if isinstance(exc.get('value'), str):
            exc['value'] = mask_text(exc['value'])
    for crumb in (event.get('breadcrumbs') or {}).get('values') or []:
        scrub_breadcrumb(crumb, None)
    return event


def scrub_breadcrumb(crumb, hint):
    if isinstance(crumb.get('message'), str):
        crumb['message'] = mask_text(crumb['message'])
    if isinstance(crumb.get('data'), dict):
        crumb['data'] = _clean(crumb['data'])
    return crumb


def init_sentry(dsn, environment, release, traces_sample_rate):
    """Initialise Sentry. Returns False (and does nothing) when no DSN is set."""
    if not dsn:
        return False
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration, ignore_logger
    from sentry_sdk.scrubber import DEFAULT_DENYLIST, DEFAULT_PII_DENYLIST, EventScrubber

    # The request log line is already structured; do not turn its 5xx lines into events.
    ignore_logger('hh.request')
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release or None,
        traces_sample_rate=traces_sample_rate,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size='never',
        event_scrubber=EventScrubber(
            denylist=list(DEFAULT_DENYLIST) + EXTRA_DENYLIST,
            pii_denylist=list(DEFAULT_PII_DENYLIST),
            recursive=True,
        ),
        before_send=scrub_event,
        before_breadcrumb=scrub_breadcrumb,
        integrations=[
            DjangoIntegration(
                transaction_style='url', middleware_spans=False, signals_spans=False, cache_spans=False,
            ),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )
    return True
