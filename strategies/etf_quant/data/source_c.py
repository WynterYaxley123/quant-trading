"""Source-C industry series construction -- approved method, frozen.

Identity
--------
``INTERNAL_EQUAL_WEIGHT_SHENWAN_SERIES_V1``  --  **NOT OFFICIAL SHENWAN INDEX**

This is an internally constructed equal-weight series over Shenwan membership.
A SWS-published industry index does not come out of this code and must never be
presented as one.

Approved method (frozen; do not substitute)
-------------------------------------------
Time-varying as-of membership supplies each session's constituent set::

    r_i,t        = adj_close_i,t / adj_close_i,t-1 - 1
    industry_t   = mean( r_i,t over VALID eligible constituents )
    index_t      = index_t-1 * (1 + industry_t),        index_base = 1000.0

Only **exact-adjusted** closes may enter. A row whose ``adj_is_exact`` is not true
is not an eligible constituent: its return would be a raw-price return wearing an
adjusted label, which is precisely the silent corruption the adjustment gate
exists to prevent.

Coverage gate (frozen, never lowered)
-------------------------------------
An industry-date is ``SOURCE_C_DATE_VALID`` iff::

    valid_constituents >= 5   AND   valid/eligible >= 0.80

where ``eligible`` is the session's as-of constituent count and ``valid`` is the
count of those with a usable exact-adjusted return. Note the denominator is the
**full** constituent set, not just the names that happen to have bars -- that is
what makes the ratio a coverage measure rather than a tautology.

Beijing constituents are included in ``eligible`` by the approved
``INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS`` policy. A BJ name with no bars therefore
*reduces* the ratio rather than disappearing, which is the intended behaviour: the
gap stays visible instead of silently thinning the industry.

Pure functions over pre-loaded rows. No I/O, no network, no provider import.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import TypedDict

from . import (
    MIN_CONSTITUENT_COVERAGE_RATIO,
    MIN_VALID_CONSTITUENTS,
    SOURCE_C_BASE,
    SOURCE_C_IDENTITY,
)
from .membership import MembershipRow, exchange_of, session_universe

VALID = "SOURCE_C_DATE_VALID"
INVALID = "SOURCE_C_DATE_INVALID"

#: Reasons a constituent is excluded from the mean. Each is recorded so a low
#: coverage ratio is always explainable.
REASON_NO_BAR = "NO_BAR"
REASON_PREV_MISSING = "PREVIOUS_CLOSE_MISSING"
REASON_NOT_EXACT = "ADJUSTMENT_NOT_EXACT"
REASON_NON_POSITIVE = "NON_POSITIVE_PRICE"
REASON_INVALID_VALUE = "NON_FINITE_RETURN"


class SourceCError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ConstituentReturn:
    symbol: str
    return_value: float | None
    exclusion_reason: str | None
    exchange: str


@dataclass(frozen=True)
class IndustryDate:
    """One industry on one session, with the arithmetic and the verdict."""

    session: date
    industry_code: str
    eligible: int
    valid: int
    coverage_ratio: float
    industry_return: float | None
    status: str
    reasons: Mapping[str, int]

    @property
    def valid_date(self) -> bool:
        return self.status == VALID


def _finite(value) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number == number and number not in (float("inf"), float("-inf"))


def constituent_return(*, close, prev_close, adj_is_exact) -> tuple[float | None, str | None]:
    """Exact-adjusted one-session return, or (None, reason).

    Fail-closed in every direction: a non-exact adjustment, a missing prior close,
    a non-positive price and a non-finite result all refuse to produce a number.

    Reasons are distinguished rather than collapsed, because "this industry is
    thin" and "these names have no prior session" call for different responses:
      * ``NO_BAR``             -- no close for the session at all
      * ``PREVIOUS_CLOSE_MISSING`` -- the session priced, but there is no prior close
        (a new listing, a resumed halt, or a gap in the vendor series)
    """
    if adj_is_exact is not True:
        return None, REASON_NOT_EXACT
    if close is None:
        return None, REASON_NO_BAR
    if prev_close is None:
        return None, REASON_PREV_MISSING
    if not _finite(close) or not _finite(prev_close):
        return None, REASON_INVALID_VALUE
    if float(close) <= 0 or float(prev_close) <= 0:
        return None, REASON_NON_POSITIVE
    value = float(close) / float(prev_close) - 1.0
    if not _finite(value):
        return None, REASON_INVALID_VALUE
    return value, None


class BJCoverageRow(TypedDict):
    industry_code: str
    bj_members: int
    bj_valid: int
    bj_missing: int


def industry_date(
    session: date,
    industry_code: str,
    constituents: Sequence[str],
    closes: Mapping[str, float],
    prev_closes: Mapping[str, float],
    adj_exact: Mapping[str, bool],
    width: int = 4,
) -> IndustryDate:
    """Evaluate one industry for one session under the frozen gate."""
    returns: list[float] = []
    reasons: dict[str, int] = {}
    for symbol in sorted(constituents):
        value, reason = constituent_return(
            close=closes.get(symbol),
            prev_close=prev_closes.get(symbol),
            adj_is_exact=adj_exact.get(symbol),
        )
        if reason is None:
            assert value is not None  # constituent_return pairs a valid value with no rejection.
            returns.append(value)
        else:
            reasons[reason] = reasons.get(reason, 0) + 1
    eligible = len(constituents)
    valid = len(returns)
    ratio = (valid / eligible) if eligible else 0.0
    passes = valid >= MIN_VALID_CONSTITUENTS and ratio >= MIN_CONSTITUENT_COVERAGE_RATIO
    return IndustryDate(
        session=session,
        industry_code=industry_code,
        eligible=eligible,
        valid=valid,
        coverage_ratio=ratio,
        industry_return=(sum(returns) / valid) if (valid and passes) else None,
        status=VALID if passes else INVALID,
        reasons=reasons,
    )


def build_session(
    rows: Sequence[MembershipRow],
    session: date,
    closes: Mapping[str, float],
    prev_closes: Mapping[str, float],
    adj_exact: Mapping[str, bool],
    width: int = 4,
) -> list[IndustryDate]:
    """Every industry of one session, in code order."""
    universe = session_universe(rows, session, width=width)
    industries: dict[str, list[str]] = {}
    for symbol, code in universe.members.items():
        industries.setdefault(code, []).append(symbol)
    return [
        industry_date(
            session=session,
            industry_code=code,
            constituents=symbols,
            closes=closes,
            prev_closes=prev_closes,
            adj_exact=adj_exact,
            width=width,
        )
        for code, symbols in sorted(industries.items())
    ]


def index_levels(series: Sequence[IndustryDate], *, base: float = SOURCE_C_BASE) -> list[dict]:
    """Chain valid industry returns into a level series.

    An invalid date contributes **no** return and holds the previous level; it is
    never treated as a zero return, which would silently damp the series.
    """
    if base <= 0:
        raise SourceCError("BASE_MUST_BE_POSITIVE")
    level = base
    out: list[dict] = []
    for item in series:
        if item.valid_date and item.industry_return is not None:
            level = level * (1.0 + item.industry_return)
        out.append(
            {
                "session": item.session,
                "industry_code": item.industry_code,
                "status": item.status,
                "coverage_ratio": item.coverage_ratio,
                "eligible": item.eligible,
                "valid": item.valid,
                "industry_return": item.industry_return,
                "index_level": level,
                "identity": SOURCE_C_IDENTITY,
                "disclaimer": "NOT OFFICIAL SHENWAN INDEX",
            }
        )
    return out


def bj_coverage_impact(
    rows: Sequence[MembershipRow],
    session: date,
    adj_exact: Mapping[str, bool],
    closes: Mapping[str, float],
    prev_closes: Mapping[str, float],
    width: int = 4,
) -> dict:
    """How much of each industry's coverage gap is attributable to missing BJ names.

    Because BJ is included in ``eligible``, a BJ name without bars lowers the
    ratio. This quantifies that so the cost of the approved policy stays visible
    instead of reading as an unexplained coverage shortfall.
    """
    universe = session_universe(rows, session, width=width)
    industries: dict[str, list[str]] = {}
    for symbol, code in universe.members.items():
        industries.setdefault(code, []).append(symbol)
    rows_out: list[BJCoverageRow] = []
    for code, symbols in sorted(industries.items()):
        bj = [s for s in symbols if exchange_of(s) == "BJ"]
        bj_valid = sum(
            1
            for s in bj
            if constituent_return(
                close=closes.get(s), prev_close=prev_closes.get(s), adj_is_exact=adj_exact.get(s)
            )[1]
            is None
        )
        rows_out.append(
            {
                "industry_code": code,
                "bj_members": len(bj),
                "bj_valid": bj_valid,
                "bj_missing": len(bj) - bj_valid,
            }
        )
    return {
        "session": session.isoformat(),
        "total_bj_members": sum(r["bj_members"] for r in rows_out),
        "total_bj_missing": sum(r["bj_missing"] for r in rows_out),
        "industries_affected": sum(1 for r in rows_out if r["bj_missing"] > 0),
        "per_industry": rows_out,
    }


__all__ = [
    "VALID",
    "INVALID",
    "REASON_NO_BAR",
    "REASON_PREV_MISSING",
    "REASON_NOT_EXACT",
    "REASON_NON_POSITIVE",
    "REASON_INVALID_VALUE",
    "SourceCError",
    "ConstituentReturn",
    "IndustryDate",
    "constituent_return",
    "industry_date",
    "build_session",
    "index_levels",
    "bj_coverage_impact",
]
