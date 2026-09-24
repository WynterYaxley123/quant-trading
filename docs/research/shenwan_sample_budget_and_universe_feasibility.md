# Shenwan research sample budget and universe continuity

Status: **SAMPLE BUDGET DECISION REQUIRED**. This is a read-only date,
availability and research-definition audit. U0 remains the only formal
research universe. U1/U2 are counterfactual diagnostics, **not adopted**.
No Baseline, Ridge prediction, IC, RankIC, return, Top5 performance,
synthetic portfolio, ETF execution or LEVEL B run occurred. Final OOS stays
`UNLOCKED_UNOPENED`.

## Evidence boundary

The audit command is `python -m research.sector_universe_feasibility` in the
unchanged `quant-research` container. It reads only the SHA-verified local
Shenwan catalog/OHLCVA and admission metadata for snapshot
`872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`.
The common calendar is `2021-12-13..2026-09-18`, 1,158 trading sessions.
Missing sector rows remain missing; invalid bars are not repaired or filled.
Availability is evaluated on the actual common trading calendar, not natural
days. The fixed-classification admission is **not strict historical PIT**.

## Mathematical nonempty is not research adequacy

U0 has 239 eligible signal sessions (`2025-04-02..2026-03-27`). For the joint
10/40/120 model, two strict 120-session boundary purges consume 240 dates.
The minimum of 243 leaves just **one Dev, one Validation and one Final OOS
signal**. It is mathematically nonempty but `RESEARCH-INFORMATIVE=false`;
there is no approved minimum useful sample policy. With a nominal 10-session
cadence, each one-signal phase would have only one possible decision point.
Forty signal dates offer about four rebalance opportunities, not forty
independent portfolio decisions. The 10/40/120 forward labels themselves
overlap heavily, so daily prediction observations are not independent
replicates. None of the candidate policies below is declared statistically
sufficient or optimal.

| Candidate policy | Dev / Val / Final signal sessions | Two purges | Required eligible sessions | U0 deficit | U1/U2 deficit | Nominal 10-session decisions Dev / Val / Final |
|---|---|---:|---:|---:|---:|---|
| A | 60 / 40 / 40 | 240 | 380 | 141 | 133 | 6 / 4 / 4 |
| B | 80 / 40 / 40 | 240 | 400 | 161 | 153 | 8 / 4 / 4 |
| C | 100 / 60 / 60 | 240 | 460 | 221 | 213 | 10 / 6 / 6 |
| D | 120 / 60 / 60 | 240 | 480 | 241 | 233 | 12 / 6 / 6 |

Decision counts are arithmetic illustrations for consecutive phase signal
sessions and a 10-session cadence. The portfolio rebalance anchor and even
the applicability of that execution-plan cadence to this research study
remain unapproved. The table reports quantity and constraints only; it does
not make a significance or sufficiency claim.

For U0, the verified raw common calendar ends exactly 120 trading sessions
after the last eligible signal. Under **continued complete valid bars and
unchanged admission**, each newly observed raw trading session could release
at most one additional eligible signal session. Thus A/B/C/D conditionally
need at least **141 / 161 / 221 / 241 additional raw trading sessions**,
respectively. These are trading-session counts derived from the existing
calendar offset, not calendar-day forecasts or guaranteed future dates.
Any new data needs a fresh provenance/quality admission.

## What actually limits the universe

| Scenario | Rule | Raw all-sector-valid dates | Final continuous common range | Structurally eligible signals | Strict 3-way nonempty? | Policy A/B/C/D? |
|---|---|---:|---|---:|---|---|
| U0 | Formal fixed 124, all complete | 822 | `2023-09-27..2026-09-18` | **239** | No | None |
| U1 | Diagnostic fixed 123, exclude 801193 | 1,151 | `2023-09-11..2026-09-18` | **247** | Yes, only 7 signal slots after purges | None |
| U2 | Diagnostic dynamic, retain 124-code catalog; as-of complete-history membership | 1,151 raw dates with at least six valid bars | No single fixed-universe common range | **247** | Yes, only 7 signal slots after purges | None |

U0 reproduces the prior SHA-verified first/last signal range exactly. U1's
structural result independently reconciles with the existing fixed-universe
signal audit; neither scenario computes model output. For U2, eligibility
means at least six sectors have a complete *past* factor/training window and
the common calendar extends 120 sessions for eventual labels. This six-sector
floor is only the technical minimum of the proposed metric contract (Top5
must be a strict subset), **not** an approved dynamic-universe admission
threshold. Future endpoint availability is reported separately and never
selects as-of sector membership. A future chosen Top5 with a missing label
would make that date/horizon metric unavailable, not trigger replacement.

Within U2's 247 diagnostic signal dates, the as-of-ready sector count is
**min 123 / median 124 / max 124**. Retrospectively, all-horizon endpoint
counts have the same min/median/max. Dynamic membership cannot make the
seven common-missing dates usable: too few sectors satisfy even the technical
floor. Its opportunity set, sector entry/exit, ranking comparability,
historical availability-known-at-time and PIT evidence remain unapproved.

### 801193 and the next bottleneck

801193 证券Ⅱ has **336 unavailable sessions in nine blocks** within the
1,158-session common calendar. Its first available record is `2022-03-02`;
the last unavailable session is `2023-09-26`. The largest missing block is
`2022-08-05..2023-09-06`, **266 trading sessions**. There is also an initial
51-session block through `2022-03-01`, six isolated earlier missing sessions,
and a final 13-session block `2023-09-08..2023-09-26`. The local OHLCVA
alone does not prove whether any block reflects index launch, source outage,
or another structural cause; `cause=UNKNOWN`.

801193 is the sole additional reason the final fixed-universe continuous
start moves from U1's `2023-09-11` to U0's `2023-09-27`; removing it releases
only **eight** more eligible signal sessions. U1 still has **seven** common
missing dates: `2022-03-03`, `2022-03-23`, `2022-03-31`, `2022-04-14`,
`2022-05-05`, `2022-05-09`, and `2023-09-08`. They affect **122 of the
remaining 123 sectors**; 801952 is the sole unaffected sector. All 123
sectors have an initial valid bar by `2021-12-13`, but the later gaps mean
“first complete date” is not the same as the start of a continuous common
window. There is no single next sector whose removal recovers the full
history: the next bottleneck is shared across 122 sectors.

For U1 the factor-ready dates span `2022-11-03..2026-09-18` (**822** dates,
not one continuous block); historical training-readiness begins
`2025-03-21` (**367** dates through the raw end); retrospective 120-session
label-ready dates span `2022-05-10..2026-03-27` (**822** dates, with gaps).
Their intersection under the strict fixed-123 rule is
`2025-03-21..2026-03-27`, **247 eligible signal dates**. The latest first
complete date is `2021-12-13`, but the terminal continuous common start is
`2023-09-11`. These ranges are availability diagnostics, not permission to
adopt a 123-sector baseline.

**U1 adoption requires `UNIVERSE_CHANGE_REQUIRES_READMISSION`** because it
changes the rank denominator, Top5 opportunity set and industry coverage.
U2 also needs separate dynamic-universe methodology and admission, including
as-of availability evidence. The formal catalog and strategy loader remain
unchanged in this audit. Neither U1 nor U2 satisfies any candidate A–D
sample budget with the current data.

## Frozen prediction-evaluation definitions — no values calculated

The versioned contract is `sector-index-prediction-metrics-v1` in the
read-only audit module. For each approved as-of universe and signal date `t`,
the target for horizon `h∈{10,40,120}` is the absolute sector-index
close-to-close label `close[t+h]/close[t]−1`. IC_h is the across-sector
Pearson correlation of the corresponding horizon model score with that
label; RankIC_h is Spearman using average ranks for score/return ties.
Top5 is selected by the *fused* 10/40/120 score descending, breaking exact
score ties by sector code ascending. Top5_forward_return_h is the arithmetic
mean of exactly those five selected-sector labels. Universe_forward_return_h
is the equal-weight arithmetic mean over the complete approved as-of
universe. Top5_minus_universe_h is their difference. These define the 15
names IC_10/40/120, RankIC_10/40/120, Top5_forward_return_10/40/120,
Universe_forward_return_10/40/120 and Top5_minus_universe_10/40/120.

The technical minimum is **six sectors** per date/horizon, to keep Top5 a
strict subset; this says nothing about statistical adequacy. A missing score
or forward label for any as-of universe member makes the affected
date/horizon metric `null` with a reason. Do not drop the sector after seeing
its future label, re-rank, replace a missing Top5 member, fill a bar, or turn
an unavailable value into zero. Zero cross-sectional variance makes a
correlation `null`. Across dates, report the equal-weight arithmetic mean of
valid date-level metrics plus valid/null date counts. No naive independent
sample t-statistic or significance claim is allowed because labels overlap.
This contract freezes definitions, **not** results or a study sample policy.

## Synthetic portfolio and OOS remain unresolved

The historical execution research YAML references rebalancing every 10
trading sessions, but `rebalance_anchor` is null and the strategy spec marks
cadence decision D02 pending. The sector-index study is not ETF execution;
the execution-plan 10-session cadence cannot be silently promoted to a
frozen synthetic portfolio. Entry convention, formation/weights, holding
and exit, overlap, mark-to-market, return measurement and turnover also
lack approved research semantics. Therefore
`SYNTHETIC_PORTFOLIO_SEMANTICS_REQUIRES_APPROVAL`. Prediction label returns
do not define portfolio holding returns; no synthetic equity, drawdown,
volatility or turnover was computed.

The deterministic config-hash schema now includes the already specified
19 factors, Ridge alpha, horizons/fusion, Top5, six-month training and
30-valid-day minimum, target, data-admission mode and snapshot, and the
prediction metric specification version. Before any formal hash/OOS lock,
the rebalance anchor/policy, synthetic holding policy, approved split policy
(phase budgets, two purges and exact dates) and approved universe policy
(mode, codes and admission) must also be supplied. Timestamp/UUID/run ID
cannot affect the hash. Because those four policies are not frozen here,
`strategy_config_hash=null`, `oos_start=null`, `oos_end=null`, and
`oos_status=UNLOCKED_UNOPENED`.

**Exact next decision:** approve a minimum candidate sample-budget policy
or specify another one **before** seeking more data, and decide whether the
formal fixed-124 universe remains mandatory. U1/U2 cannot be adopted without
their own readmission. Independently approve or reject a complete synthetic
portfolio timing/holding specification before any synthetic OOS study. No
OOS lock or performance run follows automatically from these decisions.
