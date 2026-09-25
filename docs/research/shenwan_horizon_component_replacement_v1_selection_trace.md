# Horizon Component Replacement V1 — selection trace (preregistration only)

Every admission/rejection below cites the **formal Horizon-Specific Alpha
Hypothesis V1 result statuses and gates** (artifact
`reports/research/shenwan_sector_index/horizon_specific_alpha_v1_20260925_130230_272283_utc/candidate_summary.json`,
result commit `de8b77a8da3aeac99fa5ac1fd52d6431cedf2d62`). No performance
rescan, per-date return scan, or combination enumeration was performed for
this design; component choice is a pure function of the frozen advancement
statuses. This document is a design trace, not a new result.

## 1. Source gate outcomes (verbatim facts)

| source candidate | components | gates (L1 / vs-C0 / temporal) | formal status |
|---|---|---|---|
| H10_S `[p5]` | 10d only | PASS / FAIL / PASS | HORIZON_NOT_ADVANCED |
| H10_C `[d10,p5,align,vc,dd20]` | 10d only | PASS / PASS / PASS | **HORIZON_ADVANCED_FOR_FURTHER_REVIEW** |
| H40_S `[vc]` | 40d only | PASS / PASS / PASS | **HORIZON_ADVANCED_FOR_FURTHER_REVIEW** |
| H40_C `[d120,p60,align,vc,rev5,dd20]` | 40d only | FAIL / FAIL / FAIL | HORIZON_NOT_ADVANCED |
| H120_S `[vc]` | 120d only | FAIL / FAIL / PASS | HORIZON_NOT_ADVANCED |
| H120_C `[d5,p20,vc,rev10,dd60,rsi]` | 120d only | PASS / **FAIL** / PASS | HORIZON_NOT_ADVANCED |

## 2. Why H10_C is admitted

Only H10_C advanced at 10 days, via the frozen Level-2 Pareto gate (Δ mean
RankIC +0.0215, Δ mean Spread +0.0029 over C0_H10) with temporal PASS
(4/4 positive blocks). Admission rule used here: **the only 10d component
with formal `HORIZON_ADVANCED_FOR_FURTHER_REVIEW` status**. H10_S is
excluded by its formal `HORIZON_NOT_ADVANCED` (Level-2 fail), not by
judgment.

## 3. Why H40_S is admitted (with warnings)

H40_S is the only 40d component with formal advanced status (Δ mean RankIC
+0.0027, Δ mean Spread +0.0039; blocks +0.038/+0.050/+0.051/+0.071 all
positive). It is admitted **subject to permanent caveats**:
`H40_NO_STRONG_STABILITY_EVIDENCE=true` (retained even though it passed)
and `NEUTRALITY_INDUCED_LOW_FLIP_CAVEAT=true` (its zero hard flips in the
selection diagnostics came from NEUTRAL training direction on 100/100
dates). Its formal evidence remains weak; that is exactly why Q4 exists
and why the minimal-replacement preference favors F1 on near ties.

## 4. Why H120 replacement is rejected

H120_C is formally `HORIZON_NOT_ADVANCED`: its Level-2 comparison against
C0_H120 failed because mean Spread **deteriorated** (+0.1289 vs +0.1618,
Δ −0.0329) despite higher mean RankIC (+0.2427 vs +0.2276). H120_S failed
Level 1 (mean RankIC −0.0001, mean Spread −0.0326). The frozen rule is the
formal gate, not the attractive RankIC number; therefore the design keeps
**C0_H120 unchanged** in all three schemes. No "H120_C 其实也不错"
reinterpretation is permitted.

## 5. Why exactly F0/F1/F2 and nothing else

- `F0_CONTROL` is required as the reproduction anchor: the fused question
  is only answerable against the original C0 fused baseline.
- `F1_H10_REPLACEMENT` isolates Q1 (H10_C transfer into fusion).
- `F2_H10_H40_REPLACEMENT` answers Q2/Q4 (H40_S incremental effect) and
  Q3/Q5 jointly. Its double relative gates (vs F0 and vs F1) make any
  H40-only scheme redundant: **F2 − F1 already isolates the H40
  incremental effect**, so no `F_H40_ONLY` candidate exists (budget
  minimization; §15 of the task is honored by construction).
- The budget is therefore 1 control + 2 new = 3 schemes, frozen; no
  fourth candidate may ever be appended after results.

## 6. Why fusion weights are unchanged

The weights 0.25 / 0.50 / 0.25 are the frozen original D2/C0 fusion
contract (formal `FUSION_WEIGHTS` in
`strategies/sw_sector_rotation/src/model/model.py`, verified during the
fusion-semantics audit — with the z-score step documented in the protocol
§7). This research line studies **component replacement at fixed fusion**;
weight exploration is a separate, explicitly out-of-scope question
(Fusion Weight Research is forbidden this round). No weight was re-tuned,
tested, or "improved" based on Development results.

## 7. Anti-post-hoc declaration

- No enumeration of component combinations was performed.
- No per-date return rescan was performed to pick components.
- The only numbers consulted were the already-published formal aggregate
  statuses and gate outcomes in §1, plus descriptive prediction-distribution
  statistics (mean/std/median/min/max) for the scale audit — which produced
  no fused output and did not influence selection (selection is fully
  determined by §1 statuses).
- Development reuse: this design exists after five studies inspected
  E001-E100; future results remain non-independent regardless of outcome.
