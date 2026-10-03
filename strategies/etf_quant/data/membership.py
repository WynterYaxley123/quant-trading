"""TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE -- approved industry universe policy.

The rule, in one sentence: **the industry universe for session T is the Shenwan
classification in force on T**, resolved by taking, per symbol, the latest
membership snapshot whose ``as_of_date`` is at or before T.

Why this is the approved policy: a fixed code list and the historical union are
both wrong for a backtest. A fixed list applies a classification that did not
exist yet; the union applies industry codes that were already retired. Only the
as-of rule describes each date with the taxonomy that actually existed then.

Measured regime facts this module must respect (from
`active_industry_universe_audit_v1.md`, not hard-coded here):
  * 2020-01-23 .. 2021-06-30  -> 118 active Level-2 codes
  * 2021-07-30 .. 2026-09-24  -> 162 active Level-2 codes
  * historical union          -> 181 codes
The counts are *derived* from the data by :func:`taxonomy_counts`. Nothing in
this module asserts a number.

Pure functions over pre-loaded rows: no I/O, no provider import, no I/O-side
effects. The caller supplies membership rows and a session list.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

UNIVERSE_POLICY = "TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE"

#: Classification axes. `sw` is the Shenwan series; anything else is a different
#: taxonomy and must not be pooled with it.
CLASSIFICATION_SYSTEM = "sw"
CLASSIFICATION_SOURCE = "sw"

BJ_EXCHANGE = "BJ"
SH_EXCHANGE = "SH"
SZ_EXCHANGE = "SZ"


class MembershipError(ValueError):
    """Raised when membership rows cannot satisfy the as-of contract."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class MembershipRow:
    """One (symbol, industry, snapshot) fact, already filtered to Shenwan."""

    symbol: str
    industry_code: str
    as_of_date: date


@dataclass(frozen=True)
class SessionUniverse:
    """The resolved universe for one session."""

    session: date
    snapshot_date: date
    members: Mapping[str, str]  # symbol -> industry_code (level as stored)
    taxonomy_active_count: int  # distinct industries, as-of
    by_exchange: Mapping[str, int]  # SH/SZ/BJ -> member count

    def members_for(self, industry_code: str) -> tuple[str, ...]:
        return tuple(sorted(s for s, c in self.members.items() if c == industry_code))


def exchange_of(symbol: str) -> str:
    """`600519.SH` -> `SH`. Raises rather than guessing on a malformed symbol."""
    if len(symbol) < 3 or symbol[-3] != ".":
        raise MembershipError("MALFORMED_SYMBOL")
    suffix = symbol[-2:].upper()
    if suffix not in (BJ_EXCHANGE, SH_EXCHANGE, SZ_EXCHANGE):
        raise MembershipError("UNKNOWN_EXCHANGE:" + suffix)
    return suffix


def shenwan_rows(rows: Iterable[Mapping]) -> list[MembershipRow]:
    """Keep only the Shenwan axis, and require the axis to be explicit.

    Both the source label and the classification system must say `sw`; a row that
    merely happens to carry a Shenwan-shaped code under a different system is not
    Shenwan membership.
    """
    kept: list[MembershipRow] = []
    for row in rows:
        if row.get("source") != CLASSIFICATION_SOURCE:
            continue
        if row.get("classification_system") != CLASSIFICATION_SYSTEM:
            continue
        symbol = row.get("symbol")
        code = row.get("industry_code")
        snapshot = row.get("as_of_date")
        if not symbol or not code or snapshot is None:
            continue
        if len(str(code)) != 6:
            # A Shenwan code is 6-digit prefix-hierarchical; anything shorter is a
            # different taxonomy (EastMoney's 3/4-digit board codes).
            continue
        kept.append(MembershipRow(str(symbol), str(code), snapshot))
    if not kept:
        raise MembershipError("SHENWAN_MEMBERSHIP_UNAVAILABLE")
    return kept


def level_of(code: str, width: int) -> str:
    """Shenwan codes are prefix-hierarchical: `240301` -> L2 `2403` at width 4."""
    if width not in (2, 4, 6):
        raise MembershipError("UNSUPPORTED_LEVEL_WIDTH")
    return code[:width]


def session_universe(
    rows: Sequence[MembershipRow], session: date, *, width: int = 4
) -> SessionUniverse:
    """Resolve the universe in force on *session*.

    A backward as-of join: keep rows whose snapshot is at or before the session,
    then take the latest snapshot per symbol. A symbol that only appears in a
    later snapshot was not a member yet and must be excluded -- that exclusion is
    the entire point of the policy.
    """
    eligible = [r for r in rows if r.as_of_date <= session]
    if not eligible:
        raise MembershipError("NO_MEMBERSHIP_AT_OR_BEFORE_SESSION")
    latest = max(r.as_of_date for r in eligible)
    members: dict[str, str] = {}
    for row in eligible:
        if row.as_of_date == latest:
            members[row.symbol] = level_of(row.industry_code, width)
    if not members:
        raise MembershipError("EMPTY_UNIVERSE_AT_SESSION")
    counts: dict[str, int] = {SH_EXCHANGE: 0, SZ_EXCHANGE: 0, BJ_EXCHANGE: 0}
    for symbol in members:
        counts[exchange_of(symbol)] += 1
    return SessionUniverse(
        session=session,
        snapshot_date=latest,
        members=members,
        taxonomy_active_count=len(set(members.values())),
        by_exchange=counts,
    )


def required_symbols(
    rows: Sequence[MembershipRow], sessions: Sequence[date], *, width: int = 4
) -> tuple[str, ...]:
    """Union of members across every warm-up session -- the fetch requirement.

    Beijing members are included by construction. ``INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS``
    forbids filtering them here, so no exchange filter exists in this function.
    """
    symbols: set[str] = set()
    for session in sessions:
        symbols.update(session_universe(rows, session, width=width).members)
    return tuple(sorted(symbols))


def historical_only_symbols(
    rows: Sequence[MembershipRow], sessions: Sequence[date], *, width: int = 4
) -> tuple[str, ...]:
    """Members needed during warm-up that are NOT members in the final session.

    These are the names a naive "current membership" build would silently drop.
    """
    if not sessions:
        raise MembershipError("NO_SESSIONS")
    final = set(session_universe(rows, sessions[-1], width=width).members)
    return tuple(sorted(set(required_symbols(rows, sessions, width=width)) - final))


#: Measured taxonomy-active Level-2 counts, used ONLY to label which measured
#: regime a session falls into. These are reference constants for labelling, not
#: thresholds the universe logic branches on: the universe itself is always
#: resolved by the as-of rule, never by comparing a count to these numbers.
MEASURED_TAXONOMY_REGIMES = {
    "SWCLASS2021_PRE_BREAK_118": 118,
    "SWCLASS2021_POST_BREAK_162": 162,
}


def taxonomy_counts(
    rows: Sequence[MembershipRow], sessions: Sequence[date], *, width: int = 4
) -> dict[str, object]:
    """Derived taxonomy counts. Never hard-code these in a report.

    Returns the distinct taxonomy-active counts observed across the sessions, the
    historical union over the whole membership table, and the union over the
    supplied sessions -- three different numbers that must stay separate.

    ``observed_active_counts`` is the authoritative output. ``regime_labels`` only
    attaches a human-readable name to a measured count; it never selects a
    universe.
    """
    per_session = {}
    for session in sessions:
        per_session[session] = session_universe(rows, session, width=width).taxonomy_active_count
    distinct = sorted(set(per_session.values()))
    labels: dict[int, str] = {}
    for count in distinct:
        for name, measured in MEASURED_TAXONOMY_REGIMES.items():
            if count == measured:
                labels[count] = name
                break
        else:
            labels[count] = "UNLABELLED_MEASURED_COUNT"
    return {
        "policy": UNIVERSE_POLICY,
        "sessions": len(sessions),
        "observed_active_counts": distinct,
        "regime_labels": labels,
        "taxonomy_active_last": per_session[sessions[-1]] if sessions else None,
        "union_over_sessions": len({level_of(r.industry_code, width) for r in rows}),
        "sessions_by_observed_count": {
            str(k): v for k, v in sorted(_histogram(per_session).items())
        },
    }


def _histogram(per_session: Mapping[date, int]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for value in per_session.values():
        counts[value] = counts.get(value, 0) + 1
    return counts


def bj_constituent_accounting(
    rows: Sequence[MembershipRow], session: date, *, width: int = 4
) -> dict[str, object]:
    """Per-industry Beijing share, so an exclusion can never be silent.

    ``INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS`` means an industry's BJ members are
    part of its constituent set. This reports how much that matters, which is the
    quantity a future exclusion decision would have to justify.
    """
    universe = session_universe(rows, session, width=width)
    per_industry: dict[str, dict[str, int]] = {}
    for symbol, code in universe.members.items():
        bucket = per_industry.setdefault(code, {"total": 0, "bj": 0})
        bucket["total"] += 1
        if exchange_of(symbol) == BJ_EXCHANGE:
            bucket["bj"] += 1
    shares = {
        code: {
            "total": v["total"],
            "bj": v["bj"],
            "bj_share": (v["bj"] / v["total"]) if v["total"] else 0.0,
        }
        for code, v in per_industry.items()
    }
    worst = sorted(shares.items(), key=lambda kv: (-kv[1]["bj_share"], kv[0]))
    return {
        "session": session.isoformat(),
        "bj_members": universe.by_exchange[BJ_EXCHANGE],
        "total_members": len(universe.members),
        "industries_total": len(per_industry),
        "industries_with_bj": sum(1 for v in shares.values() if v["bj"] > 0),
        "industries_bj_share_ge_20pct": sum(1 for v in shares.values() if v["bj_share"] >= 0.20),
        "max_bj_share": worst[0][1]["bj_share"] if worst else 0.0,
        "max_bj_share_industry": worst[0][0] if worst else None,
        "per_industry": shares,
    }


__all__ = [
    "UNIVERSE_POLICY",
    "CLASSIFICATION_SYSTEM",
    "CLASSIFICATION_SOURCE",
    "BJ_EXCHANGE",
    "SH_EXCHANGE",
    "SZ_EXCHANGE",
    "MembershipError",
    "MembershipRow",
    "SessionUniverse",
    "exchange_of",
    "shenwan_rows",
    "level_of",
    "session_universe",
    "required_symbols",
    "historical_only_symbols",
    "taxonomy_counts",
    "bj_constituent_accounting",
]
