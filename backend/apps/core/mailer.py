"""
Transactional email (OTP codes).

Render's free plan blocks SMTP, so the default path is an HTTPS call to an email API with a short timeout.
SMTP stays available for a server that allows it (your own server, or a paid Render instance).

  EMAIL_API_PROVIDER = brevo | resend     (with EMAIL_API_KEY)   -> HTTPS API
  otherwise EMAIL_HOST_USER / EMAIL_HOST_PASSWORD                -> SMTP, socket timeout EMAIL_TIMEOUT
  neither                                                        -> EmailNotConfigured

The sender is DEFAULT_FROM_EMAIL ("Name <address>"). The provider decides which senders it accepts: Brevo
accepts a single verified sender address, Resend needs a verified domain.

Nothing here logs the recipient, the subject or the body: only the provider name and an outcome.
"""
import logging
from email.utils import parseaddr

from django.conf import settings
from django.core.mail import send_mail

from . import outbound

logger = logging.getLogger('apps.core.mailer')


class EmailError(Exception):
    """The email could not be sent. `kind` is one of the constants below; it is safe to log, never shown to users."""

    TIMEOUT = 'timeout'
    UNREACHABLE = 'unreachable'
    CREDENTIALS = 'credentials'
    REJECTED = 'rejected'
    PROVIDER_DOWN = 'provider_down'
    NOT_CONFIGURED = 'not_configured'

    def __init__(self, kind):
        super().__init__(kind)
        self.kind = kind


def is_configured():
    return bool(_api_provider() or getattr(settings, 'EMAIL_HOST_USER', ''))


def _api_provider():
    provider = (getattr(settings, 'EMAIL_API_PROVIDER', '') or '').strip().lower()
    if provider and getattr(settings, 'EMAIL_API_KEY', ''):
        return provider
    return ''


def _sender():
    name, address = parseaddr(settings.DEFAULT_FROM_EMAIL)
    return name, address


def _brevo(to, subject, text, html):
    name, address = _sender()
    return 'https://api.brevo.com/v3/smtp/email', {'api-key': settings.EMAIL_API_KEY, 'accept': 'application/json'}, {
        'sender': {'name': name or 'Hostel Hunt', 'email': address},
        'to': [{'email': to}],
        'subject': subject,
        'textContent': text,
        # Brevo documents htmlContent as required when no template is used.
        'htmlContent': html or '<p>' + text.replace('&', '&amp;').replace('<', '&lt;') + '</p>',
    }


def _resend(to, subject, text, html):
    payload = {'from': settings.DEFAULT_FROM_EMAIL, 'to': [to], 'subject': subject, 'text': text}
    if html:
        payload['html'] = html
    return 'https://api.resend.com/emails', {'Authorization': f'Bearer {settings.EMAIL_API_KEY}'}, payload


PROVIDERS = {'brevo': _brevo, 'resend': _resend}


def _send_with_api(provider, to, subject, text, html):
    build = PROVIDERS.get(provider)
    if build is None:
        logger.error('Unknown EMAIL_API_PROVIDER %r (use one of: %s)', provider, ', '.join(sorted(PROVIDERS)))
        raise EmailError(EmailError.NOT_CONFIGURED)
    url, headers, payload = build(to, subject, text, html)
    try:
        reply = outbound.post(url, json=payload, headers=headers, timeout=(2.0, 3.5))
    except outbound.requests.Timeout:
        logger.error('Email provider %s timed out', provider)
        raise EmailError(EmailError.TIMEOUT) from None
    except outbound.requests.RequestException as exc:
        logger.error('Email provider %s unreachable: %s', provider, type(exc).__name__)
        raise EmailError(EmailError.UNREACHABLE) from None

    if 200 <= reply.status_code < 300:
        logger.info('Email accepted by %s', provider)
        return
    logger.error('Email provider %s answered HTTP %s', provider, reply.status_code)
    if reply.status_code in (401, 403):
        raise EmailError(EmailError.CREDENTIALS)
    if reply.status_code == 429 or reply.status_code >= 500:
        raise EmailError(EmailError.PROVIDER_DOWN)
    raise EmailError(EmailError.REJECTED)


def _send_with_smtp(to, subject, text, html):
    try:
        send_mail(subject, text, settings.DEFAULT_FROM_EMAIL, [to], html_message=html, fail_silently=False)
    except Exception as exc:  # smtplib, socket timeouts and TLS errors: only the type name is logged
        logger.error('SMTP send failed: %s', type(exc).__name__)
        raise EmailError(EmailError.TIMEOUT if isinstance(exc, TimeoutError) else EmailError.UNREACHABLE) from None
    logger.info('Email accepted by SMTP')


def send_email(to, subject, text, html=None):
    """Send one email or raise EmailError. Never takes longer than about 6 seconds."""
    provider = _api_provider()
    if provider:
        return _send_with_api(provider, to, subject, text, html)
    if getattr(settings, 'EMAIL_HOST_USER', ''):
        return _send_with_smtp(to, subject, text, html)
    logger.error('Email not sent: no email provider is configured (EMAIL_API_PROVIDER/EMAIL_API_KEY or EMAIL_HOST_USER).')
    raise EmailError(EmailError.NOT_CONFIGURED)
