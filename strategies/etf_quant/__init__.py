"""ETF_QUANT foundation: isolated pure computation, SIMULATION_ONLY.

No provider implementation, runner, broker or real-order path is exported.
"""
from .domain import StrategyConfig, StrategyRunMetadata

__all__ = ["StrategyConfig", "StrategyRunMetadata"]
