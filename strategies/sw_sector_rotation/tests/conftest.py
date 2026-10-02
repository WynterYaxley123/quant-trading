"""SW Sector Rotation Core 的 pytest 配置与 synthetic fixtures。

本文件为策略测试提供：

1. 把**项目根**加入 ``sys.path``，使 ``from strategies.sw_sector_rotation...``
   在容器内（``/workspace``）与 WSL 下都能工作。
2. 确定性 synthetic 行情生成器。**不下载任何真实行情**，不初始化
   Hikyuu / RQAlpha 数据库。

所有随机数据使用固定 seed，保证可复现。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# 本文件位于 <root>/strategies/sw_sector_rotation/tests/conftest.py
# parents[0]=tests, [1]=sw_sector_rotation, [2]=strategies, [3]=项目根
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def make_market_frame(
    n_days: int = 400,
    start: str = "2023-01-03",
    seed: int = 0,
    base_price: float = 100.0,
    drift: float = 0.0003,
    vol: float = 0.012,
) -> pd.DataFrame:
    """生成一个确定性的 canonical market frame（OHLCVA）。

    index 为工作日（``bdate_range``），列含
    ``open/high/low/close/volume/amount``。
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, periods=n_days)
    rets = rng.normal(drift, vol, size=n_days)
    close = base_price * np.cumprod(1.0 + rets)

    intraday = np.abs(rng.normal(0, vol / 2, size=n_days))
    open_ = close * (1.0 + rng.normal(0, vol / 3, size=n_days))
    high = np.maximum(close, open_) * (1.0 + intraday)
    low = np.minimum(close, open_) * (1.0 - intraday)
    volume = rng.uniform(1e6, 5e6, size=n_days)
    amount = volume * close

    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "amount": amount,
        },
        index=dates,
    )


def make_sector_panel(
    n_sectors: int = 12,
    n_days: int = 400,
    start: str = "2023-01-03",
    seed: int = 42,
) -> dict[str, pd.DataFrame]:
    """生成 ``n_sectors`` 个行业的 synthetic panel（用于风险过滤器测试）。"""
    return {
        f"Sector{i:02d}": make_market_frame(
            n_days=n_days, start=start, seed=seed + i, base_price=100.0 + i
        )
        for i in range(n_sectors)
    }


_TICKERS = [
    "ALPHA",
    "BETA",
    "GAMMA",
    "DELTA",
    "EPSILON",
    "ZETA",
    "ETA",
    "THETA",
    "IOTA",
    "KAPPA",
    "LAMBDA",
    "MU",
    "NU",
    "XI",
    "OMICRON",
    "PI",
]


def make_named_panel(
    n_sectors: int = 12,
    n_days: int = 400,
    start: str = "2023-01-03",
    seed: int = 7,
) -> dict[str, pd.DataFrame]:
    """生成带语义化名字的 panel（便于断言排名顺序）。"""
    names = _TICKERS[:n_sectors]
    return {
        name: make_market_frame(n_days=n_days, start=start, seed=seed + i, base_price=100.0 + i)
        for i, name in enumerate(names)
    }


@pytest.fixture
def market_frame() -> pd.DataFrame:
    """单个确定性 canonical market frame。"""
    return make_market_frame()


@pytest.fixture
def sector_panel() -> dict[str, pd.DataFrame]:
    """12 个行业的确定性 panel。"""
    return make_sector_panel()


@pytest.fixture
def named_panel() -> dict[str, pd.DataFrame]:
    """12 个有名字的行业 panel。"""
    return make_named_panel()
