"""provider 抽象基类。

只定义**最小**契约：能力声明、可用性、取数。不做过度抽象。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Mapping, Sequence

import pandas as pd


class ProviderUnavailable(RuntimeError):
    """provider 在当前环境不可用（包缺失 / 网络不通 / 数据未初始化）。

    与「数据为空」区分：前者是**能力问题**，后者是**数据问题**。
    调用方据此决定是否 fallback 到下一 provider。
    """

    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason
        super().__init__(f"provider {provider!r} 不可用: {reason}")


@dataclass(frozen=True)
class ProviderCapabilities:
    """provider 支持的能力声明。"""

    #: 支持的资产类型，如 ``{"ETF", "STOCK", "INDEX"}``
    asset_types: frozenset[str] = field(default_factory=frozenset)
    #: 支持的 K线周期，如 ``{"DAY", "1MIN", "5MIN"}``
    ktypes: frozenset[str] = field(default_factory=frozenset)
    #: 是否提供复权因子
    provides_adjust_factor: bool = False
    #: 是否 point-in-time 安全（不引入未来信息）
    is_pit: bool = True
    #: 数据的经验起始年份（用于文档与校验，不用于裁剪）
    history_start: int | None = None


class DataProvider(ABC):
    """行情数据源抽象。

    实现者只需覆盖 :meth:`is_available` 与 :meth:`fetch_daily`。
    """

    #: provider 唯一标识
    name: str = "unnamed"

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """返回能力声明。"""

    @abstractmethod
    def is_available(self) -> bool:
        """当前环境是否可用。

        实现应捕获自身异常并返回 False，**不要**把异常抛给调用方
        （可用性探测本身不应成为失败点）。
        """

    @abstractmethod
    def fetch_daily(
        self,
        symbols: Sequence[str],
        start: object,
        end: object,
    ) -> Mapping[str, pd.DataFrame]:
        """取日线数据，返回 ``{symbol: canonical_frame}``。

        - 返回的 frame 必须已通过 :func:`src.data.schema.validate_frame`。
        - 若某 symbol 无数据，**不要**伪造空行，直接不放进返回 dict。
        - 若整个 provider 不可用，抛 :class:`ProviderUnavailable`。
        """
