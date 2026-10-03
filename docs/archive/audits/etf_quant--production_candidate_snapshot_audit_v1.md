# PRODUCTION CANDIDATE SNAPSHOT AUDIT v1

**Task:** ETF-Quant V1 — production data backfill + Source-C full coverage + production candidate snapshot.
**Base commit:** `58c551a03d3f4bf3cbb39172b3843bd2b6e942ec`

---

## 1. Status

```
CANDIDATE SNAPSHOT CREATED = NO
STATUS = BLOCKED
```

| Field | Value |
|---|---|
| candidate snapshot created? | **NO** |
| snapshot_id | **none** |
| snapshot_type | n/a (would have been `PRODUCTION_CANDIDATE`) |
| cutoff | n/a |
| warm-up start | **2025-04-10** (derived, unchanged) |
| manifest SHA | **none** |
| number of files | **0** |
| all hashes verified? | n/a — nothing published |
| `SNAPSHOT_INTEGRITY_PASS` | **not claimed** |

The prior round's `SMOKE_SCOPE_ONLY` snapshot `93e11ee6…567b` is **unchanged** and is explicitly **not**
a production candidate.

---

## 2. Why it is blocked

The candidate gate requires every one of these to reach admission:

| Gate input | Status |
|---|---|
| trading calendar | ✅ admitted (1,879 sessions) |
| industry membership | ✅ admitted (419,972 Shenwan rows, 81 snapshots) |
| instrument master | ✅ **improved** — 7,702 rows, 337 delisted names recovered |
| required stock bars | ❌ **BLOCKED** — staged but not published (`CNEQUITY_PUBLISH_GATE_BLOCKER`) |
| required adjustment data | ✅ engine verified at scale (85,545/85,545 exact) but only over the old 254 symbols |
| Source-C derived series | ❌ not measurable (depends on the bars) |
| necessary ETF market-data capability | ⚠️ partial — 3 ETFs fetched of 2,142 |
| CSI300 | ⚠️ 39 of 358 sessions (10.88%); structurally ready, history not loaded |
| schema PASS | ✅ all admitted datasets schema-valid |
| hash PASS | ⚠️ only for what is published |
| cutoff PASS | n/a |
| adjustment PASS | ⚠️ for the published subset only |
| coverage audit complete | ❌ no |

**Publishing a snapshot now would label a 4.2%-constituent, 254-symbol dataset as a "production
candidate".** That would be a false label, so no snapshot was created.

---

## 3. Data state, precisely

| Location | Rows | Symbols | Range | Published? |
|---|---|---|---|---|
| `curated/daily_bars` | **85,545** | 254 | 2025-04-10 → 2026-09-24 | ✅ curated |
| `staging/daily_bars` | **2,660,545** | **3,345** | 2025-04-10 → 2026-09-24 | ❌ blocked |
| `curated/adj_factors` | 85,545 | 254 | same | ✅ curated |
| `curated/instruments` | **7,702** | — | — | ✅ curated |
| `curated/industry_members` | 419,972 (SW) | 5,930 | 2020-01-23 → 2026-09-24 | ✅ curated |
| `curated/trading_calendar` | 1,879 sessions | — | 2020-01-02 → 2027-09-27 | ✅ curated |
| `curated/index_bars` (CSI300) | 39 | 1 | 2026-08-03 → 2026-09-24 | ✅ curated |

The **2,660,545 staged rows are intact and recoverable**. Nothing was deleted to force a publish.

---

## 4. Adjustment status (unchanged, verified)

| Metric | Value |
|---|---|
| rows evaluated | **85,545** |
| `adj_is_exact` true | **85,545** |
| `adj_is_exact` false | **0** |
| exact ratio | **1.000000** |
| `strict_adj=True` | passed |
| rows genuinely differing from raw | **84,912 (99.26%)** |
| `ADJUSTMENT_GATE_PASS` | ✅ for the published subset |
| `PRODUCTION_ADJUSTMENT_BLOCKER` | not triggered |

**Caveat carried forward:** `adj_is_exact` proves *factor coverage*, not factor PIT-ness. The
`TIME_SEMANTICS_BLOCKER` from the transport audit still stands.

---

## 5. ETF data capability

| Metric | Value |
|---|---|
| ETF instruments | **2,142** (SH 1,039 / SZ 1,103) |
| with `list_date` | 1,632 |
| with `delist_date` | 0 |
| ETFs with bars fetched | **3** |
| ETF bar rows | 117 |
| ETFs with 20/20 non-null `amount` | 3 / 3 |
| **full-ETF bar fetch** | **`ETF_FULL_BAR_FETCH_DEFERRED`** — outside the approved budget, and a full sweep was not attempted |
| industry/theme ETF subset identifiable from source? | **No** — no fund-type, theme or tracking-index field exists |

### 5.1 Tradability contract status

| Contract | Status |
|---|---|
| `ETF_BAR_DERIVED_TRADABILITY_V1` | **IMPLEMENTED + TESTED** — `strategies/etf_quant/data/tradability.py`, 18 tests |
| native ETF `trading_status` | **STILL STRUCTURALLY UNSUPPORTED** — not fixed, not pretended to be fixed |
| real ETF execution | **NOT PERFORMED** |

The contract is **evidence, not proof**, and every verdict carries
`BAR_DERIVED_EX_POST_TRADABILITY_EVIDENCE_NOT_REALTIME_EXCHANGE_STATUS`. It cannot see a price-limit
queue that produced a bar but no fill, an intraday halt, or a suspension announced after the close.

---

## 6. CSI300 status

| Metric | Value |
|---|---|
| rows | **39** |
| range | 2026-08-03 → 2026-09-24 |
| sessions expected in warm-up | 358 |
| **missing sessions** | **319** |
| coverage | **10.89%** |
| null closes / non-positive closes | 0 / 0 |
| continuity beyond 39 sessions | **UNVERIFIED** (nothing to check) |
| candidate admission | ❌ not extended this round |

---

## 7. Immutability and pointer rules (§34, §36)

No snapshot was published, so no immutability question arises and **no `latest` production pointer was
created or overwritten**. The prior smoke snapshot's pointer, if any, is untouched. No `candidate_latest`
was invented.

---

## 8. Shadow and mapping gates (§37, §38)

```
SHADOW_EPOCH_CREATED = FALSE
VERIFIED_INDUSTRY_ETF_MAPPING = NONE
FORMAL_PORTFOLIO = NONE
```

Even had the candidate passed, a Shadow epoch would remain forbidden: verified industry→ETF mapping,
20-day liquidity admission and ≥5 distinct executable ETFs are all still outstanding. The correct
status would have been at most **DATA READY FOR MAPPING STAGE**, and it is not that either.

---

## 9. Hard blockers

```
CNEQUITY_PUBLISH_GATE_BLOCKER
  - compact skips daily_bars while a manifest batch is not in a terminal success state.
  - Consequence: 2,660,545 staged rows (3,345 symbols) are not in curated.

WINDOWS_COMMAND_LINE_LIMIT
  - 32,767 chars prevents a single whole-universe invocation (5,559 symbols ~ 61,000 chars),
    which is what a fully-settled publish would require from this host.

HISTORICAL_CONSTITUENT_DATA_GAP (371 symbols)
  - 355 BJ + 16 legacy SH/SZ; verified 0 rows from the pinned history route.

CSI300_HISTORY_NOT_LOADED  (39 / 358 sessions)
ETF_BARS_NOT_FETCHED_AT_SCALE (3 of 2,142)
SOURCE_C_NOT_MEASURABLE (depends on the bars)
TIME_SEMANTICS_BLOCKER (carried forward: adj_is_exact is coverage, not PIT-ness)
SOURCE_LICENSING_UNRESOLVED (carried forward; no market data committed to Git)
```

---

## 10. Declaration

**NO SHADOW EPOCH WAS CREATED. NO FORMAL PORTFOLIO/NAV/PERFORMANCE WAS CREATED. NO VERIFIED INDUSTRY→ETF
MAPPING WAS CREATED. NO FORMAL TOP-5 ETF TARGET WAS CREATED. NO REAL MARKET DATA WAS COMMITTED TO GIT.**
No strategy parameter was changed. No third-party market-data fallback was introduced.
