"""
One place that decides how long a call that leaves the server may take.

A gunicorn worker thread that waits on a slow provider is a thread no other user can have. Every
outbound HTTP call therefore carries a (connect, read) timeout, and the longest allowed value is far
below the gunicorn timeout (60 s). apps/core/test_outbound_timeouts.py scans the source and fails the
build when a new call appears without one.

  * outbound.post(...)        for plain calls (email provider, SMS); timeout defaults to SHORT.
  * outbound.get(...)         the same for a plain GET (heartbeat monitors); timeout defaults to SHORT.
  * outbound.gateway_session  for the Razorpay SDK, which makes its own requests through a session.
"""
import requests

# (connect seconds, read seconds). The worst case is the sum: 6 s for SHORT, 13 s for GATEWAY.
SHORT = (2.0, 4.0)
GATEWAY = (3.0, 10.0)

MAX_SECONDS = 10.0  # no single phase may be longer than this


def _checked(timeout):
    phases = timeout if isinstance(timeout, (tuple, list)) else (timeout,)
    if not phases or any((not isinstance(p, (int, float))) or p <= 0 or p > MAX_SECONDS for p in phases):
        raise ValueError(f'outbound timeout {timeout!r} must be positive and at most {MAX_SECONDS} s per phase')
    return timeout


def post(url, *, timeout=SHORT, **kwargs):
    """requests.post with a mandatory, bounded timeout."""
    return requests.post(url, timeout=_checked(timeout), **kwargs)


def get(url, *, timeout=SHORT, **kwargs):
    """requests.get with a mandatory, bounded timeout."""
    return requests.get(url, timeout=_checked(timeout), **kwargs)


class TimeoutSession(requests.Session):
    """A session that applies a default timeout to every request made through it."""

    def __init__(self, timeout=GATEWAY):
        super().__init__()
        self.default_timeout = _checked(timeout)

    def request(self, method, url, **kwargs):
        if kwargs.get('timeout') is None:
            kwargs['timeout'] = self.default_timeout
        return super().request(method, url, **kwargs)


_gateway_session = None


def gateway_session():
    """The shared session for payment-gateway calls (keeps the TLS connection alive between calls)."""
    global _gateway_session
    if _gateway_session is None:
        _gateway_session = TimeoutSession(GATEWAY)
    return _gateway_session
