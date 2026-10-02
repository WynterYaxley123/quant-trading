"""Execute only the frozen four-candidate Development Iteration-1 protocol.

The sealed phases are never loaded for scoring. Purge 1 prices are used only
to realize Development labels, exactly as in the frozen baseline adapter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research import development_iteration1_protocol as protocol
from research import sector_development_baseline as baseline
from research.sector_development_protocol import (
    guard_evaluation,
    guard_evaluation_dates,
    verify_frozen_prefix,
)
from research.sector_index_baseline import FEATURE_WARMUP
from research.sector_universe_feasibility import prediction_metric_contract
from strategies.sw_sector_rotation.src.common.temporal_integrity import make_forward_label
from strategies.sw_sector_rotation.src.model.model import (
    DEFAULT_ALPHA,
    DEFAULT_TOP_N,
    FORWARD_WINDOWS,
    FUSION_WEIGHTS,
    MIN_TRAIN_DATES,
    NumPyRidge,
    RankingResult,
)
from strategies.sw_sector_rotation.src.model.ranking import rank_sectors
from strategies.sw_sector_rotation.src.strategy import SWSectorRotationConfig, SWSectorRotationCore

STARTING_HEAD = "dc5626ac33da6953ae908eb0d1a0c01769474a7f"
BASELINE_RUN_ID = "20260924_145948_233618_utc"
BASELINE_AGGREGATE_SHA256 = "6948a3933ce88d85fe9ca106f40849cdad40801e4082c43bef3ab0254a07fd6c"
ARTIFACT_NAMES = (
    "predictions.csv",
    "per_date_metrics.csv",
    "aggregate_metrics.json",
    "training_diagnostics.csv",
    "data_quality_diagnostics.json",
)
WIDE_COLUMNS = (
    "ordinal",
    "signal_date",
    "sector_code",
    "pred_10",
    "pred_40",
    "pred_120",
    "fused_score",
    "fused_rank",
    "top5",
    "realized_forward_return_10",
    "realized_forward_return_40",
    "realized_forward_return_120",
    "label_end_10",
    "label_end_40",
    "label_end_120",
    "training_observations_10",
    "training_observations_40",
    "training_observations_120",
    "training_valid_days_10",
    "training_valid_days_40",
    "training_valid_days_120",
)


def transform_candidate(
    candidate_id: str,
    x_train: np.ndarray,
    x_predict: np.ndarray,
    raw_y: np.ndarray,
    origin_dates: pd.DatetimeIndex,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """Apply precisely the preregistered D0/D1/D2/D3 training transforms."""
    if candidate_id not in protocol.FROZEN_CANDIDATE_IDS:
        raise ValueError("ITERATION1_CANDIDATE_BUDGET_VIOLATION")
    train, predict, target = x_train, x_predict, raw_y
    diagnostic = {"scaler": None, "demean_residual_max_abs_mean": None}
    if candidate_id in {"D1", "D3"}:
        train, predict, diagnostic["scaler"] = protocol.standardize_train_predict(train, predict)
    if candidate_id in {"D2", "D3"}:
        target = protocol.cross_sectional_excess_training_target(
            raw_y,
            origin_dates,
            horizon=horizon,
        )
        diagnostic["demean_residual_max_abs_mean"] = max(
            abs(float(target[origin_dates == date].mean())) for date in origin_dates.unique()
        )
        if diagnostic["demean_residual_max_abs_mean"] > 1e-12:
            raise ValueError("RESEARCH_LEAKAGE_BLOCKER: target demean residual")
    return train, predict, target, diagnostic


def verify_d0_control(source: Path) -> dict:
    """Verify all original artifact hashes before copying their exact bytes."""
    metadata = json.loads((source / "metadata.json").read_text(encoding="utf-8"))
    if (
        metadata["artifact_sha256"]["aggregate_metrics.json"] != BASELINE_AGGREGATE_SHA256
        or metadata["sector_snapshot_id"] != baseline.EXPECTED_SNAPSHOT
        or metadata["phase"] != "DEVELOPMENT"
        or metadata["strict_pit"] is not False
    ):
        raise ValueError("D0_CONTROL_REPRODUCTION_BLOCKER: metadata")
    hashes = {}
    for name in ARTIFACT_NAMES:
        digest = hashlib.sha256((source / name).read_bytes()).hexdigest()
        if digest != metadata["artifact_sha256"][name]:
            raise ValueError(f"D0_CONTROL_REPRODUCTION_BLOCKER: {name}")
        hashes[name] = digest
    return hashes


def long_to_wide(long: pd.DataFrame) -> pd.DataFrame:
    """One row per Development signal and fixed-universe sector."""
    if (
        len(long) != 100 * 124 * 3
        or long.duplicated(["ordinal", "sector_code", "horizon"]).any()
        or set(long["ordinal"]) != set(range(1, 101))
        or set(long["horizon"]) != set(FORWARD_WINDOWS.values())
    ):
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: prediction grid incomplete")
    rows = []
    for (ordinal, code), group in long.groupby(["ordinal", "sector_code"], sort=True):
        by_h = {int(row.horizon): row for row in group.itertuples(index=False)}
        if (
            set(by_h) != set(FORWARD_WINDOWS.values())
            or len({row.fused_rank for row in by_h.values()}) != 1
            or len({row.top5 for row in by_h.values()}) != 1
        ):
            raise ValueError("RESEARCH_PROTOCOL_VIOLATION: Top5 differs by horizon")
        first = by_h[10]
        item = {
            "ordinal": int(ordinal),
            "signal_date": first.signal_date,
            "sector_code": code,
            "fused_score": first.fused_score,
            "fused_rank": first.fused_rank,
            "top5": bool(first.top5),
        }
        for h in FORWARD_WINDOWS.values():
            row = by_h[h]
            item[f"pred_{h}"] = row.prediction_score
            item[f"realized_forward_return_{h}"] = row.realized_forward_return
            item[f"label_end_{h}"] = row.label_end
            item[f"training_observations_{h}"] = row.training_observations
            item[f"training_valid_days_{h}"] = row.training_valid_days
        rows.append(item)
    result = pd.DataFrame(rows, columns=WIDE_COLUMNS)
    if len(result) != 100 * 124 or not result.groupby("ordinal")["top5"].sum().eq(5).all():
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: single fused Top5 failed")
    for _, day in result.groupby("ordinal", sort=True):
        actual = day.loc[day["top5"]].sort_values("fused_rank")["sector_code"].tolist()
        expected = (
            day.sort_values(["fused_score", "sector_code"], ascending=[False, True])
            .head(5)["sector_code"]
            .tolist()
        )
        if actual != expected:
            raise ValueError("RESEARCH_PROTOCOL_VIOLATION: Top5 not highest fused scores")
    return result


def pre_run_gate(processed_dir: Path, repo_dir: Path, image_id: str) -> dict:
    payload = protocol.verify_frozen_iteration1_protocol()
    gate = baseline.pre_run_gate(processed_dir, repo_dir, image_id)
    if (
        tuple(row["id"] for row in payload["candidate_family"]["candidates"])
        != protocol.FROZEN_CANDIDATE_IDS
    ):
        raise ValueError("ITERATION1_CANDIDATE_BUDGET_VIOLATION")
    baseline._git(repo_dir, "merge-base", "--is-ancestor", STARTING_HEAD, gate["git_head"])
    changed = baseline._git(
        repo_dir, "diff", "--name-only", STARTING_HEAD, gate["git_head"]
    ).splitlines()
    if set(changed) - {
        "research/development_iteration1_run.py",
        "tests/test_development_iteration1_run.py",
    }:
        raise ValueError("ITERATION1_STATE_MISMATCH: frozen source changed")
    common = payload["common_config"]
    if (
        common["feature_names_ordered"] != list(baseline.EXPECTED_FEATURES)
        or common["ridge_alpha"] != DEFAULT_ALPHA
        or common["horizons_sessions"] != list(FORWARD_WINDOWS.values())
        or common["fusion_weights"] != list(FUSION_WEIGHTS.values())
        or common["top_k"] != DEFAULT_TOP_N
        or common["minimum_valid_training_days"] != MIN_TRAIN_DATES
    ):
        raise ValueError("ITERATION1_PROTOCOL_HASH_MISMATCH: implementation configuration")
    return {
        **gate,
        "starting_head": STARTING_HEAD,
        "development_iteration1_protocol_hash": protocol.development_iteration1_protocol_hash(),
        "candidate_ids": list(protocol.FROZEN_CANDIDATE_IDS),
        "candidate_count": 4,
        "feature_count": 19,
        "alpha": DEFAULT_ALPHA,
        "horizons": list(FORWARD_WINDOWS.values()),
        "fusion": list(FUSION_WEIGHTS.values()),
        "top_k": DEFAULT_TOP_N,
        "new_candidate_performance_viewed": False,
    }


def compute_candidates(processed_dir: Path, gate: dict) -> dict[str, baseline.DevelopmentOutput]:
    """Score D1-D3 together so there is no performance-driven early stop."""
    audit = baseline.audit_local_policy(processed_dir)
    codes, names, calendar, frames, invalid_in_window, invalid_total = baseline._verified_market(
        processed_dir,
        audit["development_last_120_label_endpoint"],
    )
    if invalid_in_window or len(codes) != 124:
        raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: invalid fixed universe")
    eligible = calendar[
        (calendar >= pd.Timestamp(audit["availability"]["development"]["available_start"]))
        & (calendar <= pd.Timestamp("2026-03-27"))
    ]
    verify_frozen_prefix(eligible, codes)
    dates = eligible[:100]
    ordinals = guard_evaluation_dates("development", dates, eligible)
    if (
        ordinals != list(range(1, 101))
        or (str(dates[0].date()), str(dates[-1].date())) != baseline.EXPECTED_DEVELOPMENT_DATES
    ):
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: Development ordinal drift")
    label_calendar = calendar[
        calendar <= pd.Timestamp(audit["development_last_120_label_endpoint"])
    ]
    labels = {
        h: {
            code: make_forward_label(frames[code]["close"], h, calendar=label_calendar)
            for code in codes
        }
        for h in FORWARD_WINDOWS.values()
    }
    core = SWSectorRotationCore(SWSectorRotationConfig())
    if core.feature_names != list(baseline.EXPECTED_FEATURES):
        raise ValueError("REPO_PROTOCOL_CONFLICT: feature order")
    state = {
        cid: {
            "predictions": [],
            "per_date": [],
            "training": [],
            "scalers": [],
            "targets": [],
            "leakage_checks": 0,
        }
        for cid in protocol.FROZEN_CANDIDATE_IDS[1:]
    }
    for ordinal, signal in zip(ordinals, dates):
        guard_evaluation("development", [ordinal])
        signal_s = str(signal.date())
        signal_i = int(calendar.get_loc(signal))
        boundaries = {
            p: core.boundaries(calendar[: signal_i + 1], signal, p) for p in FORWARD_WINDOWS
        }
        if any(b is None for b in boundaries.values()):
            raise ValueError("RESEARCH_LEAKAGE_BLOCKER: temporal boundary")
        first_train_i = int(calendar.searchsorted(min(b.train_start for b in boundaries.values())))
        warmup_i = first_train_i - FEATURE_WARMUP
        if warmup_i < 0:
            raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: warmup")
        visible_calendar = calendar[warmup_i : signal_i + 1]
        visible_frames = {
            code: baseline._source_frame(frames[code], calendar[warmup_i], signal) for code in codes
        }
        if any(not frame.index.equals(visible_calendar) for frame in visible_frames.values()):
            raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: U0 history incomplete")
        panel = core.build_panel(visible_frames, include_rsrs=False, calendar=visible_calendar)
        per_candidate_results = {cid: {} for cid in state}
        for period, h in FORWARD_WINDOWS.items():
            boundary = boundaries[period]
            candidate_dates = visible_calendar[
                (visible_calendar >= boundary.train_start)
                & (visible_calendar <= boundary.label_cutoff)
            ]
            labelled_sets = [
                set(frame.dropna(subset=[f"fwd{h}"]).index) for frame in panel.values()
            ]
            labelled = sorted(set.intersection(*labelled_sets)) if labelled_sets else []
            train_dates = [
                date for date in labelled if boundary.train_start <= date <= boundary.label_cutoff
            ]
            if len(train_dates) < MIN_TRAIN_DATES:
                raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: insufficient training")
            checks = baseline.assert_training_labels_realized(
                calendar,
                candidate_dates,
                signal,
                h,
                len(codes),
            )
            origins = pd.DatetimeIndex(np.tile(train_dates, len(codes)))
            positions = calendar.get_indexer(origins)
            protocol.assert_training_chronology(origins, calendar[positions + h], signal)
            arrays = [
                panel[code]
                .loc[train_dates, list(baseline.EXPECTED_FEATURES) + [f"fwd{h}"]]
                .to_numpy(dtype=float)
                for code in codes
            ]
            stacked = np.vstack(arrays)
            x_train, raw_y = stacked[:, :-1], stacked[:, -1]
            x_predict = np.vstack(
                [
                    panel[code].loc[signal, list(baseline.EXPECTED_FEATURES)].to_numpy(dtype=float)
                    for code in codes
                ]
            )
            if (
                not np.isfinite(stacked).all()
                or not np.isfinite(x_predict).all()
                or len(train_dates) != len(candidate_dates)
                or len(stacked) != len(codes) * len(train_dates)
            ):
                raise ValueError(
                    "RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: silent sector/date exclusion"
                )
            endpoint = calendar[signal_i + h]
            if endpoint > label_calendar[-1]:
                raise ValueError("RESEARCH_PROTOCOL_VIOLATION: label endpoint beyond Purge 1")
            for cid, item in state.items():
                protocol.guard_iteration1_scope(
                    cid,
                    "development",
                    [ordinal],
                    supplied_hash=protocol.FROZEN_DEVELOPMENT_ITERATION1_PROTOCOL_HASH,
                )
                train, predict, target, diag = transform_candidate(
                    cid,
                    x_train,
                    x_predict,
                    raw_y,
                    origins,
                    h,
                )
                model = NumPyRidge(alpha=DEFAULT_ALPHA).fit(train, target)
                scores = {code: float(value) for code, value in zip(codes, model.predict(predict))}
                ranking = rank_sectors(scores)
                result = RankingResult(
                    period=period,
                    forward_days=h,
                    predict_date=signal,
                    train_start=boundary.train_start,
                    train_end=boundary.label_cutoff,
                    n_train_dates=len(train_dates),
                    n_train_samples=len(stacked),
                    scores=scores,
                )
                per_candidate_results[cid][period] = {
                    "result": result,
                    "scores": scores,
                    "ranking": ranking,
                }
                item["leakage_checks"] += checks
                item["training"].append(
                    {
                        "ordinal": ordinal,
                        "signal_date": signal_s,
                        "horizon": h,
                        "status": "success",
                        "reason": None,
                        "train_start": str(boundary.train_start.date()),
                        "label_cutoff": str(boundary.label_cutoff.date()),
                        "first_train_origin": str(train_dates[0].date()),
                        "last_train_origin": str(train_dates[-1].date()),
                        "last_train_label_end": str(
                            calendar[int(calendar.get_loc(train_dates[-1])) + h].date()
                        ),
                        "training_candidate_days": len(candidate_dates),
                        "training_valid_days": len(train_dates),
                        "training_observations": len(stacked),
                        "valid_sector_count": len(scores),
                        "missing_factor_exclusions": 0,
                        "missing_label_exclusions": 0,
                        "numerical_failures": 0,
                        "leakage_checks": checks,
                    }
                )
                if diag["scaler"] is not None:
                    item["scalers"].append({"ordinal": ordinal, "horizon": h, **diag["scaler"]})
                if diag["demean_residual_max_abs_mean"] is not None:
                    item["targets"].append(
                        {
                            "ordinal": ordinal,
                            "horizon": h,
                            "training_dates": len(train_dates),
                            "max_abs_mean": diag["demean_residual_max_abs_mean"],
                        }
                    )
        for cid, item in state.items():
            results = per_candidate_results[cid]
            fused = core.model.fuse_periods({p: result["result"] for p, result in results.items()})
            if len(fused) != len(codes):
                raise ValueError("RESEARCH_PROTOCOL_VIOLATION: incomplete fused U0")
            top = {code for code, _ in fused[:DEFAULT_TOP_N]}
            fused_lookup = dict(fused)
            fused_rank = {code: i for i, (code, _) in enumerate(fused, 1)}
            horizon_scores, horizon_labels = {}, {}
            for period, h in FORWARD_WINDOWS.items():
                result = results[period]
                horizon_scores[h] = result["scores"]
                rank = {code: i for i, (code, _) in enumerate(result["ranking"], 1)}
                diag = item["training"][-len(FORWARD_WINDOWS) + list(FORWARD_WINDOWS).index(period)]
                realized = {}
                for code in codes:
                    value = labels[h][code].get(signal, np.nan)
                    if pd.isna(value) or not np.isfinite(value):
                        raise ValueError(
                            "RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: missing realized label"
                        )
                    realized[code] = float(value)
                    item["predictions"].append(
                        {
                            "ordinal": ordinal,
                            "signal_date": signal_s,
                            "sector_code": code,
                            "sector_name": names[code],
                            "horizon": h,
                            "prediction_score": result["scores"][code],
                            "cross_sectional_rank": rank[code],
                            "fused_score": fused_lookup[code],
                            "fused_rank": fused_rank[code],
                            "top5": code in top,
                            "realized_forward_return": realized[code],
                            "label_end": str(calendar[signal_i + h].date()),
                            "exclusion_reason": None,
                            "training_observations": diag["training_observations"],
                            "training_valid_days": diag["training_valid_days"],
                            "training_label_cutoff": diag["label_cutoff"],
                        }
                    )
                horizon_labels[h] = realized
            item["per_date"].extend(
                baseline.evaluate_date(
                    ordinal,
                    signal_s,
                    codes,
                    horizon_scores,
                    fused,
                    horizon_labels,
                )
            )
    outputs = {}
    for cid, item in state.items():
        predictions = pd.DataFrame(item["predictions"], columns=baseline.PREDICTION_COLUMNS)
        per_date = pd.DataFrame(item["per_date"], columns=baseline.PER_DATE_COLUMNS)
        training = pd.DataFrame(item["training"], columns=baseline.TRAINING_COLUMNS)
        if len(predictions) != 100 * 124 * 3 or len(per_date) != 1500 or len(training) != 300:
            raise ValueError("RESEARCH_PROTOCOL_VIOLATION: candidate grid incomplete")
        outputs[cid] = baseline.DevelopmentOutput(
            predictions=predictions,
            per_date_metrics=per_date,
            aggregate_metrics=baseline.aggregate_metrics(per_date),
            training_diagnostics=training,
            data_quality_diagnostics={
                "attempted_development_dates": 100,
                "successful_dates": 100,
                "skipped_dates": [],
                "excluded_sector_date_horizon_rows": [],
                "training_excluded_sector_date_horizon_rows": [],
                "missing_factor_exclusions": 0,
                "missing_label_exclusions": 0,
                "numerical_failures": 0,
                "insufficient_training_cases": 0,
                "source_invalid_total_in_snapshot": invalid_total,
                "source_invalid_interactions_with_development": invalid_in_window,
                "training_observation_leakage_checks": item["leakage_checks"],
                "training_label_end_after_signal_count": 0,
            },
            metadata={
                "research_label": "SECTOR_INDEX_RESEARCH_ONLY",
                "phase": "DEVELOPMENT",
                "executable": False,
                "strict_pit": False,
                "synthetic_portfolio_enabled": False,
                "candidate_id": cid,
            },
        )
        outputs[cid].metadata["transformation_diagnostics"] = {
            "zero_std_feature_occurrences": sum(
                len(row["zero_std_features"]) for row in item["scalers"]
            ),
            "scaler_diagnostic_hash": hashlib.sha256(
                baseline._json_bytes(item["scalers"])
            ).hexdigest()
            if item["scalers"]
            else None,
            "target_diagnostic_hash": hashlib.sha256(
                baseline._json_bytes(item["targets"])
            ).hexdigest()
            if item["targets"]
            else None,
            "demean_residual_max_abs_mean": max(
                (row["max_abs_mean"] for row in item["targets"]), default=None
            ),
            "scaler_diagnostics": item["scalers"],
            "target_diagnostics": item["targets"],
        }
    return outputs


def comparison(aggregates: dict[str, dict]) -> dict:
    if tuple(aggregates) != protocol.FROZEN_CANDIDATE_IDS:
        raise ValueError("ITERATION1_CANDIDATE_BUDGET_VIOLATION")
    rows = []
    for cid, metrics in aggregates.items():
        if set(metrics) != set(prediction_metric_contract()["metric_names"]):
            raise ValueError("RESEARCH_PROTOCOL_VIOLATION: metric set changed")
        means = {name: stats["mean"] for name, stats in metrics.items()}
        rankic = protocol.weighted_rankic(means)
        spread = protocol.weighted_spread(means)
        eligible = protocol.eligible_for_further_review(rankic, spread)
        rows.append(
            {
                "candidate": cid,
                "Weighted_RankIC": rankic,
                "Weighted_Spread": spread,
                **{f"RankIC_{h}": means[f"RankIC_{h}"] for h in FORWARD_WINDOWS.values()},
                **{
                    f"Spread_{h}": means[f"Top5_minus_universe_{h}"]
                    for h in FORWARD_WINDOWS.values()
                },
                "promotion_status": "DEVELOPMENT_CANDIDATE_FOR_FURTHER_REVIEW"
                if eligible
                else "NOT PROMOTED",
            }
        )
    rows.sort(
        key=lambda row: (
            row["Weighted_RankIC"] is None,
            -(row["Weighted_RankIC"] or 0.0),
            -(row["Weighted_Spread"] or 0.0),
            row["candidate"],
        )
    )
    priority = [
        row["candidate"]
        for row in rows
        if row["promotion_status"] == "DEVELOPMENT_CANDIDATE_FOR_FURTHER_REVIEW"
    ]
    return {
        "comparison": rows,
        "review_priority": priority,
        "promotion_result": priority if priority else "NO_ITERATION1_CANDIDATE_PROMOTED",
    }


def write_run(
    root: Path,
    gate: dict,
    d0_source: Path,
    outputs: dict[str, baseline.DevelopmentOutput],
    repeat_of: Path | None = None,
) -> Path:
    if tuple(["D0", *outputs]) != protocol.FROZEN_CANDIDATE_IDS:
        raise ValueError("ITERATION1_CANDIDATE_BUDGET_VIOLATION")
    control_hashes = verify_d0_control(d0_source)
    run_id = datetime.now(timezone.utc).strftime("iteration1_%Y%m%d_%H%M%S_%f_utc")
    root.mkdir(parents=True, exist_ok=True)
    target = root / run_id
    target.mkdir(exist_ok=False)
    aggregates = {}
    content_hashes = {}
    for cid in protocol.FROZEN_CANDIDATE_IDS:
        folder = target / cid
        folder.mkdir()
        if cid == "D0":
            for name in ARTIFACT_NAMES:
                shutil.copyfile(d0_source / name, folder / name)
                if hashlib.sha256((folder / name).read_bytes()).hexdigest() != control_hashes[name]:
                    raise ValueError("D0_CONTROL_REPRODUCTION_BLOCKER: copied artifact")
            long = pd.read_csv(folder / "predictions.csv", dtype={"sector_code": str})
            transform = {
                "zero_std_feature_occurrences": 0,
                "scaler_diagnostic_hash": None,
                "target_diagnostic_hash": None,
                "demean_residual_max_abs_mean": None,
            }
        else:
            result = outputs[cid]
            payloads = {
                "predictions.csv": baseline._csv_bytes(result.predictions),
                "per_date_metrics.csv": baseline._csv_bytes(result.per_date_metrics),
                "aggregate_metrics.json": baseline._json_bytes(result.aggregate_metrics),
                "training_diagnostics.csv": baseline._csv_bytes(result.training_diagnostics),
                "data_quality_diagnostics.json": baseline._json_bytes(
                    result.data_quality_diagnostics
                ),
            }
            for name, data in payloads.items():
                (folder / name).write_bytes(data)
            long = result.predictions
            transform = result.metadata["transformation_diagnostics"]
        (folder / "per_date_predictions.csv").write_bytes(baseline._csv_bytes(long_to_wide(long)))
        (folder / "transformation_diagnostics.json").write_bytes(baseline._json_bytes(transform))
        aggregates[cid] = json.loads(
            (folder / "aggregate_metrics.json").read_text(encoding="utf-8")
        )
        content_hashes[cid] = {
            name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
            for name in (
                *ARTIFACT_NAMES,
                "per_date_predictions.csv",
                "transformation_diagnostics.json",
            )
        }
    summary = comparison(aggregates)
    summary["all_candidate_aggregate_metrics"] = aggregates
    summary["d0_control_sha256"] = control_hashes
    (target / "candidate_summary.json").write_bytes(baseline._json_bytes(summary))
    content_hashes["candidate_summary.json"] = hashlib.sha256(
        (target / "candidate_summary.json").read_bytes()
    ).hexdigest()
    metadata = {
        "research_label": "SECTOR_INDEX_RESEARCH_ONLY",
        "phase": "DEVELOPMENT",
        "iteration": 1,
        "candidate_family": list(protocol.FROZEN_CANDIDATE_IDS),
        "candidate_family_size": 4,
        "new_candidate_count": 3,
        "executable": False,
        "strict_pit": False,
        "classification_admission": "FIXED_CLASSIFICATION_RESEARCH",
        "split_policy_hash": baseline.EXPECTED_SPLIT_HASH,
        "prediction_config_hash": baseline.EXPECTED_PREDICTION_HASH,
        "development_iteration1_protocol_hash": protocol.FROZEN_DEVELOPMENT_ITERATION1_PROTOCOL_HASH,
        "synthetic_portfolio_config_hash": None,
        "sector_snapshot_id": baseline.EXPECTED_SNAPSHOT,
        "validation_access": "SEALED",
        "final_oos_access": "SEALED",
        "etf_execution": "DISABLED",
        "level_b": "DISABLED",
        "synthetic_portfolio": "DISABLED",
        "development_ordinals": [1, 100],
        "run_id": run_id,
        "branch": gate["branch"],
        "git_head": gate["git_head"],
        "starting_head": STARTING_HEAD,
        "docker_image_id": gate["docker_image_id"],
        "environment_changed": False,
        "baseline_control_run_id": BASELINE_RUN_ID,
        "baseline_aggregate_sha256": BASELINE_AGGREGATE_SHA256,
        "content_sha256": content_hashes,
        "notices": [
            "DEVELOPMENT ONLY",
            "NON-EXECUTABLE",
            "NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST",
            "NOT VALIDATED",
            "NOT TRADABLE",
            "NOT LEVEL B",
        ],
    }
    if repeat_of is not None:
        previous = json.loads((repeat_of / "metadata.json").read_text(encoding="utf-8"))
        if (
            previous["content_sha256"] != content_hashes
            or previous["development_iteration1_protocol_hash"]
            != metadata["development_iteration1_protocol_hash"]
        ):
            raise ValueError("ITERATION1_DETERMINISM_BLOCKER")
        metadata["determinism_repeat_of"] = previous["run_id"]
        metadata["determinism"] = "PASS_CONTENT_SHA256_IDENTICAL"
    (target / "metadata.json").write_bytes(baseline._json_bytes(metadata))
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker-image-id", required=True)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/shenwan"))
    parser.add_argument(
        "--output-root", type=Path, default=Path("reports/research/shenwan_sector_index")
    )
    parser.add_argument("--repeat-of", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    repo_dir = Path(__file__).resolve().parents[1]
    gate = pre_run_gate(args.processed_dir, repo_dir, args.docker_image_id)
    source = args.output_root / BASELINE_RUN_ID
    verify_d0_control(source)
    print("ITERATION-1 PRE-RUN GATE", flush=True)
    print(json.dumps(gate, sort_keys=True, ensure_ascii=False, indent=2), flush=True)
    if not args.execute:
        return 0
    outputs = compute_candidates(args.processed_dir, gate)
    target = write_run(args.output_root, gate, source, outputs, args.repeat_of)
    print(f"ITERATION-1 RUN COMPLETE: {target}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
