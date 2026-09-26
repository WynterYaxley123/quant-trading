# Shenwan F1 Independent Validation V1 — preregistration

PREREGISTRATION ONLY. Validation and Final OOS remain SEALED. This document
does not authorize a model run or any performance access. Research type is
F1_INDEPENDENT_VALIDATION_V1; phase PREREGISTERED. It is sector-index research,
executable=false, tradable=false, strictPit=false, FIXED_CLASSIFICATION_RESEARCH.
NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST. NOT ETF PERFORMANCE.

## Candidate, control and model

The selection trace records the sole legal Development source and Human
Review. V1_F1_CANDIDATE is exactly F1_H10_REPLACEMENT: H10_C factors
`d10,p5,align,vc,dd20`; C0_H40 and C0_H120 keep the ordered 19 factors
`d5,d10,d20,d60,d120,p5,p10,p20,p60,p120,align,v5,v20,vc,rev5,rev10,dd20,dd60,rsi`.
V0_CONTROL is F0_CONTROL: C0_H10/C0_H40/C0_H120, all with those same 19
factors. Budget is one candidate and one control. There is no fallback or
adaptive candidate selection; both must be evaluated under the same contract.

NumPyRidge alpha 0.01, raw X, no train standardization, six calendar months
anchored to the per-horizon label cutoff, minimum 30 valid training dates.
Training target is same-training-date cross-sectional excess forward return:
`raw_y(t,s,h)-mean_admissible_raw_y(t,h)`, from Development D2/C0's exact
transform. Evaluation labels remain absolute `close[t+h]/close[t]-1` for
10/40/120 common trading sessions. No RSRS, macro or flow training; RiskState
record-only. Frozen source-file SHA256 identities are in the machine config.

Fusion calls the unchanged `CrossSectionalRidgeModel.fuse_periods`: per date
and horizon, scale by m=max(1,maxAbsScore), then cross-sectional population
z-score (ddof=0); std<=1e-12/m contributes zero. Fuse
`(0.25*z10+0.50*z40+0.25*z120)/sum(weights)`. Common scored intersection must
cover fixed U0=124 for evaluable metrics. Rank descending, exact ties by
sector code ascending; Top5 is the first five fused sectors. No factors,
signs, models, parameters, weights, horizons or candidates may be searched.

## Split, phase admission and chronological training

Authority is the existing immutable Policy C split hash
`3b6b2d754211169039439c8b377fd9eb26d5cb5db0f80d62cffc1d19c81a7038`.
Development E001–100; Purge1 E101–220; Validation E221–280; Purge2 E281–400;
Final OOS E401–460. Validation is exactly 60 observations, with blocks
VB1 E221–240, VB2 E241–260, VB3 E261–280 (20 each), deterministically
derived from the formal phase bounds, never from outcomes.

Only E221–239 dates are currently known: 2026-03-03 through 2026-03-27.
They were projected from the SHA-verified date column only and verified
against the existing E001–239 prefix hash. E240–280 dates remain null/unknown.
VB1's end and all VB2/VB3 dates are unavailable; no estimated dates are frozen.
The future formal run requires the entire 60-observation phase and all label
endpoints. Partial availability does not permit a partial formal Validation.

Human Review resolves VALIDATION_PURGE_TRAINING_SEMANTICS_BLOCKER before
opening. Purge1 evaluationEligible=false and trainingSourceEligible=true,
conditionally: labels must mature, as-of and rolling windows must pass,
features/targets must be valid, and minimum training data must be satisfied.
Purge1 never enters evaluation metrics. Validation uses
FROZEN_ALGORITHM_WALK_FORWARD / prequential evaluation, not static train-once
holdout. Earlier Validation observations can train later Validation dates
only after their horizon target matures, with origin < current signal.
Their performance cannot alter any research rule. Data maturity advances;
the algorithm, candidate and gates do not adapt.

Use existing `temporal_boundaries` and `training_window`, not a new maturity
rule: last origin = common calendar[signal_position-h]; training start =
that cutoff minus six calendar months; label end <= signal date (after close).
The new helper is phase-admission/date-integrity only, with caller-provided
validity from the frozen pipeline; it neither reads labels nor fits a model.
Its tests use synthetic calendars only. No actual Validation training dates
or maturity diagnostics are generated in preregistration.

Purge2 remains evaluation-excluded. Its future Final OOS training eligibility
is UNDECIDED_REQUIRES_SEPARATE_FINAL_OOS_PREREGISTRATION. Final OOS remains
inaccessible even if a future Validation pass or opening authorization exists.

## Data snapshot and cutoff policy

Reuse the existing append policy, not a newly selected snapshot: source
sector snapshot `872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`,
U0 codes fingerprint `f24e61c51f48e1b4ca8ded83eaf24bdd71be35711f3eb0ed88d7627f332d026a`,
E001–239 prefix `bcefa227f86a805677733defea63ed3954915548a6a140b0f654510c4267790b`,
economic history through 2026-09-18
`a78ae9d6e3c0f7b985927e1d6ae721f94ae4bb85fb58440cfd76719846eff82c`.
An append may change the snapshot ID but must preserve these historical
economics, U0 and ordinal identities; otherwise SPLIT_REPRODUCIBILITY_REVIEW.
Future execution must record the actual verified snapshot/file hashes.
No new data is downloaded here. Fixed classification is non-PIT, even after
Validation PASS. Features see only prices <= signal; training labels must
be matured by that signal; evaluation outcomes may be accessed only after
separate opening authorization and never leak into earlier model inputs.

## Metrics and unique pass definition

Reuse `evaluate_date` and the D2/C0 15-metric contract: IC, RankIC, fused Top5
mean absolute forward return, fixed-universe mean return and Top5-minus-
universe spread for each horizon. IC/RankIC use raw horizon scores; Spearman
uses average ties. Missing complete-case coverage or labels produces null
with a reason, never zero-fill or universe shrink. Report per-horizon means
RankIC10/40/120 and Spread10/40/120, descriptive aggregate valid/null counts.
Overlapping labels are not independent-sample significance evidence.

Primary Weighted RankIC and Weighted Spread use 0.25/0.50/0.25 times the
corresponding horizon means. Block metrics use the same weights and means.
No new primary metric or post-hoc block-spread gate is allowed.

VALIDATION_PASS requires ALL of:

1. V1 Weighted RankIC > 0 AND Weighted Spread > 0 (strict).
2. `(V1 WR>V0 WR AND V1 WS>=V0 WS)` OR
   `(V1 WS>V0 WS AND V1 WR>=V0 WR)`.
3. No horizon mean RankIC < -0.02 (strict threshold).
4. At least 2/3 blocks with Weighted RankIC > 0, at most 1/3 below -0.02.

Otherwise VALIDATION_FAIL, with Level1/relative/red-flag/temporal failure
reasons. No near/partial/basically pass. Block Weighted Spread is reported,
not gated. Missing/non-finite required metrics cannot pass.

## Seals and one-way opening contract

Current machine seal is UNSEEN, validationOpened=false, both phases SEALED,
all three performance-read/result flags false. The CLI is a read-only live
preregistration gate: it verifies protocol, sources and lifecycle-aware leak
scan. It has no opening mode, market-data model runner or ledger writer.
Ordinary unit tests do not permanently assert the real reports tree is empty.

A separately authorized future first Validation run must durably append its
one-way audit record BEFORE first Validation value access: opened=true,
state=OBSERVED, first-open UTC timestamp, validationProtocolHash,
candidateDefinitionHash, validationPhaseDefinitionHash, splitPolicyHash,
executionGitCommit and candidate source commit. Default opening is denied.
OBSERVED can never reset to UNSEEN, even after FAIL, a rerun or deletion of
result files; original opening identity must remain immutable. The pure
transition validator is exercised on tmp_path synthetic records only; no
live opened=true state is created here. A future runner must implement and
verify durable append-before-access, not merely call the pure validator.

FAIL: same Validation may not be reused after redesign as independent
Validation; subsequent result-informed work is POST_VALIDATION_DEVELOPMENT.
PASS: only FINAL_OOS_PREREGISTRATION_ELIGIBLE, requiring Human Review plus
separate Final OOS preregistration. Both cases keep Final OOS SEALED and
sector-index-only, non-tradable status unchanged.

## Future training-set audit contract

For every Validation signal and horizon, both candidate/control must record
signalDate, horizon, trainingWindowStart/End, candidateTrainingDates,
acceptedTrainingDates/Count, rejectedUnmaturedCount, latestAcceptedTrainingDate,
latestAcceptedLabelEndDate, phaseSourceCounts (preDevelopment, Development,
Purge1, earlier Validation), futureLeakCount=0. Counts are distinct dates;
record sector-row coverage separately under frozen U0 missingness rules.
The artifact must permit independent recomputation. It is integrity data,
not performance. No actual instance is produced in this task.

## Identity, environment and stop boundary

Candidate hash covers the complete candidate/control definitions and model,
target, window, preprocessing, fusion, weights, ranking/tie/Top5 semantics.
Phase hash covers split identity, IDs, known/null dates, blocks and phase-
training admission. Split policy hash is inherited. Canonical protocol hash
covers all configs, source identities, rules/policies/seals, this document,
selection trace and normalized protocol-module identity. Serialization is
sorted UTF-8 JSON, compact separators, no NaN or timestamps. Final hashes
are recorded in the preregistration report/handoff to avoid self-reference.

Approved host-only publication repair: old 127.0.0.1:9200/9201 to unchanged
container 9200/9201; now host 19200/19201. RESEARCH_ENVIRONMENT_CHANGED=false,
HOST_PORT_PUBLICATION_CHANGED=true; image remains
`sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5`.
Use base Compose plus `D:\QuantForge\temp\quant-trading-host-port.override.yml`.
Publication ports are outside the research environment identity and do not
invalidate the frozen image/source/data/model gate.

No Validation model, predictions, coefficients, ranking, Top5, returns,
regime or metrics; no Final OOS, portfolio, ETF, Dashboard/API, QMT or push.
Stop at VALIDATION PREREGISTRATION COMPLETE, after tests, local commits,
post-commit seal and handoff audits. Run Validation only after Human Review.
