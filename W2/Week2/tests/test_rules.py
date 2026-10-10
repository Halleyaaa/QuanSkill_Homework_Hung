"""Unit tests for the pure validation / normalisation rules."""
from datetime import timezone

from src.data import rules as R


def test_timestamp_formats_normalise_to_utc():
    a, fa = R.parse_timestamp("2026-07-03T07:22:10Z")
    b, fb = R.parse_timestamp("2026-07-03T14:22:10+07:00")
    c, fc = R.parse_timestamp("2026-07-03 14:22:10", "+07:00")
    assert a == b == c and a.tzinfo == timezone.utc
    assert (fa, fb, fc) == ("iso_utc", "iso_offset", "naive_local")


def test_invalid_timestamps_rejected():
    for bad in ["31/02/2026 10:00", "N/A", "2026-13-05T10:00:00Z", "yesterday", "0000-00-00 00:00:00", ""]:
        assert R.parse_timestamp(bad)[0] is None


def test_payment_card_detection_uses_luhn():
    assert R.contains_payment_card("my card is 4111 1111 1111 1111 thanks")
    assert not R.contains_payment_card("order ORD-48213, 500,000 VND")
    assert not R.contains_payment_card("1234 5678 9012 3456")  # fails Luhn


def test_pii_redaction():
    text, n = R.redact_pii("Mail me at cust1234@example.com or call 0945 123 456.")
    assert n == 2 and "[EMAIL]" in text and "[PHONE]" in text
    assert R.residual_pii(text) == []


def test_order_numbers_are_not_phones():
    assert R.redact_pii("Order ORD-82414 is late")[1] == 0


def test_language_heuristic():
    assert R.detect_language("Hoàn tiền đơn hàng mất bao lâu vậy?") == "vi"
    assert R.detect_language("When will my refund arrive?") == "en"


def test_label_key_normalises_variants():
    assert R.label_key("Return Policy") == R.label_key("return-policy") == "return_policy"


def test_front_matter():
    meta, body = R.parse_front_matter("---\nkb_id: KB-1\nowner: \n---\nBody text\n")
    assert meta == {"kb_id": "KB-1", "owner": ""} and body.strip() == "Body text"


def test_iqr_fence():
    assert R.iqr_upper_fence([1, 2, 3, 4, 5], 3.0) == 4 + 3 * 2
