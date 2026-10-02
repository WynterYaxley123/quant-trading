"""SYNTHETIC DEMO ONLY: mature labels → Ridge → z-score fusion → capped sizing.

Eight artificial identities illustrate reusable pure functions; they are not the
107 admitted production industries. No evidence admission, account, orders, NAV,
real data or claims of profitability are produced.
"""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta, timezone

import numpy as np
import pandas as pd

from strategies.etf_quant.domain import Horizon, StrategyConfig, TradingCalendar
from strategies.etf_quant.models import TrainingObservation, fit_horizon, predict_industries
from strategies.etf_quant.models.fusion import fuse_predictions
from strategies.etf_quant.portfolio import size_targets


def run_demo(seed: int = 10719) -> dict[str, object]:
    """Exercise frozen training/maturity/ordering rules on generated inputs only."""
    rng = np.random.default_rng(seed)
    days = tuple(day.date() for day in pd.bdate_range("2023-01-02", periods=420))
    calendar = TradingCalendar(days)
    tz = timezone(timedelta(hours=8))
    signal_at = datetime.combine(days[-1], time(17), tzinfo=tz)
    universe = tuple(f"SYNTHETIC_{i:02}" for i in range(8))
    config = StrategyConfig()
    predictions = {}
    training_days = {}
    for spec in config.horizons:
        observations = []
        n = len(spec.factor_names)
        coefficients = rng.normal(0, 0.01, n)
        cutoff_index = len(days) - 1 - int(spec.horizon)
        for index in range(cutoff_index - 100, cutoff_index + 1):
            label_end = days[index + int(spec.horizon)]
            available = datetime.combine(label_end, time(16), tzinfo=tz)
            for code in universe:
                features = rng.normal(size=n)
                observations.append(
                    TrainingObservation(
                        spec.horizon,
                        code,
                        days[index],
                        label_end,
                        available,
                        spec.factor_names,
                        tuple(float(x) for x in features),
                        float(features @ coefficients + rng.normal(0, 0.001)),
                    )
                )
        model = fit_horizon(
            spec, observations, calendar=calendar, signal_at=signal_at, industry_universe=universe
        )
        current = {code: tuple(float(x) for x in rng.normal(size=n)) for code in universe}
        predictions[spec.horizon] = predict_industries(
            model, current, factor_names=spec.factor_names, signal_date=days[-1]
        )
        training_days[str(int(spec.horizon))] = model.training.training_day_count
    ranking = fuse_predictions(predictions, config=config, industry_universe=universe)
    top = ranking.rankings[: config.top_k]
    allocation = size_targets({r.industry_code: r.score for r in top})
    return {
        "label": "SYNTHETIC DEMO ONLY",
        "seed": seed,
        "external_data_required": False,
        "broker_enabled": False,
        "real_order_path": False,
        "horizons": [int(h) for h in Horizon],
        "training_days": training_days,
        "allocation_status": allocation.status.value,
        "ranked_top5": [{"identity": r.industry_code, "score": r.score} for r in top],
        "weights": {t.asset_id: t.target_weight for t in allocation.targets},
        "unallocated_weight": allocation.unallocated_weight,
    }


def main() -> None:
    """Emit an explicit synthetic JSON demonstration to stdout."""
    print(json.dumps(run_demo(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
