"""
Request id and one structured log line per request.

RequestLogMiddleware sits first in MIDDLEWARE so its timer also covers every
other middleware. Per request it emits a single JSON line on the `hh.request`
logger (stdout) with latency, route template, status, database query count and
time, response size, in-flight requests and the internal user id.

Privacy: the line never contains the path, query string, headers (so no
Authorization, Cookie, User-Agent or IP), request or response bodies, emails,
phone numbers, tokens or OTPs. `route` is the URL template, not the real path.
"""
import contextvars
import hashlib
import hmac
import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone

from django.conf import settings
from django.db import connection
from django.utils.functional import LazyObject, empty

from apps.core.privacy import mask_text

logger = logging.getLogger('hh.request')

_request_id = contextvars.ContextVar('hh_request_id', default='-')
_VALID_REQUEST_ID = re.compile(r'^[A-Za-z0-9._-]{8,64}$')
# (?P<name>...) with at most one level of nested parentheses -> <name>
_NAMED_GROUP = re.compile(r'\(\?P<(\w+)>(?:[^()]|\([^()]*\))*\)')

_lock = threading.Lock()
_inflight = 0


def current_request_id():
    return _request_id.get()


class RequestIdFilter(logging.Filter):
    """Adds `request_id` to every log record so lines can be joined to a request."""

    def filter(self, record):
        record.request_id = _request_id.get()
        return True


class PiiMaskFilter(logging.Filter):
    """Masks emails and phone-like numbers in log messages and tracebacks."""

    def filter(self, record):
        if record.args or isinstance(record.msg, str):
            record.msg = mask_text(record.getMessage())
            record.args = ()
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = mask_text(record.exc_text)
        return True


def normalize_route(route):
    route = _NAMED_GROUP.sub(r'<\1>', route or '')
    return route.lstrip('^').rstrip('$').replace('\\Z', '')


class _DbStats:
    """Counts queries and time spent in them. Used with connection.execute_wrapper()."""
    __slots__ = ('count', 'seconds')

    def __init__(self):
        self.count = 0
        self.seconds = 0.0

    def __call__(self, execute, sql, params, many, context):
        started = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            self.count += 1
            self.seconds += time.perf_counter() - started


def _user_id(request):
    """The internal user id, read only if already resolved (never triggers a lookup)."""
    user = request.__dict__.get('user')
    if user is None:
        return None
    if isinstance(user, LazyObject) and user._wrapped is empty:
        return None
    # Owner primary keys are UUIDs, so the id is logged as a string.
    return str(user.pk) if getattr(user, 'is_authenticated', False) else None


def _today():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def client_hash(request):
    """A short masked identifier for the client address, for the two-phone test in docs/EDGE_SETUP.md.

    It is the address the rate limits see (DRF's get_ident, which honours TRUSTED_PROXY_COUNT), run through an HMAC
    keyed with SECRET_KEY and the UTC date, cut to 8 hex characters. The address cannot be read back from it, two
    requests from the same client on the same day share it, and tomorrow it is a different value, so it is useful for
    checking "are these two requests from different clients" and useless for following a person. LOG_CLIENT_ID=False
    removes it from the log."""
    from rest_framework.throttling import BaseThrottle  # imported here: this module loads during logging set-up

    ident = BaseThrottle().get_ident(request) or '-'
    key = hashlib.sha256(('hh-client-id:' + settings.SECRET_KEY).encode()).digest()
    return hmac.new(key, f'{_today()}|{ident}'.encode(), hashlib.sha256).hexdigest()[:8]


def _response_bytes(response):
    length = response.headers.get('Content-Length')
    if length and length.isdigit():
        return int(length)
    if getattr(response, 'streaming', False):
        return None
    return len(response.content)


def _route_and_view(request):
    match = request.resolver_match
    if match is not None and match.route is not None:
        return normalize_route(match.route), match.view_name
    static_prefix = '/' + settings.STATIC_URL.lstrip('/')
    return ('static' if request.path.startswith(static_prefix) else 'unmatched'), '-'


class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.release = getattr(settings, 'RELEASE', '') or ''
        self.pid = os.getpid()

    def __call__(self, request):
        global _inflight
        if request.path == '/healthz':
            return self.get_response(request)

        request_id = request.META.get('HTTP_X_REQUEST_ID', '')
        if not _VALID_REQUEST_ID.match(request_id):
            request_id = uuid.uuid4().hex
        token = _request_id.set(request_id)
        with _lock:
            _inflight += 1
            inflight = _inflight
        stats = _DbStats()
        started = time.perf_counter()
        response = None
        try:
            with connection.execute_wrapper(stats):
                response = self.get_response(request)
            response['X-Request-ID'] = request_id
            return response
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            with _lock:
                _inflight -= 1
            try:
                self._log(request, response, request_id, duration_ms, stats, inflight)
            finally:
                _request_id.reset(token)

    def process_exception(self, request, exception):
        request._hh_exc = type(exception).__name__
        return None

    def _log(self, request, response, request_id, duration_ms, stats, inflight):
        status = response.status_code if response is not None else 500
        route, view = _route_and_view(request)
        level = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
        payload = {
            'ts': datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'level': logging.getLevelName(level).lower(),
            'event': 'request',
            'request_id': request_id,
            'method': request.method,
            'route': route,
            'view': view,
            'status': status,
            'duration_ms': round(duration_ms, 1),
            'db_queries': stats.count,
            'db_ms': round(stats.seconds * 1000, 1),
            'resp_bytes': _response_bytes(response) if response is not None else None,
            'inflight': inflight,
            'user_id': _user_id(request),
            # How many entries X-Forwarded-For had (a count, never the addresses). Tells you whether
            # TRUSTED_PROXY_COUNT matches the real number of proxies in front of gunicorn.
            'xff_hops': len([part for part in request.META.get('HTTP_X_FORWARDED_FOR', '').split(',') if part.strip()]),
            'release': self.release,
            'pid': self.pid,
        }
        if getattr(settings, 'LOG_CLIENT_ID', True):
            payload['client'] = client_hash(request)
        exc = getattr(request, '_hh_exc', None)
        if exc:
            payload['exc'] = exc
        logger.log(level, json.dumps(payload, separators=(',', ':'), default=str))
