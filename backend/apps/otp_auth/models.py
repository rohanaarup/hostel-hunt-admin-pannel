"""
otp_auth/models.py

The old second OTP path (routes, services, a different hash) was removed in F4: nothing called it, and the
live OTP code is apps/owners (OTPService). Only the proxy model remains so no migration is needed here; it can
be deleted together with this app in a later clean-up.
"""
from apps.owners.models import OTPRecord as BaseOTPRecord


class OTPRecord(BaseOTPRecord):
    class Meta:
        proxy = True
