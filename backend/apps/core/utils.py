"""
Back-compat re-export shim — see apps/core/tenancy/utils.py.
"""
from apps.core.tenancy.utils import (  # noqa: F401
    get_scoped_object_or_404,
    get_tenant_scoped_object_or_404,
    get_user_scoped_object_or_404,
)
