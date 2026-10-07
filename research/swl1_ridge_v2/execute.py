"""Authorized V2 Development and single Validation; Final OOS is prospective."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from research.swl1_ridge_v1.evaluation import validation_pass
from research.swl1_ridge_v1.protocol import HORIZONS, digest, immutable

from .anchor import PROTOCOL, public_anchor
from .evaluation import development_admitted, evaluate
from .lifecycle import Lifecycle
from .protocol import Spec

PUBLIC = "reports/research/swl1_ridge_v2"


def select(admitted: list[dict[str, Any]]) -> dict[str, Any]:
    best = max(r["metrics"]["composite_rank_ic"] for r in admitted)
    tied = [r for r in admitted if abs(r["metrics"]["composite_rank_ic"] - best) <= 1e-12]
    return sorted(
        tied,
        key=lambda r: (
            -min(r["metrics"]["horizons"][str(h)]["mean_rank_ic"] for h in HORIZONS),
            r["spec"]["months"],
            -r["spec"]["penalty"],
            r["spec"]["policy"],
        ),
    )[0]


def execute(root: Path, repository: Path, remote_ref: str) -> dict[str, Any]:
    protocol_path = repository / PROTOCOL
    protocol_hash = digest(protocol_path.read_bytes())
    lifecycle = Lifecycle(root / "lifecycle", protocol_path, protocol_hash)
    protocol = lifecycle.verify()
    for name, expected in protocol["implementation_hashes"].items():
        if digest((repository / name).read_bytes()) != expected:
            raise ValueError("PREREGISTERED_IMPLEMENTATION_MODIFIED")
    lifecycle.record_anchor(public_anchor(repository, remote_ref))
    if not protocol["research_feasible"]:
        return {
            "scientific_status": "NOT_RESEARCHABLE_WITH_CURRENT_DATA",
            "forward_eligible": False,
        }
    data_path = root / "factual_panel.npz"
    if digest(data_path.read_bytes()) != protocol["data_panel_sha256"]:
        raise ValueError("FROZEN_DATA_PANEL_MODIFIED")
    data = np.load(data_path, allow_pickle=False)
    features, returns = data["features"], data["returns"]
    dates, codes = data["dates"].tolist(), data["codes"].tolist()
    if codes != protocol["model_universe"]:
        raise ValueError("MODEL_UNIVERSE_DRIFT")
    public = repository / PUBLIC
    phase = protocol["split"]["indices"]
    development_claim = lifecycle.claim("development")
    leaderboard = []
    for value in protocol["specifications"]:
        spec = Spec(**value)
        metrics = evaluate(features, returns, dates, codes, phase["development"], spec)
        leaderboard.append(
            {
                "id": spec.identifier,
                "spec": value,
                "metrics": metrics,
                "admitted": development_admitted(metrics),
            }
        )
    lifecycle.complete("development", development_claim, {"leaderboard": leaderboard})
    immutable(
        public / "development.json", {"protocol_hash": protocol_hash, "leaderboard": leaderboard}
    )
    status: dict[str, Any] = {
        "scientific_status": "NO_DEVELOPMENT_CANDIDATE",
        "validation_opened": False,
        "search_spec_count": len(leaderboard),
    }
    admitted = [r for r in leaderboard if r["admitted"]]
    if admitted:
        selected = select(admitted)
        candidate_hash = lifecycle.freeze_candidate(
            {
                "spec": selected["spec"],
                "model_universe_hash": protocol["model_universe_hash"],
                "data_panel_sha256": protocol["data_panel_sha256"],
                "source_commit": protocol["source_commit"],
                "development": selected["metrics"],
            }
        )
        immutable(
            repository / "config/research/swl1-ridge-v2-candidate.json",
            json.loads((lifecycle.root / "candidate.json").read_bytes()),
        )
        claim = lifecycle.claim("validation")
        metrics = evaluate(
            features, returns, dates, codes, phase["validation"], Spec(**selected["spec"])
        )
        passed = validation_pass(metrics)
        lifecycle.complete("validation", claim, {"metrics": metrics, "passed": passed})
        immutable(
            public / "validation.json",
            json.loads((lifecycle.root / "validation.result.json").read_bytes()),
        )
        status = {
            "candidate_hash": candidate_hash,
            "validation_opened": True,
            "validation_passed": passed,
            "scientific_status": "AWAITING_PROSPECTIVE_FINAL_OOS"
            if passed
            else "FAILED_VALIDATION",
            "search_spec_count": len(leaderboard),
        }
    status.update(
        protocol_hash=protocol_hash,
        final_oos_opened=False,
        final_oos="PROSPECTIVE_FORWARD_ONLY",
        forward_eligible=False,
        etf_productization_status="NOT_STARTED",
        independent_statistical_confidence="LIMITED",
        historical_membership_confidence="RECONSTRUCTED",
    )
    immutable(public / "status.json", status)
    return status


if __name__ == "__main__":
    import sys

    print(json.dumps(execute(Path("/research"), Path("/workspace"), sys.argv[1]), indent=2))
