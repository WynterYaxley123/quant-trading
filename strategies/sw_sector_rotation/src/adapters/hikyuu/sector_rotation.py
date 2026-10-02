"""Hikyuu ↔ SW Sector Rotation Core 适配器。

职责
----
1. **KData → canonical market frame**：把 Hikyuu 的 ``KData`` 转成
   纯核心能吃的 OHLCVA DataFrame。
2. **ranking → Hikyuu 可执行组合**：把行业排名结果转成 Hikyuu
   ``Portfolio`` + ``Selector`` + ``AllocateFunds`` 的结构。

边界（重要）
------------
- 本 adapter **只做转换**，不含策略逻辑。策略逻辑全在
  ``strategies.sw_sector_rotation.src.strategy``（框架无关）。
- **不猜 Hikyuu API**。本模块使用的 API 全部在 Hikyuu 2.8.2 上实测确认，
  清单见 :data:`VERIFIED_HIKYUU_API`。
- 当前阶段**不做正式行情回测**（data/ 未初始化）。涉及行情访问的路径
  会抛 :class:`HikyuuDataNotInitialized`，由调用方或测试 skip。

实测确认的 Hikyuu 2.8.2 API
---------------------------
在容器 ``quant-research`` 内、Hikyuu 2.8.2 上通过 ``dir()`` 验证存在：

- ``hikyuu.Portfolio``: ``run / query / set_param / get_param / se / af / tm /
  real_sys_list / performance``
- ``hikyuu.SelectorBase``: ``add_stock_list / add_sys / calculate /
  get_selected / set_scores_filter / add_scores_filter / reset``
- ``hikyuu.AllocateFundsBase``: ``set_param / get_param / reset / query``
- ``hikyuu.System``: ``run / query / set_param / get_stock / st / sp / mm / tp /
  pg / to / ev``
- ``hikyuu.SystemWeight`` / ``hikyuu.TradeCostBase`` / ``hikyuu.SlippageBase``
  存在

尚未验证的路径（需行情数据初始化后在 Hikyuu 侧补测）：
构造自定义 ``Selector`` / ``AllocateFunds`` 子类并接入 ``Portfolio.run``
的完整链路。本 adapter 以 **protocol（文档化接口）** 形式提供该扩展点。
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import pandas as pd

from strategies.sw_sector_rotation.src.factors.sector_rotation import CANONICAL_COLUMNS

__all__ = [
    "VERIFIED_HIKYUU_API",
    "HikyuuDataNotInitialized",
    "SectorWeightTarget",
    "HikyuuSelectorProtocol",
    "HikyuuAllocatorProtocol",
    "kdata_to_market_frame",
    "ranked_sectors_to_targets",
    "targets_to_system_weights",
    "build_stock_selector_input",
    "AdaptersNotWiredReason",
]

#: 实测确认存在的 Hikyuu 2.8.2 API（用于文档与测试断言）。
VERIFIED_HIKYUU_API: dict[str, tuple[str, ...]] = {
    "Portfolio": (
        "run",
        "query",
        "set_param",
        "get_param",
        "se",
        "af",
        "tm",
        "real_sys_list",
        "performance",
        "reset",
    ),
    "SelectorBase": (
        "add_stock_list",
        "add_sys",
        "calculate",
        "get_selected",
        "set_scores_filter",
        "add_scores_filter",
        "reset",
        "name",
    ),
    "AllocateFundsBase": ("set_param", "get_param", "reset", "query", "name"),
    "System": (
        "run",
        "query",
        "set_param",
        "get_param",
        "get_stock",
        "st",
        "sp",
        "mm",
        "tp",
        "pg",
        "to",
        "ev",
        "clone",
    ),
}


class HikyuuDataNotInitialized(RuntimeError):
    """Hikyuu 行情库尚未初始化。

    当前项目 ``data/`` 为空，无法访问真实 KData。这是**预期状态**，
    不是缺陷。测试应捕获本异常并 ``pytest.skip``。
    """


class AdaptersNotWiredReason:
    """adapter 尚未接线的原因（用于文档与报告，不是异常）。"""

    DATA_NOT_INITIALIZED = "DATA_NOT_INITIALIZED"
    SELECTOR_SUBCLASS_PENDING = "SELECTOR_SUBCLASS_PENDING"


@dataclass
class SectorWeightTarget:
    """行业/ETF 目标权重的一条记录。"""

    symbol: str
    target_weight: float
    sectors: list[str] = field(default_factory=list)
    relation: str = ""


# ---------------------------------------------------------------------------
# KData → canonical market frame
# ---------------------------------------------------------------------------

#: Hikyuu 中日线 KData 的字段名 → canonical 列名。
_KFIELD_TO_CANONICAL = {
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
    "amount": "amount",
}


def kdata_to_market_frame(kdata: Any) -> pd.DataFrame:
    """把 Hikyuu ``KData`` 转成 canonical market frame。

    参数
    ----
    kdata:
        Hikyuu 的 ``KData`` 对象（如 ``stock.get_kdata(query)``）。

    返回
    ----
    ``DataFrame``，index 为 ``DatetimeIndex``，列含
    ``open/high/low/close/volume/amount``。

    异常
    ----
    若 ``kdata`` 为 ``None`` 或为空（通常意味着行情库未初始化），
    抛 :class:`HikyuuDataNotInitialized`。

    说明
    ----
    本函数**不 import hikyuu**，只按 KData 的数值接口读取，因此可在
    无 Hikyuu 的环境下用 mock 对象测试。
    """
    if kdata is None:
        raise HikyuuDataNotInitialized(
            "KData 为 None，通常表示 Hikyuu 行情库未初始化（data/ 为空）"
        )
    try:
        length = len(kdata)
    except TypeError as exc:  # pragma: no cover - 防御
        raise TypeError(f"kdata 不支持 len(): {type(kdata).__name__}") from exc
    if length == 0:
        raise HikyuuDataNotInitialized("KData 长度为 0，行情库无数据")

    getter = getattr(kdata, "get_datetime_list", None)
    datetimes = None
    if callable(getter):
        datetimes = list(getter())
    if datetimes is None and hasattr(kdata, "get_kdata"):
        pass  # 不递归，交由调用方处理
    if datetimes is None:
        # 退路：部分版本可用 .datetime 迭代
        try:
            datetimes = [k.datetime for k in kdata]
        except Exception as exc:  # pragma: no cover - 依赖具体版本
            raise TypeError("无法从 KData 读取日期，请确认 Hikyuu 版本与 KData 类型") from exc

    data = {}
    for kfield, col in _KFIELD_TO_CANONICAL.items():
        try:
            data[col] = [float(getattr(k, kfield)) for k in kdata]
        except AttributeError as exc:
            raise TypeError(f"KData 元素缺少字段 {kfield}") from exc

    frame = pd.DataFrame(data, index=pd.to_datetime(datetimes))
    frame = frame.sort_index()
    missing = [c for c in CANONICAL_COLUMNS if c not in frame.columns]
    if missing:  # pragma: no cover - 防御
        raise ValueError(f"转换后缺少列: {missing}")
    return frame[list(CANONICAL_COLUMNS)]


# ---------------------------------------------------------------------------
# ranking → Hikyuu 目标
# ---------------------------------------------------------------------------


def ranked_sectors_to_targets(
    ranked_sectors: Sequence[tuple[str, float]],
    etf_candidates: Sequence[Mapping] | None = None,
) -> list[SectorWeightTarget]:
    """行业排名 → 目标权重记录。

    ``etf_candidates`` 为列表时以 ETF 为单位（空列表仍为空）；
    仅 ``None`` 保留旧行业描述路径，不代表行业代码可交易。
    权重取自候选自身的 ``weight`` 字段（若存在），否则等权。
    """
    if etf_candidates is not None:
        if not etf_candidates:
            return []  # 显式空 ETF 集绝不能回退成行业代码交易
        n = len(etf_candidates) or 1
        out = []
        codes = [c.get("etf_code") for c in etf_candidates]
        if any(not isinstance(c, str) or not c.strip() for c in codes):
            raise ValueError("ETF candidate 缺少 symbol")
        if len(set(codes)) != len(codes):
            raise ValueError("ETF candidates 含 duplicate ETF，请先完成映射合并")
        present = ["weight" in c for c in etf_candidates]
        if any(present) and not all(present):
            raise ValueError("ETF weights 不得部分缺失")
        for cand in etf_candidates:
            w = float(cand.get("weight", 1.0 / n))
            if not math.isfinite(w) or w < 0:
                raise ValueError("ETF weight 必须为有限非负数")
            out.append(
                SectorWeightTarget(
                    symbol=str(cand.get("etf_code", "")),
                    target_weight=w,
                    sectors=list(cand.get("sectors", [])),
                    relation=str(cand.get("relation", "")),
                )
            )
        total = sum(t.target_weight for t in out)
        if not math.isfinite(total) or total <= 0:
            raise ValueError("ETF weight 总和必须为有限正数")
        if total > 0:
            for t in out:
                t.target_weight = t.target_weight / total
        return out

    if len({s for s, _ in ranked_sectors}) != len(ranked_sectors):
        raise ValueError("行业 targets 不得重复")
    n = len(ranked_sectors) or 1
    return [
        SectorWeightTarget(symbol=sector, target_weight=1.0 / n, sectors=[sector])
        for sector, _ in ranked_sectors
    ]


def targets_to_system_weights(targets: Sequence[SectorWeightTarget]) -> list[dict]:
    """把目标权重转成 Hikyuu ``SystemWeight`` 可消费的字典列表。

    Hikyuu 的 ``SystemWeight`` 需要 ``(System, weight)``。本函数只产出
    ``{"symbol", "weight"}``，实际 ``System`` 实例需在行情初始化后由
    ChatGPT 侧构造并绑定。
    """
    _validate_targets(targets)
    if any(not t.symbol for t in targets):
        warnings.warn(
            "跳过缺少 symbol 的 legacy target；不得作为完整订单", RuntimeWarning, stacklevel=2
        )
    return [{"symbol": t.symbol, "weight": float(t.target_weight)} for t in targets if t.symbol]


def build_stock_selector_input(
    targets: Sequence[SectorWeightTarget],
    symbol_resolver: Mapping[str, Any] | None = None,
) -> dict:
    """构造 ``SelectorBase.add_stock_list`` / ``set_scores_filter`` 的输入描述。

    返回一个**描述性** dict，而不是直接调用 Hikyuu：
    ``{"stock_list": [...], "scores": {...}, "weights": {...}}``。
    真实的 ``Stock`` 对象需要 ``StockManager`` 与行情库，当前不可用。

    ``symbol_resolver`` 可把行业/ETF 代码映射到 Hikyuu ``Stock`` 或代码串；
    为 ``None`` 时原样传递 symbol。
    """
    resolver = symbol_resolver or {}
    _validate_targets(targets)
    if any(not t.symbol for t in targets):
        raise ValueError("Selector target 缺少 symbol")
    if symbol_resolver is not None and any(t.symbol not in resolver for t in targets):
        raise ValueError("symbol_resolver 缺少 ETF 映射")
    stock_list = []
    scores = {}
    weights = {}
    for t in targets:
        sym = resolver.get(t.symbol, t.symbol)
        stock_list.append(sym)
        weights[t.symbol] = float(t.target_weight)
        scores[t.symbol] = float(t.target_weight)
    return {"stock_list": stock_list, "scores": scores, "weights": weights}


def _validate_targets(targets: Sequence[SectorWeightTarget]) -> None:
    symbols = [t.symbol for t in targets if t.symbol]
    if len(symbols) != len(set(symbols)):
        raise ValueError("duplicate target symbol")
    if any(not math.isfinite(t.target_weight) or t.target_weight < 0 for t in targets):
        raise ValueError("target weight 必须为有限非负数")


# ---------------------------------------------------------------------------
# 扩展点 protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class HikyuuSelectorProtocol(Protocol):
    """行业选择器需实现的接口（Hikyuu ``SelectorBase`` 子类）。

    由 ChatGPT 在行情初始化后实现并注册到 ``Portfolio.se``。
    """

    def add_stock_list(self, stock_list) -> None: ...

    def calculate(self): ...

    def get_selected(self): ...


@runtime_checkable
class HikyuuAllocatorProtocol(Protocol):
    """资金分配器需实现的接口（Hikyuu ``AllocateFundsBase`` 子类）。

    由 ChatGPT 在行情初始化后实现并注册到 ``Portfolio.af``。
    权重来自 :func:`targets_to_system_weights`。
    """

    def set_param(self, name, value) -> None: ...

    def reset(self) -> None: ...
