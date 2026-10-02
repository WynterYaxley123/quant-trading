"""canonical frame → 策略所需 market frame。

策略的 ``build_panel`` 期待 ``{name: DataFrame}``，其中 DataFrame 以
``DatetimeIndex`` 为索引、含 ``open/high/low/close/volume/amount`` 列。

本模块做这一次转换，让**策略核心不需要知道 canonical schema 的存在**，
也让数据层不需要知道策略的索引约定。
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

__all__ = ["canonical_to_market_frame"]

#: canonical 数值列 → 策略 frame 列（名称一致，保持显式以便未来调整）
_COLUMN_PASSTHROUGH = ("open", "high", "low", "close", "volume", "amount")


def canonical_to_market_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """把 canonical frame 转成策略所需格式（DatetimeIndex + OHLCVA 列）。

    - 保留 ``open/high/low/close/volume``（必需）与 ``amount``（若存在）。
    - 索引设为 ``date``（升序，与 canonical frame 一致）。
    - 丢弃 ``symbol`` 等元数据列（调用方以 dict key 区分标的）。
    """
    if frame is None or len(frame) == 0:
        raise ValueError("canonical_to_market_frame 收到空 frame")
    if "date" not in frame.columns:
        raise ValueError("canonical frame 缺少 date 列")

    cols = [c for c in _COLUMN_PASSTHROUGH if c in frame.columns]
    missing_required = [
        c for c in ("open", "high", "low", "close", "volume") if c not in frame.columns
    ]
    if missing_required:
        raise ValueError(f"canonical frame 缺少必需列: {missing_required}")

    out = frame.loc[:, cols].copy()
    out.index = pd.DatetimeIndex(pd.to_datetime(frame["date"]))
    out.index.name = "date"
    return out.sort_index()


def panel_to_market_frames(
    panel: Mapping[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """批量转换：``{symbol: canonical_frame}`` → ``{symbol: market_frame}``。"""
    return {k: canonical_to_market_frame(v) for k, v in panel.items()}
