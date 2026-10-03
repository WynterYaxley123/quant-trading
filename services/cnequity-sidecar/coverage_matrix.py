"""Read-only production constituent audit. All row-level output stays outside Git.

The official pinned CNEquity query interface supplies curated bars, membership,
instruments and calendar. This program does not fetch, derive, stage, compact,
publish or mutate the lake. It distinguishes the old sparse-prior measurement
from a calendar-adjacent, exact-adjustment/valid-bar measurement.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

START = date(2025, 4, 10)
CUTOFF = date(2026, 9, 24)
MIN_VALID = 5
MIN_COVERAGE = 0.80
CDR = "689009.SH"
FIELDS = (
    "trade_date",
    "industry_code",
    "symbol",
    "canonical_symbol",
    "exchange",
    "asset_type",
    "membership_eligible",
    "instrument_resolved",
    "identity_source",
    "identity_observed_at",
    "bar_available",
    "bar_valid",
    "adjustment_available",
    "adj_is_exact",
    "return_valid",
    "invalid_reason",
    "source_provenance",
    "prev_session",
    "prev_bar_available",
    "prev_adj_is_exact",
    "stored_list_date",
    "list_date_provenance",
    "stored_delist_date",
    "delist_date_provenance",
    "adj_close",
    "prev_adj_close",
    "return_value",
)


def valid_bar(row: tuple | None) -> bool:
    """Raw finalized OHLCV check; no synthetic price/volume fallback."""
    if row is None:
        return False
    adj_close, _exact, volume, op, high, low, close, _source = row
    values = (op, high, low, close, adj_close)
    return (
        all(isinstance(v, (float, int)) and math.isfinite(v) and v > 0 for v in values)
        and isinstance(volume, (float, int))
        and math.isfinite(volume)
        and volume > 0
        and high >= max(op, close)
        and low <= min(op, close)
    )


def classify(
    instrument: dict | None,
    current: tuple | None,
    previous: tuple | None,
    *,
    symbol: str | None = None,
    known_prev_symbols: set[str] | None = None,
    window_symbols: set[str] | None = None,
) -> str | None:
    """A single primary reason per member-session; UNKNOWN beats guessed dates."""
    if instrument is None:
        if symbol is not None and known_prev_symbols is not None and symbol in known_prev_symbols:
            return "CODE_MAPPING_GAP"
        return "INSTRUMENT_UNRESOLVED"
    if instrument.get("asset_type") == "cdr" or instrument.get("symbol") == CDR:
        return "CDR_UNSUPPORTED"
    if current is None:
        if symbol is not None and window_symbols is not None and symbol not in window_symbols:
            return "MEMBERSHIP_ONLY_NO_MARKET_DATA"
        return "BAR_MISSING"
    if not valid_bar(current):
        return "BAR_INVALID"
    if current[1] is not True:
        return "ADJ_NON_EXACT"
    if previous is None:
        return "PREVIOUS_BAR_MISSING"
    if not valid_bar(previous):
        return "PREVIOUS_BAR_INVALID"
    if previous[1] is not True:
        return "PREVIOUS_ADJ_NON_EXACT"
    ret = current[0] / previous[0] - 1.0
    if not math.isfinite(ret):
        return "BAR_INVALID"
    return None


def industry_failure_reason(eligible: int, valid: int, reasons: Counter) -> str:
    if not reasons and eligible < MIN_VALID:
        return "INSUFFICIENT_ELIGIBLE_CONSTITUENTS"
    if not reasons and valid < MIN_VALID:
        return "INSUFFICIENT_VALID_CONSTITUENTS"
    return sorted(reasons.items(), key=lambda x: (-x[1], x[0]))[0][0] if reasons else "UNKNOWN"


def legacy_return_valid(current: tuple | None, last_available: tuple | None) -> bool:
    """Reproduce only the earlier 40,799/57,996 audit measurement semantics."""
    if current is None or last_available is None or current[1] is not True:
        return False
    c, p = current[0], last_available[0]
    return (
        isinstance(c, (float, int))
        and isinstance(p, (float, int))
        and math.isfinite(c)
        and math.isfinite(p)
        and c > 0
        and p > 0
        and math.isfinite(c / p - 1.0)
    )


def stored_date_diagnostics(
    instrument: dict | None, day: date, reason: str | None
) -> tuple[bool, bool]:
    """Flag suspicious stored dates; never change eligibility or classify PIT."""
    if not instrument or reason not in ("MEMBERSHIP_ONLY_NO_MARKET_DATA", "BAR_MISSING"):
        return False, False
    listed, delisted = instrument.get("list_date"), instrument.get("delist_date")
    return (
        isinstance(listed, date) and day < listed,
        isinstance(delisted, date) and day > delisted,
    )


def _outside_repo(path: Path) -> Path:
    resolved = path.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("EXTERNAL_DIRECTORY_REQUIRED")
    if any((p / ".git").exists() for p in (resolved, *resolved.parents)):
        raise ValueError("OUTPUT_OR_LAKE_INSIDE_GIT_BLOCKED")
    return resolved


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def audit(lake: Path, output: Path) -> dict:
    import polars as pl
    from cnequity.query import load

    lake, output = _outside_repo(lake), _outside_repo(output)
    started = datetime.now(timezone.utc).isoformat()
    instruments_frame = load("instruments", data_root=str(lake))
    instruments = {r["symbol"]: r for r in instruments_frame.to_dicts()}
    known_prev_symbols = {r["prev_symbol"] for r in instruments.values() if r.get("prev_symbol")}
    calendar = load("trading_calendar", start=START, end=CUTOFF, data_root=str(lake))
    sessions = sorted(calendar.filter(pl.col("is_trading"))["trade_date"].to_list())
    if len(sessions) != len(set(sessions)) or not sessions or sessions[-1] != CUTOFF:
        raise ValueError("CALENDAR_CUTOFF_OR_DUPLICATE_BLOCKER")

    membership = load("industry_members", start=date(2020, 1, 1), end=CUTOFF, data_root=str(lake))
    membership = membership.filter(
        (pl.col("source") == "sw") & (pl.col("classification_system") == "sw")
    )
    snapshots: dict[date, dict[str, str]] = defaultdict(dict)
    for symbol, code, snap in membership.select(
        "symbol", "industry_code", "as_of_date"
    ).iter_rows():
        if not code or len(code) != 6 or snap is None:
            raise ValueError("MEMBERSHIP_CONTRACT_BLOCKER")
        if symbol in snapshots[snap]:
            raise ValueError("DUPLICATE_MEMBERSHIP_SNAPSHOT_BLOCKER")
        snapshots[snap][symbol] = code[:4]
    snapshot_days = sorted(snapshots)
    if not snapshot_days or snapshot_days[0] > sessions[0]:
        raise ValueError("NO_MEMBERSHIP_AT_WINDOW_START")

    bars = load(
        "daily_bars", start=START, end=CUTOFF, adjust="hfq", strict_adj=False, data_root=str(lake)
    )
    bar_count, bar_symbols = bars.height, bars["symbol"].n_unique()
    window_symbols = set(bars["symbol"].unique().to_list())
    if bars.select("symbol", "trade_date").is_duplicated().any():
        raise ValueError("DUPLICATE_DAILY_BAR_BLOCKER")
    bars = bars.select(
        "trade_date",
        "symbol",
        "adj_close",
        "adj_is_exact",
        "volume",
        "open",
        "high",
        "low",
        "close",
        "source",
    )
    rows_iter = iter(bars.sort("trade_date", "symbol").iter_rows())
    next_bar = next(rows_iter, None)
    prior_rows: dict[str, tuple] = {}
    last_available: dict[str, tuple] = {}
    previous_session = None
    snapshot_cursor = 0
    current_snapshot = snapshot_days[0]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    matrix = output / f"production_constituent_coverage_matrix_v3_{run_id}.csv"
    temp = output / f".{matrix.name}.{uuid.uuid4().hex}.partial"
    reason_member: Counter[str] = Counter()
    reason_industry_primary: Counter[str] = Counter()
    by_exchange: Counter[str] = Counter()
    by_industry: Counter[str] = Counter()
    by_symbol: Counter[str] = Counter()
    by_date: Counter[str] = Counter()
    marginal_symbols: Counter[str] = Counter()
    marginal_not_stored_post_delist: Counter[str] = Counter()
    missing_not_stored_post_delist: Counter[str] = Counter()
    per_industry: dict[str, dict[str, float]] = defaultdict(
        lambda: {"sessions": 0, "valid": 0, "coverage_sum": 0.0}
    )
    valid_dates, legacy_valid_dates, total_dates = 0, 0, 0
    member_rows = 0
    sparse_prev_accepted = 0
    cdr_denominator = cdr_numerator = 0
    stored_post_delist_missing_members = 0
    stored_pre_list_missing_members = 0
    invalid_days_with_stored_post_delist_gap = 0
    with temp.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for day in sessions:
            while (
                snapshot_cursor + 1 < len(snapshot_days)
                and snapshot_days[snapshot_cursor + 1] <= day
            ):
                snapshot_cursor += 1
                current_snapshot = snapshot_days[snapshot_cursor]
            active = snapshots[current_snapshot]
            groups = defaultdict(list)
            for symbol, code in active.items():
                groups[code].append(symbol)
            current_rows = {}
            while next_bar is not None and next_bar[0] <= day:
                bar_day, symbol, *payload = next_bar
                if bar_day == day:
                    current_rows[symbol] = tuple(payload)
                next_bar = next(rows_iter, None)

            for code, symbols in sorted(groups.items()):
                total_dates += 1
                reasons: Counter[str] = Counter()
                invalid_symbols = []
                stored_post_delist_gap = False
                valid = legacy_valid = 0
                for symbol in sorted(symbols):
                    instrument = instruments.get(symbol)
                    cur, prev = current_rows.get(symbol), prior_rows.get(symbol)
                    reason = classify(
                        instrument,
                        cur,
                        prev,
                        symbol=symbol,
                        known_prev_symbols=known_prev_symbols,
                        window_symbols=window_symbols,
                    )
                    is_valid = reason is None
                    valid += is_valid
                    if legacy_return_valid(cur, last_available.get(symbol)):
                        legacy_valid += 1
                        if prev is None:
                            sparse_prev_accepted += 1
                    exchange = symbol.rsplit(".", 1)[-1]
                    if symbol == CDR:
                        cdr_denominator += 1
                        cdr_numerator += is_valid
                    if reason is not None:
                        reason_member[reason] += 1
                        reasons[reason] += 1
                        invalid_symbols.append(symbol)
                    stored_pre_list, stored_post_delist = stored_date_diagnostics(
                        instrument, day, reason
                    )
                    if stored_post_delist:
                        stored_post_delist_missing_members += 1
                        stored_post_delist_gap = True
                    if stored_pre_list:
                        stored_pre_list_missing_members += 1
                    if (
                        reason in ("MEMBERSHIP_ONLY_NO_MARKET_DATA", "BAR_MISSING")
                        and not stored_post_delist
                    ):
                        missing_not_stored_post_delist[symbol] += 1
                    writer.writerow(
                        {
                            "trade_date": day.isoformat(),
                            "industry_code": code,
                            "symbol": symbol,
                            "canonical_symbol": symbol,
                            "exchange": exchange,
                            "asset_type": instrument.get("asset_type") if instrument else None,
                            "membership_eligible": True,
                            "instrument_resolved": instrument is not None,
                            "identity_source": instrument.get("source") if instrument else None,
                            "identity_observed_at": str(instrument.get("fetched_at"))
                            if instrument
                            else None,
                            "bar_available": cur is not None,
                            "bar_valid": valid_bar(cur),
                            "adjustment_available": cur is not None and cur[1] is True,
                            "adj_is_exact": cur[1] if cur else None,
                            "return_valid": is_valid,
                            "invalid_reason": reason,
                            "source_provenance": f"membership=sw@{current_snapshot};bar={cur[7] if cur else 'UNKNOWN'}",
                            "prev_session": previous_session.isoformat()
                            if previous_session
                            else None,
                            "prev_bar_available": prev is not None,
                            "prev_adj_is_exact": prev[1] if prev else None,
                            "stored_list_date": instrument.get("list_date") if instrument else None,
                            "list_date_provenance": "UNVERIFIED_FIELD_LEVEL"
                            if instrument
                            else "UNKNOWN",
                            "stored_delist_date": instrument.get("delist_date")
                            if instrument
                            else None,
                            "delist_date_provenance": "UNVERIFIED_FIELD_LEVEL"
                            if instrument
                            else "UNKNOWN",
                            "adj_close": cur[0] if cur else None,
                            "prev_adj_close": prev[0] if prev else None,
                            "return_value": cur[0] / prev[0] - 1.0
                            if is_valid and cur is not None and prev is not None
                            else None,
                        }
                    )
                    member_rows += 1
                eligible = len(symbols)
                passed = valid >= MIN_VALID and valid / eligible >= MIN_COVERAGE
                baseline_passed = (
                    legacy_valid >= MIN_VALID and legacy_valid / eligible >= MIN_COVERAGE
                )
                valid_dates += passed
                legacy_valid_dates += baseline_passed
                per_industry[code]["sessions"] += 1
                per_industry[code]["valid"] += passed
                per_industry[code]["coverage_sum"] += valid / eligible
                if not passed:
                    invalid_days_with_stored_post_delist_gap += stored_post_delist_gap
                    by_industry[code] += 1
                    by_date[day.isoformat()] += 1
                    primary = industry_failure_reason(eligible, valid, reasons)
                    reason_industry_primary[primary] += 1
                    for symbol in invalid_symbols:
                        by_exchange[symbol.rsplit(".", 1)[-1]] += 1
                        by_symbol[symbol] += 1
                    # A one-symbol repair is sufficient only if the frozen gate
                    # would pass after that one previously invalid member becomes valid.
                    if valid + 1 >= MIN_VALID and (valid + 1) / eligible >= MIN_COVERAGE:
                        marginal_symbols.update(invalid_symbols)
                        for symbol in invalid_symbols:
                            instrument = instruments.get(symbol)
                            stored_delist = instrument.get("delist_date") if instrument else None
                            if not isinstance(stored_delist, date) or day <= stored_delist:
                                marginal_not_stored_post_delist[symbol] += 1
            for symbol, row in current_rows.items():
                last_available[symbol] = row
            prior_rows = current_rows
            previous_session = day
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, matrix)

    report = {
        "contract": "PRODUCTION_CONSTITUENT_COVERAGE_MATRIX_V3",
        "status": "READ_ONLY_AUDIT",
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "lake_root": str(lake),
        "window": [START.isoformat(), CUTOFF.isoformat()],
        "sessions": len(sessions),
        "source_membership_rows": membership.height,
        "source_membership_snapshots": len(snapshot_days),
        "source_bar_rows": bar_count,
        "source_bar_symbols": bar_symbols,
        "member_sessions": member_rows,
        "industry_sessions": total_dates,
        "valid_industry_sessions": valid_dates,
        "invalid_industry_sessions": total_dates - valid_dates,
        "previous_reported_valid": 40799,
        "previous_reported_invalid": 17197,
        "legacy_semantics_reproduced_valid": legacy_valid_dates,
        "legacy_sparse_prior_accepted_member_sessions": sparse_prev_accepted,
        "cdr_eligible_member_sessions": cdr_denominator,
        "cdr_valid_numerator_sessions": cdr_numerator,
        "diagnostic_stored_post_delist_missing_member_sessions": stored_post_delist_missing_members,
        "diagnostic_stored_pre_list_missing_member_sessions": stored_pre_list_missing_members,
        "diagnostic_invalid_industry_days_with_stored_post_delist_gap": invalid_days_with_stored_post_delist_gap,
        "invalid_member_reasons": dict(reason_member.most_common()),
        "invalid_industry_primary_reasons": dict(reason_industry_primary.most_common()),
        "invalid_member_exchanges_in_invalid_industries": dict(by_exchange.most_common()),
        "invalid_industry_days_by_industry": dict(by_industry.most_common()),
        "invalid_industry_days_by_date": dict(by_date.most_common()),
        "invalid_member_symbols_in_invalid_industries": dict(by_symbol.most_common()),
        "one_symbol_marginal_repair_opportunities": dict(marginal_symbols.most_common()),
        "one_symbol_marginal_not_stored_post_delist": dict(
            marginal_not_stored_post_delist.most_common()
        ),
        "missing_bar_not_stored_post_delist_by_symbol": dict(
            missing_not_stored_post_delist.most_common()
        ),
        "per_industry": {
            code: {**v, "mean_coverage": v["coverage_sum"] / v["sessions"]}
            for code, v in sorted(per_industry.items())
        },
        "matrix_file": matrix.name,
        "matrix_sha256": _digest(matrix),
        "row_level_data_repo_external": True,
        "classification_limitations": [
            "Instrument field-level list_date provenance is unavailable; no prelisting deduction.",
            "Instrument field-level delist_date provenance is unavailable; diagnostic post-delist counts do not alter eligibility or assert historical PIT.",
            "MEMBERSHIP_ONLY_NO_MARKET_DATA means no bar in the requested window, not proof of no lifetime trading.",
            "CODE_MAPPING_GAP is a diagnostic of prev_symbol only; no historical rename mapping is applied.",
            "Historical membership publication/available-at evidence is unproven.",
            "Primary industry reasons are descriptive, not additive causal attribution.",
        ],
    }
    summary = output / f"coverage_summary_v3_{run_id}.json"
    summary_temp = output / f".{summary.name}.{uuid.uuid4().hex}.partial"
    with summary_temp.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(summary_temp, summary)
    return {
        "summary_path": str(summary),
        "matrix_path": str(matrix),
        "sessions": len(sessions),
        "industry_sessions": total_dates,
        "valid": valid_dates,
        "invalid": total_dates - valid_dates,
        "legacy_valid": legacy_valid_dates,
        "member_sessions": member_rows,
        "matrix_sha256": report["matrix_sha256"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lake", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.lake, args.output)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
