"""
Back-compat re-export shim — see apps/core/tenancy/querysets.py.
"""
from apps.core.tenancy.querysets import (  # noqa: F401
    TenantScopedQuerysetMixin,
    UserScopedQuerysetMixin,
)
