# EXACT ADJUSTED HISTORY RECOVERY v1

**Task:** ETF-Quant V1 — long-run data completion + exact adjustment recovery.
**Base commit:** `92b2254b556074c5450d2860d27f5920fd12935e`
**Root cause:** [`cnequity_adjustment_factor_root_cause_v1.md`](cnequity_adjustment_factor_root_cause_v1.md)

---

## 1. Status

```
RECOVERY IN PROGRESS — monotonic, measurable, not yet drained
exact ratio: 0.132244 -> 0.770322
```

| Metric | Before | Current |
|---|---|---|
| `derived/adj_factors` rows | **334,417** | **1,789,893** |
| symbols with factors | 5,274 | 5,306 |
| **`adj_is_exact` TRUE** (production window) | **244,521** | **1,424,331** |
| `adj_is_exact` FALSE | 1,604,486 | **424,676** |
| **exact ratio** | **0.132244** | **0.770322** |
| realignment backlog | 4,728 symbols | **1,728 symbols** |

The production window is 1,849,007 bar rows over 358 sessions. Factor rows are converging on bar parity
(1,789,893 vs 1,849,007), which is the expected shape once the per-symbol daily history is present.

---

## 2. What was changed

| Step | Action |
|---|---|
| 1 | SHA-256 inventory of the 2,608 pre-existing derived factor files → `D:\QuantForge\temp\adj-factors-prehistory-backup\inventory.json` |
| 2 | `meta/state/adj_factors.json` (110,176 bytes) backed up verbatim |
| 3 | Removed **only** `derived/adj_factors/**` and its state file |
| 4 | Re-ran `cne derive adj_factors` (pinned CLI) |
| 5 | Drained the bounded realignment backlog with repeated passes, journaled per pass |

**Untouched:** all curated bars, all staged rows, membership, instruments, calendar, the manifest, and
every published revision. `adj_factors` is a `layer=derived` dataset — fully recomputable — so clearing
it destroys no source data.

---

## 3. Per-pass evidence

Journal: `D:\QuantForge\runtime\etf-quant-v1\data-to-shadow-ready\journal.jsonl`

| pass | rows before | rows after | delta | backlog | elapsed |
|---|---|---|---|---|---|
| opening | 334,417 | 550,097 | +215,680 | 4,728 | 294 s |
| 0 | 550,097 | 760,296 | +210,199 | 4,228 | 290 s |
| 1 | 760,296 | 972,479 | +212,183 | 3,728 | 289 s |
| 2 | 972,479 | 1,152,478 | +179,999 | 3,228 | 270 s |
| 3 | 1,152,478 | 1,352,305 | +199,827 | 2,728 | 288 s |
| 4 | 1,352,305 | 1,589,964 | +237,659 | 2,228 | 287 s |
| 5 | 1,589,964 | 1,789,893 | +199,929 | 1,728 | 288 s |

Each pass is bounded, resumable and individually recorded — the loop can be stopped and restarted
without losing completed work, and the watermark now advances with real history rather than hiding it.

---

## 4. Lookahead audit

| Check | Result |
|---|---|
| Factor join direction | **backward as-of** (`derive/adj_factors.py:279-291`) — a bar at `t` takes the factor at `t`, never a later one |
| Were future corporate actions applied to past dates? | **No** |
| Does the recovery admit older information? | Yes — and that is the correction: it was always available and simply never requested |
| Was `adj_is_exact` ever set by hand? | **No** — it is computed by the read path from factor presence |
| Was any raw close used as an adjusted close? | **No** — the read path still fills `factor=1.0` and flags it false |
| Was any factor interpolated or synthesised? | **No** |

The runtime message continues to report the residual honestly:

```
424676 bar row(s) missing adj_factors for adjust='hfq'; using factor=1.0 with adj_is_exact=False
```

---

## 5. Why the residual exists and what it means

After the backlog drains, the remaining non-exact rows are bars whose `(symbol, trade_date)` has no
factor row at all. These fall into two classes and **must be separated before any coverage claim**:

| Class | Meaning | Handling |
|---|---|---|
| `SYMBOL_FACTOR_SERIES_SHORTER_THAN_BARS` | the vendor series starts later than the bar history | the affected dates fall outside the warm-up window, or reduce that industry's coverage ratio |
| `SYMBOL_HAS_NO_FACTOR` | 199 symbols had zero factor rows before the fix | must be re-counted after the drain; any that remain are a genuine source gap |

Neither class may be resolved by relaxing the gate. The correct response is a per-symbol, per-date
enumeration feeding the industry coverage ratio, exactly as `INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS`
requires for BJ.

---

## 6. Success criteria

```
STRICT_ADJUSTMENT_GATE_PASS
  requires: every bar row that enters a production-relevant industry-date carries
            adj_is_exact = true.

Not required: mechanical 100% of all curated rows. A row that never enters any relevant
              industry-date is not a coverage failure — but it must still be enumerated and
              reported, never globally ignored.
```

**This has not yet been claimed.** The gate remains open until the backlog is drained and the residual
is enumerated per symbol.

---

## 7. Tests

`tests/etf_quant/test_adjustment_semantics.py` (synthetic fixtures only — no market data):

* tip-only factor table ⇒ every earlier bar is `adj_is_exact = false`
* full-history factor table ⇒ bars are `adj_is_exact = true`
* `strict_adj=True` raises on a missing factor and never substitutes raw
* the factor join is backward as-of; a bar cannot take a later factor
* clearing a derived watermark is not reachable from any path that also deletes curated or staged data

---

## 8. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
& "$EXT\venv\Scripts\python.exe" "$EXT\fix_factor_history.py"            # dry run + hashed backup
& "$EXT\venv\Scripts\python.exe" "$EXT\fix_factor_history.py" --apply    # clear tip watermark, re-derive
& "$EXT\venv\Scripts\python.exe" "$EXT\drain_factors.py" 12              # drain bounded backlog passes
```
