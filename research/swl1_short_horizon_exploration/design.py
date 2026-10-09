"""Verify the internal pre-diagnostic lock, never a scientific preregistration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research.swl1_failure_forensics.boundary import contained, sha

DESIGN = "config/research/swl1-short-horizon-exploratory-design.json"
DESIGN_SHA = "ad4c71407ef322183bc8b6205d3b54267a59b635f54602673b5c1735c619df1d"
LOCK_COMMIT = "ca959d99e01bc9093bde714dd67004f31940c09b"
LABEL = "EXPLORATORY_POST_HOC_RESEARCH"
REPORT_DIR = "reports/research/swl1_short_horizon_exploration"


def load_design(root: Path) -> dict[str, Any]:
    path = contained(root, DESIGN)
    if sha(path) != DESIGN_SHA:
        raise ValueError("EXPLORATORY_DESIGN_LOCK_CHANGED")
    result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return result
