from django.db import models


class TenantScopedModel(models.Model):
    """
    Abstract base for any model whose records belong to a specific Owner,
    directly or transitively. Subclasses MUST set OWNER_LOOKUP to the ORM
    path (as a string, using __ traversal) from this model back to Owner.
    This adds no fields and requires no migration on its own.
    """
    OWNER_LOOKUP: str = None

    class Meta:
        abstract = True
