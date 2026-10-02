"""Read the existing Hikyuu ETF snapshot without importing or downloading data.

``stock.startDate`` and the first local bar are *not* evidence of an official
listing date.  The latter therefore remains null until independent evidence is
supplied to the mapping admission process.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from .hikyuu_preflight import preflight


def valid_daily_open(bar: dict | pd.Series | None) -> bool:
    """Conservative daily-bar check; absence and malformed OHLC are not filled."""
    if bar is None:
        return False
    try:
        o, h, l, c = (float(bar[k]) for k in ("open", "high", "low", "close"))  # noqa: E741 -- Established OHLC low-price name in frozen numerical helper.
    except (KeyError, TypeError, ValueError):
        return False
    from math import isfinite

    return (
        all(isfinite(x) and x > 0 for x in (o, h, l, c)) and h >= max(o, l, c) and l <= min(o, h, c)
    )


def read_local_etf_snapshot(data_dir: Path | str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return stock metadata and actual daily bars from the frozen local files.

    Preflight is mandatory because inconsistent stock.db/HDF5 can crash a later
    Hikyuu StockManager load.  Read-only SQLite and HDF5 handles are used.
    """
    import tables

    root = Path(data_dir)
    preflight(str(root))
    uri = f"file:{(root / 'stock.db').resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        stocks = db.execute(
            "select marketid, code, name, type, valid, startDate from stock order by marketid, code"
        ).fetchall()
    metadata: list[dict] = []
    bars: list[dict] = []
    for marketid, code, name, stock_type, valid, stock_start in stocks:
        # Hikyuu 2.8.2 local stock.db: ETF type is 5.  Do not silently
        # treat an index or a stock as a tradable ETF.
        if stock_type != 5 or not valid:
            continue
        market = {1: "sh", 2: "sz"}.get(marketid)
        if market is None:
            continue
        symbol = f"{market}{code}"
        path = root / f"{market}_day.h5"
        with tables.open_file(path, mode="r") as h5:
            table = h5.get_node(f"/data/{market.upper()}{code}")
            for raw in table.iterrows():
                stamp = str(int(raw["datetime"]) // 10000)
                bars.append(
                    {
                        "etf_code": symbol,
                        "date": f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}",
                        "open": int(raw["openPrice"]) / 1000,
                        "high": int(raw["highPrice"]) / 1000,
                        "low": int(raw["lowPrice"]) / 1000,
                        "close": int(raw["closePrice"]) / 1000,
                    }
                )
        own_dates = [row["date"] for row in bars if row["etf_code"] == symbol]
        metadata.append(
            {
                "etf_code": symbol,
                "market": market,
                "name": name,
                "listing_date": None,
                "listing_date_evidence": "UNKNOWN",
                "hikyuu_stock_start_date": str(stock_start) if stock_start else None,
                "local_data_start": min(own_dates) if own_dates else None,
                "local_data_end": max(own_dates) if own_dates else None,
                "last_available_date": max(own_dates) if own_dates else None,
                "bar_count": len(own_dates),
            }
        )
    return pd.DataFrame(metadata), pd.DataFrame(bars)
