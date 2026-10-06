"""Current certified scientific labels over the immutable historical release.

The original gate decision is exposed only as ``historical_classification``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from strategies.etf_quant.runtime.implementation import verify_implementation

from .refresh import checksum
from .runtime import content_hash

RELEASE = "strategies/etf_quant_v2/config/release.json"
CANDIDATE = "strategies/etf_quant_v2/config/candidate.json"
REGISTRY = "strategies/etf_quant_v2/config/mapping-registry.json"
FINAL = "reports/engineering/etf-quant-v2-final-oos.json"
FREEZE = "config/research/etf-quant-v2-final-oos-freeze.json"
ASSESSMENT = "config/research/etf-quant-v2-scientific-status.json"
STATUSES = {
    "PASS_STRONG": "HISTORICALLY_VALIDATED_STRONG",
    "PASS_WEAK": "HISTORICALLY_VALIDATED_WEAK",
    "FAIL": "FINAL_OOS_FAILED_FORWARD_SHADOW_EXPERIMENT",
}
OVERLAY_LABELS = frozenset(
    {
        "scientific_status",
        "product_status",
        "final_oos_directional_label",
        "independent_statistical_confidence",
        "historical_membership_confidence",
        "etf_execution_historical_validation",
    }
)


def current_release(release: dict[str, Any], labels: dict[str, Any]) -> dict[str, Any]:
    """Overlay current labels; the original gate decision keeps a historical name."""
    if set(labels) != OVERLAY_LABELS:
        raise ValueError("V2_SCIENTIFIC_OVERLAY_IDENTITY_ERROR")
    current = {k: v for k, v in release.items() if k != "classification"}
    current["historical_classification"] = release["classification"]
    return current | labels


def load_release(repository: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    files = verify_implementation(repository)
    for name in (RELEASE, CANDIDATE, REGISTRY, FINAL, FREEZE, ASSESSMENT):
        if files.get(name) != checksum(repository / name):
            raise ValueError("CERTIFIED_V2_RELEASE_REQUIRED")
    release, candidate, registry, final, freeze = [
        json.loads((repository / name).read_bytes())
        for name in (RELEASE, CANDIDATE, REGISTRY, FINAL, FREEZE)
    ]
    if (
        content_hash({k: v for k, v in release.items() if k != "release_sha256"})
        != release["release_sha256"]
        or content_hash({k: v for k, v in registry.items() if k != "registry_sha256"})
        != registry["registry_sha256"]
    ):
        raise ValueError("V2_RELEASE_IDENTITY_ERROR")
    if (
        release["candidate_sha256"] != candidate["candidate_sha256"]
        or release["registry_sha256"] != registry["registry_sha256"]
        or release["final_oos_sha256"] != checksum(repository / FINAL)
        or final["freeze_sha256"] != freeze["freeze_sha256"]
        or final["candidate_sha256"] != candidate["candidate_sha256"]
        or final["open_count"] != 1
        or final["model_retuned"] is not False
        or final["decision"]["scientific_status"] != STATUSES[final["decision"]["classification"]]
        or release["scientific_status"] != final["decision"]["scientific_status"]
        or release["broker_enabled"] is not False
        or release["real_order_path"] is not False
        or release["initial_capital"] != "10000"
        or release["lot_size"] != 100
    ):
        raise ValueError("V2_FINALIZATION_CONTRACT_ERROR")
    assessment = json.loads((repository / ASSESSMENT).read_bytes())
    if (
        assessment["candidate_sha256"] != candidate["candidate_sha256"]
        or assessment["final_oos_sha256"] != release["final_oos_sha256"]
        or assessment["original_final_oos_sessions"] != final["metrics"]["signals"]
        or assessment["original_final_oos_consumed"] is not True
        or assessment["original_final_oos_resealed"] is not False
        or assessment["post_oos_extension"] is not None
    ):
        raise ValueError("V2_SCIENTIFIC_OVERLAY_IDENTITY_ERROR")
    # The release digest still identifies the immutable original model/runtime
    # contract. Current epistemic labels are a separately certified overlay.
    return current_release(release, assessment["labels"]), candidate, registry
