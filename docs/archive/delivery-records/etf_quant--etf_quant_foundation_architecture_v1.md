# ETF-QUANT Foundation Architecture V1

Status: `ETF_QUANT_FOUNDATION_V1_COMPLETE — INTEGRATION_DEFERRED`.

This is an isolated, explicit-input core foundation, not a market-data pipeline,
backtest, live simulation run, executable production strategy or Research API.
All exercised inputs are synthetic. No performance result was produced.

## Identity and scope

Baseline: `bd13d278b25eace66a7eae287307413f930effd9`.

Branch: `agent/codex-etf-quant-foundation-v1`.

Worktree: `D:\quant-worktrees\codex-etf-foundation`.

The main worktree `D:\quant-trading` remains on that baseline with a clean
worktree and index. Creating the explicitly requested linked worktree registers
shared Git administrative metadata; it does not change the main checkout,
branch/HEAD, index entries or source files. No merge or push is part of this task.

All added files are confined to `strategies/etf_quant/`, `tests/etf_quant/`, and
this one architecture document. Existing files are not modified. The new package
uses relative imports only for its own components, with standard-library,
NumPy and Pandas dependencies already present in `quant-research`. There are
no imports of frozen Research, the old strategy or top-level framework code.

Hard identity: `ETF_QUANT`, `SIMULATION_ONLY`, `NO_BROKER`,
`NO_REAL_ORDER_PATH`. Runtime state cannot turn these flags on or become running.
There is no scheduler, runner, automatic fetch, order API or broker adapter.

## Components and boundaries

| Component | Responsibility | Explicit non-responsibility |
|---|---|---|
| `config/__init__.py` | Frozen baseline identity, ordered factors and fusion weights | Data/provider selection |
| `domain/__init__.py` | Immutable configuration, predictions/rankings, provisional mapping, accounting and metadata values | Fetching, persistence, execution routing |
| `factors/__init__.py` | Formal 19-factor registry and pure OHLCVA computation | Vendor column mapping, repairs, imputation |
| `models/__init__.py` | NumPy Ridge, independent horizon fit, coefficients/intercept/training metadata | Walk-forward loop, labels fetched or manufactured by a provider |
| `models/fusion.py` | Independent horizon z-scores, deterministic industry ranking and Top5 | Raw prediction weighting, partial-universe intersection |
| `mapping/__init__.py` | Provisional completeness checks and admission states | Concrete ETF selections, fuzzy matching, production admission |
| `portfolio/__init__.py` | Capped softmax and member-set-only rebalance decision | Orders, quantity rounding, weight-drift-triggered rebalance |
| `simulation/__init__.py` | Explicit-input fill pricing, immutable cash/position/PnL accounting, single NAV values | Simulation loop, real orders, market-price discovery |
| `runtime/__init__.py` | Five provider/mapper protocols, provisional DTOs and permanently deferred foundation state | Concrete implementations or orchestrator |
| `schemas/__init__.py` | Pure DTO-to-JSON projection | HTTP service, Research API or Dashboard integration |

The conceptual future flow is industry data → independent horizon models →
per-horizon standardized fusion → Top5 industries → future mapper → explicit
executable asset scores → capped sizing → pure simulation primitives. No code
currently wires these into an automated pipeline.

The provider ports are `IndustryDataProvider`, `ETFUniverseProvider`,
`TradingCalendarProvider`, `BenchmarkDataProvider`, and `IndustryETFMapper`.
Their current signatures are provisional internal contracts. There is no concrete
provider, endpoint, authentication mechanism or external data import in core.

## Authoritative calculation provenance

The following existing baseline files were inspected read-only. Their source is
copied in isolation where needed; frozen files are neither imported by the new
package nor edited to facilitate reuse.

| Baseline source | SHA256 | Authority used |
|---|---|---|
| `research/configs/f1_independent_validation_v1_candidate.json` | `5424e4fb8679172e3bcac466f0b3129e04ffc4485e98b42fee90a9537dd2ff98` | Factor lists, target, model/window and fusion semantics |
| `strategies/sw_sector_rotation/src/factors/sector_rotation.py` | `9bf6013f6efb10ab62d21f0acfc1cddb19aef44bb1661581c9957f814f05c4ec` | Actual factor formulas, epsilon and warmup behavior |
| `strategies/sw_sector_rotation/src/model/model.py` | `61fed9e609f23d579f7f01dceae79d132021fc72c5019bdcf0b9a011a86785ba` | NumPy Ridge objective/solver, stable z-score and tie-break |
| `strategies/sw_sector_rotation/src/common/temporal_integrity.py` | `da1542f1b00da3cc63d8a5e96690b75a382c1f84c884ded78d50dca6004dc5fa` | Per-horizon label cutoff and six-calendar-month anchor |

These are source-code/contract checks, not reads of Validation predictions,
returns, RankIC, spreads, Top5 performance or Final OOS. The generic old model's
legacy absolute-return description is not treated as the frozen F1 target:
the authoritative frozen candidate explicitly requires cross-sectional excess
forward return, and that target is enforced in ETF-Quant.

## Factors and feature order

H10: `d10,p5,align,vc,dd20` only.

H40 and H120: `d5,d10,d20,d60,d120,p5,p10,p20,p60,p120,align,v5,v20,vc,rev5,rev10,dd20,dd60,rsi`.

The 19 `FactorSpec` registry entries record formulas, lookbacks and input fields.
All these factor formulas use close; the baseline canonical input guard still
requires explicit `open,high,low,close,volume,amount`, positive finite prices,
nonnegative finite volume/amount, and sorted unique naive daily dates. Missing
volume/amount are not silently replaced by zero. This does not imply an audited
external schema: adapting any vendor data is deferred.

Formulas are unchanged: deviation from rolling MA; clipped rolling price-range
position with `1e-10`; weighted MA comparisons `(3,2,1)/6`; rolling return
standard deviation; volatility ratio; negative rolling mean returns; close
relative to rolling maximum; and simple-mean 14-session percentage-return RSI.
No RSRS, new factor, feature normalization or missing-value imputation is added.

Factor volatility uses sample standard deviation (`ddof=1`). Fusion uses
population standard deviation (`ddof=0`); these are intentionally distinct.
Warmup NaNs remain NaN. `align` preserves the source's False comparisons with
unavailable MAs, including early zero/partial values; the 60-session registry
lookback describes its complete comparison window, not an invented NaN mask.
Appending future rows cannot change the earlier factor prefix.

## Independent Ridge and temporal contract

Each horizon has a separate immutable `FittedHorizonModel`. The objective is
`||Xw+b-y||² + 0.01||w||²`, with unpenalized intercept, raw X and no train-time
feature standardization. Centered augmented least squares uses `numpy.linalg.lstsq`,
not normal equations. Numerical rank/nonfinite failures stop fitting; failed
refits of the primitive estimator invalidate its previous solution.

The caller supplies an explicit calendar, signal timestamp, industry universe,
features, raw forward return, label end and availability evidence. The per-horizon
label cutoff is calendar position `signal_position - horizon`. The window starts
six calendar months before that label cutoff, not six months before signal date.

Out-of-window or unmatured observation dates are rejected before examining their
feature/target values. Accepted rows must have the exact expected calendar label
end, known timezone-aware availability no later than signal time and no earlier
than the label-end date, exact ordered factors, finite features/target, no
duplicate date/industry, and the complete explicit universe on each training date.
At least 30 distinct valid dates are required. UNKNOWN availability is a blocker,
not fabricated from effective dates. For each accepted date, the full-universe
mean raw forward return is subtracted before stacking samples.

The availability value is an explicit caller evidence contract for the complete
observation. The foundation does not prove provider publication timing, same-day
close readiness or exchange timezone/close clock. Those must be audited in a
future provider contract; no production data admission is possible now.

Output includes horizon/factor order, coefficients by name, intercept, alpha,
window start/cutoff, actual training start/end, distinct date count, sample count,
signal time and target/preprocessing identity. Prediction is restricted to the
fitted signal date and the exact factor order. No daily fitting loop exists.

## Fusion, sizing and rebalance

Each of H10/H40/H120 is cross-sectionally z-scored independently using `ddof=0`.
The source's positive magnitude rescaling prevents finite extreme-score overflow;
constant/nearly constant vectors follow its `1e-12` standard-deviation guard and
produce zeros. Fusion is `0.25*z10 + 0.50*z40 + 0.25*z120`, never a weighted sum
of raw predictions. All horizons must share one signal date and full identical
industry coverage, with at least five industries. No intersection fallback.
Ranks are score descending then industry code ascending, without score rounding.

Sizing accepts ONLY caller-supplied executable asset identities/scores; it does
not map industries to ETF codes. Active-set capped softmax redistributes excess
only among uncapped selected assets, recomputing their original relative scores
to avoid losing residual mass to exponential underflow. Default maximum target
weight is 35%; the product requires five executable assets. Empty, insufficient
or cap-infeasible cases return no targets and explicitly retain 100% unallocated.
They do not invent an ETF, reduce Top5 silently or violate the cap. Feasible
targets are nonnegative, at/below cap and sum approximately to one.

Rebalance uses only Top5 member-set changes. Reordering, changing scores or
changing target weights with the same five members produces `NO_REBALANCE`.
An initial empty set requires allocation. The cap is a target-weight constraint,
not an automatic mark-to-market weight-drift trigger.

## Simulation primitives and cost convention

Initial capital is CNY 10,000. An intent declares T-close signal and T+1-open
simulation execution. The explicit supplied trading calendar must contain that
exact next session; a natural-day shift or later session is rejected. OPEN/CLOSE
are input contract markers, not a guess about exchange hours. No real exchange
calendar, open-time enforcement or executable market bar is supplied in V1.

Configured defaults are commission 3 bps, slippage 5 bps each side, SELL stamp
duty 0 and minimum commission 0. All four cost values are configurable. BUY fill
price is reference open times `(1+slippage_bps/10000)`; SELL uses subtraction.
Commission applies to slipped executed notional with the configured minimum.
Configured stamp duty applies to SELL notional only. Slippage is separately
disclosed but already included in price: accounting never deducts it again.

BUY cash pays notional plus fees; weighted average basis includes buy fees.
SELL cash receives net proceeds and realizes PnL against the retained average
basis. Partial sells retain that basis; a full sell removes the position. Immediate
valuation uses the explicit reference open, not slipped execution price, so
slippage/commission do not disappear from equity. Explicit full-position marks
are required for mark-to-market. Missing prices do not become stale-price defaults.

State is immutable, long-only and rejects insufficient cash, overselling, old
timestamps, duplicate fill IDs and a second full fill of the same intent. Cash,
quantity and money calculations use `Decimal` with fixed internal precision 50
and half-even rounding, independent of caller global precision. Tick, lot,
cash-cent rounding, partial-order lifecycles, corporate actions and liquidity/
halt/limit/tradability rules are not invented. Multiple-asset mark freshness and
production position admission remain future contracts. There is no rebalance
order generator, cost-aware quantity allocator or daily NAV/performance runner.

`NAVPoint` is a single explicit accounting projection with cash/market-value
identity guards. `StrategyRunMetadata` cannot enable broker/real order flags;
unknown implementation commit, provider and data snapshot remain null until
explicitly supplied. Serialization preserves null and renders Decimal as a
decimal string. No provenance is fetched or manufactured automatically.

## Provisional mapping, benchmarks and deferred integrations

`ETFMapping`/`MappingResult` describe identity, tracking index, method, confidence,
effective interval, verification and availability timing. Unknown fields remain
null. No current classification is backfilled into history. Incomplete metadata
is reported; even a complete synthetic candidate cannot receive `ADMITTED` in
this foundation. Production mapping, duplicate ETF consolidation and any final
PIT admission rule await the external contract.

Only benchmark identifiers and a DTO/port exist: CSI 300, NASDAQ Composite and
S&P 500. No provider, price series, currency conversion, calendar alignment or
cross-market return comparison is chosen or downloaded.

| Deferred integration | Blocking status |
|---|---|
| CNEquity provider, field/schema/availability/calendar/tradability contracts | `PENDING_DEEPSEEK_CONTRACT` |
| Industry→ETF concrete mapping and temporal evidence/admission | `PENDING_DEEPSEEK_CONTRACT` |
| Benchmark availability/provider/currency/calendar semantics | `PENDING_DEEPSEEK_CONTRACT` |
| Research API, Dashboard, README and GitHub public integration | `PENDING_MIMO_AUDIT` |
| Wiring any of the above or changing paths outside the permitted scope | `INTEGRATION_DEPENDENCY_DEFERRED` |

No other agents' worktree contents or uncommitted work are accessed, assumed or
merged. The current provider DTOs are provisional and do not claim to be the
audited final contracts. Research, F1, Validation, Final OOS, the official updater
and canonical Shenwan data remain isolated and untouched.

## Verification

All Python execution uses the existing Docker `quant-research` environment.
Only the new package/tests are copied to a temporary container directory for
focused tests, with bytecode and pytest cache disabled. The main bind mount is
not used as a write target. No image/container configuration or dependency is
changed. No network test, provider request, research runner or backtest is run.

Focused ETF-Quant offline suite: **78 passed, 0 failed, 0 skipped**. It covers
frozen configuration, identity/firewalls/null metadata, ordered factors and
formula/warmup/prefix invariance, independent Ridge and temporal guards,
per-horizon standardized fusion versus raw weighting, stable tie-break, bounded
softmax including underflow/infeasible capacity, membership-only rebalance,
costs/cash/basis/PnL/marks, duplicate-fill safety and malformed result DTOs.

Existing pure factor/Ridge baseline tests: **36 passed, 0 failed, 0 skipped**.
This is the intentionally selected safe regression subset, not a claim that the
entire repository or integration suite was run.

Separate read-only source parity audit, entirely synthetic:

- Four 320-session factor cases (random, constant, rising, falling): all 19 factor
  columns match the baseline bit-for-bit, including NaNs; prefix invariance passes.
- Twelve Ridge cases (5/19 features, alpha 0/0.01/10000, with/without intercept):
  coefficients, intercepts and predictions match the baseline bit-for-bit.
- Three fusion cases (random, constant, finite extremes): full scores and rankings
  match the baseline exactly on complete coverage, including sector-code tie-break.

Future integration or market-data admission is explicitly outside this completed
foundation task. Validation and Final OOS remain sealed and unseen.
