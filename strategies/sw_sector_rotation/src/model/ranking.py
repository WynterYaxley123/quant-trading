"""行业排名 → ETF 候选 → 权重（纯函数）。

迁移来源
--------
Legacy china-market-data v5 ``scripts/quant/predict.py`` 的排序与
``strategy.py`` 的权重归一化。

边界
----
本模块**只做纯计算**，不读取风险状态、不调整敞口。
风险敞口调整走 ``strategies.sw_sector_rotation.src.portfolio.sector_etf_mapping.apply_risk_budget``
（当前 NOT_IMPLEMENTED）。这是与 legacy 的关键差异：legacy 让
``strategy.py`` 在红灯时把 Top5 改 Top3 并归一化，那不是降敞口，
而是提高集中度，故不迁移。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

__all__ = [
    "rank_sectors",
    "select_top",
    "sector_scores_to_weights",
    "build_etf_candidates",
]


def rank_sectors(scores: Mapping[str, float]) -> list[tuple[str, float]]:
    """按分数降序排名。分值相同按行业名稳定排序。"""
    if not np.isfinite(list(scores.values())).all():
        raise ValueError("ranking score 含 NaN/Inf")
    return sorted(scores.items(), key=lambda kv: (-float(kv[1]), kv[0]))


def select_top(ranked: Sequence[tuple[str, float]], top_n: int) -> list[tuple[str, float]]:
    """取前 ``top_n``。``top_n <= 0`` 返回空列表。"""
    if top_n <= 0:
        return []
    return list(ranked[:top_n])


def sector_scores_to_weights(
    ranked: Sequence[tuple[str, float]],
    *,
    long_only: bool = True,
) -> dict[str, float]:
    """行业分数 → 组合权重，和为 1.0。

    用 ``score - min + eps`` 非负平移后归一化，避免负分数产生负权重
    （``long_only=True`` 时）。全相等时等权。
    """
    if not ranked:
        return {}
    names = [s for s, _ in ranked]
    vals = np.array([float(v) for _, v in ranked], dtype=float)
    if len(set(names)) != len(names) or not np.isfinite(vals).all():
        raise ValueError("权重输入含重复行业或非有限 score")
    if long_only:
        vals = vals - vals.min() + 1e-9
    total = float(vals.sum())
    if not np.isfinite(total):
        raise ValueError("权重归一化溢出")
    if total <= 0:
        w = 1.0 / len(names)
        return {s: w for s in names}
    return {s: float(v / total) for s, v in zip(names, vals)}


def build_etf_candidates(
    ranked: Sequence[tuple[str, float]],
    mapping: Mapping[str, Mapping],
    top_n: int,
) -> list[dict]:
    """把 Top N 行业映射为 ETF 候选（不含权重）。

    复用 :func:`strategies.sw_sector_rotation.src.portfolio.sector_etf_mapping.match_etfs_for_sectors`，
    以保证 ETF 去重规则唯一。
    """
    from strategies.sw_sector_rotation.src.portfolio.sector_etf_mapping import (
        match_etfs_for_sectors,
    )

    return match_etfs_for_sectors(select_top(ranked, top_n), mapping)
