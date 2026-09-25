"""Formal Development run for the frozen Horizon-Specific Alpha Hypothesis V1.

Horizon-local execution only: each candidate trains and evaluates exactly
one horizon; no fused score, no cross-horizon ranking, no weighted metric.
C0_H10 / C0_H40 / C0_H120 are same-horizon 19-factor controls checked
against the existing formal D2/C0 artifacts. Every non-factor setting is
the frozen D2 contract (raw X, excess training target, NumPyRidge 0.01,
6-calendar-month window, min 30 valid training days). This is POST-AUDIT
DEVELOPMENT HYPOTHESIS REFINEMENT: never independent validation, never OOS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research import development_iteration1_protocol as iteration1_protocol
from research import horizon_specific_alpha_hypothesis_v1_protocol as protocol
from research import sector_development_baseline as baseline
from research.sector_development_protocol import (
    audit_local_policy, guard_evaluation_dates, verify_frozen_prefix,
)
from research.sector_index_baseline import FEATURE_WARMUP
from strategies.sw_sector_rotation.src.factors.sector_rotation import compute_all_price_features
from strategies.sw_sector_rotation.src.model.model import (
    DEFAULT_ALPHA, FORWARD_WINDOWS, MIN_TRAIN_DATES, NumPyRidge,
)
from strategies.sw_sector_rotation.src.common.temporal_integrity import make_forward_label
from strategies.sw_sector_rotation.src.model.ranking import rank_sectors, select_top
from strategies.sw_sector_rotation.src.strategy import SWSectorRotationConfig, SWSectorRotationCore

RESEARCH_TYPE = "HORIZON_SPECIFIC_ALPHA_HYPOTHESIS_V1"
PREREGISTRATION_COMMIT = "4d0ee982a0cd4ff1efe76c9fee4c2de807643ac2"
EXPECTED_BRANCH = "experiment/sw-sector-index-research-baseline"
ITERATION1_RUN_ID = "iteration1_20260924_163607_787266_utc"
D2_PREDICTIONS_SHA256 = "b2191cdcf907d3217a14b494eac36325f473f285392784e118e17cadd13dbb17"
D2_AGGREGATE_SHA256 = "cc7f9b5712c0f072ea74d1d9634bb990e3f29e2819e6e6cddff27933b17c86b4"
D2_TRAINING_SHA256 = "ac74a26c73b9bdca0668615f0147a047536a10c24b59aaa86e9df1b8eb906415"
FACTOR_IDENTITY_TOLERANCE = 1e-9
TARGET_IDENTITY_TOLERANCE = 1e-12
C0_REPRODUCTION_TOLERANCE = 1e-12
IDENTITY_SAMPLE_ORDINALS = (1, 50, 100)
TRAINING_WINDOW_ORDINALS = (1, 25, 50, 75, 100)
IDENTITY_SAMPLE_SECTOR_COUNT = 10
TOP5_IDENTITY_ORDINALS = (1, 50, 100)
ALLOWED_UNTRACKED = ("research/horizon_specific_alpha_v1_run.py",
                     "tests/test_horizon_specific_alpha_v1_run.py")
FROZEN_PATHS = (
    "docs/research/shenwan_horizon_specific_alpha_hypothesis_v1.md",
    "docs/research/shenwan_horizon_specific_alpha_hypothesis_v1_selection_trace.md",
    "research/configs/horizon_specific_alpha_hypothesis_v1.json",
    "research/horizon_specific_alpha_hypothesis_v1_protocol.py",
    "research/horizon_specific_alpha_hypothesis_v1_selection.py",
    "tests/test_horizon_specific_alpha_hypothesis_v1.py",
)
METRIC_NAMES = ("IC", "RankIC", "Top5_return", "Universe_return", "Spread")
STATUS_ADVANCED = "HORIZON_ADVANCED_FOR_FURTHER_REVIEW"
STATUS_NOT_ADVANCED = "HORIZON_NOT_ADVANCED"
STATUS_CONTROL = "CONTROL_SAME_HORIZON_REFERENCE"
FROZEN_TEMPORAL_FAIL = "TEMPORAL_STABILITY_GATE_FAIL"
FORBIDDEN_RESULT_LABELS = ("VALIDATED", "PRODUCTION", "TRADABLE", "LIVE_READY",
                           "OOS_PASS", "WINNER", "BEST_MODEL")
SCHEME_ARTIFACT_NAMES = (
    "predictions.csv", "per_date_metrics.csv", "aggregate_metrics.json",
    "training_diagnostics.csv", "data_quality_diagnostics.json",
    "transformation_diagnostics.json",
)
RUN_ARTIFACT_NAMES = ("candidate_summary.json", "block_stability.csv", "integrity.json")
PREDICTION_COLUMNS = (
    "candidate", "horizon", "ordinal", "signal_date", "sector_code", "sector_name",
    "prediction_score", "cross_sectional_rank", "top5",
    "realized_forward_return", "label_end", "exclusion_reason",
    "training_observations", "training_valid_days", "training_label_cutoff",
)
PER_DATE_COLUMNS = (
    "candidate", "horizon", "ordinal", "signal_date", "metric", "value",
    "null_reason", "valid_sector_count",
)
TRAINING_COLUMNS = (
    "candidate", "horizon", "ordinal", "signal_date", "status", "reason",
    "train_start", "label_cutoff", "first_train_origin", "last_train_origin",
    "last_train_label_end", "training_candidate_days", "training_valid_days",
    "training_observations", "valid_sector_count", "leakage_checks",
)


@dataclass(frozen=True)
class SchemeOutput:
    predictions: pd.DataFrame
    per_date_metrics: pd.DataFrame
    aggregate_metrics: dict
    block_metrics: dict
    training_diagnostics: pd.DataFrame
    data_quality_diagnostics: dict
    transformation_diagnostics: dict


def scheme_specs() -> list[dict]:
    """Frozen schemes: three same-horizon controls, then config candidates."""
    config = protocol.load_config()
    control_factors = list(config["control"]["factorList"])
    specs = [{"schemeId": f"C0_H{h}", "isControl": True, "horizon": h,
              "archetype": "CONTROL", "factorList": control_factors}
             for h in protocol.HORIZONS]
    for candidate_id in protocol.CANDIDATE_IDS:
        item = config["candidates"][candidate_id]
        factors = list(item["factorList"])
        if factors != list(protocol.EXACT_CANDIDATES[candidate_id]):
            raise ValueError("CANDIDATE_IDENTITY_BLOCKER")
        specs.append({"schemeId": candidate_id, "isControl": False,
                      "horizon": int(item["horizon"]),
                      "archetype": item["archetype"], "factorList": factors})
    horizon_of = {"H10": 10, "H40": 40, "H120": 120}
    for spec in specs:
        if not spec["isControl"]:
            prefix = spec["schemeId"].split("_")[0]
            if horizon_of[prefix] != spec["horizon"]:
                raise ValueError("CANDIDATE_IDENTITY_BLOCKER: horizon assignment")
        positions = [protocol.FROZEN_FACTOR_ORDER.index(f) for f in spec["factorList"]]
        if positions != sorted(positions) or len(set(spec["factorList"])) != len(spec["factorList"]):
            raise ValueError("CANDIDATE_IDENTITY_BLOCKER: factor order")
        if any(f not in protocol.FROZEN_FACTOR_ORDER for f in spec["factorList"]):
            raise ValueError("CANDIDATE_IDENTITY_BLOCKER: factor name")
    ids = [spec["schemeId"] for spec in specs]
    if ids != ["C0_H10", "C0_H40", "C0_H120", *protocol.CANDIDATE_IDS]:
        raise ValueError("CANDIDATE_IDENTITY_BLOCKER: scheme set")
    return specs


def period_for_horizon(horizon: int) -> str:
    for name, value in FORWARD_WINDOWS.items():
        if value == horizon:
            return name
    raise ValueError("HORIZON_NOT_IN_FROZEN_WINDOWS")


def horizon_local_metrics(scores: dict, labels: dict, top_codes: list[str]) -> dict:
    """One horizon's five metrics with horizon-local Top5 semantics (no fusion)."""
    codes = list(scores)
    complete = [c for c in codes
                if scores.get(c) is not None and labels.get(c) is not None
                and np.isfinite(scores[c]) and np.isfinite(labels[c])]
    valid = len(complete)
    base = {"valid_sector_count": valid, "null_reason": None}
    if valid != 124 or len(top_codes) != 5:
        reason = "incomplete_fixed_universe_score_or_label" if valid != 124 else "top5_unavailable"
        return {**base, "null_reason": reason,
                **{name: None for name in METRIC_NAMES}}
    x = np.asarray([scores[c] for c in complete], dtype=float)
    y = np.asarray([labels[c] for c in complete], dtype=float)
    ic = baseline._nonconstant_correlation(x, y)
    rx = pd.Series(x).rank(method="average").to_numpy(dtype=float)
    ry = pd.Series(y).rank(method="average").to_numpy(dtype=float)
    rankic = baseline._nonconstant_correlation(rx, ry)
    top_return = float(np.mean([labels[c] for c in top_codes]))
    universe_return = float(np.mean(y))
    values = {"IC": ic, "RankIC": rankic, "Top5_return": top_return,
              "Universe_return": universe_return,
              "Spread": top_return - universe_return}
    if any(value is None for value in values.values()):
        return {**base, "null_reason": "zero_cross_sectional_variance",
                **{name: values[name] for name in METRIC_NAMES}}
    return {**base, "null_reason": None, **values}


def aggregate_scheme_metrics(per_date: pd.DataFrame) -> dict:
    """Population descriptive statistics per metric over valid dates."""
    result: dict = {}
    for name in METRIC_NAMES:
        rows = per_date.loc[per_date["metric"].eq(name)]
        values = pd.to_numeric(rows["value"], errors="coerce").dropna().to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError("HORIZON_SPECIFIC_METRIC_INTEGRITY_BLOCKER: non-finite metric")
        result[name] = {
            "validDates": int(len(values)), "nullDates": int(100 - len(values)),
            "mean": float(np.mean(values)) if len(values) else None,
            "median": float(np.median(values)) if len(values) else None,
            "std": float(np.std(values, ddof=0)) if len(values) else None,
            "min": float(np.min(values)) if len(values) else None,
            "max": float(np.max(values)) if len(values) else None,
        }
    return result


def block_metrics_for(per_date: pd.DataFrame) -> dict:
    """Frozen B1-B4 slices: mean/median RankIC, mean Spread, valid dates."""
    out = {}
    for block_id, first, last in protocol_blocks():
        rows = per_date.loc[per_date["ordinal"].between(first, last)]
        rankic = pd.to_numeric(rows.loc[rows["metric"].eq("RankIC"), "value"],
                               errors="coerce").dropna().to_numpy(dtype=float)
        spread = pd.to_numeric(rows.loc[rows["metric"].eq("Spread"), "value"],
                               errors="coerce").dropna().to_numpy(dtype=float)
        out[block_id] = {
            "first": first, "last": last,
            "validDates": int(len(rankic)),
            "rankicMean": float(np.mean(rankic)) if len(rankic) else None,
            "rankicMedian": float(np.median(rankic)) if len(rankic) else None,
            "spreadMean": float(np.mean(spread)) if len(spread) else None,
        }
    return out


def protocol_blocks() -> tuple:
    return tuple((item["id"], item["first"], item["last"])
                 for item in protocol.load_config()["blocks"])


def warnings_for(scheme_id: str, horizon: int) -> list[str]:
    """Frozen disclosure set; warnings are never swallowed or repaired."""
    warnings = []
    if horizon == 40:
        warnings.append("NO_STRONG_STABILITY_EVIDENCE")
    if scheme_id.endswith("_S"):
        warnings.append("NEUTRALITY_CAVEAT_ZERO_HARD_FLIP_MAY_BE_NEUTRAL_TRAINING_DIRECTION")
    warnings.append("DEVELOPMENT_REUSE_WARNING")
    return warnings


def apply_simplicity_preference(rows: list[dict]) -> dict:
    """Label PREFERRED_BY_SIMPLICITY only under the frozen near-tie rule."""
    labels = {row["schemeId"]: row["simplicityPreference"] for row in rows}
    for horizon in protocol.HORIZONS:
        single = next((r for r in rows if r["schemeId"] == f"H{horizon}_S"), None)
        compact = next((r for r in rows if r["schemeId"] == f"H{horizon}_C"), None)
        if single is None or compact is None:
            continue
        labels[single["schemeId"]] = "NOT_TRIGGERED"
        labels[compact["schemeId"]] = "NOT_TRIGGERED"
        prefer = protocol.prefer_single_if_near_tie(
            single_status=single["advancementStatus"],
            compact_status=compact["advancementStatus"],
            single_mean_rankic=single["meanRankIc"],
            compact_mean_rankic=compact["meanRankIc"],
            single_mean_spread=single["meanSpread"],
            compact_mean_spread=compact["meanSpread"])
        if prefer:
            labels[single["schemeId"]] = "PREFERRED_BY_SIMPLICITY"
    return labels


def evaluate_gates(mean_rankic: float, mean_spread: float,
                   c0_rankic: float, c0_spread: float,
                   block_rankic: dict, horizon: int) -> dict:
    """Frozen advancement gates, applied verbatim via the preregistered module."""
    frozen_result = protocol.advancement_status(
        candidate_horizon=horizon, control_horizon=horizon,
        mean_rankic=mean_rankic, mean_spread=mean_spread,
        c0_mean_rankic=c0_rankic, c0_mean_spread=c0_spread,
        block_mean_rankic=block_rankic)
    level1 = bool(mean_rankic > 0 and mean_spread > 0)
    level2 = bool((mean_rankic > c0_rankic and mean_spread >= c0_spread)
                  or (mean_spread > c0_spread and mean_rankic >= c0_rankic))
    temporal = bool(sum(x > 0 for x in block_rankic.values()) >= 3
                    and sum(x < -0.02 for x in block_rankic.values()) <= 1)
    if frozen_result == STATUS_ADVANCED:
        status = STATUS_ADVANCED
    else:
        status = STATUS_NOT_ADVANCED
    if bool(level1 and level2 and temporal) != (frozen_result == STATUS_ADVANCED):
        raise ValueError("ADVANCEMENT_LOGIC_INTEGRITY_BLOCKER: frozen gate divergence")
    return {
        "frozenGateResult": frozen_result,
        "advancementStatus": status,
        "level1": "LEVEL1_PASS" if level1 else "LEVEL1_FAIL",
        "level2": "LEVEL2_PASS" if level2 else "LEVEL2_FAIL",
        "temporalStability": ("TEMPORAL_STABILITY_PASS" if temporal
                              else "TEMPORAL_STABILITY_FAIL"),
    }


def factor_identity_gate(stashed: dict, frames: dict, calendar: pd.DatetimeIndex,
                         development_dates: pd.DatetimeIndex, codes: list[str]) -> dict:
    """Sampled Ridge-input factor values vs independent recomputation."""
    factors = tuple(protocol.FROZEN_FACTOR_ORDER)
    max_diff, comparisons = 0.0, 0
    for ordinal in IDENTITY_SAMPLE_ORDINALS:
        signal = development_dates[ordinal - 1]
        for code in codes[:IDENTITY_SAMPLE_SECTOR_COUNT]:
            independent = compute_all_price_features(
                baseline._source_frame(frames[code], frames[code].index[0], signal),
                include_rsrs=False,
            ).loc[signal, list(factors)].to_numpy(dtype=float)
            recorded = np.array([stashed[(ordinal, code)][f] for f in factors], dtype=float)
            if not np.isfinite(independent).all():
                raise ValueError("FACTOR_IDENTITY_BLOCKER: independent recomputation invalid")
            diff = float(np.max(np.abs(independent - recorded)))
            max_diff = max(max_diff, diff)
            comparisons += len(factors)
            if diff > FACTOR_IDENTITY_TOLERANCE:
                raise ValueError("FACTOR_IDENTITY_BLOCKER")
    return {"status": "PASS", "sampledOrdinals": list(IDENTITY_SAMPLE_ORDINALS),
            "sampledFactors": list(factors),
            "sampledSectorCount": IDENTITY_SAMPLE_SECTOR_COUNT,
            "sampleCount": comparisons, "maxAbsDiff": max_diff,
            "toleranceAbs": FACTOR_IDENTITY_TOLERANCE,
            "onMismatch": "FACTOR_IDENTITY_BLOCKER"}


def target_identity_gate(labels_by_h: dict, frames: dict, calendar: pd.DatetimeIndex,
                         development_dates: pd.DatetimeIndex, codes: list[str],
                         d2_predictions: pd.DataFrame) -> dict:
    """Sampled labels vs direct calendar arithmetic and the frozen D2 artifact."""
    lookup = {(int(row.ordinal), int(row.horizon), str(row.sector_code)): row
              for row in d2_predictions.itertuples(index=False)}
    max_direct, max_artifact, comparisons = 0.0, 0.0, 0
    for ordinal in IDENTITY_SAMPLE_ORDINALS:
        signal = development_dates[ordinal - 1]
        signal_i = int(calendar.get_loc(signal))
        for horizon in protocol.HORIZONS:
            endpoint = calendar[signal_i + horizon]
            for code in codes[:IDENTITY_SAMPLE_SECTOR_COUNT]:
                recorded = float(labels_by_h[horizon][code].loc[signal])
                close = frames[code]["close"]
                direct = float(close.loc[endpoint]) / float(close.loc[signal]) - 1.0
                row = lookup[(ordinal, horizon, code)]
                artifact = float(row.realized_forward_return)
                if str(row.label_end) != str(endpoint.date()):
                    raise ValueError("TARGET_IDENTITY_BLOCKER: endpoint semantics drift")
                max_direct = max(max_direct, abs(recorded - direct))
                max_artifact = max(max_artifact, abs(recorded - artifact))
                comparisons += 1
                if (abs(recorded - direct) > TARGET_IDENTITY_TOLERANCE
                        or abs(recorded - artifact) > TARGET_IDENTITY_TOLERANCE):
                    raise ValueError("TARGET_IDENTITY_BLOCKER")
    return {"status": "PASS", "sampledOrdinals": list(IDENTITY_SAMPLE_ORDINALS),
            "sampledHorizons": list(protocol.HORIZONS),
            "sampledSectorCount": IDENTITY_SAMPLE_SECTOR_COUNT,
            "sampleCount": comparisons,
            "maxAbsDiffDirectArithmetic": max_direct,
            "maxAbsDiffD2ControlArtifact": max_artifact,
            "toleranceAbs": TARGET_IDENTITY_TOLERANCE,
            "endpointSemantics": "common_trading_calendar_t_plus_h_confirmed",
            "trainingTargetSemantics": "same_date_cross_sectional_demean_only",
            "onMismatch": "TARGET_IDENTITY_BLOCKER"}


def training_window_identity_gate(training: pd.DataFrame,
                                  d2_training: pd.DataFrame) -> dict:
    """Frozen window identity versus the existing formal D2 diagnostics.

    Horizon-local scheme frames carry only their own horizon; every horizon
    present in the frame is checked against the all-horizon D2 reference.
    """
    fields = ("train_start", "label_cutoff", "first_train_origin",
              "last_train_origin", "last_train_label_end",
              "training_candidate_days", "training_valid_days",
              "training_observations", "valid_sector_count")
    lookup = {(int(row.ordinal), int(row.horizon)): row
              for row in d2_training.itertuples(index=False)}
    present = sorted({int(h) for h in training["horizon"]})
    if not present or any(h not in protocol.HORIZONS for h in present):
        raise ValueError("TRAINING_WINDOW_IDENTITY_BLOCKER: horizon set")
    comparisons = 0
    for ordinal in TRAINING_WINDOW_ORDINALS:
        for horizon in present:
            rows = training[(training["ordinal"] == ordinal)
                            & (training["horizon"] == horizon)]
            if len(rows) != 1:
                raise ValueError("TRAINING_WINDOW_IDENTITY_BLOCKER: row identity")
            row = rows.iloc[0]
            reference = lookup[(ordinal, horizon)]
            for field in fields:
                if str(row[field]) != str(getattr(reference, field)):
                    raise ValueError("TRAINING_WINDOW_IDENTITY_BLOCKER")
                comparisons += 1
    return {"status": "PASS", "sampledOrdinals": list(TRAINING_WINDOW_ORDINALS),
            "sampledHorizons": present, "sampleCount": comparisons,
            "comparedFields": list(fields), "onMismatch": "TRAINING_WINDOW_IDENTITY_BLOCKER"}


def top5_identity_check(outputs: dict) -> dict:
    """Recompute ranking/Top5/tie-break from artifacts; exact match required."""
    comparisons = 0
    for scheme, output in outputs.items():
        pred = output.predictions
        for ordinal in TOP5_IDENTITY_ORDINALS:
            day = pred[pred["ordinal"] == ordinal]
            ranked = day.sort_values(
                ["prediction_score", "sector_code"], ascending=[False, True])
            expected_order = ranked["sector_code"].tolist()
            actual_order = day.sort_values(
                ["cross_sectional_rank", "sector_code"])["sector_code"].tolist()
            if actual_order != expected_order:
                raise ValueError("TOP5_IDENTITY_BLOCKER")
            top5_expected = expected_order[:5]
            top5_actual = day.loc[day["top5"] == True].sort_values(  # noqa: E712
                "cross_sectional_rank")["sector_code"].tolist()
            if top5_actual != top5_expected:
                raise ValueError("TOP5_IDENTITY_BLOCKER")
            comparisons += 2
    return {"status": "PASS", "sampledOrdinals": list(TOP5_IDENTITY_ORDINALS),
            "sampledSchemes": sorted(outputs), "sampleCount": comparisons,
            "tieBreak": "sector_code_ascending", "onMismatch": "TOP5_IDENTITY_BLOCKER"}


def recompute_from_predictions(predictions: dict) -> dict:
    """Independent per-scheme metric recompute straight from prediction rows."""
    out = {}
    for scheme, pred in predictions.items():
        horizon = int(pred["horizon"].iloc[0])
        daily = {"IC": [], "RankIC": [], "Top5_return": [], "Universe_return": [],
                 "Spread": []}
        per_block = {block_id: {"RankIC": [], "Spread": []}
                     for block_id, _, _ in protocol_blocks()}
        for ordinal in range(1, 101):
            day = pred[pred["ordinal"] == ordinal]
            valid = day[day["prediction_score"].notna()
                        & day["realized_forward_return"].notna()]
            x = valid["prediction_score"].to_numpy(dtype=float)
            y = valid["realized_forward_return"].to_numpy(dtype=float)
            if len(x) >= 2 and np.std(x) > 0 and np.std(y) > 0:
                ic = float(np.corrcoef(x, y)[0, 1])
                rx = pd.Series(x).rank(method="average").to_numpy(dtype=float)
                ry = pd.Series(y).rank(method="average").to_numpy(dtype=float)
                rankic = float(np.corrcoef(rx, ry)[0, 1])
            else:
                ic, rankic = None, None
            top = valid[valid["top5"] == True]  # noqa: E712
            top_return = float(top["realized_forward_return"].mean()) if len(top) == 5 else None
            universe_return = float(valid["realized_forward_return"].mean())
            spread = (top_return - universe_return) if top_return is not None else None
            daily["IC"].append(ic)
            daily["RankIC"].append(rankic)
            daily["Top5_return"].append(top_return)
            daily["Universe_return"].append(universe_return)
            daily["Spread"].append(spread)
            for block_id, first, last in protocol_blocks():
                if first <= ordinal <= last:
                    per_block[block_id]["RankIC"].append(rankic)
                    per_block[block_id]["Spread"].append(spread)
        aggregates = {}
        for name, values in daily.items():
            arr = np.asarray([v for v in values if v is not None], dtype=float)
            aggregates[name] = {
                "validDates": int(len(arr)),
                "mean": float(np.mean(arr)) if len(arr) else None,
                "median": float(np.median(arr)) if len(arr) else None,
                "std": float(np.std(arr, ddof=0)) if len(arr) else None,
                "min": float(np.min(arr)) if len(arr) else None,
                "max": float(np.max(arr)) if len(arr) else None,
            }
        blocks = {}
        for block_id, values in per_block.items():
            ric = np.asarray([v for v in values["RankIC"] if v is not None], dtype=float)
            spr = np.asarray([v for v in values["Spread"] if v is not None], dtype=float)
            blocks[block_id] = {
                "validDates": int(len(ric)),
                "rankicMean": float(np.mean(ric)) if len(ric) else None,
                "rankicMedian": float(np.median(ric)) if len(ric) else None,
                "spreadMean": float(np.mean(spr)) if len(spr) else None,
            }
        out[scheme] = {"horizon": horizon, "aggregates": aggregates, "blocks": blocks}
    return out


def verify_metric_integrity(outputs: dict, recomputed: dict) -> dict:
    """Compare recomputed metrics/blocks/aggregates with the written artifacts."""
    worst = 0.0
    details = []
    for scheme, output in outputs.items():
        ref = recomputed[scheme]
        diffs = {}
        for name in METRIC_NAMES:
            for key in ("mean", "median", "std", "min", "max"):
                artifact = output.aggregate_metrics[name][key]
                candidate = ref["aggregates"][name][key]
                if artifact is None or candidate is None:
                    if artifact is not None or candidate is not None:
                        raise ValueError("HORIZON_SPECIFIC_METRIC_INTEGRITY_BLOCKER")
                    continue
                diff = abs(artifact - candidate)
                diffs[f"{name}.{key}"] = diff
                worst = max(worst, diff)
        for block_id in ref["blocks"]:
            for key in ("rankicMean", "rankicMedian", "spreadMean"):
                artifact = output.block_metrics[block_id][key]
                candidate = ref["blocks"][block_id][key]
                if artifact is None or candidate is None:
                    if artifact is not None or candidate is not None:
                        raise ValueError("HORIZON_SPECIFIC_METRIC_INTEGRITY_BLOCKER")
                    continue
                diff = abs(artifact - candidate)
                diffs[f"{block_id}.{key}"] = diff
                worst = max(worst, diff)
        details.append({"schemeId": scheme, "maxAbsDiff": max(diffs.values(),
                                                              default=0.0)})
    if worst > TARGET_IDENTITY_TOLERANCE:
        raise ValueError("HORIZON_SPECIFIC_METRIC_INTEGRITY_BLOCKER")
    return {"status": "PASS", "method": "independent_recompute_from_predictions",
            "toleranceAbs": TARGET_IDENTITY_TOLERANCE,
            "maxAbsDiff": worst, "perScheme": details}


def verify_advancement_integrity(rows: list[dict], recomputed: dict,
                                 c0_values: dict) -> dict:
    """Independently re-apply the frozen gates from recomputed metrics."""
    checked = 0
    for row in rows:
        if row["isControl"]:
            continue
        ref = recomputed[row["schemeId"]]
        horizon = ref["horizon"]
        mean_rankic = ref["aggregates"]["RankIC"]["mean"]
        mean_spread = ref["aggregates"]["Spread"]["mean"]
        block_rankic = {block_id: values["rankicMean"]
                        for block_id, values in ref["blocks"].items()}
        fresh = evaluate_gates(mean_rankic, mean_spread,
                               c0_values[f"C0_H{horizon}"]["meanRankIc"],
                               c0_values[f"C0_H{horizon}"]["meanSpread"],
                               block_rankic, horizon)
        for key in ("frozenGateResult", "advancementStatus", "level1", "level2",
                    "temporalStability"):
            if fresh[key] != row[key]:
                raise ValueError("ADVANCEMENT_LOGIC_INTEGRITY_BLOCKER")
        checked += 1
    return {"status": "PASS", "checkedCandidates": checked,
            "onMismatch": "ADVANCEMENT_LOGIC_INTEGRITY_BLOCKER"}


def load_frozen_d2_reference(d2_dir: Path) -> dict:
    """Read-only, hash-verified D2/C0 references for identity and reproduction."""
    expected = {"predictions.csv": D2_PREDICTIONS_SHA256,
                "aggregate_metrics.json": D2_AGGREGATE_SHA256,
                "training_diagnostics.csv": D2_TRAINING_SHA256}
    for name, digest in expected.items():
        actual = hashlib.sha256((d2_dir / name).read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError("C0_REPRODUCTION_BLOCKER: frozen D2 artifact hash changed")
    return {
        "predictions": pd.read_csv(d2_dir / "predictions.csv", dtype={"sector_code": str}),
        "aggregate": json.loads((d2_dir / "aggregate_metrics.json").read_text(encoding="utf-8")),
        "training": pd.read_csv(d2_dir / "training_diagnostics.csv",
                                dtype={"train_start": str, "label_cutoff": str,
                                       "first_train_origin": str,
                                       "last_train_origin": str,
                                       "last_train_label_end": str}),
    }


def c0_reproduction_report(outputs: dict, reference: dict) -> dict:
    """Prediction identity + metric reproduction per horizon (same-horizon C0)."""
    report = {"status": "PASS", "toleranceAbs": C0_REPRODUCTION_TOLERANCE, "perHorizon": {}}
    d2_pred = reference["predictions"]
    d2_agg = reference["aggregate"]
    worst = 0.0
    for horizon in protocol.HORIZONS:
        scheme = f"C0_H{horizon}"
        output = outputs[scheme]
        artifact_rows = d2_pred[d2_pred["horizon"] == horizon].sort_values(
            ["ordinal", "sector_code"])
        mine = output.predictions.sort_values(["ordinal", "sector_code"])
        pred_diff = float(np.max(np.abs(
            artifact_rows["prediction_score"].to_numpy(dtype=float)
            - mine["prediction_score"].to_numpy(dtype=float))))
        rank_diff = int(np.sum(
            artifact_rows["cross_sectional_rank"].to_numpy(dtype=int)
            != mine["cross_sectional_rank"].to_numpy(dtype=int)))
        ic_diff = abs(output.aggregate_metrics["IC"]["mean"] - d2_agg[f"IC_{horizon}"]["mean"])
        rankic_diff = abs(output.aggregate_metrics["RankIC"]["mean"]
                          - d2_agg[f"RankIC_{horizon}"]["mean"])
        # Frozen D2 artifact aggregate keys are snake_case ("valid_dates").
        valid_diff = abs(output.aggregate_metrics["RankIC"]["validDates"]
                         - d2_agg[f"RankIC_{horizon}"]["valid_dates"])
        # Horizon-local Top5 spread reproduction from the artifact's own
        # per-horizon predictions (the frozen NO-FUSION semantics).
        spread_values = []
        for ordinal in range(1, 101):
            day = artifact_rows[artifact_rows["ordinal"] == ordinal]
            ranked = day.sort_values(["prediction_score", "sector_code"],
                                     ascending=[False, True])
            top5 = ranked.head(5)["realized_forward_return"].to_numpy(dtype=float)
            universe = day["realized_forward_return"].to_numpy(dtype=float)
            spread_values.append(float(np.mean(top5) - np.mean(universe)))
        spread_diff = abs(output.aggregate_metrics["Spread"]["mean"]
                          - float(np.mean(spread_values)))
        worst = max(worst, pred_diff, ic_diff, rankic_diff, valid_diff, spread_diff)
        report["perHorizon"][str(horizon)] = {
            "schemeId": scheme,
            "predictionMaxAbsDiff": pred_diff,
            "predictionRankMismatches": rank_diff,
            "icMeanAbsDiff": ic_diff,
            "rankIcMeanAbsDiff": rankic_diff,
            "validDatesAbsDiff": valid_diff,
            "horizonLocalSpreadMeanAbsDiff": spread_diff,
            "legacyFusedTop5SpreadMean": d2_agg[f"Top5_minus_universe_{horizon}"]["mean"],
            "legacyFusedTop5SpreadSemantic": (
                "FUSED_TOP5_LEGACY_SEMANTICS_NOT_COMPARABLE_TO_HORIZON_LOCAL_TOP5"),
            "horizonLocalSpreadMean": output.aggregate_metrics["Spread"]["mean"],
        }
        if rank_diff:
            raise ValueError("C0_REPRODUCTION_BLOCKER: prediction rank mismatch")
    report["maxAbsDiff"] = worst
    if worst > C0_REPRODUCTION_TOLERANCE:
        raise ValueError("C0_REPRODUCTION_BLOCKER")
    return report


def pre_run_gate(processed_dir: Path, repo_dir: Path, docker_image_id: str) -> dict:
    """Fail closed: frozen protocol identity, git state, environment, seals."""
    protocol.verify_protocol()
    if docker_image_id != baseline.EXPECTED_IMAGE_ID:
        raise ValueError("ENVIRONMENT_DRIFT_BLOCKER: Docker image ID changed")
    branch = baseline._git(repo_dir, "branch", "--show-current")
    head = baseline._git(repo_dir, "rev-parse", "HEAD")
    if branch != EXPECTED_BRANCH:
        raise ValueError("RESEARCH_WORKTREE_DIRTY_BLOCKER: branch changed")
    for line in baseline._git(repo_dir, "status", "--porcelain").splitlines():
        if not line.startswith("?? ") or line[3:] not in ALLOWED_UNTRACKED:
            raise ValueError("RESEARCH_WORKTREE_DIRTY_BLOCKER: " + line)
    baseline._git(repo_dir, "merge-base", "--is-ancestor", PREREGISTRATION_COMMIT, head)
    changed = baseline._git(repo_dir, "diff", "--name-only", PREREGISTRATION_COMMIT,
                            "HEAD", "--", *FROZEN_PATHS).splitlines()
    changed += baseline._git(repo_dir, "diff", "--name-only", "HEAD", "--",
                             *FROZEN_PATHS).splitlines()
    if changed:
        raise ValueError("HISTORICAL_RESEARCH_MUTATION_BLOCKER")
    audit = audit_local_policy(processed_dir)
    if (audit["split_policy_hash"] != baseline.EXPECTED_SPLIT_HASH
            or audit["prediction_config_hash"] != baseline.EXPECTED_PREDICTION_HASH
            or audit["data_snapshot_id"] != baseline.EXPECTED_SNAPSHOT
            or audit["synthetic_portfolio_config_hash"] is not None):
        raise ValueError("RESEARCH_PROTOCOL_HASH_MISMATCH")
    dev = audit["availability"]["development"]
    if (audit["split_policy"]["formal_universe_sector_count"] != 124
            or dev["available_count"] != 100
            or (dev["available_start"], dev["available_end"])
            != baseline.EXPECTED_DEVELOPMENT_DATES
            or audit["validation_status"] != "LOCKED_PARTIALLY_AVAILABLE_UNOPENED"
            or audit["oos_performance_status"] != "UNOPENED"):
        raise ValueError("REPO_PROTOCOL_CONFLICT: frozen Development identity changed")
    config = protocol.load_config()
    return {
        "gate": "PASS", "branch": branch, "git_head": head, "git_status": "clean",
        "docker_image_id": docker_image_id, "environment_changed": False,
        "preregistrationCommit": PREREGISTRATION_COMMIT,
        "protocolHash": protocol.FROZEN_PROTOCOL_HASH,
        "configHash": protocol.FROZEN_CONFIG_HASH,
        "researchType": RESEARCH_TYPE,
        "split_policy_hash": baseline.EXPECTED_SPLIT_HASH,
        "prediction_config_hash": baseline.EXPECTED_PREDICTION_HASH,
        "sector_snapshot_id": baseline.EXPECTED_SNAPSHOT,
        "universe": "U0_FIXED_124", "sector_count": 124,
        "developmentIds": "E001-E100",
        "development_first_date": dev["available_start"],
        "development_last_date": dev["available_end"],
        "validation_access": "SEALED", "final_oos_access": "SEALED",
        "noFusion": True, "noCrossHorizonWinner": True,
        "schemes": [spec["schemeId"] for spec in scheme_specs()],
        "candidateIds": list(protocol.CANDIDATE_IDS),
        "h40EvidenceQualityWarning": config["h40EvidenceQualityWarning"],
    }


def compute_schemes(processed_dir: Path, gate: dict) -> tuple[dict, dict, dict]:
    """One deterministic pass; per-date shared panel; one horizon per scheme."""
    if gate.get("gate") != "PASS":
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: pre-run gate not passed")
    protocol.verify_protocol()
    specs = scheme_specs()
    audit = audit_local_policy(processed_dir)
    codes, names, calendar, frames, invalid_in_window, invalid_total = baseline._verified_market(
        processed_dir, audit["development_last_120_label_endpoint"])
    if invalid_in_window or len(codes) != 124:
        raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: invalid fixed universe")
    eligible = calendar[
        (calendar >= pd.Timestamp(audit["availability"]["development"]["available_start"]))
        & (calendar <= pd.Timestamp("2026-03-27"))
    ]
    verify_frozen_prefix(eligible, codes)
    dates = eligible[:100]
    ordinals = guard_evaluation_dates("development", dates, eligible)
    if (ordinals != list(range(1, 101))
            or (str(dates[0].date()), str(dates[-1].date()))
            != baseline.EXPECTED_DEVELOPMENT_DATES):
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: Development ordinal drift")
    label_calendar = calendar[calendar <= pd.Timestamp(audit["development_last_120_label_endpoint"])]
    labels_expost = {
        horizon: {code: make_forward_label(frames[code]["close"], horizon,
                                           calendar=label_calendar)
                  for code in codes}
        for horizon in protocol.HORIZONS
    }
    core = SWSectorRotationCore(SWSectorRotationConfig())
    if core.feature_names != list(protocol.FROZEN_FACTOR_ORDER):
        raise ValueError("REPO_PROTOCOL_CONFLICT: feature order")
    state = {spec["schemeId"]: {"predictions": [], "per_date": [], "training": [],
                                "targets": [], "leakage_checks": 0}
             for spec in specs}
    stashed: dict = {}
    for ordinal, signal in zip(ordinals, dates):
        protocol.guard_scope("development", [ordinal])
        signal_s = str(signal.date())
        signal_i = int(calendar.get_loc(signal))
        boundaries = {}
        for horizon in protocol.HORIZONS:
            boundary = core.boundaries(calendar[:signal_i + 1], signal,
                                       period_for_horizon(horizon))
            if boundary is None:
                raise ValueError("RESEARCH_LEAKAGE_BLOCKER: temporal boundary")
            boundaries[horizon] = boundary
        first_train_candidates = [boundaries[h].train_start for h in protocol.HORIZONS]
        first_train_i = int(calendar.searchsorted(min(first_train_candidates)))
        warmup_i = first_train_i - FEATURE_WARMUP
        if warmup_i < 0:
            raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: warmup")
        visible_calendar = calendar[warmup_i:signal_i + 1]
        visible_frames = {code: baseline._source_frame(frames[code], calendar[warmup_i], signal)
                          for code in codes}
        if any(not frame.index.equals(visible_calendar) for frame in visible_frames.values()):
            raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: U0 history incomplete")
        panel = core.build_panel(visible_frames, include_rsrs=False,
                                 calendar=visible_calendar)
        if ordinal in IDENTITY_SAMPLE_ORDINALS:
            for code in codes[:IDENTITY_SAMPLE_SECTOR_COUNT]:
                row = panel[code].loc[signal]
                stashed[(ordinal, code)] = {
                    f: float(row[f]) for f in protocol.FROZEN_FACTOR_ORDER}
        for spec in specs:
            scheme = spec["schemeId"]
            horizon = spec["horizon"]
            boundary = boundaries[horizon]
            factor_names = spec["factorList"]
            label_column = f"fwd{horizon}"
            candidate_dates = visible_calendar[
                (visible_calendar >= boundary.train_start)
                & (visible_calendar <= boundary.label_cutoff)
            ]
            labelled_sets = [set(frame.dropna(subset=[label_column]).index)
                             for frame in panel.values()]
            labelled = sorted(set.intersection(*labelled_sets)) if labelled_sets else []
            train_dates = [d for d in labelled
                           if boundary.train_start <= d <= boundary.label_cutoff]
            if len(train_dates) < MIN_TRAIN_DATES:
                raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: insufficient training")
            checks = baseline.assert_training_labels_realized(
                calendar, candidate_dates, signal, horizon, len(codes))
            origins = pd.DatetimeIndex(np.tile(train_dates, len(codes)))
            positions = calendar.get_indexer(origins)
            iteration1_protocol.assert_training_chronology(
                origins, calendar[positions + horizon], signal)
            endpoint = calendar[signal_i + horizon]
            if endpoint > label_calendar[-1]:
                raise ValueError("RESEARCH_PROTOCOL_VIOLATION: label endpoint beyond Purge 1")
            arrays = [panel[code].loc[train_dates, factor_names + [label_column]]
                      .to_numpy(dtype=float) for code in codes]
            stacked = np.vstack(arrays)
            x_train, raw_y = stacked[:, :-1], stacked[:, -1]
            x_predict = np.vstack([
                panel[code].loc[signal, factor_names].to_numpy(dtype=float)
                for code in codes])
            if (not np.isfinite(stacked).all() or not np.isfinite(x_predict).all()
                    or len(train_dates) != len(candidate_dates)
                    or len(stacked) != len(codes) * len(train_dates)):
                raise ValueError(
                    "RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: silent sector/date exclusion")
            target = iteration1_protocol.cross_sectional_excess_training_target(
                raw_y, origins, horizon=horizon)
            residual = max(abs(float(target[origins == d].mean()))
                           for d in origins.unique())
            if residual > 1e-12:
                raise ValueError("RESEARCH_LEAKAGE_BLOCKER: target demean residual")
            model = NumPyRidge(alpha=DEFAULT_ALPHA, fit_intercept=True).fit(x_train, target)
            scores = {code: float(value) for code, value in
                      zip(codes, model.predict(x_predict))}
            ranking = rank_sectors(scores)
            top_codes = [code for code, _ in select_top(ranking, 5)]
            item = state[scheme]
            item["leakage_checks"] += checks
            item["targets"].append({"ordinal": ordinal,
                                    "max_abs_mean": residual})
            item["training"].append({
                "candidate": scheme, "horizon": horizon, "ordinal": ordinal,
                "signal_date": signal_s, "status": "success", "reason": None,
                "train_start": str(boundary.train_start.date()),
                "label_cutoff": str(boundary.label_cutoff.date()),
                "first_train_origin": str(train_dates[0].date()),
                "last_train_origin": str(train_dates[-1].date()),
                "last_train_label_end": str(calendar[
                    int(calendar.get_loc(train_dates[-1])) + horizon].date()),
                "training_candidate_days": len(candidate_dates),
                "training_valid_days": len(train_dates),
                "training_observations": len(stacked),
                "valid_sector_count": len(scores), "leakage_checks": checks,
            })
            labels_today = {}
            for code in codes:
                value = labels_expost[horizon][code].get(signal, np.nan)
                if pd.isna(value) or not np.isfinite(value):
                    raise ValueError(
                        "RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: missing realized label")
                labels_today[code] = float(value)
            ranked = {code: i for i, (code, _) in enumerate(ranking, 1)}
            for code in codes:
                item["predictions"].append({
                    "candidate": scheme, "horizon": horizon, "ordinal": ordinal,
                    "signal_date": signal_s, "sector_code": code,
                    "sector_name": names[code],
                    "prediction_score": scores[code],
                    "cross_sectional_rank": ranked[code],
                    "top5": code in top_codes,
                    "realized_forward_return": labels_today[code],
                    "label_end": str(endpoint.date()), "exclusion_reason": None,
                    "training_observations": len(stacked),
                    "training_valid_days": len(train_dates),
                    "training_label_cutoff": str(boundary.label_cutoff.date()),
                })
            metrics = horizon_local_metrics(scores, labels_today, top_codes)
            for name in METRIC_NAMES:
                item["per_date"].append({
                    "candidate": scheme, "horizon": horizon, "ordinal": ordinal,
                    "signal_date": signal_s, "metric": name,
                    "value": metrics[name],
                    "null_reason": metrics["null_reason"],
                    "valid_sector_count": metrics["valid_sector_count"],
                })
    outputs = {}
    for spec in specs:
        scheme = spec["schemeId"]
        item = state[scheme]
        predictions = pd.DataFrame(item["predictions"], columns=PREDICTION_COLUMNS)
        per_date = pd.DataFrame(item["per_date"], columns=PER_DATE_COLUMNS)
        training = pd.DataFrame(item["training"], columns=TRAINING_COLUMNS)
        if (len(predictions) != 100 * 124 or len(per_date) != 100 * len(METRIC_NAMES)
                or len(training) != 100
                or predictions.duplicated(["ordinal", "sector_code"]).any()
                or set(predictions["ordinal"]) != set(range(1, 101))):
            raise ValueError("RESEARCH_PROTOCOL_VIOLATION: scheme grid incomplete")
        outputs[scheme] = SchemeOutput(
            predictions=predictions,
            per_date_metrics=per_date,
            aggregate_metrics=aggregate_scheme_metrics(per_date),
            block_metrics=block_metrics_for(per_date),
            training_diagnostics=training,
            data_quality_diagnostics={
                "attempted_development_dates": 100, "successful_dates": 100,
                "skipped_dates": [], "excluded_sector_date_rows": [],
                "missing_factor_exclusions": 0, "missing_label_exclusions": 0,
                "numerical_failures": 0, "insufficient_training_cases": 0,
                "source_invalid_total_in_snapshot": invalid_total,
                "source_invalid_interactions_with_development": invalid_in_window,
                "training_observation_leakage_checks": item["leakage_checks"],
                "training_label_end_after_signal_count": 0,
                "no_fusion": True,
            },
            transformation_diagnostics={
                "x_preprocessing": "RAW_NO_STANDARDIZATION",
                "training_target": "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN",
                "demean_residual_max_abs_mean": max(
                    (row["max_abs_mean"] for row in item["targets"]), default=None),
                "target_diagnostics": item["targets"],
            },
        )
    return outputs, stashed, {
        "codes": codes, "frames": frames, "calendar": calendar, "dates": dates,
        "labels_expost": labels_expost,
    }


def evaluate_outputs(outputs: dict, stashed: dict, context: dict,
                     d2_dir: Path) -> tuple[dict, pd.DataFrame, dict]:
    """Gates, summaries and every integrity check, before any interpretation."""
    reference = load_frozen_d2_reference(d2_dir)
    factor_identity = factor_identity_gate(
        stashed, context["frames"], context["calendar"], context["dates"], context["codes"])
    target_identity = target_identity_gate(
        context["labels_expost"], context["frames"], context["calendar"],
        context["dates"], context["codes"], reference["predictions"])
    training_identity = {"status": "PASS", "perScheme": {}, "sampleCount": 0,
                         "sampledOrdinals": list(TRAINING_WINDOW_ORDINALS),
                         "sampledHorizons": list(protocol.HORIZONS),
                         "coverage": [], "onMismatch": "TRAINING_WINDOW_IDENTITY_BLOCKER"}
    covered = set()
    for scheme, output in outputs.items():
        check = training_window_identity_gate(output.training_diagnostics,
                                              reference["training"])
        training_identity["perScheme"][scheme] = check["sampleCount"]
        training_identity["sampleCount"] += check["sampleCount"]
        for horizon in check["sampledHorizons"]:
            for ordinal in TRAINING_WINDOW_ORDINALS:
                covered.add((ordinal, horizon))
    required = {(ordinal, horizon) for ordinal in TRAINING_WINDOW_ORDINALS
                for horizon in protocol.HORIZONS}
    if covered != required:
        raise ValueError("TRAINING_WINDOW_IDENTITY_BLOCKER: coverage")
    training_identity["coverage"] = sorted(f"E{o:03d}-H{h}" for o, h in covered)
    top5_identity = top5_identity_check(outputs)
    c0_reproduction = c0_reproduction_report(outputs, reference)
    recomputed = recompute_from_predictions(
        {scheme: output.predictions for scheme, output in outputs.items()})
    metric_integrity = verify_metric_integrity(outputs, recomputed)
    c0_values = {}
    for horizon in protocol.HORIZONS:
        output = outputs[f"C0_H{horizon}"]
        c0_values[f"C0_H{horizon}"] = {
            "meanRankIc": output.aggregate_metrics["RankIC"]["mean"],
            "meanSpread": output.aggregate_metrics["Spread"]["mean"],
        }
    rows = []
    for spec in scheme_specs():
        scheme = spec["schemeId"]
        output = outputs[scheme]
        horizon = spec["horizon"]
        mean_rankic = output.aggregate_metrics["RankIC"]["mean"]
        mean_spread = output.aggregate_metrics["Spread"]["mean"]
        block_rankic = {block_id: values["rankicMean"]
                        for block_id, values in output.block_metrics.items()}
        if spec["isControl"]:
            rows.append({
                "schemeId": scheme, "isControl": True, "horizon": horizon,
                "archetype": "CONTROL", "factorList": spec["factorList"],
                "factorCount": len(spec["factorList"]),
                "advancementStatus": STATUS_CONTROL,
                "frozenGateResult": STATUS_CONTROL,
                "level1": "NOT_APPLICABLE", "level2": "NOT_APPLICABLE",
                "temporalStability": "NOT_APPLICABLE",
                "simplicityPreference": "NOT_APPLICABLE",
                "meanRankIc": mean_rankic, "meanSpread": mean_spread,
                "aggregateMetrics": output.aggregate_metrics,
                "blockMetrics": output.block_metrics,
                "deltaVsSameHorizonC0": None,
                "warnings": [],
            })
            continue
        gates = evaluate_gates(mean_rankic, mean_spread,
                               c0_values[f"C0_H{horizon}"]["meanRankIc"],
                               c0_values[f"C0_H{horizon}"]["meanSpread"],
                               block_rankic, horizon)
        rows.append({
            "schemeId": scheme, "isControl": False, "horizon": horizon,
            "archetype": spec["archetype"], "factorList": spec["factorList"],
            "factorCount": len(spec["factorList"]),
            **gates, "simplicityPreference": "NOT_APPLICABLE",
            "meanRankIc": mean_rankic, "meanSpread": mean_spread,
            "aggregateMetrics": output.aggregate_metrics,
            "blockMetrics": output.block_metrics,
            "deltaVsSameHorizonC0": {
                "meanRankIc": mean_rankic - c0_values[f"C0_H{horizon}"]["meanRankIc"],
                "meanSpread": mean_spread - c0_values[f"C0_H{horizon}"]["meanSpread"],
            },
            "warnings": warnings_for(spec["schemeId"], horizon),
        })
    simplicity = apply_simplicity_preference(rows)
    for row in rows:
        row["simplicityPreference"] = simplicity.get(
            row["schemeId"], row["simplicityPreference"])
    advancement_integrity = verify_advancement_integrity(rows, recomputed, c0_values)
    for row in rows:
        if any(bad in row["advancementStatus"] for bad in FORBIDDEN_RESULT_LABELS):
            raise ValueError("RESULT_LABEL_RESTRICTION_VIOLATION")
    summary = {
        "researchType": RESEARCH_TYPE,
        "preregistrationCommit": PREREGISTRATION_COMMIT,
        "protocolHash": protocol.FROZEN_PROTOCOL_HASH,
        "noFusion": True, "noCrossHorizonWinner": True,
        "developmentReuseWarning": True,
        "interpretation": ("POST_AUDIT_DEVELOPMENT_HYPOTHESIS_REFINEMENT_"
                           "NOT_INDEPENDENT_VALIDATION_OR_OOS"),
        "h40EvidenceQualityWarning": "NO_STRONG_STABILITY_EVIDENCE",
        "control": [row for row in rows if row["isControl"]],
        "candidates": [row for row in rows if not row["isControl"]],
        "c0Reproduction": c0_reproduction,
        "notices": [
            "DEVELOPMENT ONLY", "POST-AUDIT DEVELOPMENT HYPOTHESIS REFINEMENT",
            "DEVELOPMENT_REUSE_WARNING=true", "NOT INDEPENDENT VALIDATION",
            "NOT OOS", "NOT VALIDATED ALPHA", "NOT TRADABLE", "NO FUSION",
            "NO CROSS-HORIZON WINNER", "NO PARAMETER SEARCH", "NO SIGN FLIP",
        ],
    }
    blocks = []
    for row in rows:
        for block_id, values in row["blockMetrics"].items():
            blocks.append({
                "candidate": row["schemeId"], "horizon": row["horizon"],
                "block": block_id, "first": values["first"], "last": values["last"],
                "valid_dates": values["validDates"],
                "rankic_mean": values["rankicMean"],
                "rankic_median": values["rankicMedian"],
                "spread_mean": values["spreadMean"],
            })
    block_frame = pd.DataFrame(blocks, columns=(
        "candidate", "horizon", "block", "first", "last", "valid_dates",
        "rankic_mean", "rankic_median", "spread_mean"))
    integrity = {
        "factorIdentity": factor_identity, "targetIdentity": target_identity,
        "trainingWindowIdentity": training_identity, "c0Reproduction": c0_reproduction,
        "top5Identity": top5_identity, "metricRecompute": metric_integrity,
        "advancementLogic": advancement_integrity,
    }
    return summary, block_frame, integrity


def build_metadata(gate: dict, summary: dict, run_id: str,
                   content_hashes: dict, repeat_of: Path | None) -> dict:
    config = protocol.load_config()
    specs = scheme_specs()
    metadata = {
        "researchType": RESEARCH_TYPE,
        "phase": "DEVELOPMENT",
        "preregistrationCommit": PREREGISTRATION_COMMIT,
        "protocolHash": protocol.FROZEN_PROTOCOL_HASH,
        "executionGitCommit": gate["git_head"],
        "branch": gate["branch"],
        "sectorSnapshotId": baseline.EXPECTED_SNAPSHOT,
        "splitPolicyHash": baseline.EXPECTED_SPLIT_HASH,
        "developmentIds": "E001-E100",
        "universe": "U0",
        "candidateIds": list(protocol.CANDIDATE_IDS),
        "candidateFactorLists": {spec["schemeId"]: spec["factorList"] for spec in specs},
        "candidateHorizon": {spec["schemeId"]: spec["horizon"] for spec in specs},
        "factorOrder": list(protocol.FROZEN_FACTOR_ORDER),
        "target": "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN",
        "model": "NUMPY_RIDGE",
        "alpha": DEFAULT_ALPHA,
        "preprocessing": "RAW_NO_STANDARDIZATION",
        "trainWindow": "6_CALENDAR_MONTHS",
        "minTrainingDays": MIN_TRAIN_DATES,
        "topKSemantics": "PREDICTION_DESCENDING_SECTOR_CODE_ASCENDING_TOP5",
        "noFusion": True,
        "validation": "SEALED",
        "finalOos": "SEALED",
        "strictPit": False,
        "classification": "FIXED_CLASSIFICATION_RESEARCH",
        "executable": False,
        "tradable": False,
        "DEVELOPMENT_REUSE_WARNING": True,
        "INDEPENDENT_VALIDATION": False,
        "OOS": False,
        "h40EvidenceQualityWarning": config["h40EvidenceQualityWarning"],
        "run_id": run_id,
        "docker_image_id": gate["docker_image_id"],
        "environment_changed": False,
        "content_sha256": content_hashes,
        "advancementStatuses": {row["schemeId"]: row["advancementStatus"]
                                for row in summary["candidates"]},
        "notices": summary["notices"],
    }
    if repeat_of is not None:
        previous = json.loads((repeat_of / "metadata.json").read_text(encoding="utf-8"))
        if (previous["content_sha256"] != content_hashes
                or previous["protocolHash"] != metadata["protocolHash"]):
            raise ValueError("HORIZON_SPECIFIC_DETERMINISM_BLOCKER")
        metadata["determinism_repeat_of"] = previous["run_id"]
        metadata["determinism"] = "PASS_CONTENT_SHA256_IDENTICAL"
    return metadata


def write_run(output_root: Path, outputs: dict, summary: dict,
              blocks: pd.DataFrame, integrity: dict, gate: dict,
              repeat_of: Path | None = None) -> Path:
    for scheme, output in outputs.items():
        if (len(output.predictions) != 100 * 124
                or output.predictions.duplicated(["ordinal", "sector_code"]).any()
                or set(output.predictions["ordinal"]) != set(range(1, 101))):
            raise ValueError("RESEARCH_PROTOCOL_VIOLATION: incomplete scheme grid")
        protocol.guard_scope("development",
                             sorted(set(output.per_date_metrics["ordinal"].astype(int))))
    run_id = datetime.now(timezone.utc).strftime("horizon_specific_alpha_v1_%Y%m%d_%H%M%S_%f_utc")
    if not run_id.replace("_", "").isalnum():
        raise ValueError("run_id contains unsafe characters")
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / run_id
    target.mkdir(exist_ok=False)
    hashes = {}
    for spec in scheme_specs():
        scheme = spec["schemeId"]
        folder = target / scheme
        folder.mkdir()
        output = outputs[scheme]
        payloads = {
            "predictions.csv": baseline._csv_bytes(output.predictions),
            "per_date_metrics.csv": baseline._csv_bytes(output.per_date_metrics),
            "aggregate_metrics.json": baseline._json_bytes(output.aggregate_metrics),
            "training_diagnostics.csv": baseline._csv_bytes(output.training_diagnostics),
            "data_quality_diagnostics.json": baseline._json_bytes(output.data_quality_diagnostics),
            "transformation_diagnostics.json": baseline._json_bytes(output.transformation_diagnostics),
        }
        for name, content in payloads.items():
            (folder / name).write_bytes(content)
            hashes[f"{scheme}/{name}"] = hashlib.sha256(content).hexdigest()
    run_payloads = {
        "candidate_summary.json": baseline._json_bytes(summary),
        "block_stability.csv": baseline._csv_bytes(blocks),
        "integrity.json": baseline._json_bytes(integrity),
    }
    for name, content in run_payloads.items():
        (target / name).write_bytes(content)
        hashes[name] = hashlib.sha256(content).hexdigest()
    metadata = build_metadata(gate, summary, run_id, hashes, repeat_of)
    (target / "metadata.json").write_bytes(baseline._json_bytes(metadata))
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker-image-id", required=True)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/shenwan"))
    parser.add_argument("--output-root", type=Path,
                        default=Path("reports/research/shenwan_sector_index"))
    parser.add_argument("--d2-source-dir", type=Path,
                        default=Path("reports/research/shenwan_sector_index")
                        / ITERATION1_RUN_ID / "D2")
    parser.add_argument("--repeat-of", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    repo_dir = Path(__file__).resolve().parents[1]
    gate = pre_run_gate(args.processed_dir, repo_dir, args.docker_image_id)
    load_frozen_d2_reference(args.d2_source_dir)
    print("HORIZON-SPECIFIC V1 PRE-RUN GATE", flush=True)
    print(json.dumps(gate, sort_keys=True, ensure_ascii=False, indent=2), flush=True)
    if not args.execute:
        return 0
    outputs, stashed, context = compute_schemes(args.processed_dir, gate)
    summary, blocks, integrity = evaluate_outputs(outputs, stashed, context,
                                                  args.d2_source_dir)
    target = write_run(args.output_root, outputs, summary, blocks, integrity, gate,
                       args.repeat_of)
    print(f"HORIZON-SPECIFIC V1 RUN COMPLETE: {target}", flush=True)
    print(json.dumps({"run_dir": str(target),
                      "content_sha256": json.loads(
                          (target / "metadata.json").read_text(encoding="utf-8"))["content_sha256"]},
                     sort_keys=True, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
