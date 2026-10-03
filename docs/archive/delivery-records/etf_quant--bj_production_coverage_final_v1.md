# BJ PRODUCTION COVERAGE FINAL v1

**Task:** ETF-Quant V1 — BJ historical production recovery.
**Base commit:** `1120f62a8914c4946dd089695d40e5c0528dac41`
**PIT contract:** [`bj_tip_snapshot_pit_semantics_v1.md`](bj_tip_snapshot_pit_semantics_v1.md)

---

## 1. Verdict

```
BJ_HISTORICAL_BAR_SOURCE = PRESENT AND WORKING
BJ_BAR_COVERAGE          = 346 / 347 tip identities
BJ_PRODUCTION_READY      = BLOCKED  (ingest not yet written to the lake)
```

The decisive finding is a **correction of the prior round's conclusion**. BJ history is *not* a source
gap. It was misdiagnosed twice, and both causes are now identified precisely.

---

## 2. Two independent misdiagnoses, both corrected

### 2.1 "The THS route has no BJ series" — WRONG

The prior round tested `fetch_stock_bars` on **`832317.BJ`** and **`833874.BJ`** — both **legacy** code
space — saw 0 rows, and concluded the THS route excludes Beijing. The upstream comment it relied on says
北交所 is outside the *SH/SZ* history source, which is true of the SH/SZ endpoint, not of BJ routing.

Measured with **current** `920xxx` codes:

| Symbol | `fetch_stock_bars(sym, 2025-04-10, 2026-09-24)` |
|---|---|
| `920000.BJ` | **358 rows** — the full production window |
| `920001.BJ` | **358 rows** |
| `832317.BJ` (legacy) | **0 rows** |

Row shape is complete and usable:

```python
{'symbol': '920000.BJ', 'trade_date': '2025-04-10', 'open': 19.8, 'high': 21.45,
 'low': 19.68, 'close': 20.52, 'volume': 4501329, 'amount': 93134634.0}
```

**So the failure was the code space tested, not the source.**

### 2.2 "The BJ lane is intermittent" — WRONG

The BSE board is a **tip-only snapshot**. It answers 347 rows for `shanghai_today()` and `0` rows — with
`complete=True` — for any earlier date. It was never rate-limited, cached or flaky. See the PIT doc.

---

## 3. Required production set

`BJ_REQUIRED_PRODUCTION_SET_V2`, derived from `TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE` over the 358
production sessions — **not** a hard-coded 355:

| Metric | Value |
|---|---|
| production sessions | 358 |
| window-relevant BJ symbols | **355** |
| resolved in `instruments` (before) | **0** |
| with bars (before) | **0** |
| tip-board current identities | **347** |
| legacy / not on the tip board | **8** |

### 3.1 Code space

| Prefix | Required count |
|---|---|
| `920xxx` (current) | **351** |
| `832xxx` / `833xxx` / `874xxx` (legacy) | **4** |

98.9% of the BJ membership already carries **current** codes — which is precisely why the legacy-code
test produced a false negative for the whole exchange.

---

## 4. Historical bar measurement — 346 / 347

Every tip identity was fetched through the pinned THS route over `2025-04-10 → 2026-09-24`:

| Result | Count |
|---|---|
| **identities with historical bars** | **346** |
| identities with **0 rows** | **1** — `920985.BJ` |
| transport failures / exceptions | **0** |
| retries required | **0** |
| wall time | **102 s** for 347 symbols |

**Observed row counts span 1 … 358**, which is the *expected and healthy* shape: a name that listed
mid-window correctly has fewer sessions, and **no pre-listing rows are fabricated**. Names at 358 are
full-window participants.

### 4.1 What this proves, and what it does not

| Claim | Status |
|---|---|
| 346 BJ symbols have real, finalized bars in the window | **PROVEN** — by the bars themselves |
| 355/355 coverage | **NOT claimed** |
| `920985.BJ` has no history | **observed** — classified `BAR_SOURCE_GAP` pending per-symbol review |
| the 4 legacy codes map deterministically to current codes | **NOT yet proven** — `CODE_MAPPING_GAP` pending the 248-entry map check |
| BJ adjustment is exact | **NOT yet proven** — §5 |

Historical existence came **only** from bars (§5 of the PIT doc). The 2026-09-28 identity list was never
stamped to the cutoff.

---

## 5. BJ adjustment — still UNVERIFIED

**No BJ bars have been written to the lake, so BJ `adj_is_exact` is unmeasured.** Per the task's own
rule, bars being supported never implies adjustment is supported:

```
BJ_ADJUSTMENT_GAP = UNVERIFIED
  - Requires BJ bars to be ingested as asset_type='stock' so they enter the factor universe
    (derive/adj_factors.py:441 filters to stock/etf -- the same filter that excludes the CDR),
    then `cne derive adj_factors` must realign them through the already-repaired pipeline.
  - The repaired pipeline advances incrementally from the current watermark, so BJ-only realignment
    is possible WITHOUT clearing the recovered 2.2M-row factor table.
```

---

## 6. Exact remaining blocker

```
BJ_INGEST_NOT_WRITTEN
  root cause   : curated/instruments has zero BJ rows, so the pinned daily_bars step cannot route
                 any BJ symbol even though the BJ history source returns 346/347 successfully.
  source ev.   : adapters/ths/stock_bars.fetch_stock_bars -> 358 rows for 920000.BJ (verified).
  runtime ev.  : instruments table = 7,702 rows, exchanges SH 3,506 / SZ 4,196 / BJ 0.
  affected     : 347 BJ identities, 355 required BJ symbols.
  affected ind.: 72 of 162 industries; max BJ share 42.86% (2209); 6 industries >= 20% BJ.
  affected dates: all 358 production sessions.
  failed alternatives:
      1. board read at the cutoff          -> 0 rows, complete=True (tip-only). REJECTED.
      2. THS route on legacy codes         -> 0 rows. REJECTED (wrong code space).
      3. stamping tip identities to cutoff -> FORBIDDEN by the PIT contract.
  why bypass is unsafe: fabricating a historical board read would invent 347 names with unverifiable
       listing dates; back-stamping the tip would assert a 2026-09-24 fact that was never observed.
  exact next decision required: how the 2026-09-28-observed BJ identities should be admitted into
       curated/instruments for a 2026-09-24-cutoff candidate -- either (a) admit them with
       observed_at=2026-09-28 and effective_from=UNKNOWN, letting real bars prove existence, or
       (b) run the pinned instruments step with an explicit tip date parameter.
```

Option (a) is fully within this round's PIT contract, since bars — not the board — carry the historical
claim. It was **not executed**, because writing 347 rows into curated/instruments is a publication
decision that changes the constituent universe and should be taken deliberately.

---

## 7. Success criteria position

| Criterion | State |
|---|---|
| every production-relevant BJ has a clear outcome | **NOT YET** — ingests not written |
| bar valid / adjustment exact / return valid for numerator members | **UNMEASURED** |
| missing BJ constituents stay in the denominator | **contract preserved** |
| `BJ_PRODUCTION_READY` | **BLOCKED** |

Per §30, a missing BJ constituent is **not** a global blocker: it stays in `eligible`, is excluded from
`valid`, and the frozen `min 5` + `0.80` gate decides the industry-date. The industry impact is a visible
coverage reduction, never a silent drop.

---

## 8. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
& "$EXT\venv\Scripts\python.exe" "$EXT\bj_route_probe.py"     # which adapters exist
& "$EXT\venv\Scripts\python.exe" "$EXT\bj_ths_coverage.py"    # 346/347 historical coverage
# report: D:\QuantForge\runtime\etf-quant-v1\bj-to-shadow-ready\reports\bj_ths_coverage.json
```
