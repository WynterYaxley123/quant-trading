# Shenwan sector-index research split feasibility

Status: **STRICT_3WAY_SPLIT_NOT_FEASIBLE**. This is a date, session-count,
label-availability and configuration audit only. No baseline, Ridge fit,
prediction ranking, IC, return, equity curve, ETF execution or LEVEL B run was
performed. The fixed-classification sector-index study remains
**NON_EXECUTABLE / NOT LEVEL B / NOT ETF PERFORMANCE**.

## Evidence and frozen scope

The read-only entry point is `python -m research.sector_research_split` in the
existing `quant-research` container. It loads only SHA-verified local Shenwan
sector catalog/OHLCVA and the admission record. Data snapshot:
`872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`.
The 124-sector common calendar is `2021-12-13..2026-09-18`, 1,158 sessions.
The independently admitted all-sector signal interval is
`2025-04-02..2026-03-27`, **239 consecutive trading sessions**. It remains
`FIXED_CLASSIFICATION_RESEARCH`, not strict historical classification PIT.

The Baseline v1 signal definition is unchanged: 19 price factors,
NumPyRidge alpha 0.01, absolute forward close-to-close sector returns,
10/40/120-session labels, fusion 0.25/0.50/0.25, Top5, six calendar months
rolling training, at least 30 valid training days, RSRS excluded, macro/flow
off, and RiskState record-only. No horizon or parameter was shortened to make
the split fit.

## Three distinct clocks

For a signal at session `t`, features may use prices only through `t` (the
signal is after close). Its horizon-`h` label becomes realized at `t+h` on
the *common trading calendar*. Existing core code truncates frames at `t`,
builds labels on that visible frame, and restricts training origins to
`<= t-h`; thus every included historical training label ends no later than
`t`. The audit rechecked all **239 × 3 = 717** signal/horizon boundaries
against the actual calendar. This is a training-time check, not a model run.

Research decision time is separate: Development evaluation results must not
be available for candidate selection until the last Development label is
realized. Validation results likewise must not guide the final candidate
until its last label is realized. A protected next phase starts *strictly
after* that realization. Labels reaching into the next phase would leak its
price information to an earlier research decision.

## Strict session purge and capacity

If phase A ends at calendar index `i`, its last horizon-`h` label ends at
`i+h`. The next phase may start no earlier than `i+h+1`. Hence the `h`
sessions `i+1..i+h` are excluded between phases; the label-realization day
itself is in the purge. For three nonempty phases, the minimum is
`1 Dev + h purge + 1 Validation + h purge + 1 Final OOS = 3+2h`.

| Horizon/design | Eligible sessions | Purge per boundary | Two purges | Minimum for 3 nonempty phases | Feasible | Difference |
|---|---:|---:|---:|---:|---|---:|
| 10 only | 239 | 10 | 20 | 23 | Yes, horizon-only | +216 |
| 40 only | 239 | 40 | 80 | 83 | Yes, horizon-only | +156 |
| 120 only | 239 | 120 | 240 | 243 | **No** | **−4** |
| Joint 10/40/120 | 239 | **120** | **240** | **243** | **No** | **−4** |

Joint fusion requires all three labels, so its boundary is governed by the
maximum, 120; a 10/20/30-day `embargo-lite` is not equivalent. The strict
joint session budget is:

| Component | Minimum required | Allocation in the current design |
|---|---:|---:|
| Development signals | 1 | null — no valid three-way allocation |
| Purge 1 | 120 | 120 required |
| Validation signals | 1 | null — no valid three-way allocation |
| Purge 2 | 120 | 120 required |
| Final OOS signals | 1 | null — no valid three-way allocation |
| Total | **243** | **239 available; deficit 4** |

The date proof is even more concrete. With the earliest possible Dev signal
on `2025-04-02`, its 120-session label ends `2025-09-24`; the earliest Val
signal is `2025-09-25`. That Val signal's label ends `2026-04-01`; the
earliest Final OOS signal is `2026-04-02`. The final eligible signal is
`2026-03-27`, four trading sessions too early. These dates are a **proof of
impossibility**, not a proposed joint split or an OOS lock.

For 10-only and 40-only, a deterministic *illustration* allocates remaining
signal slots after both purges using the existing 60/20/20 ratio guidance,
with integer truncation and the remainder assigned to the last phase. It
uses dates/counts only, never observed returns. It is **not selected** and
does not replace the frozen joint baseline:

| Horizon | Dev | Purge 1 | Val | Purge 2 | Final candidate | Label tail |
|---|---|---|---|---|---|---|
| 10 only | `2025-04-02..2025-10-16` (131) | `2025-10-17..2025-10-30` (10) | `2025-10-31..2025-12-30` (43) | `2025-12-31..2026-01-15` (10) | `2026-01-16..2026-03-27` (45) | `2026-04-13` |
| 40 only | `2025-04-02..2025-08-19` (95) | `2025-08-20..2025-10-22` (40) | `2025-10-23..2025-12-04` (31) | `2025-12-05..2026-02-02` (40) | `2026-02-03..2026-03-27` (33) | `2026-05-28` |

A two-phase Dev+Validation **or** Dev+Final OOS partition with one 120-day
purge can contain at most `239−120=119` signal dates total, split into two
nonempty phases (minimum 122 calendar sessions including purge). This is
only a feasibility bound. It does **not** authorize deleting Validation or
calling a two-phase plan the agreed three-way baseline.

## Final OOS seal and configuration freeze

For the joint design, `oos_status=UNLOCKED_UNOPENED`;
`oos_signal_start`, `oos_signal_end`, `oos_label_tail_end`, `locked_at`, and
`strategy_config_hash` are all **null**. No joint OOS candidate dates are
selected, no performance has been viewed, and no lock metadata is created.
If a future approved, feasible split is locked, metadata must record
`oos_status=LOCKED_UNOPENED`, start/end, lock time, split policy version,
SHA-verified data snapshot ID, and a deterministic strategy config hash
*before* anyone sees performance. It must not contain OOS return, Sharpe,
ranking metrics, or any other OOS performance. Opening the lock is a later
separate decision.

The proposed SHA-256 fingerprint uses canonical sorted JSON of the 19
factors, model/alpha, horizons, fusion, Top5, training window and minimum,
target, risk/RSRS/macro/flow flags, data admission mode and snapshot ID, plus
approved rebalance, holding, split and universe policies. Timestamps, UUIDs
and run IDs are excluded. Hashing returns null while any of these four
policies is missing; no timestamp or arbitrary generated ID can manufacture
a lockable hash.

The existing `sw_sector_rotation_level_b_research.yaml` contains
`rebalance_sessions: 10` under an **execution research plan**, but its
`rebalance_anchor` is null. The strategy specification marks D02 cadence
unapproved, and the sector-index baseline preparation explicitly leaves
synthetic selection cadence/holding unresolved. Therefore the 10-session
reference cannot silently become a frozen sector-index portfolio rule:
**REBALANCE_SEMANTICS_NOT_FROZEN**. Portfolio formation, entry, holding,
overlap, return measurement and turnover semantics likewise remain
**HOLDING_SEMANTICS_NOT_FROZEN**. These block a synthetic-portfolio OOS lock
independently of the four-session capacity deficit.

For any later OOS, record `oos_signal_end` separately from
`oos_label_tail_end=signal_end+120 sessions`. Post-signal raw sector prices
may realize labels only. They cannot feed OOS features, historical training
at earlier dates, candidate selection, or parameter decisions. The present
joint OOS has neither endpoint because it is not selected.

## Future evaluation definitions — not executed

Cross-sectional prediction evaluation may later define IC_10/40/120
(cross-sector Pearson score/forward-return correlation), RankIC_10/40/120
(Spearman), Top5_forward_return per horizon (equal-weight selected-sector
forward label), Universe_forward_return (equal-weight eligible universe),
and Top5_minus_universe. These are label-based diagnostics, not portfolio
returns. Their eligible universe, missing-bar treatment, tie ordering and
overlapping-label uncertainty must be predeclared before a run. No such
metric was computed in this audit.

Synthetic portfolio evaluation would require a *separate prior freeze* of
rebalance interval/anchor, formation, entry and holding conventions,
overlapping versus nonoverlapping portfolios, mark-to-market, return and
turnover semantics. Only then could synthetic total return, max drawdown,
volatility and turnover be defined. Such a series remains **NON_EXECUTABLE**
with **NO ETF COSTS** and cannot be interpreted as tradable ETF performance.

## Decision options (none implemented)

- **A — preserve the 124-sector joint baseline and strict purge.** Wait for
  more future valid data. Four extra eligible signal sessions are the bare
  mathematical minimum for one signal in each phase, and would require at
  least four additional raw sessions for the 120-day tail if continuity
  persists. Meaningful phase lengths need substantially more; data must be
  re-admitted, not appended by assumption.
- **B — dynamic eligible-sector universe.** Re-audit historical membership
  and data quality. This changes fixed-universe methodology and needs
  explicit approval before implementation.
- **C — exclude the long-gap sector 801193.** A different universe may extend
  history, but it is a universe change requiring separate data admission.
- **D — independent horizon studies.** 10 and 40 can be split separately;
  this changes the joint 10/40/120 fusion study and is not an automatic fix.
- **E — purged walk-forward/time-series CV with a sealed Final OOS.** The
  reserved OOS boundary still needs 120 sessions. With 239 total, a
  one-signal OOS leaves at most 118 earlier signal sessions before that
  purge—insufficient even for one additional strict 120-purged nonempty
  train/validation fold (minimum 122 sessions). Thus E also needs more
  data or a separately approved methodological change; it cannot quietly
  reuse OOS prices for selection.

**Recommended next decision:** preserve the frozen joint design and choose
whether to wait for a materially longer, re-admitted continuous data window
(A), or explicitly commission a separate methodological redesign. Do not
run the baseline, open OOS, tune parameters, or start LEVEL B meanwhile.
