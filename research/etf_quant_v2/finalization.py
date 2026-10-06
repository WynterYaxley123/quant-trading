"""One authorized, immutable Final-OOS evaluation of the existing revision.

The historical experiment module remains byte frozen. No search is exposed here.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .coverage import digest, external_directory, immutable_bytes, json_bytes
from .experiment import Array, bootstrap, component, evaluate, public_metrics
from .protocol import canonical_hash

STATUSES = {
    "PASS_STRONG": "HISTORICALLY_VALIDATED_STRONG",
    "PASS_WEAK": "HISTORICALLY_VALIDATED_WEAK",
    "FAIL": "FINAL_OOS_FAILED_FORWARD_SHADOW_EXPERIMENT",
}
# Declared by every new freeze. The consumed V2 gate predates it and keeps its
# original decision; it is never re-evaluated under this stricter rule.
STRONG_EVIDENCE = "DEPENDENCE_AWARE_UNCERTAINTY_AND_INDEPENDENT_TIER_A_REQUIRED"


def exclusive_json(path: Path, value: dict[str, Any]) -> None:
    """An access record cannot be overwritten, including after a failed process."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())


def classify(
    metrics: dict[str, Any], gate: dict[str, Any], development_ic: float
) -> dict[str, Any]:
    blocks = metrics["folds"]
    ic = metrics.get("mean_rank_ic")
    spread = metrics.get("mean_spread")
    positive = [max(float(b["mean_rank_ic"] or 0), 0) * b["signals"] for b in blocks]
    concentration = max(positive) / sum(positive) if sum(positive) else None
    majority = len(blocks) // 2 + 1
    temporal = (
        all(b["signals"] >= gate["minimum_block_observations"] for b in blocks)
        and sum(b["mean_rank_ic"] is not None and b["mean_rank_ic"] >= 0 for b in blocks)
        >= majority
        and sum(b["mean_spread"] is not None and b["mean_spread"] >= 0 for b in blocks) >= majority
        and all(b["mean_rank_ic"] is not None and b["mean_rank_ic"] >= -0.25 for b in blocks)
    )
    numerical = (
        metrics["signals"] >= gate["minimum_observations"]
        and metrics["minimum_component_fit_fraction"] >= 0.95
        and all(v is not None and v <= 1.0 for v in metrics["component_norm_cv"].values())
        and metrics["all_fitted_coefficients_finite"]
    )
    directional = ic is not None and spread is not None and ic > 0 and spread > 0
    ratio = (
        ic / development_ic
        if ic is not None and math.isfinite(development_ic) and development_ic > 0
        else None
    )
    secondary = {
        "concentration": concentration is not None and concentration <= 0.70,
        "development_direction_retention": ratio is not None and ratio >= 0.10,
    }
    weak = sum(not value for value in secondary.values())
    classification = (
        "FAIL"
        if not (directional and temporal and numerical) or weak > 1
        else "PASS_WEAK"
        if weak
        else "PASS_STRONG"
    )
    evidence = {}
    if gate.get("strong_evidence") == STRONG_EVIDENCE:
        # Overlapping labels without a dependence-aware interval, or a universe
        # without independent Tier A membership, cannot support a strong claim.
        uncertainty = metrics.get("uncertainty") or {}
        evidence = {
            "dependence_aware_uncertainty": uncertainty.get("bootstrap_ess") is not None,
            "independent_membership_evidence": gate.get("independent_membership_rows", 0) > 0,
        }
        if classification == "PASS_STRONG" and not all(evidence.values()):
            classification = "PASS_WEAK"
    decision = {
        "classification": classification,
        "scientific_status": STATUSES[classification],
        "product_status": "EXPERIMENTAL_UNVALIDATED_RESEARCH_SHADOW"
        if classification == "FAIL"
        else "HISTORICALLY_VALIDATED_RESEARCH_CANDIDATE",
        "directional": directional,
        "temporal_robustness": temporal,
        "numerical_stability": numerical,
        "secondary": secondary,
        "positive_block_ic_concentration": concentration,
        "development_to_oos_rank_ic_ratio": ratio,
    }
    if evidence:
        decision["strong_evidence"] = evidence
    return decision


def freeze(
    panel: Path, prior: Path, output: Path, repository: Path, base_sha: str
) -> dict[str, Any]:
    """Read metadata and already opened Development only; never OOS outcomes."""
    metadata = json.loads((panel / "panel.json").read_bytes())
    candidate_path = repository / "strategies/etf_quant_v2/config/candidate.json"
    candidate = json.loads(candidate_path.read_bytes())
    revision = json.loads((prior / "experiment/revision/candidate.json").read_bytes())
    protocol = json.loads((prior / "experiment/revision/protocol.json").read_bytes())
    if canonical_hash(revision) != candidate["research_candidate_sha256"]:
        raise ValueError("REVISION_HASH_MISMATCH")
    if (
        canonical_hash({k: v for k, v in candidate.items() if k != "candidate_sha256"})
        != candidate["candidate_sha256"]
    ):
        raise ValueError("CANDIDATE_HASH_MISMATCH")
    for name, expected in candidate["research_source_files"].items():
        if digest(repository / "research/etf_quant_v2" / name) != expected:
            raise ValueError("FROZEN_RESEARCH_CODE_CHANGED")
    if digest(panel / "panel.npz") != metadata["panel_sha256"]:
        raise ValueError("PANEL_HASH_MISMATCH")
    spec = candidate["specification"]
    if (
        spec["alpha"],
        spec["training_months"],
        spec["scaling"],
        spec["horizons"],
        spec["fusion"],
    ) != (30, 12, "RAW", [10, 40, 120], [0.25, 0.50, 0.25]):
        raise ValueError("EXISTING_REVISION_REQUIRED")
    start, end = protocol["split"]["final_oos_start"], protocol["split"]["final_oos_end"]
    count = end - start + 1
    block_count = min(4, count // 10)
    if block_count < 2:
        raise ValueError("INSUFFICIENT_PREDECLARED_OOS_CALENDAR")
    boundaries = [count * k // block_count for k in range(1, block_count)]
    offsets = [0, *boundaries, count]
    gate = {
        "minimum_observations": max(20, count * 2 // 3),
        "minimum_block_observations": 10,
        "block_partition": "CONTIGUOUS_EQUAL_CALENDAR_BLOCKS;MIN_10_CALENDAR_SESSIONS;NO_OUTCOME_DEPENDENCE",
        "blocks": [
            {"start": metadata["dates"][start + a], "end": metadata["dates"][start + b - 1]}
            for a, b in zip(offsets[:-1], offsets[1:], strict=True)
        ],
        "boundaries": boundaries,
        "direction": "MEAN_RANK_IC_GT_0_AND_MEAN_TOP5_BOTTOM5_H40_SPREAD_GT_0",
        "temporal": "STRICT_MAJORITY_NONNEGATIVE_IC_AND_SPREAD;MIN_BLOCK_OBSERVATIONS;WORST_IC_GE_MINUS_0.25",
        "concentration": "MAX_POSITIVE_BLOCK_IC_TIMES_OBSERVATIONS_OVER_SUM_LE_0.70;ZERO_SUM_FAILS",
        "degradation": "POSITIVE_DIRECTION_REQUIRED;IC_DEVELOPMENT_RATIO_GE_0.10_IS_SECONDARY",
        "numerical": "EACH_HORIZON_FIT_FRACTION_GE_0.95;NORM_CV_LE_1;FINITE_COEFFICIENTS",
        "classification": "CORE_OR_TEMPORAL_OR_NUMERICAL_FAILURE_FAIL;ONE_SECONDARY_WEAK_PASS_WEAK;ALL_PASS_PASS_STRONG;TWO_SECONDARY_FAILURES_FAIL",
        "uncertainty": "120_SESSION_BLOCK_BOOTSTRAP_ONLY_IF_AT_LEAST_240_CALENDAR_AND_160_OBSERVATIONS;OTHERWISE_NULL",
        "strong_evidence": STRONG_EVIDENCE,
        "independent_membership_rows": int(metadata["membership_tier_rows"]["A"]),
    }
    frozen = {
        "schema_version": 1,
        "contract": "ETF_QUANT_V2_FINAL_OOS_SINGLE_OPEN",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "base_sha": base_sha,
        "candidate_sha256": candidate["candidate_sha256"],
        "candidate_file_sha256": digest(candidate_path),
        "revision_sha256": canonical_hash(revision),
        "protocol_sha256": protocol["protocol_sha256"],
        "data_sha256": metadata["data_sha256"],
        "panel_sha256": metadata["panel_sha256"],
        "evaluation_code_sha256": digest(Path(__file__)),
        "research_source_files": candidate["research_source_files"],
        "specification": spec,
        "universe": {k: metadata[k] for k in ("industries", "universe_coverage_cutoff")},
        "evidence_mode": "HIGH_CONFIDENCE",
        "missingness": candidate["missingness_policy"],
        "training": protocol["training"],
        "tie_rule": "SCORE_DESCENDING_INDUSTRY_CODE_ASCENDING",
        "revision_rationale": protocol["generation_rule"],
        "development_rank_ic": revision["selected"]["metrics"]["mean_rank_ic"],
        "signal_indices": [start, end],
        "final_oos_start": metadata["dates"][start],
        "final_oos_end": metadata["dates"][end],
        "gate": gate,
        "gate_sha256": canonical_hash(gate),
        "open_count_maximum": 1,
        "retuning_allowed": False,
    }
    frozen["freeze_sha256"] = canonical_hash(frozen)
    exclusive_json(output / "freeze.json", frozen)
    return frozen


def final_targets(x: Array, close: Array, segments: Any, horizon: int, stop: int) -> Array:
    """Same centered target equation as frozen experiment.targets, authorized tail."""
    y = np.full(close.shape, np.nan)
    for t in range(min(stop + 1, len(close) - horizon)):
        active = np.isfinite(x[t]).all(axis=1)
        if active.sum() < 12:
            continue
        raw = close[t + horizon] / close[t] - 1
        good = np.isfinite(raw) & (segments[t + horizon] == segments[t])
        if good[active].all():
            y[t, active] = raw[active] - raw[active].mean()
    return y


def open_once(panel: Path, output: Path, repository: Path) -> dict[str, Any]:
    frozen = json.loads((output / "freeze.json").read_bytes())
    if (
        canonical_hash({k: v for k, v in frozen.items() if k != "freeze_sha256"})
        != frozen["freeze_sha256"]
    ):
        raise ValueError("FREEZE_INTEGRITY_ERROR")
    if (
        digest(Path(__file__)) != frozen["evaluation_code_sha256"]
        or digest(panel / "panel.npz") != frozen["panel_sha256"]
    ):
        raise ValueError("FINAL_OOS_INPUT_CHANGED")
    if (
        digest(repository / "strategies/etf_quant_v2/config/candidate.json")
        != frozen["candidate_file_sha256"]
    ):
        raise ValueError("FROZEN_CANDIDATE_CHANGED")
    for name, expected in frozen["research_source_files"].items():
        if digest(repository / "research/etf_quant_v2" / name) != expected:
            raise ValueError("FROZEN_RESEARCH_CODE_CHANGED")
    # A retry may read the same immutable completed result. It never fits again.
    access = output / "access.json"
    result_path = output / "result.json"
    if access.exists():
        receipt = json.loads(access.read_bytes())
        if receipt.get("freeze_sha256") != frozen["freeze_sha256"] or not result_path.exists():
            raise ValueError("FINAL_OOS_ALREADY_OPENED_NO_REEVALUATION")
        integrity = json.loads((output / "result-integrity.json").read_bytes())
        if digest(result_path) != integrity["result_sha256"]:
            raise ValueError("IMMUTABLE_FINAL_OOS_RESULT_CHANGED")
        return json.loads(result_path.read_bytes())
    exclusive_json(
        access,
        {
            "freeze_sha256": frozen["freeze_sha256"],
            "open_count": 1,
            "opened_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    metadata = json.loads((panel / "panel.json").read_bytes())
    with np.load(panel / "panel.npz", allow_pickle=False) as data:
        mode = frozen["evidence_mode"]
        x = np.asarray(data[mode + "_X"], dtype=float)
        close, segments = data[mode + "_close"], data[mode + "_segments"]
        start, stop = frozen["signal_indices"]
        signals = range(start, stop + 1)
        spec = frozen["specification"]
        components = []
        for h in spec["horizons"]:
            y = final_targets(x, close, segments, h, stop)
            columns = [
                metadata["factors"].index(v)
                for v in (spec["h10_factors"] if h == 10 else spec["factors"])
            ]
            components.append(
                component(
                    x[:, :, columns],
                    y,
                    metadata["dates"],
                    h,
                    spec["training_months"],
                    spec["alpha"],
                    spec["scaling"],
                    signals,
                    np.isfinite(x).all(axis=2),
                )
            )
        scores = np.sum(
            np.stack([w * c[0] for w, c in zip(spec["fusion"], components, strict=True)]), axis=0
        )
        norms = np.sqrt(np.sum(np.stack([c[1] ** 2 for c in components]), axis=0))
        evaluated = evaluate(
            scores,
            final_targets(x, close, segments, 40, stop),
            signals,
            norms,
            frozen["gate"]["boundaries"],
        )
        metrics = public_metrics(evaluated)
        cv = {}
        fraction = []
        finite = True
        for h, (_, norm, coef) in zip(spec["horizons"], components, strict=True):
            n = norm[list(signals)]
            valid = np.isfinite(n)
            fraction.append(float(valid.mean()))
            cv[str(h)] = (
                float(n[valid].std() / n[valid].mean()) if valid.any() and n[valid].mean() else None
            )
            finite = finite and bool(np.isfinite(coef[list(signals)][valid]).all())
        predictions, ranks = [], []
        for t in range(start + 1, stop + 1):
            active = np.isfinite(scores[t]) & np.isfinite(scores[t - 1])
            if active.sum() >= 12:
                a, b = scores[t - 1, active], scores[t, active]
                predictions.append(float(np.abs(b - a).mean()))
                ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
                ranks.append(float(1 - np.corrcoef(ra, rb)[0, 1]))
        metrics.update(
            {
                "component_norm_cv": cv,
                "minimum_component_fit_fraction": min(fraction),
                "all_fitted_coefficients_finite": finite,
                "prediction_absolute_score_change": float(np.mean(predictions))
                if predictions
                else None,
                "ranking_turnover_one_minus_spearman": float(np.mean(ranks)) if ranks else None,
                "uncertainty": bootstrap(evaluated["ic_series"]),
            }
        )
        result = {
            "contract": frozen["contract"],
            "candidate_sha256": frozen["candidate_sha256"],
            "freeze_sha256": frozen["freeze_sha256"],
            "gate_sha256": frozen["gate_sha256"],
            "panel_sha256": frozen["panel_sha256"],
            "final_oos_opened": True,
            "open_count": 1,
            "model_retuned": False,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "start": frozen["final_oos_start"],
            "end": frozen["final_oos_end"],
            "signal_calendar_count": len(signals),
            "metrics": metrics,
            "decision": classify(metrics, frozen["gate"], frozen["development_rank_ic"]),
            "scope": "INDUSTRY_PREDICTION;NOT_ETF_NAV;OVERLAPPING_H40_LABELS;NO_INDEPENDENT_TIER_A",
            "v1_sealed_performance_read": False,
        }
        immutable_bytes(result_path, json_bytes(result))
        exclusive_json(
            output / "result-integrity.json",
            {"result_sha256": digest(result_path), "freeze_sha256": frozen["freeze_sha256"]},
        )
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("freeze", "open"))
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-sha", default="")
    args = parser.parse_args()
    panel, prior, output = map(external_directory, (args.panel, args.prior, args.output))
    repository = Path(__file__).resolve().parents[2]
    result = (
        freeze(panel, prior, output, repository, args.base_sha)
        if args.operation == "freeze"
        else open_once(panel, output, repository)
    )
    print(
        json.dumps(
            result
            if args.operation == "open"
            else {"freeze_sha256": result["freeze_sha256"], "blocks": result["gate"]["blocks"]},
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
