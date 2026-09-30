# BJ TIP-SNAPSHOT PIT SEMANTICS v1

**Task:** ETF-Quant V1 — BJ historical production recovery.
**Base commit:** `1120f62a8914c4946dd089695d40e5c0528dac41`
**Contract:** [`BJ_TIP_SNAPSHOT_PIT_SEMANTICS_V1`]

---

## 1. Purpose

`adapters/bse/instruments.py::fetch_bse_instruments` reads the Beijing exchange's own board. That board
is a **current-state snapshot**, and this document fixes the interlock that governs its use so no tip
observation can ever be presented as a historical point-in-time fact.

---

## 2. The proven tip-only behaviour

Measured with five consecutive calls per date (all returned `complete=True`):

| Date queried | `board_names()` rows | `complete` |
|---|---|---|
| **2026-09-28** (`shanghai_today()`) | **347** | `True` |
| 2026-09-25 | **0** | `True` |
| **2026-09-24** (candidate cutoff) | **0** | `True` |

The board answers **only** for the current Shanghai date. Earlier sessions return an **empty success**.

### 2.1 Why `complete=True` with zero rows is the dangerous part

`board_names()` returns `(listed, complete)`. For a past date it returns `( {}, True )` — the shape of a
*successful, complete* read that happens to find nothing. A caller that honestly passes the candidate
cutoff therefore receives a **silently empty universe that asserts its own completeness**.

That is the exact mechanism by which the 355 BJ constituents left production coverage: the sweep asked
for the cutoff, was told "complete, nothing there", and wrote nothing. **Emptyness for a past date is
never evidence of absence.**

---

## 3. The contract

```
BSE_TIP_BOARD_IS_OBSERVATION_ONLY
```

| Allowed | Forbidden |
|---|---|
| current symbol code discovery | stamping `effective_at = 2026-09-24` |
| current exchange identity | stamping `observed_at = 2026-09-24` |
| current display name | stamping `known_at = 2026-09-24` |
| current code-mapping identity | stamping `list_date = 2026-09-24` |
| routing / candidate discovery | any other historical PIT claim |

### 3.1 Field semantics

| Field | Rule |
|---|---|
| `observed_at` | **always the real observation time** — `2026-09-28` |
| `effective_from` | **`UNKNOWN`** unless independent historical evidence establishes it |
| `effective_at` | may **never** be derived from a tip board read |
| `list_date` | the board's `hqssrq` is **null by upstream design**; a null is never filled from the observation date |
| `identity_back_stamped` | must be **`false`** in every published artifact |

---

## 4. What the tip board may NOT prove

| Claim | Status |
|---|---|
| the symbol was listed on 2026-09-24 | **not proven** |
| the symbol traded on 2026-09-24 | **not proven** |
| the symbol existed on any 2025 date | **not proven** |
| the symbol belonged to a given board then | **not proven** |
| the symbol was tradable then | **not proven** |

Each of those requires **historical** evidence: finalized bars, historical instrument metadata, or as-of
Shenwan membership.

---

## 5. What DOES prove historical existence

**Historical bars are the evidence of record.** A finalized bar for `(symbol, trade_date)` proves the
symbol had a real, market-recorded existence **on that date**.

The converse is explicitly rejected: a bar on date `t` does **not** prove the symbol was listed on any
earlier date, and its first observed bar is a *lower bound* on listing, never an exact listing date.

### 5.1 Membership is untouched by the tip board

Industry membership comes **only** from `TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE`. A tip board read may not
add, remove, or reclassify a constituent.

---

## 6. Application in this round

The 347 tip-board identities were used **solely** as current symbol-identity/routing discovery, and were
written with:

```json
{
  "identity_observed_at": "2026-09-28",
  "identity_back_stamped": false,
  "window": ["2025-04-10", "2026-09-24"]
}
```

Historical existence for those symbols was then established **independently**, by fetching real bars:
**346 of 347 returned bars** covering the production window (`920985.BJ` returned none). The candidate
cutoff remains **2026-09-24** and was never overwritten.

---

## 7. Tests

`tests/etf_quant/test_tip_snapshot_pit_safety.py` (synthetic only):

* a tip identity observed after the cutoff does **not** become a historical `effective_at`;
* a tip board row **cannot** establish historical listing;
* a historical bar **may** prove date-specific existence, and only for its own date;
* `identity_observed_at` is preserved through any matrix/snapshot projection;
* the candidate cutoff is not overwritten by a tip read;
* `list_date` is never populated from the observation date.

---

## 8. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
& "$EXT\venv\Scripts\python.exe" "$EXT\bj_admit.py"        # 347 rows at tip, 0 at cutoff
& "$EXT\venv\Scripts\python.exe" "$EXT\bj_ths_coverage.py" # 346/347 historical bar coverage
```
