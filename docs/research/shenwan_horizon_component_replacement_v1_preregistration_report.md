# SHENWAN HORIZON COMPONENT REPLACEMENT V1 PREREGISTRATION REPORT

FINAL STATUS: **HORIZON COMPONENT REPLACEMENT V1 PREREGISTRATION COMPLETE
WITH NON-BLOCKING WARNINGS**. PREREGISTRATION ONLY — **NO FORMAL
COMPONENT-REPLACEMENT RESULTS GENERATED**. No fused prediction, fused
RankIC, fused Spread or Top5 comparison was computed at any point.

## 1. RESEARCH STATE

- Branch: `experiment/sw-sector-index-research-baseline`
- HEAD before: `98dfe5c9c256fe31339a2c3ca63ea1753180a7cc` (previous handoff)
- HEAD after: the commit introducing this report
  (`research: preregister horizon component replacement v1`); full SHA in
  the handoff package and the final reply
- Working tree: clean at preflight; only the seven preregistration files
  were added by the commit; clean afterward

## 2. SOURCE RESEARCH

- Horizon-Specific Alpha Hypothesis V1 preregistration commit:
  `4d0ee982a0cd4ff1efe76c9fee4c2de807643ac2`
- Formal result commit: `de8b77a8da3aeac99fa5ac1fd52d6431cedf2d62`
- Handoff commit: `98dfe5c9c256fe31339a2c3ca63ea1753180a7cc`
- Source protocol hash (re-verified this round via `verify_protocol()`):
  `d598efd34fe2a6c03832e3faaeadd738cc63a604e5da4c8f1a3740c33e69b8d4`

## 3. HANDOFF AUDIT

`git diff de8b77a8da3aeac99fa5ac1fd52d6431cedf2d62..98dfe5c9c256fe31339a2c3ca63ea1753180a7cc`
contains exactly two files — `handoff_horizon_specific_alpha_v1.md` and
`handoff_horizon_specific_alpha_v1.json` (239 insertions, nothing else).
No runner / protocol / config / tests / model logic / factor definition /
target semantics / formal-metrics change: **no post-result semantic
drift**. The previous handoff was also re-verified field-by-field against
the real repo (15/15 checks: commits, protocol hash, candidates, metrics,
statuses, test counts, determinism record, seals).

## 4. MOTIVATION

Two horizon-local components formally advanced in the source run — H10_C
(ΔRankIC +0.0215, ΔSpread +0.0029 over C0_H10; all gates PASS) and H40_S
(ΔRankIC +0.0027, ΔSpread +0.0039 over C0_H40; all gates PASS, warnings
retained). The open question is whether these horizon-local improvements
transfer into the original fixed-fusion C0 strategy. H120 produced no
admissible replacement (formal gate failures).

## 5. RESEARCH QUESTIONS

Q1 H10_C replacement improves the fused strategy at unchanged weights?
Q2 does H40_S add incremental fused improvement on top of the H10
replacement? Q3 do horizon-local gains transfer into the multi-horizon
fused ranking? Q4 does H40_S's weak evidence help or hurt inside fixed
fusion? Q5 does keeping C0_H120 preserve the original 120d support?

## 6. CONTROL — F0_CONTROL

Components C0_H10 + C0_H40 + C0_H120 at weights 0.25/0.50/0.25 — the
original D2/C0 fused baseline. Status label `CONTROL_NOT_A_CANDIDATE`.
Before any F1/F2 evaluation a future run must reproduce the original fused
output: fused_score within 1e-12 (bit-exact expected), fused_rank and Top5
exact, primary metrics within 1e-12, against the frozen D2 reference
artifacts (manifest `f0ReferenceArtifacts`) — else
`FUSION_CONTROL_REPRODUCTION_BLOCKER`.

## 7. F1_H10_REPLACEMENT

H10 component = **H10_C** `[d10, p5, align, vc, dd20]`; H40/H120 unchanged
(C0_H40, C0_H120). The only change versus F0 is the 10d component.
Purpose: isolate Q1.

## 8. F2_H10_H40_REPLACEMENT

H10 = **H10_C**, H40 = **H40_S** `[vc]`, H120 = C0_H120. Answers Q2/Q4 via
F2 − F1 (incremental H40 effect under fixed H10 replacement) and Q3/Q5 via
F2 vs F0.

## 9. WHY NO H40-ONLY CANDIDATE

Candidate-budget minimization: F2 − F1 already isolates the H40
replacement's incremental effect; a separate F_H40_ONLY scheme would add
budget without new information. Frozen: `noH40OnlyCandidate=true`; the
candidate set is exactly F0/F1/F2.

## 10. WHY NO H120 REPLACEMENT

H120_C is formally `HORIZON_NOT_ADVANCED` (Level-2 spread deterioration:
+0.1289 vs +0.1618 despite higher RankIC) and H120_S failed Level 1. The
frozen formal gate governs, not the attractive RankIC number; no
reinterpretation is permitted. H120 stays **C0_H120** in every scheme.

## 11. COMPONENT SOURCE MANIFEST

Path: `research/configs/horizon_component_replacement_v1_sources.json`.
All five component artifact SHA-256s were **recomputed from the artifact
bytes** this round (not copied) and cross-checked against the source-run
metadata and against the determinism rerun — first == rerun == recorded
for all 10 files. Representative:

| component | predictions SHA-256 | metrics SHA-256 |
|---|---|---|
| C0_H10 | `3922081c9ca15bf49102d38c0098b33b198e464e55fa978cf11ffe42ef580781` | `36568fb873f97135fa427989874eb53c5feda23615ebd78fff6ce6130ab3f07e` |
| C0_H40 | `737ba02766c2afea9848c432e9aa13910dd8119cb02f317846be5e19e0d5960a` | `8e9dc07117f5f83b2c4556ee1bb5f9b1ee5315415c1f7a9228447e2cc1e23bbc` |
| C0_H120 | `e41df4f8214520a56eb8f5e585eda5fc641f70cb2bda6d6cc76ac24cb721c5d6` | `ccc6dcb2b9e995cc44c935c803882e0636a088bf2328ef958d9921d7d872a91b` |
| H10_C | `e50c405b8178f4b1afa2ec2e8bca1e8e1b68e0e9afc57f2f700d07c22120ab59` | `1777f47b498dd5f622c1a0aa2338f95ac94f66c7e294bb8afd12a1e59761e010` |
| H40_S | `dd9b8277bd02bbf3b510e8d6cad297a6982a001255800e33dd697183c19aae07` | `09307319def853cb58d9013ee6164a22fbcbc0e1c2fdef44d6c73137f156ca9f` |

C0 components are **bit-exact** reproductions of the original D2
per-horizon prediction columns (round-trip parsing). Source result commit
`de8b77a8…`, source protocol hash `d598efd3…`, first/rerun identity
verified. `/reports/research/` is untracked by convention; provenance =
run path + content hashes + commits + protocol hash.

## 12. FUSION SEMANTICS (audited from formal implementation)

**Semantic-audit finding**: the shorthand raw linear combination is NOT the
formal implementation. Authority =
`strategies/sw_sector_rotation/src/model/model.py::CrossSectionalRidgeModel.fuse_periods`
(module SHA-256 `61fed9e6…86785ba`), and per the task's precedence rule the
formal code governs. Exact frozen formula:

`fusedScore(s) = 0.25·z10(s) + 0.50·z40(s) + 0.25·z120(s)` (Σw = 1),
where each `z_h` is the **per-date cross-sectional z-score** (population
std, ddof=0) of the raw Ridge component scores over the intersection of
horizon-scored sectors (expected U0=124), with magnitude pre-scale
`m = max(1, max|score|)` that cancels exactly in the z, and a degenerate-std
fallback `z = 0`. Ranking = fused score descending, sector-code ascending
tie-break; **Top5 = first five of the fused ranking**.

Evaluation contract (authority `evaluate_date` + `COMPARISON_WEIGHTS`,
module hashes `50f92983…` / `556de462…`): 15 frozen metrics per date —
per-horizon IC/RankIC on raw component scores, Top5 return over the FUSED
Top5, universe return, Top5-minus-universe; aggregates
mean/median/population-std/min/max/validDates; primary metrics
`Weighted_RankIC = 0.25·meanRankIC10 + 0.50·meanRankIC40 + 0.25·meanRankIC120`
and `Weighted_Spread` analogously. Labels = absolute forward returns;
complete-case 124 required; tie-break sector code ascending. No new
composite score. These semantics are pinned by tests against the real
implementations (`fuse_periods` z-score formula, affine invariance,
degenerate case, fused-Top5 evaluation).

## 13. COMPONENT SCALE AUDIT (descriptive only)

Prediction distributions of the five existing component artifacts
(12400 rows each): stds `C0_H120 4.16e-2`, `C0_H40 2.31e-2`,
`C0_H10 7.60e-3`, `H10_C 2.41e-3`, `H40_S 1.00e-3` — up to ~40× apart,
ranges ~2 orders of magnitude. **Consequence**: because `fuse_periods`
z-scores each component cross-sectionally per date, the fused result is
invariant to per-component per-date affine transforms — raw scale
differences do not affect fusion. Therefore
`RAW_COMPONENT_SCALE_DEPENDENCE_WARNING` does **not** apply
(`rawComponentScaleDependenceWarning=false` in the manifest, justified by
the invariance). No standardization/normalization/clipping may be added.
No fused output of any kind was produced during this audit (§13 = existing
artifact distributions only).

## 14. CANDIDATE BUDGET

1 control + 2 new = **3 schemes total**. Frozen; no fourth candidate, no
backfill; F2 is computed even if F1 fails (no adaptive execution).

## 15. ADVANCEMENT RULES (frozen)

- LEVEL 1: `Weighted_RankIC > 0 AND Weighted_Spread > 0` (strict).
- F1 vs F0 and F2 vs F0: Pareto — strict improvement in one primary with
  non-decrease in the other (either order).
- F2 vs F1: same Pareto rule (incremental H40 gate); F2 advances only when
  LEVEL 1 + vs F0 + vs F1 all pass.
- Horizon red flag: any mean RankIC10/40/120 < **−0.02** blocks advancement
  (`HORIZON_RED_FLAG`).
- Temporal gate (F1/F2): ≥3/4 blocks with block Weighted RankIC > 0 and
  ≤1/4 blocks with block Weighted RankIC < −0.02, block Weighted metrics
  built with the same 0.25/0.50/0.25 weights
  (`FUSION_TEMPORAL_STABILITY_GATE_FAIL`); block Weighted Spread is
  reported, not gated.
- Labels: `CONTROL_NOT_A_CANDIDATE` / `FUSION_ADVANCED_FOR_FURTHER_REVIEW`
  / `FUSION_NOT_ADVANCED` with gate substatuses; WINNER/BEST/VALIDATED/
  PRODUCTION/TRADABLE/LIVE_READY forbidden.

## 16. MINIMAL REPLACEMENT PREFERENCE

If F1 and F2 both pass all gates and both primary deltas are < 0.01 in
absolute value → prefer F1 (`MINIMAL_REPLACEMENT_PREFERENCE`); tie-break
discipline only, never a statistical claim.

## 17. H40 WEAK-EVIDENCE WARNING (immutable)

`H40_NO_STRONG_STABILITY_EVIDENCE=true` — retained permanently, including
if a future F2 result looks strong.

## 18. NEUTRALITY CAVEAT (immutable)

`NEUTRALITY_INDUCED_LOW_FLIP_CAVEAT=true` — H40_S/H120_S (`vc`) and H10_S
(`p5`) selection keys reflect NEUTRAL training direction, not proven
directional stability.

## 19. DEVELOPMENT REUSE WARNING

`DEVELOPMENT_REUSE_WARNING=true` — designed after five studies inspected
E001-E100; future results are NOT independent validation, NOT OOS, not
validated alpha, not ready for trading. Validation and Final OOS SEALED.

## 20. PROHIBITIONS

No weight search (weights frozen 0.25/0.50/0.25), no dynamic fusion, no
drop-horizon, no H120 replacement, no H40-only candidate, no component
search/conditional/regime-switch components, no parameter search, no model
search, no new factors, no sign flips, no retraining drift (artifact reuse
required; replay must identity-check), no formal result generation during
preregistration, no Validation/OOS access, no portfolio/ETF/QMT/Dashboard/
API, no push/merge.

## 21. MACHINE CONFIG

`research/configs/horizon_component_replacement_v1.json`
(canonical hash `4c2f18815e47f9352a34f4f6bba222a260cbfff73cf6c49fc3e55438dc78adf6`).

## 22. SOURCE MANIFEST

`research/configs/horizon_component_replacement_v1_sources.json`
(canonical hash `35af45f03a8c04490c5bb5ce009476fac266b0ae0027b2b9db9d50d9d6786c3f`).

## 23. PROTOCOL

- Path: `docs/research/shenwan_horizon_component_replacement_v1.md`
- Protocol SHA-256 (canonical identity covering candidates, component
  mappings, factor lists, fusion weights/semantics, source-manifest
  identity, advancement/red-flag/temporal/minimal rules, prohibitions, and
  byte hashes of docs/configs/modules):
  **`4267d73f38fc8353002459b24640148cc49c4e5777b364eb14ca84404aef9fa7`**
- Selection trace:
  `docs/research/shenwan_horizon_component_replacement_v1_selection_trace.md`
- Module: `research/horizon_component_replacement_v1_protocol.py`
  (fail-closed; drift raises
  `HORIZON_COMPONENT_REPLACEMENT_PROTOCOL_HASH_MISMATCH`)

## 24. TESTS

- Targeted (`tests/test_horizon_component_replacement_v1.py`):
  **passed 24, failed 0, skipped 0** — covers the full checklist:
  researchType, Development-only/sealed phases, candidate count/IDs,
  exact F0/F1/F2 mappings, exact factor lists, H120 stays C0 and
  H120_C/S forbidden, no H40-only, weights exact/sum/forbidden-search,
  no new factor / no sign flip, source manifest completeness, artifact
  existence + hash reproduction, first/rerun identity, Level-1/F1-vs-F0/
  F2-vs-F0/F2-vs-F1 rules, red flag −0.02 strict, B1-B4, temporal 3/4,
  minimal-replacement preference, status-label restrictions, immutable
  warnings, no parameter/model search, protocol hash + config↔protocol +
  manifest↔protocol identity, deterministic serialization, and the
  **lifecycle-aware** result-leak guard (tmp_path: empty root PASS, fake
  result BLOCKER, unrelated old results PASS; no permanent filesystem
  absence requirement).
- Full offline suite: **passed 623, failed 0, skipped 2, deselected 17**.

## 25. RESULT LEAK AUDIT

**NO FORMAL COMPONENT-REPLACEMENT RESULTS GENERATED.** Live scan of
`reports/research/shenwan_sector_index/` (runtime gate
`guard_no_formal_results`) found zero entries matching
`horizon_component_replacement_v1_*` / `component_replacement_v1_*` /
`fusion_replacement_v1_*`. Git diff and untracked files contain only
protocol, config, source manifest, selection trace, protocol module and
tests. No fused prediction, fused RankIC, fused Spread or Top5 result
exists anywhere.

## 26. HISTORICAL IMMUTABILITY

**PASS** — no tracked file modified (`git diff` vs HEAD empty before
commit); Iteration-1 / Factor Audit V1 / Factor Set V2 / Alpha Stability
metadata hashes all UNCHANGED; Horizon-Specific V1 protocol still verifies;
both source CSVs UNCHANGED; the previous handoff files untouched.

## 27. RESEARCH COMPLIANCE

Development only (E001-E100) ✓ · Validation untouched (SEALED) ✓ · Final
OOS untouched (SEALED) ✓ · no formal run ✓ · no weight search ✓ · no
horizon drop ✓ · no H120 replacement ✓ · no parameter search ✓ · no new
factors ✓ · no sign flip ✓ · no model change ✓ · no post-hoc component
search ✓ · no Docker/dependency/Hikyuu changes ✓ · no Dashboard/API ✓ · no
portfolio/ETF/QMT ✓ · no push/merge ✓.

## 28. ENVIRONMENT_CHANGED

**false** — frozen image `sha256:57858238…02e5` (`quant-research:py3.12`),
all commands via `docker compose exec quant-research`.

## 29. PREREGISTRATION COMMIT

The commit introducing this report
(`research: preregister horizon component replacement v1`), containing the
protocol document, selection trace, machine config, source manifest,
protocol module and targeted tests. Full SHA recorded in the handoff
package and the final reply. No amend/rebase/push/merge.

## 30. NEXT AUTHORIZED ACTION

**RUN HORIZON COMPONENT REPLACEMENT V1 UNDER FROZEN PROTOCOL AFTER HUMAN
REVIEW.** Not executed automatically.

## 31. FINAL STATUS

**HORIZON COMPONENT REPLACEMENT V1 PREREGISTRATION COMPLETE WITH
NON-BLOCKING WARNINGS**

1. **Fusion-semantics audit finding**: the formal fusion is a per-date
   cross-sectional z-scored weighted average, not a raw prediction linear
   combination. Resolved by the task's explicit precedence rule (formal
   code authoritative); the exact formula is frozen in protocol §7 and
   pinned by tests. Flagged so no future runner implements the raw
   shorthand.
2. **Component scale caveat resolved**: raw scales differ up to ~40× but
   the z-score step makes fusion affine-invariant, so
   `RAW_COMPONENT_SCALE_DEPENDENCE_WARNING` does not apply — recorded with
   justification in the manifest and protocol.
3. `reports/research/` artifacts are untracked by convention; provenance
   relies on protocol hash + commits + content hashes.
4. Future rank-metric recomputation from CSVs must use
   `float_precision="round_trip"` (carried-over verification note).
