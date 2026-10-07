"""Descriptive forward evidence; overlapping horizons receive no significance claims."""

from __future__ import annotations

from statistics import mean, median
from typing import Any

import numpy as np
import pandas as pd

from .adapter import ranks

ROLLING_DATES = 20
FIELDS = (
    "rank_ic",
    "top5_mean_return",
    "bottom5_mean_return",
    "top5_bottom5_spread",
    "universe_mean_return",
    "top5_overlap_count",
    "top5_overlap_rate",
    "mean_absolute_rank_error",
    "median_absolute_rank_error",
)


def evaluate(
    cross_section: list[dict[str, Any]],
    raw: dict[str, float],
    horizon: int,
    *,
    comparison_only: bool = False,
) -> dict[str, Any]:
    codes = sorted(raw)
    if set(codes) != {r["industry_code"] for r in cross_section} or len(codes) < 10:
        raise ValueError("FULL_REALIZED_CROSS_SECTION_REQUIRED")
    if not np.isfinite(list(raw.values())).all():
        raise ValueError("FINITE_REALIZED_RETURNS_REQUIRED")
    predictions = {
        r["industry_code"]: r["horizons"][str(horizon)]["raw_prediction"] for r in cross_section
    }
    centered = {c: raw[c] - mean(raw.values()) for c in codes}
    # Scientific labels are frozen same-date excess industry returns.
    left = pd.Series([predictions[c] for c in codes]).rank(method="average")
    rank_target = raw if comparison_only else centered
    right = pd.Series([rank_target[c] for c in codes]).rank(method="average")
    ic = float(left.corr(right)) if left.nunique() > 1 and right.nunique() > 1 else None
    predicted_rank, realized_rank = ranks(predictions), ranks(raw)
    ordered = sorted(codes, key=lambda c: predicted_rank[c])
    top, bottom = ordered[:5], ordered[-5:]
    actual = sorted(codes, key=lambda c: realized_rank[c])[:5]
    errors = [abs(predicted_rank[c] - realized_rank[c]) for c in codes]
    fused_top = sorted(cross_section, key=lambda r: r["fused_rank"])[:5]
    top_mean, bottom_mean = mean(raw[c] for c in top), mean(raw[c] for c in bottom)
    return {
        "horizon": horizon,
        "rank_ic": ic,
        "top5_mean_return": top_mean,
        "bottom5_mean_return": bottom_mean,
        "top5_bottom5_spread": top_mean - bottom_mean,
        "universe_mean_return": mean(raw.values()),
        "predicted_top5": top,
        "actual_top5": actual,
        "top5_overlap_count": len(set(top) & set(actual)),
        "top5_overlap_rate": len(set(top) & set(actual)) / 5,
        "mean_absolute_rank_error": mean(errors),
        "median_absolute_rank_error": median(errors),
        "fused_top5_mean_return": mean(raw[r["industry_code"]] for r in fused_top),
        "diagnostic_label": "NON_TRADABLE_RESEARCH_DIAGNOSTIC",
        "scientific_target": "SAME_DATE_CROSS_SECTION_EXCESS_INDUSTRY_RETURN",
        "realized": [
            {
                "industry_code": c,
                "predicted_rank": predicted_rank[c],
                "forecast_score": predictions[c],
                "realized_rank": realized_rank[c],
                "realized_return": raw[c],
                "scientific_target": centered[c],
            }
            for c in codes
        ],
    }


def aggregate(events: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    selected = sorted(
        (e for e in events if e["horizon"] == horizon), key=lambda e: e["signal_date"]
    )
    ics = [e["metrics"]["rank_ic"] for e in selected if e["metrics"]["rank_ic"] is not None]
    rolling = []
    for end in range(ROLLING_DATES, len(selected) + 1):
        block = selected[end - ROLLING_DATES : end]
        values = [e["metrics"]["rank_ic"] for e in block]
        rolling.append(
            {
                "from": block[0]["signal_date"],
                "through": block[-1]["signal_date"],
                "rank_ic": mean(values) if all(v is not None for v in values) else None,
                "spread": mean(e["metrics"]["top5_bottom5_spread"] for e in block),
            }
        )
    return {
        "horizon": horizon,
        "matured_forecast_dates": len(selected),
        "valid_rank_ic_dates": len(ics),
        "mean_rank_ic": mean(ics) if ics else None,
        "median_rank_ic": median(ics) if ics else None,
        "positive_rank_ic_fraction": mean(v > 0 for v in ics) if ics else None,
        **{
            key: mean(e["metrics"][key] for e in selected) if selected else None
            for key in FIELDS[1:]
        },
        "confidence_status": "INSUFFICIENT_FORWARD_EVIDENCE"
        if len(selected) < ROLLING_DATES
        else "DESCRIPTIVE_ONLY_OVERLAPPING_OBSERVATIONS",
        "rolling_window_dates": ROLLING_DATES,
        "rolling": rolling,
        "worst_rolling_interval": min(rolling, key=lambda r: r["spread"]) if rolling else None,
    }


def compare(
    first: list[dict[str, Any]], second: list[dict[str, Any]], horizon: int
) -> dict[str, Any]:
    a = {e["signal_date"]: e for e in first if e["horizon"] == horizon}
    b = {e["signal_date"]: e for e in second if e["horizon"] == horizon}
    common = sorted(a.keys() & b.keys())
    adjusted_a: list[dict[str, Any]] = []
    adjusted_b: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for day in common:
        identity_keys = ("taxonomy_identity", "realized_series_type", "target_contract")
        if any(a[day][k] != b[day][k] for k in identity_keys):
            raise ValueError("COMMON_FORWARD_TARGET_MISMATCH")
        actual_a = {r["industry_code"]: r for r in a[day]["metrics"]["realized"]}
        actual_b = {r["industry_code"]: r for r in b[day]["metrics"]["realized"]}
        codes = sorted(actual_a.keys() & actual_b.keys())
        if len(codes) < 10 or any(
            not np.isclose(
                actual_a[c]["realized_return"],
                actual_b[c]["realized_return"],
                rtol=1e-10,
                atol=1e-12,
            )
            for c in codes
        ):
            raise ValueError("COMMON_FORWARD_TARGET_MISMATCH")
        counts[day] = len(codes)
        raw = {c: actual_a[c]["realized_return"] for c in codes}
        for source, values, destination in ((a, actual_a, adjusted_a), (b, actual_b, adjusted_b)):
            rank = ranks({c: values[c]["forecast_score"] for c in codes})
            rows = [
                {
                    "industry_code": c,
                    "fused_rank": rank[c],
                    "horizons": {str(horizon): {"raw_prediction": values[c]["forecast_score"]}},
                }
                for c in codes
            ]
            destination.append(
                source[day] | {"metrics": evaluate(rows, raw, horizon, comparison_only=True)}
            )
    left, right = aggregate(adjusted_a, horizon), aggregate(adjusted_b, horizon)
    keys = (
        "mean_rank_ic",
        "median_rank_ic",
        "positive_rank_ic_fraction",
        "top5_bottom5_spread",
        "mean_absolute_rank_error",
        "median_absolute_rank_error",
        "top5_overlap_count",
        "top5_overlap_rate",
    )
    return {
        "scope": "COMMON_FORWARD_WINDOW",
        "metric_scope": "COMMON_INDUSTRY_CROSS_SECTION_DIAGNOSTIC",
        "common_industry_counts": counts,
        "raw_return_compatibility": "VERIFIED" if common else "NO_COMMON_MATURED_OBSERVATIONS",
        "centered_target_equality_required": False,
        "horizon": horizon,
        "matured_common_dates": common,
        "matured_common_date_count": len(common),
        "swl2_ridge_v1": {k: left[k] for k in keys},
        "swl2_ridge_v2": {k: right[k] for k in keys},
        "difference_v2_minus_v1": {
            k: right[k] - left[k] if left[k] is not None and right[k] is not None else None
            for k in keys
        },
        "confidence_status": "INSUFFICIENT_FORWARD_EVIDENCE"
        if len(common) < ROLLING_DATES
        else "DESCRIPTIVE_ONLY_OVERLAPPING_OBSERVATIONS",
    }
