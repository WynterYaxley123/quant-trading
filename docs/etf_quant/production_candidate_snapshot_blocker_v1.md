# PRODUCTION CANDIDATE SNAPSHOT — BLOCKER v1

**Task:** ETF-Quant V1 — long-run CNEquity data-layer recovery & production admission.
**Base commit:** `26a3295bc304097e9b76a226a455c414865a11d1`

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
| files | **0** |
| all hashes verified? | n/a — nothing published |
| `SNAPSHOT_INTEGRITY_PASS` | **not claimed** |

The prior `SMOKE_SCOPE_ONLY` snapshot `93e11ee6…567b` is **unchanged** and is not a production
candidate.

---

## 2. Gate-by-gate position

| Candidate gate input | Status |
|---|---|
| publication recovered | ✅ **PASS** — 44 successful compactions, 0 forced |
| curated full scope published | ✅ **PASS** — 1,849,007 production-window rows / 5,264 symbols |
| required stock coverage audited | ✅ **DONE** — 5,261 of 5,930 required (88.7%) |
| BJ policy actual outcome known | ✅ **DONE** — capability proven present; bar lane intermittent; impact quantified |
| **adjustment exact** | ❌ **BLOCKED** — 13.22% exact; median 1.0 factor rows per symbol |
| **Source-C coverage measured** | ❌ **BLOCKED** — 111 of 57,996 industry-days (0.19%) |
| factor readiness | ❌ downstream of the above |
| H10 / H40 / H120 readiness | ❌ downstream |
| CSI300 complete | ❌ 39 of 358 sessions (10.89%) |
| manifest / hash PASS | ⚠️ only for what is admitted |

**Five of the eleven gates now pass, three are newly unblocked this round, and the remaining blocker is
a single precise defect** (§3). Publishing a snapshot now would require mislabelling a 13%-exact-adjusted
dataset as production-ready, so none was created.

---

## 3. The single irreducible blocker

```
cne derive adj_factors commits ONE factor row per symbol instead of a factor history.
```

Measured evidence:

| Metric | Value |
|---|---|
| `derived/adj_factors` rows | **334,417** |
| symbols covered | 5,274 |
| **median factor rows per symbol** | **1.0** |
| symbols with zero factors | 199 of 5,473 |
| bar rows with no matching `(symbol, trade_date)` factor | **1,893,197** |
| resulting `adj_is_exact` ratio | **0.132244** |

With one factor row per symbol, at most one bar date per symbol can be exact, so the exact ratio is a
thin sliver rather than a coverage gradient. Downstream, the frozen Source-C gate correctly refuses
87% of the data and yields **111 valid industry-days out of 57,996**.

**This is the whole remaining problem.** Everything north of it now works.

---

## 4. Data state

| Dataset | Rows | Symbols | Range | Admitted |
|---|---|---|---|---|
| `daily_bars` (production window) | **1,849,007** | **5,264** | 2025-04-10 → 2026-09-24 | ✅ curated |
| `daily_bars` (all partitions) | 2,227,614 | 5,473 | 2016-01-04 → 2026-09-24 | ✅ curated |
| `adj_factors` | 334,417 | 5,274 | 2016-01-04 → 2026-09-24 | ⚠️ **1 row/symbol** |
| `instruments` | 7,702 | — | — | ✅ curated (SH 3,506 / SZ 4,196; **BJ 0 — lane intermittent**) |
| `industry_members` (SW) | 419,972 | 5,930 | 2020-01-23 → 2026-09-24 | ✅ curated |
| `trading_calendar` | 1,879 sessions | — | 2020-01-02 → 2027-09-27 | ✅ curated |
| `index_bars` (CSI300) | 39 | 1 | 2026-08-03 → 2026-09-24 | ⚠️ 10.89% of window |

Lake size **0.39 GB** of a 187 GB free budget — no disk pressure at any point.

---

## 5. Immutability, pointers, and downstream gates

No snapshot was published, so no immutability question arises and **no `latest` production pointer was
created or overwritten**. No `candidate_latest` was invented.

```
SHADOW_EPOCH_CREATED = FALSE
VERIFIED_INDUSTRY_ETF_MAPPING = NONE
FORMAL_PORTFOLIO_NAV_PERFORMANCE = NONE
```

Even on a full pass, a Shadow epoch would remain forbidden: verified industry→ETF mapping, 20-day
liquidity admission and ≥5 distinct executable ETFs are all outstanding. The best attainable status
would be **DATA READY FOR MAPPING STAGE**, and it is not that either.

---

## 6. Exact next actions, in order

1. **Diagnose the adjustment-factor write path** so `cne derive adj_factors` emits a full per-symbol
   factor history (observe → hypothesise → test one variable → record). This is the only blocker.
2. Re-run the production adjustment audit and require **non-exact = 0**.
3. Re-run Source-C on the **full constituent denominator** and report the true
   `source_c_valid_count` plus per-industry and per-date distributions.
4. Compute factor readiness and H10/H40/H120 training readiness.
5. Extend CSI300 to 2025-04-10 (39 → 358 sessions).
6. Re-run the instrument backfill when the BSE board answers, to admit the 347 BJ instruments.
7. Only then build and independently verify the `PRODUCTION_CANDIDATE` snapshot.

---

## 7. Declaration

**NO SHADOW EPOCH WAS CREATED. NO FORMAL PORTFOLIO/NAV/PERFORMANCE WAS CREATED. NO VERIFIED
INDUSTRY→ETF MAPPING WAS CREATED. NO FORMAL TOP-5 ETF TARGET WAS CREATED. NO REAL MARKET DATA WAS
COMMITTED TO GIT.** No strategy parameter was changed. No coverage threshold was relaxed. No raw price
entered an industry return. The pinned upstream commit was not modified.
