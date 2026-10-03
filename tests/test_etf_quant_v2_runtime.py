"""Synthetic forward preparation and delayed accounting; no real Shadow records."""

from datetime import date, datetime, time
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from strategies.etf_quant.config import FACTORS_19, H10_FACTORS
from strategies.etf_quant.domain import TradingCalendar, decimal_math
from strategies.etf_quant.models import NumPyRidge
from strategies.etf_quant.simulation import new_portfolio
from strategies.etf_quant_v2.accounting import settle_t_plus_one
from strategies.etf_quant_v2.runtime import (
    SHANGHAI,
    FrozenSpecification,
    Observation,
    prepare_signal,
)


def test_forward_fit_matches_frozen_ridge_and_excludes_sealed_signal_rows():
    days = tuple(d.date() for d in pd.bdate_range("2024-01-01", "2026-10-12"))
    signal = datetime(2026, 10, 9, 16, tzinfo=SHANGHAI)
    rng = np.random.default_rng(123)
    names = [f"I{i:02}" for i in range(12)]
    x = rng.normal(size=(len(days), 12, 19))
    returns = rng.normal(size=(len(days), 12)) * 0.01
    rows = [
        Observation(
            name,
            day,
            tuple(x[t, j]),
            {h: float(returns[t, j]) for h in (10, 40, 120)},
            {h: days[t + h] for h in (10, 40, 120)},
            signal,
            "B",
        )
        for t, day in enumerate(days[:-120])
        for j, name in enumerate(names)
    ]
    spec = FrozenSpecification(
        "synthetic",
        (10, 40, 120),
        (0.25, 0.5, 0.25),
        30.0,
        12,
        "RAW",
        "a" * 64,
        datetime(2026, 10, 4, tzinfo=SHANGHAI),
        date(2025, 12, 30),
        date(2026, 4, 2),
        True,
    )
    options = dict(
        calendar=days,
        signal_at=signal,
        snapshot_available_at=signal,
        finalized=True,
        mapping_pools={},
        exposure_vectors={},
        mapping_available_at=signal,
    )
    plan = prepare_signal(
        spec,
        rows,
        dict(zip(names, map(tuple, x[days.index(signal.date())]), strict=True)),
        **options,
    )
    assert plan["execution_date"] == "2026-10-12"
    for fitted, h in zip(plan["models"], spec.horizons, strict=True):
        selected = [
            r
            for r in rows
            if date.fromisoformat(fitted["training_window_start"])
            <= r.day
            <= date.fromisoformat(fitted["label_cutoff"])
            and not spec.final_oos_start <= r.day <= spec.final_oos_end
        ]
        columns = [FACTORS_19.index(n) for n in (H10_FACTORS if h == 10 else FACTORS_19)]
        xx = np.array([r.factors for r in selected])[:, columns]
        yy = np.array([r.returns[h] - returns[days.index(r.day)].mean() for r in selected])
        expected = NumPyRidge(30).fit(xx, yy)
        np.testing.assert_allclose(fitted["coefficients"], expected.coef_, atol=1e-12)
    changed = [
        Observation(
            r.industry,
            r.day,
            tuple(v * 999 for v in r.factors),
            r.returns,
            r.label_end,
            r.observed_at,
            r.evidence_tier,
        )
        if spec.final_oos_start <= r.day <= spec.final_oos_end
        else r
        for r in rows
    ]
    assert (
        prepare_signal(
            spec,
            changed,
            dict(zip(names, map(tuple, x[days.index(signal.date())]), strict=True)),
            **options,
        )
        == plan
    )


def test_delayed_accounting_preserves_member_trigger_and_costs():
    calendar = TradingCalendar((date(2026, 10, 9), date(2026, 10, 12), date(2026, 10, 13)))
    signal = datetime(2026, 10, 9, 16, tzinfo=SHANGHAI)
    state = new_portfolio(signal)
    options = dict(
        signal_at=signal,
        processed_at=datetime(2026, 10, 12, 16, tzinfo=SHANGHAI),
        calendar=calendar,
        weights={"ETF": 0.25},
        raw_opens={"ETF": Decimal(10)},
        raw_closes={"ETF": Decimal(11)},
        finalized=True,
    )
    result, fills = settle_t_plus_one(state, **options)
    assert len(fills) == 1 and fills[0].price == Decimal("10.0050")
    with decimal_math():
        assert fills[0].commission == fills[0].price * fills[0].intent.quantity * Decimal(".0003")
    assert result.cash >= Decimal(7500) and result.total_equity > 10000
    next_options = options | {
        "signal_at": result.as_of,
        "processed_at": datetime(2026, 10, 13, 16, tzinfo=SHANGHAI),
        "weights": {"ETF": 0.3},
    }
    held, next_fills = settle_t_plus_one(result, **next_options)
    assert next_fills == () and held.positions[0].quantity == result.positions[0].quantity
    cash, sales = settle_t_plus_one(result, **(next_options | {"weights": {}}))
    assert len(sales) == 1 and cash.positions == ()
    for update in (
        {"finalized": False},
        {"processed_at": datetime.combine(date(2026, 10, 12), time(14), SHANGHAI)},
        {"weights": {"ETF": 0.36}},
    ):
        with pytest.raises(ValueError):
            settle_t_plus_one(state, **(options | update))
