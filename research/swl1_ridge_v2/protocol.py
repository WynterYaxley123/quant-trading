"""Result-free V2 contracts: per-row ridge penalty and a seen-data-aware split.

Frozen V1 modules are imported read-only; their preregistered hashes are unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from research.swl1_ridge_v1.protocol import HORIZONS
from strategies.etf_quant.config import FACTORS_19, H10_FACTORS

# Ridge alpha per standardized training row. Standardized X'X has a diagonal of
# about the row count, so V1's absolute 0.1-100 grid barely regularized.
PENALTIES = (0.01, 0.1, 1.0, 10.0)
MONTHS = (12, 24)
POLICIES = ("A", "B")
PURGE_SESSIONS = 120
PHASE_SIGNALS = 126


@dataclass(frozen=True)
class Spec:
    penalty: float
    months: int
    policy: str

    def __post_init__(self) -> None:
        if (
            self.penalty not in PENALTIES
            or self.months not in MONTHS
            or self.policy not in POLICIES
        ):
            raise ValueError("OUTSIDE_FROZEN_SEARCH_BUDGET")

    def factors(self, horizon: int) -> tuple[str, ...]:
        if horizon not in HORIZONS:
            raise ValueError("UNREGISTERED_HORIZON")
        return H10_FACTORS if horizon == 10 and self.policy == "A" else FACTORS_19

    @property
    def identifier(self) -> str:
        return f"{self.policy}-m{self.months}-l{self.penalty:g}"


def fit_predict(
    features: np.ndarray,
    targets: np.ndarray,
    dates: list[str],
    signal: int,
    horizon: int,
    spec: Spec,
) -> tuple[np.ndarray, dict[str, Any]]:
    """V1 maturity and training-only scaling; alpha = penalty x training rows."""
    names = spec.factors(horizon)
    columns = [FACTORS_19.index(name) for name in names]
    start = (pd.Timestamp(dates[signal]) - pd.DateOffset(months=spec.months)).date().isoformat()
    valid = [
        i
        for i in range(signal - horizon + 1)
        if dates[i] >= start
        and np.isfinite(features[i][:, columns]).all()
        and np.isfinite(targets[i]).all()
    ]
    if len(valid) < 30 or not np.isfinite(features[signal][:, columns]).all():
        raise ValueError("INSUFFICIENT_COMPLETE_MATURE_TRAINING_DATES")
    x = features[valid][:, :, columns].reshape(-1, len(columns))
    y0 = targets[valid]
    y = (y0 - y0.mean(axis=1, keepdims=True)).reshape(-1)
    mean, scale = x.mean(axis=0), x.std(axis=0, ddof=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    standardized = (x - mean) / scale
    ymean = y.mean()
    alpha = spec.penalty * len(y)
    coefficients = np.linalg.solve(
        standardized.T @ standardized + alpha * np.eye(len(columns)),
        standardized.T @ (y - ymean),
    )
    prediction = (features[signal][:, columns] - mean) / scale @ coefficients + ymean
    return prediction, {
        "training_start": dates[valid[0]],
        "training_end": dates[valid[-1]],
        "mature_label_cutoff": dates[signal - horizon],
        "window_start": start,
        "valid_training_dates": len(valid),
        "industry_rows": len(y),
        "ridge_alpha": alpha,
        "feature_names": names,
    }


def split_sessions(
    dates: list[str], eligible: list[int], last_seen_signal: str
) -> dict[str, Any] | None:
    """Development may reuse seen history; Validation starts after every seen label.

    ``last_seen_signal`` is V1's last Validation signal. Its H120 label is the last
    realized return that entered any V1 metric. A V2 signal may equal that endpoint:
    its target starts on the next exchange session. Final OOS is prospective only.
    """
    if dates != sorted(set(dates)) or eligible != sorted(set(eligible)):
        raise ValueError("SORTED_UNIQUE_EXCHANGE_SPINE_REQUIRED")
    if last_seen_signal not in dates:
        raise ValueError("SEEN_BOUNDARY_NOT_AN_EXCHANGE_SESSION")
    seen_through = dates.index(last_seen_signal) + max(HORIZONS)
    validation = [i for i in eligible if i >= seen_through][:PHASE_SIGNALS]
    if len(validation) < PHASE_SIGNALS:
        return None
    development = [i for i in eligible if i <= validation[0] - PURGE_SESSIONS - 1]
    if len(development) < PHASE_SIGNALS:
        return None
    phases = {"development": development, "validation": validation}
    return {
        "indices": phases,
        "ranges": {
            k: {"start": dates[v[0]], "end": dates[v[-1]], "signals": len(v)}
            for k, v in phases.items()
        },
        "purge_sessions": PURGE_SESSIONS,
        "evaluation_signal_count": PHASE_SIGNALS,
        "seen_through": dates[seen_through] if seen_through < len(dates) else None,
        "final_oos": "PROSPECTIVE_FORWARD_ONLY",
    }
