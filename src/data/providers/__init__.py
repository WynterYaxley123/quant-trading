"""数据源 provider。

每个 provider 必须显式声明：

- ``name`` —— 唯一标识
- ``capabilities`` —— 支持的数据类别（资产类型 / K线类型）
- ``is_available()`` —— 当前环境是否可用（区分「包可用 / 网络可用 / provider 可用」）

设计约束（任务书第八节）：**不得把单一 provider 故障判定为整个数据层失败**。
调用方应遍历候选 provider，逐个尝试，全部失败才报错。
"""

from __future__ import annotations

from .base import DataProvider, ProviderCapabilities, ProviderUnavailable
from .hikyuu_preflight import (
    HikyuuDataIntegrityError,
    PreflightReport,
    preflight,
)
from .hikyuu_provider import HikyuuProvider

__all__ = [
    "DataProvider",
    "ProviderCapabilities",
    "ProviderUnavailable",
    "HikyuuProvider",
    "HikyuuDataIntegrityError",
    "PreflightReport",
    "preflight",
]
