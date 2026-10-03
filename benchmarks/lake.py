"""Load the existing sidecar hash function for synthetic-only engineering checks."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch


def fingerprint_function() -> Callable[[Path], str]:
    root = Path(__file__).resolve().parents[1] / "services/cnequity-sidecar"
    spec = importlib.util.spec_from_file_location("synthetic_lake_runner", root / "runner.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with patch.object(sys, "path", [str(root), *sys.path]):
        spec.loader.exec_module(module)
    return module.lake_fingerprint
