"""Approved ETF-Quant data contracts.

These four contracts were approved by the user and frozen before this module
existed; this package only makes them executable and testable. Nothing here
changes strategy semantics, execution semantics or portfolio semantics.

Contracts:
  * ``TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE``  -- the industry universe for a date
    is the Shenwan classification in force on that date, resolved by a backward
    as-of join on the membership snapshot grid. It is never a fixed code list and
    never the historical union.
  * ``INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS``    -- Beijing names are legitimate
    industry-series constituents and must not be silently dropped.
  * ``ETF_BAR_DERIVED_TRADABILITY_V1``         -- ex-post tradability evidence
    derived from a finalized T+1 bar, because the pinned upstream provider has no
    native ETF trading status. This is evidence, **not** a real-time exchange
    status proof.
  * ``PRODUCTION_FETCH_BUDGET_APPROVED``       -- recorded here so a build can
    cite the budget it ran under; the number itself lives in the audit docs.

Deliberately absent: any rank, any Top-5 selection, any ETF target, any
portfolio sizing. Those are downstream stages with their own gates.
"""

PRODUCTION_DATA_CONTRACTS_V1 = {
    "industry_universe": "TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE",
    "bj_constituent_policy": "INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS",
    "etf_tradability": "ETF_BAR_DERIVED_TRADABILITY_V1",
    "fetch_budget": "PRODUCTION_FETCH_BUDGET_APPROVED",
}

#: The tradeability contract is evidence, not proof. Any consumer that reports it
#: must carry this qualifier.
TRADABILITY_EVIDENCE_QUALIFIER = (
    "BAR_DERIVED_EX_POST_TRADABILITY_EVIDENCE_NOT_REALTIME_EXCHANGE_STATUS"
)

#: Source-C series identity. Never to be presented as an official Shenwan index.
SOURCE_C_IDENTITY = "INTERNAL_EQUAL_WEIGHT_SHENWAN_SERIES_V1"
SOURCE_C_NOT_OFFICIAL = "NOT OFFICIAL SHENWAN INDEX"
SOURCE_C_BASE = 1000.0

#: Frozen coverage gates. These are read, never lowered.
MIN_VALID_CONSTITUENTS = 5
MIN_CONSTITUENT_COVERAGE_RATIO = 0.80

__all__ = [
    "PRODUCTION_DATA_CONTRACTS_V1",
    "TRADABILITY_EVIDENCE_QUALIFIER",
    "SOURCE_C_IDENTITY",
    "SOURCE_C_NOT_OFFICIAL",
    "SOURCE_C_BASE",
    "MIN_VALID_CONSTITUENTS",
    "MIN_CONSTITUENT_COVERAGE_RATIO",
]
