"""
Liveness and readiness endpoints.

/healthz  Liveness. Answered by a middleware placed first in MIDDLEWARE, so it
          never touches the database, sessions, host validation or the HTTPS
          redirect. A platform health check hitting the container by IP over
          plain HTTP therefore always gets 200 while the process is up.
/readyz   Readiness. A normal view that runs one cheap query. Returns 503 when
          the database is unreachable, without putting the error in the body.
"""
import logging

from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger('apps.core.health')


def _json(payload, status=200):
    response = JsonResponse(payload, status=status)
    response['Cache-Control'] = 'no-store'
    return response


class HealthzMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == '/healthz':
            return _json({'status': 'ok'})
        return self.get_response(request)


def readyz(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception as exc:
        logger.error('readyz: database check failed: %s', exc)
        return _json({'status': 'unavailable'}, status=503)
    return _json({'status': 'ok'})
