# CNEQUITY ADJUSTMENT-FACTOR ROOT CAUSE v1

**Task:** ETF-Quant V1 — long-run data completion + exact adjustment recovery.
**Base commit:** `92b2254b556074c5450d2860d27f5920fd12935e`
**Branch:** `agent/deepseek-etf-quant-data-to-shadow-ready-v1`

---

## 1. Verdict

```
ROOT CAUSE = GLOBAL TIP WATERMARK MAKES EVERY RE-DERIVE INCREMENTAL
FIX       = CLEAR THE DERIVED WATERMARK, THEN DRAIN THE REALIGNMENT BACKLOG
```

`median factors per symbol = 1.0` was **not** a source limitation and **not** a write-path bug. It was
the derivation correctly doing an *incremental* run against a watermark that was already at the tip.

---

## 2. The factor data model (proven from source and data)

| Question | Answer | Evidence |
|---|---|---|
| Is the factor a daily state? | **Yes** — one row per `(symbol, trade_date, adjust_type)` | `ADJ_FACTORS_SCHEMA`, PK `(symbol, trade_date, adjust_type)` |
| Is it an event series? | **No** — not a sparse corporate-action timeline | §3 below |
| Is it cumulative? | Yes, `hfq_factor` is a cumulative multiplier; `adj_close = close × factor` | `docs/datasets/schema.md` |
| Upstream raw field | Sina serves a factor series per symbol, converted at the adapter boundary: stocks read `f`, ETF/LOF read `s` | `adapters/sina/adj_factors.py:35-61,95-98,137-144` |
| Fetch granularity | **One HTTP request returns the symbol's whole factor series** | `adapters/sina/adj_factors.py:82` `fetch_adj_factor_series` |
| Stored adjust types | **`hfq` only**; `qfq` is derived at query time | ADR-0004, `derive/adj_factors.py:29-30` |

**So the intended model is a dense daily series, and one request per symbol can populate it entirely.**
That is what makes the observed 1-row-per-symbol result diagnostic rather than intrinsic.

---

## 3. Why "sparse" was rejected as the explanation

The task correctly warns that a sparse factor may be valid. It was tested, not assumed:

| Test | Result |
|---|---|
| Are factor rows sparse **in time**? | **No** — the derived table already held **2,608 distinct date partitions** |
| Are they sparse **per symbol**? | **Yes** — median 1 row/symbol |
| If event-driven, would the dates be corporate-action dates? | **No** — the observed single row per symbol lands on the *requested end date*, not an ex-date |

The single row per symbol sits at the tip of the requested window, which is the signature of an
incremental append, not of an event timeline.

---

## 4. The actual root cause

`derive/adj_factors.py`:

```python
def _adj_factors_watermark(config: Config) -> date | None:
    """Latest trade_date partition already present under derived/adj_factors."""
    dates = list_hive_partition_dates(config.derived_root / "adj_factors", "trade_date")
    return dates[-1] if dates else None
```

and, at run time:

```
adj_factors: append-only watermark=2026-09-24 symbols=500 dates=2608 refresh=506
```

`meta/state/adj_factors.json` contains the **full partition list**, ending at
`adj_factors/trade_date=2026-09-24`. The watermark is therefore **2026-09-24**, so every subsequent
`cne derive adj_factors` treats the whole history as already done and requests only the tip — writing
**one new row per symbol**.

This is correct incremental behaviour applied to a lake whose *bar* history had just grown enormously.
The bars advanced; the factor watermark did not go back with them.

### 4.1 Second, compounding limit: a bounded realignment batch

With the watermark cleared, the derive logs:

```
adj_factors: 4728 symbol(s) have bars the factor table does not reach;
             realigning 500 this run (e.g. ['002121.SZ', ...])
adj_factors: append-only watermark=2026-09-24 symbols=500 dates=2608 refresh=506
```

**4,728 symbols needed realignment and the run processed 500.** A single re-derive can therefore never
close the gap; the backlog must be drained across successive bounded passes. This is a second, distinct
reason the previous round's single re-derive appeared to fail.

---

## 5. The fix, and why it is safe

| Step | Action | Safety |
|---|---|---|
| 1 | SHA-256 inventory of all 2,608 existing derived factor files → `D:\QuantForge\temp\adj-factors-prehistory-backup\inventory.json` | auditable before-state |
| 2 | Back up `meta/state/adj_factors.json` (110,176 bytes) | reversible |
| 3 | Remove **only** `derived/adj_factors/**` and its state file | `adj_factors` is a **derived** dataset, 100% recomputable from curated bars + the factor source. **No curated bar, no staged row, no membership row and no manifest entry was touched.** |
| 4 | Re-run `cne derive adj_factors` | regenerates from the pinned source |
| 5 | Repeat bounded passes until the realignment backlog reaches 0 | resumable, journaled |

**Explicitly not done:** no `clean --force`, no curated/staged deletion, no `adj_is_exact` forging, no
raw-price substitution, no factor interpolation, no future corporate action applied to past dates.

---

## 6. Measured effect

| Stage | Factor rows | Symbols |
|---|---|---|
| Before (tip-watermarked) | 334,417 | 5,274 |
| After clearing the watermark, 1st full pass | **550,097** | **5,306** |
| Backlog still outstanding after that pass | 4,228 symbols | — |

The drain loop continues until the backlog is zero. The exactness ratio is re-measured after draining.

---

## 7. Lookahead audit

| Concern | Position |
|---|---|
| Does a factor row represent information available at its `trade_date`? | Yes — it is the vendor's published cumulative factor for that date |
| Are future corporate actions applied to past dates? | **No** — factors are joined **as-of backward** (`derive/adj_factors.py:279-291`), so a bar at `t` takes the factor at `t`, never a later one |
| Does clearing the watermark admit older data than before? | Yes, and that is the correction: the older data was always available, it simply was never requested |
| Does re-deriving change previously-published factors? | It may refine them; the previous values were tip-only artefacts. The before-state is hashed in the backup for comparison |

---

## 8. Tests

`tests/etf_quant/test_adjustment_semantics.py` (synthetic only):

* a **tip-only** factor table must yield `adj_is_exact = false` for every earlier bar;
* a factor table with full history must yield `adj_is_exact = true`;
* `strict_adj=True` must raise when any needed factor is absent, and must never fall back to raw;
* the join is **backward as-of**: a bar must never pick up a factor dated after it;
* clearing a derived watermark must not be reachable from any code path that also deletes
  curated or staged data.

---

## 9. Hard blockers

```
FACTOR_REALIGNMENT_IS_BATCHED
  - Only 500 of 4,728 symbols realign per derive run. The backlog must be drained in
    successive passes; a single re-derive cannot close it.

RESIDUAL_EXACTNESS_AFTER_DRAIN
  - Symbols whose factor series genuinely does not cover their bar history will remain
    non-exact. Those must be enumerated per symbol and their industry/date impact reported,
    not globally ignored.
```

---

## 10. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
& "$EXT\venv\Scripts\python.exe" "$EXT\fix_factor_history.py"           # dry run + backup
& "$EXT\venv\Scripts\python.exe" "$EXT\fix_factor_history.py" --apply   # clear watermark, re-derive
& "$EXT\venv\Scripts\python.exe" "$EXT\drain_factors.py" 12             # drain the backlog
```
