> Current role: INDUSTRY_FORECAST_RESEARCH (SWL2-Ridge-V1 / SWL2-Ridge-V2). ETF productization is RETIRED. Historical ETF formulas, commands and observations below are audit context; writer entry points fail closed. See [current industry contracts](industry-forecast.md).

# Testing and quality

`python -m pytest -q -m "not external_runtime"` runs portable numerical contracts,
synthetic evidence, schema, provider and transport regressions. It needs no private
data or credentials. Synthetic HDF5/Parquet fixtures exercise real readers.

`external_runtime` marks permitted private-evidence/frozen-framework tests.
`integration` marks broader environment/data tests and is excluded by default.
`network` additionally identifies explicit online tests. Optional framework directories
are not imported in the portable tier because deselection happens after import.
Test-local lifecycle fixtures stay temporary; engineering never invokes formal one-shot.

When available, run frozen-image ETF acceptance with network disabled, source and
permitted runtime evidence mounted read-only, `ETF_QUANT_EXTERNAL_RUNTIME_ROOT=<runtime-root>`,
and pytest cache under /tmp: `python -m pytest -q tests/etf_quant`. Missing optional
fixtures remain explicit skips. This does not run a market-data backtest.

All active Python receives Ruff lint/format. Mypy uses **staged typing enforcement**:
raw diagnostics remain visible, exact path/code/message baselines reject regressions
and stale allowances, and touched active production modules must be type-clean.
Updates remove resolved debt without adding new allowances.

Frontend tests/types/lint/build and both API suites use synthetic fixtures. APIs test
approval/integrity, bounded reads, strict schemas, origin rules and read-only behavior.
Synthetic scale checks have no fragile timing thresholds. Repository-native static/history
auditing is not external certification. See [reproducibility](reproducibility.md).

`python -m pytest -q tests/performance` checks reference output equality, tampering,
label maturity and lookup operation counts. `python -m benchmarks.core` reports
median synthetic timings at multiple scales; wall times never gate CI.

Hikyuu/KData backtesting remains a maintainer research capability. Engineering
checks use synthetic inputs and do not invoke market-data backtests or the formal
one-shot runner. Frozen-image acceptance only reads permitted evidence with network
disabled and mounts read-only.

The separately authorized V2 rebuild ran actual Development experiments and a single
Validation in the independent developer container. These private-data operations are
not portable tests or CI. V2's forward preparation, mature labels, sealed-region
exclusion, costs, cash, rebalance and T+1 gates are verified with synthetic inputs.
Its read-only API verifies the published aggregate/candidate/source hash chain.

The historical SWL2 finalization opened its Final OOS once; portable tests
verify immutable gate/result identities without rerunning the real evaluation.
`tests/test_etf_quant_v2_shadow.py` exercises synthetic facts, factors, Ridge/fusion,
independent mapping, collisions/cash, T-close intent, delayed T+1 lot/cost accounting,
idempotence and NAV/public view. API/frontend tests verify empty arming, scientific
failure labels, version selection and date-aligned ledgers. Post-merge operational
arming/launch belongs to historical context; current scheduler remains disabled.

`tests/etf_quant/test_publication_recovery.py` and the V2 Shadow suite inject crashes
before/after latest-pointer publication for both T signals and T+1 fills. A killed
subprocess proves OS mutex release; tampered journals, ancestor changes and escapes
fail closed. Scheduler tests verify literal dual-config commands, WAIT/retry/NOOP,
dirty-checkout preservation, fast-forward and private-payload exclusion. Hosted
Windows CI evaluates the actual task-definition builder, including quoting,
least privilege, login trigger, retry window and single-instance policy.
API bounded-read tests include files growing after descriptor stat.

## SWL2 transition regression

Synthetic checks cover pre-transition numerical parity, full 107/124 outputs,
zero ETF/account calls, dynamic first-session publication, no historical backfill,
exact H10/H40/H120 finalization, gap/revision blocking, immutable retries, journal
recovery, cross-language body hashes, malformed/path-escape reads, null metrics,
honest UI maturity and shared-universe descriptive comparison. The new source
certificate preserves historical report/config/archive hashes. No sealed
performance is opened by this test workflow.

## Universe and centering closure regressions

Tests independently verify current taxonomy inventory, pinned V1/V2 universe references, all raw/z/rank/fused outputs, complete forecast rows, family-native scientific targets and legal comparison with unequal centered targets. Raw return mismatch fails closed. Additional checks cover immutable evaluation recovery and body/index limits without truncating history. All quantitative execution remains in the independent Docker image.

## SWL1 strict lifecycle

Run python -m pytest -q tests/test_swl1_research.py in the independent developer Docker image. Synthetic tests cover dynamic explicit hierarchy, pre-version rejection, exact targets/missingness, population training-only scaling, mature-label cutoffs, registered search bounds, exchange-session splits/purges, protocol/candidate tampering, Validation one-shot failure and Final-OOS consumption. Generic family tests preserve 107/124 SWL2 universes and block failed SWL1 publication. API/frontend tests show FAILED_VALIDATION without runtime reads or invented forward metrics. Real research execution is separately authorized and is never rerun by CI.

## SWL1-Ridge-V2 preregistered lifecycle

Run tests/test_swl1_ridge_v2.py and tests/test_industry_forecast_v2_registry.py
in Docker. Synthetic tests cover external public merge/ancestry/exact-byte
anchors, result-free history, seen-data witnesses, endpoint equality and unseen
labels, per-row alpha, fixed equal-calendar blocks despite drops, full dropped
signal accounting, candidate freeze, one exclusive Validation claim, retry and
historical/prospective OOS rejection. V1/SWL2 bytes and numerical behavior remain
invariant. Generic API/UI tests cover absent candidates, failed Validation and
AWAITING_PROSPECTIVE_FINAL_OOS with forward=false; no future metrics are invented.
Full portable/API/frontend gates run against a public clone without private data.

## SWL1 failure-forensics safety

Run `python -m pytest -q tests/test_swl1_failure_forensics.py` in the independent
developer image. Synthetic checks cover pinned evidence/hash failure, realpath and
symlink containment, exact H120 outcome cutoffs, adversarial future-row exclusion
in C/Fortran compressed NPY, bounded decoding, target alignment, condition/df,
constant/correlated factors, missing coefficients, contribution accounting,
code ties/calendar blocks, date-confounded comparisons, public redaction and
native aggregate parity. Fortran layout bytes are discarded without numeric
conversion; no future outcome enters a target or performance calculation.
Ordinary CI never runs the private forensic replay or changes lifecycle claims.
The separately authorized replay is post-hoc only; the original failures and all
four registered family contracts stay intact. [Report](research/swl1-v1-v2-failure-forensics.md).
