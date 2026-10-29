"""
The Redis cache backend: django-redis with a circuit breaker, so a Redis outage never takes the API down.

What goes wrong without it: with Redis unreachable every cache call would wait for a connect timeout, and one
request makes several (two throttle reads, two throttle writes, the places lookup). A black-holed Redis would
then add seconds to every request and tie up gunicorn threads. With this backend:

  * a failed call (connection refused, timeout, a Redis error) opens the breaker for BREAKER_SECONDS (default 10);
  * while it is open nothing touches the network: get returns its default, add/set/delete return None or False,
    and the helpers in apps/core/cache.py simply build the value themselves;
  * the first call after the cool-down tries Redis again; one success closes the breaker.

So an outage costs about one connect timeout per process every 10 seconds, and rate limits fail OPEN (nobody is
blocked, nothing is counted). The warning is logged at most once a minute and names only the error type, never the
address or password (REDIS_URL holds one). The breaker state belongs to the process, which is right: it describes
whether THIS process can reach Redis, not shared data.

django-redis's own IGNORE_EXCEPTIONS is left off on purpose: it hides the failure, so the breaker could not see it.
"""
import functools
import logging
import time

from django_redis.cache import RedisCache
from redis.exceptions import RedisError

logger = logging.getLogger('apps.core.cache')

_FAILURES = (RedisError, OSError)
_state = {'down_until': 0.0, 'last_warning': 0.0}
_WARN_EVERY = 60.0


def _now():
    return time.monotonic()


def reset_breaker():
    _state['down_until'] = 0.0
    _state['last_warning'] = 0.0


def breaker_open():
    return _now() < _state['down_until']


def _fallback(name, args, kwargs):
    if name == 'get':
        return args[1] if len(args) > 1 else kwargs.get('default')
    if name == 'get_many':
        return {}
    if name in ('has_key', 'delete'):
        return False
    return None


def _guarded(name, method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if breaker_open():
            return _fallback(name, args, kwargs)
        try:
            return method(self, *args, **kwargs)
        except _FAILURES as exc:
            now = _now()
            _state['down_until'] = now + self.breaker_seconds
            if now - _state['last_warning'] >= _WARN_EVERY:
                _state['last_warning'] = now
                logger.warning('Shared cache unreachable (%s): serving without it for %ss', type(exc).__name__,
                               self.breaker_seconds)
            return _fallback(name, args, kwargs)

    return wrapper


class ResilientRedisCache(RedisCache):
    def __init__(self, server, params):
        super().__init__(server, params)
        self.breaker_seconds = float((params.get('OPTIONS') or {}).get('BREAKER_SECONDS', 10))


# Every operation that talks to Redis goes through the breaker.
for _name in ('get', 'set', 'add', 'delete', 'incr', 'decr', 'touch', 'has_key', 'get_many', 'set_many',
              'delete_many', 'clear', 'ttl', 'expire', 'persist', 'incr_version'):
    if hasattr(RedisCache, _name):
        setattr(ResilientRedisCache, _name, _guarded(_name, getattr(RedisCache, _name)))
