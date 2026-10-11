"""Swagger UI and the raw OpenAPI schema, served only in DEBUG or on staging."""
from functools import wraps

from django.conf import settings
from django.http import Http404
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def docs_enabled():
    return bool(settings.DEBUG or settings.APP_ENV == 'staging')


def only_when_docs_enabled(view):
    # Checked on every request (not at import) so the setting can change per test or deploy.
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not docs_enabled():
            raise Http404
        return view(request, *args, **kwargs)

    return wrapper


schema_view = only_when_docs_enabled(SpectacularAPIView.as_view())
swagger_view = only_when_docs_enabled(SpectacularSwaggerView.as_view(url_name='schema'))
