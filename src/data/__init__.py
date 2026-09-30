"""项目级公共数据层。

本包只负责**数据**：获取、规范化、交易日历、缓存入口、完整性校验。
不负责：信号生成（属策略）、回测执行（属 Hikyuu / src.backtesting）。

设计原则
--------
1. 单一 canonical schema：所有 provider 的输出必须归一化为
   :data:`CANONICAL_COLUMNS` 定义的列，策略与回测只认这一套。
2. 数据与时点：不静默填充未来信息。缺失即缺失，由调用方显式决定策略。
3. provider 隔离：单一数据源故障不得判定为整个数据层失败。
   每个 provider 显式声明 ``is_available()`` 与 ``capabilities``。
4. 不重复下载：同一份行情在项目内只有一份落盘缓存（``data/`` 目录，
   已被 .gitignore 排除），所有策略共享。
"""

from __future__ import annotations

from .schema import (
    CANONICAL_COLUMNS,
    REQUIRED_COLUMNS,
    OPTIONAL_COLUMNS,
    DataIntegrityError,
    validate_frame,
    normalize_frame,
)

__all__ = [
    "CANONICAL_COLUMNS",
    "REQUIRED_COLUMNS",
    "OPTIONAL_COLUMNS",
    "DataIntegrityError",
    "validate_frame",
    "normalize_frame",
]
