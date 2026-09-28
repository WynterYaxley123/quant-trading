# BJ HISTORICAL BAR ROUTING FIX v1

**Task:** ETF-Quant V1 — BJ official historical bar routing fix.
**Base commit:** `a2c7f6edb168501174208cae51e58aa86fbd62db`
**Verdict:** `RCA_COMPLETE` · `ROUTING_FIX_DESIGNED_NOT_INSTALLED` · `BJ_HISTORICAL_ROUTING_BLOCKED`

---

## 1. The complete source chain (proven, not guessed)

```
cne backfill daily_bars
  └─ steps/bars.py:853   tdx_symbols, fallback_symbols = split_by_quote_source(fetch_scope)
        └─ domain/symbols.py::is_tdx_servable("920000.BJ") == False
              → every Beijing symbol lands in fallback_symbols
  └─ steps/bars.py:909-934   the fallback lane
        bj_history = _fetch_bj_history_via_tdx(config, fallback_symbols, spec_start, spec_end, ...)
        sina_symbols = [s for s in fallback_symbols if s not in bj_history["covered"]]
        fallback = fetch_bars_via_sina(config, sina_symbols, spec_start, spec_end, ...)
```

**The Beijing lanes are TDX (market id 2) then Sina. THS is not in the routing path at all.**

`_gapfill_missing_keys_via_ths` (`steps/bars.py:2761`) is described in its own docstring as
*"Use THS only for exact keys still absent after cheaper batch routes"* — it supplements **absent keys**.
A symbol that already returned a tip row is therefore never re-examined, so the one adapter that holds
the full history is structurally unreachable for BJ.

---

## 2. Two hypotheses tested and rejected

| Hypothesis | Test | Result |
|---|---|---|
| **The requested range is wrong** (1 session requested) | `list_trading_dates(config, 2025-04-10, 2026-09-24)` | **REJECTED** — returns **358** sessions, `2025-04-10 … 2026-09-24`, exactly right |
| **THS has no BJ series** | `fetch_stock_bars("920000.BJ", …)` | **REJECTED** — **358 rows**, full OHLCV + `amount` |

So neither the range nor the source is at fault.

---

## 3. The self-defeating loop — why the TDX-BJ lane cannot work

`_fetch_bj_history_via_tdx` (`steps/bars.py:1466`) documents itself as *"Beijing daily history from TDX,
which serves it under market id 2"*, takes `(config, symbols, start, end, run_id, *, reserve_tip)`, and
persists by delegating to the official publisher:

```python
result = fetch_daily_bars_parallel(config, list(symbols), lo, hi, run_id, "daily_bars")
covered = _bj_history_covered(config, run_id, list(symbols), lo, hi) - failed
```

But `fetch_daily_bars_parallel` partitions through **`split_by_quote_source` again** — and that helper
routes Beijing to Sina. So the Beijing-history function hands its Beijing symbols to a function that
routes Beijing away from the Beijing lane. It then reports whatever Sina returned as `covered`.

That is the loop, and it fully explains the measurement:

| Observation | Explanation |
|---|---|
| 347 symbols, 347 rows | one tip session per symbol |
| every row `trade_date = 2026-09-24` | Sina answered the current session |
| `source = 'sina'` | the Sina fallback lane, not TDX and not THS |
| direct THS = **358 rows** for the same symbol | the data exists; the route never reaches it |

---

## 4. Why the fix was not installed

`_fetch_bj_history_via_tdx` returns `{"rows_read", "rows_written", "covered", "requested"}` and achieves
persistence **only** by delegating to `fetch_daily_bars_parallel` — the official staging + manifest
publisher. A drop-in replacement must reproduce that publication path exactly, including the run/batch
bookkeeping that `_bj_history_covered` reads back.

The two shortcuts were both refused:

| Shortcut | Why refused |
|---|---|
| write THS rows straight into `curated/` | bypasses the manifest and publication lifecycle — forbidden by the round's own rule |
| stage THS rows without the batch metadata | `covered` would be wrong, re-introducing the stale-batch blocker class the earlier rounds spent three rounds clearing |

The correct fix is to make the **partition** Beijing-aware — route BJ to a lane that uses the THS adapter
*and* publishes through `fetch_daily_bars_parallel`'s own machinery — rather than to replace the fetcher
underneath it. That change is localized but non-trivial, and it was **not made here rather than be made
unsafely**.

---

## 5. The designed contract

```
if exchange == BJ and a historical range is requested:
        fetch via  adapters.ths.stock_bars.fetch_stock_bars(symbol, start, end)
        publish via the official staging -> manifest -> compact lifecycle
        label     source = "ths"        (the truth; "sina" would corrupt
                                         _supplement_bse_tip_amounts' source-keyed heuristics)
elif exchange == BJ and only the tip is requested:
        unchanged -- the BSE snapshot still owns the tip
elif exchange in {SH, SZ}:
        byte-for-byte unchanged
```

Sina is **not** removed: it keeps the tip/snapshot role it is actually good at. Only the **historical
backfill** stops using a tip-only route.

---

## 6. Report (§80)

| Item | Value |
|---|---|
| old route | `_fetch_bj_history_via_tdx` → `fetch_daily_bars_parallel` → **Sina tip** |
| intended new route | BJ historical → **THS** (`fetch_stock_bars`), published officially |
| source-selection rule | `split_by_quote_source` → `is_tdx_servable(exchange)`; BJ is not TDX-servable |
| symbols tested | `920000.BJ`, `920001.BJ`, `920985.BJ`, `832317.BJ` |
| rows, direct THS adapter | **358** for `920000.BJ` and `920001.BJ`; **0** for `920985.BJ` and `832317.BJ` |
| rows, official pipeline | **1** per symbol (347 total), all `2026-09-24`, `source='sina'` |
| SH regression | **none** — `is_tdx_servable("600519.SH") == True`, lane untouched |
| SZ regression | **none** — `is_tdx_servable("000001.SZ") == True`, lane untouched |
| `BJ_HISTORICAL_ROUTING` | **BLOCKED** |

---

## 7. Minimal irreducible blocker (§87)

```
BJ_HISTORICAL_ROUTING_STILL_TIP_ONLY
  true root cause : split_by_quote_source sends BJ to the fallback lane; that lane is TDX -> Sina,
                    and THS is reachable only as a gap-fill for ABSENT keys, never for a symbol
                    that returned a tip row. _fetch_bj_history_via_tdx delegates back through the
                    same partition, so the BJ lane cannot serve BJ.
  code location   : steps/bars.py:853 (partition), :909-934 (fallback lane), :1466 (BJ TDX hook),
                    :2761 (THS gap-fill restricted to missing keys), domain/symbols.py::is_tdx_servable
  data evidence   : fetch_stock_bars("920000.BJ", 2025-04-10, 2026-09-24) -> 358 rows (live)
  runtime evidence: curated BJ = 347 rows / 347 symbols, all trade_date = 2026-09-24, source = sina
  affected symbols: 347 admitted BJ identities, 355 required BJ symbols
  affected ind.   : 72 of 162 industries; max BJ share 42.86% (2209); 6 industries >= 20% BJ
  affected dates  : 357 of 358 production sessions per BJ symbol
  safe alternatives attempted:
      1. board read at the historical cutoff -> empty with complete=True (tip-only). REJECTED.
      2. THS route on legacy codes          -> 0 rows. REJECTED (wrong code space).
      3. stamping tip identities to cutoff  -> FORBIDDEN by the PIT contract.
      4. accepting the 1-session result     -> REJECTED: it is a tip snapshot presented as history.
      5. direct curated write of THS rows   -> REFUSED: bypasses manifest/publication lifecycle.
  why bypass is unsafe: a direct write skips the manifest and the batch bookkeeping that
      _bj_history_covered and compact_allowed depend on, which is exactly the failure class the
      prior three rounds had to recover from.
  exact next decision required: whether the sidecar may make split_by_quote_source (or the
      fallback-spec construction at bars.py:857) Beijing-aware so BJ history is fetched from THS
      and published through fetch_daily_bars_parallel -- the smallest change that keeps the
      official lifecycle intact while giving the one adapter that has BJ history a route.
```

---

## 8. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
& "$EXT\venv\Scripts\python.exe" -c @"
import sys; sys.path.insert(0, r'$EXT\source\src')
from cnequity.domain.symbols import is_tdx_servable
print(is_tdx_servable('920000.BJ'), is_tdx_servable('600519.SH'))
"@
& "$EXT\venv\Scripts\python.exe" "$EXT\bj_ths_coverage.py"    # 346/347 full history via THS
```
