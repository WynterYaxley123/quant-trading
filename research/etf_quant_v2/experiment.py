"""Chronological Ridge experiments with frozen policy and single Validation access."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from .coverage import digest, external_directory, immutable_bytes, json_bytes
from .diagnostics import dependence, feature_geometry, ridge_vs_ols
from .protocol import Candidate, candidates, canonical_hash
from .recovery import write_json

Array = NDArray[np.float64]
MODES = ("HIGH_CONFIDENCE", "EXTENDED_HISTORY")
HORIZONS = (10, 40, 80, 120)


@dataclass(frozen=True)
class ExperimentSplit:
    development_start: int
    development_end: int
    validation_start: int
    validation_end: int
    final_oos_start: int
    final_oos_end: int
    maturity_tail_start: int

    def permit(self, phase: str, indices: list[int]) -> None:
        if phase == "DEVELOPMENT":
            allowed = range(0, self.development_end + 1)
        elif phase == "VALIDATION":
            allowed = range(0, self.validation_end + 1)
        else:
            raise ValueError("FINAL_OOS_ACCESS_DENIED")
        if any(i not in allowed for i in indices):
            raise ValueError("PHASE_LABEL_ACCESS_DENIED")


def make_split(dates: list[str], universe_cutoff: str | None = None) -> ExperimentSplit:
    n = len(dates)
    tail, final, validation, gap = 120, 60, 80, 120
    final_end = n - tail - 1
    final_start = final_end - final + 1
    validation_end = final_start - gap - 1
    validation_start = validation_end - validation + 1
    development_end = validation_start - gap - 1
    development_start = int(np.searchsorted(dates, "2020-07-01"))
    if universe_cutoff is not None:
        development_start = max(development_start, int(np.searchsorted(dates, universe_cutoff)) + 1)
    if development_end - development_start < 160:
        raise ValueError("NO_DEFENSIBLE_DEVELOPMENT_INTERVAL")
    if dates[development_end + 120] >= "2026-03-03":
        raise ValueError("V1_SEALED_PERFORMANCE_PERIOD_EXCLUDED")
    return ExperimentSplit(
        development_start,
        development_end,
        validation_start,
        validation_end,
        final_start,
        final_end,
        final_end + 1,
    )


def freeze_protocol(metadata: dict[str, Any], output: Path, panel: Any) -> dict[str, Any]:
    split = make_split(metadata["dates"], metadata["universe_coverage_cutoff"])
    comparison_start = {"EXTENDED_HISTORY": split.development_start}
    available = np.asarray(np.isfinite(panel["HIGH_CONFIDENCE_X"]).all(axis=2)).sum(axis=1) >= 12
    first = int(np.flatnonzero(available)[0])
    cutoff = (pd.Timestamp(metadata["dates"][first]) + pd.DateOffset(months=12)).date().isoformat()
    comparison_start["HIGH_CONFIDENCE"] = max(
        split.development_start, int(np.searchsorted(metadata["dates"], cutoff)) + 120
    )
    policy = {
        "contract": "ETF_QUANT_V2_EVIDENCE_TIERED_EXPERIMENT",
        "data_sha256": metadata["data_sha256"],
        "split": asdict(split),
        "phase_dates": {key: metadata["dates"][value] for key, value in asdict(split).items()},
        "stage1": [asdict(c) | {"identifier": c.identifier} for c in candidates()],
        "evidence_modes": list(MODES),
        "mode_development_start": comparison_start,
        "comparison_policy": "COMMON_6M_12M_ALL_HORIZON_EVALUATION_DATES_WITHIN_EACH_MODE;24M_SUBJECT_TO_160_SIGNALS",
        "selection": {
            "minimum_signals": 160,
            "folds": 4,
            "minimum_cross_section": 12,
            "positive_fold_majority": 3,
            "minimum_worst_rank_ic": -0.05,
            "maximum_coefficient_norm_cv": 1.0,
            "maximum_positive_fold_concentration": 0.60,
            "positive_mean_rank_ic_and_spread": True,
            "long_incremental_rank_ic": 0.005,
            "prefer": "HIGH_CONFIDENCE_PASS;MEDIAN_FOLD_IC;MEDIAN_FOLD_SPREAD;WORST_FOLD;STABILITY;SIMPLICITY",
            "ties": {"rank_ic": 0.005, "spread": 0.001},
            "bootstrap_block": 120,
            "replications": 1000,
            "seed": 20261004,
        },
        "one_focused_stage2": True,
        "one_validation_informed_development_revision": True,
        "training": {
            "minimum_dates": 30,
            "calendar_window_before_mature_horizon_cutoff": True,
            "training_only_population_standardization": True,
            "cross_section": "SIGNAL_FEATURE_ELIGIBLE_UNIVERSE;COMPLETE_MATURED_TARGETS;NO_FUTURE_ASSET_SELECTION",
        },
        "execution": {
            "policy": "V1_VERIFIED_MAPPING_PROXY_CASH_SIZING_T_PLUS_1_UNCHANGED",
            "historical_missing_mapping": "CASH;NO_CURRENT_EVIDENCE_BACKSTAMP",
        },
        "validation_open_count_maximum": 1,
        "final_oos_access": "DENIED",
    }
    policy["protocol_sha256"] = canonical_hash(policy)
    immutable_bytes(output / "protocol.json", json_bytes(policy))
    return policy


def targets(
    x: Array,
    close: Array,
    segments: NDArray[np.int64],
    horizon: int,
    split: ExperimentSplit,
    phase: str,
) -> Array:
    stop = split.development_end if phase == "DEVELOPMENT" else split.validation_end
    split.permit(phase, list(range(stop + 1)))
    y = np.full(close.shape, np.nan)
    eligible = np.asarray(np.isfinite(x).all(axis=2), dtype=np.bool_)
    for t in range(min(stop + 1, len(close) - horizon)):
        active = eligible[t]
        if active.sum() < 12:
            continue
        raw = close[t + horizon] / close[t] - 1
        good = np.asarray(np.isfinite(raw) & (segments[t + horizon] == segments[t]), dtype=np.bool_)
        if not good[active].all():
            continue
        y[t, active] = raw[active] - raw[active].mean()
    return y


class SufficientStatistics:
    """Centered Ridge objective equivalent to NumPyRidge, with reusable date sums."""

    def __init__(self, x: Array, y: Array) -> None:
        eligible = np.isfinite(x).all(axis=2) & np.isfinite(y)
        values = np.where(eligible[..., None], x, 0)
        target = np.where(eligible, y, 0)
        quantities = (
            eligible.sum(axis=1).astype(float),
            (eligible.sum(axis=1) >= 12).astype(float),
            values.sum(axis=1),
            target.sum(axis=1),
            np.einsum("tnp,tnq->tpq", values, values),
            np.einsum("tnp,tn->tp", values, target),
        )
        self.prefix = [
            np.concatenate((np.zeros((1, *v.shape[1:])), np.cumsum(v, axis=0))) for v in quantities
        ]

    def fit(
        self, start: int, stop: int, alpha: float, standardized: bool
    ) -> tuple[Array, float, Array, Array]:
        n, days, sx, sy, sxx, sxy = [p[stop + 1] - p[start] for p in self.prefix]
        if n < 12 * 30 or days < 30:
            raise ValueError("INSUFFICIENT_MATURE_TRAINING_DATES")
        mean, target_mean = sx / n, float(sy / n)
        gram, xy = sxx - np.outer(sx, sx) / n, sxy - sx * sy / n
        std = np.sqrt(np.maximum(np.diag(gram), 0) / n) if standardized else np.ones_like(mean)
        if not np.isfinite(std).all() or (std <= 1e-12).any():
            raise ValueError("ZERO_TRAINING_VARIANCE")
        scaled = gram / np.outer(std, std)
        eigenvalues, vectors = np.linalg.eigh((scaled + scaled.T) / 2)
        if eigenvalues.min() < -1e-6 * max(float(eigenvalues.max()), 1):
            raise ValueError("INVALID_NUMERICAL_GRAM")
        coef = vectors @ ((vectors.T @ (xy / std)) / (np.maximum(eigenvalues, 0) + alpha))
        intercept = target_mean - float((mean / std) @ coef)
        if not np.isfinite(coef).all() or not np.isfinite(intercept):
            raise ValueError("NONFINITE_FIT")
        return coef, intercept, mean, std


def component(
    x: Array,
    y: Array,
    dates: list[str],
    horizon: int,
    months: int,
    alpha: float,
    scaling: str,
    signals: range,
    current_eligible: NDArray[np.bool_] | None = None,
) -> tuple[Array, Array, Array]:
    stats = SufficientStatistics(x, y)
    scores = np.full(y.shape, np.nan)
    norms = np.full(len(x), np.nan)
    coefficients = np.full((len(x), x.shape[2]), np.nan)
    minimum = next((t for t in range(len(x)) if np.isfinite(x[t]).all(axis=1).sum() >= 12), len(x))
    for t in signals:
        cutoff = t - horizon
        if cutoff < 1:
            continue
        window_start = (
            (pd.Timestamp(dates[cutoff]) - pd.DateOffset(months=months)).date().isoformat()
        )
        start = int(np.searchsorted(dates, window_start))
        if start < minimum:
            continue
        active = np.isfinite(x[t]).all(axis=1)
        if current_eligible is not None:
            active &= current_eligible[t]
        if active.sum() < 12:
            continue
        try:
            coef, intercept, _, std = stats.fit(
                start, cutoff, alpha, scaling == "TRAIN_ONLY_STANDARDIZED"
            )
            predictions = (x[t, active] / std) @ coef + intercept
            prediction_std = predictions.std(ddof=0)
            if prediction_std <= 1e-12 or not np.isfinite(predictions).all():
                continue
            scores[t, active] = (predictions - predictions.mean()) / prediction_std
            norms[t], coefficients[t] = float(np.linalg.norm(coef)), coef
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            continue
    return scores, norms, coefficients


def bootstrap(values: Array, block: int = 120) -> dict[str, Any]:
    """Retain calendar gaps in resampling; never compress missing days into time."""
    count = int(np.isfinite(values).sum())
    if len(values) < 2 * block or count < 160:
        return {"interval": None, "bootstrap_ess": None, "reason": "INSUFFICIENT_BLOCKS"}
    rng = np.random.default_rng(20261004)
    means = []
    for _ in range(1000):
        starts = rng.integers(0, len(values) - block + 1, size=(len(values) + block - 1) // block)
        sample = values[(starts[:, None] + np.arange(block)).ravel()[: len(values)]]
        if np.isfinite(sample).sum() >= 30:
            means.append(float(np.nanmean(sample)))
    variance = float(np.var(means, ddof=1))
    return {
        "interval": list(map(float, np.quantile(means, [0.025, 0.975]))),
        "bootstrap_ess": min(float(count), float(np.nanvar(values, ddof=1)) / variance)
        if variance > 0
        else None,
        "block": block,
        "replications": len(means),
        "calendar_missing_sessions": len(values) - count,
    }


def evaluate(
    scores: Array,
    target: Array,
    signals: range,
    norms: Array,
    fold_boundaries: list[int] | None = None,
) -> dict[str, Any]:
    ic, spread = np.full(len(signals), np.nan), np.full(len(signals), np.nan)
    turnover = []
    prior_weights: dict[int, float] = {}
    for k, t in enumerate(signals):
        active = np.isfinite(scores[t])
        if active.sum() < 12 or not np.isfinite(target[t, active]).all():
            continue
        prediction, actual = scores[t, active], target[t, active]
        if np.std(actual) <= 1e-12:
            continue
        prediction_rank = pd.Series(prediction).rank(method="average").to_numpy()
        actual_rank = pd.Series(actual).rank(method="average").to_numpy()
        ic[k] = float(np.corrcoef(prediction_rank, actual_rank)[0, 1])
        ordered = np.lexsort((np.flatnonzero(active), -prediction))
        spread[k] = float(actual[ordered[:5]].mean() - actual[ordered[-5:]].mean())
        winners = np.flatnonzero(active)[ordered[:5]]
        weights = {int(i): 0.2 for i in winners}
        turnover.append(
            sum(
                abs(weights.get(i, 0) - prior_weights.get(i, 0))
                for i in weights.keys() | prior_weights.keys()
            )
        )
        prior_weights = weights
    fold_stats = []
    fold_indices = (
        np.split(np.arange(len(signals)), fold_boundaries)
        if fold_boundaries is not None
        else np.array_split(np.arange(len(signals)), 4)
    )
    for indices in fold_indices:
        a, b = ic[indices], spread[indices]
        finite = np.isfinite(a)
        fold_stats.append(
            {
                "signals": int(finite.sum()),
                "mean_rank_ic": float(np.nanmean(a)) if finite.any() else None,
                "mean_spread": float(np.nanmean(b)) if finite.any() else None,
            }
        )
    valid = np.isfinite(ic)
    if not valid.any():
        return {"signals": 0, "folds": fold_stats, "ic_series": ic, "spread_series": spread}
    norm = norms[list(signals)]
    norm = norm[np.isfinite(norm)]
    std = float(np.nanstd(ic, ddof=1))
    return {
        "signals": int(valid.sum()),
        "mean_rank_ic": float(np.nanmean(ic)),
        "median_rank_ic": float(np.nanmedian(ic)),
        "rank_ic_ir": float(np.nanmean(ic)) / std if std else None,
        "positive_rank_ic_fraction": float(np.mean(ic[valid] > 0)),
        "mean_spread": float(np.nanmean(spread)),
        "folds": fold_stats,
        "coefficient_norm_cv": float(norm.std() / norm.mean())
        if len(norm) and norm.mean()
        else None,
        "coefficient_norm_median": float(np.median(norm)) if len(norm) else None,
        "predictive_top5_absolute_weight_turnover": float(np.mean(turnover)) if turnover else None,
        "counterfactual_industry_cost_proxy": float(np.mean(turnover)) * 0.0008
        if turnover
        else None,
        "ic_series": ic,
        "spread_series": spread,
    }


def passing(result: dict[str, Any], incremental: float | None, long: bool) -> bool:
    if result["signals"] < 160 or result.get("coefficient_norm_cv") is None:
        return False
    folds = result["folds"]
    if any(f["signals"] < 30 or f["mean_rank_ic"] is None for f in folds):
        return False
    positives = [max(f["mean_rank_ic"], 0) for f in folds]
    majority = sum(f["mean_rank_ic"] > 0 and f["mean_spread"] > 0 for f in folds)
    return bool(
        result["mean_rank_ic"] > 0
        and result["mean_spread"] > 0
        and majority >= 3
        and min(f["mean_rank_ic"] for f in folds) >= -0.05
        and result["coefficient_norm_cv"] <= 1
        and sum(positives) > 0
        and max(positives) / sum(positives) <= 0.60
        and (not long or (incremental is not None and incremental >= 0.005))
    )


def public_metrics(result: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in result.items() if not isinstance(v, np.ndarray)}


def run_grid(
    metadata: dict[str, Any],
    panel: Any,
    protocol: dict[str, Any],
    output: Path,
    specs: tuple[Candidate, ...] | None = None,
    phase: str = "DEVELOPMENT",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    split = ExperimentSplit(**protocol["split"])
    signals = (
        range(split.development_start, split.development_end + 1)
        if phase == "DEVELOPMENT"
        else range(split.validation_start, split.validation_end + 1)
    )
    specs = candidates() if specs is None else specs
    results, retained = [], {}
    factor_names = metadata["factors"]
    for mode in MODES:
        if phase == "DEVELOPMENT":
            signals = range(protocol["mode_development_start"][mode], split.development_end + 1)
        x = np.asarray(panel[mode + "_X"], dtype=float)
        y = {
            h: targets(x, panel[mode + "_close"], panel[mode + "_segments"], h, split, phase)
            for h in HORIZONS
        }
        fold_boundaries = None
        if protocol["selection"].get("fold_partition") == "TARGET_OBSERVABILITY_CALENDAR_BLOCKS":
            observed = np.flatnonzero(np.isfinite(y[40][list(signals)]).any(axis=1))
            if len(observed) >= 160:
                fold_boundaries = [int(observed[len(observed) * k // 4]) for k in (1, 2, 3)]
        components: dict[tuple[int, int, float, str], tuple[Array, Array, Array]] = {}
        for c in specs:
            for h in c.horizons:
                key = (h, c.training_months, c.alpha, c.scaling)
                if key not in components:
                    columns = [factor_names.index(name) for name in c.factors(h)]
                    identity = canonical_hash(
                        {
                            "panel": metadata["panel_sha256"],
                            "protocol": protocol["protocol_sha256"],
                            "mode": mode,
                            "component": key,
                            "phase": phase,
                            "fit_code_sha256": digest(Path(__file__)),
                        }
                    )
                    cache = output / "cache" / (identity + ".npz")
                    cache.parent.mkdir(exist_ok=True)
                    if cache.exists():
                        values = np.load(cache)
                        components[key] = (
                            values["scores"],
                            values["norms"],
                            values["coefficients"],
                        )
                    else:
                        computed = component(
                            x[:, :, columns],
                            y[h],
                            metadata["dates"],
                            h,
                            c.training_months,
                            c.alpha,
                            c.scaling,
                            signals,
                            np.isfinite(x).all(axis=2),
                        )
                        np.savez_compressed(
                            cache, scores=computed[0], norms=computed[1], coefficients=computed[2]
                        )
                        components[key] = computed
            scores = np.sum(
                np.stack(
                    [
                        w * components[(h, c.training_months, c.alpha, c.scaling)][0]
                        for h, w in zip(c.horizons, c.fusion, strict=True)
                    ]
                ),
                axis=0,
            )
            norms = np.nanmean(
                np.vstack(
                    [components[(h, c.training_months, c.alpha, c.scaling)][1] for h in c.horizons]
                ),
                axis=0,
            )
            result = evaluate(scores, y[40], signals, norms, fold_boundaries)
            incremental = None
            if len(c.horizons) == 3 and result["signals"]:
                short = np.sum(
                    np.stack(
                        [
                            w * components[(h, c.training_months, c.alpha, c.scaling)][0]
                            for h, w in zip(c.horizons[:2], c.fusion[:2], strict=True)
                        ]
                    ),
                    axis=0,
                )
                shorter = evaluate(short, y[40], signals, norms, fold_boundaries)
                if shorter["signals"]:
                    incremental = result["mean_rank_ic"] - shorter["mean_rank_ic"]
            record = {
                "candidate": asdict(c),
                "id": c.identifier,
                "mode": mode,
                "metrics": public_metrics(result),
                "incremental_long_rank_ic": incremental,
                "passes": passing(result, incremental, len(c.horizons) == 3),
            }
            results.append(record)
            retained[c.identifier + "/" + mode] = {"result": result, "scores": scores}
            write_json(output / ("grid-" + phase.lower() + ".json"), results)
        print(
            json.dumps(
                {
                    "stage": phase,
                    "mode": mode,
                    "candidates": len(specs),
                    "passed": sum(r["passes"] for r in results if r["mode"] == mode),
                }
            ),
            flush=True,
        )
    return results, retained


def select(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [r for r in results if r["passes"] and r["mode"] == "HIGH_CONFIDENCE"]
    if not eligible:
        eligible = [r for r in results if r["passes"]]
    if not eligible:
        return None

    def key(r: dict[str, Any]) -> tuple[Any, ...]:
        metrics = r["metrics"]
        folds = metrics["folds"]
        return (
            round(float(np.median([f["mean_rank_ic"] for f in folds])) / 0.005),
            round(float(np.median([f["mean_spread"] for f in folds])) / 0.001),
            min(f["mean_rank_ic"] for f in folds),
            -metrics["coefficient_norm_cv"],
            -len(r["candidate"]["horizons"]),
            r["id"],
        )

    return max(eligible, key=key)


def structural_diagnostics(
    metadata: dict[str, Any], panel: Any, protocol: dict[str, Any]
) -> dict[str, Any]:
    split = ExperimentSplit(**protocol["split"])
    result: dict[str, Any] = {}
    for mode in MODES:
        x = np.asarray(panel[mode + "_X"], dtype=float)
        stats: dict[str, Any] = {}
        for h in HORIZONS:
            y = targets(
                x, panel[mode + "_close"], panel[mode + "_segments"], h, split, "DEVELOPMENT"
            )
            diagnostics = []
            for j in range(y.shape[1]):
                series = y[split.development_start : split.development_end + 1, j]
                runs = np.split(
                    np.arange(len(series)),
                    np.where(np.diff(np.isfinite(series).astype(int)))[0] + 1,
                )
                runs = [r for r in runs if len(r) >= 100 and np.isfinite(series[r]).all()]
                if runs:
                    longest = max(runs, key=len)
                    value = dependence(series[longest], h)
                    value["industry"] = metadata["industries"][j]
                    value["block_uncertainty"] = bootstrap(series, h)
                    diagnostics.append(value)
            stats[str(h)] = {
                "industries_measured": len(diagnostics),
                "median_ess": float(np.median([r["ess_positive_sequence"] for r in diagnostics]))
                if diagnostics
                else None,
                "median_nonoverlapping_blocks": float(
                    np.median([r["nonoverlapping_horizon_blocks"] for r in diagnostics])
                )
                if diagnostics
                else None,
                "mechanical_overlap": (h - 1) / h,
                "per_industry": diagnostics,
            }
        y = targets(x, panel[mode + "_close"], panel[mode + "_segments"], 40, split, "DEVELOPMENT")
        fit_day = split.development_end
        cutoff = fit_day - 40
        start = int(
            np.searchsorted(
                metadata["dates"],
                (pd.Timestamp(metadata["dates"][cutoff]) - pd.DateOffset(months=6))
                .date()
                .isoformat(),
            )
        )
        xx, yy = x[start : cutoff + 1], y[start : cutoff + 1]
        valid = np.isfinite(xx).all(axis=2) & np.isfinite(yy)
        if valid.sum() >= 100:
            stats["ridge_vs_ols"] = ridge_vs_ols(xx[valid], yy[valid])
            stats["feature_geometry"] = feature_geometry(xx[valid])
        result[mode] = stats
    return result


def validation_open(output: Path, frozen: dict[str, Any]) -> None:
    gate = output / "validation-access.json"
    identity = canonical_hash(frozen)
    value = {"candidate_sha256": identity, "open_count": 1, "final_oos_opened": False}
    if gate.exists():
        if json.loads(gate.read_text()) != value:
            raise ValueError("VALIDATION_CANDIDATE_CANNOT_BE_REPLACED")
        return
    descriptor = os.open(gate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(json_bytes(value))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    external_directory(args.output)
    metadata = json.loads((args.panel / "panel.json").read_text())
    if digest(args.panel / "panel.npz") != metadata["panel_sha256"]:
        raise ValueError("PANEL_HASH_MISMATCH")
    panel = np.load(args.panel / "panel.npz")
    protocol = freeze_protocol(metadata, args.output, panel)
    diagnostics_path = args.output / "diagnostics.json"
    if not diagnostics_path.exists():
        write_json(diagnostics_path, structural_diagnostics(metadata, panel, protocol))
    results, retained = run_grid(metadata, panel, protocol, args.output)
    winner = select(results)
    if winner is None:
        write_json(
            args.output / "stage1-status.json",
            {"status": "NO_PASSING_STAGE1_CANDIDATE", "stage2_authorized": True},
        )
        print("NO_PASSING_STAGE1_CANDIDATE;FOCUSED_STAGE2_REQUIRED", flush=True)
        return
    metrics = retained[winner["id"] + "/" + winner["mode"]]["result"]
    winner["block_uncertainty"] = bootstrap(metrics["ic_series"])
    frozen = {
        "contract": "ETF_QUANT_V2_DEVELOPMENT_CANDIDATE",
        "selected": winner,
        "protocol_sha256": protocol["protocol_sha256"],
        "data_sha256": metadata["data_sha256"],
        "source_files": {p.name: digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        "mapping_policy": "FROZEN_V1_FORWARD_EVIDENCE_ONLY_WITH_CASH_FALLBACK",
        "final_oos_opened": False,
        "shadow_started": False,
    }
    immutable_bytes(args.output / "development-candidate.json", json_bytes(frozen))
    validation_open(args.output, frozen)
    spec = Candidate(
        **(
            winner["candidate"]
            | {
                "horizons": tuple(winner["candidate"]["horizons"]),
                "fusion": tuple(winner["candidate"]["fusion"]),
            }
        )
    )
    validation_path = args.output / "validation.json"
    if not validation_path.exists():
        validation, _ = run_grid(metadata, panel, protocol, args.output, (spec,), "VALIDATION")
        chosen = next(r for r in validation if r["mode"] == winner["mode"])
        m = chosen["metrics"]
        accepted = (
            m["signals"] >= 40 and m.get("mean_rank_ic", -1) > 0 and m.get("mean_spread", -1) > 0
        )
        write_json(
            validation_path,
            {
                "status": "ACCEPTED" if accepted else "FAILED",
                "candidate_sha256": canonical_hash(frozen),
                "results": validation,
                "accepted": accepted,
                "open_count": 1,
                "final_oos_opened": False,
                "development_to_validation_rank_ic": m.get("mean_rank_ic", 0)
                - winner["metrics"]["mean_rank_ic"],
            },
        )
    print(
        json.dumps(
            {
                "winner": winner["id"],
                "mode": winner["mode"],
                "validation": json.loads(validation_path.read_text())["status"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
