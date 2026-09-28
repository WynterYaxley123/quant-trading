# Production constituent coverage matrix v3

Status: **READ-ONLY MEASUREMENT; NOT SOURCE-C ADMISSION**. Fixed window
2025-04-10 through 2026-09-24, pinned CNEquity 0.11.0 at
`1650e384a3fd1f67a70144a489acc91432f1df27`. The row-level CSV and
machine-readable summary are outside Git:

- `D:\QuantForge\runtime\etf-quant-v1\codex-final-completion\reports\production_constituent_coverage_matrix_v3_20260928T082941Z_24d008a9.csv`
- `D:\QuantForge\runtime\etf-quant-v1\codex-final-completion\reports\coverage_summary_v3_20260928T082941Z_24d008a9.json`
- CSV SHA-256: `2288c49115be5a081e02706017429b6cfe1fda69de16e92217c92bf0c416bad0`

The audit uses the pinned `cnequity.query.load` contract for instruments,
trading calendar, Shenwan membership and `daily_bars` with `adjust="hfq"`.
`strict_adj=False` is necessary to *observe and count* the 358 inexact CDR
rows without aborting the whole audit; an `adj_is_exact != True` row is never
allowed into a return. A valid return additionally requires a finalized,
positive-volume, sane OHLCV bar on this and the **immediately prior trading
session**. There is no synthetic close, no carry-forward and no date guessed
from instrument metadata. Membership is the most recent available snapshot
dated no later than the trading session, but its publication/available-at
history is **unproven**. This is not strict ex-ante PIT evidence.

## Measured decomposition

| Measure | Result |
|---|---:|
| Trading sessions | 358 |
| Industry-sessions | 57,996 |
| Member-sessions | 2,078,225 |
| Curated bar rows / symbols | 1,943,979 / 5,611 |
| Shenwan snapshot rows / dates | 419,972 / 81 |
| Previously reported valid (sparse-prior rule) | 40,799 |
| Same legacy rule independently reproduced | 40,799 |
| Strict calendar-adjacent audit valid | 40,763 |
| Strict invalid | 17,233 |
| Legacy sparse-prior-accepted member-sessions | 886 |
| Industries with at least one strict-valid date | 116 / 162 |
| CDR eligible / valid numerator member-sessions | 358 / 0 |

The 36-industry-day delta is **not** a new market-data revision: the earlier
40,799 accepted the last available bar instead of the immediately prior
calendar session. This matrix counts a per-date gate; a recursively chained
Source-C level can have fewer usable dates after a broken prefix. The
2025-04-10 first day has no previous day in this requested window and all 162
industries fail the strict return gate. An index base-value convention is a
separate Source-C decision and must not be inferred from this count.

Primary descriptive reason among the 17,233 invalid industry-days (one reason
per industry-day; these are **not** additive causal attribution):

| Primary reason | Industry-days | Share |
|---|---:|---:|
| Membership symbol has no bar in this *requested window* | 13,834 | 80.28% |
| Fewer than five eligible constituents | 2,130 | 12.36% |
| Instrument identity unresolved | 716 | 4.15% |
| Missing current bar | 417 | 2.42% |
| Missing immediately prior-session bar | 136 | 0.79% |

Across *all* 2,078,225 member-sessions, primary invalid reasons are:
`MEMBERSHIP_ONLY_NO_MARKET_DATA` 106,328; `BAR_MISSING` 22,259;
`INSTRUMENT_UNRESOLVED` 6,449; `PREVIOUS_BAR_MISSING` 6,391;
`CDR_UNSUPPORTED` 358; `BAR_INVALID` 3. The external summary also preserves
complete counts by trading date, industry and symbol. Invalid members within
invalid industries, counted by exchange: SH 25,953; SZ 24,740; BJ 269.
Consequently the earlier handoff inference “BJ exactness means no BJ-caused
gap” is not valid: exactness and bar completeness are different tests.

Forty-six industries have zero valid day. At the 162-industry level, the
percentiles of *mean member coverage* are P0 0, P25 0.7847, P50 0.9404,
P75 0.9922, P100 0.9972 (nearest-rank by zero-based floor). The marginal
one-symbol repair counter ranks `002447.SZ`, `600634.SH`, `000835.SZ`,
`002619.SZ`, `002113.SZ`, and `002464.SZ` at 347
potential industry-days each. These are **counterfactual gate flips**, not
proof the symbol can be repaired or that impacts add. Several high-impact
names are stored as delisted years before this window; e.g. `002447.SZ`
has stored `delist_date=2022-06-27` and `600634.SH` has
`delist_date=2021-07-21`. Across the matrix, **113,369** missing-bar
member-sessions have a stored `delist_date` before the session, and **14,318**
invalid industry-days have at least one such member. Another **524** missing
member-sessions have a stored `list_date` later than the session. These are
*diagnostics only*: fields are not independently proven at field-level, and
none has changed eligibility or been converted into an ex-ante PIT exclusion.
Their 2025/2026 membership is a taxonomy-history
or as-of snapshot integrity concern, not permission to manufacture bars or
remove denominator members. Listing/delisting fields lack field-level
provenance; `PRE_LISTING_EXPECTED` and `POST_DELISTING_EXPECTED` are not
asserted by the matrix.

## Contract implications

- Frozen per-industry gate remains five valid names and at least 80% of all
  as-of members, BJ included. No global 100% gate was invented.
- `MEMBERSHIP_ONLY_NO_MARKET_DATA` means no bar in this **window**, not no
  lifetime market data. Missing bars do not prove suspension or delisting.
- The current pinned membership is reconstructed monthly snapshots, without
  historical publication timestamps; strict historical PIT admission remains
  unresolved.
- Zero-eligible-threshold industries cannot be repaired by price backfill
  alone. A verified historical taxonomy/membership change would be required;
  no such change has been applied.
- The audit is read-only. It did not fetch, stage, compact, publish, snapshot,
  or alter CNEquity data.

Reproduce the audit in the isolated pinned CNEquity environment by running
`services/cnequity-sidecar/coverage_matrix.py` with `--lake` pointing to the
external authoritative lake and `--output` to an existing external runtime
directory. Both paths are rejected if inside a Git repository.
