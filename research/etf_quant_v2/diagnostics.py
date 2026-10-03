"""Structure-only Development diagnostics; no data loading or sealed access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from strategies.etf_quant.models import NumPyRidge

FloatArray = NDArray[np.float64]


def finite_matrix(values: ArrayLike) -> FloatArray:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 2 or not all(result.shape) or not np.isfinite(result).all():
        raise ValueError("FINITE_NONEMPTY_MATRIX_REQUIRED")
    return result


@dataclass(frozen=True)
class Standardization:
    means: tuple[float, ...]
    stds: tuple[float, ...]

    def __post_init__(self) -> None:
        if (
            not self.means
            or len(self.means) != len(self.stds)
            or not np.isfinite(self.means).all()
            or not np.isfinite(self.stds).all()
            or any(value <= 0 for value in self.stds)
        ):
            raise ValueError("ZERO_OR_INVALID_TRAIN_VARIANCE")

    @classmethod
    def fit(cls, eligible_training: ArrayLike) -> Standardization:
        train = finite_matrix(eligible_training)
        with np.errstate(over="raise", invalid="raise"):
            means, stds = train.mean(axis=0), train.std(axis=0, ddof=0)
        if not np.isfinite(stds).all() or (stds <= 0).any():
            raise ValueError("ZERO_OR_INVALID_TRAIN_VARIANCE")
        return cls(tuple(map(float, means)), tuple(map(float, stds)))

    def apply(self, values: ArrayLike) -> FloatArray:
        frame = finite_matrix(values)
        if frame.shape[1] != len(self.means):
            raise ValueError("FEATURE_SCHEMA_MISMATCH")
        with np.errstate(over="raise", divide="raise", invalid="raise"):
            result = (frame - np.asarray(self.means)) / np.asarray(self.stds)
        if not np.isfinite(result).all():
            raise ValueError("NONFINITE_STANDARDIZATION")
        return result


def dependence(values: ArrayLike, horizon: int) -> dict[str, Any]:
    """Temporal ESS per industry series; never flatten cross sections into time.

    Positive-sequence ACF estimate is complemented by non-overlapping block
    counts. It is diagnostic, not a claim of independence or a significance test.
    """
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 1 or len(x) < 3 or horizon not in (10, 40, 80, 120):
        raise ValueError("ORDERED_TEMPORAL_SERIES_REQUIRED")
    if not np.isfinite(x).all():
        raise ValueError("MISSING_TEMPORAL_LABELS_NO_GAP_COMPRESSION")
    centered = x - x.mean()
    denominator = float(centered @ centered)
    if denominator <= 0:
        raise ValueError("DEGENERATE_TARGET")
    max_lag = min(2 * horizon, len(x) // 3)
    acf = [float(centered[:-lag] @ centered[lag:] / denominator) for lag in range(1, max_lag + 1)]
    positive_sum = 0.0
    for lag in range(0, len(acf) - 1, 2):
        pair = acf[lag] + acf[lag + 1]
        if pair <= 0:
            break
        positive_sum += pair
    ess = min(float(len(x)), len(x) / (1 + 2 * positive_sum))
    return {
        "sessions": len(x),
        "horizon": horizon,
        "adjacent_label_overlap_fraction": (horizon - 1) / horizon,
        "acf": acf,
        "acf_max_lag": max_lag,
        "ess_positive_sequence": ess,
        "nonoverlapping_horizon_blocks": len(x) // horizon,
        "assumptions": "STATIONARY_ORDERED_COMPLETE_SINGLE_INDUSTRY_SERIES;TRUNCATED_ACF",
    }


def feature_geometry(values: ArrayLike) -> dict[str, Any]:
    x = finite_matrix(values)
    centered = x - x.mean(axis=0)
    std = x.std(axis=0, ddof=0)
    singular = np.linalg.svd(centered, compute_uv=False)
    eigenvalues = singular**2 / len(x)
    condition = float(singular[0] / singular[-1]) if singular[-1] > 0 else None
    nonconstant = std > 0
    correlation = np.full((x.shape[1], x.shape[1]), np.nan)
    if nonconstant.sum() > 1:
        correlation[np.ix_(nonconstant, nonconstant)] = np.corrcoef(x[:, nonconstant], rowvar=False)
    # Missing/undefined correlation is null in serialized diagnostic metadata.
    corr = [[float(v) if np.isfinite(v) else None for v in row] for row in correlation]
    return {
        "means": x.mean(axis=0).tolist(),
        "population_std": std.tolist(),
        "covariance_eigenvalues": eigenvalues.tolist(),
        "design_condition_number": condition,
        "covariance_condition_number": condition**2 if condition is not None else None,
        "feature_correlation": corr,
        "constant_feature_indices": np.where(~nonconstant)[0].tolist(),
        "rank": int(np.linalg.matrix_rank(centered)),
    }


def ridge_vs_ols(values: ArrayLike, target: ArrayLike) -> dict[str, Any]:
    x = finite_matrix(values)
    ols, ridge = NumPyRidge(alpha=0).fit(x, target), NumPyRidge(alpha=0.01).fit(x, target)
    a, b = ols.predict(x), ridge.predict(x)
    ols_norm, ridge_norm = float(np.linalg.norm(ols.coef_)), float(np.linalg.norm(ridge.coef_))
    correlation = float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else None
    return {
        "alpha": 0.01,
        "feature_scaling": "RAW",
        "ols_coefficients": ols.coef_.tolist(),
        "ridge_coefficients": ridge.coef_.tolist(),
        "ols_coefficient_norm": ols_norm,
        "ridge_coefficient_norm": ridge_norm,
        "shrinkage_norm_ratio": ridge_norm / ols_norm if ols_norm > 0 else None,
        "coefficient_sign_agreement": float(np.mean(np.sign(ols.coef_) == np.sign(ridge.coef_))),
        "prediction_correlation": correlation,
        "prediction_max_absolute_difference": float(np.max(np.abs(a - b))),
        "geometry": feature_geometry(x),
    }


def moving_block_interval(
    values: ArrayLike, *, block: int = 120, replications: int = 1000, seed: int = 20261004
) -> tuple[float, float]:
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not np.isfinite(x).all() or len(x) < block * 2 or block < 1:
        raise ValueError("INSUFFICIENT_BLOCK_BOOTSTRAP_DATA")
    if replications < 100:
        raise ValueError("INSUFFICIENT_BOOTSTRAP_REPLICATIONS")
    generator = np.random.default_rng(seed)
    offsets = np.arange(block)
    estimates = []
    for _ in range(replications):
        starts = generator.integers(0, len(x) - block + 1, size=(len(x) + block - 1) // block)
        sample = x[(starts[:, None] + offsets).ravel()[: len(x)]]
        estimates.append(float(sample.mean()))
    low, high = np.quantile(estimates, [0.025, 0.975])
    return float(low), float(high)
