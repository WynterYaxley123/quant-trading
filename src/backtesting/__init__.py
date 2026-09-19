"""框架级回测层。

当前实现进度
------------
已完成并验证：

- :mod:`src.backtesting.result` —— 标准化结果结构
  （``BacktestResult`` / ``BacktestMetadata`` / ``BacktestMetrics``）

尚未实现：

- ``runner.py``（框架级编排：strategy discovery / config / framework 选择）
- ``hikyuu_runner.py``（Hikyuu 执行链路）

**未实现的模块不在此处导出** —— 只有真实存在且可 import 的 public API
才进入本命名空间。待实现后逐步加入。
"""

from __future__ import annotations

from .result import (
    BacktestResult,
    BacktestMetadata,
    BacktestMetrics,
    UNSUPPORTED,
    RESULT_FILES,
    now_run_id,
)

__all__ = [
    "BacktestResult",
    "BacktestMetadata",
    "BacktestMetrics",
    "UNSUPPORTED",
    "RESULT_FILES",
    "now_run_id",
]
