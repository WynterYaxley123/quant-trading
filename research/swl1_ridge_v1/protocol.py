"""Result-free contracts for the independently authorized first SWL1 generation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategies.etf_quant.config import FACTORS_19, H10_FACTORS

HORIZONS = (10, 40, 120)
WEIGHTS = (0.25, 0.50, 0.25)
ALPHAS = (0.1, 1.0, 10.0, 30.0, 100.0)


def body(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def immutable(path: Path, value: object) -> str:
    raw = body(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(raw)
            handle.flush()
    except FileExistsError:
        if path.read_bytes() != raw:
            raise ValueError("IMMUTABLE_RESEARCH_ARTIFACT_CONFLICT") from None
    return digest(raw)


@dataclass(frozen=True)
class Spec:
    alpha: float
    months: int
    policy: str

    def __post_init__(self) -> None:
        if self.alpha not in ALPHAS or self.months not in (12, 24) or self.policy not in ("A", "B"):
            raise ValueError("OUTSIDE_FROZEN_SEARCH_BUDGET")

    def factors(self, horizon: int) -> tuple[str, ...]:
        if horizon not in HORIZONS:
            raise ValueError("UNREGISTERED_HORIZON")
        return H10_FACTORS if horizon == 10 and self.policy == "A" else FACTORS_19

    @property
    def identifier(self) -> str:
        return f"{self.policy}-m{self.months}-a{self.alpha:g}"


def split_sessions(dates: list[str], eligible: list[int]) -> dict[str, Any] | None:
    """Choose 252 then 126 using counts only; purges use the full exchange spine."""
    if dates != sorted(set(dates)) or eligible != sorted(set(eligible)):
        raise ValueError("SORTED_UNIQUE_EXCHANGE_SPINE_REQUIRED")
    eligible_set = set(eligible)
    for count in (252, 126):
        if len(eligible) < 2 * count + 126:
            continue
        final = eligible[-count:]
        before_validation = [i for i in eligible if i <= final[0] - 121]
        if len(before_validation) < count:
            continue
        validation = before_validation[-count:]
        development = [i for i in eligible if i <= validation[0] - 121]
        if len(development) < 126:
            continue
        phases = {"development": development, "validation": validation, "final_oos": final}
        if any(i not in eligible_set for indices in phases.values() for i in indices):
            raise ValueError("INELIGIBLE_SIGNAL")
        return {
            "indices": phases,
            "ranges": {
                k: {"start": dates[v[0]], "end": dates[v[-1]], "signals": len(v)}
                for k, v in phases.items()
            },
            "purge_sessions": 120,
            "evaluation_signal_count": count,
        }
    return None


def exact_targets(returns: np.ndarray, horizon: int) -> np.ndarray:
    """Complete fixed-universe windows only; no missing-return renormalization."""
    result = np.full_like(returns, np.nan, dtype=float)
    for index in range(len(returns) - horizon):
        window = returns[index + 1 : index + horizon + 1]
        if np.isfinite(window).all():
            result[index] = np.prod(1 + window, axis=0) - 1
    return result


def eligible_signals(
    features: np.ndarray, returns: np.ndarray, dates: list[str], months: int
) -> list[int]:
    """Count mechanics only, without fitting or evaluating return direction."""
    if months not in (12, 24):
        raise ValueError("UNREGISTERED_TRAINING_WINDOW")
    complete = np.isfinite(features).all(axis=(1, 2))
    mature = np.array(
        [
            i + 120 < len(returns) and np.isfinite(returns[i + 1 : i + 121]).all()
            for i in range(len(returns))
        ]
    )
    first = (pd.Timestamp(dates[0]) + pd.DateOffset(months=months)).date().isoformat()
    result = []
    for i in np.flatnonzero(complete & mature):
        start = (pd.Timestamp(dates[i]) - pd.DateOffset(months=months)).date().isoformat()
        valid = [
            j
            for j in range(max(0, int(i) - 119))
            if dates[j] >= start and complete[j] and mature[j]
        ]
        if dates[i] >= first and len(valid) >= 30:
            result.append(int(i))
    return result


def fit_predict(
    features: np.ndarray,
    targets: np.ndarray,
    dates: list[str],
    signal: int,
    horizon: int,
    spec: Spec,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Training-only scaling; exact independent mature cutoff per horizon."""
    names = spec.factors(horizon)
    columns = [FACTORS_19.index(name) for name in names]
    start = (pd.Timestamp(dates[signal]) - pd.DateOffset(months=spec.months)).date().isoformat()
    valid = [
        i
        for i in range(signal - horizon + 1)
        if dates[i] >= start
        and np.isfinite(features[i, :, columns]).all()
        and np.isfinite(targets[i]).all()
    ]
    if len(valid) < 30 or not np.isfinite(features[signal, :, columns]).all():
        raise ValueError("INSUFFICIENT_COMPLETE_MATURE_TRAINING_DATES")
    x = features[valid][:, :, columns].reshape(-1, len(columns))
    y0 = targets[valid]
    y = (y0 - y0.mean(axis=1, keepdims=True)).reshape(-1)
    mean, scale = x.mean(axis=0), x.std(axis=0, ddof=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    standardized = (x - mean) / scale
    ymean = y.mean()
    coefficients = np.linalg.solve(
        standardized.T @ standardized + spec.alpha * np.eye(len(columns)),
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
        "feature_names": names,
    }
