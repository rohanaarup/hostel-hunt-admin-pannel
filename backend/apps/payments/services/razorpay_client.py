"""
apps/payments/services/razorpay_client.py
-----------------------------------------
THE ONLY file in this codebase that imports the razorpay SDK.

All Razorpay API interactions are centralised here:
  - create_order            → Orders API (creates a Razorpay order)
  - create_upi_intent       → Payments API (returns UPI deep-link URL)
  - get_card_checkout_session → Returns config dict for Flutter card checkout
  - verify_payment_signature → HMAC-SHA256 check using RAZORPAY_KEY_SECRET
  - verify_webhook_signature → HMAC check using RAZORPAY_WEBHOOK_SECRET (different secret)
  - initiate_refund          → Refunds API

RULES:
  1. Never import this SDK from any other file.
  2. RAZORPAY_KEY_SECRET and RAZORPAY_WEBHOOK_SECRET never leave this file or
     appear in any API response.  KEY_ID (public) may be returned to the client.
"""

import logging

import razorpay
import razorpay.errors
import requests as _requests
from django.conf import settings

logger = logging.getLogger('apps.payments')


# ─── SDK client factory ────────────────────────────────────────────────────────

def _get_client() -> razorpay.Client:
    """Return a lazily-initialised Razorpay SDK client using server-side credentials."""
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


# ─── Public API functions ──────────────────────────────────────────────────────

def create_order(amount_paise: int, receipt_id: str) -> dict:
    """
    Create a Razorpay order via the Orders API.

    Args:
        amount_paise: Amount in paise (INR × 100). Example: ₹6,500 → 650000.
        receipt_id:   Short unique identifier for this order (max 40 chars).
                      We use str(booking.id)[:40].

    Returns:
        Razorpay order dict, notably order['id'] (e.g. "order_XXXX").

    Raises:
        Exception on Razorpay API failure — caller should handle.
    """
    client = _get_client()
    order = client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt_id[:40],
        "payment_capture": 1,  # Auto-capture on payment success
    })
    logger.info("Razorpay order created: %s (amount=%s paise)", order.get('id'), amount_paise)
    return order


def create_upi_intent(
    order_id: str,
    amount_paise: int,
    upi_app: str,
    contact: str,
    email: str,
) -> str:
    """
    Create a Razorpay UPI payment with intent flow.

    Calls POST /v1/payments/create/upi directly (Razorpay SDK does not
    expose this endpoint as a named method).

    Args:
        order_id:    Razorpay order ID (order_XXXX) from create_order().
        amount_paise: Amount in paise, must match the order amount.
        upi_app:     'gpay' | 'phonepe' | 'paytm' (used for logging; intent URL
                     works with any installed UPI app).
        contact:     Student's phone number (required by Razorpay API).
        email:       Student's email (required by Razorpay API).

    Returns:
        UPI intent deep-link URL string (e.g. "upi://pay?pa=...").
        Returns empty string if Razorpay does not return a next[] link.

    Raises:
        Exception on API failure — caller should handle.
    """
    api_url = "https://api.razorpay.com/v1/payments/create/upi"
    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "order_id": order_id,
        "method": "upi",
        "upi": {"flow": "intent"},
        "contact": contact or "9000000000",
        "email": email or "student@hostelhunt.com",
        "ip": "127.0.0.1",
        "referer": "https://hostelhunt.com",
        "user_agent": "HostelHuntFlutterApp/1.0",
    }
    response = _requests.post(
        api_url,
        json=payload,
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    next_steps = data.get('next', [])
    intent_url = next_steps[0].get('url', '') if next_steps else ''

    logger.info(
        "UPI intent created: order=%s app=%s url_present=%s",
        order_id, upi_app, bool(intent_url),
    )
    return intent_url


def get_card_checkout_session(order_id: str) -> dict:
    """
    Return the configuration dict for Flutter's Razorpay hosted card checkout.

    Flutter should pass this config to the razorpay_flutter SDK's
    Razorpay.open() method, or construct a WebView checkout URL from it.

    No Razorpay API call is made here — the config is assembled from
    server-side settings and the provided order_id.

    Args:
        order_id: Razorpay order ID from create_order().

    Returns:
        Config dict with key, order_id, prefill fields, and theme.
    """
    return {
        "key": settings.RAZORPAY_KEY_ID,  # Public key — safe to send to client
        "order_id": order_id,
        "currency": "INR",
        "name": "Hostel Hunt",
        "description": "Hostel Bed Payment",
        "theme": {"color": "#B5451B"},  # Auburn — Hostel Hunt brand colour
        "method": {
            "upi": False,       # Disable UPI in card checkout (handled separately)
            "card": True,
            "netbanking": True,
            "wallet": False,
        },
    }


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """
    Verify Razorpay payment signature using RAZORPAY_KEY_SECRET.

    Algorithm: HMAC-SHA256(order_id + "|" + payment_id, key_secret)
    Used by VerifyPaymentView (card flow direct callback).

    Args:
        order_id:   Razorpay order ID.
        payment_id: Razorpay payment ID (pay_XXXX).
        signature:  razorpay_signature value from the client callback.

    Returns:
        True if signature is valid, False otherwise.
    """
    try:
        client = _get_client()
        client.utility.verify_payment_signature({
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature,
        })
        logger.info("Signature verified OK: order=%s payment=%s", order_id, payment_id)
        return True
    except razorpay.errors.SignatureVerificationError:
        logger.warning(
            "Signature FAILED: order=%s payment=%s", order_id, payment_id
        )
        return False


def verify_webhook_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """
    Verify Razorpay webhook HMAC signature using RAZORPAY_WEBHOOK_SECRET.

    IMPORTANT: Uses RAZORPAY_WEBHOOK_SECRET — NOT the KEY_SECRET.
    The two secrets are entirely different; do not substitute one for the other.

    Args:
        payload_bytes:    Raw request body bytes from WebhookView.
        signature_header: Value of X-Razorpay-Signature HTTP header.

    Returns:
        True if the webhook is genuine, False if tampered / unknown origin.
    """
    if not signature_header:
        logger.warning("Webhook signature header missing")
        return False
    try:
        client = _get_client()
        client.utility.verify_webhook_signature(
            payload_bytes.decode('utf-8'),
            signature_header,
            settings.RAZORPAY_WEBHOOK_SECRET,
        )
        return True
    except razorpay.errors.SignatureVerificationError:
        logger.warning("Webhook signature verification failed")
        return False
    except Exception as exc:
        logger.exception("Webhook verification error: %s", exc)
        return False


def initiate_refund(payment_id: str, amount_paise: int) -> dict:
    """
    Initiate a refund via Razorpay's Refunds API.

    Args:
        payment_id:   Razorpay payment ID (pay_XXXX) of the original charge.
        amount_paise: Amount to refund in paise. Pass the full amount for a
                      complete refund, or a smaller value for partial refund.

    Returns:
        Razorpay refund object dict (contains refund['id'] etc.).

    Raises:
        Exception on Razorpay API failure — caller should handle.
    """
    client = _get_client()
    refund = client.payment.refund(payment_id, {
        "amount": amount_paise,
        "speed": "normal",
        "notes": {"source": "HostelHunt Admin Refund"},
    })
    logger.info(
        "Refund initiated: refund_id=%s payment=%s amount=%s paise",
        refund.get('id'), payment_id, amount_paise,
    )
    return refund
