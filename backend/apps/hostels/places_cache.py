"""
A short in-memory cache for the public city and locality lists.

These lists are small, the same for everyone, change rarely, and are read on every app launch. Each uncached read
costs one or two database round trips; at the distance between Render (Singapore) and a Mumbai database that is
a visible part of the response time.

  * TTL: PUBLIC_LIST_CACHE_SECONDS (default 60; 0 turns the cache off).
  * The cache is per worker process (LocMemCache). Saving a City, Locality, LocalityAlias or Hostel in a process
    bumps a version number, so that process serves fresh data at once; another worker, and bulk updates that fire
    no signal (the deactivate_test_hostels command), show the change when the TTL ends.
  * Never used for anything personal or for bed availability.
"""
from django.conf import settings
from django.core.cache import cache
from rest_framework.response import Response

VERSION_KEY = 'hh:places:version'


def _version():
    return cache.get_or_set(VERSION_KEY, 1, None)


def bump(**kwargs):
    """Signal receiver: forget every cached places answer in this process."""
    try:
        cache.incr(VERSION_KEY)
    except ValueError:  # not set yet
        cache.set(VERSION_KEY, 2, None)


def cached_list(request, build):
    """build() returns a DRF Response; its data is kept for the TTL when the answer is a 200."""
    seconds = getattr(settings, 'PUBLIC_LIST_CACHE_SECONDS', 60)
    if seconds <= 0:
        return build()
    key = f'hh:places:{_version()}:{request.get_full_path()}'
    data = cache.get(key)
    if data is not None:
        return Response(data)
    response = build()
    if response.status_code == 200:
        cache.set(key, response.data, seconds)
    return response
