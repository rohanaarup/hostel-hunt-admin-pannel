"""
Shared-cache helpers (Phase 3). Everything cached across requests goes through here.

  get_or_set(name, ttl, builder, parts=(), user_id=None, per_user=False, should_cache=None)
      The cached value, built by builder() when missing. Three protections:
        * TTL jitter: +-10 percent, so keys written together do not all expire together.
        * Single flight: when a key is missing, ONE caller builds it (cache.add is the lock); the others wait a
          moment for the result instead of all hitting the database (a stampede).
        * Fail open: if the cache is down (the backend answers None to add) the caller just builds the value.
  bump_version(name) / current_version(name)
      Invalidation by version: every key carries the name's version, so bumping it makes every old entry
      unreachable at once, in every worker, with no key scan. The version is a microsecond timestamp rather than
      a counter, so a counter the cache evicted can never come back as a number an old entry still carries.
  make_key(name, *parts, user_id=None)
      hh:<env>:<name>[:parts][:u<id>]:v<N>. Per-user data must pass per_user=True and a user id; the key then
      holds the id, so one user can never be handed another's entry.

Rules (scale rules S1 and S2): no module-level caches for shared data; keys are namespaced; per-user data carries
the user id. Never cache anything personal in a public key, and never bed availability (it changes with payments).
With REDIS_URL unset the default cache is LocMem: per process, which is fine for local runs and CI, and every
helper behaves the same.
"""
import logging
import random
import time

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('apps.core.cache')

LOCK_SECONDS = 10      # longest a builder may hold the single-flight lock
WAIT_SECONDS = 2.0     # longest a waiter waits for the builder before building for itself
POLL_SECONDS = 0.05
_MISSING = object()


def _env():
    return getattr(settings, 'APP_ENV', 'production')


def version_key(name):
    return f'hh:{_env()}:ver:{name}'


def _now_us():
    return time.time_ns() // 1000


def current_version(name):
    key = version_key(name)
    value = cache.get(key)
    if value is None:
        fresh = _now_us()
        cache.add(key, fresh, None)
        value = cache.get(key) or fresh  # if the cache is down every call sees "fresh", which is harmless
    return int(value)


def bump_version(name):
    """Make every cached entry under `name` unreachable. Safe to call when the cache is down."""
    new = max(_now_us(), current_version(name) + 1)
    cache.set(version_key(name), new, None)
    return new


def make_key(name, *parts, user_id=None, version=None):
    pieces = [f'hh:{_env()}', name]
    pieces.extend(str(p) for p in parts)
    if user_id is not None:
        pieces.append(f'u{user_id}')
    pieces.append(f'v{version if version is not None else current_version(name)}')
    return ':'.join(pieces)


def jittered_ttl(ttl):
    return max(1, int(round(ttl * random.uniform(0.9, 1.1))))


def get_or_set(name, ttl, builder, *, parts=(), user_id=None, per_user=False, should_cache=None):
    if per_user and user_id is None:
        raise ValueError('a per-user cache entry needs a user_id in its key')
    if ttl is None or ttl <= 0:
        return builder()

    key = make_key(name, *parts, user_id=user_id)
    value = cache.get(key, _MISSING)
    if value is not _MISSING:
        return value

    lock = key + ':lock'
    got = cache.add(lock, 1, LOCK_SECONDS)
    if got is None:  # the cache is down: no lock, no storing, just build
        return builder()
    if got:
        try:
            value = builder()
            if should_cache is None or should_cache(value):
                cache.set(key, value, jittered_ttl(ttl))
            return value
        finally:
            cache.delete(lock)

    # Another caller is building this key: wait briefly for its result.
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        value = cache.get(key, _MISSING)
        if value is not _MISSING:
            return value
    value = builder()  # the builder was slow or failed: do the work ourselves rather than wait longer
    if should_cache is None or should_cache(value):
        cache.set(key, value, jittered_ttl(ttl))
    return value


def reset_for_tests():
    """Tests only. Nothing process-local needs resetting today (tests call cache.clear()); kept so a future
    process-local helper has one obvious place to be reset."""
    return None
