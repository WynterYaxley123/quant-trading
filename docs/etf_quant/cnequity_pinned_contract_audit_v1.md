# Pinned CNEquity contract audit v1

Authority: `rootSunc/CNEquity` commit
`1650e384a3fd1f67a70144a489acc91432f1df27`, version 0.11.0.
This audit compares the **pinned documentation**, **pinned implementation**,
and **observed isolated-runtime behavior**; newer online docs are not
substituted. The upstream checkout and its dependencies were not modified.

| Concern | Pinned docs/source contract | Observed behavior and implication |
|---|---|---|
| Query and adjustment | `docs/datasets/query-guide.md`, `query/reader.py`: curated `daily_bars` are raw; `load(adjust="hfq")` adds adjusted columns; `strict_adj=True` rejects missing factors, while false may use a factor of one but sets `adj_is_exact=False`. | 1,943,979 window bars, 1,943,621 exact; all 358 inexact rows belong to CDR `689009.SH`. The read-only matrix explicitly excludes all 358 from returns; it never treats fallback as exact. |
| Membership | `docs/datasets/catalog.md`, `query-guide.md`, `adapters/sw/industry_history.py`, `steps/structure.py`: `industry_members` is `snapshot_with_backfill`; `as_of_date` identifies a reconstructed month-end classification snapshot, not guaranteed publication/availability time. The adapter takes each symbol's latest `start_date <= as_of_date` but has no end/delist condition. | 419,972 Shenwan rows across 81 snapshots. A classification can persist into 2025/2026 after its stock's stored delist date. Monthly backward-as-of membership resolves the 162-industry taxonomy, but an *active tradable member* interpretation and strict historical PIT remain **unproven**. `load(..., as_of=...)` strict PIT applies to financial/disclosure datasets, not a magic conversion of membership. |
| Instrument identity | `docs/datasets/schema.md`, `steps/reference.py`, `storage/instruments.py`: `list_date` nullable; BSE board adapter emits null, EastMoney `f26` may enrich it, sticky merge can retain prior values. | `920201.BJ` stores `list_date=2026-09-24`, `source=bse`, `fetched_at=2026-09-28`, and has no window bars. Dataset-level `source=bse` does **not** establish field-level date provenance; the date is not used as prelisting proof or silently nulled. |
| BJ routing | Pinned `query-guide.md` describes BJ as Sina-routed because `domain/symbols.TDX_EXCHANGES={SH,SZ}`. Pinned `adapters/tdx_protocol/client.py` also contains a BJ TDX history helper. | **PINNED_DOC_IMPLEMENTATION_DISCREPANCY**. The approved sidecar adds BJ to the live routing partition, preserving pinned upstream. Measured 94,972 BJ bars / 347 symbols at exact ratio 1. This does not prove every BJ session has a bar. |
| Publication | `docs/modules/storage.md`, `docs/modules/orchestrator.md`, `docs/reference/cli.md`: fetch → staging/batch → settle → compact → curated. Direct curated writes are outside contract. | Existing 95 non-pass manifest records were separately classified by the DeepSeek handoff as carrying no unpublished production bar rows; they were not manually settled. New backfills must use the official lifecycle. |
| Historical/delisted symbols | `docs/reference/cli.md` `cne delisted` and `backfill daily_bars --symbols`; `query-guide.md` rejects an empty response as proof of a suspension. | Many 2025/2026 membership names have no window market data; some have stored delist dates years before the window. An official source may recover true missing historical bars, but cannot invent post-delist prices. Neither membership row nor frozen denominator is silently dropped. |
| Index benchmark | `docs/datasets/query-guide.md`: `index_bars` are raw index points, never adjusted. Pinned `adapters/tdx_protocol/client.py` requests eight fixed TDX indices, `steps/bars.py` rejects incomplete symbol×session coverage and unfinished current daily bars. | Curated window initially has all eight indices only from 2026-08-03 onward (39 rows each). The same pinned adapter read-only fetched 358 rows each over 2025-04-10..2026-09-24, so this is a publication/backfill gap rather than evidence for changing provider or code. |
| Snapshot | `docs/reference/cli.md` and `storage/snapshots.py`: immutable dataset copies with hashes, state/contract fingerprints, lineage, verify and restore. | Official snapshots are appropriate for protecting the index dataset before backfill and freezing a candidate later, only after upstream gates are audited. A fresh custom snapshot format must not replace the official lifecycle. |

The `INTERNAL_EQUAL_WEIGHT_SHENWAN_SERIES_V1` is **not** an official Shenwan
index. Its fixed five-name/80% per-industry-date gate uses exact adjusted
constituent returns with BJ included in the full as-of denominator.
`strategies/etf_quant/data/source_c.py` holds a displayed level on an invalid
day, whereas `strategies/etf_quant/runtime/industry.py` marks a broken
recursive prefix unusable. The earlier 40,799-day external measurement also
accepted a last-available previous bar instead of the previous *trading
session*. These three semantics must not be conflated. The new coverage
matrix measures the strict date gate only; it is not a claim that a complete
production Source-C level or model is ready.

No third-party runtime price fallback, direct curated write, mock data,
future labels, sealed Validation performance or Final OOS were used in this
audit.
