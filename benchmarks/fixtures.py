"""Synthetic inputs only; no provider, runtime or market-data reads."""

from datetime import date, datetime, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd

from strategies.etf_quant.domain.industry_level import default_taxonomy


def industry(days: int = 60, industries: int = 20, constituents: int = 6):
    calendar = tuple(d.date() for d in pd.bdate_range("2024-01-01", periods=days))
    taxonomy = default_taxonomy()
    codes = list(taxonomy.named_industry_codes)[:industries]
    members, bars, instruments = [], [], []
    for c, code in enumerate(codes):
        for s in range(constituents):
            symbol = f"SYN_{c}_{s}"
            members.append(
                {
                    "symbol": symbol,
                    "industry_code": taxonomy.level3_children[code][0],
                    "as_of_date": calendar[0],
                    "classification_system": "sw",
                }
            )
            instruments.append({"symbol": symbol, "asset_type": "stock", "list_date": calendar[0]})
            for i, day in enumerate(calendar):
                bars.append(
                    {
                        "symbol": symbol,
                        "trade_date": day,
                        "adj_close": 10 + c + s / 10 + i / 100,
                        "adj_is_exact": True,
                        "volume": 100.0,
                    }
                )
    return SimpleNamespace(
        sessions=calendar,
        cutoff=calendar[-1],
        tables={
            "industry_membership": pd.DataFrame(members),
            "stock_bars": pd.DataFrame(bars),
            "instruments": pd.DataFrame(instruments),
        },
    )


def liquidity(etfs: int = 16, sessions: int = 40):
    days = tuple(d.date() for d in pd.bdate_range("2024-01-01", periods=sessions))
    bars, instruments, status = [], [], []
    for e in range(etfs):
        code = f"{510000 + e}.SH"
        instruments.append(
            {
                "symbol": code,
                "asset_type": "etf",
                "list_date": date(2020, 1, 1),
                "delist_date": None,
                "prev_symbol": None,
            }
        )
        for day in days:
            bars.append(
                {
                    "symbol": code,
                    "trade_date": day,
                    "open": 1.0,
                    "high": 1.1,
                    "low": 0.9,
                    "close": 1.0,
                    "volume": 1000.0,
                    "amount": 1000000.0 + e,
                    "source": "exchange",
                }
            )
            status.append(
                {
                    "symbol": code,
                    "trade_date": day,
                    "source": "exchange",
                    "is_trading": True,
                    "status": "normal",
                }
            )
    return SimpleNamespace(
        sessions=days,
        cutoff=days[-1],
        tables={
            "etf_bars": pd.DataFrame(bars),
            "instruments": pd.DataFrame(instruments),
            "trading_status": pd.DataFrame(status),
        },
    )


def prediction(days: int = 420, sectors: int = 8):
    from strategies.etf_quant.domain import StrategyConfig

    config = StrategyConfig()
    calendar = pd.bdate_range("2024-01-01", periods=days)
    universe = tuple(f"SYN_{i}" for i in range(sectors))
    names = tuple(dict.fromkeys(n for spec in config.horizons for n in spec.factor_names))
    rng = np.random.default_rng(72)
    closes = pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0, 0.005, (days, sectors)), axis=0)),
        index=calendar,
        columns=universe,
    )
    features = {
        c: pd.DataFrame(rng.normal(size=(days, len(names))), index=calendar, columns=names)
        for c in universe
    }
    return (
        SimpleNamespace(closes=closes, universe=universe),
        SimpleNamespace(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        features,
        config,
    )


def market(days: int = 600, sectors: int = 6):
    rng = np.random.default_rng(9)
    calendar = pd.bdate_range("2024-01-01", periods=days)
    result = {}
    for i in range(sectors):
        close = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, days)))
        result[str(i)] = pd.DataFrame(
            {
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1000.0,
                "amount": 100000.0,
            },
            index=calendar,
        )
    return result, calendar
