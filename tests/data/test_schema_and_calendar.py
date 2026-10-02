"""公共数据层 schema 与 calendar 的离线测试。

不联网、不依赖 Hikyuu 数据目录。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.data.calendar import TradingCalendar, _to_date
from src.data.schema import (
    CANONICAL_COLUMNS,
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    DataIntegrityError,
    align_columns,
    normalize_frame,
    validate_frame,
)

# --- fixtures -------------------------------------------------------------


def _frame(n: int = 5, start: str = "2024-01-02") -> pd.DataFrame:
    dates = pd.bdate_range(start=start, periods=n)
    close = np.linspace(10.0, 11.0, n)
    return pd.DataFrame(
        {
            "date": dates,
            "symbol": "TEST",
            "open": close - 0.1,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": np.full(n, 1000.0),
            "amount": close * 1000.0,
        }
    )


# --- schema 常量 -----------------------------------------------------------


def test_required_columns_minimal():
    assert REQUIRED_COLUMNS == (
        "date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
    )


def test_canonical_is_required_plus_optional():
    assert CANONICAL_COLUMNS == REQUIRED_COLUMNS + OPTIONAL_COLUMNS


def test_amount_is_optional_not_required():
    assert "amount" in OPTIONAL_COLUMNS
    assert "amount" not in REQUIRED_COLUMNS


# --- normalize_frame ------------------------------------------------------


def test_normalize_lowercases_columns():
    df = _frame().rename(columns={"open": "OPEN", "close": "Close", "date": "Date"})
    out = normalize_frame(df)
    assert "open" in out.columns and "close" in out.columns and "date" in out.columns


def test_normalize_maps_aliases():
    df = pd.DataFrame(
        {
            "日期": ["2024-01-02", "2024-01-03"],
            "开盘价": [10.0, 10.1],
            "最高价": [10.5, 10.6],
            "最低价": [9.8, 9.9],
            "收盘价": [10.2, 10.3],
            "成交量": [100.0, 200.0],
        }
    )
    out = normalize_frame(df, symbol="X")
    assert set(REQUIRED_COLUMNS).issubset(out.columns)
    assert out["symbol"].iloc[0] == "X"


def test_normalize_vol_alias_to_volume():
    df = _frame().rename(columns={"volume": "vol"}).drop(columns=["amount"])
    out = normalize_frame(df)
    assert "volume" in out.columns


def test_normalize_sorts_dates_ascending():
    df = _frame(5).iloc[::-1].reset_index(drop=True)
    out = normalize_frame(df)
    assert out["date"].is_monotonic_increasing


def test_normalize_dedups_keeping_last():
    df = _frame(3)
    dup = pd.concat([df, df.iloc[[0]].assign(close=99.0)], ignore_index=True)
    out = normalize_frame(dup)
    assert len(out) == 3
    assert out.loc[out["date"] == df["date"].iloc[0], "close"].iloc[0] == 99.0


def test_normalize_missing_date_raises():
    with pytest.raises(DataIntegrityError, match="date"):
        normalize_frame(pd.DataFrame({"open": [1.0]}))


def test_normalize_rejects_non_dataframe():
    with pytest.raises(DataIntegrityError):
        normalize_frame([1, 2, 3])  # type: ignore[arg-type]


# --- validate_frame -------------------------------------------------------


def test_validate_ok():
    validate_frame(normalize_frame(_frame()))


def test_validate_missing_required_column_raises():
    df = normalize_frame(_frame()).drop(columns=["volume"])
    with pytest.raises(DataIntegrityError, match="缺少必需列"):
        validate_frame(df)


def test_validate_duplicate_dates_raises():
    df = normalize_frame(_frame())
    df.loc[1, "date"] = df.loc[0, "date"]
    with pytest.raises(DataIntegrityError, match="重复日期"):
        validate_frame(df)


def test_validate_unsorted_dates_raises():
    df = normalize_frame(_frame())
    df = df.iloc[::-1].reset_index(drop=True)
    with pytest.raises(DataIntegrityError, match="升序"):
        validate_frame(df)


def test_validate_nan_in_price_raises_not_filled():
    """缺失值必须报错，绝不静默填充。"""
    df = normalize_frame(_frame())
    df.loc[2, "close"] = np.nan
    with pytest.raises(DataIntegrityError, match="缺失值"):
        validate_frame(df)


def test_validate_inf_raises():
    df = normalize_frame(_frame())
    df.loc[2, "high"] = np.inf
    with pytest.raises(DataIntegrityError):
        validate_frame(df)


def test_validate_ohlc_bounds_violation():
    df = normalize_frame(_frame())
    df.loc[1, "high"] = df.loc[1, "low"] - 1.0
    with pytest.raises(DataIntegrityError, match="OHLC"):
        validate_frame(df)


def test_validate_close_above_high_violation():
    df = normalize_frame(_frame())
    df.loc[1, "close"] = df.loc[1, "high"] + 5.0
    with pytest.raises(DataIntegrityError, match="OHLC"):
        validate_frame(df)


def test_validate_require_optional():
    df = normalize_frame(_frame())
    with pytest.raises(DataIntegrityError, match="可选列"):
        validate_frame(df, require_optional=["adjust_factor"])


def test_validate_empty_frame_passes_structural_checks():
    df = normalize_frame(_frame()).iloc[0:0]
    validate_frame(df)  # 空表不报错，由调用方决定可用性


def test_validate_can_disable_finite_check():
    df = normalize_frame(_frame())
    df.loc[2, "close"] = np.nan
    validate_frame(df, check_finite=False)  # 显式关闭才允许


# --- align_columns --------------------------------------------------------


def test_align_columns_intersects_dates():
    a = normalize_frame(_frame(5, "2024-01-02"), symbol="A")
    b = normalize_frame(_frame(5, "2024-01-04"), symbol="B")
    out = align_columns({"A": a, "B": b})
    assert set(out.keys()) == {"A", "B"}
    assert (out["A"].index == out["B"].index).all()


def test_align_columns_empty_input():
    assert align_columns({}) == {}


# --- TradingCalendar ------------------------------------------------------


def test_calendar_sorted_and_dedup():
    cal = TradingCalendar(["2024-01-03", "2024-01-02", "2024-01-03"])
    assert cal.days == (pd.Timestamp("2024-01-02").date(), pd.Timestamp("2024-01-03").date())


def test_calendar_contains():
    cal = TradingCalendar(["2024-01-02", "2024-01-03"])
    assert cal.contains("2024-01-02")
    assert not cal.contains("2024-01-04")


def test_calendar_position_raises_on_non_trading_day():
    """非交易日必须抛错，不猜测临近交易日。"""
    cal = TradingCalendar(["2024-01-02", "2024-01-03"])
    with pytest.raises(KeyError):
        cal.position("2024-01-04")


def test_calendar_shift_within_range():
    cal = TradingCalendar(["2024-01-02", "2024-01-03", "2024-01-04"])
    assert cal.shift("2024-01-02", 2) == pd.Timestamp("2024-01-04").date()
    assert cal.shift("2024-01-04", -1) == pd.Timestamp("2024-01-03").date()


def test_calendar_shift_out_of_range_raises_not_clamped():
    """越界必须抛错，不截断到边界（否则会把数据不足伪装成充足）。"""
    cal = TradingCalendar(["2024-01-02", "2024-01-03"])
    with pytest.raises(IndexError):
        cal.shift("2024-01-03", 1)
    with pytest.raises(IndexError):
        cal.shift("2024-01-02", -1)


def test_calendar_between():
    cal = TradingCalendar(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    got = cal.between("2024-01-03", "2024-01-04")
    assert got == [pd.Timestamp("2024-01-03").date(), pd.Timestamp("2024-01-04").date()]


def test_calendar_empty():
    cal = TradingCalendar([])
    assert len(cal) == 0
    assert "empty" in repr(cal)


def test_to_date_variants():
    expected = pd.Timestamp("2024-01-02").date()
    assert _to_date("2024-01-02") == expected
    assert _to_date("20240102") == expected
    assert _to_date(20240102) == expected
    assert _to_date(pd.Timestamp("2024-01-02")) == expected
