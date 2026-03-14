import re


AADHAAR_RE = re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
OTP_CVV_PIN_RE = re.compile(r"(?i)\b(otp|cvv|pin)\b(\s*(?:is|:|-)?\s*)(\d{3,8})\b")
SENSITIVE_TOPIC_RE = re.compile(
    r"(?i)\b(otp|cvv|pin|aadhaar number|aadhar number|full aadhaar|card number|debit card number|credit card number)\b"
)


def _mask_keep_last4(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) <= 4:
        return "*" * len(digits)
    return "X" * (len(digits) - 4) + digits[-4:]


def _mask_aadhaar(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    masked = "XXXX XXXX " + digits[-4:]
    return masked


def _mask_card(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    if len(digits) < 13:
        return match.group(0)
    masked = _mask_keep_last4(digits)
    chunks = [masked[i:i + 4] for i in range(0, len(masked), 4)]
    return " ".join(chunks)


def _mask_otp_like(match: re.Match) -> str:
    return f"{match.group(1)}{match.group(2)}****"


def mask_sensitive_text(text: str) -> str:
    if not text:
        return text

    masked = OTP_CVV_PIN_RE.sub(_mask_otp_like, text)
    masked = AADHAAR_RE.sub(_mask_aadhaar, masked)
    masked = CARD_RE.sub(_mask_card, masked)
    return masked


def contains_sensitive_financial_input(text: str) -> bool:
    if not text:
        return False

    if SENSITIVE_TOPIC_RE.search(text):
        return True

    if OTP_CVV_PIN_RE.search(text):
        return True

    return False