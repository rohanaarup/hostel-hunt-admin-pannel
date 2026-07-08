import random
import string
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import OTPRecord

class OTPService:
    @staticmethod
    def generate_otp_code(length=6):
        """Generates a numeric OTP code."""
        return ''.join(random.choices(string.digits, k=length))
        
    @staticmethod
    def create_otp(identifier, purpose):
        """Creates an OTP record for a given identifier."""
        # Invalidate ALL existing OTP records for this identifier/purpose
        # This covers both unverified OTPs AND verified-but-unconsumed tokens
        OTPRecord.objects.filter(
            identifier=identifier, 
            purpose=purpose, 
            is_used=False,
        ).update(is_used=True, verification_token=None)
        
        code = OTPService.generate_otp_code()
        
        from django.contrib.auth.hashers import make_password
        
        expires_at = timezone.now() + timedelta(minutes=10)
        
        record = OTPRecord.objects.create(
            identifier=identifier,
            otp_code=make_password(code),
            purpose=purpose,
            expires_at=expires_at
        )
        
        return code, record

    @staticmethod
    def verify_otp(identifier, code, purpose):
        """Verifies if an OTP is valid."""
        record = OTPRecord.objects.filter(
            identifier=identifier,
            purpose=purpose,
            is_used=False,
            is_verified=False,
            expires_at__gt=timezone.now()
        ).order_by('-created_at').first()
        
        from django.contrib.auth.hashers import check_password
        import uuid
        
        if not record:
            return False, "No valid OTP found or OTP has expired.", None
            
        if not check_password(code, record.otp_code):
            return False, "Invalid OTP code.", None
            
        # Mark as verified (NOT used) and generate verification token
        # The token stays valid until consumed by register/reset-password
        record.is_verified = True
        record.verification_token = uuid.uuid4()
        record.save()
        
        return True, "OTP verified successfully.", record.verification_token

    @staticmethod
    def send_otp(identifier, code, purpose, identifier_type):
        """Sends the OTP via Email or Phone and returns (success_bool, message)."""
        import logging
        import requests
        from requests.auth import HTTPBasicAuth
        
        logger = logging.getLogger('apps.owners.services')
        message = f"Your Hostel Hunt OTP code is: {code}. It is valid for 10 minutes."
        
        if identifier_type == 'email':
            subject = "Hostel Hunt - Verification Code"
            try:
                if not getattr(settings, 'EMAIL_HOST_USER', None):
                    if settings.DEBUG:
                        logger.warning(f"DEV FALLBACK: No EMAIL_HOST_USER. Printing OTP for {identifier}: {code}")
                        return True, "Email sent successfully (Dev Fallback)."
                    else:
                        return False, "SMTP credentials not configured."
                        
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [identifier],
                    fail_silently=False,
                )
                logger.info(f"SMTP EMAIL SENT TO {identifier}")
                return True, "Email sent successfully."
            except Exception as e:
                error_msg = f"SMTP authentication or connection failed: {str(e)}"
                logger.error(error_msg)
                if settings.DEBUG:
                    logger.warning(f"DEV FALLBACK: SMTP failed. Printing OTP for {identifier}: {code}")
                    return True, "Email sent successfully (Dev Fallback)."
                return False, error_msg
            
        elif identifier_type == 'phone':
            if not getattr(settings, 'TWILIO_ACCOUNT_SID', None) or not getattr(settings, 'TWILIO_AUTH_TOKEN', None):
                if settings.DEBUG:
                    logger.warning(f"DEV FALLBACK: No Twilio config. Printing OTP for {identifier}: {code}")
                    return True, "SMS sent successfully (Dev Fallback)."
                else:
                    error_msg = "SMS provider is not configured in the environment."
                    logger.error(error_msg)
                    return False, error_msg
                
            twilio_url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
            payload = {
                "To": identifier,
                "From": getattr(settings, 'TWILIO_FROM_NUMBER', ''),
                "Body": message
            }
            try:
                response = requests.post(
                    twilio_url, 
                    data=payload, 
                    auth=HTTPBasicAuth(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                )
                if response.status_code in [200, 201]:
                    logger.info(f"SMS SENT TO {identifier} via Twilio.")
                    return True, "SMS sent successfully."
                else:
                    error_msg = f"Twilio API Error ({response.status_code}): {response.text}"
                    logger.error(error_msg)
                    if settings.DEBUG:
                        logger.warning(f"DEV FALLBACK: Twilio failed. Printing OTP for {identifier}: {code}")
                        return True, "SMS sent successfully (Dev Fallback)."
                    return False, error_msg
            except requests.exceptions.RequestException as e:
                error_msg = f"Failed to connect to SMS provider: {str(e)}"
                logger.error(error_msg)
                if settings.DEBUG:
                    logger.warning(f"DEV FALLBACK: SMS connection failed. Printing OTP for {identifier}: {code}")
                    return True, "SMS sent successfully (Dev Fallback)."
                return False, error_msg
            
        return False, "Invalid identifier type."
