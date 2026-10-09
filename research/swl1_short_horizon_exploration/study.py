"""Run the locked finite experiment on a physically bounded private view."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from research.swl1_failure_forensics.report import write
from research.swl1_ridge_v1.protocol import exact_targets
from research.swl1_ridge_v2.evaluation import calendar_blocks

from .boundary import load_view
from .design import DESIGN, DESIGN_SHA, LABEL, LOCK_COMMIT, load_design
from .diagnostics import evaluate, market_states, paired, stats
from .signals import Array, equal_reversal, fit_ridge, relative_features, reversal_features


def decision(models: dict[str, Any]) -> str:
    strong, directional = [], []
    for spec in ("S1", "S2"):
        means, checks = [], []
        for h in ("5", "10"):
            m = models[spec][h]
            ic = m["rank_ic"]
            means.append(ic["mean"] is not None and ic["mean"] > 0)
            checks.append(
                bool(
                    means[-1]
                    and ic["median"] > 0
                    and m["raw_top5_minus_bottom5_spread"]["mean"] > 0
                    and m["positive_blocks"] >= 3
                    and all(
                        v["rank_ic"]["mean"] is not None and v["rank_ic"]["mean"] > 0
                        for v in m["leave_one_industry_out"]
                    )
                )
            )
        directional.append(all(means))
        strong.append(all(checks))
    return "A" if all(strong) else "B" if any(directional) else "C"


def correlations(features: Array, targets: dict[int, Array], indices: list[int]) -> dict[str, Any]:
    values = np.concatenate(
        (features[indices], targets[5][indices, :, None], targets[10][indices, :, None]), axis=2
    )
    pooled = np.corrcoef(values.reshape(-1, 4), rowvar=False)
    daily = np.stack([np.corrcoef(row, rowvar=False) for row in values])

    def clean(matrix: Any) -> list[list[float | None]]:
        return [[float(v) if np.isfinite(v) else None for v in row] for row in matrix]

    return {
        "labels": ["relative_REV5", "relative_REV10", "Y5", "Y10"],
        "common_dates": len(indices),
        "pooled_pearson": clean(pooled),
        "mean_daily_cross_sectional_pearson": clean(daily.mean(axis=0)),
        "independent_observations": False,
    }


def run(root: Path, view: Path, private: Path, public: Path) -> dict[str, Any]:
    design = load_design(root)
    returns, dates, codes, reference, receipt = load_view(root, view)
    if private.exists() and any(private.iterdir()):
        raise ValueError("FRESH_PRIVATE_RUN_REQUIRED")
    features0 = reversal_features(returns)
    features = relative_features(features0)
    equal = equal_reversal(features0)
    targets = {h: exact_targets(returns, h) for h in (5, 10)}
    relative_targets = {
        h: value - value.mean(axis=1, keepdims=True) for h, value in targets.items()
    }
    first = dates.index(design["first_signal"])
    models: dict[str, Any] = {s: {} for s in ("S0", "S1", "S2", "S3", "S4", "S5")}
    traces: dict[str, Any] = {s: {} for s in models}
    fits: dict[str, Any] = {}
    states, dimensions = market_states(returns)
    regimes: dict[str, Any] = {}
    accounting: dict[str, Any] = {}
    for horizon in (5, 10):
        h = str(horizon)
        candidates = list(range(first, len(dates) - horizon))
        complete = [
            i
            for i in candidates
            if np.isfinite(features[i]).all() and np.isfinite(targets[horizon][i]).all()
        ]
        accounting[h] = {
            "required_signals": len(candidates),
            "complete_signals": len(complete),
            "incomplete_fixed_universe_signals": len(candidates) - len(complete),
            "last_signal": dates[candidates[-1]],
            "last_target_maturity": dates[candidates[-1] + horizon],
        }
        score_lists: dict[str, tuple[list[int], Array]] = {
            "S0": (complete, np.zeros((len(complete), len(codes)))),
            "S1": (complete, features0[complete, :, 0]),
            "S2": (complete, features0[complete, :, 1]),
            "S3": (complete, equal[complete]),
        }
        ridge_indices, ridge_scores, records, errors = [], [], [], []
        for i in complete:
            try:
                prediction, metadata = fit_ridge(features, targets[horizon], dates, i, horizon)
            except ValueError as error:
                errors.append({"signal_date": dates[i], "reason": str(error)})
                continue
            ridge_indices.append(i)
            ridge_scores.append(prediction)
            records.append(metadata)
        score_lists["S4"] = (ridge_indices, np.asarray(ridge_scores).reshape(-1, len(codes)))
        fits[h] = {"fit_records": records, "dropped": errors}
        if horizon == 10:
            native = [i for i in complete if dates[i] in reference]
            score_lists["S5"] = native, np.asarray([reference[dates[i]] for i in native])
        else:
            models["S5"][h] = {
                "status": "NOT_APPLICABLE_NO_FROZEN_H5_REFERENCE",
                "signal_count": 0,
                "rank_ic": stats([]),
            }
        for spec, (indices, scores) in score_lists.items():
            summary, trace = evaluate(
                scores,
                targets[horizon][indices],
                indices,
                dates,
                codes,
                design["temporal_blocks"]["end"],
            )
            summary.update(
                {
                    "status": "COMPUTED",
                    "requested_signal_count": len(candidates) if spec != "S5" else len(reference),
                    "excluded_signals": len(candidates) - len(indices)
                    if spec != "S5"
                    else len(reference) - len(indices),
                    "exclusion_reasons": dict(Counter(e["reason"] for e in errors))
                    if spec == "S4"
                    else {"INCOMPLETE_FIXED_UNIVERSE": len(candidates) - len(complete)}
                    if spec != "S5"
                    else {},
                }
            )
            models[spec][h], traces[spec][h] = summary, trace
            group_stats = []
            for group in ("UP_LOW", "UP_HIGH", "DOWN_LOW", "DOWN_HIGH"):
                mask = np.asarray([states[i] == group for i in indices])
                group_stats.append(
                    {
                        "state": group,
                        "signals": int(mask.sum()),
                        "rank_ic": stats(trace["rank_ic"][mask]),
                        "raw_spread": stats(trace["spread"][mask]),
                        "co_movement_effective_dimension": stats(
                            dimensions[np.asarray(indices)[mask]]
                        ),
                    }
                )
            regimes.setdefault(spec, {})[h] = group_stats
    comparison: dict[str, Any] = {
        "ridge_minus_simple": {},
        "frozen_v2_reference": {"5": "NOT_APPLICABLE_NO_FROZEN_H5_REFERENCE"},
        "parameter_stability": {},
    }
    for h in ("5", "10"):
        comparison["ridge_minus_simple"][h] = {
            s: paired(traces["S4"][h], traces[s][h]) for s in ("S1", "S2", "S3")
        }
        records = fits[h]["fit_records"]
        weights = np.asarray([r["coefficients"] for r in records]).reshape(-1, 2)
        comparison["parameter_stability"][h] = {
            "relative_rev5_weight": stats(weights[:, 0]),
            "relative_rev10_weight": stats(weights[:, 1]),
            "regularized_condition": stats([r["regularized_condition"] for r in records]),
            "effective_degrees_of_freedom": stats(
                [r["effective_degrees_of_freedom"] for r in records]
            ),
            "training_day_count": stats([r["valid_training_dates"] for r in records]),
            "industry_row_count": stats([r["industry_rows"] for r in records]),
            "alpha": stats([r["alpha"] for r in records]),
            "all_training_dates_before_signal": all(r["training_date_lt_signal"] for r in records),
            "all_training_labels_mature": all(r["all_training_labels_mature"] for r in records),
        }
    comparison["frozen_v2_reference"]["10"] = {
        s: paired(traces[s]["10"], traces["S5"]["10"]) for s in ("S1", "S2", "S3", "S4")
    }
    common = [
        i
        for i in range(first, len(dates) - 10)
        if np.isfinite(features[i]).all()
        and np.isfinite(relative_targets[5][i]).all()
        and np.isfinite(relative_targets[10][i]).all()
    ]
    correlation = correlations(features, relative_targets, common)
    recommendation = decision(models)
    next_actions = {
        "A": "CONSIDER_SIMPLE_REVERSAL_INDEPENDENT_PREREGISTRATION_AFTER_DATA_RIGHTS_AND_PIT_QUALIFICATION",
        "B": "COLLECT_INDEPENDENT_PROSPECTIVE_EVIDENCE_WITHOUT_MODEL_PROMOTION",
        "C": "STOP_EXPANDING_THE_POST_HOC_REVERSAL_FAMILY; DO_NOT_CREATE_V3",
    }
    # Public output is aggregate-only. Per-date arrays and training provenance
    # have a separate private destination outside the repository.
    private.mkdir(parents=True, exist_ok=True)
    write(private / "fit-records.json", fits)
    from research.swl1_failure_forensics.boundary import sha

    comparison["private_fit_trace_sha256"] = sha(private / "fit-records.json")
    arrays: dict[str, Any] = {}
    for spec, horizons in traces.items():
        for h, trace in horizons.items():
            for key in ("indices", "rank_ic", "spread", "scores"):
                arrays[f"{spec}_H{h}_{key}"] = np.asarray(trace[key])
    np.savez_compressed(private / "diagnostics.npz", allow_pickle=False, **arrays)
    comparison["private_diagnostics_sha256"] = sha(private / "diagnostics.npz")
    summary = {
        "label": LABEL,
        "status": "ACTUAL_HISTORICAL_NUMERIC_STUDY_COMPUTED",
        "design_sha256": DESIGN_SHA,
        "model_universe": len(codes),
        "primary_series": design["primary_series"],
        "accounting": accounting,
        "models": models,
        "factor_target_correlations": correlation,
        "formal_validation": False,
    }
    boundary = {
        **receipt,
        "unseen_outcomes_read": False,
        "new_source_downloads": 0,
        "new_source_registry_entries": 0,
        "new_ledger_entries": 0,
        "worker_input_is_physically_truncated": True,
        "source_rights_uncertainty": "OWNER_HISTORICAL_SCOPE_ONLY_NOT_VENDOR_OR_PRODUCTION_ADMISSION",
        "pit": "CURRENT_TAXONOMY_RECONSTRUCTION_NOT_CERTIFIED_HISTORICAL_PIT",
        "original_panel_historical_unseen_access": "NOT_CERTIFIED",
        "accounting": accounting,
    }
    write(
        public / "exploratory-design-manifest.json",
        {
            "label": LABEL,
            "manifest_path": DESIGN,
            "manifest_sha256": DESIGN_SHA,
            "internal_lock_commit": LOCK_COMMIT,
            "independent_preregistration": False,
            "locked_before_new_diagnostics": True,
            "spec_count": 6,
            "manifest": design,
        },
        public=True,
    )
    write(public / "data-boundary.json", boundary, public=True)
    write(
        public / "signal-definitions.json",
        {
            "label": LABEL,
            "specifications": design["specifications"],
            "targets": design["targets"],
            "rank_contract": design["rank_contract"],
            "absolute_relative_rank_equivalence": "SUBTRACTING_COMMON_SAME_DATE_MEAN_PRESERVES_RANKS_EXACTLY",
            "source_definition_parity_max_error": receipt["rev_reconstruction_max_absolute_error"],
        },
        public=True,
    )
    write(public / "research-summary.json", summary, public=True)
    write(
        public / "model-comparison.json",
        {
            "label": LABEL,
            **comparison,
            "factor_target_correlations": correlation,
            "regimes": {
                "label": "POST_HOC_DESCRIPTIVE",
                "definitions": design["regimes"],
                "all_states": regimes,
            },
            "new_model_generation": False,
        },
        public=True,
    )
    write(
        public / "temporal-robustness.json",
        {
            "label": LABEL,
            "block_definition": design["temporal_blocks"],
            "blocks": {
                s: {h: m.get("calendar_blocks", []) for h, m in hs.items()}
                for s, hs in models.items()
            },
            "dependence": {
                s: {h: m.get("dependence", {}) for h, m in hs.items()} for s, hs in models.items()
            },
            "no_iid_p_values": True,
        },
        public=True,
    )
    write(
        public / "industry-sensitivity.json",
        {
            "label": LABEL,
            "diagnostic_without_retraining": True,
            "no_industry_pruning": True,
            "all_30_leave_one_out": {
                s: {h: m.get("leave_one_industry_out", []) for h, m in hs.items()}
                for s, hs in models.items()
            },
            "concentration_and_turnover": {
                s: {
                    h: {
                        "selection": m.get("selection_concentration", {}),
                        "turnover": m.get("turnover", {}),
                    }
                    for h, m in hs.items()
                }
                for s, hs in models.items()
            },
        },
        public=True,
    )
    write(
        public / "research-decision.json",
        {
            "label": LABEL,
            "decision": recommendation,
            "primary_economic_hypothesis": "FIXED_DIRECTION_SHORT_HORIZON_INDUSTRY_REVERSAL",
            "recommended_next_action": next_actions[recommendation],
            "rule": design["decision_rule"],
            "independent_validation_created": False,
            "new_formal_model_created": False,
            "V3_trained": False,
            "swl1_v1_status": "FAILED_VALIDATION",
            "swl1_v2_status": "FAILED_VALIDATION",
            "limitations": design["limitations"],
            "formal_forecasts_created": 0,
            "real_orders_created": 0,
        },
        public=True,
    )
    audit_saved_run(root, private, public)
    return summary


def audit_saved_run(root: Path, private: Path, public: Path) -> None:
    """Aggregate existing traces only: no fit, target evaluation or lifecycle call."""
    load_design(root)
    summary = json.loads((public / "research-summary.json").read_text())
    comparison = json.loads((public / "model-comparison.json").read_text())
    records = json.loads((private / "fit-records.json").read_text())
    with np.load(private / "diagnostics.npz", allow_pickle=False) as saved:
        for spec, horizons in summary["models"].items():
            for h, model in horizons.items():
                if model["status"] == "COMPUTED":
                    scores = saved[f"{spec}_H{h}_scores"]
                    model["score_distribution"] = {
                        "pooled_values": stats(scores.ravel()),
                        "cross_sectional_std": stats(scores.std(axis=1, ddof=0)),
                    }
        protocol = json.loads((root / "config/research/swl1-ridge-v2-protocol.json").read_text())
        candidate = json.loads((root / "config/research/swl1-ridge-v2-candidate.json").read_text())
        validation = json.loads(
            (root / "reports/research/swl1_ridge_v2/validation.json").read_text()
        )
        comparison["frozen_reference_native_phase_parity"] = {}
        for phase, native in (
            ("development", candidate["development"]),
            ("validation", validation["metrics"]),
        ):
            wanted = set(protocol["split"]["indices"][phase])
            positions = [k for k, i in enumerate(saved["S5_H10_indices"]) if i in wanted]
            actual_ic = stats(saved["S5_H10_rank_ic"][positions])
            actual_spread = stats(saved["S5_H10_spread"][positions])
            expected = native["horizons"]["10"]
            if (
                len(positions) != len(wanted)
                or not np.isclose(actual_ic["mean"], expected["mean_rank_ic"], rtol=0, atol=1e-12)
                or not np.isclose(actual_spread["mean"], expected["spread"], rtol=0, atol=1e-12)
            ):
                raise ValueError("FROZEN_H10_REFERENCE_AGGREGATE_PARITY_FAILED")
            comparison["frozen_reference_native_phase_parity"][phase] = {
                "status": "READ_ONLY_RECORDED_REFERENCE_PARITY",
                "signals": len(positions),
                "mean_rank_ic": actual_ic["mean"],
                "raw_spread": actual_spread["mean"],
                "original_public_rank_ic": expected["mean_rank_ic"],
                "new_validation_execution": False,
            }
    for h, value in records.items():
        fits = value["fit_records"]
        assignment = calendar_blocks(
            [fit["signal_date"] for fit in fits], "2023-08-02", "2026-09-21"
        )
        comparison["parameter_stability"][h]["calendar_blocks"] = [
            {
                "block": b + 1,
                "relative_rev5_weight": stats(
                    [
                        fit["coefficients"][0]
                        for fit, block in zip(fits, assignment, strict=True)
                        if block == b
                    ]
                ),
                "relative_rev10_weight": stats(
                    [
                        fit["coefficients"][1]
                        for fit, block in zip(fits, assignment, strict=True)
                        if block == b
                    ]
                ),
            }
            for b in range(4)
        ]
        comparison["parameter_stability"][h]["training_ranges_private"] = True
        comparison["parameter_stability"][h]["trace_accounting"] = {
            "fits": len(fits),
            "dropped": len(value["dropped"]),
            "every_fit_has_training_indices_and_maturity_dates": all(
                "training_indices" in fit and "last_training_maturity" in fit for fit in fits
            ),
        }
    write(public / "research-summary.json", summary, public=True)
    write(public / "model-comparison.json", comparison, public=True)
