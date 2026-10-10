"""
Text masking for logs and error reports.

mask_text() hides email addresses and phone-number-like digit runs. It is a
safety net: the first rule is not to log personal data at all.
"""
import re

_EMAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
# A standalone run of digits with optional +, spaces or dashes. Only treated as a
# phone number when it holds 9+ digits, so dates (2026-10-10) and small numbers survive,
# and hex ids (preceded by word characters) are never matched.
_PHONE = re.compile(r'(?<![\w.])\+?\d[\d\s-]{7,}\d(?![\w])')


def _mask_phone(match):
    digits = re.sub(r'\D', '', match.group())
    return '[phone]' if len(digits) >= 9 else match.group()


def mask_text(text):
    if not isinstance(text, str) or not text:
        return text
    return _PHONE.sub(_mask_phone, _EMAIL.sub('[email]', text))
