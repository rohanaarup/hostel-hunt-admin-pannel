"""
Back-compat re-export shim — see apps/core/tenancy/checks.py.
"""
from apps.core.tenancy.checks import (  # noqa: F401
    check_scoped_models_declare_lookup,
    check_business_models_are_classified,
    BUSINESS_APP_LABELS,
)
