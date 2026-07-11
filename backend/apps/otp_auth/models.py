"""
otp_auth/models.py — OTP Record Model

Matches Railway Postgres `otp_records` table schema exactly.
Uses app_label='owners' to match Railway's content type `owners.otprecord`.
"""
import hashlib
from django.utils import timezone
from apps.owners.models import OTPRecord as BaseOTPRecord

class OTPRecord(BaseOTPRecord):
    """
    Proxy model extending owners.OTPRecord with methods needed by otp_auth services.
    """
    # Rate limit constants (enforced in service layer)
    MAX_SENDS_PER_HOUR = 5
    COOLDOWN_SECONDS = 60
    MAX_ATTEMPTS = 5
    VALIDITY_MINUTES = 5

    class Meta:
        proxy = True

    def is_expired(self):
        return timezone.now() > self.expires_at

    @staticmethod
    def hash_otp(otp_code: str) -> str:
        return hashlib.sha256(otp_code.encode()).hexdigest()

    def verify_code(self, otp_code: str) -> bool:
        return self.otp_code == self.hash_otp(otp_code)

    # Note: save() is inherited from BaseOTPRecord, but we can override it if needed.
    # However, BaseOTPRecord doesn't auto-set expires_at in save, so we add it here.
    def save(self, *args, **kwargs):
        if not self.pk and not self.expires_at:
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(minutes=self.VALIDITY_MINUTES)
        super().save(*args, **kwargs)
