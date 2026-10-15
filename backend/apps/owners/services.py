import hmac
import logging
import secrets
import string
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from apps.core import mailer, outbound
from apps.core.dev import dev_otp_exposed
from .models import OTPRecord

logger = logging.getLogger('apps.owners.services')


class OTPRateLimited(Exception):
    """A new code was asked for too soon or too often for this address or number."""

    def __init__(self, message, retry_after):
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


class OTPService:
    VALIDITY_MINUTES = 10
    MAX_ATTEMPTS = 5          # wrong guesses before the code is locked
    COOLDOWN_SECONDS = 60     # between two codes for the same address and purpose
    MAX_SENDS_PER_HOUR = 5    # codes per address and purpose

    LOCKED = "Too many wrong attempts. Please request a new code."

    @staticmethod
    def generate_otp_code(length=6):
        """A numeric OTP code from the operating system's secure random source."""
        return ''.join(secrets.choice(string.digits) for _ in range(length))

    @staticmethod
    def hash_code(identifier, purpose, code):
        """Keyed hash (HMAC-SHA256 with a key derived from SECRET_KEY): fast, and useless without the server's key.

        Only 10^6 six-digit codes exist, so a slow hash adds no protection; the wrong-guess cap does.
        """
        return salted_hmac('hh.otp', f'{identifier}|{purpose}|{code}', algorithm='sha256').hexdigest()

    @staticmethod
    def create_otp(identifier, purpose):
        """Creates an OTP record for a given identifier, or raises OTPRateLimited."""
        now = timezone.now()
        with transaction.atomic():
            # The row lock makes two simultaneous requests for the same address take turns.
            recent = list(
                OTPRecord.objects.select_for_update()
                .filter(identifier=identifier, purpose=purpose, created_at__gte=now - timedelta(hours=1))
                .values_list('created_at', flat=True)
            )
            if recent:
                wait = OTPService.COOLDOWN_SECONDS - (now - max(recent)).total_seconds()
                if wait > 0:
                    seconds = int(wait) + 1
                    raise OTPRateLimited(f'Please wait {seconds} seconds before asking for another code.', seconds)
                if len(recent) >= OTPService.MAX_SENDS_PER_HOUR:
                    minutes = max(1, int((min(recent) + timedelta(hours=1) - now).total_seconds() // 60) + 1)
                    raise OTPRateLimited('Too many codes were requested. Please try again later.', minutes * 60)

            # Invalidate ALL existing OTP records for this identifier/purpose
            # This covers both unverified OTPs AND verified-but-unconsumed tokens
            OTPRecord.objects.filter(identifier=identifier, purpose=purpose, is_used=False).update(
                is_used=True, verification_token=None,
            )

            code = OTPService.generate_otp_code()
            record = OTPRecord.objects.create(
                identifier=identifier,
                otp_code=OTPService.hash_code(identifier, purpose, code),
                purpose=purpose,
                expires_at=now + timedelta(minutes=OTPService.VALIDITY_MINUTES),
            )
        return code, record

    @staticmethod
    def _matches(record, code):
        stored = record.otp_code or ''
        if stored.startswith('pbkdf2_'):  # a code issued before this release; valid for at most 10 more minutes
            return check_password(code, stored)
        expected = OTPService.hash_code(record.identifier, record.purpose, code)
        return hmac.compare_digest(stored, expected)

    @staticmethod
    def verify_otp(identifier, code, purpose):
        """Verifies if an OTP is valid. Wrong guesses are counted on the record; the code locks at MAX_ATTEMPTS."""
        with transaction.atomic():
            record = (
                OTPRecord.objects.select_for_update()
                .filter(
                    identifier=identifier, purpose=purpose, is_used=False, is_verified=False,
                    expires_at__gt=timezone.now(),
                )
                .order_by('-created_at')
                .first()
            )
            if not record:
                return False, "No valid OTP found or OTP has expired.", None

            if record.attempts >= OTPService.MAX_ATTEMPTS:
                record.is_used = True
                record.save(update_fields=['is_used'])
                return False, OTPService.LOCKED, None

            if not OTPService._matches(record, code):
                record.attempts += 1
                locked = record.attempts >= OTPService.MAX_ATTEMPTS
                if locked:
                    record.is_used = True
                record.save(update_fields=['attempts', 'is_used'])
                return False, (OTPService.LOCKED if locked else "Invalid OTP code."), None

            # Mark as verified (NOT used) and generate verification token
            # The token stays valid until consumed by register/reset-password
            record.is_verified = True
            record.verification_token = uuid.uuid4()
            record.save(update_fields=['is_verified', 'verification_token'])
            return True, "OTP verified successfully.", record.verification_token

    @staticmethod
    def discard(record):
        """Forget a code that could not be delivered, so it does not count against the sender's limits."""
        OTPRecord.objects.filter(pk=record.pk).delete()

    @staticmethod
    def send_otp(identifier, code, purpose, identifier_type):
        """Sends the OTP via Email or Phone and returns (success_bool, message)."""
        message = f"Your Hostel Hunt OTP code is: {code}. It is valid for {OTPService.VALIDITY_MINUTES} minutes."

        if identifier_type == 'email':
            if not mailer.is_configured():
                if dev_otp_exposed():
                    logger.warning(f"DEV FALLBACK: No email provider. Printing OTP for {identifier}: {code}")
                    return True, f"Email failed (No SMTP). Your TEST OTP is: {code}"
                logger.error("Email OTP not sent: no email provider is configured.")
                return False, "Email service is not configured."
            try:
                mailer.send_email(identifier, "Hostel Hunt - Verification Code", message)
            except mailer.EmailError as exc:
                # The provider's detail goes to the server log only (mailer.py), never to the client.
                logger.error("Failed to send OTP email: %s", exc.kind)
                return False, "We couldn't send the verification email just now. Please try again in a minute."
            logger.info("OTP email sent")
            return True, "Email sent successfully."

        elif identifier_type == 'phone':
            if not getattr(settings, 'TWILIO_ACCOUNT_SID', None) or not getattr(settings, 'TWILIO_AUTH_TOKEN', None):
                if dev_otp_exposed():
                    logger.warning(f"DEV FALLBACK: No Twilio config. Printing OTP for {identifier}: {code}")
                    return True, "SMS sent successfully (Dev Fallback)."
                else:
                    logger.error("SMS provider is not configured in the environment.")
                    return False, "SMS provider is not configured in the environment."

            twilio_url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
            payload = {
                "To": identifier,
                "From": getattr(settings, 'TWILIO_FROM_NUMBER', ''),
                "Body": message
            }
            try:
                response = outbound.post(
                    twilio_url,
                    data=payload,
                    auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                )
                if response.status_code in [200, 201]:
                    logger.info("OTP SMS sent via Twilio")
                    return True, "SMS sent successfully."
                else:
                    logger.error("Twilio API error: HTTP %s", response.status_code)
                    if dev_otp_exposed():
                        logger.warning(f"DEV FALLBACK: Twilio failed. Printing OTP for {identifier}: {code}")
                        return True, "SMS sent successfully (Dev Fallback)."
                    return False, "Failed to send the SMS. Please try again later."
            except outbound.requests.RequestException as e:
                logger.error("Failed to connect to SMS provider: %s", type(e).__name__)
                return False, "Failed to send the SMS. Please try again later."

        return False, "Invalid identifier type."
