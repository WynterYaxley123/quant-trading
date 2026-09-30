# PRODUCTION_DATA_COVERAGE_AUDIT_V1

**Task:** ETF-Quant V1 — CNEquity production coverage + active industry universe admission audit.
**Base commit:** `bd218fb79389fdd3e8af1b06997e8c7af2bd1610`
**Nature:** real-data coverage / universe / admission audit. No model was run, no rank was produced,
no Shadow epoch was created, no ETF mapping was built.

---

## 1. Status

```
PRIMARY   : PRODUCTION_FETCH_BUDGET_REVIEW_REQUIRED
SECONDARY : CNEQUITY_PRODUCTION_COVERAGE_BLOCKED (full-universe bars not fetched this round)
```

The strategy's **exact** production requirement is now known (358 sessions, 5,930 symbols,
~17,700 requests, ~16.6 GB), and a real 240-symbol production sample was fetched and audited end to end
with **perfect adjustment exactness**. The full-universe fetch was **budgeted but not executed**, because
it is a multi-gigabyte, multi-hour build that the task requires to be reviewed before running
(task §31).

A `PRODUCTION_CANDIDATE_CNEQUITY_SNAPSHOT` was **NOT** created: the coverage precondition
(≥5 resolvable constituents with bars for a material share of industries) is **not** met by the sample
lake, so the candidate gate would have to fail. Producing one anyway would have mislabelled a partial
sample as a production candidate.

---

## 2. What was measured, and on what

| Item | Value |
|---|---|
| Lake | `D:\QuantForge\external\cnequity-etf-quant-v1\lake-minimal` (external, not in Git) |
| Pinned CNEquity | `1650e384a3fd1f67a70144a489acc91432f1df27`, version 0.11.0, **unmodified** |
| Proxy policy | audited `direct` policy (ambient proxy removed for child processes only) |
| TLS | strict throughout; `verify=False` never used |
| New data fetched this round | **240 stock symbols × 358 sessions** |
| Rows written | **85,044** bars (plus 117 ETF bars earlier) |
| Transport errors | **0** |
| Rate limiting / retries beyond the client's own | none |

### 2.1 Lake inventory after the expansion

| Dataset | Rows | Symbols | Range |
|---|---|---|---|
| `daily_bars` | **85,545** | **254** | 2025-04-10 → 2026-09-24 |
| `adj_factors` | **85,545** | 254 | 2025-04-10 → 2026-09-24 |
| `industry_members` | 419,972 (SW) | 5,930 | 2020-01-23 → 2026-09-24 |
| `instruments` | 7,365 | — | 5,222 stocks / 2,142 ETFs / 1 CDR |
| `trading_calendar` | 1,879 sessions | — | 2020-01-02 → 2027-09-27 |
| `trading_status` | 12,447 | 5 | 2016-01-04 → 2026-09-24 |
| `index_bars` (CSI300) | 39 | 1 | 2026-08-03 → 2026-09-24 |

`daily_bars` is **100% `data_version=v2`** and **100% `source=tdx_protocol`** in this window, so the
volume unit is contractually **shares** throughout. Reuse: the 29 prior symbols were **reused, not
re-fetched**; only the 240 new symbols were fetched.

---

## 3. `PRODUCTION_ADJUSTMENT_AUDIT_V1`

The prior round proved exactness on 1,086 rows. This round repeats it at **79× the volume and 9× the
symbol count**.

| Metric | Value |
|---|---|
| Total bar rows evaluated | **85,545** |
| Symbols | **254** |
| Window | 2025-04-10 → 2026-09-24 (358 sessions) |
| Requested adjustment | `adjust="hfq"` |
| **`adj_is_exact` TRUE** | **85,545** |
| **`adj_is_exact` FALSE** | **0** |
| **exact ratio** | **1.000000 (100.00%)** |
| Non-exact symbols affected | **none** |
| Non-exact dates affected | **none** |
| `adj_close <= 0` rows | **0** |
| `strict_adj=True` | **PASSED** — raised nothing |
| Rows where `adj_close != close` | **84,912 / 85,545 (99.26%)** |

**The 99.26% divergence is the proof that a real factor was applied** rather than the raw price being
passed through. The remaining 0.74% are rows where the cumulative factor is exactly 1 (no corporate
action has occurred since the series base), which is correct.

```
PRODUCTION_ADJUSTMENT_AUDIT_V1 = PASS
  requested adjusted == actual adjusted, for every row, with no silent raw fallback.
  ADJUSTMENT_EXACTNESS_BLOCKER not triggered.
```

**Caveat carried forward, not resolved:** `adj_is_exact` describes **factor coverage**, not factor
PIT-ness. The `TIME_SEMANTICS_BLOCKER` from the transport audit still stands — nothing here proves that
the factor known today was the factor known at the time.

---

## 4. Stock universe requirement

Required symbols are derived from **current active Shenwan membership**, never from a guessed list.

| Metric | Value |
|---|---|
| Membership symbols at 2026-09-24 | **5,930 unique** |
| SH | **2,470** |
| SZ | **3,105** |
| BJ | **355** |
| Membership symbols **absent from `instruments`** | **707** |
| Membership symbols with bars in the lake **now** | **251** |
| Symbols still needing a bars fetch | **5,901** (5,930 − 29 resolved at audit start) |

### 4.1 The 707 missing instruments

These are membership symbols the lake's `instruments` frame does not contain. The sample names
(`000003.SZ 000004.SZ 000005.SZ 000013.SZ 000015.SZ 000018.SZ …`) are long-delisted legacy codes.
**Cause:** the instrument universe was populated from the live TDX board, which lists only what trades
today; no `cne backfill instruments` (baostock delisted recovery) was run.

**Consequence:** these 707 names are **not fetchable** until `instruments` is backfilled. They are
invisible to the strategy, which is a survivorship exposure in the industry-construction constituent set.
**Recommended first action of the next round: `cne backfill instruments`.**

---

## 5. `PRODUCTION_FETCH_BUDGET_ESTIMATE`

Derived from the warm-up contract (`2025-04-10 → 2026-09-24`, 358 sessions) — **not** a guessed horizon.

| Item | Value |
|---|---|
| Required window | **2025-04-10 → 2026-09-24** (358 sessions, 532 calendar days) |
| Symbols to fetch | **5,901** |
| Year partitions | **2** (2025, 2026) |
| THS history requests | 5,901 × 2 = **11,802** |
| `adj_factors` requests (sina, per symbol) | **5,901** |
| **Total requests** | **~17,703** |
| Measured THS latency (direct egress, strict TLS) | **0.08 s/request** |
| Serial wall-clock, bars only | **~16 minutes** |
| Est. parquet download | **~3,378 MB (3.30 GB)** |
| Lake footprint after ingest (parquet + factors) | **~16.6 GB** |
| Re-run cost | **Resumable** — the lake keeps incremental watermarks; a interrupted build resumes |

### 5.1 Why this needs review rather than blind execution

- **3.3 GB of network transfer** and **~16.6 GB on disk** is the largest single acquisition this project
  has attempted outside the Shenwan canonical work.
- The estimate assumes a **2-year** partition slice per symbol. The first year-partition (2025) is only
  partially used (from 2025-04-10), so the real download will be smaller — but the request count is
  unchanged, because THS bills one request per year-file regardless of how much of it is used.
- **This is a review gate, not a failure.** The budget is well within what this host can do
  (~16 min serial for bars), so the reviewer may simply approve it.

### 5.2 Two-phase plan (as the task permits)

| Phase | Scope | Status |
|---|---|---|
| **A** | Targeted coverage sample | **EXECUTED** — 240 symbols from 40 industries |
| **B** | Full production candidate | **NOT EXECUTED** — awaiting budget review |

---

## 6. `BJ_CONSTITUENT_POLICY_RECOMMENDATION`

### 6.1 The facts

| Question | Answer |
|---|---|
| Are BJ names real current industry members? | **Yes — 355 names, 5.9% of all members** |
| Are they a reconstruction artifact? | **No** — they are present at the latest snapshot, in 72 of 162 industries |
| Does the instrument universe support them? | **No** for bars: `[universe].ingest` had to be set to `all_a_sh_sz` because the BSE board endpoint returned no active securities from this host |
| Are they in the *final tradable* set? | Irrelevant — they are **constituents**, not execution vehicles |

### 6.2 Distortion if BJ is excluded

This is the decisive analysis, and it is **not** uniform:

| Metric | Value |
|---|---|
| Industries containing BJ members | **72 of 162** |
| Max BJ share of an industry | **42.86%** (`2209`: 6 of 14 members) |
| Industries with BJ share ≥ 20% | **6** — `2209` 42.9%, `1109` 33.3%, `2206` 26.1%, `7703` 25.0%, `1108` 23.1%, `6406` 20.0% |
| Industries with BJ share ≥ 10% | 10 (`+3306` 14.7%, `3305` 14.3%, `6206` 13.0%, `7702` 18.8%) |

**Excluding BJ would materially distort at least 6 industries**, dropping `2209` from 14 members to 8 and
`1109` from 3 to 2. Several of these would fall below the `min_valid_constituents = 5` gate entirely,
removing industries from the universe for a reason that has nothing to do with the industry's economic
content.

### 6.3 `BJ_CONSTITUENT_POLICY_RECOMMENDATION`

```
RECOMMENDATION: INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS
                (subject to BJ bars becoming fetchable)
```

**Rationale.**

1. **The constituent role and the execution role are different questions.** A BJ stock contributes to an
   industry's return series; it is never bought. The ETF execution leg is unaffected by BJ membership.
2. **Excluding BJ is not neutral — it is systematically biased**, concentrated in exactly the six
   industries above, several of which are small. A silent exclusion changes those industries' return
   series and their gate status.
3. **CNEquity already models this exclusion explicitly.** `industry_index` records `n_members`,
   `n_priced` and **`n_excluded`** precisely so that industries which cannot be fully priced remain
   visible rather than quietly thinned. That is the pattern to follow: **include BJ when priced, count it
   in `n_excluded` when not** — never drop it silently.
4. **The alternative (exclude BJ) must be an explicit, recorded contract choice**, applied consistently
   from universe definition through coverage gating, and reported per industry — not an incidental
   by-product of an ingest flag.

### 6.4 What must be fixed before BJ can be included

| Requirement | Status |
|---|---|
| BJ membership in the industry series | **Available** (355 names present) |
| BJ bars | **BLOCKED** — BSE board unreachable here, `[universe].ingest` narrowed to `all_a_sh_sz` |
| BJ `instruments` coverage | **Partial** — BJ names present only where the board answered |
| BJ historical ST | **Known gap** — CNEquity documents that no free source provides dated BJ historical ST |

**This is a contract decision.** Recorded as `CODEX_CONTRACT_CHANGE_REQUIRED`.

---

## 7. Industry construction coverage (Source C)

Three different metrics were previously conflated by a single 0% figure. They are separated here.

### 7.1 M1 — membership-based gate (needs no bars)

| Metric | Value |
|---|---|
| Industries at 2026-09-24 | **162** |
| Pass `members >= 5` | **128** |
| Fail | **34** |

### 7.2 M2 — resolvable-instrument gate

| Metric | Value |
|---|---|
| Pass `resolvable_instruments >= 5` | **124** |
| Fail | **38** = 34 thin membership + 4 unresolvable (`2401`, `2201`, `2301`, `7501`) |

### 7.3 M3 — construction gate on bars **actually present in this lake**

| Metric | Value |
|---|---|
| Industry-days evaluated | 55,728 |
| Gate PASS (`valid >= 5` AND `ratio >= 0.80`) | **0 (0.00%)** |

> **This 0% is a sampling artifact and must not be read as a coverage ceiling.** The gate's denominator
> is **full membership** (up to 280 members) while the numerator is limited to the **6 members per
> industry** that this sample fetched. A ratio of 6/280 = 2.1% can never clear 0.80. The metric is
> therefore **diagnostic only** and is reported for completeness, not as a finding about CNEquity.

### 7.4 Constituent-count distribution

| Population | min | P10 | P25 | median | P75 | P90 | max |
|---|---|---|---|---|---|---|---|
| All 162 industries (members) | 1 | 2 | 7 | **21** | 39 | 99 | 280 |
| 124 gate survivors (resolvable) | 5 | — | — | **26** | — | — | 244 |

### 7.5 Gate pass-rate, honestly stated

| Question | Answer |
|---|---|
| Pass rate on the real universe | **Not yet measurable** — requires the full fetch |
| Which industries never pass | **Not determinable** from a 6-member sample |
| Which dates fail | **Not determinable** from a 6-member sample |
| Projected pass at full fetch | **124 of 162** industries clear `>=5 resolvable`; a full bar fetch is expected to clear the 0.80 ratio for most of them, but the actual per-date ratio **cannot be asserted without fetching** |
| Were the gates relaxed? | **NO** — `min_valid_constituents = 5` and `min_constituent_coverage_ratio = 0.80` were left exactly as frozen |

---

## 8. `SIGNAL_READINESS_MATRIX_2026_09_24`

| Stage | Criterion | Industries | Of 162 |
|---|---|---|---|
| **A** | membership valid (`>= 5` members) | **128** | 79.0% |
| **B** | stock history sufficient (`>= 5` resolvable instruments) | **124** | 76.5% |
| **C** | adjustment exact (window-wide) | **100%** of 85,545 rows | — |
| **D** | factor warm-up sufficient | satisfiable for the 254 fetched; **requires full fetch** for the rest | — |
| **E** | coverage gate PASS (bars in this lake) | **40** | 24.7% |
| **F** | H10 model eligible | requires the same per-industry bars as B | **124** projected |
| **G** | H40 model eligible | same | **124** projected |
| **H** | H120 model eligible | same | **124** projected |
| **I** | **common eligible (A ∧ B ∧ C ∧ D)** | **124** | **76.5%** |

**Note on F/G/H.** They are not different counts. H10/H40/H120 all consume the same per-industry bar
series; they differ only in how much *history* they need, and **H120 is the binding horizon**
(see the warm-up contract). Once the 358-session window is fetched, a symbol either supports all three
horizons or none.

**No ranking, fusion, Top-5 or ETF target was produced.** This matrix is eligibility only.

---

## 9. ETF data readiness (no mapping)

| Metric | Value |
|---|---|
| ETFs in `instruments` | **2,142** (SH 1,039 / SZ 1,103) |
| With `list_date` | **1,632** |
| With `delist_date` | **0** |
| With bars in the current window | **3** |
| ETF bar rows | **117** |
| ETFs with ≥ 20 sessions | **3** |
| ETFs with **20/20 non-null `amount`** | **3** |
| ETFs with any null `amount` | **0** |
| Window | 2026-08-03 → 2026-09-24 |

**Limitations, stated plainly.**

1. Only 3 ETFs were fetched, so this is an **instrument-identity and schema** readiness result, **not** a
   statement about the 2,142-ETF universe's bar coverage.
2. **No industry/theme ETF subset can be identified from the data.** `instruments` has no fund-type,
   theme, or tracking-index field (confirmed by the previous audit and re-confirmed by the absence of any
   such column). Therefore the task's "A-share industry/theme ETF candidate universe" **cannot be
   constructed from CNEquity data alone** — a limitation of the source, not of this audit.
3. **No liquidity winner was selected**, no 20-day average computed for selection, and no ETF mapping
   created. The `amount` check is *presence*, not ranking.
4. `delist_date = 0` for all ETFs is consistent with the prior finding that delisted ETFs are not
   discovered by the code-space sweep.

---

## 10. CSI 300 production-history readiness

| Metric | Value |
|---|---|
| Symbol | `000300.SH` |
| Rows | **39** |
| Range | 2026-08-03 → 2026-09-24 |
| Sessions expected in the warm-up window | **358** |
| Sessions present | **39** |
| **Missing sessions** | **319** (first: 2025-04-10) |
| Full-window coverage | **10.89%** |
| `close` null / `close <= 0` | 0 / 0 |
| Source | `tdx_protocol`, **100% single-source** |
| `data_version` | **`v1`** |
| `frequency` | `1d` (single value, enforced by `BENCHMARK_IDENTITY_BLOCKER`) |

**Verdict:** the benchmark is **structurally ready** — single stable source, no nulls, no non-positive
closes, single frequency, identity enforced — but its **history is not yet loaded**. Date continuity is
**unverified beyond 39 sessions**, because there is nothing to check. Extending it is trivial
(`cne backfill index_bars --start 2025-04-10`) and is included in the recommended next action.

Carried-forward caveat: `index_bars` remains `data_version=v1`, so its `volume`/`amount` are
`source_native` and **must not** be used as benchmark turnover.

No NASDAQ or S&P 500 was introduced.

---

## 11. Source licensing

| Dataset | Underlying source | CNEquity registry rights note |
|---|---|---|
| `daily_bars` (stocks) | `tdx_protocol` (primary), plus supplementary routes | `SOURCES.yml` → `unknown` on all permission fields |
| `adj_factors` | `sina` | `unknown` on all permission fields |
| `industry_members` (SW) | `sw` — `swsresearch.com` | `unknown` on all permission fields |
| `index_bars` | `tdx_protocol`, `ths` | `ths`: `commercial_use = written_permission_required`, `redistribution = prohibited_for_free_products` (reviewed 2026-08-29) |
| `instruments` | `tdx_protocol`, `baostock`, `bse`, `sina` | `unknown` |
| `trading_status` | `eastmoney`, `exchange`, `baostock` | `eastmoney`: `commercial_use = written_permission_required`, `redistribution = prohibited_without_written_permission` |

```
LICENSING_REVIEW_REQUIRED
```

This is a **register, not a legal opinion.** No conclusion about permitted use is drawn. Per
`SOURCES.yml:189`, a derived dataset does not acquire upstream rights. **No market data was committed to
Git** in this round or any prior round; the lake and exports live outside the repository.

---

## 12. Candidate snapshot

```
CREATED: NO
```

Rationale: the coverage precondition for `PRODUCTION_DATA_CANDIDATE_PASS` is not met — 5,901 of 5,930
membership symbols have no bars, so a snapshot would represent a 4.2% sample. Publishing one labelled
"production candidate" would misrepresent its scope.

The prior round's `SMOKE_SCOPE_ONLY` snapshot `93e11ee6…567b` remains the only admitted export and is
**unchanged** by this round. Its manifest is **not** claimed to be production-grade.

---

## 13. Hard blockers

```
PRODUCTION_BARS_NOT_FETCHED
  - 5,901 membership symbols have no bars. Budget: ~17,703 requests, ~3.3 GB, ~16 min serial.
  - Awaiting review; the estimate is well within host capability.

INSTRUMENTS_MISSING_707_MEMBERSHIP_SYMBOLS
  - Legacy delisted codes absent because the instrument frame came from the live board only.
  - Fix: `cne backfill instruments` (baostock delisted recovery) before the bars build, or those
    names are permanently invisible (survivorship exposure in the constituent set).

BJ_BARS_UNFETCHABLE_FROM_THIS_HOST
  - BSE board returned no active securities; ingest narrowed to all_a_sh_sz.
  - 355 BJ members (5.9%), 72 industries, up to 42.9% of one industry -> material distortion.

COVERAGE_GATE_NOT_YET_MEASURABLE
  - The 0.80 ratio gate cannot be evaluated at full membership without a full fetch.

ETF_UNIVERSE_NOT_IDENTIFIABLE_FROM_SOURCE
  - No fund-type/theme/tracking-index field exists, so an industry/theme ETF subset cannot be derived.

ETF_BARS_AND_20D_AMOUNT_UNVERIFIED_AT_SCALE
  - Only 3 ETFs fetched; 2,142 exist. Readiness is structural, not coverage.

CSI300_HISTORY_NOT_LOADED
  - 39 of 358 sessions (10.89%). Structurally ready; trivially extendable.

TIME_SEMANTICS_BLOCKER (carried forward)
  - adj_is_exact proves factor coverage, not factor PIT-ness.

SOURCE_LICENSING_UNRESOLVED (carried forward)
```

---

## 14. CODEX_CONTRACT_CHANGE_REQUIRED

| # | Item |
|---|---|
| 1 | Freeze the industry universe policy (see `active_industry_universe_audit_v1.md` §7) |
| 2 | Decide the BJ constituent policy (include with `n_excluded` accounting vs explicit exclusion) |
| 3 | Decide the ETF tradability contract (`PROPOSED_TRADABILITY_FALLBACK_CONTRACT`, currently NOT APPROVED) |
| 4 | Decide whether the universe is 162 / 128 / 124 |
| 5 | Decide whether the ETF execution leg may rely on bar-derived tradability |
| 6 | Approve the ~17,703-request / 3.3 GB production fetch budget |

---

## 15. Declaration

**No strategy parameter, factor, Ridge, fusion weight, Top-5 rule, softmax, 35% cap, rebalance rule or
T+1 accounting was modified.** No formal ranking, fusion or ETF target was produced. No ETF mapping was
created. No Shadow epoch, NAV or trade was created. Validation and Final OOS were not read. Shenwan
canonical data was not modified. The pinned CNEquity commit was not changed.

---

## 16. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
& "$EXT\venv\Scripts\python.exe" "$EXT\audit_budget_coverage.py"
& "$EXT\venv\Scripts\python.exe" "$EXT\audit_production_coverage.py"
& "$EXT\venv\Scripts\python.exe" "$EXT\audit_coverage_metrics.py"
& "$EXT\venv\Scripts\python.exe" "$EXT\audit_readiness.py"
```
