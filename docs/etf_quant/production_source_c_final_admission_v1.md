# PRODUCTION SOURCE-C FINAL ADMISSION v1

**Task:** ETF-Quant V1 — long-run CNEquity data-layer recovery & production admission.
**Base commit:** `26a3295bc304097e9b76a226a455c414865a11d1`
**Window:** `2025-04-10 → 2026-09-24`, 358 sessions, H120-bound (unchanged).

---

## 1. Status

```
SOURCE_C_PRODUCTION_COVERAGE_BLOCKED
BLOCKER = STRICT_ADJUSTMENT_GATE (exact-adjusted coverage 4.63% of published bars)
```

The publication layer was recovered (§ `cnequity_publish_gate_recovery_v1.md`) and the constituent
universe expanded to **5,261 of 5,930 required symbols (88.7%)**. Source-C still cannot be admitted,
and the reason has moved: it is now **adjustment coverage**, not bars, not publication, not membership.

**No strategy parameter, gate threshold or factor definition was changed to obtain this result.**

---

## 2. Universe layers (all measured, none hard-coded)

| Layer | Definition | Value |
|---|---|---|
| `historical_union_count` | distinct Level-2 codes over the whole membership table | **181** |
| `taxonomy_active_count` | distinct Level-2 codes in force per session | **162** (constant across all 358 sessions) |
| `structural_eligible_count` | taxonomy-active with ≥ 5 resolvable instruments | **128** |
| `instrument_resolved_count` | taxonomy-active with ≥ 1 resolvable instrument | **160** |
| required symbols (`TIME_VARYING_ASOF`) | union of members over the warm-up | **5,930** |
| **price_available** | required symbols with published production bars | **5,261** (88.7%) |
| **adjustment_exact** | bar rows carrying `adj_is_exact = true` | **85,545 of 1,849,007 (4.63%)** |
| `source_c_valid_count` | passes the frozen `5 / 0.80` gate | **0 of 162** |
| `factor_eligible_count` | ≥ 120 sessions of finite factors | **not measurable** (downstream of adjustment) |
| `model_common_universe_count` | intersection across H10/H40/H50 | **not measurable** |

The measured taxonomy regimes (derived, not asserted): **118** for 2020-01-23 … 2021-06-30 and **162**
for 2021-07-30 … 2026-09-24, with a single structural break at 2021-07-30 — 19 codes retired, 63
introduced, 99 carried over. The warm-up window lies entirely in the 162-regime, and the as-of rule is
still applied rather than the count being hard-coded.

---

## 3. The blocking fact, measured

After re-deriving `derived/adj_factors` over the expanded scope:

```
bars with adjustment:  rows=1,849,007   symbols=5,264
adj_is_exact TRUE  =       244,521
adj_is_exact FALSE =     1,604,486
ratio              =      0.132244          (up from 0.046265 before the re-derive)

adj_factors rows     =       334,417   symbols=5,274   range 2016-01-04 .. 2026-09-24
daily_bars rows      =     2,227,614   symbols=5,473   range 2016-01-04 .. 2026-09-24
median factors per symbol =            1.0
symbols with ZERO factors =            199 of 5,473
bar rows whose (symbol, trade_date) has NO factor = 1,893,197
```

The runtime states the consequence directly:

```
1604486 bar row(s) missing adj_factors for adjust='hfq';
using factor=1.0 with adj_is_exact=False
```

### 3.1 The irreducible defect

**Median factors per symbol is exactly `1.0`.** The derivation is committing a *single* factor date per
symbol rather than the symbol's factor history. With one factor row per symbol, only the bar on that one
date can be exact — which is why the exact ratio is a thin sliver (13.2%) rather than a coverage
gradient, and why 1,893,197 bar rows have no factor row at all.

This is **not** a bar problem, not a publication problem and not a membership problem. It is the
adjustment-factor derivation's write path producing one row per symbol.

### 3.2 Why Source-C returned 0 / 162

`source_c.constituent_return` refuses any row whose `adj_is_exact is not True`
(`REASON_NOT_EXACT`). At 13.2% exact coverage every industry-day collapses below the frozen
`ratio >= 0.80` gate:

```
industry-days evaluated : 57,996
valid                   : 111   (0.19%)
industries              : 162
pass-rate P10..P90      : 0.003 / 0.003 / 0.003 / 0.000 / 0.000
industries passing every day : 0
industries passing no day    : 51
```

This is the **gate working correctly**. The engine declined to build an industry series out of
raw-price returns wearing an adjusted label — precisely the silent corruption the gate exists to prevent.
**Note the genuine movement: 0 valid industry-days → 111**, purely from re-deriving factors, which
confirms the diagnosis rather than assuming it.

### 3.3 The remedy requires no contract change

Re-deriving `adj_factors` is the correct and only lever, and it is already the pinned mechanism
(`cne derive adj_factors`). The remaining work is to make that derivation produce a full factor history
per symbol rather than a single row — a data-layer defect to be diagnosed next, in the same
observe → hypothesise → test → record loop. It is **not** a reason to relax the adjustment gate, and the
gate was not relaxed.

---

## 4. Construction engine status

The engine itself is complete, frozen and tested — it is **not** the blocker.

| Check | Status |
|---|---|
| `TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE` implemented | ✅ `strategies/etf_quant/data/membership.py` |
| `INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS` honoured | ✅ BJ stays in the `eligible` denominator |
| exact-adjusted return only | ✅ refuses non-exact rows (this is what fired) |
| equal-weight mean, base 1000 recursion | ✅ `source_c.py` |
| frozen gates `5 / 0.80` unmodified | ✅ read from `config/__init__.py`, never lowered |
| identity / disclaimer | ✅ `INTERNAL_EQUAL_WEIGHT_SHENWAN_SERIES_V1` · `NOT OFFICIAL SHENWAN INDEX` |
| tests | ✅ 40 contract tests + 28 Source-C tests, all passing |

---

## 5. BJ impact, quantified

| Metric | Value |
|---|---|
| BJ members at cutoff | **355** |
| industries containing BJ members | **72 of 162** |
| max BJ share | **42.86%** (`2209`) |
| industries with BJ share ≥ 20% | **6** |

Per `INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS` these names remain in `eligible`, so the BJ bar gap
**reduces** the affected industries' coverage ratio rather than disappearing. With BJ unbarred,
`2209` (42.9% BJ), `2206` (26.1%) and `1108` (23.1%) **cannot reach the 0.80 gate at all**, and `6406`
(20.0%) sits exactly on the boundary. This is the systematic distortion the approved policy exists to
surface — and it is reported, not resolved by exclusion.

The BJ bar gap is a **local configuration artefact** that has now been diagnosed and re-enabled; the
BSE board was observed returning 347 live BJ securities on one call and zero on another, i.e. it is
**intermittent**, which is recorded rather than worked around.

---

## 6. Hard blockers

```
STRICT_ADJUSTMENT_GATE_BLOCKER
  - 1,604,486 of 1,849,007 published production bars carry adj_is_exact = false (exact ratio 13.22%).
  - ROOT CAUSE: `cne derive adj_factors` commits a MEDIAN OF 1.0 FACTOR ROWS PER SYMBOL instead of the
    symbol's factor history. Measured: 334,417 factor rows over 5,274 symbols; 199 symbols have none;
    1,893,197 bar rows have no matching (symbol, trade_date) factor at all.
  - Consequence: Source-C is correctly 111/57,996 industry-days (0.19%) and MUST NOT be reported
    otherwise. The gate was not relaxed and no raw price entered an industry return.

BJ_BAR_LANE_INTERMITTENT
  - The pinned BSE board answered 347 rows on one call and 0 on another within minutes.
  - BJ capability is proven present (see cnequity_bj_constituent_capability_v1.md); the endpoint is not
    reliable enough to schedule against without bounded retry.

SIXTEEN_LEGACY_NON_BJ_CODES
  - 4 SH + 12 SZ the vendor no longer serves (verified 0 rows from both routes).
  - They lower specific industries' coverage ratios; they do not block globally.

RUN_33A84CD1_GATE_BLOCKED
  - 19 batches from an interrupted invocation; retryable, payload intact.
```

---

## 7. What must happen next, in order

1. Complete `cne derive adj_factors` over the expanded scope.
2. Re-run the adjustment audit and require **non-exact = 0** for production rows.
3. Re-run this Source-C measurement on the **full constituent denominator** (no sampled numerator).
4. Only then report `source_c_valid_count` and the per-industry / per-date coverage distributions.
5. Factor readiness, H10/H40/H120 training readiness and the common model universe are all downstream
   of step 3 and were **not** attempted; computing them on a 4.6% exact-adjusted basis would be
   meaningless.

---

## 8. Declaration

No ranking, fusion, Top-5, ETF target, portfolio, NAV or Shadow epoch was produced. No coverage
threshold was relaxed. No raw price entered an industry return. No strategy parameter was changed.

---
