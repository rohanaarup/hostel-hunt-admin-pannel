"""Development-only switches. Nothing here may be enabled in production."""
from django.conf import settings


def dev_otp_exposed():
    """True only when DEBUG is on AND EXPOSE_DEV_OTP is explicitly set.

    Gates every place an OTP value may appear in a response or a log line.
    Read at call time so tests can override either setting.
    """
    return bool(settings.DEBUG and getattr(settings, 'EXPOSE_DEV_OTP', False))
