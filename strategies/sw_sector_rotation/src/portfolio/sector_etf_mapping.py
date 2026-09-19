"""行业 → ETF 映射与组合权重计算。

迁移来源
--------
Legacy china-market-data v5 ``scripts/quant/predict.py``：
``load_etf_mapping`` / ``score_etf`` 的算法思想。

重要边界
--------
legacy 的 21 只 ETF 列表、``scale_bn``、规模与产品信息属于**历史产品快照**，
**不得**作为当前生产配置直接使用。本模块：

- 提供**算法**：sector → ETF 匹配、穿透（一个 ETF 覆盖多个行业）、
  按分数归一化权重。
- ETF 清单以 ``configs/strategies/sw_sector_rotation_mapping.example.yaml``
  形式提供，标注 ``LEGACY REFERENCE ONLY / REQUIRES REVALIDATION``。
- **不联网更新 ETF 列表。**

未迁移的错误逻辑
----------------
legacy ``strategy.py`` 在红灯 ≥ 3 时把 Top5 缩到 Top3，再归一化到 100%。
这**并没有降低总敞口**，只是提高集中度，因此不予迁移。
风险敞口调整统一走 :func:`apply_risk_budget`，当前为 ``NOT_IMPLEMENTED``。
"""

from __future__ import annotations

from typing import Mapping, Sequence
import math
import warnings

__all__ = [
    "NOT_IMPLEMENTED",
    "RELATION_DIRECT",
    "RELATION_COMPOSITE",
    "RELATION_PROXY",
    "RiskBudgetNotImplemented",
    "apply_risk_budget",
    "match_etfs_for_sectors",
    "normalize_scores_to_weights",
    "passthrough_sector_weights",
]

NOT_IMPLEMENTED = "NOT_IMPLEMENTED"

RELATION_DIRECT = "direct"
RELATION_COMPOSITE = "composite"
RELATION_PROXY = "proxy"
_VALID_RELATIONS = {RELATION_DIRECT, RELATION_COMPOSITE, RELATION_PROXY}


class RiskBudgetNotImplemented(NotImplementedError):
    """风险预算调整尚未实现，等待 ChatGPT 后续设计。"""


def match_etfs_for_sectors(
    ranked_sectors: Sequence[tuple[str, float]],
    mapping: Mapping[str, Mapping],
) -> list[dict]:
    """把排好序的行业映射到 ETF 候选。

    参数
    ----
    ranked_sectors:
        ``[(sector, score), ...]``，已按分数降序。
    mapping:
        ``{sector: {"code": ..., "name": ..., "relation": ..., "sector_weights": {...}}}``。
        ``relation`` 取 ``direct`` / ``composite`` / ``proxy``。
        ``sector_weights`` 可选，用于一个 ETF 穿透多个行业时的权重分配。

    返回
    ----
    ``[{"etf_code", "etf_name", "sectors", "relation", "score"}, ...]``，
    同一 ETF 只出现一次，其分数为所覆盖行业的最高分。
    """
    by_etf: dict[str, dict] = {}
    seen = set()
    for sector, score in ranked_sectors:
        if sector in seen or not math.isfinite(float(score)):
            raise ValueError("ranking 含重复行业或非有限 score")
        seen.add(sector)
        entry = mapping.get(sector)
        if not entry:
            warnings.warn(f"missing ETF mapping: {sector}", RuntimeWarning, stacklevel=2)
            continue
        if not isinstance(entry, Mapping):
            raise ValueError(f"{sector}: 一个行业多个 ETF 的分配规则尚未定义")
        code = entry.get("code")
        if not isinstance(code, str) or not code.strip():
            raise ValueError(f"{sector}: ETF code 必须为非空字符串")
        code = code.strip()
        relation = entry.get("relation", RELATION_PROXY)
        if relation not in _VALID_RELATIONS:
            raise ValueError(f"{sector}: unknown relation {relation}")
        rec = by_etf.get(code)
        if rec is None:
            by_etf[code] = {
                "etf_code": code,
                "etf_name": entry.get("name", ""),
                "sectors": [sector],
                "relation": relation,
                "score": float(score),
            }
        else:
            rec["sectors"].append(sector)
            rec["score"] = max(rec["score"], float(score))
            # 混含直接与包含关系时，保留更强的 direct
            if relation == RELATION_DIRECT:
                rec["relation"] = RELATION_DIRECT
    return sorted(by_etf.values(), key=lambda r: (-r["score"], r["etf_code"]))


def normalize_scores_to_weights(scores: Mapping[str, float]) -> dict[str, float]:
    """把分数归一化为权重，和为 1.0。

    使用 ``score - min(score) + eps`` 做非负平移，避免负分数导致负权重。
    全部相等或为空时等权。
    """
    if not scores:
        return {}
    vals = {k: float(v) for k, v in scores.items()}
    if not all(math.isfinite(v) for v in vals.values()):
        raise ValueError("score 含 NaN/Inf")
    lo = min(vals.values())
    shifted = {k: v - lo + 1e-9 for k, v in vals.items()}
    total = sum(shifted.values())
    if not math.isfinite(total):
        raise ValueError("score 权重归一化溢出")
    if total <= 0:
        n = len(vals)
        return {k: 1.0 / n for k in vals}
    return {k: v / total for k, v in shifted.items()}


def passthrough_sector_weights(
    etf_entry: Mapping, sectors_in_etf: Sequence[str]
) -> dict[str, float]:
    """计算 ETF 内部各行业的穿透权重。

    若 ``etf_entry`` 显式给出 ``sector_weights``，按其归一化；
    否则对 ``sectors_in_etf`` 等权。
    """
    explicit = etf_entry.get("sector_weights")
    if explicit is not None:
        if not isinstance(explicit, Mapping) or not explicit:
            raise ValueError("sector_weights 必须为非空 mapping")
        if any(not math.isfinite(float(v)) or float(v) < 0 for v in explicit.values()):
            raise ValueError("sector_weights 必须为有限非负值")
        total = sum(float(v) for v in explicit.values())
        if math.isfinite(total) and total > 0:
            return {k: float(v) / total for k, v in explicit.items()}
        raise ValueError("sector_weights 总和必须为有限正数")
    if len(set(sectors_in_etf)) != len(sectors_in_etf):
        raise ValueError("穿透行业不得重复")
    if not sectors_in_etf:
        return {}
    w = 1.0 / len(sectors_in_etf)
    return {s: w for s in sectors_in_etf}


def apply_risk_budget(*args, **kwargs):
    """根据 :class:`~strategies.sw_sector_rotation.src.risk.sector_rotation.RiskState` 调整**总敞口**。

    当前 **NOT_IMPLEMENTED**，等待 ChatGPT 后续设计。可选方向（未实现）：
    降低股票/ETF 总仓位、提高现金、减少 Top N、切宽基、停止开仓。

    明确不采用 legacy 的错误做法：把 Top5 缩到 Top3 再归一化到 100%
    —— 那并不降低总敞口，只是增加集中度。
    """
    raise RiskBudgetNotImplemented(
        f"apply_risk_budget 当前为 {NOT_IMPLEMENTED}，"
        "风险敞口调整策略待 ChatGPT 设计后实现。"
    )
