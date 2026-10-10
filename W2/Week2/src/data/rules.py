"""Pure, testable validation and normalisation rules for the Week 2 pipeline.

Every function here is deterministic and has no side effects, so it can be unit-tested
(see tests/test_rules.py) and reused by later weeks.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timedelta, timezone

# ----------------------------------------------------------------------------- hashing
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def record_hash(values: list[str]) -> str:
    """Stable hash of a raw record (field values joined with an unlikely separator)."""
    return sha256_text("\x1f".join(values))


# ----------------------------------------------------------------------------- text
_WS = re.compile(r"\s+")


def normalise_whitespace(text: str) -> str:
    return _WS.sub(" ", unicodedata.normalize("NFC", text)).strip()


def dedup_key(text: str) -> str:
    """Key used for near-duplicate detection: case-folded, whitespace-collapsed text."""
    return normalise_whitespace(text).casefold()


def label_key(value: str) -> str:
    return re.sub(r"[\s\-]+", "_", value.strip().casefold())


# ----------------------------------------------------------------------------- timestamps
_ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_ISO_OFFSET = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")
_NAIVE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


def parse_offset(offset: str) -> timezone:
    sign = 1 if offset[0] == "+" else -1
    hh, mm = offset[1:].split(":")
    return timezone(sign * timedelta(hours=int(hh), minutes=int(mm)))


def parse_timestamp(raw: str, naive_offset: str = "+07:00") -> tuple[datetime | None, str]:
    """Return (UTC datetime, format_name) or (None, 'invalid')."""
    s = (raw or "").strip()
    try:
        if _ISO_Z.match(s):
            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc), "iso_utc"
        if _ISO_OFFSET.match(s):
            return datetime.fromisoformat(s).astimezone(timezone.utc), "iso_offset"
        if _NAIVE.match(s):
            local = datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=parse_offset(naive_offset))
            return local.astimezone(timezone.utc), "naive_local"
    except ValueError:
        return None, "invalid"
    return None, "invalid"


# ----------------------------------------------------------------------------- privacy
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\w)(?:\+84[ .-]?|0)\d{2,3}[ .-]?\d{3}[ .-]?\d{3,4}(?!\w)")
CARD_CANDIDATE_RE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")


def luhn_ok(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def contains_payment_card(text: str) -> bool:
    for m in CARD_CANDIDATE_RE.finditer(text or ""):
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and luhn_ok(digits):
            return True
    return False


def redact_pii(text: str) -> tuple[str, int]:
    """Replace e-mail addresses and phone numbers. Returns (redacted_text, n_replacements)."""
    text, n1 = EMAIL_RE.subn("[EMAIL]", text)
    text, n2 = PHONE_RE.subn("[PHONE]", text)
    return text, n1 + n2


def residual_pii(text: str) -> list[str]:
    """Used as a gate on PROCESSED output: anything found here is a pipeline failure."""
    found = []
    if EMAIL_RE.search(text or ""):
        found.append("email")
    if PHONE_RE.search(text or ""):
        found.append("phone")
    if contains_payment_card(text or ""):
        found.append("payment_card")
    return found


# ----------------------------------------------------------------------------- language
_VI_CHARS = re.compile(
    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]",
    re.IGNORECASE)


def detect_language(text: str, vi_min: int = 2) -> str:
    """Very small heuristic: the MVP scope is English only, so we only need to spot Vietnamese."""
    return "vi" if len(_VI_CHARS.findall(text or "")) >= vi_min else "en"


# ----------------------------------------------------------------------------- KB front matter
def parse_front_matter(raw: str) -> tuple[dict, str]:
    """Parse '---' delimited 'key: value' front matter. Returns (metadata, body)."""
    if not raw.startswith("---\n"):
        return {}, raw
    end = raw.find("\n---\n", 4)
    if end == -1:
        return {}, raw
    meta = {}
    for line in raw[4:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, raw[end + 5:]


def iqr_upper_fence(values: list[float], k: float) -> float:
    s = sorted(values)
    if not s:
        return float("inf")

    def q(p: float) -> float:
        pos = (len(s) - 1) * p
        lo = int(pos)
        hi = min(lo + 1, len(s) - 1)
        return s[lo] + (s[hi] - s[lo]) * (pos - lo)

    q1, q3 = q(0.25), q(0.75)
    return q3 + k * (q3 - q1)
