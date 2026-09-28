# BJ PRODUCTION INGESTION FINAL v1

**Task:** ETF-Quant V1 — BJ historical production ingestion.
**Base commit:** `01d06668956c10c96c88eaf71413e2fe72a46dda`
**Prerequisite:** [`bj_identity_routing_admission_v1.md`](bj_identity_routing_admission_v1.md) — **PASS**

---

## 1. Outcome

```
BJ_IDENTITY_ROUTING_ADMISSION   = PASS   (347 identities, 0 back-stamped)
BJ_OFFICIAL_HISTORICAL_INGESTION = INCOMPLETE  (1 session/symbol vs 346x full history available)
BJ_PRODUCTION_READY             = BLOCKED
```

The routing blocker is **solved**. A second, independent ingestion blocker is now exposed — and it is a
pipeline defect, **not** a data gap: the direct pinned adapter proves the history exists.

---

## 2. Required set

`BJ_REQUIRED_PRODUCTION_SET_FINAL`, derived from `TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE` over the 358
production sessions:

| Metric | Value |
|---|---|
| window-relevant BJ symbols | **355** |
| — current `920xxx` | **351** |
| — legacy `83xxxx` / `87xxxx` | **4** |
| admitted identities in `curated/instruments` | **347** |
| proven historical bars (direct pinned adapter) | **346** |
| zero-bar identity | **1** — `920985.BJ` |

The set is unchanged from the prior round's 355, and the reason is now demonstrable: the derivation is
the same as-of membership walk over the same 358 sessions, and the result is reproducible.

---

## 3. Identity admission — the routing fix worked

```
before: {'SZ': 4196, 'SH': 3506}
after : {'SH': 3507, 'SZ': 4199, 'BJ': 347}
instruments total: 7,702 -> 8,053
```

`instruments: +347 Beijing listing(s) the snapshot had never seen (920000.BJ, 920001.BJ, 920002.BJ)`

All 347 are `exchange='BJ'`, `asset_type='stock'` (so they enter the adjustment factor universe,
unlike the CDR). `identity_back_stamped = 0`.

---

## 4. Official ingestion — measured, and short

Three checkpointed batches through the **official** `cne backfill daily_bars` path:

| chunk | symbols | rc | status | rows_read | rows_written | elapsed |
|---|---|---|---|---|---|---|
| 0 | 120 | 0 | `success` | 120 | 120 | 88.5 s |
| 1 | 120 | 0 | `success` | 120 | 120 | 80.3 s |
| 2 | 107 | 0 | `success` | 107 | 107 | 79.3 s |

Those "rows" are **symbols**, not bar rows. The resulting curated content is the problem:

```
curated BJ rows: 347     symbols: 347
range: 2026-09-24 -> 2026-09-24
sources: ['sina']
```

**Every BJ symbol received exactly one session — the cutoff date — from the `sina` lane**, whereas the
direct pinned THS route returns **358 rows** for `920000.BJ` spanning the whole window.

### 4.1 The cross-check (§29) is decisive

| Route | `920000.BJ` over 2025-04-10 → 2026-09-24 |
|---|---|
| **direct pinned adapter** `adapters.ths.stock_bars.fetch_stock_bars` | **358 rows**, full OHLCV + amount |
| **official** `cne backfill daily_bars` | **1 row** (`2026-09-24`, `source='sina'`) |

The source demonstrably holds the history. The official path is not reaching it.

### 4.2 Why this is an ingestion bug and not a source gap

Per §90 the comparison is conclusive: the same pinned library, the same symbol, the same window, and a
337-row difference. The official path routed BJ to the **`sina`** lane and produced a single tip session,
which is the signature of a snapshot read rather than a historical sweep — and `sina` is exactly the lane
`domain/symbols.split_by_quote_source` assigns to BJ.

```
BJ_OFFICIAL_INGEST_ROUTES_TO_TIP_ONLY
  root cause (localized, not yet fixed):
    split_by_quote_source puts every BJ symbol on the non-TDX lane, and the official daily_bars
    step draws BJ history from `sina`, which yields one current session instead of the window,
    while the pinned THS adapter -- which returns the full 358-row history for the same symbol --
    is not consulted for BJ.
  source evidence : fetch_stock_bars('920000.BJ', 2025-04-10, 2026-09-24) -> 358 rows (live)
  runtime evidence: curated BJ = 347 rows / 347 symbols, all trade_date = 2026-09-24, source = sina
  affected        : 347 admitted BJ identities, 355 required BJ symbols
  affected ind.   : 72 of 162 industries; max BJ share 42.86% (2209); 6 industries >= 20% BJ
  affected dates  : 357 of 358 production sessions per BJ symbol
  failed safe alternatives:
      1. board read at the historical cutoff -> empty, complete=True (tip-only). REJECTED.
      2. THS route on legacy codes          -> 0 rows. REJECTED (wrong code space).
      3. stamping tip identities to cutoff  -> FORBIDDEN by the PIT contract.
      4. treating the 1-session result as sufficient -> REJECTED: it is a tip snapshot, and
         accepting it would present 347 tip bars as a 358-session history.
  why bypass is unsafe: writing THS rows directly into curated would bypass the manifest,
       publication and adjustment semantics that the rest of the lake depends on; and back-filling
       from a tip read would fabricate sessions that were never observed.
  exact next decision required: how BJ history should be routed to a history-capable adapter in
       the official daily_bars step -- whether by teaching the BJ lane a historical window, or by
       admitting the THS BJ route as the BJ history source in the sidecar.
```

---

## 5. Zero-bar and legacy symbols

| Symbol | Status |
|---|---|
| `920985.BJ` | tip identity exists; **0 bars** from the direct adapter → `BAR_SOURCE_GAP` pending a listing check |
| `832317.BJ` | legacy; direct adapter returns **0 rows** → needs the 248-entry legacy→current mapping before any conclusion |
| `833874.BJ`, `833994.BJ`, `874090.BJ` | legacy, same treatment |
| `920157.BJ`, `920202.BJ`, `920305.BJ`, `920680.BJ` | current-format but absent from the tip board → listing-status classification still required |

**The legacy codes must not be retried as-is** (§24). The prior round's false negative came from exactly
that mistake, so no legacy code is ever queried directly again without a proven mapping.

---

## 6. The PIT contamination found during admission

`920201.BJ` carries `list_date = 2026-09-24` — the requested cutoff — while its provenance registry entry
is clean. This is a date-coalesce artefact in the pinned instruments path, is **indistinguishable from a
real listing date**, and is reported as `BJ_LIST_DATE_CUTOFF_ECHO` rather than explained away.

---

## 7. Post-conditions

| Check | Result |
|---|---|
| BJ identities routed | **347** ✅ |
| BJ bars available for the production window | **1 session of 358** ❌ |
| BJ adjustment exactness | **UNMEASURED** — requires real history first |
| missing BJ constituents stay in the denominator | **contract preserved** |
| pre-listing rows synthesised | **none** — only real observed sessions were written |
| `BJ_PRODUCTION_READY` | **BLOCKED** |

---

## 8. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
& "$EXT\venv\Scripts\python.exe" "$EXT\bj_admission_run.py"    # identities 0 -> 347
& "$EXT\venv\Scripts\python.exe" "$EXT\bj_ths_coverage.py"     # direct adapter: 346/347 full history
```
