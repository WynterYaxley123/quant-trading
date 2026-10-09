"""Explicit past-only reversal features and one fixed mature-label Ridge."""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from strategies.etf_quant.models import NumPyRidge

Array = NDArray[np.float64]


def reversal_features(returns: Array) -> Array:
    if returns.ndim != 2 or returns.shape[1] < 2:
        raise ValueError("RETURN_MATRIX_REQUIRED")
    source = returns.copy()
    finite_rows = np.flatnonzero(np.isfinite(source).all(axis=1))
    if len(finite_rows):
        # The frozen recursive close series starts at the first valid return.
        # That close has no preceding close: pct_change cannot use its seed return.
        source[finite_rows[0]] = np.nan
    result = np.full((*returns.shape, 2), np.nan)
    for column, window in enumerate((5, 10)):
        for t in range(window - 1, len(returns)):
            values = source[t - window + 1 : t + 1]
            if np.isfinite(values).all():
                result[t, :, column] = -values.mean(axis=0)
    return result


def relative_features(features: Array) -> Array:
    return features - features.mean(axis=1, keepdims=True)


def equal_reversal(features: Array) -> Array:
    relative = relative_features(features)
    scale = relative.std(axis=1, ddof=0, keepdims=True)
    standardized = relative / np.where(scale > 1e-12, scale, 1.0)
    return cast(Array, standardized.mean(axis=2))


def fit_ridge(
    features: Array, targets: Array, dates: list[str], signal: int, horizon: int
) -> tuple[Array, dict[str, Any]]:
    """No parameter arguments: the only window and penalty are design-locked."""
    if horizon not in (5, 10) or features.shape != (*targets.shape, 2):
        raise ValueError("SHORT_HORIZON_TWO_FEATURE_CONTRACT")
    start = (pd.Timestamp(dates[signal]) - pd.DateOffset(months=24)).date().isoformat()
    valid = [
        i
        for i in range(signal - horizon + 1)
        if dates[i] >= start and np.isfinite(features[i]).all() and np.isfinite(targets[i]).all()
    ]
    if len(valid) < 30 or not np.isfinite(features[signal]).all():
        raise ValueError("INSUFFICIENT_COMPLETE_MATURE_TRAINING_DATES")
    x = features[valid].reshape(-1, 2)
    y0 = targets[valid]
    y = (y0 - y0.mean(axis=1, keepdims=True)).reshape(-1)
    mean, scale = x.mean(axis=0), x.std(axis=0, ddof=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    standardized = (x - mean) / scale
    alpha = 10.0 * len(y)
    model = NumPyRidge(alpha=alpha, fit_intercept=True).fit(standardized, y)
    prediction = cast(Array, model.predict((features[signal] - mean) / scale))
    gram = standardized.T @ standardized
    regularized = gram + alpha * np.eye(2)
    return prediction, {
        "signal_date": dates[signal],
        "horizon": horizon,
        "training_start": dates[valid[0]],
        "training_end": dates[valid[-1]],
        "last_training_maturity": dates[valid[-1] + horizon],
        "maturity_cutoff": dates[signal],
        "window_start": start,
        "valid_training_dates": len(valid),
        "industry_rows": len(y),
        "alpha": alpha,
        "training_indices": valid,
        "training_mean": mean.tolist(),
        "training_scale": scale.tolist(),
        "coefficients": model.coef_.tolist(),
        "intercept": float(model.intercept_),
        "regularized_condition": float(np.linalg.cond(regularized)),
        "effective_degrees_of_freedom": float(np.trace(np.linalg.solve(regularized, gram))),
        "training_date_lt_signal": all(i < signal for i in valid),
        "all_training_labels_mature": all(i + horizon <= signal for i in valid),
    }
