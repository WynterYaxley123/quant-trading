"""Authorized generation execution; no tuning after a phase claim."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .evaluation import directional_label, evaluate, validation_pass
from .lifecycle import Lifecycle
from .protocol import HORIZONS, Spec, digest, immutable


def execute(root: Path, repository: Path) -> dict[str, Any]:
    protocol_path = repository / "config/research/swl1-ridge-v1-protocol.json"
    protocol_hash = digest(protocol_path.read_bytes())
    lifecycle = Lifecycle(root / "lifecycle", protocol_path, protocol_hash)
    protocol = lifecycle.verify()
    for name, expected in protocol["implementation_hashes"].items():
        if digest((repository / name).read_bytes()) != expected:
            raise ValueError("PREREGISTERED_IMPLEMENTATION_MODIFIED")
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
    public = repository / "reports/research/swl1_ridge_v1"
    phase = protocol["split"]["indices"]
    development_claim = lifecycle.claim("development")
    leaderboard = []
    for value in protocol["specifications"]:
        spec = Spec(**value)
        metrics = evaluate(features, returns, dates, codes, phase["development"], spec)
        admitted = metrics["sufficient_dates"] and all(
            metrics["horizons"][str(h)]["mean_rank_ic"] is not None
            and metrics["horizons"][str(h)]["mean_rank_ic"] >= -0.02
            for h in HORIZONS
        )
        leaderboard.append(
            {"id": spec.identifier, "spec": value, "metrics": metrics, "admitted": admitted}
        )
        print(f"Development {spec.identifier}: admitted={admitted}", flush=True)
    lifecycle.complete("development", development_claim, {"leaderboard": leaderboard})
    immutable(
        public / "development.json", {"protocol_hash": protocol_hash, "leaderboard": leaderboard}
    )
    admitted_rows = [r for r in leaderboard if r["admitted"]]
    if not admitted_rows:
        status = {
            "scientific_status": "NO_DEVELOPMENT_CANDIDATE",
            "forward_eligible": False,
            "validation_opened": False,
            "final_oos_opened": False,
            "search_spec_count": len(leaderboard),
        }
    else:
        # Frozen 1e-12 numerical ties; remaining keys encode the preregistered order.
        best_score = max(r["metrics"]["composite_rank_ic"] for r in admitted_rows)
        tied = [
            r for r in admitted_rows if abs(r["metrics"]["composite_rank_ic"] - best_score) <= 1e-12
        ]
        selected = sorted(
            tied,
            key=lambda r: (
                -min(r["metrics"]["horizons"][str(h)]["mean_rank_ic"] for h in HORIZONS),
                r["spec"]["months"],
                -r["spec"]["alpha"],
                r["spec"]["policy"],
            ),
        )[0]
        candidate = {
            "spec": selected["spec"],
            "model_universe_hash": protocol["model_universe_hash"],
            "data_panel_sha256": protocol["data_panel_sha256"],
            "source_commit": protocol["source_commit"],
            "development": selected["metrics"],
            "scaling": "STANDARDIZED",
            "horizons": list(HORIZONS),
            "fusion": [0.25, 0.5, 0.25],
        }
        candidate_hash = lifecycle.freeze_candidate(candidate)
        immutable(
            repository / "config/research/swl1-ridge-v1-candidate.json",
            json.loads((lifecycle.root / "candidate.json").read_bytes()),
        )
        validation_claim = lifecycle.claim("validation")
        spec = Spec(**selected["spec"])
        metrics = evaluate(features, returns, dates, codes, phase["validation"], spec)
        passed = validation_pass(metrics)
        lifecycle.complete("validation", validation_claim, {"metrics": metrics, "passed": passed})
        immutable(
            public / "validation.json",
            json.loads((lifecycle.root / "validation.result.json").read_bytes()),
        )
        status = {
            "candidate_hash": candidate_hash,
            "validation_opened": True,
            "validation_passed": passed,
            "final_oos_opened": False,
            "forward_eligible": False,
            "scientific_status": "FAILED_VALIDATION",
            "search_spec_count": len(leaderboard),
        }
        if passed:
            final_claim = lifecycle.claim("final_oos")
            metrics = evaluate(features, returns, dates, codes, phase["final_oos"], spec)
            label = directional_label(metrics)
            lifecycle.complete(
                "final_oos",
                final_claim,
                {"metrics": metrics, "directional_label": label, "consumed": True},
            )
            immutable(
                public / "final_oos_seal.json",
                json.loads((lifecycle.root / "final_oos_seal.json").read_bytes()),
            )
            immutable(
                public / "final_oos.json",
                json.loads((lifecycle.root / "final_oos.result.json").read_bytes()),
            )
            status.update(
                final_oos_opened=True,
                final_oos_consumed=True,
                directional_label=label,
                scientific_status="HISTORICAL_RESEARCH_CANDIDATE"
                if label in ("POSITIVE", "STRONG_POSITIVE")
                else f"FINAL_OOS_{label}",
                forward_eligible=label in ("POSITIVE", "STRONG_POSITIVE"),
            )
    status.update(
        protocol_hash=protocol_hash,
        validation_reopened=False,
        validation_informed_revision=False,
        final_oos_reopened=False,
        final_oos_retuned=False,
        formal_forward_forecasts_created=0,
        live_deployment_promoted=False,
        live_scheduler_enabled=False,
        etf_productization_status="NOT_STARTED",
        independent_statistical_confidence="LIMITED",
        historical_membership_confidence="RECONSTRUCTED",
    )
    immutable(public / "status.json", status)
    return status


if __name__ == "__main__":
    print(json.dumps(execute(Path("/research"), Path("/workspace")), indent=2))
