from django.db import models


class TenantScopedModel(models.Model):
    """
    Abstract base for any model whose records belong to a specific Owner
    (hostel-owner tenant), directly or transitively. Subclasses MUST set
    OWNER_LOOKUP to the ORM path (as a string, or a tuple/list of strings
    for a model reachable from more than one FK path — e.g. MediaItem via
    either `hostel` or `room`) from this model back to Owner. Adds no
    fields and requires no migration on its own.
    """
    OWNER_LOOKUP = None

    class Meta:
        abstract = True


class UserScopedModel(models.Model):
    """
    Abstract base for any model whose records belong to a specific
    requesting user directly (student-owned data — bookings, wishlist,
    reviews), as opposed to TenantScopedModel's owner/tenant relationship.
    Subclasses MUST set USER_LOOKUP the same way TenantScopedModel models
    set OWNER_LOOKUP. Adds no fields and requires no migration on its own.

    A model can inherit both TenantScopedModel and UserScopedModel when it
    is legitimately readable from two different "eyes" (e.g. Booking: the
    hostel owner sees their hostel's bookings, the student sees their own).
    """
    USER_LOOKUP = None

    class Meta:
        abstract = True


class GlobalModel(models.Model):
    """
    Explicit marker for a model that has been deliberately reviewed and
    judged to have no owner/tenant or user scope at all (e.g. OTPRecord,
    which is keyed by an email/phone identifier before any account even
    exists). Exists purely so the startup system check
    (apps.core.tenancy.checks) can tell "intentionally unscoped" apart
    from "nobody thought about this yet" for every model in a tenancy-
    relevant app. Adds no fields and requires no migration on its own.
    """

    class Meta:
        abstract = True
