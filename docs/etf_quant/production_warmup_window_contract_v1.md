# PRODUCTION_WARMUP_WINDOW_CONTRACT_V1

**Task:** ETF-Quant V1 — CNEquity production coverage + active industry universe admission audit.
**Base commit:** `bd218fb79389fdd3e8af1b06997e8c7af2bd1610`
**Method:** derived from the **frozen** strategy logic and the **real** CNEquity trading calendar.
No parameter was changed and no assumption about "one year" or "two years" was made.

---

## 1. Inputs (all measured, none assumed)

| Input | Value | Source |
|---|---|---|
| Horizons | H10 / H40 / H120 trading days | `research/horizon_component_replacement_v1_protocol.py:44` |
| Rolling training window | **6 calendar months** | `spec.md:169`; `temporal_integrity.temporal_boundaries(train_months=6)` |
| Minimum valid training days | **30** | `spec.md:172` (`min_train_dates = 30`) |
| Longest factor lookback | **120 sessions** (`d120`, `p120`) | `factors/sector_rotation.py:66-67` |
| Target maturity | label at `calendar[pos(t) + fwd]` | `temporal_integrity.make_forward_label` |
| Trading calendar | **1,879 sessions**, `2020-01-02 → 2027-09-27` | real CNEquity `trading_calendar` in the lake |

### 1.1 The frozen purge rule (verbatim semantics)

`strategies/sw_sector_rotation/src/common/temporal_integrity.py:240-242`:

```python
label_cutoff = cal[pred_pos - forward_days]
realized_end = cal[pred_pos + forward_days] if pred_pos + forward_days < len(cal) else None
train_start = label_cutoff - pd.DateOffset(months=train_months)
```

> `label_cutoff = calendar[pos(S) − fwd]` — the last training date whose `fwd`-day forward label is
> **already realized** on the signal date `S`. Training uses `[train_start, label_cutoff]`.

This is the purge. It is exact and involves no approximation.

---

## 2. Required history per horizon

Signal date **S = 2026-09-24**, calendar position **1632** of 1,879.

| Horizon | `label_cutoff` = `cal[pos−fwd]` | calendar pos | `train_start` = `label_cutoff − 6 months` | sessions in `[train_start, label_cutoff]` |
|---|---|---|---|---|
| **H10** | 2026-09-10 | 1622 | **2026-03-10** | 128 |
| **H40** | 2026-07-30 | 1592 | **2026-01-30** | 119 |
| **H120** | 2026-04-02 | 1512 | **2025-10-02** | **118** |

Every window clears the 30-minimum-valid-days requirement with large margin (118–128 sessions), so the
minimum-days rule is **not** the binding constraint — **the 120-session factor lookback is**.

---

## 3. Factor warm-up: why bars must start earlier than `train_start`

Every feature must be computable at the **first** training date. The longest lookback is 120 sessions
(`d120`, `p120`), and `dd60`/`rsi` are shorter. A rolling-120 statistic needs 120 prior observations, so
the **first stock bar must precede the first feature date by 120 sessions**.

| Horizon | earliest feature date (= `train_start`) | −120 sessions ⇒ earliest **stock bar** date |
|---|---|---|
| H10 | 2026-03-10 (pos 1495) | 2025-09-03 |
| H40 | 2026-01-30 (pos 1474) | 2025-08-05 |
| **H120** | **2025-10-02** (pos 1395) | **2025-04-10** (pos 1275) |

The **binding** horizon is **H120**, because its `label_cutoff` is the furthest back and therefore its
`train_start` — and hence its factor warm-up — is the earliest.

---

## 4. `2026-09-24_SIGNAL_HISTORY_REQUIREMENT`

Binding horizon **H120**:

| Requirement | Value | Basis |
|---|---|---|
| **required earliest feature date** | **2025-10-02** | H120 `train_start` |
| **required earliest stock bar date** | **2025-04-10** | `train_start` minus 120 sessions |
| **required earliest membership date** | **2025-10-02** | membership must be resolvable at the first training date |
| **required label maturity** | labels on `[train_start, label_cutoff]` = `[2025-10-02, 2026-04-02]` must be realized by S | `label + 120 ≤ S` |
| **minimum trading-session span** | **358 sessions** | from `2025-04-10` to `2026-09-24` inclusive |
| **minimum calendar span** | **532 days (1.46 years)** | real dates, not rounded |

### 4.1 Cross-check of the 358-session figure

`S` is at position 1632; `2025-04-10` is at position 1275. `1632 − 1275 + 1 = 358`. ✔

### 4.2 Is the CNEquity membership floor sufficient?

| Check | Value |
|---|---|
| Required earliest membership date | **2025-10-02** |
| CNEquity Shenwan membership floor | **2020-01-23** |
| Sufficient? | **YES** — with **2,079 days (≈5.7 years) of margin** |

So the **2020 membership floor does not constrain the current signal date**. It *would* constrain a
signal date before roughly `2020-10` (which needs `train_start − 6 months` ≥ 2020-01), which is also
before the 2021-07-30 code-space break — another reason the effective research window is comfortably
inside the modern classification regime.

---

## 5. Resulting production fetch requirement

| Item | Value |
|---|---|
| Bar window to fetch | **2025-04-10 → 2026-09-24** |
| Sessions | **358** |
| Calendar span | 532 days |
| Year partitions touched | **2025, 2026** (2 per symbol) |
| Membership snapshots in window | ~12 monthly snapshots |

### 5.1 Why 358 sessions and not "about a year"

A naive `S − 120 trading days` would give `2026-04-02` and **omit the entire factor warm-up**, producing
all-NaN `d120`/`p120` at the first training dates and silently shrinking the effective training set.
A naive `S − 6 months` would give `2026-03-24` and omit both the purge offset and the warm-up. The correct
figure is **358 sessions / 532 calendar days**, and it is larger than either naive estimate.

### 5.2 Minimum-history table for other signal dates

The requirement scales with `S`. For any signal date, the binding rule is:

```
earliest_stock_bar(S) = calendar[ pos(S) − 120 − fwd_binding − (sessions in 6 months) − 120 ]
```

which for the current calendar reduces to approximately:

| Signal date | required earliest stock bar |
|---|---|
| 2026-09-24 | 2025-04-10 |
| 2026-12-31 | 2025-07-15 (approx.) |
| 2027-03-31 | 2025-10-10 (approx.) |

Approximate rows are marked as such; only the `2026-09-24` row is measured here.

---

## 6. Contract summary

```
PRODUCTION_WARMUP_WINDOW_CONTRACT_V1
  signal_date                      : 2026-09-24
  binding_horizon                  : H120
  required_earliest_feature_date   : 2025-10-02
  required_earliest_stock_bar_date : 2025-04-10
  required_earliest_membership_date: 2025-10-02
  required_label_maturity_window   : 2025-10-02 .. 2026-04-02  (all realized by S)
  minimum_trading_session_span     : 358
  minimum_calendar_span_days       : 532
  factor_warmup_sessions           : 120
  purge_offset_sessions            : 120 (H120)
  training_window                  : 6 calendar months, 118 sessions for H120
  min_valid_training_days_required : 30   (satisfied: 118 >= 30)
```

---

## 7. Consequences for the coverage build

1. **Do not fetch from 2020.** The strategy needs **only** `2025-04-10 → 2026-09-24`. Fetching from the
   membership floor would multiply the request budget by ~4.7× for data the frozen model never reads.
2. **Do not fetch a single calendar year.** 2025-04-10 → 2026-09-24 spans two year-partitions; a
   one-year build starting 2025-10 would leave the first ~120 sessions of warm-up missing.
3. **Membership needs only 12 snapshots**, not the full 81.
4. **The 30-day minimum is not binding.** Any build that satisfies the 358-session requirement
   automatically satisfies it.

---

## 8. Hard blockers

```
WARMUP_WINDOW_IS_H120_BOUND
  - H10/H40 need only 2025-09-03 / 2025-08-05 of bars; H120 needs 2025-04-10.
  - A build sized to H10 or H40 alone would silently starve the H120 model.

LABEL_MATURITY_NOT_STORED
  - Nothing in the lake proves that a given label was realized by S; the purge is asserted structurally
    by the consumer via the trading calendar (the frozen code already does this correctly).
  - Consistent with TIME_SEMANTICS_BLOCKER in the transport audit.

CALENDAR_CONTAINS_ANNOUNCED_FUTURE_SESSIONS
  - The admitted calendar runs to 2027-09-27. Future *sessions* are legitimate; future *prices* are not.
  - Any consumer must clamp price reads to the cutoff, never to the calendar end.
```

---

## 9. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
& "$EXT\venv\Scripts\python.exe" "$EXT\derive_warmup.py"
```

The script reads the real `trading_calendar` from the lake and applies the frozen
`label_cutoff = calendar[pos(S) − fwd]`, `train_start = label_cutoff − 6 months` rule directly.
