# SHENWAN HORIZON-SPECIFIC ALPHA HYPOTHESIS V1 FORMAL DEVELOPMENT RUN REPORT

FINAL STATUS: **HORIZON-SPECIFIC ALPHA HYPOTHESIS V1 FORMAL DEVELOPMENT RUN
COMPLETE WITH NON-BLOCKING WARNINGS**. POST-AUDIT DEVELOPMENT HYPOTHESIS
REFINEMENT — `DEVELOPMENT_REUSE_WARNING=true`, NOT INDEPENDENT VALIDATION,
NOT OOS, not validated alpha, not ready for trading. Two candidates passed
all preregistered gates (H10_C, H40_S); four did not; no cross-horizon
winner is declared.

## 1. RESEARCH STATE

- Branch: `experiment/sw-sector-index-research-baseline`
- HEAD before: `4d0ee982a0cd4ff1efe76c9fee4c2de807643ac2` (preregistration)
- HEAD after: the commit introducing this report
  (`research: run horizon specific alpha hypothesis v1`); full SHA in the
  handoff package and the accompanying summary
- Working tree: clean at preflight, clean during both runs (runner gate
  admits only the untracked runner + tests), clean at commit

## 2. PREREGISTRATION

- Commit: `4d0ee982a0cd4ff1efe76c9fee4c2de807643ac2` (parent:
  `ff34ad5cc09ff419b1d12aad33ca7dfff4fe865e`)
- Protocol path: `docs/research/shenwan_horizon_specific_alpha_hypothesis_v1.md`
- Protocol hash (recomputed and verified before run, during gate, and at
  artifact write): `d598efd34fe2a6c03832e3faaeadd738cc63a604e5da4c8f1a3740c33e69b8d4`
- Machine config: `research/configs/horizon_specific_alpha_hypothesis_v1.json`
  (config hash `ddaaa1c761bf1ab37d86bd5228ad306d54af66575fbe2c06ed4df576e01446ec`)
- Selection trace:
  `docs/research/shenwan_horizon_specific_alpha_hypothesis_v1_selection_trace.md`
- **Protocol unchanged confirmation**: git diff of all six frozen
  preregistration files against `4d0ee982…` is empty; `verify_protocol()`
  re-derived the frozen hash at every gate.

## 3. ENVIRONMENT

- Docker image identity: `sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5`
  (`quant-research:py3.12`, verified by pre-run gate against the frozen
  expectation)
- **ENVIRONMENT_CHANGED = false**. All execution via
  `docker compose exec quant-research`; no dependency, Docker, Hikyuu, or
  data change.

## 4. SAMPLE

- Development **E001-E100**, date range **2025-04-02 to 2025-08-26** (read
  from the frozen split policy, not hardcoded), all 100 dates valid on every
  scheme
- Universe **U0 = 124** fixed Shenwan Level-2 sector indexes
  (snapshot `872bcbc2…4e500`), fixed classification research,
  `strictPit=false`, `executable=false`, `tradable=false`
- Validation and Final OOS: SEALED (hard guard; any E101+ or sealed-phase
  access raises `SEALED_OR_NON_DEVELOPMENT_ACCESS_BLOCKER`)

## 5. CANDIDATE IDENTITY

Exactly six frozen new candidates; **no extra candidate**; factor lists read
from the machine config and verified against `EXACT_CANDIDATES` at runtime:

| Candidate | Horizon | Archetype | Exact factor list (pipeline order) |
|---|---:|---|---|
| H10_S | 10 | SINGLE_STABLE | `[p5]` |
| H10_C | 10 | COMPACT_STABLE | `[d10, p5, align, vc, dd20]` |
| H40_S | 40 | SINGLE_STABLE | `[vc]` |
| H40_C | 40 | COMPACT_STABLE | `[d120, p60, align, vc, rev5, dd20]` |
| H120_S | 120 | SINGLE_STABLE | `[vc]` |
| H120_C | 120 | COMPACT_STABLE | `[d5, p20, vc, rev10, dd60, rsi]` |

## 6. CONTROLS

Same-horizon controls C0_H10 / C0_H40 / C0_H120 = the frozen D2/C0 19-factor
model evaluated at its own horizon only. Reproduction identity against the
existing formal Iteration-1 D2 artifact (`iteration1_20260924_163607_787266_utc/D2`,
byte-hash verified before use):

- **prediction-level identity: bit-exact** for all three horizons
  (with round-trip float parsing, `prediction_score` arrays equal exactly;
  rank mismatches 0; max abs diff under default parsing 1.01e-16 = CSV
  reader noise only)
- mean IC / mean RankIC / valid dates: reproduce exactly (abs diff 0.00e+00)
- mean Spread: horizon-local Top5 spread reproduces from the D2 artifact's
  own per-horizon predictions (abs diff ≤ 6.1e-18). **Semantic note**: the
  legacy D2 `Top5_minus_universe` aggregate used the *fused* Top5; the
  frozen protocol mandates horizon-local Top5 (no fusion), so the two
  spread figures are different quantities and are not compared as one:

| horizon | horizon-local Top5 spread (gates use this) | legacy fused-Top5 spread (disclosure only) |
|---:|---:|---:|
| 10 | -0.000047 | +0.005297 |
| 40 | +0.003865 | +0.012788 |
| 120 | +0.161804 | +0.117993 |

## 7. MODEL SETTINGS

Raw X, no standardization; training target = same-training-date
cross-sectional excess forward return (evaluation labels = absolute forward
return, common calendar `t+h`, no endpoint shift/fill); `NumPyRidge(alpha
0.01, fit_intercept=True)`; 6-calendar-month rolling window anchored to the
per-horizon legal label cutoff; minimum 30 valid training days; each
candidate trained at **its own horizon only** (no cross-horizon training);
Top5 = prediction score descending with sector-code-ascending tie-break;
Spread = mean Top5 absolute forward return − mean universe absolute forward
return; **no fusion anywhere** (`noFusion=true`); no weighted RankIC/Spread;
frozen blocks B1=E001-025, B2=E026-050, B3=E051-075, B4=E076-100.

## 8. H10 RESULTS

| scheme | Mean IC | Mean RankIC | Median RankIC | Mean Spread | Median Spread | valid dates | L1 | L2 | Temporal | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| C0_H10 (control) | -0.017436 | +0.025446 | -0.002143 | -0.000047 | -0.001602 | 100 | — | — | — | CONTROL_SAME_HORIZON_REFERENCE |
| H10_S `[p5]` | +0.002697 | +0.004797 | -0.010334 | +0.000133 | +0.000086 | 100 | PASS | FAIL | PASS | HORIZON_NOT_ADVANCED |
| H10_C `[d10,p5,align,vc,dd20]` | +0.035714 | +0.046993 | +0.033750 | +0.002836 | -0.000564 | 100 | PASS | PASS | PASS | **HORIZON_ADVANCED_FOR_FURTHER_REVIEW** |

H10_S: no Level-2 improvement over C0 (ΔRankIC −0.0206). H10_C improves on
both primaries (ΔRankIC +0.0215, ΔSpread +0.0029) and passes all three
gates. **Compact beats single at 10 days.**

## 9. H40 RESULTS

**H40 EVIDENCE QUALITY WARNING / NO_STRONG_STABILITY_EVIDENCE (retained,
per preregistration; a good result does not remove it).**

| scheme | Mean IC | Mean RankIC | Median RankIC | Mean Spread | Median Spread | valid dates | L1 | L2 | Temporal | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| C0_H40 (control) | +0.021682 | +0.049692 | +0.057410 | +0.003865 | +0.005963 | 100 | — | — | — | CONTROL_SAME_HORIZON_REFERENCE |
| H40_S `[vc]` | +0.055242 | +0.052441 | +0.059868 | +0.007790 | -0.001454 | 100 | PASS | PASS | PASS | **HORIZON_ADVANCED_FOR_FURTHER_REVIEW** |
| H40_C `[d120,p60,align,vc,rev5,dd20]` | -0.016143 | +0.005299 | +0.026581 | -0.012996 | -0.024324 | 100 | FAIL | FAIL | FAIL | HORIZON_NOT_ADVANCED |

The preregistered temporal weakness concern is **confirmed for H40_C**
(block RankIC +0.176/+0.268/−0.150/−0.273; two blocks below −0.02) and
**not confirmed for H40_S** (blocks +0.038/+0.050/+0.051/+0.071, all
positive). H40_S passes with small positive margins (ΔRankIC +0.0027,
ΔSpread +0.0039); its median Spread is slightly negative (−0.0015) and its
advancement is subject to the neutrality caveat (§15) and the retained
NO_STRONG_STABILITY_EVIDENCE warning.

## 10. H120 RESULTS

| scheme | Mean IC | Mean RankIC | Median RankIC | Mean Spread | Median Spread | valid dates | L1 | L2 | Temporal | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| C0_H120 (control) | +0.239157 | +0.227595 | +0.246279 | +0.161804 | +0.088274 | 100 | — | — | — | CONTROL_SAME_HORIZON_REFERENCE |
| H120_S `[vc]` | -0.015065 | -0.000130 | +0.020120 | -0.032598 | -0.048934 | 100 | FAIL | FAIL | PASS | HORIZON_NOT_ADVANCED |
| H120_C `[d5,p20,vc,rev10,dd60,rsi]` | +0.263193 | +0.242679 | +0.260261 | +0.128892 | +0.139604 | 100 | PASS | FAIL | PASS | HORIZON_NOT_ADVANCED |

The earlier Development diagnostics' "steadier 120d" block stability does
**not** translate into a same-horizon Pareto improvement: H120_C raises
RankIC (+0.0151 over C0) but loses Spread (−0.0329), so Level 2 fails;
H120_S is essentially neutral. Same Development data as always — this is
not independent evidence.

## 11. DELTA VS SAME-HORIZON C0

| candidate | Δ mean RankIC | Δ mean Spread | Level-2 mechanics |
|---|---|---|---|
| H10_S | -0.020649 | +0.000181 | fails: RankIC below C0, Spread not above C0's by option-B pairing |
| H10_C | **+0.021547** | **+0.002884** | option A: RankIC > C0 and Spread ≥ C0 |
| H40_S | **+0.002748** | **+0.003924** | option A: both primaries strictly above C0 |
| H40_C | -0.044393 | -0.016862 | fails both options |
| H120_S | -0.227725 | -0.194402 | fails Level 1 first |
| H120_C | +0.015083 | -0.032912 | fails: Spread below C0 (no Pareto) |

## 12. BLOCK STABILITY (mean RankIC / mean Spread, B1-B4)

| scheme | RankIC B1 | B2 | B3 | B4 | Spread B1 | B2 | B3 | B4 |
|---|---|---|---|---|---|---|---|---|
| C0_H10 | +0.1793 | +0.0251 | -0.0145 | -0.0881 | +0.0220 | -0.0090 | -0.0013 | -0.0119 |
| H10_S | -0.0569 | +0.0040 | +0.0153 | +0.0568 | -0.0200 | -0.0046 | +0.0142 | +0.0110 |
| H10_C | +0.1523 | +0.0229 | +0.0002 | +0.0127 | +0.0123 | +0.0072 | -0.0064 | -0.0019 |
| C0_H40 | +0.2400 | +0.2615 | -0.1177 | -0.1851 | +0.0496 | +0.0464 | -0.0284 | -0.0520 |
| H40_S | +0.0380 | +0.0497 | +0.0509 | +0.0711 | -0.0205 | +0.0167 | +0.0094 | +0.0256 |
| H40_C | +0.1760 | +0.2680 | -0.1496 | -0.2733 | +0.0458 | -0.0102 | -0.0321 | -0.0555 |
| C0_H120 | +0.2726 | +0.2016 | +0.2529 | +0.1833 | +0.2375 | +0.3423 | +0.0584 | +0.0090 |
| H120_S | +0.0543 | -0.1112 | +0.0190 | +0.0374 | -0.0571 | -0.0984 | -0.0034 | +0.0284 |
| H120_C | +0.4448 | +0.3009 | +0.1421 | +0.0828 | +0.4173 | +0.2468 | -0.0156 | -0.1329 |

Note the improvement concentration: H10_C's RankIC edge is B1-heavy
(+0.1523; B3 = +0.0002 barely positive), while H40_S is the only scheme with
four uniformly positive moderate blocks. H120_C decays B1→B4 and turns
negative on spread in B3/B4.

## 13. TEMPORAL GATE (frozen rule applied per candidate)

Rule: at least 3/4 blocks with mean RankIC > 0 AND at most 1/4 blocks with
mean RankIC < −0.02 (strict inequalities; a block exactly −0.02 does not
count as a red block).

| candidate | positive blocks | blocks < −0.02 | verdict |
|---|---|---|---|
| H10_S | 3 (B2,B3,B4) | 0 | PASS |
| H10_C | 4 (B3 = +0.0002) | 0 | PASS |
| H40_S | 4 | 0 | PASS |
| H40_C | 2 | 2 (B3 −0.150, B4 −0.273) | FAIL |
| H120_S | 3 | 1 (B2 −0.111) | PASS |
| H120_C | 4 | 0 | PASS |

## 14. SIMPLICITY PREFERENCE

**Not triggered.** No horizon has both S and C advanced (H10: only C; H40:
only S; H120: neither), so the near-tie rule never applied. `simplicityPreference`
= `NOT_TRIGGERED` on all six; raw metrics (§8-§11) reported separately.

## 15. NEUTRALITY CAVEAT

Retained exactly as preregistered. `H40_S` and `H120_S` are `[vc]`;
`H10_S` is `[p5]`. The Alpha Stability transition table records the legal
training direction as NEUTRAL on 100/100 dates for p5@10 and vc@40, and
99/100 for vc@120 — so the selection key "zero hard flips" reflects
**NEUTRALITY_INDUCED_LOW_FLIP_RATE**, not established DIRECTIONAL_STABILITY.
This run's formal evidence is separate: H40_S shows positive mean RankIC
with four uniformly positive blocks (directional stability in this sample),
while H120_S shows no directional content (mean RankIC −0.0001). The
statement "vc has no hard flips therefore vc is stable" is NOT made and is
NOT supported.

## 16. ADVANCEMENT DECISION

Frozen gates applied verbatim (`advancement_status`, strict `>`; components
independently recomputed from predictions and cross-checked — all agree):

| candidate | L1 | L2 | Temporal | Simplicity | Status |
|---|---|---|---|---|---|
| H10_S | LEVEL1_PASS | LEVEL2_FAIL | TEMPORAL_STABILITY_PASS | NOT_TRIGGERED | HORIZON_NOT_ADVANCED |
| H10_C | LEVEL1_PASS | LEVEL2_PASS | TEMPORAL_STABILITY_PASS | NOT_TRIGGERED | **HORIZON_ADVANCED_FOR_FURTHER_REVIEW** |
| H40_S | LEVEL1_PASS | LEVEL2_PASS | TEMPORAL_STABILITY_PASS | NOT_TRIGGERED | **HORIZON_ADVANCED_FOR_FURTHER_REVIEW** |
| H40_C | LEVEL1_FAIL | LEVEL2_FAIL | TEMPORAL_STABILITY_FAIL | NOT_TRIGGERED | HORIZON_NOT_ADVANCED |
| H120_S | LEVEL1_FAIL | LEVEL2_FAIL | TEMPORAL_STABILITY_PASS | NOT_TRIGGERED | HORIZON_NOT_ADVANCED |
| H120_C | LEVEL1_PASS | LEVEL2_FAIL | TEMPORAL_STABILITY_PASS | NOT_TRIGGERED | HORIZON_NOT_ADVANCED |

No `VALIDATED / PRODUCTION / TRADABLE / LIVE_READY / OOS_PASS / WINNER /
BEST_MODEL` label exists anywhere in the artifacts.

## 17. NO CROSS-HORIZON WINNER

Declared: horizons have different targets and are compared only against
their own same-horizon control. Nothing here supports "H120 is best" or
"H40 is worst"; the only valid claims are per-horizon advanced / not
advanced as above.

## 18. PRIMARY RESEARCH DIAGNOSIS (evidence-based)

- **H10**: `MIXED_BUT_COMPACT_SUPPORTED` — the single-factor hypothesis is
  not supported (H10_S fails Level 2 on RankIC), but the frozen compact
  cross-family set improves on C0_H10 on both primaries and passes all
  gates; its edge is B1-heavy, so it qualifies for further review only.
- **H40**: `SINGLE_FACTOR_ADVANCED_WITH_RETAINED_WARNINGS` — H40_S (vc)
  passes all gates with small positive margins and uniformly positive
  blocks, while H40_C confirms the preregistered temporal-weakness concern
  (regime flip B1/B2 → B3/B4). NO_STRONG_STABILITY_EVIDENCE and the
  neutrality caveat remain in force.
- **H120**: `NO_PARETO_IMPROVEMENT_OVER_C0` — the previously steadier 120d
  diagnostics do not yield a same-horizon Pareto improvement: H120_C
  raises RankIC but loses Top5 spread (Level 2 fail), H120_S is neutral.
  C0_H120 remains the strongest 120d scheme under the frozen rules.

## 19. NEXT_RESEARCH_GATE

**MIXED_HORIZON_EVIDENCE** (frozen allowed value). Two candidates passed all
preregistered gates (satisfying the necessary condition of
HORIZON_HYPOTHESIS_SUPPORTED_FOR_FURTHER_REVIEW), but four failed with
clearly different mechanisms (Level-2 spread-Pareto failure at 120d;
temporal-gate failure of H40_C; Level-1/Level-2 weakness of the single
factors), so the faithful frozen value is the mixed one. This is a research
judgment only: **no Validation is opened**; any next design requires human
review first.

## 20. ARTIFACTS

- First formal run: `reports/research/shenwan_sector_index/horizon_specific_alpha_v1_20260925_130230_272283_utc/`
- Determinism rerun: `reports/research/shenwan_sector_index/horizon_specific_alpha_v1_20260925_131549_730952_utc/`
- Structure (each run): `metadata.json`, `candidate_summary.json`,
  `block_stability.csv`, `integrity.json` at root; per scheme
  (C0_H10, C0_H40, C0_H120, H10_S, H10_C, H40_S, H40_C, H120_S, H120_C):
  `predictions.csv`, `per_date_metrics.csv`, `aggregate_metrics.json`,
  `training_diagnostics.csv`, `data_quality_diagnostics.json`,
  `transformation_diagnostics.json` — 57 non-metadata artifacts per run.
- `/reports/research/` is untracked by repo convention (`.gitignore`);
  provenance = protocol hash + commits + recorded content SHA-256s.

## 21. FACTOR IDENTITY

**PASS** — E001/E050/E100 × all 19 pipeline factors × 10 sectors = 570
comparisons against the frozen feature pipeline; maxAbsDiff **1.60e-14**
(tolerance 1e-9, floating-point only).

## 22. TARGET IDENTITY

**PASS** — 3 Development dates × 3 horizons × 10 sectors = 90 comparisons;
`label_end = calendar[t+h]` confirmed on every row; maxAbsDiff
**0.00e+00** vs direct calendar arithmetic, **1.11e-16** vs the frozen D2
artifact (tolerance 1e-12; the latter is CSV reader noise — see §28 note).
No endpoint shift, fill, or interpolation; excess target applied only as
same-date cross-sectional demeaning in training; evaluation on absolute
forward returns.

## 23. TRAINING WINDOW IDENTITY

**PASS** — E001/E025/E050/E075/E100 × 10/40/120 across all 9 schemes = 405
field comparisons (window start, window end, legal label cutoff, first/last
train origin, last label end, candidate/valid days, observation count,
valid sectors) against the frozen D2 training diagnostics; exact match on
every field; coverage of all 15 ordinal×horizon combinations verified.

## 24. C0 REPRODUCTION

**PASS** — max abs diff **1.01e-16** (tolerance 1e-12), zero rank
mismatches; with round-trip float parsing the C0_H10/H40/H120
`prediction_score` arrays are **bit-exact** against the frozen D2 artifact.
Mean IC / mean RankIC / valid dates reproduce at 0.00e+00; horizon-local
spread reproduces from the artifact's own predictions (≤6.1e-18). Legacy
fused-Top5 spread values recorded in §6 for disclosure only.

## 25. TOP5 IDENTITY

**PASS** — 3 dates × 9 schemes = 54 exact checks (ranking order and Top5
set recomputed from artifact predictions with sector-code-ascending
tie-break; exact match everywhere).

## 26. METRIC INTEGRITY

**PASS** — independent recompute of IC / RankIC / Top5 return / Universe
return / Spread (daily and aggregates) and block metrics straight from
`predictions.csv`: max abs diff **2.22e-16** (tolerance 1e-12). A separate
standalone from-disk verification (outside the runner) reconciled every
scheme at ≤2.8e-17 with round-trip parsing.

## 27. ADVANCEMENT LOGIC INTEGRITY

**PASS** — Level 1 / Level 2 / temporal gate / simplicity independently
re-applied from recomputed metrics for all 6 candidates: statuses and
component flags agree exactly with the recorded results (6/6).

## 28. DETERMINISM

- Non-metadata artifact count: **57 per run**
- File-by-file SHA-256 comparison (first run vs rerun): **57/57 identical**;
  recorded hashes match file bytes in both runs (0 mismatches);
  rerun metadata `determinism = PASS_CONTENT_SHA256_IDENTICAL`,
  `determinism_repeat_of = horizon_specific_alpha_v1_20260925_130230_272283_utc`
- Representative hashes: `candidate_summary.json a574ba19…972ae2`,
  `block_stability.csv 13299598…46569a`, `integrity.json 3080047c…dd2290`,
  `H10_S/predictions.csv 800b5cd8…be963e`, `H40_S/predictions.csv
  dd9b8277…9aae07`, `H120_C/predictions.csv 40a20b4f…2361bab`
- Non-blocking note (verification methodology): pandas `read_csv` default
  float parsing perturbs values by ~1e-16 and **breaks exact ties**, which
  changes tie-sensitive Spearman ranks; any future recomputation of rank
  metrics from CSVs must use `float_precision="round_trip"`. The artifacts
  themselves are written losslessly (`%.17g`) and are internally consistent.

## 29. TESTS

- Targeted (prereg `tests/test_horizon_specific_alpha_hypothesis_v1.py` 14
  + runner `tests/test_horizon_specific_alpha_v1_run.py` 15): **passed 29,
  failed 0, skipped 0**
- Full offline suite: **passed 599, failed 0, skipped 2, deselected 17**
  (integration marker policy; 584 prereg baseline + 15 new)
- No test was skipped, xfailed, or deleted to achieve green.

## 30. DEVELOPMENT REUSE DISCLOSURE

**POST-AUDIT DEVELOPMENT HYPOTHESIS REFINEMENT. DEVELOPMENT_REUSE_WARNING=true.
NOT INDEPENDENT VALIDATION. NOT OOS.** Iteration-1, Factor Audit V1, Factor
Set V2, Alpha Stability Audit V1 and this run all inspect the same
Development sample E001-E100. These results are not validated alpha and not
ready for trading regardless of their sign.

## 31. RESEARCH COMPLIANCE

Development only ✓ · Validation untouched (SEALED) ✓ · Final OOS untouched
(SEALED) ✓ · no fusion / no cross-horizon winner ✓ · no sign flip ✓ · no
candidate adaptation (lists identical to preregistration) ✓ · no factor
search ✓ · no parameter search ✓ · no model replacement ✓ · no Docker
changes ✓ · no dependency changes ✓ · no Hikyuu changes ✓ · no
Dashboard/API ✓ · no Portfolio ✓ · no ETF ✓ · no QMT ✓ · preregistration
files byte-unchanged ✓ · historical artifacts and source CSVs hash-verified
unchanged ✓.

## 32. ENVIRONMENT_CHANGED

**false** (image `sha256:57858238…02e5` verified at both run gates).

## 33. RESULT COMMIT

The commit introducing this report and the handoff package
(`research: run horizon specific alpha hypothesis v1`); full SHA recorded
in `docs/research/handoff_horizon_specific_alpha_v1.md` and `.json`. No
push, no merge, no rebase, no amend.

## 34. NEXT AUTHORIZED ACTION

**HUMAN REVIEW REQUIRED BEFORE NEXT RESEARCH DESIGN.** Not executed
automatically.

## 35. FINAL STATUS

**HORIZON-SPECIFIC ALPHA HYPOTHESIS V1 FORMAL DEVELOPMENT RUN COMPLETE
WITH NON-BLOCKING WARNINGS**

Non-blocking warnings (all disclosed, none swallowed):

1. **Pre-artifact implementation bugs (disclosed per research-bug
   discipline):** the first `--execute` attempt crashed twice before any
   artifact was written — (a) `training_window_identity_gate` assumed
   multi-horizon training frames while horizon-local schemes carry one
   horizon each (IndexError); (b) `c0_reproduction_report` read the frozen
   D2 aggregate key `validDates` instead of the artifact's `valid_dates`
   (KeyError). Both were clear logic bugs in the new runner only, fixed
   with regression tests; frozen preregistration untouched; **no formal
   artifact was affected** (no run directory existed at either crash; the
   completed run started from scratch afterward). This is why the status is
   not `FORMAL_RUN_IMPLEMENTATION_BLOCKER`: §56's procedure covers bugs in
   completed formal results, and §55 permits fixing clear identity/logic
   bugs; both facts are recorded here instead of being silently absorbed.
2. **CSV read-precision caveat** (§28): tie-sensitive rank recomputation
   from CSVs requires `float_precision="round_trip"`.
3. **H40 NO_STRONG_STABILITY_EVIDENCE** retained despite H40_S advancing.
4. **Neutrality caveat** retained for H40_S / H120_S (vc) and H10_S (p5).
5. **Development reuse** across five studies on one sample.
6. `reports/research/` artifacts are untracked by convention; provenance
   relies on protocol hash, commits, and content hashes.
