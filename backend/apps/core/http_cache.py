"""
Cache headers: which answers a shared cache (a CDN such as Cloudflare, or a browser) may keep, and which never.

The few anonymous public reads that are the same for everyone:

  hostels-list         max-age / s-maxage 30   (public scope only; owners' lists are never cached)
  city-list            max-age / s-maxage 120
  city-locality-list   max-age / s-maxage 120
  hostels-localities   max-age / s-maxage 120

  * Anonymous request, 200 answer  ->  `Cache-Control: public, max-age=N, s-maxage=N`, a strong `ETag` (hash of the
    body), `Vary: Authorization`, and a bodiless 304 when the client sends a matching `If-None-Match`. `s-maxage` is
    the lifetime for SHARED caches (the edge), `max-age` for the browser.
  * Request with a token           ->  `Cache-Control: private, no-store` (and no ETag), so no shared cache can
    ever keep or hand out a signed-in user's answer.

EVERYTHING ELSE gets `Cache-Control: private, no-store` unless the view already set its own header (the health checks
set `no-store`; Django's admin sets its own; WhiteNoise sets the long lifetime of static files): the hostel detail (it
carries bed availability), payments, bookings, dashboards, auth, the webhook, every write, and every error answer. A
header that is missing is a cache's invitation to decide for itself; this middleware never leaves that choice open.

Who benefits: the edge (Cloudflare serves the public lists without waking the origin), a browser, and the app once it
keeps an HTTP cache (planned in F6). Render's own edge does not cache JSON.
"""
import hashlib

from django.conf import settings
from django.http import HttpResponseNotModified
from django.utils.cache import patch_cache_control, patch_vary_headers

PUBLIC_MAX_AGE = {
    'hostels-list': 30,
    'city-list': 120,
    'city-locality-list': 120,
    'hostels-localities': 120,
}


def _etag_matches(header, etag):
    wanted = etag.strip('"')
    for candidate in header.split(','):
        candidate = candidate.strip()
        if candidate == '*':
            return True
        if candidate.startswith('W/'):
            candidate = candidate[2:]
        if candidate.strip('"') == wanted:
            return True
    return False


def _private(request, response):
    """The default for everything that is not a public list: no shared cache may keep it."""
    if response.has_header('Cache-Control'):
        return response
    static_prefix = '/' + (getattr(settings, 'STATIC_URL', None) or '/static/').lstrip('/')
    if request.path.startswith(static_prefix):
        return response  # WhiteNoise's own lifetime for versioned files
    patch_cache_control(response, private=True, no_store=True)
    return response


class PublicCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method not in ('GET', 'HEAD') or response.status_code != 200 or response.streaming:
            return _private(request, response)
        match = getattr(request, 'resolver_match', None)
        name = match.view_name if match is not None else None
        max_age = PUBLIC_MAX_AGE.get(name)
        if max_age is None:
            return _private(request, response)

        patch_vary_headers(response, ('Authorization',))
        if request.META.get('HTTP_AUTHORIZATION'):
            patch_cache_control(response, private=True, no_store=True)
            return response
        if name == 'hostels-list' and (request.GET.get('scope') or 'public').lower() != 'public':
            return _private(request, response)  # an owner or staff list: only reachable with a token anyway

        etag = '"%s"' % hashlib.md5(response.content, usedforsecurity=False).hexdigest()
        response['ETag'] = etag
        patch_cache_control(response, public=True, max_age=max_age, s_maxage=max_age)
        header = request.META.get('HTTP_IF_NONE_MATCH')
        if header and _etag_matches(header, etag):
            not_modified = HttpResponseNotModified()
            for key in ('ETag', 'Cache-Control', 'Vary'):
                not_modified[key] = response[key]
            return not_modified
        return response
