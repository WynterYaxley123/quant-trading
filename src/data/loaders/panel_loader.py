"""panel 加载：多标的 → 横截面 panel。

关键约束
--------
1. **不伪造数据**：某标的在某日无数据时，该标的该日不进入 panel；
   是否 forward-fill 由调用方（策略/回测）显式决定并记录，
   本模块默认不做任何填充。
2. **provider fallback**：按候选顺序尝试，全部失败才抛错；
   某个 provider 缺某标的时记录进 ``missing`` 而不是整体失败。
3. **原样报告**：返回 ``LoadResult``，内含 panel、日历、每个标的的来源与
   数据区间，供 metadata 追溯。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from ..calendar import TradingCalendar
from ..providers.base import DataProvider, ProviderUnavailable
from ..schema import DataIntegrityError, validate_frame

__all__ = ["MarketDataRequest", "LoadResult", "load_panel"]


@dataclass(frozen=True)
class MarketDataRequest:
    """一次取数请求。"""

    symbols: Sequence[str]
    start: object
    end: object
    #: 过滤资产类型（如 ``{"ETF"}``）；None 表示不过滤
    asset_types: frozenset[str] | None = None
    #: K线周期
    ktype: str = "DAY"

    def __post_init__(self) -> None:
        if not self.symbols:
            raise ValueError("MarketDataRequest.symbols 不能为空")


@dataclass
class LoadResult:
    """取数结果，含完整溯源信息。"""

    #: ``{symbol: canonical_frame}``，索引为 RangeIndex（含 date 列）
    panel: dict[str, pd.DataFrame] = field(default_factory=dict)
    #: 交易日历（由 panel 中某标的的日期构造；panel 为空时为空日历）
    calendar: TradingCalendar = field(default_factory=lambda: TradingCalendar([]))
    #: 每个 symbol 的 provider 名称
    sources: dict[str, str] = field(default_factory=dict)
    #: 请求了但未取到的 symbol 及原因
    missing: dict[str, str] = field(default_factory=dict)
    #: 每个 symbol 的实际数据区间
    coverage: dict[str, tuple[date, date]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return bool(self.panel)

    def symbols(self) -> list[str]:
        return list(self.panel.keys())


def load_panel(
    request: MarketDataRequest,
    providers: Sequence[DataProvider],
) -> LoadResult:
    """按顺序尝试 providers，装配 canonical panel。

    - 某 symbol 在第一个可用 provider 取到即停止尝试其余 provider。
    - provider 抛 :class:`ProviderUnavailable` 时跳过它，继续下一个。
    - 全部 provider 都失败 → 抛 :class:`ProviderUnavailable`。
    - 空的 providers 列表 → 抛 ValueError（调用方错误）。
    """
    if not providers:
        raise ValueError("load_panel 需要至少一个 provider")

    result = LoadResult()
    remaining = list(request.symbols)
    used: dict[str, str] = {}

    last_error: Exception | None = None
    any_available = False
    for p in providers:
        if not remaining:
            break
        try:
            avail = p.is_available()
        except Exception as e:  # provider 探测不应导致失败
            last_error = e
            continue
        if not avail:
            last_error = ProviderUnavailable(p.name, "is_available() 返回 False")
            continue
        any_available = True
        try:
            frames = p.fetch_daily(remaining, request.start, request.end)
        except ProviderUnavailable as e:
            last_error = e
            continue

        for sym, df in frames.items():
            if request.asset_types is not None:
                # 资产类型过滤：provider 未提供 asset_type 列时按子类判断
                at = df.get("asset_type")
                if (
                    at is not None
                    and len(at)
                    and str(at.iloc[0]).upper() not in {a.upper() for a in request.asset_types}
                ):
                    result.missing[sym] = (
                        f"资产类型 {at.iloc[0]} 不在请求范围 {sorted(request.asset_types)}"
                    )
                    continue
            try:
                validate_frame(df)
            except DataIntegrityError as e:
                result.missing[sym] = f"数据校验失败: {e}"
                continue
            result.panel[sym] = df
            result.sources[sym] = p.name
            used[sym] = p.name
            d0 = pd.Timestamp(df["date"].iloc[0]).date()
            d1 = pd.Timestamp(df["date"].iloc[-1]).date()
            result.coverage[sym] = (d0, d1)
            if sym in remaining:
                remaining.remove(sym)

    for sym in remaining:
        result.missing.setdefault(sym, "所有 provider 均未返回该标的数据")

    if not result.panel:
        if not any_available:
            raise ProviderUnavailable(
                "all",
                f"没有任何可用 provider。最后错误: {last_error}",
            )
        # 有可用 provider 但确实无数据 —— 这是数据问题，不是能力问题
        raise DataIntegrityError(
            f"provider 可用但未取到任何数据。请求: {list(request.symbols)}，"
            f"未取到: {result.missing}"
        )

    # 日历：取覆盖最长的标的的日期序列（不取并集，避免把某标的的停牌日
    # 当成全市场交易日）
    longest = max(result.panel.values(), key=len)
    result.calendar = TradingCalendar(longest["date"].tolist())
    return result
