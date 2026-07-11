import secrets
from datetime import timedelta

from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings

from .models import OTPRecord


class OTPRateLimitException(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class OTPVerificationException(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class OTPService:
    @staticmethod
    def _generate_otp() -> str:
        return str(secrets.randbelow(900000) + 100000)

    @staticmethod
    def _check_rate_limit(existing, identifier):
        if existing is None:
            return

        now = timezone.now()
        seconds_since_last = (now - existing.created_at).total_seconds()

        if seconds_since_last < OTPRecord.COOLDOWN_SECONDS:
            remaining = int(OTPRecord.COOLDOWN_SECONDS - seconds_since_last)
            raise OTPRateLimitException(
                f'Please wait {remaining} second(s) before requesting a new OTP.'
            )

    @staticmethod
    def _send_email(recipient_email: str, otp_code: str) -> None:
        import logging
        logger = logging.getLogger(__name__)
        subject = 'Your OTP for ROHII Hostel Hunt'
        html_message = _build_email_html(otp_code)
        plain_message = f'Your ROHII Hostel Hunt OTP is: {otp_code}. Valid for 5 minutes.'

        try:
            if not getattr(settings, 'EMAIL_HOST_USER', None):
                if settings.DEBUG:
                    logger.warning(f"DEV FALLBACK: No EMAIL_HOST_USER. Printing OTP for {recipient_email}: {otp_code}")
                    return
                else:
                    raise Exception("SMTP credentials not configured.")

            send_mail(
                subject=subject,
                message=plain_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                fail_silently=False,
            )
            logger.info(f"SMTP EMAIL SENT TO {recipient_email}")
        except Exception as e:
            logger.error(f"Failed to send OTP to {recipient_email}: {e}")
            raise e

    @classmethod
    def generate_and_send(cls, identifier: str, purpose: str = 'registration') -> None:
        identifier = identifier.strip().lower()
        existing = OTPRecord.objects.filter(identifier=identifier, purpose=purpose).first()

        cls._check_rate_limit(existing, identifier)

        now = timezone.now()
        otp_code = cls._generate_otp()
        otp_hash = OTPRecord.hash_otp(otp_code)

        OTPRecord.objects.filter(identifier=identifier, purpose=purpose).delete()
        OTPRecord.objects.create(
            identifier=identifier,
            otp_code=otp_hash,
            purpose=purpose,
            expires_at=now + timedelta(minutes=OTPRecord.VALIDITY_MINUTES),
            is_used=False,
        )

        cls._send_email(identifier, otp_code)

    @staticmethod
    def verify(identifier: str, otp_code: str, purpose: str = 'registration') -> None:
        identifier = identifier.strip().lower()
        record = OTPRecord.objects.filter(identifier=identifier, purpose=purpose).first()

        if record is None:
            raise OTPVerificationException('No OTP found. Please request a new one.')

        if record.is_used:
            raise OTPVerificationException('OTP already used. Please request a new one.')

        if record.is_expired():
            raise OTPVerificationException('OTP expired. Please request a new one.')

        if not record.verify_code(otp_code):
            raise OTPVerificationException('Incorrect OTP.')

        record.is_used = True
        record.save(update_fields=['is_used'])


def _build_email_html(otp: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px; }}
    .container {{ background-color: white; border-radius: 10px; padding: 30px;
                 max-width: 500px; margin: 0 auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
    .header {{ color: #ff6b35; text-align: center; margin-bottom: 20px; }}
    .otp-box {{ background-color: #fff3e0; border: 2px solid #ff6b35; border-radius: 8px;
               padding: 20px; text-align: center; margin: 20px 0; }}
    .otp-code {{ font-size: 32px; font-weight: bold; color: #ff6b35; letter-spacing: 5px; }}
    .footer {{ color: #666; font-size: 12px; text-align: center; margin-top: 20px; }}
  </style>
</head>
<body>
  <div class="container">
    <h1 class="header">🏠 ROHII Hostel Hunt</h1>
    <p>Welcome! Use the following One-Time Password (OTP) to verify your email address:</p>
    <div class="otp-box">
      <div class="otp-code">{otp}</div>
    </div>
    <p><strong>⏰ This OTP is valid for 5 minutes only.</strong></p>
    <p>If you didn't request this OTP, please ignore this email.</p>
    <div class="footer">
      <p>© 2026 ROHII Hostel Hunt. All rights reserved.</p>
      <p>This is an automated email. Please do not reply.</p>
    </div>
  </div>
</body>
</html>"""
