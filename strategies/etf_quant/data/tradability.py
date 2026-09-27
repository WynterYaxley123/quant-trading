"""ETF_BAR_DERIVED_TRADABILITY_V1 -- approved ex-post tradability evidence.

Background. The pinned upstream provider has **no native ETF trading status**:
ETFs are excluded from its EastMoney suspended and ST boards, and its baostock ST
backfill rejects them ("cannot resolve '510300.SH' to exactly one all-A
instrument"). The previously recorded `TRADING_STATUS_EMPTY` blocker is therefore
not fixable by widening a query. The user approved a bar-derived contract instead.

What this is
------------
**Ex-post evidence** that an ETF actually traded on the T+1 session, inferred from
a finalized daily bar. It answers "did this instrument trade?" for a session that
has already closed.

What this is NOT
----------------
It is **not** a real-time exchange trading-status proof. It cannot see:
  * a price-limit queue that produced a bar but no fill for our order;
  * an intraday halt (临时停牌) at daily granularity;
  * a suspension announced after the close or before the open on T+1.

Any artifact that carries this evidence must also carry
``TRADABILITY_EVIDENCE_QUALIFIER``.

The rule (frozen)
-----------------
An ETF is tradable on T+1 iff **all** of:
  1. the instrument is admitted/active;
  2. a **finalized** T+1 bar exists for it;
  3. T+1 open   > 0;
  4. T+1 volume > 0;
  5. T+1 amount > 0.

Any missing clause -> ``T1_TRADABILITY_EVIDENCE_BLOCKED``.

Forbidden substitutions (each is a silent falsification of the session):
  * T+1 close instead of open;
  * T+2 open;
  * previous close;
  * synthetic or interpolated open.

``volume > 0`` is load-bearing, not decorative: a suspension is represented as a
carried-forward row with ``volume = 0`` and ``amount = 0``, so without clause 4 a
suspended ETF would present as tradable.

Pure functions, no I/O.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

TRADABILITY_CONTRACT = "ETF_BAR_DERIVED_TRADABILITY_V1"
TRADABILITY_QUALIFIER = "BAR_DERIVED_EX_POST_TRADABILITY_EVIDENCE_NOT_REALTIME_EXCHANGE_STATUS"

PASS = "T1_TRADABILITY_EVIDENCE_PASS"
BLOCKED = "T1_TRADABILITY_EVIDENCE_BLOCKED"

#: A daily bar for session T may only be treated as final at/after 15:05 Shanghai.
SHANGHAI = timezone(timedelta(hours=8))
SESSION_FINAL_AT = time(15, 5)


class TradabilityError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class TradabilityVerdict:
    """The verdict plus the exact reason, so a block is never unexplained."""

    status: str
    reason: str
    execution_date: date | None
    etf_code: str | None
    qualifier: str = TRADABILITY_QUALIFIER
    contract: str = TRADABILITY_CONTRACT

    @property
    def tradable(self) -> bool:
        return self.status == PASS


def _positive(value) -> bool:
    """Strictly positive finite number. None, NaN and 0 are all failures."""
    if value is None or isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number == number and number not in (float("inf"), float("-inf")) and number > 0


def is_finalized(bar: Mapping, *, fetched_at) -> bool:
    """A same-session bar is final only at/after 15:05 Asia/Shanghai.

    Mirrors the frozen ingest gate: a bar observed before the close may still be
    forming, so it cannot be evidence about a completed session.
    """
    trade_date = bar.get("trade_date")
    if trade_date is None or fetched_at is None:
        return False
    if isinstance(fetched_at, str):
        fetched_at = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    if not isinstance(fetched_at, datetime) or fetched_at.tzinfo is None:
        raise TradabilityError("OBSERVED_TIME_MUST_BE_TIMEZONE_AWARE")
    local = fetched_at.astimezone(SHANGHAI)
    if isinstance(trade_date, str):
        trade_date = date.fromisoformat(trade_date)
    if local.date() < trade_date:
        return False
    if local.date() == trade_date and local.time() < SESSION_FINAL_AT:
        return False
    return True


def evaluate(*, etf_code: str, admitted: bool, signal_date: date,
             execution_date: date | None, bar: Mapping | None) -> TradabilityVerdict:
    """Decide tradability for the T+1 session of a T-close signal.

    ``bar`` must be the T+1 bar itself. A bar for any other date is refused rather
    than reinterpreted -- that refusal is what makes the forbidden substitutions
    structurally impossible instead of merely discouraged.
    """
    def blocked(reason, when=None):
        return TradabilityVerdict(BLOCKED, reason, when, etf_code)

    if execution_date is None:
        return blocked("NO_EXECUTION_SESSION")
    if execution_date <= signal_date:
        # T-close signal -> T+1 open execution. Same-day execution is a lookahead.
        return blocked("EXECUTION_DATE_NOT_AFTER_SIGNAL_DATE", execution_date)
    if not admitted:
        return blocked("INSTRUMENT_NOT_ADMITTED", execution_date)
    if bar is None:
        return blocked("T1_BAR_MISSING", execution_date)

    bar_date = bar.get("trade_date")
    if isinstance(bar_date, str):
        bar_date = date.fromisoformat(bar_date)
    if bar_date != execution_date:
        # Covers T+1 close relabelled, T+2 open, previous close, and any other
        # substitution, in one structural check.
        return blocked("T1_BAR_DATE_MISMATCH", execution_date)
    if bar.get("symbol") not in (None, etf_code):
        return blocked("T1_BAR_SYMBOL_MISMATCH", execution_date)
    if not is_finalized(bar, fetched_at=bar.get("fetched_at")):
        return blocked("T1_BAR_NOT_FINALIZED", execution_date)

    if not _positive(bar.get("open")):
        return blocked("T1_OPEN_NOT_POSITIVE", execution_date)
    if not _positive(bar.get("volume")):
        return blocked("T1_VOLUME_NOT_POSITIVE", execution_date)
    if not _positive(bar.get("amount")):
        # Sina-sourced ETF rows carry a null amount by contract, so this clause is
        # a real fail-closed path, not a formality.
        return blocked("T1_AMOUNT_NOT_POSITIVE", execution_date)
    return TradabilityVerdict(PASS, "ALL_FIVE_CLAUSES_SATISFIED", execution_date, etf_code)


def next_session(sessions, signal_date: date) -> date | None:
    """The first session strictly after *signal_date*, or None if unknown."""
    later = [s for s in sessions if s > signal_date]
    return later[0] if later else None


def evaluate_for_sessions(*, etf_code: str, admitted: bool, signal_date: date,
                          sessions, bars_by_date: Mapping) -> TradabilityVerdict:
    """Convenience wrapper: resolve T+1 from a real session list, then evaluate."""
    execution = next_session(sessions, signal_date)
    if execution is None:
        return TradabilityVerdict(BLOCKED, "NO_NEXT_SESSION_IN_CALENDAR", None, etf_code)
    return evaluate(etf_code=etf_code, admitted=admitted, signal_date=signal_date,
                    execution_date=execution, bar=bars_by_date.get(execution))


__all__ = [
    "TRADABILITY_CONTRACT",
    "TRADABILITY_QUALIFIER",
    "PASS",
    "BLOCKED",
    "SESSION_FINAL_AT",
    "TradabilityError",
    "TradabilityVerdict",
    "is_finalized",
    "evaluate",
    "next_session",
    "evaluate_for_sessions",
]
