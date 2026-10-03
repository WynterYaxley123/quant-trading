"""Reusable finite-window Development factors, with explicit visible label tails."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from strategies.sw_sector_rotation.src.common.temporal_integrity import make_forward_label
from strategies.sw_sector_rotation.src.factors.sector_rotation import (
    compute_align_feature,
    compute_all_price_features,
)

# All admitted features have finite lookbacks. RSI here is a simple rolling mean.
_WARMUP = {
    **{f"{prefix}{n}": n - 1 for prefix in ("d", "p") for n in (5, 10, 20, 60, 120)},
    "v5": 5,
    "v20": 20,
    "vc": 20,
    "rev5": 5,
    "rev10": 10,
    "dd20": 19,
    "dd60": 59,
    "rsi": 14,
}


class DevelopmentPanel:
    """One immutable call-scoped precomputation; never include sealed signal dates."""

    def __init__(self, frames: Mapping[str, pd.DataFrame], last_signal: pd.Timestamp) -> None:
        self.frames = {code: frame.loc[:last_signal].copy() for code, frame in frames.items()}
        self.features = {
            code: compute_all_price_features(frame, include_rsrs=False)
            for code, frame in self.frames.items()
        }
        self.last_signal = last_signal

    def visible(
        self, warmup: pd.Timestamp, signal: pd.Timestamp, horizons: tuple[int, ...]
    ) -> dict[str, pd.DataFrame]:
        """Reproduce a fresh moving-window panel, including its initial missing rows."""
        if signal > self.last_signal or warmup > signal:
            raise ValueError("DEVELOPMENT_PANEL_VISIBILITY_BLOCKER")
        panel = {}
        for code, frame in self.frames.items():
            visible = frame.loc[warmup:signal]
            out = self.features[code].loc[visible.index].copy()
            for column, count in _WARMUP.items():
                out.loc[out.index[:count], column] = float("nan")
            # Comparisons with unavailable moving averages produce 0, not NaN.
            initial_align = compute_align_feature(visible.iloc[:59])
            out.loc[initial_align.index, "align"] = initial_align
            for h in horizons:
                out[f"fwd{h}"] = make_forward_label(
                    visible["close"], h, calendar=visible.index.tolist()
                )
            panel[code] = out
        return panel
