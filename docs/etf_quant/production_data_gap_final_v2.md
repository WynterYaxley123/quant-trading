# PRODUCTION DATA GAP FINAL v2 (supersedes v1 measurements; v1 not overwritten)

**Window:** `2025-04-10 → 2026-09-24`, 358 sessions, 162 L2 industries, 57,996
industry-days. **Final evidence:** coverage matrix
`production_constituent_coverage_matrix_v3_20260928T091144Z_288178d0.csv`
(SHA-256 `6fc016bd0965b31579dd20527c1118eb60153c4539c04d9b20f26beb0b975e91`) +
summary JSON of the same run id. Repo-external, read-only audit.

## 1. Final headline

| Measure | DeepSeek handoff | FINAL |
|---|---:|---:|
| Curated window bar rows | 1,943,979 | **1,944,307** |
| Curated symbols | 5,611 | 5,611 |
| Adjustment-exact rows | 1,943,621 | ~all but the 358 CDR rows |
| Source-C valid industry-days (strict calendar-adjacent) | 40,799 (legacy semantics) | **40,800 / 57,996 = 70.35%** |
| Invalid industry-days | 17,197 (legacy) | **17,196** |
| Recursive Source-C level usable (readiness audit) | — | 38,684 industry-sessions |
| Cutoff-ready industries (Source-C usable at 2026-09-24) | — | **107 / 162** |
| CSI300 `000300.SH` sessions | 39 / 358 | **358 / 358** |

## 2. What the 17,196 invalid industry-days are (measured, not estimated)

Primary reason per invalid industry-day:

| Reason | Industry-days | Share of 17,196 |
|---|---:|---:|
| `MEMBERSHIP_ONLY_NO_MARKET_DATA` | 13,836 | 80.46% |
| `INSUFFICIENT_ELIGIBLE_CONSTITUENTS` | 2,130 | 12.39% |
| `INSTRUMENT_UNRESOLVED` | 716 | 4.16% |
| `BAR_MISSING` | 378 | 2.20% |
| `PREVIOUS_BAR_MISSING` | 136 | 0.79% |

Member-session level (inside invalid industry-days): `MEMBERSHIP_ONLY_NO_MARKET_DATA`
106,328; `BAR_MISSING` 21,931; `INSTRUMENT_UNRESOLVED` 6,449; `PREVIOUS_BAR_MISSING`
6,391; `CDR_UNSUPPORTED` 358 (all `689009.SH`, denominator-visible, numerator-excluded);
`BAR_INVALID` 3. Exchange split of invalid members: SH 25,588 / SZ 24,740 / BJ 269.

**Structural legitimacy:** 14,281 of 17,196 invalid industry-days (83.0%) carry
stored post-delist member gaps — membership snapshots legitimately retain
classifications for stocks whose stored delist date has passed (the pinned
membership adapter has no end/delist condition; see the pinned contract audit).
These are *expected* gaps, not recoverable data loss. A further 113,369 missing
member-sessions are stored-post-delist; 524 are stored-pre-list.
`PRE_LISTING_EXPECTED` / `POST_DELISTING_EXPECTED` remain diagnostic (field-level
date provenance unverified) and were never used to change denominators.

## 3. Recovery performed in this lineage (all via the official CNEquity lifecycle)

| Action | Effect |
|---|---|
| Exact-adjustment recovery (watermark root cause + backlog drain) | exact ratio → 99.98% |
| BJ historical routing (`BEIJING_AWARE_HISTORICAL_ROUTING`) | BJ 94,972 rows / 347 symbols, exact 100% |
| CSI300 official `index_bars` backfill | 39 → **358 / 358** sessions, 0 overlap mismatches |
| `601318.SH` targeted backfill + adj-factor realign (official, pre/post snapshots) | +328 net rows; last marginal repair; valid 40,799 → 40,800 |
| CDR `689009.SH` | kept denominator-visible; 0 gate flips; no CDR support added |

Remaining one-symbol marginal opportunities not stored-post-delist are small and
were enumerated (`one_symbol_marginal_not_stored_post_delist` in the summary);
after the `601318.SH` repair no further high-impact recoverable symbol exists
(remaining candidates are predominantly delisted or suspended names whose gaps
are structurally expected).

## 4. What was NOT done

- No coverage threshold was relaxed; no membership was thinned; no raw price
  entered a numerator; no `adj_is_exact` value was forged; no direct curated
  write; no third-party runtime price fallback; no fake 57,996/57,996.
- `920201.BJ list_date=2026-09-24` remains `LIST_DATE_UNVERIFIED` at field level
  (date externally corroborated; unused by Source-C).

## 5. Residual gap statement

The residual 17,196 invalid industry-days are dominated by
`MEMBERSHIP_ONLY_NO_MARKET_DATA` over delisted/suspended/never-ingested members.
They are legitimate, measured and reason-coded. The model-runnable subset is
admitted separately as `COMMON_MODEL_UNIVERSE_V1` (107 industries), with the
full-162 zero-complete-training-date fact preserved.
