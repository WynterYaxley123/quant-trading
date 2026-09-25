"""Development-only replay diagnostics under the frozen Alpha Stability V1 protocol.

No new candidate or trading score is produced. Existing formal V2 predictions
are an identity reference, not a target for model selection.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research import alpha_stability_regime_audit_v1_protocol as protocol
from research import development_iteration1_protocol as iteration1
from research import factor_alpha_audit_v1_protocol as factor_audit
from research import factor_alpha_audit_v1_run as factor_run
from research import sector_development_baseline as baseline
from research.sector_development_protocol import audit_local_policy, guard_evaluation_dates, verify_frozen_prefix
from research.sector_index_baseline import FEATURE_WARMUP
from strategies.sw_sector_rotation.src.common.temporal_integrity import make_forward_label
from strategies.sw_sector_rotation.src.factors.sector_rotation import compute_all_price_features
from strategies.sw_sector_rotation.src.model.model import DEFAULT_ALPHA, FORWARD_WINDOWS, MIN_TRAIN_DATES, NumPyRidge
from strategies.sw_sector_rotation.src.strategy import SWSectorRotationConfig, SWSectorRotationCore

AUDIT_TYPE = protocol.AUDIT_TYPE
SOURCE_V2_RUN = "factor_set_v2_20260925_090958_520718_utc"
SOURCE_D0_RUN = "iteration1_20260924_163607_787266_utc"
EXPECTED_BRANCH = baseline.EXPECTED_BRANCH
FACTOR_SAMPLE_ORDINALS = (1, 50, 100)
WINDOW_SAMPLE_ORDINALS = (1, 25, 50, 75, 100)
IDENTITY_SECTORS = 10
FLOAT_TOLERANCE = 1e-10

TABLE_NAMES = (
    "factor_transfer_daily.csv", "factor_transfer_summary.csv",
    "factor_transfer_transition.csv", "factor_rankic_autocorrelation.csv",
    "factor_block_transfer.csv", "coefficient_daily.csv",
    "coefficient_stability_summary.csv", "coefficient_alignment_summary.csv",
    "contribution_daily_summary.csv", "contribution_sector_daily.csv",
    "contribution_factor_summary.csv", "contribution_correlation.csv",
    "contribution_block_summary.csv", "horizon_stability_summary.csv",
)


@dataclass(frozen=True)
class AuditResult:
    tables: dict[str, pd.DataFrame]
    summary: dict
    identities: dict
    context: dict


def _optional_mean(values) -> float | None:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.mean(arr)) if len(arr) else None


def _optional_corr(left, right, *, spearman: bool = False) -> float | None:
    x, y = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    valid = np.isfinite(x) & np.isfinite(y)
    if valid.sum() < 2:
        return None
    x, y = x[valid], y[valid]
    if spearman:
        x = pd.Series(x).rank(method="average").to_numpy(dtype=float)
        y = pd.Series(y).rank(method="average").to_numpy(dtype=float)
    if np.std(x) == 0 or np.std(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def _stats(values) -> dict:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if not len(arr):
        return {name: None for name in ("mean", "median", "std", "min", "max")}
    return {"mean": float(np.mean(arr)), "median": float(np.median(arr)),
            "std": float(np.std(arr, ddof=0)), "min": float(np.min(arr)),
            "max": float(np.max(arr))}


def _sign(value: float) -> int:
    return int(np.sign(value))


def _adjacent_sign_stats(values) -> tuple[int, float | None]:
    signs = [_sign(float(value)) for value in values if pd.notna(value)]
    pairs = list(zip(signs, signs[1:]))
    if not pairs:
        return 0, None
    changes = sum(a != b for a, b in pairs)
    return changes, 1.0 - changes / len(pairs)


def transition_matrix_rows(paired: pd.DataFrame, factor: str, horizon: int) -> list[dict]:
    """Fixed 3×3 matrix, including zero-count cells in registered order."""
    classes = ("POSITIVE", "NEUTRAL", "NEGATIVE")
    return [{"factor": factor, "horizon": horizon,
             "train_direction": train_class, "evaluation_direction": eval_class,
             "count": int(((paired["train_direction"] == train_class)
                           & (paired["evaluation_direction"] == eval_class)).sum())}
            for train_class, eval_class in itertools.product(classes, repeat=2)]


def cancellation_ratio(centered_row: np.ndarray) -> float:
    denominator = float(np.abs(centered_row).sum())
    return float(np.clip(1.0 - abs(float(np.sum(centered_row))) /
                         (denominator + protocol.CANCELLATION_EPS), 0.0, 1.0))


def diversification_ratio(centered_matrix: np.ndarray) -> float:
    components = np.std(centered_matrix, axis=0, ddof=0)
    return float(np.std(centered_matrix.sum(axis=1), ddof=0) /
                 (float(components.sum()) + protocol.CANCELLATION_EPS))


def _read_v2_reference(root: Path) -> tuple[dict, dict]:
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    if (metadata.get("protocolHash") != "3fbba8e5b41c0b5b839dab2788f1e000b9add95406bb14cbaf4c13f31664b4f4"
            or metadata.get("candidateIds") != list(protocol.SCHEMES)
            or metadata.get("phase") != "DEVELOPMENT"):
        raise ValueError("V2_REFERENCE_IDENTITY_BLOCKER")
    predictions, diagnostics = {}, {}
    for scheme in protocol.SCHEMES:
        predictions[scheme] = pd.read_csv(root / scheme / "predictions.csv", dtype={"sector_code": str})
        diagnostics[scheme] = pd.read_csv(root / scheme / "training_diagnostics.csv")
        for name in ("predictions.csv", "training_diagnostics.csv", "per_date_metrics.csv"):
            rel = f"{scheme}/{name}"
            if hashlib.sha256((root / rel).read_bytes()).hexdigest() != metadata["content_sha256"][rel]:
                raise ValueError("V2_REFERENCE_ARTIFACT_HASH_BLOCKER: " + rel)
    return predictions, diagnostics


def pre_run_gate(repo_dir: Path, processed_dir: Path, v2_root: Path,
                 image_id: str, prereg_commit: str) -> dict:
    protocol.verify_protocol(repo_dir)
    if image_id != baseline.EXPECTED_IMAGE_ID:
        raise ValueError("ENVIRONMENT_STABILITY_BLOCKER")
    branch = baseline._git(repo_dir, "branch", "--show-current")
    head = baseline._git(repo_dir, "rev-parse", "HEAD")
    if branch != EXPECTED_BRANCH or baseline._git(repo_dir, "status", "--porcelain"):
        raise ValueError("RESEARCH_WORKTREE_DIRTY_BLOCKER")
    if head != prereg_commit:
        raise ValueError("ALPHA_STABILITY_PREREGISTRATION_COMMIT_MISMATCH")
    baseline._git(repo_dir, "merge-base", "--is-ancestor", prereg_commit, head)
    if baseline._git(repo_dir, "diff", "--name-only", prereg_commit, "HEAD", "--",
                     "docs/research/shenwan_alpha_stability_regime_audit_v1.md",
                     protocol.CONFIG_RELPATH,
                     "research/alpha_stability_regime_audit_v1_protocol.py"):
        raise ValueError("ALPHA_STABILITY_PROTOCOL_HASH_DRIFT_BLOCKER")
    audit = audit_local_policy(processed_dir)
    dev = audit["availability"]["development"]
    if (audit["split_policy_hash"] != baseline.EXPECTED_SPLIT_HASH
            or audit["prediction_config_hash"] != baseline.EXPECTED_PREDICTION_HASH
            or audit["data_snapshot_id"] != baseline.EXPECTED_SNAPSHOT
            or dev["available_count"] != 100
            or (dev["available_start"], dev["available_end"]) != baseline.EXPECTED_DEVELOPMENT_DATES
            or audit["validation_status"] != "LOCKED_PARTIALLY_AVAILABLE_UNOPENED"
            or audit["oos_performance_status"] != "UNOPENED"):
        raise ValueError("SEALED_OR_NON_DEVELOPMENT_ACCESS_BLOCKER")
    v2_meta = json.loads((v2_root / "metadata.json").read_text(encoding="utf-8"))
    if v2_meta.get("sectorSnapshotId") != baseline.EXPECTED_SNAPSHOT:
        raise ValueError("V2_REFERENCE_IDENTITY_BLOCKER")
    return {"gate": "PASS", "branch": branch, "gitCommit": head,
            "preregistrationCommit": prereg_commit, "protocolHash": protocol.FROZEN_PROTOCOL_HASH,
            "dockerImageId": image_id, "sectorSnapshotId": baseline.EXPECTED_SNAPSHOT,
            "splitPolicyHash": baseline.EXPECTED_SPLIT_HASH,
            "firstDate": dev["available_start"], "lastDate": dev["available_end"],
            "labelTailEnd": audit["development_last_120_label_endpoint"],
            "validation": "SEALED", "finalOos": "SEALED", "environmentChanged": False}


def assert_formal_result_state(output_root: Path, repeat_of: Path | None = None) -> None:
    """First execution must be result-free; only its exact rerun is allowed."""
    if not output_root.exists():
        if repeat_of is not None:
            raise ValueError("PREREGISTRATION_RESULT_LEAK_BLOCKER: rerun source absent")
        return
    existing = sorted(p.resolve() for p in output_root.iterdir()
                      if p.is_dir() and p.name.startswith("alpha_stability_regime_audit_"))
    allowed = [repeat_of.resolve()] if repeat_of is not None else []
    if existing != allowed:
        raise ValueError(f"PREREGISTRATION_RESULT_LEAK_BLOCKER: {existing}")


def _training_relationship(x: np.ndarray, y: np.ndarray, train_dates,
                           horizon: int, cache: dict) -> list[dict]:
    """x: legal dates × fixed sectors × frozen factors; y: dates × sectors."""
    per_date = []
    for d, date in enumerate(train_dates):
        key = (str(date.date()), horizon)
        if key not in cache:
            cache[key] = [factor_audit.cross_sectional_ic(x[d, :, j], y[d],
                                                           min_pairs=protocol.MIN_PAIRS)
                          for j in range(len(protocol.FACTOR_ORDER))]
        per_date.append(cache[key])
    results = []
    for factor_index in range(len(protocol.FACTOR_ORDER)):
        daily = [per_date[d][factor_index] for d in range(len(x))]
        valid = [item for item in daily if not item["skipped"]]
        results.append({"train_mean_ic": _optional_mean([r["ic"] for r in valid]),
                        "train_median_ic": float(np.median([r["ic"] for r in valid])) if valid else None,
                        "train_mean_rankic": _optional_mean([r["rankic"] for r in valid]),
                        "train_median_rankic": float(np.median([r["rankic"] for r in valid])) if valid else None,
                        "train_valid_dates": len(valid)})
    return results


def legal_training_dates(panel: dict, visible_calendar: pd.DatetimeIndex,
                         boundary, horizon: int) -> tuple[list, list]:
    """Exact V2 labelled intersection, within the core's temporal boundary."""
    candidates = visible_calendar[
        (visible_calendar >= boundary.train_start)
        & (visible_calendar <= boundary.label_cutoff)]
    labelled_sets = [set(frame.dropna(subset=[f"fwd{horizon}"]).index)
                     for frame in panel.values()]
    labelled = sorted(set.intersection(*labelled_sets)) if labelled_sets else []
    train_dates = [date for date in labelled
                   if boundary.train_start <= date <= boundary.label_cutoff]
    return list(candidates), train_dates


def _coefficient_contributions(scheme: str, ordinal: int, signal: str, horizon: int,
                               factors: tuple[str, ...], x_train: np.ndarray,
                               x_predict: np.ndarray, target: np.ndarray,
                               reference: dict[tuple[int, int, str], float],
                               codes: list[str]) -> tuple[list[dict], list[dict], list[dict], list[dict], float, float]:
    model = NumPyRidge(alpha=DEFAULT_ALPHA).fit(x_train, target)
    beta = np.asarray(model.coef_, dtype=float)
    prediction = model.predict(x_predict)
    difference = max(abs(float(prediction[i]) - reference[(ordinal, horizon, code)])
                     for i, code in enumerate(codes))
    if difference > FLOAT_TOLERANCE:
        raise ValueError("RIDGE_COEFFICIENT_IDENTITY_BLOCKER")
    centered = (x_predict - np.mean(x_predict, axis=0)) * beta
    reconstruction = float(np.max(np.abs(centered.sum(axis=1) - (prediction - np.mean(prediction)))))
    if reconstruction > FLOAT_TOLERANCE:
        raise ValueError("CONTRIBUTION_IDENTITY_BLOCKER")
    feature_std = np.std(x_train, axis=0, ddof=0)
    absolute = np.abs(centered)
    all_abs = float(absolute.sum())
    component_std = np.std(centered, axis=0, ddof=0)
    diversification = diversification_ratio(centered)
    coeff_rows, factor_rows, sector_rows, corr_rows = [], [], [], []
    for j, factor in enumerate(factors):
        coeff_rows.append({"scheme": scheme, "ordinal": ordinal, "signal_date": signal,
                           "horizon": horizon, "factor": factor, "beta": float(beta[j]),
                           "training_feature_std": float(feature_std[j]),
                           "scale_adjusted_beta": float(beta[j] * feature_std[j])})
        factor_rows.append({"scheme": scheme, "ordinal": ordinal, "signal_date": signal,
                            "horizon": horizon, "block": protocol.block_id(ordinal),
                            "factor": factor,
                            "contribution_std": float(component_std[j]),
                            "mean_abs_contribution": float(np.mean(absolute[:, j])),
                            "absolute_share": float(absolute[:, j].sum() / all_abs) if all_abs > 0 else None})
    if all_abs > 0 and abs(sum(row["absolute_share"] for row in factor_rows) - 1.0) > 1e-12:
        raise ValueError("CONTRIBUTION_IDENTITY_BLOCKER: shares")
    for i, code in enumerate(codes):
        denominator = float(absolute[i].sum())
        cancellation = cancellation_ratio(centered[i])
        sector_rows.append({"scheme": scheme, "ordinal": ordinal, "signal_date": signal,
                            "horizon": horizon, "block": protocol.block_id(ordinal),
                            "sector_code": code,
                            "absolute_component_sum": denominator,
                            "cancellation_ratio": cancellation,
                            "total_centered_prediction": float(centered[i].sum())})
    if scheme != "V2_A":
        for a, b in itertools.product(range(len(factors)), repeat=2):
            corr_rows.append({"scheme": scheme, "ordinal": ordinal, "horizon": horizon,
                              "factor_a": factors[a], "factor_b": factors[b],
                              "spearman": protocol.cross_sectional_spearman(centered[:, a], centered[:, b])})
    for row in factor_rows:
        row["diversification_ratio"] = diversification
    return coeff_rows, factor_rows, sector_rows, corr_rows, difference, reconstruction


def compute_audit(processed_dir: Path, v2_root: Path, d0_root: Path, gate: dict) -> AuditResult:
    """Replay only the frozen Development grid, with V2 as an identity oracle."""
    if gate.get("gate") != "PASS" or gate.get("validation") != "SEALED":
        raise ValueError("SEALED_OR_NON_DEVELOPMENT_ACCESS_BLOCKER")
    protocol.verify_protocol()
    source_predictions, source_diagnostics = _read_v2_reference(v2_root)
    reference = {
        scheme: {(int(r.ordinal), int(r.horizon), str(r.sector_code)): float(r.prediction_score)
                 for r in frame.itertuples(index=False)}
        for scheme, frame in source_predictions.items()
    }
    diagnostic_ref = {
        (int(row.ordinal), int(row.horizon)): row
        for row in source_diagnostics["C0"].itertuples(index=False)
    }
    audit = audit_local_policy(processed_dir)
    codes, names, calendar, frames, invalid, _ = baseline._verified_market(
        processed_dir, audit["development_last_120_label_endpoint"])
    if invalid or len(codes) != 124:
        raise ValueError("FACTOR_IDENTITY_BLOCKER: fixed U0 is not complete")
    eligible = calendar[
        (calendar >= pd.Timestamp(audit["availability"]["development"]["available_start"]))
        & (calendar <= pd.Timestamp("2026-03-27"))
    ]
    verify_frozen_prefix(eligible, codes)
    dates = eligible[:100]
    ordinals = guard_evaluation_dates("development", dates, eligible)
    protocol.guard_scope("development", ordinals)
    if (ordinals != list(range(1, 101))
            or (str(dates[0].date()), str(dates[-1].date())) != baseline.EXPECTED_DEVELOPMENT_DATES):
        raise ValueError("SEALED_OR_NON_DEVELOPMENT_ACCESS_BLOCKER: date identity")
    label_calendar = calendar[calendar <= pd.Timestamp(audit["development_last_120_label_endpoint"])]
    labels_expost = {h: {code: make_forward_label(frames[code]["close"], h,
                                                  calendar=label_calendar) for code in codes}
                     for h in protocol.HORIZONS}
    core = SWSectorRotationCore(SWSectorRotationConfig())
    if tuple(core.feature_names) != protocol.FACTOR_ORDER:
        raise ValueError("FACTOR_IDENTITY_BLOCKER: factor order")
    factor_matrix = np.empty((100, 124, 19), dtype=float)
    label_matrix = {h: np.empty((100, 124), dtype=float) for h in protocol.HORIZONS}
    rows = {"factor_transfer_daily.csv": [], "coefficient_daily.csv": [],
            "contribution_daily_summary.csv": [], "contribution_sector_daily.csv": [],
            "contribution_correlation_daily": []}
    cache: dict = {}
    train_identity_cases = 0
    prediction_count = 0
    max_prediction_diff = 0.0
    max_contribution_diff = 0.0
    for date_index, (ordinal, signal) in enumerate(zip(ordinals, dates)):
        protocol.guard_scope("development", [ordinal])
        signal_s = str(signal.date())
        signal_i = int(calendar.get_loc(signal))
        boundaries = {period: core.boundaries(calendar[:signal_i + 1], signal, period)
                      for period in FORWARD_WINDOWS}
        if any(boundary is None for boundary in boundaries.values()):
            raise ValueError("TRAINING_WINDOW_IDENTITY_BLOCKER: boundary missing")
        first_train_i = int(calendar.searchsorted(min(b.train_start for b in boundaries.values())))
        warmup_i = first_train_i - FEATURE_WARMUP
        if warmup_i < 0:
            raise ValueError("FACTOR_IDENTITY_BLOCKER: warmup unavailable")
        visible_calendar = calendar[warmup_i:signal_i + 1]
        visible_frames = {code: baseline._source_frame(frames[code], calendar[warmup_i], signal)
                          for code in codes}
        if any(not frame.index.equals(visible_calendar) for frame in visible_frames.values()):
            raise ValueError("FACTOR_IDENTITY_BLOCKER: U0 history incomplete")
        panel = core.build_panel(visible_frames, include_rsrs=False, calendar=visible_calendar)
        x_predict_all = np.vstack([
            panel[code].loc[signal, list(protocol.FACTOR_ORDER)].to_numpy(dtype=float)
            for code in codes])
        factor_matrix[date_index] = x_predict_all
        for period, horizon in FORWARD_WINDOWS.items():
            boundary = boundaries[period]
            candidate_dates, train_dates = legal_training_dates(
                panel, visible_calendar, boundary, horizon)
            if len(train_dates) < MIN_TRAIN_DATES or len(train_dates) != len(candidate_dates):
                raise ValueError("TRAINING_WINDOW_IDENTITY_BLOCKER: legal dates")
            baseline.assert_training_labels_realized(calendar, candidate_dates, signal,
                                                     horizon, len(codes))
            expected = diagnostic_ref[(ordinal, horizon)]
            expected_fields = (str(expected.train_start), str(expected.label_cutoff),
                               str(expected.first_train_origin), str(expected.last_train_origin),
                               int(expected.training_valid_days), int(expected.training_observations))
            actual_fields = (str(boundary.train_start.date()), str(boundary.label_cutoff.date()),
                             str(train_dates[0].date()), str(train_dates[-1].date()),
                             len(train_dates), len(train_dates) * len(codes))
            if expected_fields != actual_fields:
                raise ValueError("TRAINING_WINDOW_IDENTITY_BLOCKER: V2 diagnostic mismatch")
            if ordinal in WINDOW_SAMPLE_ORDINALS:
                frozen = core.run_period(period, panel, visible_calendar, signal)
                if frozen is None or list(frozen["train_dates"]) != train_dates:
                    raise ValueError("TRAINING_WINDOW_IDENTITY_BLOCKER: core date set mismatch")
                train_identity_cases += 1
            x_by_date = np.stack([
                panel[code].loc[train_dates, list(protocol.FACTOR_ORDER)].to_numpy(dtype=float)
                for code in codes], axis=1)
            y_by_date = np.stack([
                panel[code].loc[train_dates, f"fwd{horizon}"].to_numpy(dtype=float)
                for code in codes], axis=1)
            if not (np.isfinite(x_by_date).all() and np.isfinite(y_by_date).all()
                    and np.isfinite(x_predict_all).all()):
                raise ValueError("FACTOR_IDENTITY_BLOCKER: missing model inputs")
            training_relation = _training_relationship(
                x_by_date, y_by_date, train_dates, horizon, cache)
            label_vector = np.asarray([labels_expost[horizon][code].get(signal, np.nan)
                                       for code in codes], dtype=float)
            label_matrix[horizon][date_index] = label_vector
            if not np.isfinite(label_vector).all():
                raise ValueError("TARGET_IDENTITY_BLOCKER: missing endpoint")
            evaluation_relation = [factor_audit.cross_sectional_ic(
                x_predict_all[:, j], label_vector, min_pairs=protocol.MIN_PAIRS)
                for j in range(len(protocol.FACTOR_ORDER))]
            relation_lookup = {}
            for j, factor in enumerate(protocol.FACTOR_ORDER):
                train, evaluation = training_relation[j], evaluation_relation[j]
                a, b = train["train_mean_rankic"], evaluation["rankic"]
                relation_lookup[factor] = (a, b)
                rows["factor_transfer_daily.csv"].append({
                    "ordinal": ordinal, "signal_date": signal_s, "block": protocol.block_id(ordinal),
                    "factor": factor, "horizon": horizon, **train,
                    "evaluation_ic": evaluation["ic"], "evaluation_rankic": b,
                    "evaluation_valid_pairs": evaluation["valid_pairs"],
                    "train_direction": protocol.direction(a),
                    "evaluation_direction": protocol.direction(b),
                    "raw_sign_agreement": protocol.raw_sign_agreement(a, b),
                    "hard_flip": protocol.hard_flip(a, b),
                })
            x_train_all = x_by_date.transpose(1, 0, 2).reshape(-1, len(protocol.FACTOR_ORDER))
            raw_y = y_by_date.T.reshape(-1)
            origins = pd.DatetimeIndex(np.tile(train_dates, len(codes)))
            target = iteration1.cross_sectional_excess_training_target(raw_y, origins,
                                                                          horizon=horizon)
            if any(abs(float(target[origins == d].mean())) > 1e-12 for d in train_dates):
                raise ValueError("TARGET_IDENTITY_BLOCKER: excess target residual")
            for scheme, factors in protocol.SCHEMES.items():
                indices = [protocol.FACTOR_ORDER.index(factor) for factor in factors]
                coeff, contributions, sectors, correlations, diff, reconstruction = (
                    _coefficient_contributions(
                        scheme, ordinal, signal_s, horizon, factors,
                        x_train_all[:, indices], x_predict_all[:, indices], target,
                        reference[scheme], codes))
                max_prediction_diff = max(max_prediction_diff, diff)
                max_contribution_diff = max(max_contribution_diff, reconstruction)
                prediction_count += len(codes)
                for row in coeff:
                    train_rankic, eval_rankic = relation_lookup[row["factor"]]
                    beta = row["beta"]
                    row["train_mean_rankic"] = train_rankic
                    row["evaluation_rankic"] = eval_rankic
                    row["beta_vs_train_sign_agreement"] = protocol.raw_sign_agreement(beta, train_rankic)
                    row["beta_vs_evaluation_sign_agreement"] = protocol.raw_sign_agreement(beta, eval_rankic)
                    row["beta_to_evaluation_hard_flip"] = protocol.beta_evaluation_hard_flip(beta, eval_rankic)
                rows["coefficient_daily.csv"].extend(coeff)
                rows["contribution_daily_summary.csv"].extend(contributions)
                rows["contribution_sector_daily.csv"].extend(sectors)
                rows["contribution_correlation_daily"].extend(correlations)
    if train_identity_cases != 15 or prediction_count != 100 * 3 * 4 * 124:
        raise ValueError("ALPHA_STABILITY_IDENTITY_GRID_BLOCKER")
    factor_identity = factor_run.factor_identity_gate(factor_matrix, frames, calendar, dates, codes)
    target_identity = factor_run.target_identity_gate(
        label_matrix, frames, calendar, dates, codes, d0_root)
    identities = {
        "trainingWindow": {"status": "PASS", "sampleCount": train_identity_cases,
                           "exactDateSets": True, "maxDifference": 0},
        "factor": factor_identity, "target": target_identity,
        "coefficient": {"status": "PASS", "predictionComparisons": prediction_count,
                        "maxAbsDiff": max_prediction_diff, "tolerance": FLOAT_TOLERANCE},
        "contribution": {"status": "PASS", "sectorComparisons": prediction_count,
                         "maxAbsDiff": max_contribution_diff, "tolerance": FLOAT_TOLERANCE},
    }
    tables = summarize_tables(rows, v2_root)
    context = {"firstDate": str(dates[0].date()), "lastDate": str(dates[-1].date()),
               "sectorCount": len(codes), "factorCount": len(protocol.FACTOR_ORDER),
               "trainingRelationCacheEntries": len(cache)}
    summary = build_summary(tables, identities, context)
    return AuditResult(tables=tables, summary=summary, identities=identities, context=context)


def summarize_tables(rows: dict, v2_root: Path) -> dict[str, pd.DataFrame]:
    """Fixed descriptive summaries; no search or promotion gate."""
    transfer = pd.DataFrame(rows["factor_transfer_daily.csv"])
    coefficient = pd.DataFrame(rows["coefficient_daily.csv"])
    contribution = pd.DataFrame(rows["contribution_daily_summary.csv"])
    sector = pd.DataFrame(rows["contribution_sector_daily.csv"])
    correlation_daily = pd.DataFrame(rows["contribution_correlation_daily"])
    expected = 100 * 19 * 3
    if (len(transfer) != expected or len(coefficient) != 100 * 3 * 28
            or len(contribution) != len(coefficient) or len(sector) != 100 * 3 * 4 * 124):
        raise ValueError("ALPHA_STABILITY_GRID_BLOCKER")
    transfer_summary, transitions, autocorr, blocks = [], [], [], []
    for (factor, horizon), group in transfer.groupby(["factor", "horizon"], sort=False):
        group = group.sort_values("ordinal")
        paired = group.dropna(subset=["train_mean_rankic", "evaluation_rankic"])
        x = paired["train_mean_rankic"].to_numpy(dtype=float)
        y = paired["evaluation_rankic"].to_numpy(dtype=float)
        evaluation = group["evaluation_rankic"].to_numpy(dtype=float)
        evaluation_stats = _stats(evaluation)
        raw_changes, _ = _adjacent_sign_stats(evaluation)
        classes = [c for c in group["evaluation_direction"] if pd.notna(c)]
        class_changes = sum(a != b for a, b in zip(classes, classes[1:]))
        transfer_summary.append({
            "factor": factor, "horizon": horizon, "valid_signal_dates": len(paired),
            "mean_train_rankic": _optional_mean(x),
            "median_train_rankic": float(np.median(x)) if len(x) else None,
            "mean_evaluation_rankic": _optional_mean(y),
            "median_evaluation_rankic": float(np.median(y)) if len(y) else None,
            "transfer_pearson": _optional_corr(x, y),
            "transfer_spearman": _optional_corr(x, y, spearman=True),
            "mean_absolute_transfer_error": float(np.mean(np.abs(y - x))) if len(x) else None,
            "mean_signed_transfer_delta": float(np.mean(y - x)) if len(x) else None,
            "raw_sign_agreement_rate": _optional_mean(paired["raw_sign_agreement"]),
            "hard_flip_count": int(paired["hard_flip"].sum()),
            "hard_flip_rate": _optional_mean(paired["hard_flip"]),
            "evaluation_std": evaluation_stats["std"],
            "evaluation_min": evaluation_stats["min"], "evaluation_max": evaluation_stats["max"],
            "evaluation_positive_dates": int((group["evaluation_direction"] == "POSITIVE").sum()),
            "evaluation_neutral_dates": int((group["evaluation_direction"] == "NEUTRAL").sum()),
            "evaluation_negative_dates": int((group["evaluation_direction"] == "NEGATIVE").sum()),
            "evaluation_raw_sign_changes": raw_changes,
            "evaluation_direction_changes": class_changes,
        })
        transitions.extend(transition_matrix_rows(paired, factor, horizon))
        for lag in protocol.LAGS:
            autocorr.append({"factor": factor, "horizon": horizon, "lag": lag,
                             "pearson_autocorrelation": protocol.lag_autocorrelation(
                                 evaluation.tolist(), lag),
                             "overlapping_labels": True, "descriptive_only": True})
        for name, first, last in protocol.BLOCKS:
            block = paired[(paired["ordinal"] >= first) & (paired["ordinal"] <= last)]
            blocks.append({"factor": factor, "horizon": horizon, "block": name,
                           "valid_dates": len(block),
                           "mean_train_rankic": _optional_mean(block["train_mean_rankic"]),
                           "mean_evaluation_rankic": _optional_mean(block["evaluation_rankic"]),
                           "median_evaluation_rankic": float(block["evaluation_rankic"].median()) if len(block) else None,
                           "raw_sign_agreement_rate": _optional_mean(block["raw_sign_agreement"]),
                           "hard_flip_rate": _optional_mean(block["hard_flip"])})
    coeff_summary, alignment = [], []
    for (scheme, horizon, factor), group in coefficient.groupby(
            ["scheme", "horizon", "factor"], sort=False):
        group = group.sort_values("ordinal")
        beta = group["beta"].to_numpy(dtype=float)
        adjusted = group["scale_adjusted_beta"].to_numpy(dtype=float)
        changes, persistence = _adjacent_sign_stats(beta)
        adjusted_changes, adjusted_persistence = _adjacent_sign_stats(adjusted)
        beta_stats, adjusted_stats = _stats(beta), _stats(adjusted)
        coeff_summary.append({
            "scheme": scheme, "horizon": horizon, "factor": factor, "valid_dates": len(group),
            "positive_coefficient_share": float(np.mean(beta > 0)),
            "negative_coefficient_share": float(np.mean(beta < 0)),
            "zero_coefficient_share": float(np.mean(beta == 0)),
            "sign_change_count": changes, "adjacent_sign_persistence_rate": persistence,
            **{f"beta_{key}": val for key, val in beta_stats.items()},
            **{f"scale_adjusted_beta_{key}": val for key, val in adjusted_stats.items()},
            "scale_adjusted_sign_persistence_rate": adjusted_persistence,
            "scale_adjusted_sign_changes": adjusted_changes,
            "scale_adjusted_median_abs_adjacent_change": float(np.median(np.abs(np.diff(adjusted)))) if len(adjusted) > 1 else None,
            "diagnostic_only": True,
        })
        alignment.append({
            "scheme": scheme, "horizon": horizon, "factor": factor,
            "valid_dates": len(group),
            "beta_vs_train_sign_agreement": _optional_mean(group["beta_vs_train_sign_agreement"]),
            "beta_vs_evaluation_sign_agreement": _optional_mean(group["beta_vs_evaluation_sign_agreement"]),
            "beta_to_evaluation_hard_flip_rate": _optional_mean(group["beta_to_evaluation_hard_flip"]),
        })
    factor_summary = []
    for (scheme, horizon, factor), group in contribution.groupby(
            ["scheme", "horizon", "factor"], sort=False):
        share = _stats(group["absolute_share"])
        dispersion = _stats(group["contribution_std"])
        factor_summary.append({
            "scheme": scheme, "horizon": horizon, "factor": factor,
            "valid_dates": len(group),
            **{f"share_{key}": val for key, val in share.items()},
            "mean_contribution_std": dispersion["mean"],
            "median_contribution_std": dispersion["median"],
            "mean_abs_contribution": _optional_mean(group["mean_abs_contribution"]),
        })
    block_rows = []
    block_groups = [(scheme, horizon, "ALL", group)
                    for (scheme, horizon), group in sector.groupby(
                        ["scheme", "horizon"], sort=False)]
    block_groups += [(scheme, horizon, name, group)
                     for (scheme, horizon, name), group in sector.groupby(
                         ["scheme", "horizon", "block"], sort=False)]
    for scheme, horizon, name, group in block_groups:
        cancel = _stats(group["cancellation_ratio"])
        day_values = contribution[
            (contribution["scheme"] == scheme) & (contribution["horizon"] == horizon)
            & ((contribution["block"] == name) if name != "ALL" else True)]
        day_values = day_values.drop_duplicates("ordinal")
        diversify = _stats(day_values["diversification_ratio"])
        block_rows.append({"scheme": scheme, "horizon": horizon, "block": name,
                           "sector_observations": len(group),
                           **{f"cancellation_{key}": value for key, value in cancel.items()},
                           **{f"diversification_{key}": value for key, value in diversify.items()}})
    correlation = []
    for (scheme, horizon, factor_a, factor_b), group in correlation_daily.groupby(
            ["scheme", "horizon", "factor_a", "factor_b"], sort=False):
        correlation.append({"scheme": scheme, "horizon": horizon,
                            "factor_a": factor_a, "factor_b": factor_b,
                            "valid_dates": int(group["spearman"].notna().sum()),
                            "mean_daily_spearman": _optional_mean(group["spearman"])})
    horizon_rows = []
    for scheme in protocol.SCHEMES:
        formal = pd.read_csv(v2_root / scheme / "per_date_metrics.csv")
        for horizon in protocol.HORIZONS:
            model = formal[formal["metric"] == f"RankIC_{horizon}"].sort_values("ordinal")
            if len(model) != 100:
                raise ValueError("V2_REFERENCE_IDENTITY_BLOCKER: model metric grid")
            subset = [row for row in transfer_summary if row["horizon"] == horizon]
            cancellation = sector[(sector["scheme"] == scheme) & (sector["horizon"] == horizon)]
            day = contribution[(contribution["scheme"] == scheme)
                               & (contribution["horizon"] == horizon)].drop_duplicates("ordinal")
            beta_rows = [row for row in coeff_summary
                         if row["scheme"] == scheme and row["horizon"] == horizon]
            align_rows = [row for row in alignment
                          if row["scheme"] == scheme and row["horizon"] == horizon]
            horizon_rows.append({
                "scheme": scheme, "horizon": horizon,
                "formal_model_mean_rankic": _optional_mean(model["value"]),
                **{f"formal_model_{name.lower()}_mean_rankic": _optional_mean(
                    model[(model["ordinal"] >= first) & (model["ordinal"] <= last)]["value"])
                   for name, first, last in protocol.BLOCKS},
                "mean_factor_transfer_pearson": _optional_mean([r["transfer_pearson"]
                                                                   for r in subset]),
                "mean_factor_raw_sign_agreement": _optional_mean([r["raw_sign_agreement_rate"]
                                                                      for r in subset]),
                "mean_factor_hard_flip_rate": _optional_mean([r["hard_flip_rate"]
                                                                  for r in subset]),
                "mean_cancellation_ratio": _optional_mean(cancellation["cancellation_ratio"]),
                "mean_diversification_ratio": _optional_mean(day["diversification_ratio"]),
                "mean_coefficient_sign_persistence": _optional_mean([
                    row["adjacent_sign_persistence_rate"] for row in beta_rows]),
                "mean_beta_future_sign_alignment": _optional_mean([
                    row["beta_vs_evaluation_sign_agreement"] for row in align_rows]),
            })
    tables = {
        "factor_transfer_daily.csv": transfer,
        "factor_transfer_summary.csv": pd.DataFrame(transfer_summary),
        "factor_transfer_transition.csv": pd.DataFrame(transitions),
        "factor_rankic_autocorrelation.csv": pd.DataFrame(autocorr),
        "factor_block_transfer.csv": pd.DataFrame(blocks),
        "coefficient_daily.csv": coefficient,
        "coefficient_stability_summary.csv": pd.DataFrame(coeff_summary),
        "coefficient_alignment_summary.csv": pd.DataFrame(alignment),
        "contribution_daily_summary.csv": contribution,
        "contribution_sector_daily.csv": sector,
        "contribution_factor_summary.csv": pd.DataFrame(factor_summary),
        "contribution_correlation.csv": pd.DataFrame(correlation),
        "contribution_block_summary.csv": pd.DataFrame(block_rows),
        "horizon_stability_summary.csv": pd.DataFrame(horizon_rows),
    }
    if set(tables) != set(TABLE_NAMES):
        raise ValueError("ALPHA_STABILITY_ARTIFACT_GRID_BLOCKER")
    return tables


def build_summary(tables: dict[str, pd.DataFrame], identities: dict, context: dict) -> dict:
    return {
        "auditType": AUDIT_TYPE, "phase": "DEVELOPMENT",
        "protocolHash": protocol.FROZEN_PROTOCOL_HASH,
        "sample": {"ids": "E001-E100", **context, "horizons": list(protocol.HORIZONS),
                   "schemes": list(protocol.SCHEMES)},
        "identity": identities,
        "counts": {name: len(frame) for name, frame in tables.items()},
        "researchFlags": {
            "POST_V2_DEVELOPMENT_DIAGNOSTIC": True,
            "INDEPENDENT_VALIDATION": False, "OOS": False,
            "DIAGNOSTIC_ONLY": True, "NO_NEW_CANDIDATE": True,
            "VALIDATION": "SEALED", "FINAL_OOS": "SEALED",
        },
        "interpretationPolicy": "DESCRIPTIVE ONLY; no candidate promotion or causal proof",
    }


def verify_artifact_integrity(run_dir: Path) -> dict:
    """Independently recalculate selected aggregates from persisted daily CSVs."""
    files = {name: pd.read_csv(run_dir / name) for name in TABLE_NAMES}
    daily = files["factor_transfer_daily.csv"]
    summary = files["factor_transfer_summary.csv"]
    transition = files["factor_transfer_transition.csv"]
    blocks = files["factor_block_transfer.csv"]
    coefficient = files["coefficient_daily.csv"]
    coeff_summary = files["coefficient_stability_summary.csv"]
    contribution = files["contribution_daily_summary.csv"]
    factor_summary = files["contribution_factor_summary.csv"]
    sector = files["contribution_sector_daily.csv"]
    block_summary = files["contribution_block_summary.csv"]
    maximum = {"transfer": 0.0, "transition": 0.0, "coefficient": 0.0,
               "contributionShare": 0.0, "cancellation": 0.0, "block": 0.0}
    comparisons = {key: 0 for key in maximum}

    def compare(kind: str, actual, expected) -> None:
        if pd.isna(actual) and pd.isna(expected):
            return
        if pd.isna(actual) or pd.isna(expected):
            raise ValueError(f"ALPHA_STABILITY_METRIC_INTEGRITY_BLOCKER: {kind} null mismatch")
        diff = abs(float(actual) - float(expected))
        maximum[kind] = max(maximum[kind], diff)
        comparisons[kind] += 1
        if diff > 1e-12:
            raise ValueError(f"ALPHA_STABILITY_METRIC_INTEGRITY_BLOCKER: {kind} {diff}")

    for row in summary.itertuples(index=False):
        group = daily[(daily["factor"] == row.factor) & (daily["horizon"] == row.horizon)]
        paired = group.dropna(subset=["train_mean_rankic", "evaluation_rankic"])
        x = paired["train_mean_rankic"].to_numpy(dtype=float)
        y = paired["evaluation_rankic"].to_numpy(dtype=float)
        compare("transfer", row.valid_signal_dates, len(paired))
        compare("transfer", row.mean_train_rankic, _optional_mean(x))
        compare("transfer", row.mean_evaluation_rankic, _optional_mean(y))
        compare("transfer", row.transfer_pearson, _optional_corr(x, y))
        compare("transfer", row.transfer_spearman, _optional_corr(x, y, spearman=True))
        compare("transfer", row.mean_absolute_transfer_error,
                float(np.mean(np.abs(y - x))) if len(x) else None)
        compare("transfer", row.mean_signed_transfer_delta,
                float(np.mean(y - x)) if len(x) else None)
        compare("transfer", row.raw_sign_agreement_rate,
                _optional_mean(paired["raw_sign_agreement"]))
        compare("transfer", row.hard_flip_count, int(paired["hard_flip"].sum()))
        compare("transfer", row.hard_flip_rate, _optional_mean(paired["hard_flip"]))
        matrix = transition[(transition["factor"] == row.factor)
                            & (transition["horizon"] == row.horizon)]
        if len(matrix) != 9 or int(matrix["count"].sum()) != len(paired):
            raise ValueError("ALPHA_STABILITY_METRIC_INTEGRITY_BLOCKER: transition grid")
        for cell in matrix.itertuples(index=False):
            expected = int(((paired["train_direction"] == cell.train_direction)
                            & (paired["evaluation_direction"] == cell.evaluation_direction)).sum())
            compare("transition", cell.count, expected)
    for row in blocks.itertuples(index=False):
        group = daily[(daily["factor"] == row.factor) & (daily["horizon"] == row.horizon)
                      & (daily["block"] == row.block)].dropna(
                          subset=["train_mean_rankic", "evaluation_rankic"])
        compare("block", row.valid_dates, len(group))
        compare("block", row.mean_train_rankic, _optional_mean(group["train_mean_rankic"]))
        compare("block", row.mean_evaluation_rankic,
                _optional_mean(group["evaluation_rankic"]))
        compare("block", row.raw_sign_agreement_rate,
                _optional_mean(group["raw_sign_agreement"]))
        compare("block", row.hard_flip_rate, _optional_mean(group["hard_flip"]))
    for row in coeff_summary.itertuples(index=False):
        group = coefficient[(coefficient["scheme"] == row.scheme)
                            & (coefficient["horizon"] == row.horizon)
                            & (coefficient["factor"] == row.factor)].sort_values("ordinal")
        beta = group["beta"].to_numpy(dtype=float)
        changes, persistence = _adjacent_sign_stats(beta)
        compare("coefficient", row.valid_dates, len(beta))
        compare("coefficient", row.sign_change_count, changes)
        compare("coefficient", row.adjacent_sign_persistence_rate, persistence)
        compare("coefficient", row.positive_coefficient_share, float(np.mean(beta > 0)))
        compare("coefficient", row.negative_coefficient_share, float(np.mean(beta < 0)))
        compare("coefficient", row.zero_coefficient_share, float(np.mean(beta == 0)))
    for (scheme, ordinal, horizon), group in contribution.groupby(
            ["scheme", "ordinal", "horizon"]):
        shares = group["absolute_share"].dropna()
        if len(shares):
            compare("contributionShare", float(shares.sum()), 1.0)
    for row in factor_summary.itertuples(index=False):
        group = contribution[(contribution["scheme"] == row.scheme)
                             & (contribution["horizon"] == row.horizon)
                             & (contribution["factor"] == row.factor)]
        compare("contributionShare", row.share_mean,
                _optional_mean(group["absolute_share"]))
    for row in block_summary.itertuples(index=False):
        group = sector[(sector["scheme"] == row.scheme)
                       & (sector["horizon"] == row.horizon)
                       & ((sector["block"] == row.block) if row.block != "ALL" else True)]
        compare("cancellation", row.sector_observations, len(group))
        compare("cancellation", row.cancellation_mean,
                _optional_mean(group["cancellation_ratio"]))
        compare("cancellation", row.cancellation_median,
                float(group["cancellation_ratio"].median()))
    if (set(daily["ordinal"]) != set(range(1, 101))
            or set(coefficient["ordinal"]) != set(range(1, 101))
            or set(sector["ordinal"]) != set(range(1, 101))):
        raise ValueError("SEALED_OR_NON_DEVELOPMENT_ACCESS_BLOCKER")
    return {"status": "PASS", "maxAbsDifferences": maximum,
            "comparisons": comparisons, "tolerance": 1e-12,
            "source": "independent recomputation from persisted daily artifacts"}


def write_run(output_root: Path, result: AuditResult, gate: dict,
              repeat_of: Path | None = None) -> Path:
    protocol.verify_protocol()
    protocol.guard_scope("development", list(range(1, 101)))
    if gate.get("gitCommit") != gate.get("preregistrationCommit"):
        raise ValueError("ALPHA_STABILITY_PREREGISTRATION_COMMIT_MISMATCH")
    run_id = datetime.now(timezone.utc).strftime("alpha_stability_regime_audit_%Y%m%d_%H%M%S_%f_utc")
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / run_id
    target.mkdir(exist_ok=False)
    hashes = {}
    for name in TABLE_NAMES:
        payload = baseline._csv_bytes(result.tables[name])
        (target / name).write_bytes(payload)
        hashes[name] = hashlib.sha256(payload).hexdigest()
    summary_bytes = baseline._json_bytes(result.summary)
    (target / "audit_summary.json").write_bytes(summary_bytes)
    hashes["audit_summary.json"] = hashlib.sha256(summary_bytes).hexdigest()
    integrity = {"identity": result.identities,
                 "metricRecompute": verify_artifact_integrity(target)}
    integrity_bytes = baseline._json_bytes(integrity)
    (target / "integrity.json").write_bytes(integrity_bytes)
    hashes["integrity.json"] = hashlib.sha256(integrity_bytes).hexdigest()
    if repeat_of is not None:
        old = json.loads((repeat_of / "metadata.json").read_text(encoding="utf-8"))
        if old["protocolHash"] != protocol.FROZEN_PROTOCOL_HASH or old["contentSha256"] != hashes:
            raise ValueError("ALPHA_STABILITY_AUDIT_DETERMINISM_BLOCKER")
    metadata = {
        "researchLabel": "SECTOR_INDEX_RESEARCH_ONLY", "phase": "DEVELOPMENT",
        "auditType": AUDIT_TYPE, "runId": run_id,
        "preregistrationCommit": gate["preregistrationCommit"],
        "executionGitCommit": gate["gitCommit"],
        "protocolHash": protocol.FROZEN_PROTOCOL_HASH,
        "sectorSnapshotId": gate["sectorSnapshotId"],
        "splitPolicyHash": gate["splitPolicyHash"],
        "factorOrder": list(protocol.FACTOR_ORDER),
        "schemes": {name: list(factors) for name, factors in protocol.SCHEMES.items()},
        "horizons": list(protocol.HORIZONS),
        "developmentIds": "E001-E100", "startDate": gate["firstDate"],
        "endDate": gate["lastDate"], "sectorCount": 124,
        "directionThreshold": protocol.DIRECTION_THRESHOLD,
        "blocks": [{"id": n, "first": a, "last": b} for n, a, b in protocol.BLOCKS],
        "autocorrelationLags": list(protocol.LAGS),
        "cancellationEps": protocol.CANCELLATION_EPS,
        "strictPit": False, "classification": "FIXED_CLASSIFICATION_RESEARCH",
        "executable": False, "tradable": False,
        "validation": "SEALED", "finalOos": "SEALED",
        "POST_V2_DEVELOPMENT_DIAGNOSTIC": True,
        "INDEPENDENT_VALIDATION": False, "OOS": False,
        "DIAGNOSTIC_ONLY": True, "environmentChanged": False,
        "dockerImageId": gate["dockerImageId"], "contentSha256": hashes,
        "determinismRepeatOf": repeat_of.name if repeat_of else None,
    }
    (target / "metadata.json").write_bytes(baseline._json_bytes(metadata))
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker-image-id", required=True)
    parser.add_argument("--preregistration-commit", required=True)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/shenwan"))
    parser.add_argument("--v2-root", type=Path,
                        default=Path("reports/research/shenwan_sector_index") / SOURCE_V2_RUN)
    parser.add_argument("--d0-root", type=Path,
                        default=Path("reports/research/shenwan_sector_index") / SOURCE_D0_RUN / "D0")
    parser.add_argument("--output-root", type=Path,
                        default=Path("reports/research/shenwan_sector_index"))
    parser.add_argument("--repeat-of", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    gate = pre_run_gate(repo, args.processed_dir, args.v2_root,
                        args.docker_image_id, args.preregistration_commit)
    assert_formal_result_state(args.output_root, args.repeat_of)
    print(json.dumps(gate, ensure_ascii=False, sort_keys=True), flush=True)
    if not args.execute:
        return 0
    result = compute_audit(args.processed_dir, args.v2_root, args.d0_root, gate)
    target = write_run(args.output_root, result, gate, args.repeat_of)
    print(f"ALPHA STABILITY AUDIT COMPLETE: {target}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
