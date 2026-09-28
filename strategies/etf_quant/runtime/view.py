"""Explicit public DTOs for read-only observation. No source download/client."""
from dataclasses import asdict

from ..config import FACTORS_19, H10_FACTORS, FUSION_WEIGHTS
from ..domain import StrategyConfig
from ..domain.industry_level import (ETF_QUANT_INDUSTRY_LEVEL_V1, INDUSTRY_LEVEL_WIDTH,
                                     TAXONOMY_IDENTITY)
from ..factors import FACTOR_REGISTRY
from ..mapping.liquidity import LIQUIDITY_SESSIONS
from ..schemas import to_primitive
from .industry import IDENTITY, METHOD, PIT_FLAG


def public_strategy(config=None, *, lot_size=100):
    config = StrategyConfig() if config is None else config
    return {"version": "ETF_QUANT_V1", "mode": "SIMULATION_ONLY", "currency": "CNY", "initial_cash": "10000",
        "model": "Ridge", "alpha": .01, "training_window_months": 6, "minimum_training_days": 30,
        "window_anchor": "PER_HORIZON_LABEL_CUTOFF", "target": "SAME_DATE_CROSS_SECTIONAL_EXCESS_FORWARD_RETURN",
        "preprocessing": "NONE_RAW_X", "horizons": [10, 40, 120], "h10_factors": list(H10_FACTORS),
        "h40_factors": list(FACTORS_19), "h120_factors": list(FACTORS_19),
        "fusion": {str(h): w for h, w in FUSION_WEIGHTS}, "zscore_ddof": 0, "top_k": 5, "target_weight_cap": .35,
        "weighting": "CAPPED_SOFTMAX_REDISTRIBUTE_UNCAPPED_ONLY", "rebalance": "EXECUTABLE_ETF_SET_CHANGE_ONLY",
        "execution": "T_CLOSE_SIGNAL_NEXT_TRADING_SESSION_RAW_OPEN", "bookkeeping": "DELAYED_EOD_ACTUAL_PROCESSED_AT",
        "lot_size": lot_size, "costs": to_primitive(config.costs), "broker_enabled": False, "real_order_path": False,
        "source_c_identity": IDENTITY, "construction": METHOD, "pit_quality": PIT_FLAG,
        "industry_level": ETF_QUANT_INDUSTRY_LEVEL_V1, "industry_level_width": INDUSTRY_LEVEL_WIDTH,
        "taxonomy_identity": TAXONOMY_IDENTITY,
        "liquidity_rule": "TWENTY_SESSION_REQUIRED_AMOUNT_NO_SUBSTITUTION",
        "liquidity_sessions": LIQUIDITY_SESSIONS,
        "available_at": None, "source_published_at": None,
        "factor_registry": [to_primitive(s) for s in FACTOR_REGISTRY.values()]}


def empty_view(*, status="NOT_STARTED", reason="NO_SUCCESSFUL_RUNTIME_RUN", config=None):
    return {"status": {"product": "ETF_QUANT", "version": "ETF_QUANT_V1", "mode": "SIMULATION_ONLY",
        "phase": status, "reason": reason, "snapshot_id": None, "source_commit": None, "source_version": None,
        "code_commit": None, "cutoff": None, "updated_at": None, "signal_date": None, "execution_date": None,
        "epoch": None, "mapping_hash": None, "strategy_hash": None, "broker_enabled": False,
        "industry_level": ETF_QUANT_INDUSTRY_LEVEL_V1,
        "real_order_path": False, "validation_opened": False, "final_oos_read": False},
        "strategy": public_strategy(config), "models": [], "rankings": {"10d": [], "40d": [], "120d": [], "fusion": []},
        "portfolio_summary": {"status": "NOT_STARTED", "cash": None, "market_value": None, "total_equity": None,
            "initial_cash": "10000", "realized_pnl": None, "unrealized_pnl": None, "total_return": None,
            "total_pnl": None, "daily_return": None, "turnover": None,
            "turnover_definition": "CUMULATIVE_ABSOLUTE_SLIPPED_NOTIONAL_DIVIDED_BY_INITIAL_CASH",
            "max_drawdown": None, "sharpe": None, "rebalance_count": None, "last_rebalance_at": None},
        "holdings": [], "nav": [], "trades": [],
        "mappings": {"status": "MAPPING_ADMISSION_BLOCKED", "reason": "NO_VERIFIED_EVIDENCE", "entries": [],
            "diagnostics": [], "industry_level": ETF_QUANT_INDUSTRY_LEVEL_V1,
            "liquidity_sessions": LIQUIDITY_SESSIONS, "liquidity_window": []},
        "benchmark": {"symbol": "000300.SH", "status": "NOT_STARTED", "points": [],
            "nasdaq": "DEFERRED", "sp500": "DEFERRED", "model_input": False},
        "health": {"status": status, "blockers": [reason], "quality_flags": [PIT_FLAG],
            "adjustment_exact_rows": None, "adjustment_rejected_rows": None, "coverage": None,
            "strict_tls": "SIDECAR_ONLY_NO_TLS_OVERRIDE", "historical_performance": False}}
