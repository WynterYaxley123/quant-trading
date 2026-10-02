"""交易日历。

来源（实测于 Hikyuu 2.8.2，见 ``docs/data/hikyuu_data_capabilities.md``）：

- ``StockManager.is_holiday(date)`` 可用（实测 2024-01-01 → True，2024-01-02 → False）。
- ``StockManager.get_trading_calendar(query, market)`` 在当前数据配置下**返回空**
  （Holiavy 表有数据、Market.lastDate 未更新，无法作为基准）。
- **可靠做法**：从已加载证券的 ``KData.get_datetime_list()`` 取交易日，
  它自动跳过周末与休市日（实测 2024-01-02..01-09 正确得到 6 个交易日）。

因此本模块提供两条路径：

1. :func:`trading_days_from_kdata` —— 从证券 K线提取交易日（推荐，实测可用）。
2. :func:`is_holiday` / :func:`trading_days_from_holidays` —— 基于
   ``is_holiday`` 生成区间内交易日（不依赖任何证券，但有数据源依赖）。

两条路径都**不填充**、不猜测缺失日期。
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from datetime import date, datetime, timedelta
from typing import cast

__all__ = [
    "TradingCalendar",
    "is_holiday",
    "trading_days_from_holidays",
]


def _to_date(d: object) -> date:
    """把多种日期表示转成 ``datetime.date``。"""
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        return datetime.strptime(d.replace("-", "")[:8], "%Y%m%d").date()
    if isinstance(d, int):
        s = str(d)[:8]
        return datetime.strptime(s, "%Y%m%d").date()
    # hikyuu.Datetime
    if hasattr(d, "year") and hasattr(d, "month") and hasattr(d, "day"):
        return date(int(d.year), int(d.month), int(d.day))
    raise TypeError(f"无法识别的日期类型: {type(d).__name__}")


def is_holiday(d: object) -> bool:
    """判断某日是否为休市日（委托 Hikyuu ``StockManager.is_holiday``）。

    需要 Hikyuu 已加载（``hikyuu.load_hikyuu``）。未加载时抛 RuntimeError，
    不静默返回 False —— 把「未知」误判为「交易日」会造成严重时点错误。
    """
    import hikyuu

    sm = hikyuu.StockManager.instance()
    if len(sm) == 0:
        raise RuntimeError(
            "StockManager 未加载数据，无法判断交易日。"
            "请先调用 hikyuu.load_hikyuu(config_file=...) 或项目数据层初始化。"
        )
    return bool(sm.is_holiday(hikyuu.Datetime(int(_to_date(d).strftime("%Y%m%d")))))


def trading_days_from_holidays(start: object, end: object) -> list[date]:
    """用 ``is_holiday`` 枚举 ``[start, end]`` 内的交易日。

    不含开始/结束日的交易日会全部返回。若 ``is_holiday`` 不可用则抛异常，
    **不静默退化为「全部日期都是交易日」**。
    """
    s, e = _to_date(start), _to_date(end)
    if e < s:
        raise ValueError(f"结束日期 {e} 早于开始日期 {s}")
    out: list[date] = []
    cur = s
    step = timedelta(days=1)
    while cur <= e:
        if cur.weekday() < 5 and not is_holiday(cur):
            out.append(cur)
        cur += step
    return out


class TradingCalendar:
    """交易日历容器。

    构造后用 :meth:`index` 取有序日期序列，用 :meth:`contains` 判断某日是否交易日，
    用 :meth:`shift` 按交易日偏移（回测里计算 label 边界常用）。

    时点护栏：本类的所有方法都只使用**已给定**的日期集合，
    不引入未来日期。
    """

    def __init__(self, days: Iterable[object]) -> None:
        norm = sorted({_to_date(d) for d in days})
        self._days: tuple[date, ...] = tuple(norm)
        self._pos: dict[date, int] = {d: i for i, d in enumerate(self._days)}

    def __len__(self) -> int:
        return len(self._days)

    def __iter__(self) -> Iterator[date]:
        return iter(self._days)

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        if not self._days:
            return "TradingCalendar(empty)"
        return f"TradingCalendar(n={len(self._days)}, {self._days[0]}..{self._days[-1]})"

    @property
    def days(self) -> tuple[date, ...]:
        """全部交易日（升序元组）。"""
        return self._days

    def index(self) -> list[date]:
        """交易日列表（升序）。"""
        return list(self._days)

    def contains(self, d: object) -> bool:
        return _to_date(d) in self._pos

    def position(self, d: object) -> int:
        """返回某交易日的下标；非交易日抛 KeyError（不猜测临近交易日）。"""
        return self._pos[_to_date(d)]

    def shift(self, d: object, n: int) -> date:
        """从交易日 ``d`` 偏移 ``n`` 个交易日（``n`` 可为负）。

        越界抛 IndexError，**不截断到边界** —— 静默截断会把
        「数据不足」伪装成「数据充足」。
        """
        i = self.position(d)
        j = i + n
        if j < 0 or j >= len(self._days):
            raise IndexError(
                f"交易日偏移越界: {d} {n:+d} → 下标 {j}，可用范围 [0, {len(self._days) - 1}]"
            )
        return self._days[j]

    def between(self, start: object, end: object) -> list[date]:
        """返回 ``[start, end]`` 闭区间内的交易日。"""
        s, e = _to_date(start), _to_date(end)
        return [d for d in self._days if s <= d <= e]

    @classmethod
    def from_kdata(cls, kdata: object) -> "TradingCalendar":
        """从 Hikyuu ``KData`` 对象构造日历（推荐路径）。

        使用 ``kd.get_datetime_list()``，该序列已自动排除周末与休市日。
        """
        dts = kdata.get_datetime_list() if hasattr(kdata, "get_datetime_list") else kdata
        return cls(cast(Iterable[object], dts))

    @classmethod
    def from_dates(cls, dates: Sequence[object]) -> "TradingCalendar":
        return cls(dates)
