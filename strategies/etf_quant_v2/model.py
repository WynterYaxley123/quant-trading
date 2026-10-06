"""Frozen V2 numerical implementation extracted from the historical product runner.

Same fitting order, eligibility, excess labels, scaling and fusion; no product calls.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from strategies.etf_quant.config import FACTORS_19, H10_FACTORS
from strategies.etf_quant.models import NumPyRidge

SHANGHAI = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class FrozenSpecification:
    identifier: str
    horizons: tuple[int, ...]
    fusion: tuple[float, ...]
    alpha: float
    training_months: int
    scaling: str
    candidate_sha256: str
    frozen_at: datetime
    final_oos_start: date
    final_oos_end: date
    validated: bool
    final_oos_authorized: bool = False

    def __post_init__(self) -> None:
        if (
            not self.identifier
            or len(self.horizons) != len(self.fusion)
            or any(h not in (10, 40, 80, 120) for h in self.horizons)
            or len(set(self.horizons)) != len(self.horizons)
            or not math.isclose(sum(self.fusion), 1)
            or any(w <= 0 for w in self.fusion)
            or not math.isfinite(self.alpha)
            or self.alpha <= 0
            or self.training_months not in (6, 9, 12, 18, 24)
            or self.scaling not in ("RAW", "TRAIN_ONLY_STANDARDIZED")
            or len(self.candidate_sha256) != 64
            or self.frozen_at.tzinfo is None
            or self.final_oos_start > self.final_oos_end
        ):
            raise ValueError("INVALID_V2_FROZEN_SPECIFICATION")


@dataclass(frozen=True)
class Observation:
    industry: str
    day: date
    factors: tuple[float, ...]
    returns: Mapping[int, float]
    label_end: Mapping[int, date]
    observed_at: datetime
    evidence_tier: str


def predict_forecast(
    spec: FrozenSpecification,
    observations: Sequence[Observation],
    current_factors: Mapping[str, tuple[float, ...]],
    *,
    calendar: Sequence[date],
    signal_at: datetime,
    snapshot_available_at: datetime,
    finalized: bool,
    allow_unvalidated_research: bool = False,
) -> dict[str, Any]:
    """Fit coefficients from mature facts, then reuse frozen V1 execution functions."""
    if any(t.tzinfo is None for t in (signal_at, snapshot_available_at)):
        raise ValueError("FORWARD_TIMEZONE_REQUIRED")
    day = signal_at.astimezone(SHANGHAI).date()
    sessions = tuple(calendar)
    if (
        not finalized
        or sessions != tuple(sorted(set(sessions)))
        or day not in sessions
        or signal_at.astimezone(SHANGHAI).time() < time(15)
        or day <= spec.frozen_at.astimezone(SHANGHAI).date()
        or snapshot_available_at > signal_at
        or (not spec.validated and not allow_unvalidated_research)
    ):
        raise ValueError("GENUINE_FINALIZED_FORWARD_DATE_REQUIRED")
    positions = {session: i for i, session in enumerate(sessions)}
    index = positions[day]
    industries = sorted(current_factors)
    current = np.asarray([current_factors[i] for i in industries], dtype=float)
    if (
        current.shape != (len(industries), 19)
        or len(industries) < 12
        or not np.isfinite(current).all()
    ):
        raise ValueError("COMPLETE_CURRENT_FEATURE_CROSS_SECTION_REQUIRED")
    scores = np.zeros(len(industries))
    model_records = []
    components = {}
    for horizon, weight in zip(spec.horizons, spec.fusion, strict=True):
        if index < horizon:
            raise ValueError("MATURE_CALENDAR_HISTORY_REQUIRED")
        cutoff = sessions[index - horizon]
        window = (pd.Timestamp(cutoff) - pd.DateOffset(months=spec.training_months)).date()
        rows = [
            r
            for r in observations
            if window <= r.day <= cutoff
            and (
                spec.final_oos_authorized or not spec.final_oos_start <= r.day <= spec.final_oos_end
            )
        ]
        eligible = [
            r
            for r in rows
            if r.evidence_tier in ("A", "B", "C")
            and r.observed_at.tzinfo is not None
            and r.observed_at <= signal_at
            and horizon in r.returns
            and horizon in r.label_end
            and r.label_end[horizon] <= day
        ]
        for row in eligible:
            if row.day not in positions:
                raise ValueError("UNKNOWN_TRAINING_SESSION")
            maturity = positions[row.day] + horizon
            if maturity >= len(sessions) or row.label_end[horizon] != sessions[maturity]:
                raise ValueError("EXACT_HORIZON_MATURITY_REQUIRED")
            if (
                len(row.factors) != 19
                or not all(math.isfinite(v) for v in row.factors)
                or not math.isfinite(row.returns[horizon])
            ):
                raise ValueError("COMPLETE_FINITE_TRAINING_FACTS_REQUIRED")
        if len({r.day for r in eligible}) < 30:
            raise ValueError("INSUFFICIENT_MATURE_TRAINING")
        by_day: dict[date, list[Observation]] = {}
        for row in eligible:
            by_day.setdefault(row.day, []).append(row)
        if any(
            len({r.industry for r in values}) != len(values) or len(values) < 12
            for values in by_day.values()
        ):
            raise ValueError("COMPLETE_TRAINING_CROSS_SECTIONS_REQUIRED")
        names = H10_FACTORS if horizon == 10 else FACTORS_19
        columns = [FACTORS_19.index(n) for n in names]
        x = np.asarray([r.factors for r in eligible], dtype=float)[:, columns]
        centered_targets = {
            d: float(np.mean([r.returns[horizon] for r in values])) for d, values in by_day.items()
        }
        y = np.asarray([r.returns[horizon] - centered_targets[r.day] for r in eligible])
        mean, std = np.zeros(len(columns)), np.ones(len(columns))
        if spec.scaling == "TRAIN_ONLY_STANDARDIZED":
            mean, std = x.mean(axis=0), x.std(axis=0, ddof=0)
            if not np.isfinite(std).all() or (std <= 0).any():
                raise ValueError("ZERO_TRAIN_VARIANCE")
        fitted = NumPyRidge(spec.alpha).fit((x - mean) / std, y)
        predicted = fitted.predict((current[:, columns] - mean) / std)
        if float(predicted.std(ddof=0)) <= 1e-12:
            raise ValueError("DEGENERATE_CURRENT_PREDICTIONS")
        normalized = (predicted - predicted.mean()) / predicted.std(ddof=0)
        scores += weight * normalized
        components[str(horizon)] = {
            code: {"raw_prediction": float(raw), "cross_section_zscore": float(z)}
            for code, raw, z in zip(industries, predicted, normalized, strict=True)
        }
        model_records.append(
            {
                "horizon": horizon,
                "factors": list(names),
                "alpha": spec.alpha,
                "coefficients": fitted.coef_.tolist(),
                "intercept": fitted.intercept_,
                "training_means": mean.tolist(),
                "training_stds": std.tolist(),
                "label_cutoff": str(cutoff),
                "training_window_start": str(window),
                "training_dates": len(by_day),
                "training_samples": len(eligible),
            }
        )
    ranked = sorted(zip(industries, map(float, scores), strict=True), key=lambda r: (-r[1], r[0]))
    return {"rankings": ranked, "models": model_records, "components": components}
