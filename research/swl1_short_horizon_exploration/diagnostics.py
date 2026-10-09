"""Descriptive diagnostics with explicit ties, gaps and dependent observations."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from research.swl1_ridge_v2.evaluation import calendar_blocks, extremes

from .signals import Array


def stats(values: Any) -> dict[str, Any]:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    return {
        "count": len(x),
        "mean": float(x.mean()) if len(x) else None,
        "median": float(np.median(x)) if len(x) else None,
        "positive_fraction": float((x > 0).mean()) if len(x) else None,
        "std": float(x.std(ddof=0)) if len(x) else None,
        "minimum": float(x.min()) if len(x) else None,
        "maximum": float(x.max()) if len(x) else None,
    }


def rank_rows(scores: Array, targets: Array) -> Array:
    """Vectorized average-tie Spearman, checked against the frozen scalar oracle."""
    if scores.shape != targets.shape or scores.ndim != 2:
        raise ValueError("MATCHED_SCORE_TARGET_MATRICES_REQUIRED")
    x = pd.DataFrame(scores).rank(axis=1, method="average").to_numpy()
    y = pd.DataFrame(targets).rank(axis=1, method="average").to_numpy()
    x, y = x - x.mean(axis=1, keepdims=True), y - y.mean(axis=1, keepdims=True)
    numerator = np.sum(x * y, axis=1)
    denominator = np.sqrt(np.sum(x * x, axis=1) * np.sum(y * y, axis=1))
    return np.divide(numerator, denominator, out=np.full(len(x), np.nan), where=denominator > 0)


def autocorrelation(values: Array, indices: list[int], lag: int) -> float | None:
    locations = {i: k for k, i in enumerate(indices)}
    pairs = [(k, locations[i + lag]) for k, i in enumerate(indices) if i + lag in locations]
    x = np.asarray([values[a] for a, _ in pairs])
    y = np.asarray([values[b] for _, b in pairs])
    valid = np.isfinite(x) & np.isfinite(y)
    if valid.sum() < 3 or np.std(x[valid]) <= 1e-12 or np.std(y[valid]) <= 1e-12:
        return None
    return float(np.corrcoef(x[valid], y[valid])[0, 1])


def block_interval(values: Array, indices: list[int]) -> dict[str, Any]:
    """Circular blocks stay within contiguous session runs, including S5's gap."""
    valid = np.isfinite(values)
    runs: list[list[int]] = []
    for k, index in enumerate(indices):
        if not valid[k]:
            continue
        if not runs or indices[runs[-1][-1]] + 1 != index:
            runs.append([])
        runs[-1].append(k)
    eligible = [r for r in runs if len(r) >= 20]
    blocks = [
        np.asarray([r[(start + j) % len(r)] for j in range(20)])
        for r in eligible
        for start in range(len(r))
    ]
    if not blocks:
        return {
            "lower_5pct": None,
            "upper_95pct": None,
            "replicates": 0,
            "reason": "NO_COMPLETE_20_SESSION_RUN",
        }
    generator = np.random.default_rng(20261009)
    n = int(valid.sum())
    means = []
    for _ in range(500):
        selected = generator.integers(0, len(blocks), size=(n + 19) // 20)
        resample = np.concatenate([values[blocks[i]] for i in selected])[:n]
        means.append(float(resample.mean()))
    lo, hi = np.percentile(means, [5, 95])
    return {
        "lower_5pct": float(lo),
        "upper_95pct": float(hi),
        "replicates": 500,
        "block_sessions": 20,
        "seed": 20261009,
        "contiguous_runs": len(eligible),
        "independent_confidence": False,
        "assumption": "APPROXIMATE_LOCAL_STATIONARITY; GLOBAL_REGIME_CHANGES_LIMIT_INTERPRETATION",
    }


def evaluate(
    scores: Array,
    targets: Array,
    indices: list[int],
    dates: list[str],
    codes: list[str],
    block_end: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if (
        len(indices) != len(scores)
        or scores.shape != targets.shape
        or not np.isfinite(scores).all()
        or not np.isfinite(targets).all()
    ):
        raise ValueError("COMPLETE_MATCHED_CROSS_SECTIONS_REQUIRED")
    ic = rank_rows(scores, targets)
    spread = np.full(len(scores), np.nan)
    top_return, bottom_return = np.full(len(scores), np.nan), np.full(len(scores), np.nan)
    top_count, bottom_count = np.zeros(len(codes)), np.zeros(len(codes))
    top_turn, bottom_turn, persistence = [], [], []
    previous: tuple[set[int], set[int], int, Array] | None = None
    tied, overlap, undefined = 0, 0, 0
    for k, score in enumerate(scores):
        if np.ptp(score) == 0:
            undefined += 1
            previous = None
            continue
        top, bottom = extremes(score, codes)
        top_set, bottom_set = set(top.tolist()), set(bottom.tolist())
        tied += int(len(set(score.tolist())) < len(score))
        if top_set & bottom_set:
            overlap += 1
            previous = None
            continue
        top_return[k], bottom_return[k] = targets[k, top].mean(), targets[k, bottom].mean()
        spread[k] = top_return[k] - bottom_return[k]
        top_count[top] += 1
        bottom_count[bottom] += 1
        if previous is not None and previous[2] + 1 == indices[k]:
            top_turn.append(1 - len(top_set & previous[0]) / 5)
            bottom_turn.append(1 - len(bottom_set & previous[1]) / 5)
            persistence.append(float(rank_rows(score[None, :], previous[3][None, :])[0]))
        previous = top_set, bottom_set, indices[k], score
    row_dates = [dates[i] for i in indices]
    blocks = calendar_blocks(row_dates, "2023-08-02", block_end)
    per_block: list[dict[str, Any]] = [
        {
            "block": b + 1,
            "signals": blocks.count(b),
            "rank_ic": stats(ic[np.asarray(blocks) == b]),
            "spread": stats(spread[np.asarray(blocks) == b]),
        }
        for b in range(4)
    ]
    leave_one_out = []
    for excluded, code in enumerate(codes):
        keep = [i for i in range(len(codes)) if i != excluded]
        leave_one_out.append(
            {
                "excluded_identity": code,
                "rank_ic": stats(rank_rows(scores[:, keep], targets[:, keep])),
            }
        )

    def selection(counts: Array) -> dict[str, Any]:
        total = counts.sum()
        shares = counts / total if total else np.zeros_like(counts)
        return {
            "hhi": float(np.sum(shares * shares)) if total else None,
            "maximum_share": float(shares.max()) if total else None,
            "all_industries": [
                {"identity": c, "count": int(n), "share": float(s) if total else None}
                for c, n, s in zip(codes, counts, shares, strict=True)
            ],
        }

    summary = {
        "signal_count": len(indices),
        "first_signal": row_dates[0] if row_dates else None,
        "last_signal": row_dates[-1] if row_dates else None,
        "rank_ic": stats(ic),
        "raw_top5_minus_bottom5_spread": stats(spread),
        "top5_raw_return": stats(top_return),
        "bottom5_raw_return": stats(bottom_return),
        "calendar_blocks": per_block,
        "positive_blocks": sum(
            v["rank_ic"]["mean"] is not None and v["rank_ic"]["mean"] > 0 for v in per_block
        ),
        "turnover": {
            "top5": stats(top_turn),
            "bottom5": stats(bottom_turn),
            "adjacent_session_rank_persistence": stats(persistence),
        },
        "selection_concentration": {
            "top5": selection(top_count),
            "bottom5": selection(bottom_count),
        },
        "leave_one_industry_out": leave_one_out,
        "tied_cross_sections": tied,
        "overlapping_tie_groups": overlap,
        "undefined_constant_rankings": undefined,
        "dependence": {
            "rank_ic_autocorrelation": {
                str(lag): autocorrelation(ic, indices, lag) for lag in (1, 5, 10, 20)
            },
            "descriptive_block_interval": block_interval(ic, indices),
        },
    }
    private = {"indices": indices, "rank_ic": ic, "spread": spread, "scores": scores}
    return summary, private


def paired(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    a = {i: k for k, i in enumerate(first["indices"])}
    b = {i: k for k, i in enumerate(second["indices"])}
    common = sorted(a.keys() & b.keys())
    return {
        "matched_signal_count": len(common),
        "delta_rank_ic": stats([first["rank_ic"][a[i]] - second["rank_ic"][b[i]] for i in common]),
        "delta_raw_spread": stats([first["spread"][a[i]] - second["spread"][b[i]] for i in common]),
        "comparison": "EXPLORATORY_INFORMED_COMPARISON",
        "date_matching": "EXACT",
    }


def market_states(returns: Array) -> tuple[list[str], Array]:
    states, dimensions = ["UNAVAILABLE"] * len(returns), np.full(len(returns), np.nan)
    dispersion = np.full(len(returns), np.nan)
    for t in range(20, len(returns)):
        window = returns[t - 19 : t + 1]
        if not np.isfinite(window).all():
            continue
        trend = float(np.prod(1 + window.mean(axis=1)) - 1)
        dispersion[t] = float(window.std(axis=1, ddof=0).mean())
        prior = dispersion[:t][np.isfinite(dispersion[:t])]
        if len(prior):
            states[t] = ("UP" if trend >= 0 else "DOWN") + (
                "_HIGH" if dispersion[t] >= np.median(prior) else "_LOW"
            )
        if t >= 60:
            covariance = np.cov(returns[t - 59 : t + 1], rowvar=False)
            eigen = np.maximum(np.linalg.eigvalsh(covariance), 0)
            if np.sum(eigen * eigen) > 0:
                dimensions[t] = np.sum(eigen) ** 2 / np.sum(eigen * eigen)
    return states, dimensions
