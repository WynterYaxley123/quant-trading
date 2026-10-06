"""Fail closed for retired ETF writes; retain explicitly isolated synthetic replay."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def guard_legacy_write(root: Path) -> None:
    allowed = os.environ.get("SWL2_LEGACY_SYNTHETIC_REPLAY_ROOT")
    if allowed:
        base = Path(allowed).resolve()
        temporary = Path(tempfile.gettempdir()).resolve()
        target = root.resolve()
        if base != temporary and base.is_relative_to(temporary) and target.is_relative_to(base):
            return
    raise ValueError("SWL2_ETF_PRODUCTIZATION_RETIRED_LEGACY_READ_ONLY")
