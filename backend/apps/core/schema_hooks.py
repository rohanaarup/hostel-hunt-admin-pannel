"""
OpenAPI post-processing: make the generated schema independent of the database engine.

drf-spectacular reads each integer field's numeric range from the active database. Postgres
(production, CI) gives 2147483647 for integer fields while SQLite gives 9223372036854775807 with
`format: int64`, so a schema generated on a developer's SQLite would differ from the committed
one. This hook rewrites the SQLite values to the Postgres ones, so `backend/schema.yml` is the same
wherever it is generated.
"""
from django.db import connection

_SQLITE_MAX = 9223372036854775807
_POSTGRES_MAX = 2147483647


def _normalise(node):
    if isinstance(node, dict):
        if node.get('type') == 'integer' and node.get('maximum') == _SQLITE_MAX:
            node['maximum'] = _POSTGRES_MAX
            node.pop('format', None)
        for value in node.values():
            _normalise(value)
    elif isinstance(node, list):
        for value in node:
            _normalise(value)


def use_postgres_integer_ranges(result, generator, request, public):
    if connection.vendor != 'postgresql':
        _normalise(result)
    return result
