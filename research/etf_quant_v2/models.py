"""V2 pure model fits using the frozen numerical solver and prediction z-score.

There is deliberately no file/provider/runtime entry point. An admitted factual
adapter must supply dated availability, complete universes and membership proofs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

import numpy as np

from strategies.etf_quant.models import NumPyRidge
from strategies.etf_quant.models.fusion import cross_sectional_zscore

from .diagnostics import Standardization
from .protocol import (
    Candidate,
    MembershipEvidence,
    Split,
    canonical_hash,
    training_indices,
    validate_candidate,
)


@dataclass(frozen=True)
class Observation:
    day: date
    industry: str
    features: tuple[float, ...]
    factor_names: tuple[str, ...]
    feature_available_at: datetime
    membership: MembershipEvidence
    label_end: date
    label_available_at: datetime
    raw_forward_return: float


@dataclass(frozen=True)
class Fit:
    coefficients: tuple[float, ...]
    intercept: float
    preprocessing: Standardization | None
    training_dates: tuple[date, ...]
    candidate_id: str
    horizon: int

    def predict(self, values: Sequence[Sequence[float]]) -> tuple[float, ...]:
        x = np.asarray(values, dtype=np.float64)
        if self.preprocessing is not None:
            x = self.preprocessing.apply(x)
        if x.ndim != 2 or x.shape[1] != len(self.coefficients) or not np.isfinite(x).all():
            raise ValueError("FINITE_MATCHING_FEATURES_REQUIRED")
        with np.errstate(over="raise", invalid="raise"):
            predictions = x @ np.asarray(self.coefficients) + self.intercept
        if not np.isfinite(predictions).all():
            raise ValueError("NONFINITE_PREDICTION")
        return tuple(map(float, predictions))


def fit(
    candidate: Candidate,
    horizon: int,
    rows: Sequence[Observation],
    *,
    sessions: Sequence[date],
    signal_at: datetime,
    split: Split,
    universe_by_date: Mapping[date, tuple[str, ...]],
) -> Fit:
    """Training-only scaling and mature labels in complete dated cross sections."""
    split.guard(signal_at.date())
    validate_candidate(candidate)
    factors = candidate.factors(horizon)
    if signal_at.tzinfo is None or signal_at.utcoffset() is None:
        raise ValueError("SIGNAL_TIMEZONE_REQUIRED")
    indices = training_indices(sessions, signal_at.date(), horizon, candidate.training_months)
    accepted_days = {sessions[i] for i in indices}
    positions = {day: i for i, day in enumerate(sessions)}
    by_date: dict[date, dict[str, Observation]] = {}
    for row in rows:
        # Dates gate access to the remaining payload, including target values.
        if row.day not in accepted_days:
            continue
        split.guard(row.day, row.label_end)
        if row.label_end != sessions[positions[row.day] + horizon]:
            raise ValueError("LABEL_MATURITY_MISMATCH")
        if any(
            t.tzinfo is None or t.utcoffset() is None
            for t in (row.feature_available_at, row.label_available_at)
        ):
            raise ValueError("AVAILABILITY_TIMEZONE_REQUIRED")
        feature_decision = signal_at.replace(
            year=row.day.year, month=row.day.month, day=row.day.day
        )
        row.membership.admit(feature_decision)
        if row.feature_available_at > feature_decision or row.label_available_at > signal_at:
            raise ValueError("FUTURE_TRAINING_INFORMATION")
        if row.factor_names != factors or len(row.features) != len(factors):
            raise ValueError("FROZEN_FACTOR_VOCABULARY_MISMATCH")
        if not np.isfinite(row.features).all() or not np.isfinite(row.raw_forward_return):
            raise ValueError("MISSING_TRAINING_VALUES")
        group = by_date.setdefault(row.day, {})
        if row.industry in group:
            raise ValueError("DUPLICATE_TRAINING_OBSERVATION")
        group[row.industry] = row
    x: list[tuple[float, ...]] = []
    y: list[float] = []
    for day, group in sorted(by_date.items()):
        universe = universe_by_date.get(day)
        if not universe or len(set(universe)) != len(universe) or set(group) != set(universe):
            raise ValueError("COMPLETE_DATED_UNIVERSE_REQUIRED")
        ordered = [group[code] for code in sorted(universe)]
        targets = np.asarray([row.raw_forward_return for row in ordered])
        # Same-date excess target is the frozen ETF factor/model vocabulary.
        targets -= targets.mean()
        x.extend(row.features for row in ordered)
        y.extend(map(float, targets))
    if len(by_date) < 30:
        raise ValueError("INSUFFICIENT_MATURED_TRAINING_DATES")
    preprocessing = (
        Standardization.fit(x) if candidate.scaling == "TRAIN_ONLY_STANDARDIZED" else None
    )
    train = preprocessing.apply(x) if preprocessing else np.asarray(x, dtype=np.float64)
    model = NumPyRidge(alpha=candidate.alpha).fit(train, y)
    return Fit(
        tuple(map(float, model.coef_)),
        model.intercept_,
        preprocessing,
        tuple(sorted(by_date)),
        candidate.identifier,
        horizon,
    )


def fuse(
    candidate: Candidate, scores: Mapping[int, Mapping[str, float]], *, universe: tuple[str, ...]
) -> tuple[tuple[str, float], ...]:
    """Generic registered horizons; deterministic complete-universe fusion."""
    validate_candidate(candidate)
    if (
        len(universe) < 5
        or len(set(universe)) != len(universe)
        or set(scores) != set(candidate.horizons)
    ):
        raise ValueError("COMPLETE_HORIZON_UNIVERSE_REQUIRED")
    ordered = tuple(sorted(universe))
    fused = np.zeros(len(ordered))
    for horizon, weight in zip(candidate.horizons, candidate.fusion, strict=True):
        if set(scores[horizon]) != set(ordered):
            raise ValueError("HORIZON_UNIVERSE_MISMATCH")
        fused += weight * cross_sectional_zscore([scores[horizon][code] for code in ordered])
    fused /= sum(candidate.fusion)
    return tuple(sorted(zip(ordered, map(float, fused)), key=lambda item: (-item[1], item[0])))


def cache_identity(
    snapshot_hash: str,
    factor_hash: str,
    date_range: tuple[str, str],
    preprocessing: Mapping[str, object],
) -> str:
    """Content-addressed intermediates cannot cross snapshot or preprocessing scope."""
    for value in (snapshot_hash, factor_hash):
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("CACHE_PROVENANCE_REQUIRED")
    if date_range[0] > date_range[1]:
        raise ValueError("CACHE_DATE_RANGE_REQUIRED")
    return canonical_hash(
        {
            "data_snapshot": snapshot_hash,
            "factor_spec": factor_hash,
            "date_range": date_range,
            "preprocessing": preprocessing,
        }
    )
