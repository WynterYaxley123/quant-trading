"""V1 exclusive phase claims plus a publication anchor; no historical Final OOS."""

from __future__ import annotations

from typing import Any

from research.swl1_ridge_v1.lifecycle import Lifecycle as FrozenLifecycle
from research.swl1_ridge_v1.protocol import immutable


class Lifecycle(FrozenLifecycle):
    def freeze_candidate(self, candidate: dict[str, Any]) -> str:
        if not (self.root / "development.result.json").is_file():
            raise ValueError("COMPLETED_DEVELOPMENT_REQUIRED")
        return super().freeze_candidate(candidate)

    def record_anchor(self, anchor: dict[str, Any]) -> str:
        self.verify()
        return immutable(self.root / "anchor.json", anchor)

    def claim(self, phase: str) -> dict[str, Any]:
        if phase == "final_oos":
            raise ValueError("PROSPECTIVE_FINAL_OOS_ONLY")
        if phase == "development" and not (self.root / "anchor.json").is_file():
            raise ValueError("PUBLIC_PREREGISTRATION_ANCHOR_REQUIRED")
        return super().claim(phase)
