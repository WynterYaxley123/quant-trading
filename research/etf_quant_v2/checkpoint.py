"""Resume a completed factual panel only after checking every recorded digest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .coverage import digest, external_directory


def completed_panel(root: Path) -> dict[str, Any] | None:
    external_directory(root)
    manifest = root / "panel.json"
    if not manifest.exists():
        return None
    doc = json.loads(manifest.read_text())
    if digest(root / "panel.npz") != doc["panel_sha256"]:
        raise ValueError("COMPLETED_PANEL_DIGEST_MISMATCH")
    for name, expected in doc["coverage_sha256"].items():
        if digest(root / "coverage" / name) != expected:
            raise ValueError("COVERAGE_CHECKPOINT_DIGEST_MISMATCH")
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    args = parser.parse_args()
    value = completed_panel(args.panel)
    print(
        json.dumps(
            {
                "status": "VERIFIED_COMPLETE" if value else "INCOMPLETE_REBUILD_REQUIRED",
                "data_sha256": value["data_sha256"] if value else None,
            }
        )
    )


if __name__ == "__main__":
    main()
