# Public repository hardening report — 2026-10-03

This engineering pass uses owner-authorized **MIT** licensing. It introduces a
portable contributor path while preserving the existing quantitative implementation
and immutable historical evidence. Mypy is deliberately staged; the legacy debt
is counted, not described as zero.

## A. Baseline findings

`origin/main` was fetched and verified at
`bdc69bb3a1fb360c773515c395db8b5c1e3cc9ff`; the supplied managed worktree was clean
and isolated. The repository API confirmed `public` visibility. Development reused
that isolated worktree on `engineering/public-repo-hardening-v1`, without editing
deployed/runtime checkouts.

Root LICENSE, workflow files, pyproject, Ruff, Mypy and pre-commit were absent.
An existing `pytest.ini` was found and its marker/default integration policy was
carried into pyproject rather than maintained as conflicting configuration.
AST measurement found 197 Python files, 39,030 lines, 1,925 functions, 535 complete
signatures (27.79%) and 27.43% function docstrings. The reported Python BOM was
confirmed in `tests/etf_quant/test_proxy_execution_policy.py`. There were 31 tracked
text files containing CRLF; most are immutable/historical artifacts.

The before inventory also confirmed large modules, machine-specific operational
paths, external-runtime fixture dependencies and absent synthetic demo/CI. Existing
Node and scientific versions were preserved; high version numbers alone were not
treated as defects.

## B. License status

The root LICENSE contains the complete MIT grant, with the repository owner's
public handle and contributors. README, third-party notices and component license
metadata agree. The bundled shadcn/ui MIT copyright/permission notice retains its
exact original SHA-256. External CNEquity is not vendored and retains Apache-2.0;
scientific distributions retain their existing notices. Pattern/UX references
identified in dashboard notices contain no copied Apache source. Market-data
redistribution clearance remains separate and REVIEW_REQUIRED.

## C–D. Python foundation, Ruff, Mypy and pre-commit

Tool-only pyproject, EditorConfig, Git attributes, pinned hooks and both direct
developer requirements and a fully pinned tested dependency resolution are present.
No installable-package conversion was introduced.

Ruff correctness/import/modernization rules and selected B/SIM rules pass. The
formatter checks 155 unbound Python files. Exact certificate-bound file exceptions
preserve the 47 Python source files listed in the existing code-integrity manifest.
Their existing lint categories are enumerated per file; they remain Mypy-checked.
No entire production directory is lint-excluded. Pandas elementwise comparisons
and validation-side-effect assignments have local, reasoned exceptions.

Mypy checks source, strategies, research, services, scripts and the demo. Strict
new-code/schema/calendar/notification boundaries have zero diagnostics. The staged
gate passes with **530 exact legacy path/code/message diagnostics** in
`config/engineering/mypy-baseline.json`; regressions and stale allowances fail.
With the same configured legacy scope, baseline diagnostics were 532. Raw Mypy
still reports these 530 errors: the passing result is the staged gate, not a claim
of full strict typing. No `ignore_errors` application override or new widespread
`Any`/`type: ignore` policy was added. Optional unstubbed framework imports have
explicit missing-import overrides.

All nine configured pre-commit hooks pass. First-run hook environments were built
in the independent developer container, with Git metadata mounted read-only.

## E. Annotation and docstring improvement

Complete signatures increased from 535/1,925 (27.79%) to 558/1,934 (28.85%).
Function docstring coverage increased from 27.43% to 27.77%. These are full-source
measurements including tests/private helpers, not percentages from a selected
successful directory. Improvements cover calendar iteration/construction, provider
and request errors, existing research Ridge inputs, dataclass initialization,
new inventory/type-check boundaries and the synthetic example. Existing certificate
boundaries were not edited to inflate coverage.

## F. Encoding and line endings

The sole Python BOM was removed. New/changed unbound source uses UTF-8/LF and Git
has an explicit LF policy. The 31 remaining CRLF-containing text artifacts retain
their certified/historical bytes; exact paths and encoding lists are in the health
inventory. Certified source/config/metadata have `-text` Git rules and text-hook
exceptions so checkout/index conversion cannot invalidate hashes. No binary was
normalized and no certificate was rewritten.

## G. Print/logging audit

Baseline: 88 intentional CLI/report-output calls and 16 test/output calls. After:
94 intentional CLI/report-output calls and 16 test/output calls. The additional
calls are explicit synthetic-demo and tooling stdout interfaces. Reusable library
code has no internal debug/status prints requiring replacement; the Feishu example
and existing runtime CLI output remain intentional. New internal logging policy
uses `logging.getLogger(__name__)`, with no import-time global configuration.
DEBUG_PRINTS_REMAINING=0; print classifications were reviewed, not mechanically
converted to logging.

## H. Large modules and refactor decisions

Evidence schema: 982 lines, checksum-bound; proxy mapping: 747 lines,
checksum-bound; PIT builder: originally 865 lines, expanded by readable formatting.
Schema classes own their validation/serialization contracts; proxy selection owns
its deterministic assignment policy. Splitting these solely for line count would
invalidate the current implementation certificate and introduce unnecessary public
re-export/provenance changes. No large-file split was performed. The builder's
stage orchestration and existing helpers were retained; checkout resolution and
optional path configuration were improved without copying strategy logic.
This is a justified deferral, not a claim that these files were refactored.

## I. Portability and paths

The portable suite/demo requires no developer drive or runtime root. Three PIT
scripts resolve imports relative to the actual checkout. Explicit
`ETF_QUANT_PIT_ROOT` / `ETF_QUANT_PROXY_ROOT` overrides support other machines;
`ETF_QUANT_CONSOLE_CONFIG` supports machine-local launcher configuration and
`-Config` retains precedence. Existing Windows operational defaults remain valid.
Historical paths and containment-test fixtures are preserved; these are classified
in the inventory rather than replaced indiscriminately.

## J. Developer environment

The existing devcontainer entry point now uses an independent developer image
with digest-pinned Python 3.12.11 and Node 24.19.0 bases, pnpm 11.25.0 and the tested
Python lock. It neither starts nor rebuilds the frozen `quant-research` service.
The final Dockerfile was built successfully. Windows uses Docker without a host
virtual environment/global scientific install. Node 22 compatibility was not
empirically established, so Node/pnpm requirements were not lowered.

## K. Minimal synthetic demo

`python -m examples.minimal_demo` passes with fixed seed 10719. Eight artificial
identities exercise existing mature-label/six-calendar-month/30-date training,
independent Ridge horizons, population z-scores, 0.25/0.50/0.25 fusion, ranking and
35%-capped Top5 sizing. It uses the existing production functions directly.
It is explicitly SYNTHETIC DEMO ONLY, with no evidence admission, broker, real
data, orders, account, NAV or profitability claim. A determinism/sizing test passes.

## L–M. Portable and maintainer test tiers

Portable command: `python -m pytest -m "not external_runtime"`.
Result: **983 passed, 2 skipped, 99 deselected**, in 54.78 seconds with no network
and no runtime mount. It covers numerical models, fusion, sizing, temporal guards,
mapping, evidence validation, transport fixtures and data integrity. The small
HDF5 preflight fixtures are generated, so PyTables was added to the developer lock
instead of deselecting those meaningful tests.

Private-evidence/verified-local-data tests carry explicit external_runtime markers;
pure tests in the same modules remain portable. Framework/integration directories
are not imported during portable collection because deselection otherwise happens
too late. Maintainer collection and original assertions remain available.

Official frozen-image ETF acceptance with read-only source/runtime mounts and
`--network none`: **612 passed, 1 skipped**, in 603.38 seconds. No scientific
dependencies, data or production containers were modified by testing.

## N. GitHub Actions

Four jobs cover repository hygiene, portable Python/demo, frontend/APIs and
Windows launcher syntax/source checks. Actions are pinned to verified immutable
checkout/setup-python/setup-node/pnpm-setup SHAs. Triggers are PRs and main pushes,
permissions are contents:read, superseded runs are cancelled. No deployment,
pull_request_target, secrets, private data, runtime DB or sealed performance is used.
Hosted results and merge identities are recorded below after verification.

[Foundation CI run 37046519290](https://github.com/WynterYaxley123/quant-trading/actions/runs/37046519290)
completed successfully: hygiene, python-portable, frontend-and-apis and
windows-launcher all passed. The foundation was merged through PR #5 using normal
merge commit `c2f19fa69de145891c598dfbbca4f216f7af7c28` after these checks.

## O–P. Documentation and contributor experience

README now has a data-free contributor start, real quality commands and MIT status.
CONTRIBUTING explains portable/maintainer tiers, hook installation, staged typing,
certificate exceptions and platform versions. The active docs index points to
these guides; docs/archive is a logical archive linking 33 historical audit/handoff
documents without moving, deleting or rewriting any original evidence. No document
was declared superseded/duplicate merely by guessing from its name.

## Q. Security and data audit

The native source/history audit passes with zero tracked/new/history credential
candidates, forbidden data paths or sealed performance paths. The historical
blanket infrastructure firewall was replaced with direct validation of the
existing certified implementation hashes; no protected file changes are allowed.
New tooling, CI and demo files were also inspected. No raw data, curated data,
runtime database, Shadow payload, `.env`, binary dependency, node_modules, virtual
environment or build output was committed. Only relative source locations and
counts are published in the inventory.

## R–S. Frozen strategy and Shadow integrity

Every file in `autonomous_code_integrity_v1.json` retains its recorded SHA-256.
Candidate, configured model universe, scientific requirements, Docker compose,
CNEquity pin, PIT policies and T/T+1 accounting remain unchanged. ETF acceptance
and observer security tests pass. No broker or real-order path was introduced.

Formal Shadow namespace: 6 files before, 6 after, zero differing path/hash entries.
Epoch/signal/intent/fill deltas are all zero. No one-shot cycle, market refresh or
sealed-performance access was used as an engineering test.

## T. PRs and merges

Foundation/portability/maintainability/contributor changes:
[PR #5](https://github.com/WynterYaxley123/quant-trading/pull/5).
Logical commits separate tooling/license, source/test/CI and documentation.
The final factual inventory/report is a second reviewable documentation PR based
on that new main commit. Only normal GitHub merges are used; no force push or
history rewrite. The final documentation PR remains subject to the same hosted
quality gates before its merge; its merge record is preserved in GitHub/Git.

## U. Before/after metrics

| Metric | Before | After |
| --- | ---: | ---: |
| Python files | 197 | 202 |
| Python lines, including comments/blanks | 39,030 | 45,101 |
| Complete signatures | 535 | 558 |
| Complete-signature coverage | 27.79% | 28.85% |
| Function docstring coverage | 27.43% | 27.77% |
| Intentional CLI/report prints | 88 | 94 |
| Test prints | 16 | 16 |
| Internal debug prints | 0 | 0 |
| Python BOM files | 1 | 0 |
| CRLF-containing text artifacts | 31 | 31, byte preservation |
| Comparable legacy Mypy diagnostics | 532 | 530 |
| Ruff diagnostics with the same final accepted scope | 347 | 0 |
| Portable pytest result | not established | 983 passed |
| Hosted CI jobs | 0 | 4 |
| Runnable synthetic demo | absent | passed |

Full function/module/class counts, largest files, path/print locations, document
classes and exact encoding lists are in [health-inventory.json](health-inventory.json).
LOC expansion comes predominantly from formatting compact one-line statements.
The initial unrestricted scan, before certificate exceptions and source cleanup,
reported 476 diagnostics. The comparable accepted-scope scan uses the archived
baseline with the final tool policy, without including the newly introduced tools.

## V. Remaining limitations

- 530 explicit legacy Mypy diagnostics remain. The project has a regression gate,
  not universal strict typing. Only modest legacy annotation/docstring improvement
  was possible while preserving the current certified implementation bytes.
- 47 certificate-bound Python files retain existing formatting/named lint debt.
  Their cleanup requires a separately reviewed certificate transition.
- Existing operational fallback paths still describe the configured machine;
  portable unit/demo flows do not use them.
- Optional real-artifact/framework tests remain a maintainer responsibility.
- Node 22 compatibility and market-data redistribution are not claimed.
- The source/history scanner is a built-in pattern/path/hash audit, not an external
  security certification. Archive classifications are explicit heuristics.

## W. Final flags

```text
PRIMARY=PUBLIC_REPOSITORY_ENGINEERING_HARDENING_COMPLETE_WITH_DOCUMENTED_STAGING
OWNER_LICENSE_DECISION=MIT
LICENSE_FILE=PASS
LICENSE_OWNER_DECISION_REQUIRED=FALSE
SOURCE_DATA_REDISTRIBUTION_CLEARANCE=REVIEW_REQUIRED
PYPROJECT=PASS
RUFF=PASS_ACCEPTED_SCOPE_CERTIFICATE_EXCEPTIONS_DOCUMENTED
MYPY=PASS_STAGED_GATE
TOLERATED_LEGACY_MYPY_DIAGNOSTICS=530
STRICT_AND_NEW_CODE_MYPY_DIAGNOSTICS=0
PRE_COMMIT=PASS
BOM_NORMALIZATION=PASS
LINE_ENDING_POLICY=PASS_CERTIFIED_BYTES_PRESERVED
DEBUG_PRINTS_REMAINING=0
LOGGING_POLICY=PASS
LARGE_FILE_REFACTOR=JUSTIFIED_NOT_NEEDED_UNDER_CURRENT_CERTIFICATE
PORTABLE_PATH_CONFIGURATION=PASS
DEVELOPER_MACHINE_PATH_DEPENDENCY_FOR_PORTABLE_FLOW=FALSE
MINIMAL_SYNTHETIC_DEMO=PASS
MINIMAL_DEMO_EXTERNAL_DATA_REQUIRED=FALSE
PORTABLE_PYTHON_TESTS=PASS
PORTABLE_PYTHON_TESTS_EXTERNAL_RUNTIME_REQUIRED=FALSE
EXTERNAL_RUNTIME_TEST_TIER=PRESERVED
FRONTEND_TESTS=PASS
FRONTEND_TYPECHECK=PASS
FRONTEND_LINT=PASS
FRONTEND_BUILD=PASS
RESEARCH_API_TESTS=PASS
ETF_API_SECURITY_TESTS=PASS
ETF_FULL_REGRESSION=PASS
GITHUB_ACTIONS=PASS
CI_PORTABLE_PYTHON=PASS
CI_FRONTEND=PASS
CI_REPOSITORY_HYGIENE=PASS
CI_REQUIRES_PRIVATE_RUNTIME=FALSE
CI_REQUIRES_SEALED_DATA=FALSE
CI_REQUIRES_SECRETS=FALSE
DOCS_INDEX=PASS
HISTORICAL_DOCS_ORGANIZED=PASS_LOGICAL_ARCHIVE
README=PASS
SECRET_AUDIT=PASS
RAW_DATA_GIT_AUDIT=PASS
RUNTIME_DATA_GIT_AUDIT=PASS
SEALED_DATA_AUDIT=PASS
FROZEN_STRATEGY_CHANGED=FALSE
CN_EQUITY_PIN_CHANGED=FALSE
SHADOW_EPOCH_DELTA=0
SHADOW_SIGNAL_DELTA=0
SHADOW_INTENT_DELTA=0
SHADOW_FILL_DELTA=0
BROKER_ENABLED=FALSE
REAL_ORDER_PATH=FALSE
MAIN_PR_MERGES=NORMAL_ONLY
FORCE_PUSH_USED=FALSE
HISTORY_REWRITTEN=FALSE
REMAINING_ENGINEERING_BLOCKERS=NO_LOCAL_GATE_FAILURES_LEGACY_DEBT_DOCUMENTED
```
