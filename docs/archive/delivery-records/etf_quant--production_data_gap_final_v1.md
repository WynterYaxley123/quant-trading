# PRODUCTION DATA GAP FINAL v1

**Task:** ETF-Quant V1 — autonomous production completion.
**Base SHA:** `6ac7d1debaaff6cb0157ebb679c1c1517de2e532`
**Status:** `PARTIAL — phase 1/2 evidence gathered; matrix decomposition NOT completed`

> This document records **only verified findings**. Phases not reached are marked NOT RUN rather than
> given invented results.

---

## 1. Publication gate investigation (§25) — COMPLETE

`meta/manifest.db` currently holds **95 blocking batches**, not the 2 previously reported. The earlier
count was a per-`run_id` view; the lake-wide count is larger. They decompose into exactly three classes:

| Class | Count | Production impact |
|---|---|---|
| `compact` `status=warning` | **~72** | **NONE** — these are *compaction bookkeeping records*, not data batches. `rows_written` 0/55,043/121,273/135,235. They carry no symbols and no window. |
| `daily_bars` `status=failed`, `worker exited without finish_run` | **19** (run `33a84cd1`) | **NONE** — `rows_written=0`, superseded by later successful runs; the ~1,000 SZ symbols they cover were published by subsequent runs. |
| non-`daily_bars` metadata failures | **4** | **NONE for bars** — `industry_members` (proxy `Invalid port: ':1]'`), `instruments` ×2 (the pre-fix BSE-board failure), `trading_status` ×2 (`510300.SH` ambiguity). |

### 1.1 The one genuinely interesting entry

```
run=3f72a2b9  batch=2025-04-10_2026-09-23-batch-0  task=daily_bars  status=failed
symbols=1  window=2025-04-10..2026-09-23  rows_written=0
error: daily_bars: TDX returned no rows for 1 requested symbol(s): 920201.BJ
```

**`920201.BJ` has no historical bars from the Beijing TDX lane.** This independently corroborates
`§9`: the symbol carries `list_date = 2026-09-24` (exactly the candidate cutoff) **and** returns zero
history. Both facts point at the same conclusion — the identity exists on the tip board, but there is no
observable trading history, which is consistent with a **listing at/after the cutoff** or a code that was
never traded in the window.

### 1.2 Publication rule outcome (§26–27)

Per §26, no batch was force-settled: none of the 95 contains recoverable production rows. Per §27 they
are therefore **allowed to remain blocked**, with the justification above:
`NO_PRODUCTION_IMPACT`. No `fake success`, no hand-edited status, no direct curated write.

---

## 2. BJ `list_date` provenance (§9, §28–30) — ROOT CAUSE IDENTIFIED, CORRECTION NOT APPLIED

| Fact | Value |
|---|---|
| symbol | **`920201.BJ`** (万得) |
| stored `list_date` | **2026-09-24** |
| candidate cutoff | **2026-09-24** — **identical** |
| identity observation time | 2026-09-28 (routing registry, clean) |
| historical bars | **0** — `TDX returned no rows` |

### 2.1 Assessment

The equality of `list_date` and the cutoff, combined with zero historical bars, makes a genuine listing
date **unverifiable from any available source**. Per §29 the value must therefore **not** be treated as a
real listing date. The contamination sits in the pinned schema field `list_date`, which the sidecar
identity shim does not write — the registry entry for this symbol is clean
(`effective_from=UNKNOWN`, `identity_back_stamped=false`).

### 2.2 What was NOT done, and why

`list_date` was **not** nulled or overwritten. Changing it requires deciding whether the pinned
instruments merge should null any BJ `list_date` equal to the requested trade date, which affects the
whole merge path and needs its own test. Marking it unilaterally would be a bigger, less auditable change
than the evidence currently justifies. It is left **flagged as `LIST_DATE_UNVERIFIED`** for the next
round, and it does not affect Source-C (which never reads `list_date`).

---

## 3. Source-C gap decomposition (§33–34, §107) — **NOT RUN**

The 17,197 invalid industry-days were **not** decomposed by reason, exchange, symbol, industry or date in
this round. `PRODUCTION_CONSTITUENT_COVERAGE_MATRIX_V3` was not built. **No percentages are reported**,
because §107 forbids presupposed numbers and the measurement did not happen.

Known inputs for whoever runs it:

* Source-C after the BJ recovery: **40,799 / 57,996 (0.7035)**, 116 industries with ≥1 valid day
* whole-lake exactness: **1,943,621 / 1,943,979 (0.999816)**, the 358 non-exact rows being **only the CDR**
* curated: **1,943,979 rows / 5,611 symbols**, window `2025-04-10 → 2026-09-24`
* BJ: **94,972 rows / 347 symbols**, exact ratio **1.000000**
* known remaining unresolved scope: `832317`, `833874`, `833994`, `874090`, `920985`, `920157`,
  `920202`, `920305`, `920680`

**Since BJ is now fully exact, the residual 17,197 cannot be BJ-caused.** That is a *deduction from
measured facts*, not a decomposition, and it does not substitute for the matrix.

---

## 4. Honest status

| Phase | Status |
|---|---|
| §25 publication cleanup | **COMPLETE** (95 batches classified, 0 with production impact) |
| §28–30 list_date audit | **ROOT CAUSE FOUND**, correction deferred with reason |
| §31–35 constituent matrix + Pareto | **NOT RUN** |
| §36–41 recovery | **NOT RUN** |
| §43–45 Source-C recompute | **NOT RUN** (last measured 0.7035) |
| §46–55 factors / models | **NOT RUN** |
| §57–59 CSI300 | **NOT RUN** (last known 39/358) |
| §60–65 snapshot | **NOT RUN** |
| §66–87 mapping / liquidity / portfolio / T+1 | **NOT RUN** |
| §88–89 shadow readiness | **BLOCKED** — depends on every phase above |

No downstream gate is claimed as PASS on the strength of unrun work.
