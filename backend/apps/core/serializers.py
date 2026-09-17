"""
Back-compat re-export shim — see apps/core/tenancy/serializers.py.
"""
from apps.core.tenancy.serializers import (  # noqa: F401
    TenantOwnershipValidationMixin,
    UserOwnershipValidationMixin,
)
