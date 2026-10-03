# PRODUCTION SOURCE-C ADMISSION v1

**Task:** ETF-Quant V1 — production data backfill + Source-C full coverage + production candidate snapshot.
**Base commit:** `58c551a03d3f4bf3cbb39172b3843bd2b6e942ec`

Read alongside [`production_backfill_execution_v1.md`](production_backfill_execution_v1.md), which
records why the curated bar set did not grow this round.

---

## 1. Status

```
SOURCE_C_PRODUCTION_COVERAGE_BLOCKED
```

The Source-C construction engine is **implemented, frozen and fully tested**, but it cannot produce a
production-coverage result because the stock bars it requires did not publish to the curated lake
(`CNEQUITY_PUBLISH_GATE_BLOCKER`). Running it against what *is* admitted would produce a number that
misrepresents coverage, so that was not done and no coverage figure is claimed.

---

## 2. The construction contract, as implemented

Identity: **`INTERNAL_EQUAL_WEIGHT_SHENWAN_SERIES_V1`** — **NOT OFFICIAL SHENWAN INDEX**.

| Step | Rule | Module |
|---|---|---|
| Daily membership | `TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE`: per symbol, the latest snapshot with `as_of_date <= session` | `strategies/etf_quant/data/membership.py` |
| Constituent return | `r = adj_close_t / adj_close_{t-1} - 1`, **only where `adj_is_exact is True`** | `source_c.py::constituent_return` |
| Industry return | arithmetic mean of valid constituent returns | `source_c.py::industry_date` |
| Chaining | `index_t = index_{t-1} × (1 + industry_t)`, base **1000.0** | `source_c.py::index_levels` |
| Invalid date | contributes **no** return and **holds** the previous level — never treated as 0 | `index_levels` |
| Gates (frozen) | `valid >= 5` **AND** `valid/eligible >= 0.80`, denominator = **full** membership | `config/__init__.py` |

### 2.1 Fail-closed behaviour, pinned by tests

| Condition | Reason recorded | Enters the mean? |
|---|---|---|
| `adj_is_exact` not `True` | `ADJUSTMENT_NOT_EXACT` | **No** |
| no close for the session | `NO_BAR` | No |
| no prior close (new listing / resumed halt) | `PREVIOUS_CLOSE_MISSING` | No |
| non-positive price | `NON_POSITIVE_PRICE` | No |
| non-finite value | `NON_FINITE_RETURN` | No |

`NO_BAR` and `PREVIOUS_CLOSE_MISSING` are deliberately **distinguished**: "this industry is thin" and
"these names have no prior session" call for different responses. Both are recorded per industry-date so
a low coverage ratio is always explainable.

### 2.2 Beijing constituents

`INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS` is honoured by construction: BJ symbols are part of `eligible`, so
a BJ name **without bars lowers the coverage ratio** rather than disappearing. `bj_coverage_impact`
quantifies that per industry, so the cost of the policy stays visible instead of reading as an
unexplained shortfall.

---

## 3. Why no coverage number is reported

| Requirement | State |
|---|---|
| Membership | ✅ admitted — 419,972 Shenwan rows, 81 snapshots, `2020-01-23 → 2026-09-24` |
| Exact adjustment engine | ✅ verified at scale — **85,545 / 85,545 `adj_is_exact`, ratio 1.000000**, `strict_adj=True` passed |
| Stock bars at required scale | ❌ **5,901 of 5,930 membership symbols have no published bars**; staged rows are blocked by the publish gate |
| Industry coverage gates | ⛔ **not measurable** — the `0.80` ratio denominator is full membership (up to 280 names) while only 251 membership symbols are published, so any ratio would be an artifact |

The previous round already demonstrated this failure mode honestly: a sample-scoped run reported a
**0.00%** gate pass rate that was purely a sampling artifact. Repeating that here would repeat the same
misleading number. **It is not repeated.**

---

## 4. Semantically distinct universe layers (§21)

These must never be collapsed into a single "universe = N" statement. Values are derived, never
hard-coded (`membership.py::taxonomy_counts` returns measured counts and labels them; it never branches
on them).

| Layer | Definition | Value |
|---|---|---|
| `taxonomy_active_count` | distinct Level-2 codes in force on the session | **162** (measured; constant across all 358 warm-up sessions) |
| `historical_union_count` | distinct Level-2 codes over the whole membership table | **181** |
| `structural_eligible_count` | taxonomy-active with ≥ 5 resolvable instruments | **128** |
| `instrument_resolved_count` | taxonomy-active with ≥ 1 resolvable instrument | **160** |
| `source_c_valid_count` | passes the frozen `5 / 0.80` gate | **NOT MEASURABLE** (§3) |
| `factor_eligible_count` | ≥ 120 sessions of finite factors | **NOT MEASURABLE** (§3) |
| `model_common_universe_count` | intersection across H10/H40/H120 | **NOT MEASURABLE** (§3) |

Also derived and reported separately: the measured taxonomy regimes are **118** (2020-01-23 …
2021-06-30, 18 sessions) and **162** (2021-07-30 … 2026-09-24, 63 sessions) with a single structural
break at **2021-07-30** — 19 codes retired, 63 introduced, 99 carried over.

---

## 5. Test evidence for the construction contract

`tests/etf_quant/test_source_c_construction.py` — **28 tests**, part of a suite of **210 passed /
1 skipped / 0 failed** in the frozen `quant-research:py3.12` image:

| Group | What is pinned |
|---|---|
| Return arithmetic | exact-adjusted return; equal-weight mean is arithmetic; a wild non-exact return cannot leak into the mean |
| Adjustment gate | non-exact, missing close, missing prior close, non-positive and non-finite each refuse to produce a return |
| Coverage gate | 5/5 passes; 4/5 fails the count gate; 8/10 passes at exactly 0.80; 7/10 fails; a mean is **not** published when the ratio gate fails |
| Level chaining | base 1000; compounds; an invalid date **holds** the level rather than contributing 0 |
| As-of membership | future snapshots never reach past sessions; a retired industry is absent later; the union is never used as a daily universe |
| BJ policy | BJ counts toward `eligible`; a BJ gap lowers the ratio; `bj_coverage_impact` reports it |
| Diagnostics | each exclusion reason is recorded and distinguishable |
| Identity | every emitted row carries `INTERNAL_EQUAL_WEIGHT_SHENWAN_SERIES_V1` and `NOT OFFICIAL SHENWAN INDEX` |

---

## 6. What remains to be done

1. Clear the publish gate (see the execution doc §6) so the 2,660,545 staged rows reach `curated`.
2. Re-run Source-C over the full as-of membership and the **full** constituent denominator.
3. Only then report `source_c_valid_count`, per-industry coverage distribution and per-date valid counts.
4. Factor warm-up and training readiness for H10/H40/H120 (§22, §23) are downstream of that and were
   **not** attempted — they would be meaningless on 4.2% of the constituents.

**No ranking, fusion, Top-5, target weight or portfolio was produced. No Shadow epoch was created.**

---

## 7. Hard blockers

```
SOURCE_C_PRODUCTION_COVERAGE_BLOCKED
  - 5,901 of 5,930 required membership symbols have no published curated bars.
  - The frozen 0.80 coverage gate is a fraction of FULL membership and is therefore not
    measurable on a partial constituent set; reporting it would repeat a known artifact.

HISTORICAL_CONSTITUENT_DATA_GAP (371 symbols)
  - 355 BJ members (see INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS: they stay in the denominator,
    so the gap is visible rather than silently thinning their industries).
  - 16 legacy SH/SZ codes the vendor no longer serves.
```

---
