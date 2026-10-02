"""数据加载器 —— 把 provider 的输出装配成策略需要的 panel。

职责边界：
- loaders 负责**组合与对齐**（多标的 → 横截面 panel）。
- 不做因子计算（属策略）、不做回测（属 src.backtesting）。
"""

from __future__ import annotations

from .panel_loader import (
    LoadResult,
    MarketDataRequest,
    load_panel,
)
from .shenwan_sector_loader import (
    load_sector_catalog,
    load_sector_ohlcva,
    load_sector_panel,
)

__all__ = [
    "MarketDataRequest",
    "LoadResult",
    "load_panel",
    "load_sector_catalog",
    "load_sector_ohlcva",
    "load_sector_panel",
]
