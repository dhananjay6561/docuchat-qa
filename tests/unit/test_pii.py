import pytest

from app.pii import mask_pii


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mail me at jane.doe@example.com", "mail me at [EMAIL]"),
        ("call +1 415-555-0132 now", "call [PHONE] now"),
        ("my number is 9876543210", "my number is [PHONE]"),
        ("card 4111 1111 1111 1111 please", "card [CARD] please"),
        ("card 4111-1111-1111-1111", "card [CARD]"),
    ],
)
def test_masks_personal_data(text: str, expected: str) -> None:
    masked, changed = mask_pii(text)
    assert masked == expected
    assert changed is True


@pytest.mark.parametrize(
    "text",
    [
        "Where is order ORD-1002?",
        "Invoice INV-2026-0042 total is 910.44 USD",
        "Leave accrues at 2 days per month",
        "tracking 1234567890123",  # 13 digits but fails the Luhn check, so not a card
    ],
)
def test_leaves_normal_text_alone(text: str) -> None:
    masked, changed = mask_pii(text)
    assert masked == text
    assert changed is False


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("+91 98765 43210", "[PHONE]"),
        ("+44 20 7946 0958", "[PHONE]"),
        ("98765-43210", "[PHONE]"),
        ("+1 (415) 555-0132", "[PHONE]"),
    ],
)
def test_masks_international_formats(text: str, expected: str) -> None:
    assert mask_pii(text)[0] == expected


def test_answer_guardrail_keeps_only_published_contacts() -> None:
    from app.pii import redact_answer

    published = frozenset({"support@lumenhome.example"})
    text = "Email support@lumenhome.example, not priya.sharma@brightside.example or refunds@evil.example."
    redacted, changed = redact_answer(text, published)
    assert changed
    assert "support@lumenhome.example" in redacted
    assert "priya.sharma" not in redacted and "refunds@evil.example" not in redacted
    assert redact_answer("Order ORD-1002 ships 2026-11-06 for 24.50 USD.", published) == (
        "Order ORD-1002 ships 2026-11-06 for 24.50 USD.",
        False,
    )
