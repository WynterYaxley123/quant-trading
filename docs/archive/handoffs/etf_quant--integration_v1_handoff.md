# ETF Quant V1 integration handoff — 2026-09-27

FINAL STATUS: **ETF_QUANT_V1_DATA_INTEGRATION_BLOCKED**

The offline engineering pipeline, manual transport, read-only API and Dashboard
are committed locally. Real data admission and forward Shadow are NOT_STARTED.
No market-data result, live account performance or successful GitHub sync is
claimed. Stop here; this is not authorization for V2 or model optimization.

## Git and provenance

- Main `D:/quant-trading` is STRICT READ-ONLY at
  `bd13d278b25eace66a7eae287307413f930effd9`; index/worktree/diffs are clean.
- Integration `D:/quant-worktrees/etf-quant-integration`, branch
  `integration/etf-quant-v1`, base `integration/research-dashboard-v1` at
  `457b432056ebc894992de330a3b480c062e90bcc`.
- Base contains Dashboard `a4b549ca2114060d156ce7ee60f436d9e1aad35a` and Research
  API `ae92a2a1e49bc322bf4961f5115e24b0ba24ec46`. Later main Research changes
  were intentionally NOT merged. Other worktrees were not changed.
- Final SHA is the HEAD containing this handoff; obtain with read-only
  `git --no-optional-locks rev-parse HEAD`. A document cannot embed its own
  containing commit SHA without changing that SHA.

| Approved original commit | Applied integration commit |
|---|---|
| 521a10899a14d479e0cfbefeb7d023186334d9b7 | 3fc5a5a278d5d78d84626848d14c5366e0f363e6 |
| c3e56c03aedce1e55b1ff5179ff6704bc0ea9b98 | d2257d3de0833bc41b92029b05bc69171f0a5a42 |
| c75e78d2d209852d54fc4ef186d5d8534cb67516 | dd1df7cdbd27af9c1bbef95f615fb6ff5537cadd |

New implementation commits, in order:

1. `53a74488f4378496d5b41f537c65803a61164d04`: pinned sidecar, immutable
   exports, Source C and current-snapshot prediction inputs.
2. `71331e5633680afd65443e1992f3735fc0883610`: evidence-gated mapping.
3. `bcf3148b6f6cdb1eb9bccad8d1267f6f8a3cc3b9`: atomic forward Shadow.
4. `872391dcf788d1005c175f99455b390ab83e9360`: safe manual Docker transport,
   full accounting/time disclosure and read-only security scanner.
5. `b4c17b2a86e1088bc64e8d64893674f3cdea578b`: independent read-only ETF API.
6. `42918b995c04edd5383110a7c629574230478f06`: independent ETF Dashboard.
7. `52440d8811e48c176495ca34f752bd5fdd723d9c`: consumed instrument evidence
   included in immutable prefix, unknown listing dates remain null.
8. Containing documentation commit: README, safety ignores, notices and handoff.

Existing origin: https://github.com/WynterYaxley123/quant-trading.git, no embedded
credentials. Push attempted: **NO**. Full default regression is not green;
the user's conditional push gate is not satisfied. Remote branch SHA is
**unknown/not queried**, not inferred from local HEAD. No remote, credentials,
global Git settings, history or main branch were changed. No PR was created.

## CNEquity: installed, but real data blocked

Official software https://github.com/rootSunc/CNEquity, pinned commit
`1650e384a3fd1f67a70144a489acc91432f1df27`, version **0.11.0**.

External sidecar: `D:/QuantForge/external/cnequity-etf-quant-v1`.
Source is detached at the audited commit with clean tracked source. Isolated
venv installed the 40 production lock packages; no dev packages or global quant
installation. `pip check`: no broken requirements. Runner verify:
`PINNED_SOURCE_PASS`.

Upstream uv.lock SHA256:
`0404b9f66a9bc860117deba2c9ee969568b8c4577341ecdccabe04a71c186b96`.
Build tools separately pinned to setuptools80.9.0/wheel0.45.1 with hashes.
The original quant-research Docker was not rebuilt or modified.

Actual metadata smoke:

- Started `2026-09-27T12:02:05.682685+00:00`.
- Completed `2026-09-27T12:07:33.801575+00:00`.
- Result `NETWORK_METADATA_SMOKE_BLOCKED`, exception `RemoteProtocolError`.
- Strict upstream SSLContext retained. No verify=False, certificate bypass,
  provider switch or claim of a successful real network smoke.
- External evidence:
  `D:/QuantForge/external/cnequity-etf-quant-v1/logs/metadata_smoke_20260927T120205.json`.
- Future wrapper supplies the existing upstream client with an explicit 30s
  timeout; that wrapper was NOT rerun as a successful smoke.

No lake was initialized and no genuine normalized export was admitted.
Admitted datasets: **none**. All seven required datasets are blocked: calendar,
stock bars, membership, ETF bars, instruments, trading status and CSI300.
Snapshot ID, cutoff, dataset row counts, actual adjustment exact/rejected counts
and actual export hash status: **null/unavailable** (not zero/synthetic values).
`strict_adj=True` and `adj_is_exact=true` are enforced in code/tests, but real
adjustment admission is unverified. Source C real coverage remains unknown.

Actual external runtime `D:/QuantForge/runtime/etf-quant-v1` contains only a
verified failed-attempt generation, not a successful account:

- Run ID `20260927T120733_76c804e54626`.
- Failure manifest SHA256
  `48e8a9558d0fc267abd03a9fe0980baf055aa5e282707b6da5da18e56f334fe2`.
- Status `DATA_ADMISSION_BLOCKED`, reason `CNEQUITY_RUNTIME_SMOKE_BLOCKED`.
- No latest-success, model output, epoch, holdings, trade or NAV was published.

## Source C / frozen models

`INTERNAL_SHENWAN_INDUSTRY_SERIES_V1`, construction
`INTERNAL_EQUAL_WEIGHT_SHENWAN_SERIES_V1`, **NOT OFFICIAL SHENWAN INDEX**.
Equal-weight exact-adjusted constituent returns, recursive base1000. Minimum
five valid constituents and 80% of all eligible members. No interpolation,
ffill, synthetic zero returns/OHLC or hidden rebasing after a broken prefix.
Original classification codes are preserved rather than guessed official
indices. Membership PIT is `HISTORICAL_MEMBERSHIP_PIT_UNPROVEN`; historical
available_at/source_published_at remain null. Warmup/training/engineering only.

Strategy version `ETF_QUANT_V1`. Actual runtime strategy hash: **null**.
Public default specification SHA256 (configuration only, not an admitted run):
`ab1b0b1bf182893e5e750abf4bf560692796001de20b7311d60c8f4d9a91089c`.

- Three independent Ridge models, alpha0.01, raw X, six calendar months per
  horizon label cutoff, minimum30 valid training dates.
- H10: `d10,p5,align,vc,dd20`.
- H40 and H120 each: `d5,d10,d20,d60,d120,p5,p10,p20,p60,p120,align,v5,v20,vc,rev5,rev10,dd20,dd60,rsi`.
- Same-date full-universe excess-return target. Feature date < signal date;
  per-horizon label end <= signal date, checked before reading target values.
- Population z-score independently by horizon/date before fusion .25/.50/.25.
  Descending score, ascending original code ties, Top5.
- Foundation capped softmax35%; redistribute only to uncapped names.
- Rebalance only on final executable set change / initial build.

Tests verify factor parity, independent horizons, maturity/no lookahead,
determinism, z-score-before-fusion, ranking, caps, accounting and rounding.
No Validation data is a fixture. No formal historical replay or warmup
performance is generated.

## Mapping and account

Default `VERIFIED_MAPPING_REGISTRY_V1` is empty. VERIFIED mappings **0**;
admitted/distinct executable ETFs **0**. Twenty-session amount admission:
`NOT_EVALUATED`. No fuzzy names, fabricated ETF codes, evidence or dates.
Mapping readiness: `MAPPING_ADMISSION_BLOCKED`; Shadow: `NOT_STARTED`.

Configured initial capital: CNY10,000. Actual cash, market value, equity,
holdings count, returns, drawdown, Sharpe and turnover: **null**, account has not
started. Actual holdings/trades/NAV arrays are empty. There are zero actual
fills/NAV points, not a zero-value or CNY10,000 funded account.

User-authorized time semantics: persist T0 intent first; use genuine finalized
T1 raw OPEN at T1 EOD, market_execution_at=09:30, executed_at/processed_at=actual
processing time. Missed T1 blocks rather than replaying late. First epoch starts
at actual all-gates-PASS time, no pre-epoch NAV. No real intent was executed.

Commission3bps/slippage5bps each side, stamp duty0/minimum0 explicitly modeled
and configurable. Lot100 configurable, floor, SELL-before-BUY, cost-aware cash,
leftovers preserved/no negative cash. Current finalized raw close required for
valuation; no stale/future-price fallback. Consumed economic dataset and
instrument evidence is frozen; unknown listing dates are never invented.

## API / Dashboard verification

ETF API built-in Node only, local127.0.0.1:3312, read-only GET/HEAD/OPTIONS;
writes405. Exact local CORS, external-root containment, closed IDs, all-file and
pointer hashes, public DTOs only, sanitized errors. No Research API changes.

Under `/api/etf-quant/v1/`:

`status`, `strategy`, `models`, `health`, `rankings/10d`, `rankings/40d`,
`rankings/120d`, `rankings/fusion`, `portfolio/summary`, `portfolio/holdings`,
`portfolio/nav`, `trades`, `mappings`, `benchmark/csi300`.

Dashboard eight routes under `/etf-quant/`:
`overview`, `portfolio`, `rankings`, `factors`, `mappings`, `trades`, `benchmarks`,
`health`. Independent ETF capabilities/schema/data port; original Research
contracts/navigation remain. No automatic mock fallback; all response
generations must match. Existing direct dependencies/npm lock unchanged;
pnpm lock converted from that lock.

Actual browser QA visited all eight routes against the genuine failed runtime:

| Surface | Actual result |
|---|---|
| Overview | DATA_ADMISSION_BLOCKED; configured budget, not funded equity |
| Portfolio / Holdings / NAV | Null account, empty holdings, no curve |
| Rankings | Empty in all four horizons/fusion; Top20/show-all UI tested |
| Factors / Ridge coefficients | Frozen5/19/19 names; coefficients null |
| Mapping | MAPPING_ADMISSION_BLOCKED / NO_VERIFIED_EVIDENCE |
| Trades | Empty, delayed-processing disclosure visible |
| CSI300 | NOT_STARTED, no invented curve |
| Health | DEGRADED / CNEQUITY_RUNTIME_SMOKE_BLOCKED; real failure time |

Research homepage independently showed API DISCONNECTED while ETF health
remained usable. Desktop/mobile navigation verified; temporary viewport reset.
Computer-use skill required visible UI verification and proof capture.
Screenshot outside Git:
`D:/QuantForge/temp/etf-quant-v1-ui-proof/health-blocked.png`.
Local health link: http://127.0.0.1:5173/etf-quant/health.
NASDAQ Composite and S&P500 remain **DEFERRED**.

A separate temporary **synthetic** two-day Python-to-Node contract test passed
with explicit not_real_results=true. Its models/fills/NAV never entered the
actual runtime or formal report. It proves serialization, not real admission.

## Test matrix and known baseline blocker

All quant computations/tests ran in existing quant-research Docker, in copied
integration sources at `/tmp/etf-regression-v1.GjkpZwWJ`, not the main bind.
PYTHONDONTWRITEBYTECODE=1, python -B, no pytest cache. Nothing was installed.

| Category | Passed | Failed/errors | Skipped |
|---|---:|---:|---:|
| ETF core/config/factors/models/public mirror | 73 | 0 | 0 |
| Source C/export | 16 | 0 | 0 |
| Mapping/sidecar contract | 13 | 0 | 0 |
| Foundation simulation | 6 | 0 | 0 |
| Runtime/shadow/host transport | 22 | 0 | 0 |
| ETF Python total | 130 | 0 | 0 |
| ETF Node API | 48 | 0 | 0 |
| Security scanner tests | 4 | 0 | 0 |
| Dashboard (existing + ETF) | 77 | 0 | 3 |
| Safe existing Python Research regression | 226 | 0 | 0 |
| Existing Research API | 18 | 0 | 7 |
| Sidecar real metadata network smoke | 0 | 1 blocked | 0 |

Combined ETF + safe Research: **356 passed**, two known legacy warnings.
Dashboard typecheck/lint/production build PASS. Research API typecheck PASS.
Original Foundation78 tests are retained. Scoped Decimal precision fixture
prevents framework import side effects in ETF assertions without changing old
assertions; runtime fixes its own calculation precision and restores caller
context. No failing test was removed, disabled or weakened.

Default full offline pytest: **575 passed, 8 failed, 44 errors, 2 skipped,
17 deselected**, 20.43s. THIS IS NOT A FULL-SUITE PASS.
Untouched integration base457b comparison, same data-free environment:
**445 passed, same8 failed/same44 errors, 2 skipped, 17 deselected**.
The added130 ETF tests explain the increase in passing count. Exact failures
are old frozen-data-dependent audit/preparation/split/protocol tests.

Required ignored fixtures absent from that base include
`data/raw/etf_evidence/index_evidence_manifest.json`,
`data/processed/shenwan/sector_admission.json` and exact frozen canonical/calendar
inputs. They were not manufactured, replaced with current data, copied from
sealed performance, or made to pass via skip/deletion. No further Research
mutation is authorized to fix this pre-existing baseline issue.

Original skip reasons:

- Two Python framework data checks: DATA_NOT_INITIALIZED for Hikyuu and
  RQALPHA_DATA_NOT_INITIALIZED for RQAlpha bundle in the copied test setup.
  Explicit recheck:15 passed,2 skipped. Default marker config deselects17
  integration tests; config unchanged.
- Dashboard3 real-artifact tests require both live Research API base URL and
  external formal Development report root; neither supplied.
- Research API7 integration tests require external formal Development report
  root; not supplied. Unit tests ran normally. No sealed root supplied.

Reproducible safe commands (inside copied Docker source for Python):

```text
python -B -m pytest tests/etf_quant strategies/sw_sector_rotation/tests tests/test_sector_development_integrity_audit.py tests/test_development_iteration1_protocol.py tests/test_development_iteration1_run.py -q -p no:cacheprovider --tb=short
python -B -m pytest -q -p no:cacheprovider --tb=no
services/etf-quant-api: node --test
services/etf-quant-runner: node --test security-audit.test.mjs
services/research-api: pnpm test && pnpm typecheck
dashboard: pnpm typecheck && pnpm lint && pnpm exec vitest run --maxWorkers=1 && pnpm build
```

## Security, isolation and next safe action

Read-only scanner covers tracked/new files, history blobs/all local refs,
credential-pattern candidates, forbidden data/env paths, >500KB files, sensitive
sealed filenames and firewall diff. No credential values are printed.
Reviewed old README xxxx/yyyy placeholder exemption is exact-line SHA only,
not a broad credential-pattern exemption. Scanner tests validate this behavior.
This is a fallback pattern/path audit, **not a third-party security certification**.
Final post-commit counts are provided in the final task response.

Content secret/data/firewall gates PASS: no secret candidates, tracked runtime/
CNEquity data/.env, leaked credentials, new large unapproved blobs or immutable
Research path changes. Software/data redistribution are different: source data
licensing unresolved, repository-wide ownership/license needs human review.
Public reuse **REVIEW_REQUIRED**; GitHub push **BLOCKED** by full-test gate.

Docker retained image
`sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5`.
Python3.12.11/Hikyuu2.8.2/RQAlpha6.4.0/AKShare1.18.88/NumPy2.3.5/Pandas2.3.3/
SciPy1.16.3 unchanged. No image/compose/mount/dependency/environment changes.

CONTRACT_IMPLEMENTATION_DISCREPANCY: CSV+JSON export intentionally replaces
suggested Parquet, preserving Docker without pyarrow. UI files use existing
TanStack layout with a separate ETF namespace rather than restructuring the
existing Research application. Delay-booking semantics are explicitly approved
by the user, not a claim of timely T1 execution evidence.

NEXT SAFE ACTION: resolve the pinned upstream metadata failure without TLS
bypass/provider substitution; prepare only an authorized minimal real lake and
official VERIFIED ETF evidence. Independently supply exact old offline frozen
fixtures (or obtain explicit direction for their test classification), rerun
required tests before conditional integration-only sync. No automatic retry,
real cycle, Validation, Final OOS, V2, model tuning or scheduler is running.

MAIN WORKTREE WAS NOT MODIFIED

FROZEN F1 RESEARCH WAS NOT MODIFIED

VALIDATION PERFORMANCE WAS NOT READ

VALIDATION REMAINS SEALED

FINAL OOS REMAINS SEALED

SHENWAN CANONICAL DATA WAS NOT MODIFIED

EXISTING QUANT-RESEARCH DOCKER WAS NOT MODIFIED

CNEQUITY RUNS ONLY IN AN ISOLATED SIDECAR

HISTORICAL WARMUP PERFORMANCE WAS NOT PRESENTED AS FORWARD SHADOW PERFORMANCE

NO BROKER CONNECTION EXISTS

NO REAL ORDER PATH EXISTS

NO LEVERAGE OR SHORTING EXISTS

NASDAQ COMPOSITE IS DEFERRED

S&P 500 IS DEFERRED

NO SECRET VALUE WAS COMMITTED

NO CNEQUITY MARKET DATA WAS PUSHED TO GITHUB

MAIN WAS NOT PUSHED OR MERGED
