"""PIT evidence validation contracts; public facade: schema.py."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime

EVIDENCE_SCHEMA_VERSION = "1.0.0"


TRACKING_IDENTITY = "ETF_TRACKING_RELATION_EVIDENCE_V1"


WEIGHT_IDENTITY = "BENCHMARK_CONSTITUENT_WEIGHT_EVIDENCE_V1"


CLASSIFICATION_IDENTITY = "SHENWAN_L2_CLASSIFICATION_EVIDENCE_V1"


EXPOSURE_IDENTITY = "BENCHMARK_L2_EXPOSURE_PIT_PACKAGE_V1"


MAPPING_IDENTITY = "B40_MAPPING_EVIDENCE_V1"


REGISTRY_IDENTITY = "PRODUCTION_PIT_EVIDENCE_REGISTRY_V1"


OFFICIAL_HOST_SUFFIXES = (
    "csindex.com.cn",
    "cnindex.com.cn",
    "sse.com.cn",
    "szse.cn",
    "swsresearch.com",
)


_HTTPS = re.compile(r"https:[/]{2}([^/@:\s]+)/([^\s#]+)")


_SHA256 = re.compile(r"[0-9a-f]{64}")


_SAFE_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*")


AVAILABILITY_HISTORICAL_PIT = "HISTORICAL_PIT_PROVEN"


AVAILABILITY_FORWARD_ONLY = "FORWARD_ONLY"


AVAILABILITY_UNUSABLE = "NOT_PRODUCTION_USABLE"


AVAILABILITY_STATES = (
    AVAILABILITY_HISTORICAL_PIT,
    AVAILABILITY_FORWARD_ONLY,
    AVAILABILITY_UNUSABLE,
)


VALIDITY_FORWARD_ONLY_UNTIL_SUPERSEDED = "FORWARD_ONLY_UNTIL_SUPERSEDED"


WEIGHT_COMPLETE = "COMPLETE"


WEIGHT_INCOMPLETE = "INCOMPLETE"


WEIGHT_QUALITY_STATES = (WEIGHT_COMPLETE, WEIGHT_INCOMPLETE)


CLASSIFICATION_OFFICIAL = "OFFICIAL_CLASSIFICATION"


CLASSIFICATION_CONFLICT = "CLASSIFICATION_CONFLICT"


CLASSIFICATION_UNCLASSIFIED = "UNCLASSIFIED_FOR_V1"


CLASSIFICATION_QUALITY_STATES = (
    CLASSIFICATION_OFFICIAL,
    CLASSIFICATION_CONFLICT,
    CLASSIFICATION_UNCLASSIFIED,
)


WEIGHT_SUM_BAND = (99.0, 100.5)


TRACKING_STATUSES = ("LISTED", "NOT_LISTED", "DELISTED", "UNKNOWN")


REJECTION_NO_OFFICIAL_WEIGHT = "NO_OFFICIAL_COMPLETE_WEIGHT_VECTOR"


REJECTION_CLASSIFICATION_INCOMPLETE = "CLASSIFICATION_INCOMPLETE"


REJECTION_CLASSIFICATION_CONFLICT = "CLASSIFICATION_CONFLICT"


REJECTION_NOT_YET_AVAILABLE = "EVIDENCE_NOT_AVAILABLE_AT_DECISION"


REJECTION_BELOW_THRESHOLD = "TARGET_EXPOSURE_BELOW_THRESHOLD"


REJECTION_NOT_LARGEST = "TARGET_NOT_LARGEST_L2"


REJECTION_NO_TRACKING = "NO_OFFICIAL_TRACKING_RELATION"


class EvidenceError(ValueError):
    """An evidence package could not be established from official artifacts."""

    def __init__(self, code: str, details: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.details = {} if details is None else details


def canonical_bytes(value) -> bytes:
    """Deterministic JSON encoding used for every hash in the evidence layer."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def sha256_json(value) -> str:
    return sha256_bytes(canonical_bytes(value))


def require_text(value, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": field_name})
    return value.strip()


def require_sha256(value, field_name: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": field_name})
    return value


def require_official_url(value, field_name: str) -> str:
    """Only an official HTTPS URL with a real path may be pinned."""
    if not isinstance(value, str):
        raise EvidenceError("EVIDENCE_OFFICIAL_SOURCE_BLOCKER", {"field": field_name})
    match = _HTTPS.fullmatch(value)
    if match is None:
        raise EvidenceError(
            "EVIDENCE_OFFICIAL_SOURCE_BLOCKER",
            {"field": field_name, "reason": "NOT_OFFICIAL_HTTPS_URL"},
        )
    host = match.group(1).lower()
    if not any(host == suffix or host.endswith("." + suffix) for suffix in OFFICIAL_HOST_SUFFIXES):
        raise EvidenceError(
            "EVIDENCE_OFFICIAL_SOURCE_BLOCKER",
            {"field": field_name, "host": host, "reason": "HOST_NOT_AN_OFFICIAL_PUBLISHER"},
        )
    return value


def require_safe_name(value, field_name: str) -> str:
    """Relative POSIX path of a pinned raw file, confined to the source root."""
    if not isinstance(value, str) or not value:
        raise EvidenceError("EVIDENCE_OFFICIAL_SOURCE_BLOCKER", {"field": field_name})
    if value.startswith("/") or "\\" in value or ".." in value.split("/"):
        raise EvidenceError(
            "EVIDENCE_OFFICIAL_SOURCE_BLOCKER",
            {"field": field_name, "reason": "ESCAPES_SOURCE_ROOT"},
        )
    for part in value.split("/"):
        if not _SAFE_NAME.fullmatch(part):
            raise EvidenceError(
                "EVIDENCE_OFFICIAL_SOURCE_BLOCKER",
                {"field": field_name, "reason": "UNSAFE_PATH_PART"},
            )
    return value


def parse_instant(value, field_name: str) -> datetime:
    """An explicit, timezone-aware instant. A naive timestamp is never assumed local."""
    if not isinstance(value, str):
        raise EvidenceError(
            "EVIDENCE_TIME_BLOCKER", {"field": field_name, "reason": "NOT_A_STRING"}
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvidenceError(
            "EVIDENCE_TIME_BLOCKER", {"field": field_name, "reason": "UNPARSEABLE"}
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvidenceError(
            "EVIDENCE_TIME_BLOCKER", {"field": field_name, "reason": "TIMEZONE_REQUIRED"}
        )
    return parsed


def parse_day(value, field_name: str) -> date:
    if not isinstance(value, str):
        raise EvidenceError("EVIDENCE_TIME_BLOCKER", {"field": field_name})
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise EvidenceError(
            "EVIDENCE_TIME_BLOCKER", {"field": field_name, "reason": "NOT_AN_ISO_DATE"}
        ) from error


def optional_instant(value, field_name: str) -> datetime | None:
    return None if value is None else parse_instant(value, field_name)


def optional_day(value, field_name: str) -> date | None:
    return None if value is None else parse_day(value, field_name)


def parse_weight_pct(value):
    """Parse an official weight, or ``None`` when the provider published none.

    This evidence boundary accepts JSON numbers and strings only. The research
    proxy parser also accepts objects with numeric text representations; keep
    these distinct contracts. A missing weight is missing evidence, never zero.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if number == number and abs(number) != float("inf") else None
    if isinstance(value, str):
        text = value.strip()
    else:
        return None
    if not text:
        return None
    if text.endswith("%"):
        text = text[:-1].strip()
    if text in {"-", "--", "- -", "—", "N/A", "n/a"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if number == number and abs(number) != float("inf") else None


def bare_code(value) -> str:
    """``600519.SH`` -> ``600519``. The identity used on both sides of a join."""
    if not isinstance(value, str):
        return ""
    return value.strip().split(".")[0].strip()


B40_MIN_TARGET_EXPOSURE = 40.0
