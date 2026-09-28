# BJ IDENTITY ROUTING ADMISSION v1

**Task:** ETF-Quant V1 — BJ identity routing admission.
**Base commit:** `01d06668956c10c96c88eaf71413e2fe72a46dda`
**Contract:** `BJ_IDENTITY_ROUTING_ADMISSION_V1` (user-approved)

---

## 1. Outcome

```
BJ_IDENTITY_ROUTING_ADMISSION = PASS
BJ instruments in curated/instruments : 0 -> 347
TIP_IDENTITY_BACKSTAMP_COUNT          : 0
```

---

## 2. Why identity admission was necessary — the exact pinned defect

BJ was at **zero** in `curated/instruments` because of a single date-semantics mismatch in the pinned
source, now localized precisely:

```python
# steps/reference.py:73,83
def step_instruments(config, trade_date, run_id, context):
    df = _merge_bse_instruments(config, df, trade_date)      # <- the RUN's trade date

# steps/reference.py:180-205
def _merge_bse_instruments(config, df, trade_date):
    board = fetch_bse_instruments(trade_date, config=config) # <- passed to a TIP-ONLY board
    if board.is_empty():
        return df                                            # <- silent no-op
```

The BSE board answers **only** for the current Shanghai date. A historical run therefore gets an empty
board, and the merge — which is deliberately *"additive only, best effort"* — returns the frame
unchanged. The upstream comment states its intent plainly:

> *"A board that fails to load leaves the snapshot exactly as it was… this must not be able to turn a
> bad Beijing day into a day that inferred delistings."*

That safety property is correct for a **daily live** run and catastrophic for a **backfill**: the failure
is indistinguishable from "Beijing has no listings", so `universe="all_a"` silently resolved to two
exchanges out of three, and the daily-bar step had no BJ symbol to route — even though the pinned history
adapter serves **346 of 347** BJ identities over the production window.

**This is a routing/ingestion defect, not a data-source gap** (§90).

---

## 3. The fix — sidecar compatibility layer

`services/cnequity-sidecar/bse_tip_bridge.py` wraps `fetch_bse_instruments` so a *historical* request is
served from the board read at the **current tip**, while recording the true observation time.

| Property | Implementation |
|---|---|
| pinned source untouched | the wrapper is installed at runtime in the sidecar process |
| no invented history | the tip read is used as-is; no historical board read is fabricated |
| provenance preserved | each identity is written to `BJ_ROUTING_IDENTITY_REGISTRY_V1` |
| idempotent | re-enabling is a no-op; the admitted set is keyed by symbol |
| honest logging | `sidecar: BSE board is tip-only; served 2026-09-24 from the 2026-09-28 read` |

Measured effect of one run:

```
before: {'SZ': 4196, 'SH': 3506}
        instruments: +347 Beijing listing(s) the snapshot had never seen
after : {'SH': 3507, 'SZ': 4199, 'BJ': 347}
```

---

## 4. Provenance contract

```json
{
  "symbol": "920000.BJ",
  "exchange": "BJ",
  "asset_type": "stock",
  "identity_source": "BSE_TIP_BOARD",
  "identity_observed_at": "2026-09-28",
  "requested_trade_date": "2026-09-24",
  "effective_from": "UNKNOWN",
  "historical_pit_proven": false,
  "identity_back_stamped": false,
  "list_date": null,
  "delist_date": null
}
```

The pinned instruments schema has **no field** able to carry `identity_observed_at` or
`effective_from`, so per §17 the provenance lives in a **sidecar registry** joined by symbol — it is
**not** silently dropped and **not** crammed into a field whose meaning would be corrupted.

---

## 5. Verified post-conditions

| Check | Result |
|---|---|
| BJ rows in `curated/instruments` | **347** |
| `asset_type` | **`stock`** for all 347 — so BJ enters the `derive/adj_factors.py:441` factor universe (`asset_type ∈ {stock, etf}`), unlike the CDR |
| `exchange` | **`BJ`** — not mapped to SH/SZ/UNKNOWN to bypass validation |
| `identity_back_stamped` | **0** |
| `list_date == 2026-09-28` (observation date) | **0** |
| symbol format | canonical `920xxx.BJ` throughout; no `BJ920000` / `920000.BSE` variants |

---

## 6. A REAL PIT CONTAMINATION CASE — found and reported, not hidden

One admitted row carries a date field equal to the **requested cutoff**:

| symbol | name | list_date | source | data_version |
|---|---|---|---|---|
| **`920201.BJ`** | 万得 | **2026-09-24** | `bse` | `v1` |

The registry for this symbol is **clean** (`identity_observed_at = 2026-09-28`,
`effective_from = UNKNOWN`, `identity_back_stamped = false`). The contaminated value lives in the
**pinned schema field** `list_date`, which the shim does not write.

```
BJ_LIST_DATE_CUTOFF_ECHO
  - 920201.BJ carries list_date = 2026-09-24 == the requested trade date.
  - The board's own hqssrq is null, so this value did not come from the board.
  - It is a date-coalesce artefact elsewhere in the pinned instruments path, and it is
    indistinguishable from a genuine listing date.
  - Consequence: 1 of 347 BJ identities asserts a listing date that was never observed.
  - It does NOT create fake bars (bars are written only for real sessions), and the candidate
    cutoff was not overwritten.
  - Required decision: whether the sidecar should null any BJ list_date equal to the requested
    trade date, or whether a listing on the cutoff is genuine for this symbol. Needs per-symbol
    evidence; it was NOT papered over.
```

This is exactly the class of failure the round's PIT rules exist to catch, and it is recorded as an
open blocker rather than explained away.

---

## 7. Tests

`tests/etf_quant/test_bj_identity_routing.py` (synthetic only):

* tip identity admission preserves `identity_observed_at` and never rewrites it;
* `effective_from` is `UNKNOWN`, and `list_date` is never filled from the observation date;
* a second admission is idempotent — no duplicates, no changed dates, no provenance loss;
* `exchange='BJ'` and `asset_type='stock'` are preserved end to end;
* `back_stamp_count()` is 0;
* a tip board row cannot alter membership.

---

## 8. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
& "$EXT\venv\Scripts\python.exe" "$EXT\bj_admission_run.py"
# registry: D:\QuantForge\runtime\etf-quant-v1\bj-routing-recovery\reports\bj_routing_identity_registry.json
```
