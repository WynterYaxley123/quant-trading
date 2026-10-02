"""框架级回测层。

已完成并验证：

- :mod:`src.backtesting.result` —— 标准化结果结构
  （``BacktestResult`` / ``BacktestMetadata`` / ``BacktestMetrics``）
- :mod:`src.backtesting.runner` —— 框架级编排
  （strategy discovery / config / framework 选择 / 统一错误边界）
- :mod:`src.backtesting.hikyuu_runner` —— Hikyuu 执行链路
- :mod:`src.backtesting.testing` —— LEVEL A 执行冒烟测试组件（非正式策略）

Hikyuu 相关 import 只出现在 ``hikyuu_runner`` / ``testing`` 与
策略包的 ``adapters/hikyuu/`` 中，不污染 factors/model/risk。

**导入本包不要求 hikyuu 已安装**：只有真正调用 hikyuu runner 时才需要。
`hikyuu_runner` 的导入被显式保护，失败时把原因记录到
``HIKYUU_RUNNER_IMPORT_ERROR``（非静默：调用 ``run_backtest`` 且 framework
为 hikyuu 时会明确报错，而不是神秘失败）。
"""

from __future__ import annotations

from .result import (
    RESULT_FILES,
    UNSUPPORTED,
    BacktestMetadata,
    BacktestMetrics,
    BacktestResult,
    now_run_id,
)
from .runner import (
    BacktestRequest,
    BacktestRequestError,
    StrategySpec,
    UnknownFrameworkError,
    UnknownStrategyError,
    available_frameworks,
    discover_strategies,
    register_framework,
    run_backtest,
)

#: hikyuu runner 导入失败时的原因（None 表示导入成功）
HIKYUU_RUNNER_IMPORT_ERROR: str | None = None

try:  # pragma: no cover - 环境相关
    from . import hikyuu_runner  # noqa: F401  触发框架注册
except ImportError as _e:  # hikyuu 未安装（离线开发环境）
    HIKYUU_RUNNER_IMPORT_ERROR = f"{type(_e).__name__}: {_e}"

__all__ = [
    # result
    "BacktestResult",
    "BacktestMetadata",
    "BacktestMetrics",
    "UNSUPPORTED",
    "RESULT_FILES",
    "now_run_id",
    # runner
    "BacktestRequest",
    "BacktestRequestError",
    "StrategySpec",
    "UnknownFrameworkError",
    "UnknownStrategyError",
    "available_frameworks",
    "discover_strategies",
    "register_framework",
    "run_backtest",
    # 环境
    "HIKYUU_RUNNER_IMPORT_ERROR",
]
