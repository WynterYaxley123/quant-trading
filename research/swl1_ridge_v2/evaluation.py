"""Descriptive diagnostics with recorded drops, calendar blocks and symmetric ties."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np

from research.swl1_ridge_v1.evaluation import rank_ic
from research.swl1_ridge_v1.protocol import HORIZONS, WEIGHTS, body, digest, exact_targets

from .protocol import Spec, fit_predict

BLOCKS = 4
DEVELOPMENT_FLOOR = -0.02


def extremes(prediction: np.ndarray, codes: list[str], count: int = 5) -> tuple[Any, Any]:
    """Top and bottom both break score ties by ascending industry code."""
    code = np.asarray(codes)
    top = np.lexsort((code, -prediction))[:count]
    bottom = np.lexsort((code, prediction))[:count]
    return top, bottom


def public_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Per-fit trace is private; preserve aggregate actual alpha and its byte hash."""
    return {key: value for key, value in metrics.items() if key != "fit_records"}


def calendar_blocks(row_dates: list[str], start: str, end: str) -> list[int]:
    """Equal calendar-duration blocks over the phase's registered signal range."""
    first, span = (
        date.fromisoformat(start),
        (date.fromisoformat(end) - date.fromisoformat(start)).days,
    )
    if span <= 0:
        return [0] * len(row_dates)
    return [
        min(BLOCKS - 1, (date.fromisoformat(d) - first).days * BLOCKS // span) for d in row_dates
    ]


def summarize(
    rows: list[dict[str, Any]],
    dropped: list[dict[str, str]],
    required_count: int,
    start: str,
    end: str,
) -> dict[str, Any]:
    per_horizon: dict[str, Any] = {}
    for h in HORIZONS:
        values = [r["horizons"][str(h)] for r in rows]
        ic = [v["rank_ic"] for v in values]
        per_horizon[str(h)] = {
            "mean_rank_ic": float(np.mean(ic)) if ic else None,
            "median_rank_ic": float(np.median(ic)) if ic else None,
            "positive_fraction": float(np.mean(np.asarray(ic) > 0)) if ic else None,
            "top5_return": float(np.mean([v["top5"] for v in values])) if values else None,
            "bottom5_return": float(np.mean([v["bottom5"] for v in values])) if values else None,
            "spread": float(np.mean([v["spread"] for v in values])) if values else None,
        }
    composite = [
        sum(w * r["horizons"][str(h)]["rank_ic"] for h, w in zip(HORIZONS, WEIGHTS, strict=True))
        for r in rows
    ]
    assignment = calendar_blocks([r["date"] for r in rows], start, end)
    blocks = []
    for k in range(BLOCKS):
        group = [c for c, b in zip(composite, assignment, strict=True) if b == k]
        blocks.append(float(np.mean(group)) if group else None)

    def weighted(key: str) -> float | None:
        if not rows:
            return None
        return float(
            sum(w * per_horizon[str(h)][key] for h, w in zip(HORIZONS, WEIGHTS, strict=True))
        )

    return {
        "signal_count": len(rows),
        "required_signal_count": required_count,
        "sufficient_dates": len(rows) >= max(30, int(np.ceil(required_count * 0.9))),
        "dropped_signals": dropped,
        "horizons": per_horizon,
        "composite_rank_ic": float(np.mean(composite)) if rows else None,
        "median_composite_rank_ic": float(np.median(composite)) if rows else None,
        "weighted_positive_fraction": weighted("positive_fraction"),
        "weighted_spread": weighted("spread"),
        "block_partition": "EQUAL_CALENDAR_DURATION",
        "block_composite_rank_ic": blocks,
        "block_signal_counts": [assignment.count(k) for k in range(BLOCKS)],
        "positive_blocks": sum(x is not None and x > 0 for x in blocks),
        "independent_statistical_confidence": "LIMITED",
        "dependence": "TEMPORALLY_DEPENDENT_OVERLAPPING_HORIZONS",
    }


def development_admitted(metrics: dict[str, Any]) -> bool:
    """V1 floors plus the stability V1 required only at Validation."""
    means = [metrics["horizons"][str(h)]["mean_rank_ic"] for h in HORIZONS]
    return bool(
        metrics["sufficient_dates"]
        and all(m is not None and m >= DEVELOPMENT_FLOOR for m in means)
        and metrics["positive_blocks"] >= 3
    )


def evaluate(
    features: np.ndarray,
    returns: np.ndarray,
    dates: list[str],
    codes: list[str],
    signals: list[int],
    spec: Spec,
    phase: str = "synthetic",
) -> dict[str, Any]:
    """Only the phase's factual maturity prefix is turned into labels."""
    last_maturity = max(signals) + max(HORIZONS)
    targets = {h: exact_targets(returns[: last_maturity + 1], h) for h in HORIZONS}
    rows: list[dict[str, Any]] = []
    dropped: list[dict[str, str]] = []
    fits: list[dict[str, Any]] = []
    for index in signals:
        parts = {}
        horizon = "evaluation"
        try:
            for h in HORIZONS:
                horizon = str(h)
                prediction, metadata = fit_predict(features, targets[h], dates, index, h, spec)
                fits.append(
                    {
                        "signal_date": dates[index],
                        "phase": phase,
                        "spec": spec.identifier,
                        "horizon": h,
                        **metadata,
                    }
                )
                actual = targets[h][index]
                if not np.isfinite(actual).all():
                    raise ValueError("INCOMPLETE_FIXED_UNIVERSE_TARGET")
                ic = rank_ic(prediction, actual)
                if ic is None:
                    raise ValueError("CONSTANT_CROSS_SECTION")
                top, bottom = extremes(prediction, codes)
                parts[str(h)] = {
                    "rank_ic": ic,
                    "top5": float(np.mean(actual[top])),
                    "bottom5": float(np.mean(actual[bottom])),
                    "spread": float(np.mean(actual[top]) - np.mean(actual[bottom])),
                }
        except ValueError as error:
            dropped.append(
                {
                    "signal_date": dates[index],
                    "phase": phase,
                    "spec": spec.identifier,
                    "horizon": horizon,
                    "reason_code": str(error),
                }
            )
            continue
        rows.append({"date": dates[index], "horizons": parts})
    if len(rows) + len(dropped) != len(signals):
        raise ValueError("SIGNAL_ACCOUNTING_MISMATCH")
    metrics = summarize(rows, dropped, len(signals), dates[signals[0]], dates[signals[-1]])
    metrics["fit_records"] = fits
    metrics["fit_records_sha256"] = digest(body(fits))
    metrics["fit_count"] = len(fits)
    metrics["ridge_alpha_by_horizon"] = {
        str(h): {
            "minimum": min(values) if values else None,
            "maximum": max(values) if values else None,
            "fits": len(values),
        }
        for h in HORIZONS
        for values in [[f["ridge_alpha"] for f in fits if f["horizon"] == h]]
    }
    return metrics
