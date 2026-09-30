# BJ HISTORICAL ROUTING FULL BACKFILL v1

**Task:** ETF-Quant V1 — BJ routing fix + full BJ production backfill.
**Base commit:** `65e7ba22cd67cc49be3f5307c35f1d19c03d27b4`
**Prerequisite:** [`bj_historical_routing_single_symbol_proof_v1.md`](bj_historical_routing_single_symbol_proof_v1.md) — **PASS**

---

## 1. Verdict

```
BJ_SINGLE_SYMBOL_E2E_PASS
BJ_HISTORICAL_ROUTING_PASS
BJ_FULL_BACKFILL_PASS
BJ_ADJUSTMENT_PASS          (0 non-exact BJ rows)
```

Beijing went from **1 tip row per symbol** to a **real 358-session history**, through the official
lifecycle, with adjustment exactness measured rather than assumed.

---

## 2. What changed

| Stage | Before | After |
|---|---|---|
| BJ rows in curated (production window) | **347** (1/symbol, all `2026-09-24`, `sina`) | **94,972** |
| median rows per symbol | **1** | **358** |
| date range | `2026-09-24` only | `2025-04-10 → 2026-09-24` |
| `tdx_protocol` rows | 0 | **94,625** |
| `sina` rows | 347 | **347** (tip session only) |
| all-symbol curated rows | 1,849,007 | **1,943,979** |
| all-symbol curated symbols | 5,264 | **5,611** |

The `sina` count staying at exactly **347** is itself evidence the fix is surgical: Beijing's tip
session still comes from the BSE/Sina tip path, and only the **history** moved to TDX.

---

## 3. The fix that produced this

`services/cnequity-sidecar/bj_quote_partition.py` — `BEIJING_AWARE_QUOTE_PARTITION_V1`.

`domain/symbols.py:91` declares `TDX_EXCHANGES = frozenset({"SH", "SZ"})`, so
`is_tdx_servable("920000.BJ")` is `False` and every Beijing symbol is pushed to the Sina fallback lane
at `steps/bars.py:853`. The TDX protocol itself serves Beijing completely — measured directly at
**358 rows** with full OHLCV + `amount` — and the pinned `_fetch_bj_history_via_tdx` exists precisely
because *"Beijing daily history from TDX, which serves it under market id 2."*

The sidecar therefore widens the servable set by exactly one member, at runtime:

```
TDX exchanges  ['SH', 'SZ']  ->  ['BJ', 'SH', 'SZ']
probe          {'920000.BJ': True, '600519.SH': True, '000001.SZ': True}
```

No fetcher was replaced; the existing Beijing-history function now simply works as designed.

---

## 4. Publication path — official throughout

Every row travelled `fetch_daily_bars_parallel` → staging → batch metadata → `_bj_history_covered` →
settle → publish → compact → curated. **No direct curated write, no hand-written parquet, no SQL
insert, no manifest bypass.**

The backfill ran in 9 checkpointed chunks of ≤40 symbols. Several exited `rc=1`, which is the
**compaction gate deferring publication** (the established, expected behaviour — `daily_bars` had
non-terminal batches), not a fetch failure. Those runs were then settled and compacted with the
recovery pattern established in the earlier publication rounds:

| Recovery pass | Result |
|---|---|
| runs with blocking batches | 13 |
| compactions succeeded | **11** |
| still gate-blocked | 2 (`33a84cd1` 19 incomplete, `3f72a2b9` 1 incomplete) |
| rows published by those compactions | ~20.8 M across runs |

**No `clean --force`, no staged deletion, no manifest hand-editing.**

---

## 5. Full BJ report (§85)

| Metric | Value |
|---|---|
| BJ identities admitted | **347** |
| symbols with bars after backfill | **347** |
| total BJ rows | **94,972** |
| date range | `2025-04-10 → 2026-09-24` |
| median rows per symbol | **358** |
| min / max rows per symbol | **1 / 358** |
| zero-row symbols | **0** |
| symbols with < 5 rows | **41** |
| source distribution | `tdx_protocol` 94,625 · `sina` 347 |

### 5.1 The 41 low-row symbols — correct, not a defect

They are all **high `9202xx` codes** (`920185`–`920262`), i.e. names that listed late in the window.
A short history is the *expected* shape for a recent listing, and **no pre-listing row was
fabricated** (§32): the earliest bar for each of these equals its real first traded session.

Per §32 the requirement is not "358 rows per symbol" but "rows consistent with the real tradable
interval", and that is what the data shows.

---

## 6. BJ adjustment report (§87)

The adjustment pipeline was run **incrementally** — the existing 2,227,256 factor rows were reused, not
rebuilt (§39):

| Metric | Value |
|---|---|
| factor rows before | 2,227,256 |
| factor rows after | **2,322,228** |
| **delta** | **+94,972** — exactly the BJ bar count |
| symbols realigned | **346** |
| backlog after | **0 (DRAINED)** |
| **BJ bar rows exact** | **94,972** |
| **BJ non-exact rows** | **0** |
| **BJ exact ratio** | **1.000000** |

BJ ordinary equities carry `asset_type='stock'`, so they entered the factor universe
(`derive/adj_factors.py:441` filters to `stock`/`etf`) — the same filter that excludes the CDR.

### 6.1 Whole-lake exactness

| Metric | Value |
|---|---|
| production-window bar rows | 1,943,979 |
| exact | **1,943,621** |
| non-exact | **358** |
| **ratio** | **0.999816** |
| non-exact symbols | **1 — `689009.SH` (the CDR), unchanged** |

**BJ contributes ZERO non-exact rows.** The CDR remains the only exception, exactly as
`CDR_FACTOR_SUPPORT_DEFERRED` recorded, and it was not reopened.

Hard rules preserved throughout: backward as-of join, no future factor, no raw fallback, no
interpolation, no forged `adj_is_exact`.

---

## 7. Source-C before / after (§88)

| Metric | Before BJ | After BJ |
|---|---|---|
| valid industry-days | 39,657 | **40,799** |
| total industry-days | 57,996 | 57,996 |
| **valid ratio** | **0.6838** | **0.7035** |
| industries with ≥1 valid day | 113 | **116** |
| **restored** | — | **+1,142 industry-days, +3 industries** |

`INTERNAL_EQUAL_WEIGHT_SHENWAN_SERIES_V1` — **not** an official Shenwan index. Frozen gates unchanged:
`min_valid_constituents = 5`, `min_constituent_coverage_ratio = 0.80`.

### 7.1 Honest reading of the movement

The gain is **+1,142 industry-days (+2.0 points of ratio)**, which is smaller than the 355 BJ
constituents might suggest. That is expected and is not a failure: BJ names are a *minority* of the
`eligible` denominator in 66 of the 72 industries that contain them, so restoring them lifts the ratio
without flipping whole industry-dates. The three industries that crossed the gate are the ones where BJ
share was material.

Per §45 the BJ work must not be judged by a presupposed number — the measured result is reported as
found.

### 7.2 Remaining invalidity

`17,197` industry-days remain invalid. The dominant cause is **non-BJ constituent gaps**, since BJ now
contributes zero non-exact rows. The remaining unresolved scope is the legacy/absent codes
(`832317`, `833874`, `833994`, `874090`, `920985`, `920157`, `920202`, `920305`, `920680`) plus the SH/SZ
long tail — all of which stay **visible in the denominator**, never silently dropped.

---

## 8. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
& "$EXT\venv\Scripts\python.exe" "$EXT\bj_single_symbol_proof.py" 920000.BJ   # single-symbol PASS
& "$EXT\venv\Scripts\python.exe" "$EXT\bj_full_backfill.py"                    # chunked backfill
& "$EXT\venv\Scripts\python.exe" "$EXT\bj_recover_batches.py"                  # settle + compact
& "$EXT\venv\Scripts\python.exe" "$EXT\drain_factors.py" 20                    # incremental realign
```
