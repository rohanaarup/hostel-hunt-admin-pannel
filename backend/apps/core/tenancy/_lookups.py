"""
Internal helpers shared by querysets.py, utils.py and permissions.py.
Not part of the public tenancy API — import from the sibling modules
instead of this one.
"""
from django.db.models import Q


def scope_q(lookup, value):
    """
    Build a Q object for one OWNER_LOOKUP/USER_LOOKUP declaration, which
    may be a single ORM path string or a tuple/list of alternative paths
    (e.g. MediaItem is reachable via `hostel` OR `room__hostel`). Multiple
    paths are OR-combined: a match on any one of them is sufficient.
    """
    if isinstance(lookup, (tuple, list)):
        q = Q()
        for path in lookup:
            q |= Q(**{path: value})
        return q
    return Q(**{lookup: value})


def scope_match(instance, lookup, value):
    """
    Object-level equivalent of scope_q: walk a dotted ORM path (or the
    first matching path out of a tuple/list of alternatives) on an
    in-memory instance and compare it to `value`. Used by the object-level
    permission classes, which check an already-fetched instance rather
    than filtering a queryset.
    """
    paths = lookup if isinstance(lookup, (tuple, list)) else [lookup]
    for path in paths:
        obj = instance
        for attr in path.split("__"):
            if obj is None:
                break
            obj = getattr(obj, attr, None)
        if obj is not None and obj == value:
            return True
    return False
