"""
Back-compat re-export shim. The real implementation lives in
apps/core/tenancy/ — see that package for the canonical scoping
infrastructure (TenantScopedModel, UserScopedModel, GlobalModel).
Existing `from apps.core.models import TenantScopedModel` imports across
hostels/rooms/bookings/residents/notices/payments keep working unchanged;
new code should import from apps.core.tenancy.models directly.
"""
from apps.core.tenancy.models import (  # noqa: F401
    TenantScopedModel,
    UserScopedModel,
    GlobalModel,
)
