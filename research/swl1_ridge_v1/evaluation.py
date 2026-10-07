"""Phase-bounded descriptive Ridge diagnostics; no trading or IID claims."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .protocol import HORIZONS, WEIGHTS, Spec, exact_targets, fit_predict


def rank_ic(prediction: np.ndarray, realized: np.ndarray) -> float | None:
    a = pd.Series(prediction).rank(method="average").to_numpy()
    b = pd.Series(realized).rank(method="average").to_numpy()
    if a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def summarize(rows: list[dict[str, Any]], required_count: int) -> dict[str, Any]:
    per_horizon: dict[str, Any] = {}
    for h in HORIZONS:
        ic = [r["horizons"][str(h)]["rank_ic"] for r in rows]
        spread = [r["horizons"][str(h)]["spread"] for r in rows]
        per_horizon[str(h)] = {
            "mean_rank_ic": float(np.mean(ic)) if ic else None,
            "median_rank_ic": float(np.median(ic)) if ic else None,
            "positive_fraction": float(np.mean(np.asarray(ic) > 0)) if ic else None,
            "top5_return": float(np.mean([r["horizons"][str(h)]["top5"] for r in rows]))
            if rows
            else None,
            "bottom5_return": float(np.mean([r["horizons"][str(h)]["bottom5"] for r in rows]))
            if rows
            else None,
            "spread": float(np.mean(spread)) if spread else None,
        }
    composite = [
        sum(w * r["horizons"][str(h)]["rank_ic"] for h, w in zip(HORIZONS, WEIGHTS, strict=True))
        for r in rows
    ]
    blocks = [
        float(np.mean(group)) if len(group) else None for group in np.array_split(composite, 4)
    ]

    def weighted(key: str) -> float | None:
        return (
            float(sum(w * per_horizon[str(h)][key] for h, w in zip(HORIZONS, WEIGHTS, strict=True)))
            if rows
            else None
        )

    return {
        "signal_count": len(rows),
        "required_signal_count": required_count,
        "sufficient_dates": len(rows) >= max(30, int(np.ceil(required_count * 0.9))),
        "horizons": per_horizon,
        "composite_rank_ic": float(np.mean(composite)) if rows else None,
        "median_composite_rank_ic": float(np.median(composite)) if rows else None,
        "weighted_positive_fraction": weighted("positive_fraction"),
        "weighted_spread": weighted("spread"),
        "block_composite_rank_ic": blocks,
        "positive_blocks": sum(x is not None and x > 0 for x in blocks),
        "independent_statistical_confidence": "LIMITED",
        "dependence": "TEMPORALLY_DEPENDENT_OVERLAPPING_HORIZONS",
    }


def validation_pass(metrics: dict[str, Any]) -> bool:
    if not metrics["sufficient_dates"] or metrics["composite_rank_ic"] is None:
        return False
    means = [metrics["horizons"][str(h)]["mean_rank_ic"] for h in HORIZONS]
    return bool(
        metrics["composite_rank_ic"] > 0
        and metrics["median_composite_rank_ic"] > 0
        and metrics["weighted_positive_fraction"] >= 0.55
        and metrics["weighted_spread"] > 0
        and sum(x > 0 for x in means) >= 2
        and min(means) >= -0.03
        and metrics["positive_blocks"] >= 3
    )


def directional_label(metrics: dict[str, Any]) -> str:
    if not metrics["sufficient_dates"] or metrics["composite_rank_ic"] is None:
        return "MIXED"
    means = [metrics["horizons"][str(h)]["mean_rank_ic"] for h in HORIZONS]
    if metrics["composite_rank_ic"] > 0 and metrics["weighted_spread"] > 0:
        if (
            min(means) > 0
            and metrics["weighted_positive_fraction"] >= 0.60
            and metrics["positive_blocks"] == 4
        ):
            return "STRONG_POSITIVE"
        if (
            sum(x > 0 for x in means) >= 2
            and metrics["weighted_positive_fraction"] >= 0.55
            and metrics["positive_blocks"] >= 3
        ):
            return "POSITIVE"
    negatives = [
        sum(x < 0 for x in means) >= 2,
        metrics["weighted_positive_fraction"] < 0.5,
        metrics["weighted_spread"] < 0,
        metrics["positive_blocks"] <= 1,
    ]
    return "NEGATIVE" if metrics["composite_rank_ic"] < 0 and sum(negatives) >= 3 else "MIXED"


def evaluate(
    features: np.ndarray,
    returns: np.ndarray,
    dates: list[str],
    codes: list[str],
    signals: list[int],
    spec: Spec,
) -> dict[str, Any]:
    """Only the phase's factual maturity prefix is turned into labels."""
    last_maturity = max(signals) + max(HORIZONS)
    targets = {h: exact_targets(returns[: last_maturity + 1], h) for h in HORIZONS}
    rows = []
    for index in signals:
        parts = {}
        try:
            for h in HORIZONS:
                prediction, _ = fit_predict(features, targets[h], dates, index, h, spec)
                actual = targets[h][index]
                if not np.isfinite(actual).all():
                    raise ValueError("INCOMPLETE_FIXED_UNIVERSE_TARGET")
                ic = rank_ic(prediction, actual)
                if ic is None:
                    raise ValueError("CONSTANT_CROSS_SECTION")
                order = np.lexsort((np.array(codes), -prediction))
                top, bottom = float(np.mean(actual[order[:5]])), float(np.mean(actual[order[-5:]]))
                parts[str(h)] = {
                    "rank_ic": ic,
                    "top5": top,
                    "bottom5": bottom,
                    "spread": top - bottom,
                }
            rows.append({"date": dates[index], "horizons": parts})
        except ValueError:
            continue
    return summarize(rows, len(signals))
