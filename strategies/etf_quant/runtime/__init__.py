"""Foundation state/ports only. Deliberately no orchestrator, scheduler or loop."""

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from ..config import (
    INTEGRATION_DEPENDENCY_DEFERRED,
    MAPPING_CONTRACT_PENDING,
    PUBLIC_INTEGRATION_REVIEW_PENDING,
)
from ..domain import (
    BenchmarkId,
    IndustryRanking,
    MappingResult,
    Product,
    RunMode,
    TradingCalendar,
    simulation_only,
)


@dataclass(frozen=True)
class IndustryBar:
    industry_code: str
    session: date
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    amount: float | None


@dataclass(frozen=True)
class ETFInstrument:
    asset_id: str
    name: str
    listed_from: date | None = None
    exchange: str | None = None


@dataclass(frozen=True)
class BenchmarkPoint:
    benchmark: BenchmarkId
    session: date
    index_level: float
    currency: str | None = None


class IndustryDataProvider(Protocol):
    def history(
        self, industries: tuple[str, ...], start: date, end: date
    ) -> tuple[IndustryBar, ...]: ...


class ETFUniverseProvider(Protocol):
    def universe(self, as_of: date) -> tuple[ETFInstrument, ...]: ...


class TradingCalendarProvider(Protocol):
    def calendar(self, start: date, end: date) -> TradingCalendar: ...


class BenchmarkDataProvider(Protocol):
    def history(
        self, benchmark: BenchmarkId, start: date, end: date
    ) -> tuple[BenchmarkPoint, ...]: ...


class IndustryETFMapper(Protocol):
    def map_industries(
        self, rankings: tuple[IndustryRanking, ...], as_of: date
    ) -> tuple[MappingResult, ...]: ...


@dataclass(frozen=True)
class RuntimeState:
    product: Product = Product.ETF_QUANT
    mode: RunMode = RunMode.SIMULATION_ONLY
    phase: str = "FOUNDATION_ONLY"
    data_contract: str = MAPPING_CONTRACT_PENDING
    public_integration: str = PUBLIC_INTEGRATION_REVIEW_PENDING
    integration_state: str = INTEGRATION_DEPENDENCY_DEFERRED
    broker_enabled: bool = False
    real_order_path: bool = False

    def __post_init__(self):
        simulation_only(self.product, self.mode)
        if (
            self.phase != "FOUNDATION_ONLY"
            or self.data_contract != MAPPING_CONTRACT_PENDING
            or self.public_integration != PUBLIC_INTEGRATION_REVIEW_PENDING
            or self.integration_state != INTEGRATION_DEPENDENCY_DEFERRED
            or self.broker_enabled is not False
            or self.real_order_path is not False
        ):
            raise ValueError("foundation cannot enable an integration/runtime/broker path")
