# F1 Independent Validation V1 preregistration handoff

## Final status and Git identity

VALIDATION PREREGISTRATION COMPLETE. Preregistration only; no Validation
execution, actual Validation training set or label-maturity diagnostic.

Branch: `experiment/sw-sector-index-research-baseline`.
Preregistration/authoring HEAD: `c4f3ecec69fc42599df02a459563c046f4fedf65`.
Message: `research: preregister f1 independent validation v1`.
The immediately following docs-only handoff commit contains only this file
and its JSON counterpart. Its SHA cannot be self-recorded; read final Git HEAD
and verify its parent is the preregistration commit. Worktree/index were clean
after preregistration; the final clean-state audit follows handoff commit.

Protocol: `docs/research/shenwan_f1_independent_validation_v1.md`.
Report: `docs/research/shenwan_f1_independent_validation_v1_preregistration_report.md`.
Selection: `docs/research/shenwan_f1_independent_validation_v1_selection_trace.md`.
Machine handoff: `docs/research/handoff_f1_independent_validation_v1_prereg.json`.

## Frozen provenance and hashes

Only source: HORIZON_COMPONENT_REPLACEMENT_V1. Result commit
`91b89a97a9a2b54e133d2979c695d7c3da22626e`; handoff
`e388fdce6d846019b854704a1967ca0a6b12afd6`; implementation
`fb207b8b868a3aaceed568d4a8e1b62340371bff`; preregistration
`95e54ee6461b315b51f5ca7cc17cd985caa96a1d`; preregistration handoff
`d28e42bf7bb09fcc5b9faa19ab3ff0a96429c1cd`. Source protocol hash:
`4267d73f38fc8353002459b24640148cc49c4e5777b364eb14ca84404aef9fa7`.
Ancestor/provenance audit PASS; 42/42 source content files verified.
Human Review admits only F1; F2 was formally not advanced and deteriorated
Spread. No new/backup candidate, H40/H120 replacement or search is allowed.

- canonical protocol SHA256: `2344cc685201476de957109b9fccc2681923e2c4591b5ed91740a56baf128410`
- protocol Markdown byte SHA256: `6f9c29669cb30f7bfa35133a66549e3e354617c99b6a10f27a807a569fdd20c5`
- candidateDefinitionHash: `6c2b16555b6dfd5d848ea451b09e7b75f53da67747fc76fd052d93afd3ea156b`
- config canonical hash: `39c603097c2cf49e61b610407dc0a7609a6b14426a125ead556ac9ed1008c9d8`
- splitPolicyHash: `3b6b2d754211169039439c8b377fd9eb26d5cb5db0f80d62cffc1d19c81a7038`
- validationPhaseDefinitionHash: `28d3980e28b41b37d2a327aad6081e8312cf66d66762c13e33cc8ba814c8fa7f`

## Exact candidate/control and common algorithm

One candidate `V1_F1_CANDIDATE`: H10_C `[d10,p5,align,vc,dd20]`, C0_H40,
C0_H120. One control `V0_CONTROL`: C0_H10/C0_H40/C0_H120.
C0 factor order: `[d5,d10,d20,d60,d120,p5,p10,p20,p60,p120,align,v5,v20,vc,rev5,rev10,dd20,dd60,rsi]`.
Candidate/control match the formal source exactly; drift audit PASS.

NumPyRidge alpha=.01, raw X, no train standardization; six calendar months
anchored at each horizon's label cutoff, min30 valid dates. Targets are
same-training-date cross-sectional excess forward returns; evaluation labels
are absolute returns. Existing population per-date/per-horizon z-score fusion
and its numerical rule are unchanged; weights .25/.50/.25. Rank fused score
descending, sector code ascending for ties, select the first five. Exact full
definition remains in the hash-covered candidate config, not redefined here.

## Split, Human Review decision and data policy

Formal Policy C: Development E001–100; Purge1 E101–220; Validation E221–280;
Purge2 E281–400; Final OOS E401–460. Blocks derive from the 60 Validation
ordinals: VB1 E221–240, VB2 E241–260, VB3 E261–280 (20 each).
Only E221–239 dates are known: 2026-03-03–2026-03-27 (19). Exact dates are in
the frozen split config. E240–280 dates stay null/unknown (41); no extrapolation.
A future formal run needs all 60 dates and realized 10/40/120 label endpoints.
No current Validation label-maturity analysis was performed.

PREVIOUS BLOCKER: VALIDATION_PURGE_TRAINING_SEMANTICS_BLOCKER.
RESOLUTION: HUMAN_REVIEW_DECISION.
BLOCKER_RESOLVED_BEFORE_VALIDATION_OPEN=true.

Purge1 evaluationEligible=false, trainingSourceEligible=true conditionally:
existing rolling window, horizon maturity/as-of, min30 and feature/target
validity must all pass. The unchanged formal maturity rule is
`label_end <= current_signal_date` after close; origin must be strictly earlier.
Validation mode is FROZEN_ALGORITHM_WALK_FORWARD / prequential: refit the
frozen algorithm at each authorized signal. Earlier Validation observations
can train later signals only after horizon-specific maturity under the same
rules. Data matures over time; performance never adapts the research design.
Purge2 evaluation is excluded; its Final OOS training admission is UNDECIDED
until separate Final OOS preregistration. No future information is permitted.

Source sector snapshot:
`872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`.
Existing formal append-only policy preserves fixed U0_124, economic history
through 2026-09-18 and the E001–239 prefix. A valid append may change snapshot
ID; actual future file/snapshot hashes must be recorded, not guessed. Any
historical revision raises SPLIT_REPRODUCIBILITY_REVIEW. Features see no
post-signal prices; only mature training labels may enter the model.
strictPit=false; FIXED_CLASSIFICATION_RESEARCH;
NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST.
SECTOR_INDEX_RESEARCH_ONLY, executable=false and tradable=false remain.

## Gates, lifecycle and independent audit

Original 15 metrics remain IC, RankIC, Top5 return, Universe return and Spread
for 10/40/120. Primary weighted RankIC/Spread use .25/.50/.25. Missing/nonfinite
required metrics cannot pass; no zero-filled or invented metric.

Unique VALIDATION_PASS requires all four:

1. V1 Weighted RankIC > 0 AND Weighted Spread > 0.
2. At least one primary strictly improves versus V0; the other does not decline.
3. No horizon mean RankIC < -.02.
4. At least two blocks have Weighted RankIC > 0; at most one has it < -.02.

Block Spread is reported, not hard-gated. Otherwise VALIDATION_FAIL; no
partial/near pass. FAIL permanently leaves the opened phase OBSERVED;
redesign is POST_VALIDATION_DEVELOPMENT and cannot reuse it as independent
Validation. PASS grants only FINAL_OOS_PREREGISTRATION_ELIGIBLE, subject to
Human Review and separate OOS preregistration, not automatic OOS execution.

Current seal: Validation=SEALED, Final OOS=SEALED, state=UNSEEN,
validationOpened=false, firstOpenedAt=null; all three performance/result
flags false. Local independence audit PASS: 14 Development metadata records,
no findings; Git/history/paths/handoffs/tests/logs reviewed without Validation
performance payloads. Runtime post-preregistration-commit seal audit PASS,
including all source hashes and unchanged frozen identities.

Default opening is denied. A future explicit authorization must persist a
durable one-way UNSEEN→OBSERVED record BEFORE first Validation value access:
UTC first-open time, protocol/candidate/phase/split hashes, execution and source
commits, Validation identity and Final OOS seal. OBSERVED cannot reset; opening
identity cannot be rewritten. Current module validates the contract only;
it has no live ledger writer/model runner. Tests use synthetic tmp_path records.

Future training audit is an independently recomputable integrity artifact for
every signal/horizon and both schemes: window bounds; candidate/accepted dates
and accepted count; unmatured rejection count; latest accepted origin and label
end; phase counts (preDevelopment, Development, Purge1, earlier Validation);
futureLeakCount=0; separate fixed-U0 sector-row coverage. No actual Validation
training audit is produced here.

## Tests, immutability and operational exception

Pre-change targeted: 88 passed. Pre-change full offline: 631 passed,
2 skipped, 17 deselected, 2 existing warnings, 0 failed. New protocol: 71 passed;
new protocol plus existing temporal integrity: 88 passed. Post-change full
offline: 702 passed, 2 skipped, 17 deselected, 2 existing warnings, 0 failed.
No new skip/xfail, deleted test or weakened gate. Docker-only execution.
Historical protocols/configs/results/handoffs and strategy core are unchanged;
only eight new preregistration files plus two docs-only handoff files are added.

Docker quant-research and quant-jupyter running. Frozen image:
`sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5`.
No rebuild/recreate/dependency change in this task. Approved host-only exception:
old 127.0.0.1:9200→9200 / 9201→9201; current 127.0.0.1:19200→9200 /
19201→9201. Internal ports unchanged. Every Compose call uses base
`D:\quant-trading\docker-compose.yml` plus
`D:\QuantForge\temp\quant-trading-host-port.override.yml`.
RESEARCH_ENVIRONMENT_CHANGED=false; HOST_PORT_PUBLICATION_CHANGED=true.

Warnings: only 19/60 Validation dates known; strict historical PIT absent;
Development selection-sensitive; future snapshot unknown; actual availability
and training audit untested by design; future runner implementation still
requires authorization. No independent Validation outcome or tradability claim.
Next safe entry: Human Review of this preregistration; separate explicit
authorization is required for future data-availability checks or execution.
Do not resume portfolio/ETF/Dashboard/API work or open Final OOS automatically.

PURGE1 IS NOT AN EVALUATION PHASE

PURGE1 IS CONDITIONALLY TRAINING-ELIGIBLE

VALIDATION USES FROZEN-ALGORITHM WALK-FORWARD EVALUATION

ONLY LEGALLY MATURED HISTORICAL LABELS MAY ENTER TRAINING

NO FUTURE INFORMATION IS PERMITTED

NO VALIDATION RESULTS GENERATED

NO VALIDATION PERFORMANCE DATA READ

NO FINAL OOS DATA READ

VALIDATION REMAINS SEALED

FINAL OOS REMAINS SEALED

RUN VALIDATION ONLY AFTER HUMAN REVIEW
