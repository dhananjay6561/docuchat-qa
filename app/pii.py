"""Masks personal data before anything is written to the log database.

Cards are masked first because a card number also contains phone-number-shaped digit runs.
"""

import re

CARD = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
PHONE = re.compile(r"(?<![\w-])(?:\+\d{1,3}[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4}\b")
# International numbers group digits differently (+91 98765 43210, +44 20 7946 0958), so any
# "+country code" followed by 2-5 digit groups counts. Found by the log audit (REG-001, REG-002).
INTL_PHONE = re.compile(r"(?<![\w-])\+\d{1,3}(?:[ .-]?\d{2,5}){2,4}\b")
IN_LOCAL_PHONE = re.compile(r"(?<![\w-])\d{5}[ -]\d{5}\b")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _luhn_ok(digits: str) -> bool:
    # Luhn check avoids masking long numbers that aren't cards (invoice or tracking numbers).
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def _mask_card(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return "[CARD]" if 13 <= len(digits) <= 19 and _luhn_ok(digits) else match.group(0)


def _mask_intl(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return "[PHONE]" if 9 <= len(digits) <= 15 else match.group(0)  # E.164 allows up to 15 digits


def mask_pii(text: str) -> tuple[str, bool]:
    """Return (masked_text, was_anything_masked)."""
    masked = CARD.sub(_mask_card, text)
    masked = INTL_PHONE.sub(_mask_intl, masked)
    masked = PHONE.sub("[PHONE]", masked)
    masked = IN_LOCAL_PHONE.sub("[PHONE]", masked)
    masked = EMAIL.sub("[EMAIL]", masked)
    return masked, masked != text


def redact_answer(text: str, published_emails: frozenset[str]) -> tuple[str, bool]:
    """Output guardrail: remove contact details from a model answer before the user sees it.

    The model can be talked into repeating personal or planted contact details found in documents
    (red-team P01/P04). A prompt rule can be bypassed; this filter can't. Addresses the business
    publishes on purpose (e.g. the support email) are kept.
    """

    def keep_published(match: re.Match[str]) -> str:
        return match.group(0) if match.group(0).lower() in published_emails else "[contact removed]"

    redacted = EMAIL.sub(keep_published, text)
    redacted = CARD.sub(_mask_card, redacted)
    redacted = INTL_PHONE.sub(_mask_intl, redacted)
    redacted = PHONE.sub("[PHONE]", redacted)
    return redacted, redacted != text
