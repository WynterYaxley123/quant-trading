"""Immutable domain values. Metadata is explicit; no I/O or inferred provenance."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from enum import Enum, IntEnum
from numbers import Real

from ..config import BASELINE_COMMIT, FUSION_WEIGHTS, HORIZON_FACTORS, TARGET_IDENTITY


def finite(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite real number")
    return float(value)


def decimal_value(value, name: str, *, positive=False) -> Decimal:
    # Money must not silently inherit binary-float rounding.
    if isinstance(value, bool) or not isinstance(value, (Decimal, str, int)):
        raise ValueError(f"{name} requires Decimal, integer or decimal string")
    try:
        result = Decimal(value)
    except Exception as error:
        raise ValueError(f"invalid {name}") from error
    if not result.is_finite() or result < 0 or positive and result <= 0:
        raise ValueError(f"invalid {name}")
    return result


def identifier(value: str, name="identifier") -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"invalid {name}")


def session(value: date) -> None:
    if type(value) is not date:
        raise ValueError("sessions must be explicit date values, not timestamps")


def timestamp(value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("explicit timezone-aware timestamp required")


def decimal_math():
    """Fixed internal precision; no exchange tick/lot/cent rounding policy."""
    return localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN))


class Product(str, Enum):
    ETF_QUANT = "ETF_QUANT"


class RunMode(str, Enum):
    SIMULATION_ONLY = "SIMULATION_ONLY"


class Horizon(IntEnum):
    H10 = 10
    H40 = 40
    H120 = 120


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class SessionPhase(str, Enum):
    CLOSE = "CLOSE"
    OPEN = "OPEN"


class BenchmarkId(str, Enum):
    CSI_300 = "CSI_300"
    NASDAQ_COMPOSITE = "NASDAQ_COMPOSITE"
    SP_500 = "SP_500"


def simulation_only(product: Product, mode: RunMode) -> None:
    if product is not Product.ETF_QUANT or mode is not RunMode.SIMULATION_ONLY:
        raise ValueError("ETF_QUANT / SIMULATION_ONLY invariant")


@dataclass(frozen=True)
class FactorSpec:
    name: str
    formula: str
    lookback_sessions: int
    input_fields: tuple[str, ...] = ("close",)

    def __post_init__(self):
        identifier(self.name)
        identifier(self.formula, "formula")
        if type(self.lookback_sessions) is not int or self.lookback_sessions <= 0:
            raise ValueError("invalid factor lookback")
        if not isinstance(self.input_fields, tuple) or not self.input_fields:
            raise ValueError("immutable input field specification required")


@dataclass(frozen=True)
class HorizonModelSpec:
    horizon: Horizon
    factor_names: tuple[str, ...]
    alpha: float = 0.01
    training_window_months: int = 6
    minimum_valid_training_days: int = 30
    target_identity: str = TARGET_IDENTITY

    def __post_init__(self):
        if not isinstance(self.horizon, Horizon):
            raise ValueError("explicit Horizon required")
        expected = dict(HORIZON_FACTORS)[int(self.horizon)]
        if self.factor_names != expected or not isinstance(self.factor_names, tuple):
            raise ValueError("frozen factor names/order mismatch")
        if (
            finite(self.alpha, "alpha") != 0.01
            or type(self.training_window_months) is not int
            or self.training_window_months != 6
            or type(self.minimum_valid_training_days) is not int
            or self.minimum_valid_training_days != 30
            or self.target_identity != TARGET_IDENTITY
        ):
            raise ValueError("frozen Ridge baseline mismatch")


@dataclass(frozen=True)
class TransactionCost:
    commission_bps: Decimal = Decimal("3")
    slippage_bps: Decimal = Decimal("5")
    stamp_duty_bps: Decimal = Decimal("0")
    minimum_commission: Decimal = Decimal("0")

    def __post_init__(self):
        for name in ("commission_bps", "slippage_bps", "stamp_duty_bps", "minimum_commission"):
            value = decimal_value(getattr(self, name), name)
            if name.endswith("_bps") and value >= 10000:
                raise ValueError("basis points must be below 10000")
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class StrategyConfig:
    product: Product = Product.ETF_QUANT
    mode: RunMode = RunMode.SIMULATION_ONLY
    model_name: str = "Ridge"
    horizons: tuple[HorizonModelSpec, ...] = field(
        default_factory=lambda: tuple(
            HorizonModelSpec(Horizon(h), names) for h, names in HORIZON_FACTORS
        )
    )
    fusion_weights: tuple[tuple[int, float], ...] = FUSION_WEIGHTS
    top_k: int = 5
    initial_cash: Decimal = Decimal("10000")
    currency: str = "CNY"
    max_target_weight: float = 0.35
    costs: TransactionCost = field(default_factory=TransactionCost)

    def __post_init__(self):
        simulation_only(self.product, self.mode)
        if (
            self.model_name != "Ridge"
            or type(self.horizons) is not tuple
            or not all(isinstance(s, HorizonModelSpec) for s in self.horizons)
            or tuple(s.horizon for s in self.horizons) != tuple(Horizon)
            or self.fusion_weights != FUSION_WEIGHTS
            or type(self.fusion_weights) is not tuple
            or type(self.top_k) is not int
            or self.top_k != 5
            or finite(self.max_target_weight, "cap") != 0.35
            or self.currency != "CNY"
            or not isinstance(self.costs, TransactionCost)
        ):
            raise ValueError("frozen ETF_QUANT V1 baseline mismatch")
        cash = decimal_value(self.initial_cash, "initial_cash", positive=True)
        if cash != 10000:
            raise ValueError("V1 initial capital is CNY 10000")
        object.__setattr__(self, "initial_cash", cash)


@dataclass(frozen=True)
class ModelPrediction:
    horizon: Horizon
    signal_date: date
    industry_code: str
    prediction: float

    def __post_init__(self):
        if not isinstance(self.horizon, Horizon):
            raise ValueError("explicit Horizon required")
        session(self.signal_date)
        identifier(self.industry_code)
        finite(self.prediction, "prediction")


@dataclass(frozen=True)
class IndustryRanking:
    rank: int
    industry_code: str
    score: float

    def __post_init__(self):
        if type(self.rank) is not int or self.rank <= 0:
            raise ValueError("invalid rank")
        identifier(self.industry_code)
        finite(self.score, "score")


@dataclass(frozen=True)
class FusedRanking:
    signal_date: date
    rankings: tuple[IndustryRanking, ...]
    horizon_zscores: tuple[tuple[Horizon, tuple[ModelPrediction, ...]], ...]

    def __post_init__(self):
        session(self.signal_date)
        if (
            not isinstance(self.rankings, tuple)
            or len(self.rankings) < 5
            or not all(isinstance(r, IndustryRanking) for r in self.rankings)
            or len({r.industry_code for r in self.rankings}) != len(self.rankings)
            or tuple(r.rank for r in self.rankings) != tuple(range(1, len(self.rankings) + 1))
            or self.rankings
            != tuple(sorted(self.rankings, key=lambda r: (-r.score, r.industry_code)))
            or not isinstance(self.horizon_zscores, tuple)
            or tuple(h for h, _ in self.horizon_zscores) != tuple(Horizon)
        ):
            raise ValueError("invalid immutable fused ranking schema")
        universe = {r.industry_code for r in self.rankings}
        for horizon, rows in self.horizon_zscores:
            if (
                not isinstance(horizon, Horizon)
                or not isinstance(rows, tuple)
                or len(rows) != len(universe)
                or any(
                    not isinstance(p, ModelPrediction)
                    or p.horizon is not horizon
                    or p.signal_date != self.signal_date
                    for p in rows
                )
                or {p.industry_code for p in rows} != universe
            ):
                raise ValueError("fused result horizon/date/universe mismatch")

    @property
    def top5(self) -> tuple[IndustryRanking, ...]:
        return self.rankings[:5]


class MappingAdmission(str, Enum):
    PENDING_CONTRACT = "PENDING_DEEPSEEK_CONTRACT"
    INCOMPLETE = "INCOMPLETE_METADATA"
    REJECTED = "REJECTED"
    ADMITTED = "ADMITTED"  # Reserved, NOT usable by foundation V1.


@dataclass(frozen=True)
class ETFMapping:
    industry_code: str
    industry_name: str | None = None
    etf_code: str | None = None
    etf_name: str | None = None
    mapping_method: str | None = None
    tracking_index_code: str | None = None
    tracking_index_name: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    verified_at: datetime | None = None
    available_at: datetime | None = None
    mapping_confidence: float | None = None
    admission_status: MappingAdmission = MappingAdmission.PENDING_CONTRACT

    def __post_init__(self):
        identifier(self.industry_code)
        if not isinstance(self.admission_status, MappingAdmission):
            raise ValueError("invalid mapping state")
        if self.admission_status is MappingAdmission.ADMITTED:
            raise ValueError("PENDING_DEEPSEEK_CONTRACT: no production mapping admission in V1")
        for name in (
            "industry_name",
            "etf_code",
            "etf_name",
            "mapping_method",
            "tracking_index_code",
            "tracking_index_name",
        ):
            value = getattr(self, name)
            if value is not None:
                identifier(value, name)
        for value in (self.effective_from, self.effective_to):
            if value is not None:
                session(value)
        if self.effective_to is not None and (
            self.effective_from is None or self.effective_to <= self.effective_from
        ):
            raise ValueError("mapping interval must be known and nonempty")
        for value in (self.verified_at, self.available_at):
            if value is not None:
                timestamp(value)
        if (
            self.mapping_confidence is not None
            and not 0 <= finite(self.mapping_confidence, "confidence") <= 1
        ):
            raise ValueError("mapping confidence outside [0,1]")


@dataclass(frozen=True)
class MappingResult:
    industry_code: str
    status: MappingAdmission
    candidates: tuple[ETFMapping, ...] = ()
    reasons: tuple[str, ...] = ()

    def __post_init__(self):
        identifier(self.industry_code)
        if (
            not isinstance(self.status, MappingAdmission)
            or self.status is MappingAdmission.ADMITTED
            or not isinstance(self.candidates, tuple)
            or not isinstance(self.reasons, tuple)
            or any(
                not isinstance(m, ETFMapping) or m.industry_code != self.industry_code
                for m in self.candidates
            )
        ):
            raise ValueError("provisional mapping result required; production admission deferred")


@dataclass(frozen=True)
class TargetPosition:
    asset_id: str
    target_weight: float

    def __post_init__(self):
        identifier(self.asset_id)
        if not 0 <= finite(self.target_weight, "target weight") <= 1:
            raise ValueError("invalid weight")


@dataclass(frozen=True)
class Position:
    asset_id: str
    quantity: Decimal
    average_cost: Decimal
    mark_price: Decimal

    def __post_init__(self):
        identifier(self.asset_id)
        for name in ("quantity", "average_cost", "mark_price"):
            object.__setattr__(self, name, decimal_value(getattr(self, name), name, positive=True))

    @property
    def market_value(self) -> Decimal:
        with decimal_math():
            return self.quantity * self.mark_price

    @property
    def unrealized_pnl(self) -> Decimal:
        with decimal_math():
            return self.market_value - self.quantity * self.average_cost


@dataclass(frozen=True)
class PortfolioState:
    as_of: datetime
    cash: Decimal = Decimal("10000")
    positions: tuple[Position, ...] = ()
    realized_pnl: Decimal = Decimal("0")
    initial_cash: Decimal = Decimal("10000")
    applied_fill_ids: tuple[str, ...] = ()
    executed_intent_ids: tuple[str, ...] = ()
    product: Product = Product.ETF_QUANT
    mode: RunMode = RunMode.SIMULATION_ONLY

    def __post_init__(self):
        simulation_only(self.product, self.mode)
        timestamp(self.as_of)
        object.__setattr__(self, "cash", decimal_value(self.cash, "cash"))
        object.__setattr__(
            self, "initial_cash", decimal_value(self.initial_cash, "initial_cash", positive=True)
        )
        if not isinstance(self.realized_pnl, Decimal) or not self.realized_pnl.is_finite():
            raise ValueError("finite Decimal realized PnL required")
        if (
            not isinstance(self.positions, tuple)
            or not all(isinstance(p, Position) for p in self.positions)
            or len({p.asset_id for p in self.positions}) != len(self.positions)
            or not isinstance(self.applied_fill_ids, tuple)
            or len(set(self.applied_fill_ids)) != len(self.applied_fill_ids)
            or not isinstance(self.executed_intent_ids, tuple)
            or len(set(self.executed_intent_ids)) != len(self.executed_intent_ids)
        ):
            raise ValueError("duplicate/mutable portfolio entries")

    @property
    def market_value(self) -> Decimal:
        with decimal_math():
            return sum((p.market_value for p in self.positions), Decimal(0))

    @property
    def total_equity(self) -> Decimal:
        with decimal_math():
            return self.cash + self.market_value

    @property
    def unrealized_pnl(self) -> Decimal:
        with decimal_math():
            return sum((p.unrealized_pnl for p in self.positions), Decimal(0))


@dataclass(frozen=True)
class TradingCalendar:
    sessions: tuple[date, ...]

    def __post_init__(self):
        if not isinstance(self.sessions, tuple) or not self.sessions:
            raise ValueError("explicit calendar required")
        for day in self.sessions:
            session(day)
        if tuple(sorted(set(self.sessions))) != self.sessions:
            raise ValueError("calendar must be sorted/unique")


@dataclass(frozen=True)
class SimulatedOrderIntent:
    intent_id: str
    asset_id: str
    side: Side
    quantity: Decimal
    signal_session: date
    execution_session: date
    signal_phase: SessionPhase = SessionPhase.CLOSE
    execution_phase: SessionPhase = SessionPhase.OPEN
    mode: RunMode = RunMode.SIMULATION_ONLY

    def __post_init__(self):
        identifier(self.intent_id)
        identifier(self.asset_id)
        session(self.signal_session)
        session(self.execution_session)
        if (
            not isinstance(self.side, Side)
            or self.mode is not RunMode.SIMULATION_ONLY
            or self.signal_phase is not SessionPhase.CLOSE
            or self.execution_phase is not SessionPhase.OPEN
            or self.execution_session <= self.signal_session
        ):
            raise ValueError("simulation T-close / later-open intent required")
        object.__setattr__(
            self, "quantity", decimal_value(self.quantity, "quantity", positive=True)
        )


@dataclass(frozen=True)
class SimulatedFill:
    fill_id: str
    intent: SimulatedOrderIntent
    executed_at: datetime
    reference_open: Decimal
    price: Decimal
    commission: Decimal
    slippage: Decimal
    stamp_duty: Decimal

    def __post_init__(self):
        identifier(self.fill_id)
        timestamp(self.executed_at)
        if (
            not isinstance(self.intent, SimulatedOrderIntent)
            or self.executed_at.date() != self.intent.execution_session
        ):
            raise ValueError("fill session/intent mismatch")
        for name in ("reference_open", "price", "commission", "slippage", "stamp_duty"):
            object.__setattr__(
                self,
                name,
                decimal_value(
                    getattr(self, name), name, positive=name in {"reference_open", "price"}
                ),
            )


@dataclass(frozen=True)
class NAVPoint:
    timestamp: datetime
    cash: Decimal
    market_value: Decimal
    total_equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    normalized_nav: Decimal

    def __post_init__(self):
        timestamp(self.timestamp)
        for name in ("cash", "market_value", "total_equity", "normalized_nav"):
            object.__setattr__(self, name, decimal_value(getattr(self, name), name))
        for name in ("realized_pnl", "unrealized_pnl"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValueError("finite Decimal PnL required")
        with decimal_math():
            if self.total_equity != self.cash + self.market_value:
                raise ValueError("NAV cash/market-value identity mismatch")


@dataclass(frozen=True)
class StrategyRunMetadata:
    run_id: str
    created_at: datetime
    product: Product = Product.ETF_QUANT
    mode: RunMode = RunMode.SIMULATION_ONLY
    baseline_commit: str = BASELINE_COMMIT
    implementation_commit: str | None = None
    data_snapshot: str | None = None
    provider_identity: str | None = None
    broker_enabled: bool = False
    real_order_path: bool = False

    def __post_init__(self):
        identifier(self.run_id)
        timestamp(self.created_at)
        simulation_only(self.product, self.mode)
        if self.broker_enabled is not False or self.real_order_path is not False:
            raise ValueError("NO_BROKER / NO_REAL_ORDER_PATH")
        if self.baseline_commit != BASELINE_COMMIT:
            raise ValueError("baseline identity mismatch")
        if self.implementation_commit is not None and (
            not isinstance(self.implementation_commit, str)
            or len(self.implementation_commit) != 40
            or any(c not in "0123456789abcdef" for c in self.implementation_commit)
        ):
            raise ValueError("explicit implementation commit must be a full Git SHA")
        for name in ("data_snapshot", "provider_identity"):
            value = getattr(self, name)
            if value is not None:
                identifier(value, name)
