"""Compatibility facade; strategy discovery lives in the application layer.

Existing imports remain supported. Infrastructure implementations must not add
strategy discovery here; application callers own configuration and orchestration.
"""

from src.application.backtesting import (
    BacktestRequest as BacktestRequest,
)
from src.application.backtesting import (
    BacktestRequestError as BacktestRequestError,
)
from src.application.backtesting import (
    StrategySpec as StrategySpec,
)
from src.application.backtesting import (
    UnknownFrameworkError as UnknownFrameworkError,
)
from src.application.backtesting import (
    UnknownStrategyError as UnknownStrategyError,
)
from src.application.backtesting import (
    available_frameworks as available_frameworks,
)
from src.application.backtesting import (
    discover_strategies as discover_strategies,
)
from src.application.backtesting import (
    register_framework as register_framework,
)
from src.application.backtesting import (
    run_backtest as run_backtest,
)
