# CSI300 production benchmark completion v1

Status: **CSI300_COVERAGE_PASS**, not a Production Candidate Snapshot or
Shadow admission. Fixed window 2025-04-10 through 2026-09-24; pinned CNEquity
0.11.0 commit `1650e384a3fd1f67a70144a489acc91432f1df27`.

## Docs → source → runtime

Pinned `docs/datasets/query-guide.md` says `index_bars` are raw index levels,
without an equity adjustment factor. Pinned `docs/reference/cli.md` specifies
`cne backfill index_bars` and automatic compact on success. Pinned
`adapters/tdx_protocol/client.py::fetch_index_bars` requests all eight fixed
indices from TDX; `steps/bars.py::_validate_index_bar_coverage` rejects any
missing symbol×trading-session key. The current session is rejected before
close. The official path is therefore suitable for the fully historical,
closed window; no provider change, mock mode or direct curated write is
needed.

Before backfill, pinned `load("index_bars")` returned 312 rows: all eight
indices had exactly 39 sessions, 2026-08-03 through 2026-09-24. A read-only
call to the **same pinned adapter** returned 2,864 rows, 358 per index, for
the full fixed window. Thus the observed root cause was a narrow prior
request/publication scope, not missing index classification, a schema error or
inability of the source to provide the earlier dates.

The official `cne snapshot create` + `verify` preserved revision 1 as
`etf-quant-pre-index-backfill-20260928-1` (4 verified files). Then the
official `cne backfill index_bars --start 2025-04-10 --end 2026-09-24`
successfully fetched/staged 2,864 rows and compacted them to curated revision
2, run `9fef9fd9-4641-4c62-a584-5a930a8eb73e`, revision ID
`cae8c0c773b34d4b89523faf8cfe81c3`. The subsequent official snapshot
`etf-quant-index-complete-20260928-1` passed verification (6 files). Both
snapshots live under the external authoritative lake's `meta/snapshots/`.

Independent reread via pinned `cnequity.query.load` measured:

| Gate | Result |
|---|---|
| Trading calendar sessions | 358 |
| `000300.SH` sessions / missing dates | 358 / 0 |
| All eight index rows | 2,864 = 8 × 358 |
| Duplicate `(symbol, trade_date)` | 0 |
| Null close | 0 for each index |
| Minimum CSI300 close | 3,735.12 (>0) |
| Source labels | `tdx_protocol` only |
| First / last date | 2025-04-10 / 2026-09-24 |

The post-backfill overlap comparison against the verified pre-backfill
snapshot found **zero** changed OHLCVA/source rows for `000300.SH` and six
other indices. `399001.SZ` had OHLC differences on all 39 pre-existing dates,
typically 0.001 from server precision (example 2026-08-03 close 13,448.311
before, 13,448.31 after); volume, amount and source were unchanged. This is
an explicit revision to the *non-frozen index lake*, not an unchanged-prefix
claim. No frozen F1, Validation or Final OOS data were touched. The CSI300
benchmark series used by ETF-Quant is unchanged on its 39-date overlap.

Do not treat this index-only milestone snapshot as the full multi-dataset
Production Candidate. That candidate remains gated on Source-C, factors and
all three horizon models.
