# T+1 EXECUTION CONTRACT FINAL v1

**Contract:** `T_CLOSE_SIGNAL_NEXT_TRADING_SESSION_RAW_OPEN` — the signal is the
finalized close of session T; economic execution is the actual raw open of the
next trading session T+1. Evidence of that execution exists only after the T+1
final daily bar is available (≥ 15:05 Asia/Shanghai); bookkeeping is stamped
with the actual delayed processing time.

**Classification (required):** `DELAYED_T1_OPEN_ACCOUNTING`,
`NOT_REALTIME_EXECUTION_EVIDENCE`.

**Classification (as implemented, name mapping):**
`execution_price_source = FINALIZED_T1_RAW_OPEN`,
`accounting_mode = AUTHORIZED_DELAYED_EOD`,
`bookkeeping = DELAYED_EOD_ACTUAL_PROCESSED_AT`
(`strategies/etf_quant/runtime/shadow.py`, trade-record construction).

## 1. Required temporal inequality

```
economic_execution_at  <  evidence_available_at  <=  processed_at
(T+1 09:30 raw open)      (T+1 finalized bar           (actual delayed
                           ≥ 15:05 same day)            bookkeeping time)
```

Enforcement:

- `market_execution_at` is stamped as T+1 09:30 Asia/Shanghai; `processed_at` is
  the actual wall-clock bookkeeping time (`shadow.py` fill loop).
- A T+1 bar is evidence only when *finalized*: `data/tradability.py::is_finalized`
  rejects any bar observed before 15:05 on its own trade date — so
  `evidence_available_at <= processed_at` is structural, and
  `NOT_REALTIME_EXECUTION_EVIDENCE` is not a label but a gate.
- The read-only API re-validates every served trade:
  `intent_persisted_at < market_execution_at <= processed_at` and
  `executed_at === processed_at` (`services/etf-quant-api/server.mjs`),
  failing closed with `RUNTIME_INTEGRITY_BLOCKER` otherwise.

## 2. Tradability verdict (`ETF_BAR_DERIVED_TRADABILITY_V1`)

`data/tradability.py::evaluate` requires, in order: an execution session strictly
after the signal session (same-day execution is a lookahead and refused);
instrument admitted; the T+1 bar itself (any other date refused —
`T1_BAR_DATE_MISMATCH`; symbol mismatch refused); the bar finalized;
`open > 0`; `volume > 0`; `amount > 0` (null/NaN/zero fail closed — a real path
for Sina-sourced ETF rows). Otherwise `BLOCK` with a reason code. Substitution
with T+1 close, T+2 open or previous close is structurally impossible.

## 3. Cycle-level guarantees (`runtime/shadow.py`)

- T0 persists a sealed intent (`intent_id`, signal/execution dates, targets,
  mapping entries, hashes); no portfolio mutation at T0.
- T+1 re-verifies persisted-intent integrity
  (`PERSISTED_T0_INTENT_INTEGRITY_BLOCKER`), per-asset finalized T+1 bars
  (`T1_EXECUTION_BAR_BLOCKER`) and mapping continuity
  (`T1_MAPPING_CONTINUITY_BLOCKER`) before any fill.
- Fills are priced at the finalized T+1 raw **open** with lot rounding
  (lot 100, floor), sells-before-buys, frozen costs
  (commission 3bps / slippage 5bps / stamp duty 0).
- A missed T+1 is blocked, never replayed; epochs start only at the first real
  execution (`PRE_EPOCH_NAV_PROHIBITED`).
- Rebalance only when the executable ETF set changes
  (`EXECUTABLE_ETF_SET_CHANGE_ONLY`); weight-only drift is not a rebalance.

## 4. Verification status

| Layer | Evidence |
|---|---|
| Unit semantics | `tests/etf_quant/test_approved_data_contracts.py` (tradability clauses incl. fail-closed amount), `test_simulation.py` |
| Full T0→T+1 daily cycle | `tests/etf_quant/test_shadow.py` (8 tests) |
| API temporal re-validation | `services/etf-quant-api/tests/server.test.mjs` |
| Real-data execution | **NEVER RUN** — no shadow epoch exists; this audit certifies the machinery, not an execution |

**Verdict:** `T1_CONTRACT_PASS` (machinery certified by tests and code audit;
no formal signal, intent, fill, holding, NAV or performance was created).
