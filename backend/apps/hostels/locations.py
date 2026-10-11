"""
Helpers for matching the city / locality text people type against the City and Locality tables.

Two spellings that differ only by case, spaces, hyphens, dots or accents are the same place:
`match_key("K.P.H.B  Colony") == match_key("kphb colony")`. Genuinely different spellings
(Dilsukhnagar / Dilsuknagar) are joined by a LocalityAlias that staff add once.
"""
import re
import unicodedata
import uuid


def normalise_slug(value):
    """URL-friendly form: lower case, ASCII, words joined by single hyphens."""
    text = unicodedata.normalize('NFKD', value or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', text).strip('-')


def match_key(value):
    """Comparison form: the slug with the hyphens removed, so spacing never matters."""
    return normalise_slug(value).replace('-', '')


def _as_uuid(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def resolve_city(value):
    """The City a name, slug or id refers to, or None."""
    from .models import City

    value = (value or '').strip() if isinstance(value, str) else value
    if not value:
        return None
    pk = _as_uuid(value)
    if pk is not None:
        return City.objects.filter(pk=pk).first()
    key = match_key(value)
    if not key:
        return None
    return next((city for city in City.objects.all() if match_key(city.name) == key), None)


def resolve_localities(value, city=None):
    """Localities a name, slug, alias or id refers to (restricted to `city` when given)."""
    from .models import Locality, LocalityAlias

    value = (value or '').strip() if isinstance(value, str) else value
    if not value:
        return []
    pk = _as_uuid(value)
    scope = Locality.objects.filter(city=city) if city is not None else Locality.objects.all()
    if pk is not None:
        return list(scope.filter(pk=pk))
    key = match_key(value)
    if not key:
        return []
    found = {loc.pk: loc for loc in scope if match_key(loc.name) == key}
    aliases = LocalityAlias.objects.select_related('locality')
    if city is not None:
        aliases = aliases.filter(city=city)
    for alias in aliases:
        if match_key(alias.alias_slug) == key:
            found[alias.locality.pk] = alias.locality
    return list(found.values())
