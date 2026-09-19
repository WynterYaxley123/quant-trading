"""provider / loader / preflight 的离线测试。

不联网、不加载 Hikyuu 数据目录：provider 用假对象，preflight 用
临时 SQLite + 临时 HDF5 构造一致性/不一致场景。
"""

from __future__ import annotations

import os
import sqlite3

import numpy as np
import pandas as pd
import pytest

from src.data.loaders import MarketDataRequest, load_panel
from src.data.providers import (
    DataProvider,
    HikyuuDataIntegrityError,
    ProviderCapabilities,
    ProviderUnavailable,
    preflight,
)
from src.data.schema import DataIntegrityError


# --- 假 provider ----------------------------------------------------------


class _FakeProvider(DataProvider):
    name = "fake"

    def __init__(self, frames=None, available=True, raise_unavailable=False):
        self._frames = frames or {}
        self._available = available
        self._raise = raise_unavailable
        self.calls = 0

    @property
    def capabilities(self):
        return ProviderCapabilities(asset_types=frozenset({"ETF"}), ktypes=frozenset({"DAY"}))

    def is_available(self):
        return self._available

    def fetch_daily(self, symbols, start, end):
        self.calls += 1
        if self._raise:
            raise ProviderUnavailable(self.name, "simulated failure")
        return {s: self._frames[s] for s in symbols if s in self._frames}


class _ExplodingProvider(DataProvider):
    name = "exploding"

    @property
    def capabilities(self):
        return ProviderCapabilities()

    def is_available(self):
        raise RuntimeError("probe exploded")

    def fetch_daily(self, symbols, start, end):  # pragma: no cover
        raise AssertionError("不应被调用")


def _frame(symbol: str, n: int = 10, start: str = "2024-01-02") -> pd.DataFrame:
    dates = pd.bdate_range(start=start, periods=n)
    close = np.linspace(10.0, 11.0, n)
    return pd.DataFrame(
        {
            "date": dates,
            "symbol": symbol,
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
            "volume": np.full(n, 100.0),
        }
    )


# --- MarketDataRequest ----------------------------------------------------


def test_request_rejects_empty_symbols():
    with pytest.raises(ValueError):
        MarketDataRequest(symbols=[], start="2024-01-01", end="2024-02-01")


# --- load_panel -----------------------------------------------------------


def test_load_panel_basic():
    p = _FakeProvider({"510300": _frame("510300"), "159934": _frame("159934")})
    res = load_panel(
        MarketDataRequest(symbols=["510300", "159934"], start="2024-01-01", end="2024-02-01"),
        [p],
    )
    assert res.ok
    assert set(res.panel) == {"510300", "159934"}
    assert res.sources["510300"] == "fake"
    assert len(res.calendar) == 10


def test_load_panel_records_missing_without_faking():
    p = _FakeProvider({"510300": _frame("510300")})
    res = load_panel(
        MarketDataRequest(symbols=["510300", "NOPE"], start="2024-01-01", end="2024-02-01"),
        [p],
    )
    assert "NOPE" in res.missing
    assert "NOPE" not in res.panel


def test_load_panel_falls_back_to_next_provider():
    """单 provider 故障不得判定为整个数据层失败。"""
    bad = _FakeProvider(available=False)
    good = _FakeProvider({"510300": _frame("510300")})
    res = load_panel(
        MarketDataRequest(symbols=["510300"], start="2024-01-01", end="2024-02-01"),
        [bad, good],
    )
    assert res.ok
    assert res.sources["510300"] == "fake"


def test_load_panel_skips_provider_that_raises():
    p1 = _FakeProvider(raise_unavailable=True)
    p2 = _FakeProvider({"510300": _frame("510300")})
    res = load_panel(
        MarketDataRequest(symbols=["510300"], start="2024-01-01", end="2024-02-01"),
        [p1, p2],
    )
    assert res.ok


def test_load_panel_probe_exception_does_not_kill_chain():
    """可用性探测抛异常不应导致整体失败。"""
    p2 = _FakeProvider({"510300": _frame("510300")})
    res = load_panel(
        MarketDataRequest(symbols=["510300"], start="2024-01-01", end="2024-02-01"),
        [_ExplodingProvider(), p2],
    )
    assert res.ok


def test_load_panel_all_providers_unavailable_raises():
    with pytest.raises(ProviderUnavailable):
        load_panel(
            MarketDataRequest(symbols=["510300"], start="2024-01-01", end="2024-02-01"),
            [_FakeProvider(available=False)],
        )


def test_load_panel_no_providers_raises():
    with pytest.raises(ValueError):
        load_panel(
            MarketDataRequest(symbols=["510300"], start="2024-01-01", end="2024-02-01"),
            [],
        )


def test_load_panel_rejects_invalid_frame():
    bad = _frame("510300")
    bad.loc[2, "close"] = np.nan  # 会触发 validate_frame
    p = _FakeProvider({"510300": bad})
    with pytest.raises(DataIntegrityError, match="未取到任何数据"):
        load_panel(
            MarketDataRequest(symbols=["510300"], start="2024-01-01", end="2024-02-01"),
            [p],
        )


# --- preflight ------------------------------------------------------------


def _make_hikyuu_dir(tmp_path, *, db_codes, h5_codes, lastdates=None):
    """构造一个最小 Hikyuu 数据目录用于 preflight 测试。"""
    import tables

    dest = str(tmp_path)
    db = os.path.join(dest, "stock.db")
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE Market (marketid INTEGER PRIMARY KEY, market VARCHAR(10),
            name VARCHAR(60), description VARCHAR(100), code VARCHAR(20), lastDate INTEGER);
        CREATE TABLE Stock (stockid INTEGER PRIMARY KEY, marketid INTEGER,
            code VARCHAR(20), name VARCHAR(60), type INTEGER, valid INTEGER,
            startDate INTEGER, endDate INTEGER);
        """
    )
    ld = lastdates or {"SH": 20240102, "SZ": 20240102}
    for mid, mkt in ((1, "SH"), (2, "SZ")):
        conn.execute(
            "insert into market values(?,?,?,?,?,?)",
            (mid, mkt, mkt, mkt, "000001", ld.get(mkt, 20240102)),
        )
    for i, code in enumerate(db_codes):
        mid = 1 if code.startswith("5") else 2
        conn.execute(
            "insert into stock values(?,?,?,?,?,?,?,?)",
            (i + 1, mid, code, code, 5, 1, 20200101, 99999999),
        )
    conn.commit()
    conn.close()

    class _Rec(tables.IsDescription):
        datetime = tables.Int64Col(pos=0)
        openPrice = tables.Int64Col(pos=1)
        highPrice = tables.Int64Col(pos=2)
        lowPrice = tables.Int64Col(pos=3)
        closePrice = tables.Int64Col(pos=4)
        transAmount = tables.Int64Col(pos=5)
        transCount = tables.Int64Col(pos=6)

    for mkt, prefix in (("SH", "sh"), ("SZ", "sz")):
        codes = [c for c in h5_codes if (c.startswith("5") and mkt == "SH") or (not c.startswith("5") and mkt == "SZ")]
        path = os.path.join(dest, f"{prefix}_day.h5")
        f = tables.open_file(path, "w")
        grp = f.create_group("/", "data")
        for code in codes:
            t = f.create_table(grp, f"{mkt}{code}", _Rec)
            row = t.row
            row["datetime"] = 202401020000
            row["openPrice"] = 1000
            row["highPrice"] = 1100
            row["lowPrice"] = 900
            row["closePrice"] = 1050
            row["transAmount"] = 100
            row["transCount"] = 10
            row.append()
            t.flush()
        f.close()
    return dest


def test_preflight_passes_on_consistent_data(tmp_path):
    dest = _make_hikyuu_dir(tmp_path, db_codes=["510300", "159934"],
                           h5_codes=["510300", "159934"])
    rep = preflight(dest)
    assert rep.db_stock_count == 2
    assert rep.h5_table_count == 2


def test_preflight_missing_db_raises(tmp_path):
    with pytest.raises(HikyuuDataIntegrityError, match="stock.db"):
        preflight(str(tmp_path))


def test_preflight_detects_stock_without_kdata(tmp_path):
    """这正是会导致 StockManager.reload() 段错误的场景。"""
    dest = _make_hikyuu_dir(tmp_path, db_codes=["510300", "159934", "512660"],
                            h5_codes=["510300", "159934"])
    with pytest.raises(HikyuuDataIntegrityError, match="无 K线表"):
        preflight(dest)


def test_preflight_detects_orphan_h5_table(tmp_path):
    dest = _make_hikyuu_dir(tmp_path, db_codes=["510300"],
                            h5_codes=["510300", "159934"])
    with pytest.raises(HikyuuDataIntegrityError, match="无对应 valid 证券"):
        preflight(dest)


def test_preflight_detects_invalid_last_date(tmp_path):
    """99999999 是误用 stock.endDate 的典型症状。"""
    dest = _make_hikyuu_dir(tmp_path, db_codes=["510300"], h5_codes=["510300"],
                            lastdates={"SH": 99999999})
    with pytest.raises(HikyuuDataIntegrityError, match="lastDate"):
        preflight(dest)


def test_preflight_missing_required_market_file(tmp_path):
    dest = _make_hikyuu_dir(tmp_path, db_codes=["510300"], h5_codes=["510300"])
    os.remove(os.path.join(dest, "sz_day.h5"))
    with pytest.raises(HikyuuDataIntegrityError, match="HDF5 日线文件缺失"):
        preflight(dest)
