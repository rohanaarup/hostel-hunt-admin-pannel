"""
How a Razorpay payment's method becomes what we store (Phase 6).

Razorpay's payment entity carries a `method`: upi, card, netbanking, wallet, emi, paylater and so on. The webhook used to
record every capture as CARD because it "lacked method info"; it does not lack it. A capture whose entity has no method
at all is still recorded as CARD (the old behaviour), and a method we have no name for is OTHER.
"""
from .models import PaymentAttempt

_BY_ENTITY = {
    'upi': PaymentAttempt.Method.UPI,
    'card': PaymentAttempt.Method.CARD,
    'netbanking': PaymentAttempt.Method.NETBANKING,
    'wallet': PaymentAttempt.Method.WALLET,
}

_PAID_VIA = {
    PaymentAttempt.Method.UPI_GPAY: 'UPI',
    PaymentAttempt.Method.UPI_PHONEPE: 'UPI',
    PaymentAttempt.Method.UPI_PAYTM: 'UPI',
    PaymentAttempt.Method.UPI: 'UPI',
    PaymentAttempt.Method.CARD: 'CARD',
    PaymentAttempt.Method.NETBANKING: 'NETBANKING',
    PaymentAttempt.Method.WALLET: 'WALLET',
}


def attempt_method_for(entity_method):
    """The PaymentAttempt.Method for the `method` of a Razorpay payment entity."""
    if not entity_method:
        return PaymentAttempt.Method.CARD
    return _BY_ENTITY.get(str(entity_method).lower(), PaymentAttempt.Method.OTHER)


def paid_via_for(attempt_method):
    """UPI, CARD, NETBANKING, WALLET or OTHER, for an attempt method."""
    return _PAID_VIA.get(attempt_method, 'OTHER')


def paid_via_from_entity(entity_method):
    """What the entity itself says, or None when it says nothing (the caller then falls back to the attempt)."""
    if not entity_method:
        return None
    return paid_via_for(attempt_method_for(entity_method))
