# BJ HISTORICAL ROUTING SINGLE-SYMBOL PROOF v1

**Task:** ETF-Quant V1 — BJ routing fix + single-symbol end-to-end proof.
**Base commit:** `65e7ba22cd67cc49be3f5307c35f1d19c03d27b4`
**Verdict:** `BJ_SINGLE_SYMBOL_E2E_PASS` · `BJ_HISTORICAL_ROUTING_PASS`

---

## 1. The root cause, isolated to one line

`domain/symbols.py:91`:

```python
TDX_EXCHANGES = frozenset({"SH", "SZ"})
```

`is_tdx_servable(symbol)` is `parse_symbol(symbol).exchange in TDX_EXCHANGES`, so **every** Beijing
symbol is judged un-servable by the TDX protocol and is pushed to the Sina fallback lane
(`steps/bars.py:853`).

**But TDX does serve Beijing, and the pinned source already says so.** Calling the protocol client
directly, bypassing the gate:

| Call | Result |
|---|---|
| `fetch_daily_bars(["920000.BJ"], 2025-04-10, 2026-09-24)` | **358 rows**, `2025-04-10..2026-09-24` |
| `fetch_daily_bars(["920001.BJ"], …)` | **358 rows** |
| `fetch_daily_bars(["600519.SH"], …)` | 358 rows *(control)* |
| `fetch_daily_bars(["000001.SZ"], …)` | 358 rows *(control)* |

Columns in every case: `open high low close volume amount`.

And `steps/bars.py:1466` `_fetch_bj_history_via_tdx` states its own reason for existing:

> *"Beijing daily history from TDX, which serves it under market id 2."*

So the pipeline contains a Beijing-history function built on a lane that its own gate excludes Beijing
from. `_fetch_bj_history_via_tdx` calls `fetch_daily_bars_parallel`, which partitions through
`split_by_quote_source` → `is_tdx_servable` → **False for BJ** → Sina.

**The gate was the bug, not the protocol, not the date range, not the source.**

---

## 2. The fix — `BEIJING_AWARE_QUOTE_PARTITION_V1`

`services/cnequity-sidecar/bj_quote_partition.py` adds `"BJ"` to the TDX-servable exchange set at
runtime, in the sidecar. The pinned checkout is untouched.

```
BJ  historical -> TDX protocol (market id 2), whole range in one call
BJ  tip        -> unchanged; the BSE snapshot still owns the tip
SH / SZ        -> byte-for-byte unchanged (same set membership)
```

It repairs the **partition** — the layer this round identified as the place that must change — and
leaves the fetcher alone, so the pinned `_fetch_bj_history_via_tdx` begins working exactly as designed
instead of being replaced.

Observed at run time:

```
PARTITION_FIX {'status': 'ENABLED', 'before': ['SH', 'SZ'], 'after': ['BJ', 'SH', 'SZ'],
               'probe': {'920000.BJ': True, '600519.SH': True, '000001.SZ': True}}
Beijing history via TDX: 1/1 symbol(s) answered over 2025-04-10..2026-09-23 (357 rows)
```

The line that previously read `0/1` now reads `1/1`.

---

## 3. Single-symbol end-to-end proof — `920000.BJ`

| Step | Result |
|---|---|
| curated **before** | **1 row**, `2026-09-24`, `source='sina'` |
| direct TDX reference | **358 rows**, `2025-04-10..2026-09-24` |
| official run (`cne backfill daily_bars`) | rc=0, 94 s |
| curated **after** | **358 rows**, `2025-04-10..2026-09-24` |
| sources after | `tdx_protocol` (history) + `sina` (tip session) |
| **`single_symbol_e2e`** | **PASS** |

### 3.1 Field equality against the direct adapter (§17)

358 overlapping dates compared field by field:

| Field | Differing rows |
|---|---|
| `open` | **0** |
| `high` | **0** |
| `low` | **0** |
| `close` | **0** |
| `amount` | **0** |
| `volume` | **1** |

The single `volume` difference is the **documented, expected** normalization at the tip session: TDX
reports volume in lots while the BSE snapshot publishes exact shares, and `_fetch_bj_history_via_tdx`
is explicitly written to `reserve_tip` so the current session keeps the BSE snapshot's exact figure.
`steps/bars.py:1466` records the same behaviour ("TDX reports it in lots… only from 2026 is Sina
finer"). **One row in 358, in the one field with a documented unit difference — every price and the
whole turnover series agree exactly.**

---

## 4. Second-symbol proof — `920001.BJ`

Identical in every respect, which rules out special-casing:

| Metric | `920001.BJ` |
|---|---|
| curated before | **1 row** |
| direct TDX | **358 rows** |
| curated after | **358 rows**, `2025-04-10..2026-09-24` |
| sources | `tdx_protocol` + `sina` |
| field equality | open/high/low/close/`amount` = **0 differing**; volume = 1 (tip) |
| **`single_symbol_e2e`** | **PASS** |

---

## 5. Publication path (§18) — no bypass, no regression

The rows travelled the **official** lifecycle: `fetch_daily_bars_parallel` → staging → batch metadata →
`_bj_history_covered` → settle → publish. Nothing was written to `curated` directly; no parquet was
hand-written; no SQL insert was issued; the manifest was not skipped.

The pinned `_fetch_bj_history_via_tdx` returned `covered = {920000.BJ}` and the batch settled
normally — **the stale-batch blocker class was not re-introduced**, because the fix changes *which
adapter answers*, not *how rows are published*.

---

## 6. Reports (§82, §83)

| Symbol | direct rows | official before | official after | range | source | PASS |
|---|---|---|---|---|---|---|
| `920000.BJ` | 358 | 1 | **358** | 2025-04-10 → 2026-09-24 | tdx_protocol + sina | **PASS** |
| `920001.BJ` | 358 | 1 | **358** | 2025-04-10 → 2026-09-24 | tdx_protocol + sina | **PASS** |

Machine-readable: `D:\QuantForge\runtime\etf-quant-v1\bj-full-recovery\reports\single_symbol_*.json`

---

## 7. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
# 1. prove the protocol serves BJ
& "$EXT\venv\Scripts\python.exe" "$EXT\tdx_bj_direct2.py"
# 2. single-symbol end-to-end through the official pipeline
& "$EXT\venv\Scripts\python.exe" "$EXT\bj_single_symbol_proof.py" 920000.BJ
& "$EXT\venv\Scripts\python.exe" "$EXT\bj_single_symbol_proof.py" 920001.BJ
```
