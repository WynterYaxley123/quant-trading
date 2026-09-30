"""Per-signal/horizon population z-score fusion; no raw-score weighted sum."""
from collections.abc import Mapping, Sequence

import numpy as np

from ..domain import FusedRanking, Horizon, IndustryRanking, ModelPrediction, StrategyConfig


def cross_sectional_zscore(values) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not x.size or not np.isfinite(x).all():
        raise ValueError("finite nonempty score vector required")
    magnitude = max(float(np.max(np.abs(x))), 1.0)
    scaled = x / magnitude
    std = scaled.std(ddof=0)
    return (scaled - scaled.mean()) / std if std > 1e-12 / magnitude else np.zeros_like(x)


def fuse_predictions(predictions: Mapping[Horizon, Sequence[ModelPrediction]], *,
                     config: StrategyConfig | None = None,
                     industry_universe: Sequence[str] | None = None) -> FusedRanking:
    config = StrategyConfig() if config is None else config
    if set(predictions) != set(Horizon) or not all(isinstance(h, Horizon) for h in predictions):
        raise ValueError("all three independent horizons required")
    scores, signal_dates = {}, set()
    for h in Horizon:
        by_code = {}
        for p in predictions[h]:
            if not isinstance(p, ModelPrediction) or p.horizon is not h or p.industry_code in by_code:
                raise ValueError("prediction horizon / duplicate industry mismatch")
            signal_dates.add(p.signal_date)
            by_code[p.industry_code] = p.prediction
        scores[h] = by_code
    universe = tuple(sorted(scores[Horizon.H10])) if industry_universe is None else tuple(sorted(industry_universe))
    if len(universe) < config.top_k or len(set(universe)) != len(universe):
        raise ValueError("complete explicit universe with at least five industries required")
    if len(signal_dates) != 1 or any(set(v) != set(universe) for v in scores.values()):
        raise ValueError("signal date / full horizon coverage mismatch; intersection forbidden")
    signal_date = next(iter(signal_dates))
    fused = np.zeros(len(universe))
    normalized = []
    for h, weight in config.fusion_weights:
        horizon = Horizon(h)
        z = cross_sectional_zscore([scores[horizon][code] for code in universe])
        fused += weight * z
        normalized.append((horizon, tuple(ModelPrediction(horizon, signal_date, code, float(v))
                                          for code, v in zip(universe, z))))
    # Baseline weights sum exactly to one; source implementation's normalization
    # is retained explicitly, not applied to unstandardized predictions.
    fused /= sum(w for _, w in config.fusion_weights)
    ranked = sorted(zip(universe, map(float, fused)), key=lambda item: (-item[1], item[0]))
    return FusedRanking(signal_date, tuple(IndustryRanking(i + 1, code, score)
                                         for i, (code, score) in enumerate(ranked)), tuple(normalized))
