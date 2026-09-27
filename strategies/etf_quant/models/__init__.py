"""Independent, explicit-input Ridge models. No I/O, preprocessing or runner."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Sequence

import numpy as np
import pandas as pd

from ..domain import Horizon, HorizonModelSpec, ModelPrediction, TradingCalendar, finite, identifier, session, timestamp


class NumPyRidge:
    """Established centered augmented least-squares objective.

    ||Xw+b-y||² + alpha||w||²; intercept unpenalized, raw X, no scaling.
    Ported from baseline NumPyRidge without importing/modifying frozen code.
    """
    def __init__(self, alpha=0.01, fit_intercept=True):
        self.alpha = finite(alpha, "alpha")
        if self.alpha < 0 or type(fit_intercept) is not bool: raise ValueError("invalid Ridge parameters")
        self.fit_intercept = fit_intercept
        self.coef_ = None
        self.intercept_ = 0.0
        self.n_features_in_ = None

    def fit(self, X, y):
        self.coef_, self.intercept_, self.n_features_in_ = None, 0.0, None
        X, y = np.asarray(X, dtype=float), np.asarray(y, dtype=float)
        if (X.ndim != 2 or y.ndim != 1 or not X.shape[0] or not X.shape[1]
                or X.shape[0] != y.shape[0] or not np.isfinite(X).all() or not np.isfinite(y).all()):
            raise ValueError("finite nonempty X matrix / matching y vector required")
        n = X.shape[1]
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                xm = X.mean(axis=0) if self.fit_intercept else np.zeros(n)
                ym = y.mean() if self.fit_intercept else 0.0
                xc, yc = X - xm, y - ym
                A, b = xc, yc
                if self.alpha > 0:
                    A = np.vstack((xc, np.sqrt(self.alpha) * np.eye(n)))
                    b = np.concatenate((yc, np.zeros(n)))
                coef, _, rank, _ = np.linalg.lstsq(A, b, rcond=None)
                if self.alpha > 0 and rank < n: raise ValueError("unreliable numerical feature rank")
                intercept = float(ym - xm @ coef)
                fitted = X @ coef + intercept
                if not np.isfinite(coef).all() or not np.isfinite(intercept) or not np.isfinite(fitted).all():
                    raise ValueError("nonfinite Ridge solution")
        except (FloatingPointError, np.linalg.LinAlgError) as error:
            raise ValueError("Ridge numerical solve failed") from error
        self.coef_, self.intercept_, self.n_features_in_ = coef, intercept, n
        return self

    def predict(self, X):
        if self.coef_ is None: raise RuntimeError("Ridge not fitted")
        X = np.asarray(X, dtype=float)
        if X.ndim == 1: X = X.reshape(1, -1)
        if X.ndim != 2 or X.shape[1] != self.n_features_in_ or not np.isfinite(X).all():
            raise ValueError("finite prediction matrix with matching feature order required")
        try:
            with np.errstate(over="raise", invalid="raise"):
                result = X @ self.coef_ + self.intercept_
        except FloatingPointError as error:
            raise ValueError("prediction overflow") from error
        if not np.isfinite(result).all(): raise ValueError("nonfinite prediction")
        return result


@dataclass(frozen=True)
class TrainingObservation:
    horizon: Horizon
    industry_code: str
    observation_date: date
    label_end: date | None
    available_at: datetime | None
    factor_names: tuple[str, ...]
    features: tuple[float, ...]
    raw_forward_return: float


@dataclass(frozen=True)
class TrainingMetadata:
    horizon: Horizon
    factor_names: tuple[str, ...]
    alpha: float
    training_window_months: int
    window_start: date
    label_cutoff: date
    training_start: date
    training_end: date
    training_day_count: int
    sample_count: int
    signal_at: datetime
    target_identity: str
    feature_preprocessing: str = "NONE_RAW_X_NO_TRAIN_STANDARDIZATION"

    def __post_init__(self):
        spec = HorizonModelSpec(self.horizon, self.factor_names, self.alpha,
                                self.training_window_months, target_identity=self.target_identity)
        timestamp(self.signal_at)
        for day in (self.window_start, self.label_cutoff, self.training_start, self.training_end):
            session(day)
        if (not self.window_start <= self.training_start <= self.training_end <= self.label_cutoff < self.signal_at.date()
                or self.window_start != (pd.Timestamp(self.label_cutoff) - pd.DateOffset(months=6)).date()
                or type(self.training_day_count) is not int or self.training_day_count < spec.minimum_valid_training_days
                or type(self.sample_count) is not int or self.sample_count < self.training_day_count
                or self.feature_preprocessing != "NONE_RAW_X_NO_TRAIN_STANDARDIZATION"):
            raise ValueError("invalid training metadata / frozen window identity")


@dataclass(frozen=True)
class FittedHorizonModel:
    spec: HorizonModelSpec
    coefficients: tuple[float, ...]
    intercept: float
    training: TrainingMetadata

    def __post_init__(self):
        if (not isinstance(self.spec, HorizonModelSpec) or not isinstance(self.training, TrainingMetadata)
                or type(self.coefficients) is not tuple or len(self.coefficients) != len(self.spec.factor_names)
                or self.training.horizon is not self.spec.horizon
                or self.training.factor_names != self.spec.factor_names
                or self.training.alpha != self.spec.alpha
                or self.training.training_window_months != self.spec.training_window_months
                or self.training.target_identity != self.spec.target_identity):
            raise ValueError("fitted model feature / training identity mismatch")
        for value in self.coefficients: finite(value, "coefficient")
        finite(self.intercept, "intercept")

    @property
    def named_coefficients(self) -> tuple[tuple[str, float], ...]:
        return tuple(zip(self.spec.factor_names, self.coefficients))


def fit_horizon(spec: HorizonModelSpec, observations: Sequence[TrainingObservation], *,
                calendar: TradingCalendar, signal_at: datetime,
                industry_universe: Sequence[str]) -> FittedHorizonModel:
    """Pure fit on explicit observations, never a walk-forward/data pipeline.

    Window anchored to per-horizon label cutoff, not signal minus six months.
    Require full explicit universe on each accepted date and known availability;
    no fill, imputation, partial cross-sectional centering or label manufacture.
    Caller must supply source/evidence-backed availability in a future adapter.
    """
    if not isinstance(spec, HorizonModelSpec) or not isinstance(calendar, TradingCalendar):
        raise ValueError("explicit frozen model specification / calendar required")
    timestamp(signal_at)
    days = calendar.sessions
    if signal_at.date() not in days: raise ValueError("signal not in supplied calendar")
    signal_i = days.index(signal_at.date())
    h = int(spec.horizon)
    if signal_i < h: raise ValueError("insufficient historical calendar")
    cutoff = days[signal_i - h]
    start = (pd.Timestamp(cutoff) - pd.DateOffset(months=spec.training_window_months)).date()
    universe = tuple(sorted(industry_universe))
    if not universe or len(set(universe)) != len(universe): raise ValueError("explicit unique universe required")
    for code in universe: identifier(code)
    positions = {day: i for i, day in enumerate(days)}
    accepted = {}
    for row in observations:
        if not isinstance(row, TrainingObservation) or row.horizon is not spec.horizon:
            raise ValueError("horizon observation mismatch")
        session(row.observation_date)
        if row.observation_date not in positions: raise ValueError("observation outside supplied calendar")
        # Only date tokens are examined before rejecting outside/unmatured rows.
        if not start <= row.observation_date <= cutoff: continue
        expected_end = days[positions[row.observation_date] + h]
        if row.label_end != expected_end: raise ValueError("label-end maturity evidence mismatch")
        if row.available_at is None: raise ValueError("training availability UNKNOWN")
        timestamp(row.available_at)
        if row.available_at.date() < expected_end: raise ValueError("label marked available before maturity")
        if row.available_at > signal_at: raise ValueError("unavailable training label")
        if (row.industry_code not in universe or row.factor_names != spec.factor_names
                or type(row.factor_names) is not tuple or type(row.features) is not tuple
                or len(row.features) != len(spec.factor_names)):
            raise ValueError("training universe / feature schema/order mismatch")
        for x in row.features: finite(x, "training feature")
        finite(row.raw_forward_return, "training target")
        group = accepted.setdefault(row.observation_date, {})
        if row.industry_code in group: raise ValueError("duplicate date-industry sample")
        group[row.industry_code] = row
    if any(set(group) != set(universe) for group in accepted.values()):
        raise ValueError("incomplete training cross-section; no partial target centering")
    if len(accepted) < spec.minimum_valid_training_days:
        raise ValueError("INSUFFICIENT_VALID_TRAINING_DAYS")
    X, y = [], []
    for day in sorted(accepted):
        rows = [accepted[day][code] for code in universe]
        raw = np.asarray([r.raw_forward_return for r in rows])
        with np.errstate(over="raise", invalid="raise"):
            excess = raw - raw.mean()
        X.extend(r.features for r in rows)
        y.extend(excess)
    model = NumPyRidge(alpha=spec.alpha).fit(X, y)
    metadata = TrainingMetadata(spec.horizon, spec.factor_names, spec.alpha,
        spec.training_window_months, start, cutoff, min(accepted), max(accepted),
        len(accepted), len(y), signal_at, spec.target_identity)
    return FittedHorizonModel(spec, tuple(map(float, model.coef_)), model.intercept_, metadata)


def predict_industries(model: FittedHorizonModel, features: dict[str, tuple[float, ...]], *,
                       factor_names: tuple[str, ...], signal_date: date) -> tuple[ModelPrediction, ...]:
    session(signal_date)
    if signal_date != model.training.signal_at.date() or factor_names != model.spec.factor_names:
        raise ValueError("prediction date / feature order mismatch")
    if not features: raise ValueError("explicit prediction universe required")
    result = []
    for code, values in sorted(features.items()):
        identifier(code)
        if len(values) != len(factor_names): raise ValueError("feature count mismatch")
        X = np.asarray([finite(x, "prediction feature") for x in values])
        with np.errstate(over="raise", invalid="raise"):
            score = float(X @ np.asarray(model.coefficients) + model.intercept)
        result.append(ModelPrediction(model.spec.horizon, signal_date, code, score))
    return tuple(result)
