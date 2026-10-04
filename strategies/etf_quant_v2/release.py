"""Certified final scientific status, separate from immutable research freezes."""

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
STATUSES = {
    "PASS_STRONG": "HISTORICALLY_VALIDATED_STRONG",
    "PASS_WEAK": "HISTORICALLY_VALIDATED_WEAK",
    "FAIL": "FINAL_OOS_FAILED_FORWARD_SHADOW_EXPERIMENT",
}


def load_release(repository: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    files = verify_implementation(repository)
    for name in (RELEASE, CANDIDATE, REGISTRY, FINAL, FREEZE):
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
    return release, candidate, registry
