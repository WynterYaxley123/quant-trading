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

import math
import re
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import overload

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
    "MappingEvidence",
    "validate_mapping_evidence",
    "resolve_primary_mapping",
    "daily_mapping_availability",
    "mapping_admission",
]

NOT_IMPLEMENTED = "NOT_IMPLEMENTED"

RELATION_DIRECT = "direct"
RELATION_COMPOSITE = "composite"
RELATION_PROXY = "proxy"
_VALID_RELATIONS = {RELATION_DIRECT, RELATION_COMPOSITE, RELATION_PROXY}

MAPPING_STATUSES = frozenset(
    {
        "VALIDATED",
        "UNKNOWN",
        "NO_SUITABLE_ETF",
        "NOT_LISTED_YET",
        "MULTIPLE_CANDIDATES",
        "SOURCE_INSUFFICIENT",
    }
)


@dataclass(frozen=True)
class MappingEvidence:
    """One evidence-backed relationship, not an ETF selection or trade signal."""

    sector_code: str
    sector_name: str
    etf_code: str | None = None
    etf_name: str | None = None
    market: str | None = None
    tracking_index_code: str | None = None
    tracking_index_name: str | None = None
    mapping_status: str = "UNKNOWN"
    mapping_effective_from: str | None = None
    mapping_effective_to: str | None = None
    etf_listing_date: str | None = None
    source_provider: str | None = None
    source_url: str | None = None
    source_file: str | None = None
    source_retrieved_at: str | None = None
    source_sha256: str | None = None
    evidence_type: str | None = None
    is_primary: bool = False
    notes: str | None = None


@overload
def _date(value: str) -> date: ...


@overload
def _date(value: None) -> None: ...


def _date(value: str | None) -> date | None:
    if value is None:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"日期须为 YYYY-MM-DD: {value!r}")
    return date.fromisoformat(value)


def validate_mapping_evidence(rows: Sequence[MappingEvidence], catalog: Mapping[str, str]) -> None:
    """Reject fabricated dates, unverifiable primary relationships and ambiguity."""
    if not rows:
        raise ValueError("mapping 必须显式包含 UNKNOWN 行，不能用空表暗示全覆盖")
    grouped: dict[str, list[MappingEvidence]] = {}
    for r in rows:
        if r.sector_code not in catalog or catalog[r.sector_code] != r.sector_name:
            raise ValueError(f"无效的二级行业代码/名称: {r.sector_code}")
        if r.mapping_status not in MAPPING_STATUSES:
            raise ValueError(f"无效 mapping_status: {r.mapping_status}")
        if r.etf_code is not None and not re.fullmatch(r"(sh|sz)\d{6}", r.etf_code):
            raise ValueError(f"ETF 代码必须含市场前缀: {r.etf_code}")
        start = _date(r.mapping_effective_from)
        end = _date(r.mapping_effective_to)
        listed = _date(r.etf_listing_date)
        if start and end and end < start:
            raise ValueError("mapping effective_to 早于 effective_from")
        if r.source_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", r.source_sha256):
            raise ValueError("source_sha256 格式错误")
        if r.source_file and not r.source_sha256:
            raise ValueError("本地来源文件必须记录 SHA256")
        if r.is_primary and r.mapping_status != "VALIDATED":
            raise ValueError("只有 VALIDATED 关系可标记 primary")
        if r.mapping_status == "VALIDATED":
            required = (
                r.etf_code,
                r.etf_name,
                r.market,
                r.tracking_index_code,
                r.tracking_index_name,
                r.mapping_effective_from,
                r.etf_listing_date,
                r.source_provider,
                r.source_retrieved_at,
                r.evidence_type,
            )
            if not all(required) or not (r.source_url or r.source_file):
                raise ValueError("VALIDATED mapping 缺关系、时点或来源证据")
            assert r.etf_code is not None
            if r.market != r.etf_code[:2]:
                raise ValueError("ETF market 与代码不符")
            # Relationship may predate listing; execution still cannot.
            if listed is None:
                raise ValueError("VALIDATED mapping 缺上市日期")
        grouped.setdefault(r.sector_code, []).append(r)
    if set(grouped) != set(catalog):
        raise ValueError("必须为全部二级行业显式记录 mapping 状态")
    for code, candidates in grouped.items():
        primaries = [r for r in candidates if r.is_primary]
        for i, left in enumerate(primaries):
            for right in primaries[i + 1 :]:
                left_start, right_start = (
                    _date(left.mapping_effective_from),
                    _date(right.mapping_effective_from),
                )
                left_end, right_end = (
                    _date(left.mapping_effective_to),
                    _date(right.mapping_effective_to),
                )
                assert left_start is not None and right_start is not None
                if (left_end is None or right_start <= left_end) and (
                    right_end is None or left_start <= right_end
                ):
                    raise ValueError(f"{code}: 同期 primary ETF 不唯一")
        if (
            len(candidates) > 1
            and not primaries
            and not all(r.mapping_status == "MULTIPLE_CANDIDATES" for r in candidates)
        ):
            raise ValueError(f"{code}: 多候选未明确标记 MULTIPLE_CANDIDATES")


def resolve_primary_mapping(
    rows: Sequence[MappingEvidence], sector_code: str, as_of: str
) -> MappingEvidence | None:
    """Resolve only an explicitly validated primary active on this date."""
    day = _date(as_of)
    matches = [
        r
        for r in rows
        if r.sector_code == sector_code
        and r.is_primary
        and r.mapping_status == "VALIDATED"
        and (start := _date(r.mapping_effective_from)) is not None
        and day >= start
        and ((end := _date(r.mapping_effective_to)) is None or day <= end)
    ]
    if len(matches) > 1:
        raise ValueError(f"{sector_code}: primary ETF 不唯一")
    if not matches:
        return None
    return matches[0]


def daily_mapping_availability(
    rows: Sequence[MappingEvidence],
    sector_code: str,
    as_of: str,
    *,
    execution_date: str | None,
    bar: Mapping | None,
    sector_bar_valid: bool,
) -> dict:
    """Use the signal session and the *next* execution session separately."""
    from quant_primitives.ohlc import valid_daily_open

    if execution_date is not None and _date(execution_date) <= _date(as_of):
        raise ValueError("execution_date 必须晚于 signal date")
    if execution_date is None and bar is not None:
        raise ValueError("无下一交易日时不得提供 ETF bar")
    r = resolve_primary_mapping(rows, sector_code, as_of)
    if r is not None and execution_date is not None:  # noqa: SIM102 -- Preserve independently documented frozen validation branches.
        if resolve_primary_mapping(rows, sector_code, execution_date) != r:
            r = None
    active = r is not None
    listed = (
        r is not None
        and (listing_date := _date(r.etf_listing_date)) is not None
        and _date(as_of) >= listing_date
    )
    has_bar = bool(
        r is not None
        and execution_date is not None
        and bar is not None
        and bar.get("date") == execution_date
        and bar.get("etf_code") == r.etf_code
    )
    tradable = has_bar and valid_daily_open(bar)
    return {
        "sector_code": sector_code,
        "date": as_of,
        "execution_date": execution_date,
        "sector_bar_valid": bool(sector_bar_valid),
        "is_mapping_active": active,
        "is_listed": listed,
        "has_bar": has_bar,
        "is_tradable": tradable,
        "is_etf_executable": active and listed and tradable,
        "is_executable": bool(sector_bar_valid) and active and listed and tradable,
    }


def mapping_admission(
    rows: Sequence[MappingEvidence],
    catalog: Mapping[str, str],
    executable_counts: Sequence[int],
) -> str:
    """A conservative gate: missing evidence never becomes READY."""
    validate_mapping_evidence(rows, catalog)
    mapped = {r.sector_code for r in rows if r.mapping_status == "VALIDATED" and r.is_primary}
    if not mapped or not executable_counts:
        return "ETF_MAPPING_NOT_ADMISSIBLE"
    if len(mapped) == len(catalog) and min(executable_counts) >= 5:
        return "ETF_MAPPING_READY"
    return "ETF_MAPPING_PARTIAL"


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
        f"apply_risk_budget 当前为 {NOT_IMPLEMENTED}，风险敞口调整策略待 ChatGPT 设计后实现。"
    )
