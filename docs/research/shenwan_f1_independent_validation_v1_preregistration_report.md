# F1 Independent Validation V1 preregistration report

## FINAL STATUS

VALIDATION PREREGISTRATION COMPLETE. This is preregistration only; no formal
Validation run, actual Validation training set or maturity diagnostic exists
from this task. Validation and Final OOS remain SEALED. Post-commit seal and
final clean-state evidence/commit identities are recorded in the separate
handoff and final response, following the repository's two-commit convention.

## Git and Docker preflight

Branch `experiment/sw-sector-index-research-baseline`; initial HEAD
`e388fdce6d846019b854704a1967ca0a6b12afd6`. Worktree and index were clean
before changes. All source commits were checked as ancestors of HEAD. Only
new F1 preregistration/config/test/document files are staged; historical
research and strategy core have no modifications. The preregistration
commit is the commit containing this report; its full SHA is recorded by
the subsequent handoff (a committed file cannot contain its own SHA).

Both quant-research and quant-jupyter run normally. Frozen image:
`sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5`.
Python 3.12.11; Hikyuu 2.8.2; RQAlpha 6.4.0; AKShare 1.18.88; NumPy 2.3.5;
Pandas 2.3.3; SciPy 1.16.3, verified from installed package metadata.
Mounts D:\quant-trading→/workspace and D:\quant-trading\data→/workspace/data,
command bash, entrypoint /usr/local/bin/_entrypoint.sh, user mambauser,
working directory /workspace and quant-trading_default network match the
approved operational record. No rebuild, dependency install or data download.

HOST_PORT_OPERATIONAL_EXCEPTION acknowledged: Windows HNS excluded TCP
9128–9227 covered old host 9200/9201. Approved host publication is now
127.0.0.1:19200→container 9200 and 127.0.0.1:19201→container 9201.
Container internal ports are unchanged. Local override:
`D:\QuantForge\temp\quant-trading-host-port.override.yml`; base Compose:
`D:\quant-trading\docker-compose.yml`. Every Compose invocation used both
files; no recreate occurred. RESEARCH_ENVIRONMENT_CHANGED=false;
HOST_PORT_PUBLICATION_CHANGED=true. Existing image-only environment gates
accept this distinction; no historical protocol was patched to accommodate it.

## Source provenance, selection and drift audit

Sole Development source: HORIZON_COMPONENT_REPLACEMENT_V1. Formal result
`91b89a97a9a2b54e133d2979c695d7c3da22626e`; handoff
`e388fdce6d846019b854704a1967ca0a6b12afd6`; implementation
`fb207b8b868a3aaceed568d4a8e1b62340371bff`; preregistration
`95e54ee6461b315b51f5ca7cc17cd985caa96a1d`; preregistration handoff
`d28e42bf7bb09fcc5b9faa19ab3ff0a96429c1cd`; canonical protocol hash
`4267d73f38fc8353002459b24640148cc49c4e5777b364eb14ca84404aef9fa7`.
This is a semantic protocol hash, distinct from its Markdown file hash.

First/rerun roots are frozen in machine config. Both metadata byte hashes,
the common 21-file content manifest and every content SHA were verified:
42/42 matching. Formal summary/source report/handoff agree: F0 primary
metrics 0.08810651455546813 / 0.037216498377093545; F1
0.09349328088119589 / 0.044456330026128345, advanced for further review;
F2 0.09486741148701808 / 0.015939832916397074, not advanced.
Next gate H10_REPLACEMENT_ONLY_SUPPORTED. F1-only Human Review is recorded
in the selection trace. F2's spread deterioration prevents its admission;
no H40/H120 replacement or backup candidate enters the new budget.

V1_F1_CANDIDATE exactly preserves H10_C `[d10,p5,align,vc,dd20]`, C0_H40,
C0_H120. V0_CONTROL preserves C0_H10/C0_H40/C0_H120. Every C0 factor list
is the original ordered 19. Both use raw-X NumPyRidge alpha .01, six
calendar months anchored at each horizon label cutoff, min30 dates,
same-training-date excess target and absolute evaluation labels. Existing
population z-score fusion, .25/.50/.25, Top5 and ascending code tie-break
remain unchanged. Runtime verifies factor mappings against the original
protocol and eleven frozen implementation/document fingerprints. No candidate
drift, retraining of Development, factor/model/sign/parameter/weight search.

## Previous blocker resolution and training admission

PREVIOUS BLOCKER: VALIDATION_PURGE_TRAINING_SEMANTICS_BLOCKER.
RESOLUTION: HUMAN_REVIEW_DECISION.
BLOCKER_RESOLVED_BEFORE_VALIDATION_OPEN=true.

PURGE1 EVALUATION ELIGIBILITY=false; TRAINING ELIGIBILITY=conditional true.
Purge1 is EVALUATION_EXCLUDED + CONDITIONALLY_TRAINING_ELIGIBLE, never an
evaluation sample. It must satisfy each horizon's legal maturity, as-of,
rolling window, minimum-data and existing feature/target validity rules.
Current formal label maturity is label_end <= current signal date after
close; last origin is calendar[signal_position-h], and origin < signal date.
This reuses `temporal_boundaries`, `training_window` and the core's existing
run_period semantics; no inequality or target-end definition was changed.

VALIDATION EXECUTION MODE=FROZEN_ALGORITHM_WALK_FORWARD / prequential.
The frozen Ridge algorithm refits at each future authorized signal date.
Earlier Validation observations can train later dates only after their
horizon labels mature, strictly chronologically. No Validation performance
may change the design. Data availability advances in time; research rules
stay frozen. This definition of independent Validation freezes candidate,
algorithm and gates before first performance view; it does not require a
static train-once holdout fit. Purge2 evaluation is excluded, but its Final
OOS training admission remains undecided pending separate OOS preregistration.

## Split and data snapshot policy

Formal Policy C: Development E001–100, Purge1 E101–220, Validation E221–280,
Purge2 E281–400, Final OOS E401–460. Three deterministic 20-date Validation
blocks: VB1 E221–240, VB2 E241–260, VB3 E261–280. Present Validation dates
E221–239: 2026-03-03–2026-03-27 (19); E240–280 (41) remain unknown/null.
No date extrapolation. The date-column-only projection was verified against
the existing 239-date prefix; it loaded no prices, targets or performance.
A future formal run requires all 60 ordinals and realized 10/40/120 labels.

Source snapshot is
`872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`.
Existing policy explicitly permits an append with unchanged U0, economic
history through 2026-09-18 and E001–239 prefix. Snapshot ID may then change;
configuration/split identities and historical economics may not. Future
actual snapshot/file hashes must be recorded; an alteration raises
SPLIT_REPRODUCIBILITY_REVIEW. Features see no prices after signal, training
labels must be mature at signal, evaluation labels cannot enter the model
early. No current Validation label maturity or actual training set was tested.
strictPit=false; FIXED_CLASSIFICATION_RESEARCH;
NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST; SECTOR_INDEX_RESEARCH_ONLY,
executable=false and tradable=false remain even after any future PASS.

## Independence audit

PASS within the retained local research record: Git history/file paths
across local refs contain no Validation/OOS result paths; current reports
contain 14 Development metadata records, all with both phases SEALED, no
Validation/performance-named path or formal result. Only the approved
Development sources' outcome artifacts were read, after metadata/hash
identity checks. Existing tests retain Development-only guards and synthetic
fixtures; the new tests use synthetic calendars/numbers/lifecycle records.
Project logs contain only README and .gitkeep, no retained execution log.
The live result-leak gate checks metadata, known performance filenames and
Validation/OOS paths without reading prediction/metric/label payloads.
It is invoked explicitly at preregistration; ordinary unit tests use tmp_path,
so future formal results do not make perpetual-absence assertions stale.

## Metrics, gates and policies

Original 15-metric contract: IC, RankIC, fused Top5 forward return, fixed-U0
return and spread for 10/40/120; raw horizon scores for IC/RankIC, absolute
evaluation labels, average-tie Spearman. Report mean/median/population std/
min/max and valid/null counts; missing complete-case data stays null with a
reason. Primary Weighted RankIC/Spread use .25/.50/.25 horizon means.
Overlapping labels do not establish independent statistical significance.

Unique VALIDATION_PASS requires strict positive V1 primary metrics, strict
improvement in at least one against V0 and no decrease in the other, no
horizon mean RankIC < -.02, at least 2/3 positive block Weighted RankIC and
at most 1/3 below -.02. Block spread is reported, not gated. Missing/nonfinite
required metrics cannot pass. Any failed gate means VALIDATION_FAIL with
specific reasons; no partial/near pass.

FAIL permanently leaves Validation OBSERVED. Redesign using its results is
POST_VALIDATION_DEVELOPMENT and cannot reuse that sample as independent
Validation. PASS makes only FINAL_OOS_PREREGISTRATION_ELIGIBLE: Human Review
and separate OOS preregistration are mandatory. Final OOS stays SEALED.

## Seals, opening and future training audit

Current validationOpened=false, first-open timestamp=null, state UNSEEN;
Validation/Final OOS SEALED; performance/result flags all false. Default
opening is denied. A future authorized first run must append a durable
UNSEEN→OBSERVED record before first value access with first-open UTC time,
protocol/candidate/phase/split hashes, execution commit and candidate source
commit. Opening identity is immutable and OBSERVED cannot reset. The current
module provides pure validation of this contract and no live opening/ledger
writer or model runner. Opened=true appears only in ephemeral synthetic tests.

For every future signal/horizon and both schemes, the integrity audit must
record window bounds, candidate/accepted dates and count, unmatured rejection
count, latest accepted origin and label endpoint, phase-source counts
(preDevelopment, Development, Purge1, earlier Validation), futureLeakCount=0,
and independently recomputable fixed-U0 row coverage. No real instance of
this audit is generated in preregistration.

## Hashes

- candidateDefinitionHash: `6c2b16555b6dfd5d848ea451b09e7b75f53da67747fc76fd052d93afd3ea156b`
- validationPhaseDefinitionHash: `28d3980e28b41b37d2a327aad6081e8312cf66d66762c13e33cc8ba814c8fa7f`
- splitPolicyHash: `3b6b2d754211169039439c8b377fd9eb26d5cb5db0f80d62cffc1d19c81a7038`
- canonical protocol SHA256: `2344cc685201476de957109b9fccc2681923e2c4591b5ed91740a56baf128410`
- config canonical hash: `39c603097c2cf49e61b610407dc0a7609a6b14426a125ead556ac9ed1008c9d8`
- protocol Markdown byte SHA256: `6f9c29669cb30f7bfa35133a66549e3e354617c99b6a10f27a807a569fdd20c5`

## Tests and historical immutability

Fresh pre-change targeted: 88 passed (Component Replacement protocol/runner,
Development policy and split). Fresh pre-change full offline: 631 passed,
2 skipped, 17 deselected, 0 failed. New module: 71 passed. New module plus
existing temporal-integrity tests: 88 passed. Post-change full offline:
702 passed, 2 skipped, 17 deselected, 0 failed. Two warnings are unchanged:
legacy target without symbol and unmapped ETF in existing unrelated tests.
No test deletion, new skip/xfail, gate weakening or dependence on online
Shenwan data. All Python/test execution used the existing Docker service.

Historical Iteration-1, Factor Audit, Factor Set V2, Alpha Stability,
Horizon-Specific and Component Replacement protocols/configs/results/handoffs
are unchanged. Changes are additions for this preregistration only. Original
source integrity passes before/after tests. Import and frozen-protocol checks
pass. Final commit and handoff audits must preserve this seal and clean Git.

## Warnings and next safe entry point

Validation is only 19/60 available; no formal execution is currently eligible.
Unknown dates/snapshot remain null, not inferred. Strict historical PIT is
not established. Development estimates are selection-sensitive; a future
walk-forward PASS would not imply tradability or automatic Final OOS.
The future runner must implement durable append-before-access and actual
training audits under this contract; this task intentionally adds no runner.
Next safe action is Human Review of this preregistration and a separately
authorized data-availability/integrity check; no Validation opening here.

NO VALIDATION RESULTS GENERATED

NO VALIDATION PERFORMANCE DATA READ

NO FINAL OOS DATA READ

VALIDATION REMAINS SEALED

FINAL OOS REMAINS SEALED

RUN VALIDATION ONLY AFTER HUMAN REVIEW
