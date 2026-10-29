"""
Optional guard for a deployment behind an edge (Cloudflare in front of Render).

With EDGE_SHARED_SECRET set, every request must carry the header `X-Edge-Secret` with that value, or it is refused with
403. The edge adds the header (a Cloudflare "Modify Request Header" transform rule with the same value); someone who
finds the origin address (hostel-hunt-backend.onrender.com) and calls it directly does not have it. That matters for
three things the edge provides and the origin cannot check on its own: the firewall and rate rules, the cache, and the
client address, which TRUSTED_PROXY_COUNT reads from X-Forwarded-For (a request that skips the edge can write that
header itself).

  * Unset (the default): this middleware does nothing.
  * /healthz is answered before this middleware runs, and /readyz is exempt here, so Render's own health checks (which
    do not go through the edge) keep working.
  * The secret is compared in constant time and is never logged, echoed or put in the refusal. The refusal is a plain
    403 with a generic body, and the request log still records it (status 403).
"""
import hmac

from django.conf import settings
from django.http import JsonResponse

HEADER = 'HTTP_X_EDGE_SECRET'
EXEMPT_PATHS = frozenset({'/healthz', '/readyz'})


class EdgeSecretMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        secret = getattr(settings, 'EDGE_SHARED_SECRET', '')
        if not secret or request.path in EXEMPT_PATHS:
            return self.get_response(request)
        supplied = request.META.get(HEADER, '')
        if supplied and hmac.compare_digest(supplied.encode(), secret.encode()):
            return self.get_response(request)
        return JsonResponse({'detail': 'Forbidden.'}, status=403)
