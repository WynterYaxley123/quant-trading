"""One compatibility layer for external paths; public checks require no runtime."""

from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def runtime_root() -> Path:
    value = os.environ.get("ETF_QUANT_EXTERNAL_RUNTIME_ROOT")
    if value:
        return Path(value)
    if os.name == "nt":
        fallback = json.loads((REPO / "config/legacy-runtime.json").read_text())
        return Path(fallback["windows_runtime_root"])
    return (
        Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
        / "quant-trading/etf-quant-v1"
    )


def evidence_root(kind: str) -> Path:
    if kind not in {"PIT", "PROXY"}:
        raise ValueError("UNKNOWN_EVIDENCE_ROOT")
    value = os.environ.get(f"ETF_QUANT_{kind}_ROOT")
    return (
        Path(value)
        if value
        else runtime_root()
        / ("production-pit-evidence-v1" if kind == "PIT" else "proxy-exposure-v1")
    )
