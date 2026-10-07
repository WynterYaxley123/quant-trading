"""Freeze one result-free V2 protocol on V1's admitted panel and universe."""

from __future__ import annotations

import json
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np

from research.swl1_ridge_v1.protocol import digest, eligible_signals, immutable

from .anchor import PROTOCOL
from .protocol import MONTHS, PENALTIES, POLICIES, split_sessions
from .seen import chronology_proof, v1_lineage

V1_PROTOCOL = "config/research/swl1-ridge-v1-protocol.json"


def implementation_hashes(repository: Path) -> dict[str, str]:
    """V2 sources and the frozen V1 sources they import."""
    return {
        p.relative_to(repository).as_posix(): digest(p.read_bytes())
        for package in ("research/swl1_ridge_v1", "research/swl1_ridge_v2")
        for p in sorted((repository / package).glob("*.py"))
    }


def preregister(root: Path, repository: Path, source_commit: str) -> dict[str, Any]:
    v1 = json.loads((repository / V1_PROTOCOL).read_bytes())
    panel = root / "factual_panel.npz"
    if digest(panel.read_bytes()) != v1["data_panel_sha256"]:
        raise ValueError("V1_ADMITTED_PANEL_REQUIRED")
    data = np.load(panel, allow_pickle=False)
    dates, codes = data["dates"].tolist(), data["codes"].tolist()
    if codes != v1["model_universe"]:
        raise ValueError("MODEL_UNIVERSE_DRIFT")
    # Common 24-month eligibility keeps both windows comparable, as in V1.
    eligible = eligible_signals(data["features"], data["returns"], dates, 24)
    last_seen = v1["split"]["ranges"]["validation"]["end"]
    split = split_sessions(dates, eligible, last_seen)
    proof = chronology_proof(v1, dates, split, v1_lineage(repository, root))
    protocol = {
        "protocol_version": "SWL1_RIDGE_V2_PREREGISTRATION_1",
        "family_id": "swl1_ridge_v2",
        "parent_generation": {
            "family_id": "swl1_ridge_v1",
            "status": "FAILED_VALIDATION",
            "protocol_hash": digest((repository / V1_PROTOCOL).read_bytes()),
        },
        "source_commit": source_commit,
        "research_feasible": split is not None,
        "data_panel_sha256": v1["data_panel_sha256"],
        "date_spine_hash": digest(json.dumps(dates, separators=(",", ":")).encode()),
        "model_universe": codes,
        "model_universe_hash": v1["model_universe_hash"],
        "primary_series": v1["primary_series"],
        "membership_confidence": "RECONSTRUCTED",
        "target": v1["target"],
        "horizons": v1["horizons"],
        "fusion": v1["fusion"],
        "scaling": "STANDARDIZED",
        "penalty_rule": "Ridge alpha = penalty x standardized training rows",
        "specifications": [
            {"penalty": penalty, "months": months, "policy": policy}
            for penalty, months, policy in product(PENALTIES, MONTHS, POLICIES)
        ]
        if split
        else [],
        "search_budget_max": len(PENALTIES) * len(MONTHS) * len(POLICIES),
        "seen_data": {
            "v1_last_validation_signal": last_seen,
            "rule": "All V1 Development/Validation outcome sessions are seen; every V2 Validation target session must be later. Predictor endpoint equality is permitted.",
        },
        "unseen_validation_proof": proof,
        "split": split,
        "development_admission": "All horizons sufficient; every mean RankIC >= -0.02; >=3/4 positive equal-calendar blocks.",
        "block_rule": "Four equal calendar durations over registered phase endpoints; min(3, floor(4*day_offset/span_days)); endpoints never shift after dropped signals.",
        "drop_accounting": "Every dropped signal records signal_date, phase, spec, horizon, reason_code; valid+dropped equals registered phase size. Full per-fit alpha evidence stays private; public aggregate ranges and hashes remain reproducible.",
        "selection": "Composite mean RankIC descending; 1e-12 ties; minimum horizon mean descending; 12m before 24m; larger penalty; policy lexical.",
        "validation_gate": v1["validation_gate"]
        | {"positive_chronological_blocks": ">=3/4 equal-calendar"},
        "final_oos": "PROSPECTIVE_FORWARD_ONLY",
        "final_oos_mode": "PROSPECTIVE_ONLY",
        "preregistration_anchor": "Protocol merged alone; Development requires its exact bytes on a fetched remote-tracking ref.",
        "independent_statistical_confidence": "LIMITED",
        "iid_inference": False,
        "failure_rules": v1["failure_rules"],
        "implementation_hashes": implementation_hashes(repository),
    }
    checksum = immutable(repository / PROTOCOL, protocol)
    return {
        "protocol_hash": checksum,
        "split": None if split is None else split["ranges"],
        "search_specs": len(protocol["specifications"]),
    }


if __name__ == "__main__":
    import sys

    print(json.dumps(preregister(Path("/research"), Path("/workspace"), sys.argv[1]), indent=2))
