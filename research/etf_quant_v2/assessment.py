"""Concise aggregate evidence from real Development artifacts; no OOS labels."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

from strategies.etf_quant.config import FACTORS_19, H10_FACTORS

from .coverage import digest, immutable_bytes, json_bytes
from .experiment import ExperimentSplit, component, targets
from .protocol import Candidate, canonical_hash
from .recovery import write_json


def paired_comparisons(rows: list[dict[str, Any]]) -> dict[str, Any]:
    comparisons: dict[str, Any] = {}
    for mode in ("HIGH_CONFIDENCE", "EXTENDED_HISTORY"):
        indexed = {r["id"]: r for r in rows if r["mode"] == mode}
        scaled = []
        windows: dict[str, list[float]] = {"6": [], "12": [], "24": []}
        for r in indexed.values():
            c, m = r["candidate"], r["metrics"]
            if m["signals"] >= 160:
                windows[str(c["training_months"])].append(m["mean_rank_ic"])
            if c["scaling"] == "RAW":
                identifier = r["id"].replace("-RAW-", "-TRAIN_ONLY_STANDARDIZED-")
                other = indexed.get(identifier)
                if other and min(m["signals"], other["metrics"]["signals"]) >= 160:
                    scaled.append(other["metrics"]["mean_rank_ic"] - m["mean_rank_ic"])
        comparisons[mode] = {
            "standardization_pairs": len(scaled),
            "median_standardized_minus_raw_ic": float(np.median(scaled)) if scaled else None,
            "window_median_ic": {
                k: {"eligible_specs": len(v), "median": float(np.median(v)) if v else None}
                for k, v in windows.items()
            },
            "warning": "24m has shorter feasible evaluation. Within-mode comparisons require 160 signals; these marginal summaries are not causal window effects.",
        }
    return comparisons


def supplements(
    metadata: dict[str, Any], panel: Any, policy: dict[str, Any], selected: dict[str, Any]
) -> dict[str, Any]:
    split = ExperimentSplit(**policy["split"])
    spec = Candidate(
        **(
            selected["candidate"]
            | {
                "horizons": tuple(selected["candidate"]["horizons"]),
                "fusion": tuple(selected["candidate"]["fusion"]),
            }
        )
    )
    signals = range(policy["mode_development_start"]["HIGH_CONFIDENCE"], split.development_end + 1)
    all_modes: dict[str, Any] = {}
    coefficients: dict[str, Any] = {}
    for mode in ("HIGH_CONFIDENCE", "EXTENDED_HISTORY"):
        x = panel[mode + "_X"]
        label = {
            h: targets(
                x, panel[mode + "_close"], panel[mode + "_segments"], h, split, "DEVELOPMENT"
            )
            for h in (10, 40, 80, 120)
        }
        predictions, signs, coef = {}, {}, {}
        for h in (10, 40, 80, 120):
            names = H10_FACTORS if h == 10 else FACTORS_19
            columns = [metadata["factors"].index(n) for n in names]
            scores, _, values = component(
                x[:, :, columns],
                label[h],
                metadata["dates"],
                h,
                spec.training_months,
                spec.alpha,
                spec.scaling,
                signals,
                np.isfinite(x).all(axis=2),
            )
            predictions[h] = scores
            valid = values[np.isfinite(values).all(axis=1)]
            coef[str(h)] = valid
            signs[str(h)] = {
                "training_fits": len(valid),
                "positive_sign_fraction": (valid > 0).mean(axis=0).tolist() if len(valid) else None,
                "temporal_coefficient_std": valid.std(axis=0).tolist() if len(valid) else None,
                "features": list(names),
            }
        correlations = {}
        for a, b in combinations((10, 40, 80, 120), 2):
            correlation_summary: dict[str, Any] = {}
            for kind, series in (("target", label), ("prediction", predictions)):
                measured = []
                for t in signals:
                    active = np.isfinite(series[a][t]) & np.isfinite(series[b][t])
                    if (
                        active.sum() >= 12
                        and min(np.std(series[a][t, active]), np.std(series[b][t, active])) > 1e-12
                    ):
                        measured.append(
                            float(np.corrcoef(series[a][t, active], series[b][t, active])[0, 1])
                        )
                correlation_summary[kind] = {
                    "sessions": len(measured),
                    "mean_cross_section_correlation": float(np.mean(measured))
                    if measured
                    else None,
                }
            correlations[f"{a}/{b}"] = correlation_summary
        all_modes[mode] = {"correlations": correlations, "coefficients": signs}
        coefficients[mode] = coef
    differences = {}
    for horizon_key in ("10", "40", "80", "120"):
        a, b = (
            coefficients["HIGH_CONFIDENCE"][horizon_key],
            coefficients["EXTENDED_HISTORY"][horizon_key],
        )
        differences[horizon_key] = {
            "same_shape": a.shape == b.shape,
            "maximum_absolute_difference": float(np.max(np.abs(a - b)))
            if a.shape == b.shape and a.size
            else None,
            "sign_agreement": float(np.mean(np.sign(a) == np.sign(b)))
            if a.shape == b.shape and a.size
            else None,
        }
    return {
        "development_common_dates_start": metadata["dates"][signals.start],
        "per_mode": all_modes,
        "tier_coefficient_sensitivity": differences,
        "tier_sensitivity_limitation": "Common recent fit windows contain the same Tier B facts. Agreement here is not an independent test of pre-2021 Tier C historical assignment accuracy.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    output = root / "publish"
    output.mkdir(exist_ok=True)
    experiment = root / "experiment"
    metadata = json.loads((root / "panel/panel.json").read_text())
    recovery = json.loads((root / "dataset/recovery.json").read_text())
    original = json.loads((experiment / "development-candidate.json").read_text())
    revision = json.loads((experiment / "revision/candidate.json").read_text())
    validation = json.loads((experiment / "validation.json").read_text())
    policy = json.loads((experiment / "revision/protocol.json").read_text())
    diagnostic = json.loads((experiment / "diagnostics.json").read_text())
    supplemental = supplements(
        metadata, np.load(root / "panel/panel.npz"), policy, revision["selected"]
    )
    selected = revision["selected"]
    candidate = {
        "product": "ETF_QUANT_V2",
        "research_status": "VALIDATION_INFORMED_NOT_INDEPENDENTLY_VALIDATED",
        "frozen_at": datetime.fromtimestamp(
            (experiment / "revision/candidate.json").stat().st_mtime, timezone.utc
        ).isoformat(),
        "model_family": "NUMPY_RIDGE",
        "evidence_mode": selected["mode"],
        "specification": selected["candidate"]
        | {
            "identifier": selected["id"],
            "factors": list(FACTORS_19),
            "h10_factors": list(
                Candidate(
                    **(
                        selected["candidate"]
                        | {
                            "horizons": tuple(selected["candidate"]["horizons"]),
                            "fusion": tuple(selected["candidate"]["fusion"]),
                        }
                    )
                ).factors(10)
            ),
        },
        "data_sha256": metadata["data_sha256"],
        "protocol_sha256": policy["protocol_sha256"],
        "research_candidate_sha256": canonical_hash(revision),
        "original_candidate_sha256": canonical_hash(original),
        "research_source_files": revision["source_files"],
        "validation_accepted": False,
        "validation_summary_sha256": digest(experiment / "validation.json"),
        "validation_open_count": 1,
        "final_oos_start": policy["phase_dates"]["final_oos_start"],
        "final_oos_end": policy["phase_dates"]["final_oos_end"],
        "final_oos_opened": False,
        "shadow_started": False,
        "shadow_ready": True,
        "broker_enabled": False,
        "real_order_path": False,
        "mapping_policy": "FROZEN_V1_INDUSTRY_FIRST_VERIFIED_PROXY_CASH",
        "missingness_policy": "NO_GAP_BRIDGING;COMPLETE_MATURE_CROSS_SECTIONS",
        "future_launch_requirement": "EXPLICIT_HUMAN_AUTHORIZATION_AND_SEPARATE_UNVALIDATED_RESEARCH_ACKNOWLEDGEMENT",
    }
    candidate["candidate_sha256"] = canonical_hash(candidate)
    immutable_bytes(output / "candidate.json", json_bytes(candidate))
    compact = {
        mode: {
            "horizon_ess": {
                str(h): {k: v for k, v in diagnostic[mode][str(h)].items() if k != "per_industry"}
                for h in (10, 40, 80, 120)
            },
            "ridge_vs_ols": {
                k: v for k, v in diagnostic[mode]["ridge_vs_ols"].items() if k != "geometry"
            },
            "feature_geometry": diagnostic[mode]["feature_geometry"],
        }
        for mode in ("HIGH_CONFIDENCE", "EXTENDED_HISTORY")
    }
    stage1 = json.loads((experiment / "grid-development.json").read_text())
    report = {
        "contract": "ETF_QUANT_V2_ACTUAL_RESEARCH_AGGREGATES",
        "product": "ETF_QUANT_V2",
        "research_status": candidate["research_status"],
        "candidate_sha256": candidate["candidate_sha256"],
        "historical": {
            k: v
            for k, v in metadata.items()
            if k not in ("dates", "source_files", "recovery", "industries")
        },
        "industries": metadata["industries"],
        "recovery": {
            k: v
            for k, v in recovery.items()
            if k not in ("files", "failures", "paths", "source_files", "unresolved")
        },
        "phase_dates": policy["phase_dates"],
        "strict_vs_reconstructed_overlap": {
            "independent_tier_a_snapshots": 0,
            "measured_assignment_error": None,
            "reason": "NO_INDEPENDENT_HISTORICAL_TIER_A_SNAPSHOT_AVAILABLE",
        },
        "diagnostics": compact,
        "supplemental": supplemental,
        "stage1": {
            "specifications": 120,
            "controlled_horizon_comparison": [
                r
                for r in stage1
                if r["mode"] == "HIGH_CONFIDENCE"
                and r["candidate"]["alpha"] == 10
                and r["candidate"]["training_months"] == 12
                and r["candidate"]["scaling"] == "RAW"
            ],
            "per_mode_gates": {
                m: sum(r["passes"] for r in stage1 if r["mode"] == m)
                for m in ("HIGH_CONFIDENCE", "EXTENDED_HISTORY")
            },
            "paired_comparisons": paired_comparisons(stage1),
        },
        "stage2": {"specifications": 36, "cycles": 1, "original_selected": original["selected"]},
        "revision": {
            "cycles": 1,
            "selected": selected,
            "independent_validation": None,
            "generation_rule": policy["generation_rule"],
        },
        "validation": validation,
        "final_oos_opened": False,
        "shadow_started": False,
        "execution": {
            "historical_mapping_cash_fallback_rate": 1.0,
            "actual_etf_turnover": 0.0,
            "actual_etf_cost": 0.0,
            "reason": "Verified registry first availability is 2026-09-28, after research signal periods; no evidence backstamp. Predictive industry turnover and 8bps cost proxy are counterfactual and are not ETF NAV.",
        },
        "limitations": [
            "No independent Tier A overlap accuracy estimate",
            "Retrospective pre-2021 taxonomy and unresolved retired-symbol price coverage",
            "Short observable High Confidence Development comparison and small H120 ESS",
            "One Validation failed; revision has no independent Validation and Final OOS stays sealed",
            "Historical mapping unavailable; no measured tradable ETF profitability",
        ],
        "artifact_hashes": {
            name: digest(experiment / name)
            for name in (
                "protocol.json",
                "grid-development.json",
                "stage2/protocol.json",
                "stage2/grid-development.json",
                "development-candidate.json",
                "validation-access.json",
                "validation.json",
                "revision/protocol.json",
                "revision/grid-development.json",
                "revision/candidate.json",
            )
        },
    }
    write_json(output / "research.json", report)
    for name, artifact in (
        ("stage1-protocol.json", "protocol.json"),
        ("stage2-protocol.json", "stage2/protocol.json"),
        ("revision-protocol.json", "revision/protocol.json"),
    ):
        immutable_bytes(output / name, (experiment / artifact).read_bytes())
    print(
        json.dumps(
            {
                "candidate": candidate["specification"]["identifier"],
                "candidate_sha256": candidate["candidate_sha256"],
                "research_bytes": (output / "research.json").stat().st_size,
            }
        )
    )


if __name__ == "__main__":
    main()
