# Shenwan Development-only prediction protocol — frozen policy

Status: **DEVELOPMENT PREDICTION PROTOCOL LOCKED**. This is a configuration,
calendar and access-control freeze, not a model run or a tradable backtest.
The official universe is U0, the fixed 124 Shenwan level-2 sectors under
`FIXED_CLASSIFICATION_RESEARCH` (`strict_pit=false`). U1 (exclude 801193)
and U2 (dynamic available universe) are diagnostic only. Each yields only
eight more eligible signal sessions (239 → 247) while changing the
cross-sectional denominator, ranking opportunities and membership semantics.
No universe change or readmission was approved.

## Approved Policy C and current calendar

Ordinals are assigned to the ordered **eligible signal trading calendar**,
beginning at E001. Eligibility retains the existing fixed-124 all-sector
OHLC validity, factor warmup, six-calendar-month training with at least 30
valid dates, per-horizon training-label purge and realized 10/40/120-session
forward labels. No future return, IC, regime or model outcome can move an
ordinal boundary. Each phase boundary excludes exactly 120 eligible trading
sessions; the prior phase's longest label endpoint lies in the purge.

| Phase | Frozen ordinals | Required | Present on snapshot | Actual present dates |
|---|---:|---:|---:|---|
| Development | E001–E100 | 100 | 100 | 2025-04-02–2025-08-26 |
| Purge 1 | E101–E220 | 120 | 120 | 2025-08-27–2026-03-02 |
| Validation | E221–E280 | 60 | 19 | 2026-03-03–2026-03-27 |
| Purge 2 | E281–E400 | 120 | 0 | not available |
| Final OOS | E401–E460 | 60 | 0 | not available |

Total requirement is **460 eligible sessions**, current count **239**,
deficit **221**. Validation needs 41 more eligible sessions. The last
Development 120-session label realizes on 2026-03-02 (E220), strictly before
the first Validation signal on 2026-03-03 (E221). These are verified local
calendar dates, not estimated natural-day offsets. Because E401–E460 are not
available, the OOS *ordinal policy* is locked but no OOS date range or
performance is locked/opened.

Policy A would leave only four nominal 10-session Validation/OOS decision
points. B increases only Development while leaving the same four nominal
points in Validation/OOS. Policy C allocates 100/60/60; D would add 20
Development signals but require 20 extra eligible sessions. These nominal
counts are arithmetic comparisons, **not statistical adequacy claims**;
research cadence/anchor is not frozen.

## Reproducibility and configuration hashes

`research.sector_development_protocol` is the read-only policy entry point.
Run `python -m research.sector_development_protocol` inside the existing
container to reproduce the metadata; it writes no result files.
`split_policy_hash` is SHA-256 of canonical sorted JSON containing the fixed
U0 policy/code-list fingerprint, 100/60/60 counts, 120/120 purges, admission
mode, eligible-calendar semantics and all five ordinal intervals. It excludes
time, UUID, observed dates, data snapshot and performance; a future data
append cannot change this policy hash. Current value:

`3b6b2d754211169039439c8b377fd9eb26d5cb5db0f80d62cffc1d19c81a7038`

`prediction_config_hash` additionally covers the exact ordered 19 factors,
NumPyRidge alpha 0.01, 10/40/120 labels, fusion 0.25/0.50/0.25, Top5,
six-calendar-month rolling training, 30-valid-day minimum, absolute forward
close-to-close target, RSRS/macro/flow/RiskState flags, and the full frozen
15-metric prediction contract. Current value:

`64d5fabe6f194f416c6576d4da9cd5e2fb2ad1e699e2c074047960addaa0ed8c`

The observed snapshot ID is separately
`872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`.
The frozen E001–E239 date-prefix SHA-256 is
`bcefa227f86a805677733defea63ed3954915548a6a140b0f654510c4267790b`;
the fixed sorted 124-code fingerprint is
`f24e61c51f48e1b4ca8ded83eaf24bdd71be35711f3eb0ed88d7627f332d026a`.
The canonical historical sector-name/OHLCVA/validity rows through
2026-09-18 have a separate SHA-256 fingerprint
`a78ae9d6e3c0f7b985927e1d6ae721f94ae4bb85fb58440cfd76719846eff82c`.
Source-file metadata is excluded from this economic-data digest so a
genuine append with unchanged historical values does not spuriously fail.
The separate snapshot ID may change on append, while the two configuration
hashes and original ordinal identities remain unchanged. If historical
sector values, eligibility dates or U0 codes change, the audit raises
`SPLIT_REPRODUCIBILITY_REVIEW`; it must not silently reindex.

## Prediction-only evaluation contract and seals

The future Development runner may evaluate **only E001–E100**. Its model
training at each signal `t` must use only labels realized by `t` under the
existing per-horizon cutoff. Purge dates can be used to *realize earlier
labels*; they cannot emit evaluation metrics. The 15 frozen outputs are
IC, RankIC, Top5 forward sector return, universe forward sector return, and
Top5-minus-universe for each horizon 10/40/120. IC uses the corresponding
horizon score; Top5 selection uses fused score, descending, then sector code
ascending. The label is `sector_close[t+h]/sector_close[t]-1`, known only at
`t+h`. Per-date cross-sectional metrics use the fixed approved as-of universe.
The technical minimum is six sectors, only to keep Top5 a strict subset.
Missing scores/labels for any as-of member make that date/horizon metric
null with a reason; no future-aware universe shrink, replacement or zero
fill is allowed. Zero-variance correlations are null. Multi-date summaries
are equal-weight means of valid dates with valid/null counts; overlapping
forward labels prohibit naive independent-sample significance claims.

`guard_evaluation("development", ordinals)` and its date wrapper reject
E101–E220 as purge and E221+ with `SEALED_PHASE_ACCESS_ERROR`. Validation is
`LOCKED_PARTIALLY_AVAILABLE_UNOPENED`; Final OOS is
`FINAL_OOS_POLICY_LOCKED_DATES_NOT_YET_AVAILABLE` and
`oos_performance_status=UNOPENED`. A future runner must use these guards at
its output boundary. This freeze did **not** compute or view any prediction,
Validation, OOS, portfolio or performance metric.

`synthetic_portfolio_enabled=false` and
`synthetic_portfolio_config_hash=null`. The old execution-plan 10-session
rebalance number does not settle research anchor, entry, holding, overlap,
return measurement or turnover. No equity curve, synthetic total return,
Sharpe, drawdown or turnover may be generated from this protocol.

Final OOS performance must remain sealed until Development is complete,
candidate decisions are frozen, Validation is fully available and evaluated,
the final model/config is frozen, E401–E460 data are available, and explicit
Final OOS authorization is given. The exact next task, in a separate turn,
is a guarded **Development-only prediction baseline** for E001–E100; it is
not authorized by this documentation alone. No LEVEL B or ETF execution.
