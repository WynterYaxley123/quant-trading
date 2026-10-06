# SWL2 industry forecast source transition

Base: b28c24518de36fb0045a5f4313916e65d4ac3b54. Branch:
refactor/swl2-industry-forecast-only. This source delivery promotes no deployed
checkout, enables no task and creates no live forecast or ETF event. The actual
merge identity/time is resolved later from first-parent main history; runtime
activation binds source/model/time independently and cannot publish that day.

## Preserved science and history

The user explicitly approved preserving the frozen V1 universe of 107 and V2
warmup universe of 124. Taxonomy size and ETF mapping coverage are separate.
All 91 pre-existing report/research/config/archive artifacts selected from base
remain unchanged. Eight replaced current documents were archived as exact Git-base
bytes with original paths, source commit and SHA256 in the documentation map.
Historical source certificates retain their bytes. The new delta carries every
prior deployment change and binds the unchanged installation parent and deployment
certificate; it never pretends current source had historical certification.

V1 factors, alpha .01, six-month raw-X fits, target centering and fusion remain
unchanged. V2's alpha30/m12 raw-X prediction was extracted once from its legacy
runtime and compared against the actual base source on synthetic 124-industry
inputs: exact model/coefficient/ranking equality, raw-score tolerance 1e-12.
No ETF mapping/sizing/accounting call is made by either active adapter. Export
regression removes ETF/benchmark payloads and still loads industry facts.
No market backtest, sealed V1 performance, real Final OOS rerun, retuning or
new Validation operation runs in this engineering workflow.

## Publication and evaluation regressions

Synthetic tests cover dynamic official first-session boundaries, current finalized
observation after close, no retrospective/future/partial publication, complete
admitted rows, immutable original scores, same-day retry without refitting,
source/model mismatch, stale mutex metadata, before-pointer journal recovery,
concurrent runner exclusion before factual loading and tampered generation rejection.
Namespace symlink escapes block before IO. Event bodies use content-addressed immutable
objects with a compact hash-chain index; a full H120 outcome regression passes with
a 4 KiB index budget even though bodies exceed that budget. Each body is read with
a 512 KiB bound, independent of the 16 MiB / 10,000-event index bound.
H10/H40/H120 use exact sessions and finalized complete paths; missing middle
sessions, NaN closes, changed signal facts and segment gaps cannot become outcomes.
Python-created full forecast/evaluation generations are read unchanged by Node.

RankIC uses average ties against same-date excess-return targets. Spreads, Top5
overlap, rank errors and rolling20 remain descriptive, with empty/constant nulls.
Common dates/horizons additionally use shared industries with equal realized
returns; each model retains its frozen primary universe. No significance winner,
tradable NAV, capital, lot, cash allocation or transaction-cost path is introduced.
The factual type is RECONSTRUCTED_SWL2_EQUAL_WEIGHT, not official index bars.

## Local validation

Executed in the independent Docker developer environment, using only synthetic
facts and read-only Git metadata. Native-Git clone checks avoid leaking worktree
GIT_DIR/GIT_WORK_TREE into test-created repositories.

| Gate | Observed result |
| --- | --- |
| Full portable Python | 1299 passed, 2 skipped, 99 external-runtime deselected |
| Focused forecast/runner | 25 passed, including Python → Node generation parity |
| Forecast plus export-reader regression | 42 passed |
| Industry API | 16 passed, no skips |
| Combined legacy/industry API, scheduler, launcher/security tests | 162 passed, 6 Linux platform skips |
| Historical Research API | 63 passed, 7 optional integration skips |
| Frontend full suite | 138 passed, 3 optional real-artifact integration skips |
| Frontend typecheck/lint/production build | PASS; existing-size warning for bundled index |
| Mypy staged gate | PASS; 168 unchanged reviewed legacy diagnostics; strict/new code zero |
| Ruff lint / format | PASS; all 301 active Python files formatted |
| Pre-commit all tracked files | PASS, all nine hooks |
| Performance contracts | 16 passed; synthetic benchmark ran, no timing threshold |
| Old and new synthetic demos | PASS; new demo fits full 107/124 and matures all three horizons |
| Independent developer Docker build | PASS using pinned Dockerfile/requirements, no deployed-image change |
| Documentation reference audit | PASS, zero broken links or changed archived bytes |
| Built-in source/history security audit | PASS, zero secret candidates, forbidden runtime paths or source firewall drift |
| Industry PowerShell launcher parser | PASS on host; no service started |

The six combined Node skips are Windows-only checks; hosted Windows CI runs the
launcher/task-definition checks. Python optional skips/deselection and seven
Research API / three frontend external integrations are not PASS claims for
private-data acceptance. No private runtime is mounted for quantitative tests.
Production console/browser integration needs operator-installed dependencies and
permitted external metadata; it is not exercised against live QuantForge here.

GitHub delivery, clean committed-checkout regression and post-merge verification
are reported separately with their actual commit identities after completion.
