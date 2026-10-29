"""
A short shared cache for the public city and locality lists.

These lists are small, the same for everyone, change rarely, and are read on every app launch. Each uncached read
costs one or two database round trips; at the distance between Render (Singapore) and a Mumbai database that is
a visible part of the response time.

  * TTL: PUBLIC_LIST_CACHE_SECONDS (default 60, jittered by 10 percent; 0 turns the cache off).
  * Kept in the shared cache (apps/core/cache.py), so with REDIS_URL set every worker and every instance sees the
    same entry, and a change in any process shows at once everywhere: saving a City, Locality, LocalityAlias, Hostel
    or Room bumps the "places" version (see HostelsConfig.ready), and so do the bulk updates that fire no signal
    (the deactivate_test_hostels command calls bump() itself). Without REDIS_URL the cache is per process, as before.
  * Single flight: when an entry expires, one request rebuilds it and the others wait for that result.
  * Never used for anything personal or for bed availability.
"""
from django.conf import settings
from rest_framework.response import Response
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList

from apps.core import cache as shared

NAME = 'places'
MAX_PATH_LENGTH = 200  # a longer path (query string) is built every time: unbounded keys must not fill the cache


def bump(**kwargs):
    """Signal receiver and plain function: forget every cached places answer, in every process."""
    shared.bump_version(NAME)


def _plain(data):
    if isinstance(data, ReturnList):
        return list(data)
    if isinstance(data, ReturnDict):
        return dict(data)
    return data


def cached_list(request, build):
    """build() returns a DRF Response; its data is kept for the TTL when the answer is a 200."""
    seconds = getattr(settings, 'PUBLIC_LIST_CACHE_SECONDS', 60)
    path = request.get_full_path()
    if seconds <= 0 or len(path) > MAX_PATH_LENGTH:
        return build()

    def make():
        response = build()
        return response.status_code, _plain(response.data)

    status, data = shared.get_or_set(NAME, seconds, make, parts=(path,), should_cache=lambda value: value[0] == 200)
    return Response(data, status=status)
