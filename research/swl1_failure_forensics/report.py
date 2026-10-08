"""Explicit aggregate boundary and finite JSON encoding for public diagnostics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PRIVATE_KEYS = frozenset(
    (
        "signal_date",
        "predictions",
        "prediction",
        "raw_returns",
        "fit_records",
        "membership",
        "industry_code",
        "coefficients",
    )
)


def public_safe(value: Any) -> None:
    if isinstance(value, dict):
        if PRIVATE_KEYS.intersection(value):
            raise ValueError("PRIVATE_DIAGNOSTIC_PUBLICATION_BLOCKED")
        for item in value.values():
            public_safe(item)
    elif isinstance(value, list):
        if len(value) > 100:
            raise ValueError("PER_DATE_OR_LARGE_PAYLOAD_BLOCKED")
        for item in value:
            public_safe(item)
    json.dumps(value, allow_nan=False)


def write(path: Path, value: Any, *, public: bool = False) -> None:
    if path.is_symlink():
        raise ValueError("OUTPUT_SYMLINK_BLOCKED")
    if public:
        public_safe(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
