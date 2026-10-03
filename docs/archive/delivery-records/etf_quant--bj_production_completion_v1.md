# BJ PRODUCTION COMPLETION v1

**Task:** ETF-Quant V1 — long-run downstream completion to shadow-ready.
**Base commit:** `e8c2f2198784d108630ef2c55797b838db951b8e`

---

## 1. Verdict

```
BJ_CAPABILITY            = SUPPORTED (re-confirmed)
BJ_INSTRUMENT_COVERAGE   = 347 / 355 required
BJ_BAR_COVERAGE          = BLOCKED (instrument admission not yet written to the lake)
BJ_PRODUCTION_READY      = BLOCKED
```

---

## 2. THE ROOT CAUSE — the BSE board is a TIP snapshot, not a historical series

This resolves the prior round's "intermittent lane" finding, which was a **misdiagnosis**.

Measured directly, five consecutive calls for each date:

| Date queried | `board_names()` result | `complete` |
|---|---|---|
| **2026-09-28** (`shanghai_today()`) | **347 securities** | `True` |
| 2026-09-25 | **0** | `True` |
| 2026-09-24 (candidate cutoff) | **0** | `True` |

**The board answers only for the current Shanghai date and returns an *empty success* for any past
session.** It is not rate-limited, not flaky, and there is no cache or resolver defect. The earlier
"347 rows then 0 rows" observation is fully explained: the first call used the current date, the later
calls used the frozen cutoff.

### 2.1 Why this is dangerous and must be recorded

`board_names()` returns `(listed, complete)` with `complete=True` even when `listed` is empty for a past
date. A caller that honestly passes the **candidate cutoff** therefore receives a **silently empty
universe that reports itself complete**. That is the mechanism by which the 355 BJ constituents
disappeared from production coverage, and it will recur for any historical backfill that trusts the
`complete` flag without cross-checking the date against the tip.

```
BSE_BOARD_IS_TIP_ONLY
  - board_names(d) returns 347 rows for shanghai_today() and 0 rows with complete=True for any
    earlier session.
  - Empty is NOT evidence of absence for a past date.
  - Any historical BJ universe must come from the tip board plus the legacy->current code map,
    never from a board read at the historical date.
```

---

## 3. Required production set

`BJ_REQUIRED_PRODUCTION_SET_V1`, derived from `TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE` over the 358
production sessions (2025-04-10 → 2026-09-24) — **not** a hard-coded 355:

| Metric | Value |
|---|---|
| production sessions | 358 |
| **window-relevant BJ symbols** | **355** |
| resolved in `instruments` (before this round) | **0** |
| with bars (before this round) | **0** |
| **covered by the tip board** | **347** |
| **not covered by the tip board** | **8** |

### 3.1 The 8 uncovered symbols, classified

| Symbol | Class |
|---|---|
| `832317.BJ`, `833874.BJ`, `833994.BJ` | **legacy code space** — needs the `bse_code_mapping.json` legacy→current bridge |
| `874090.BJ` | **legacy code space** (NEEQ-select tier prefix) |
| `920157.BJ`, `920202.BJ`, `920305.BJ`, `920680.BJ` | current format, **absent from today's board** — listed after the cutoff, or delisted/suspended; requires per-symbol classification |

The 4 legacy codes are exactly the case the 248-entry mapping seed exists for. The 4 `920xxx` codes need
a listing-status check, because a symbol that listed *after* 2026-09-24 is correctly outside the window
and must be classified **`WINDOW_IRRELEVANT`** rather than treated as a gap.

---

## 4. Measurement detail

| Item | Value |
|---|---|
| BSE board rows at tip | **347** |
| `asset_type` | `stock` for all rows |
| `exchange` | `BJ` for all rows |
| `list_date` | **null** — the board's `hqssrq` comes back null, by upstream design |
| tip payload written to | `D:\QuantForge\runtime\etf-quant-v1\final-readiness\reports\bse_instruments_tip.parquet` |
| `[sources.bse].enabled` | **true** (verified in the production config) |
| failures / retries | **0** — no retry was needed once the correct date was used |

---

## 5. Configuration

```toml
[universe]
ingest = "all_a"          # admits the Beijing board; was "all_a_sh_sz"
```

`all_a_sh_sz` excluded BJ at the universe layer, which is why BJ never entered `instruments` even when
the board was reachable. With `all_a`, the pinned `instruments` step still requires an **active BJ**
reading to publish, and that reading must now be taken at the tip rather than at the frozen cutoff.

**Frozen research environment untouched** — this is the ETF-Quant sidecar config only.

---

## 6. Remaining gaps and the exact blocker

```
BJ_INSTRUMENT_ADMISSION_NOT_WRITTEN
  - The tip board yields 347 BJ instruments but the `instruments` step still refuses to publish,
    because it reads the board at the historical cutoff and therefore sees zero active BJ names.
  - root cause : BSE board is tip-only; instruments step passes the cutoff date.
  - fix path   : admit the tip-board instruments through the pinned instrument write path while
                 stamping them with the cutoff (identity is static; list_date is null from the board
                 anyway), OR run the instruments step with an explicit tip date.
  - NOT DONE   : requires writing to curated/instruments; not executed in this round.
  - unsafe to bypass : fabricating a historical board read would invent 347 names with unverifiable
                 listing dates. Taking the tip read is honest; inventing the past is not.

BJ_BAR_COVERAGE_UNMEASURED
  - No BJ bars exist yet, so BJ adjustment exactness and BJ session coverage are UNMEASURED.
  - BJ history must come from the Sina/BSE lane; the THS per-year history route has no BJ series
    by design (0 rows for 832317.BJ / 833874.BJ).

BJ_ADJUSTMENT_GAP
  - Per the task's own rule, bars being supported does NOT imply adjustment is supported.
  - Because no BJ bars exist, BJ exact-adjustment capability is UNVERIFIED and must not be claimed.
  - BJ_PRODUCTION_READY therefore remains BLOCKED regardless of the instrument result.
```

---

## 7. Industry impact (unchanged from the prior audit, still applicable)

| Metric | Value |
|---|---|
| BJ members | 355 |
| industries containing BJ members | **72 of 162** |
| max BJ share of one industry | **42.86%** (`2209`) |
| industries with BJ share ≥ 20% | **6** — `2209` 42.9%, `1109` 33.3%, `2206` 26.1%, `7703` 25.0%, `1108` 23.1%, `6406` 20.0% |

With BJ unbarred, `2209`, `2206` and `1108` cannot reach the 0.80 gate at all and `6406` sits exactly on
it. Under `INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS` these names stay in the denominator, so the effect is a
**visible coverage reduction**, never a silent drop.

The measured Source-C position with BJ unbarred is **39,657 / 57,996 valid industry-days (0.6838)** over
**113 of 162** industries — see [`cdr_689009_coverage_impact_v1.md`](cdr_689009_coverage_impact_v1.md).

---

## 8. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
& "$EXT\venv\Scripts\python.exe" "$EXT\bj_required.py"   # required set + board attempts
& "$EXT\venv\Scripts\python.exe" "$EXT\bj_admit.py"      # tip-board admission coverage
```
