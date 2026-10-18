"""
Cache headers for the few anonymous public reads that are the same for everyone.

  hostels-list         max-age 30   (public scope only; owners' lists are never cached)
  city-list            max-age 120
  city-locality-list   max-age 120
  hostels-localities   max-age 120

What is deliberately NOT here: the hostel detail (it carries bed availability), anything under /payments/,
/bookings/ or /dashboard/, and every response to a request that carries an Authorization header.

  * Anonymous request, 200 answer  ->  `Cache-Control: public, max-age=N`, a strong `ETag` (hash of the body),
    `Vary: Authorization`, and a bodiless 304 when the client sends a matching `If-None-Match`.
  * Request with a token           ->  `Cache-Control: private, no-store` (and no ETag), so no shared cache can
    ever keep or hand out a signed-in user's answer.

Who benefits: a browser or CDN in front of the API, and the app once it keeps an HTTP cache (planned in F6).
Render's edge does not cache JSON on its own; the headers cost almost nothing and make that possible later.
"""
import hashlib

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


class PublicCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method not in ('GET', 'HEAD') or response.status_code != 200 or response.streaming:
            return response
        match = getattr(request, 'resolver_match', None)
        name = match.view_name if match is not None else None
        max_age = PUBLIC_MAX_AGE.get(name)
        if max_age is None:
            return response

        patch_vary_headers(response, ('Authorization',))
        if request.META.get('HTTP_AUTHORIZATION'):
            patch_cache_control(response, private=True, no_store=True)
            return response
        if name == 'hostels-list' and (request.GET.get('scope') or 'public').lower() != 'public':
            return response  # an owner or staff list: only reachable with a token anyway

        etag = '"%s"' % hashlib.md5(response.content, usedforsecurity=False).hexdigest()
        response['ETag'] = etag
        patch_cache_control(response, public=True, max_age=max_age)
        header = request.META.get('HTTP_IF_NONE_MATCH')
        if header and _etag_matches(header, etag):
            not_modified = HttpResponseNotModified()
            for key in ('ETag', 'Cache-Control', 'Vary'):
                not_modified[key] = response[key]
            return not_modified
        return response
