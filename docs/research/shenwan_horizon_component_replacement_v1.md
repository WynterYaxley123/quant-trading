# Shenwan Sector Rotation — Horizon Component Replacement V1 (fixed-fusion hypothesis)

**PREREGISTRATION ONLY. NO FORMAL COMPONENT-REPLACEMENT RESULT IS AUTHORIZED
BY THIS DOCUMENT.**

## 1. Research state, source identity and interpretation

Frozen on `experiment/sw-sector-index-research-baseline` at preregistration
time HEAD `98dfe5c9c256fe31339a2c3ca63ea1753180a7cc` (the previous
handoff commit). Source research: HORIZON-SPECIFIC ALPHA HYPOTHESIS V1 —
preregistration `4d0ee982a0cd4ff1efe76c9fee4c2de807643ac2`, formal result
`de8b77a8da3aeac99fa5ac1fd52d6431cedf2d62`, handoff
`98dfe5c9c256fe31339a2c3ca63ea1753180a7cc`, protocol hash
`d598efd34fe2a6c03832e3faaeadd738cc63a604e5da4c8f1a3740c33e69b8d4`.
The handoff commit diff was audited: it contains only the two handoff files
(no research-semantics change).

`DEVELOPMENT_REUSE_WARNING=true`: this is **POST-AUDIT DEVELOPMENT
HYPOTHESIS REFINEMENT** designed after Iteration-1, Factor Audit V1, Factor
Set V2, Alpha Stability Audit V1 and Horizon-Specific V1 all inspected the
same Development sample E001-E100. Any future formal result of this
preregistration is **NOT independent validation**, **NOT OOS**, not
validated alpha, not ready for trading. Validation and Final OOS remain
SEALED; only Development E001-E100 on U0_FIXED_124 (2025-04-02 …
2025-08-26) may ever be used.

## 2. Motivation (from formal source results only)

The Horizon-Specific V1 formal Development run produced exactly two
same-horizon advances, quoted from its `candidate_summary.json`:

- **H10_C** `[d10, p5, align, vc, dd20]` vs C0_H10: mean RankIC +0.0470 vs
  +0.0254 (Δ +0.0215), mean spread +0.0028 vs −0.0000 (Δ +0.0029); LEVEL1
  PASS / LEVEL2 PASS / TEMPORAL PASS → `HORIZON_ADVANCED_FOR_FURTHER_REVIEW`.
- **H40_S** `[vc]` vs C0_H40: mean RankIC +0.0524 vs +0.0497 (Δ +0.0027),
  mean spread +0.0078 vs +0.0039 (Δ +0.0039); all three gates PASS →
  `HORIZON_ADVANCED_FOR_FURTHER_REVIEW`. **Warnings retained**:
  `H40_NO_STRONG_STABILITY_EVIDENCE=true` and
  `NEUTRALITY_INDUCED_LOW_FLIP_CAVEAT=true` — vc's zero hard flips came
  from NEUTRAL training direction (100/100 dates at 40d), which is not
  proven stable directional alpha.
- **H120**: no replacement candidate passed the relative gate.
  H120_C `[d5, p20, vc, rev10, dd60, rsi]` raised mean RankIC (+0.2427 vs
  +0.2276) but **deteriorated spread** (+0.1289 vs +0.1618) and is formally
  `HORIZON_NOT_ADVANCED`; H120_S is neutral. Therefore **no H120
  replacement enters this design** (§8).

## 3. Research questions

- **Q1** — does replacing the H10 component of the original C0 fused
  strategy with H10_C improve the fused strategy at unchanged fusion
  weights?
- **Q2** — with H10 replaced, does further replacing H40 with H40_S add
  incremental fused improvement?
- **Q3** — do the horizon-local improvements transfer into the original
  multi-horizon fused ranking rather than staying horizon-local?
- **Q4** — does H40_S's weak evidence add value inside fixed fusion, or
  does it damage the H10 replacement's improvement?
- **Q5** — by keeping C0_H120 unchanged, is the original 120d stable
  support preserved?

These are hypotheses to test in a future authorized run, not established
claims.

## 4. Exact scheme freeze and budget

Exactly **3 schemes: 1 control + 2 new hypotheses**. No fourth candidate,
no backfill. Candidate IDs are frozen as follows:

| Scheme | h10 component | h40 component | h120 component | fusion weights |
|---|---|---|---|---|
| `F0_CONTROL` | C0_H10 | C0_H40 | C0_H120 | 0.25 / 0.50 / 0.25 |
| `F1_H10_REPLACEMENT` | **H10_C** | C0_H40 | C0_H120 | 0.25 / 0.50 / 0.25 |
| `F2_H10_H40_REPLACEMENT` | **H10_C** | **H40_S** | C0_H120 | 0.25 / 0.50 / 0.25 |

Exact component factor lists (pipeline order, from the frozen source
config):

- C0_H10 / C0_H40 / C0_H120: the 19 frozen factors
  `d5,d10,d20,d60,d120,p5,p10,p20,p60,p120,align,v5,v20,vc,rev5,rev10,dd20,dd60,rsi`
- H10_C: `[d10, p5, align, vc, dd20]`
- H40_S: `[vc]`

`F0_CONTROL` is not a candidate; it is the same-horizon-component
reconstruction of the original D2/C0 fused baseline. All three schemes are
always computed in a future run (no adaptive skipping when F1 fails).

**No H40-only candidate** (budget minimization: F2 − F1 already isolates
the H40 incremental effect under fixed H10 replacement). **No H120
replacement** (H120_C / H120_S are formally NOT_ADVANCED; their high
RankIC does not override the spread deterioration — §8). **No component
search** of any kind.

## 5. Component source manifest

Machine manifest: `research/configs/horizon_component_replacement_v1_sources.json`
(hashes below were recomputed from the artifact bytes during this
preregistration, not copied):

| component | predictions SHA-256 | aggregate metrics SHA-256 | first==rerun |
|---|---|---|---|
| C0_H10 | `3922081c9ca15bf49102d38c0098b33b198e464e55fa978cf11ffe42ef580781` | `36568fb873f97135fa427989874eb53c5feda23615ebd78fff6ce6130ab3f07e` | yes |
| C0_H40 | `737ba02766c2afea9848c432e9aa13910dd8119cb02f317846be5e19e0d5960a` | `8e9dc07117f5f83b2c4556ee1bb5f9b1ee5315415c1f7a9228447e2cc1e23bbc` | yes |
| C0_H120 | `e41df4f8214520a56eb8f5e585eda5fc641f70cb2bda6d6cc76ac24cb721c5d6` | `ccc6dcb2b9e995cc44c935c803882e0636a088bf2328ef958d9921d7d872a91b` | yes |
| H10_C | `e50c405b8178f4b1afa2ec2e8bca1e8e1b68e0e9afc57f2f700d07c22120ab59` | `1777f47b498dd5f622c1a0aa2338f95ac94f66c7e294bb8afd12a1e59761e010` | yes |
| H40_S | `dd9b8277bd02bbf3b510e8d6cad297a6982a001255800e33dd697183c19aae07` | `09307319def853cb58d9013ee6164a22fbcbc0e1c2fdef44d6c73137f156ca9f` | yes |

Source run: `reports/research/shenwan_sector_index/horizon_specific_alpha_v1_20260925_130230_272283_utc/`
(first) and `…_131549_730952_utc/` (determinism rerun, 57/57 byte-identical
at source). C0 components are **bit-exact** reproductions of the original
D2 per-horizon prediction columns (verified with round-trip float parsing).
`/reports/research/` is untracked by convention; provenance = run path +
content SHA-256 + result commit + protocol hash.

## 6. Component source policy (frozen)

- **Prefer artifact reuse**: a future formal run must consume the
  already-generated, determinism-verified component prediction artifacts
  above. The research question is COMPONENT REPLACEMENT / FUSION, not
  horizon-model retraining; reuse maximally isolates the fusion effect.
  `noRetraining=true`.
- The original D2 fusion contract requires only per-horizon score vectors
  at fusion time (no internal representation regeneration) — verified from
  `fuse_periods` (§7). There is no ambiguity, so no
  COMPONENT_REUSE_SEMANTICS_BLOCKER.
- If a future architecture must replay components instead of reading
  artifacts, every replayed prediction must first pass an identity check
  against the source artifact (≤1e-12; bit-exact expected) — else
  `COMPONENT_REPLAY_IDENTITY_BLOCKER`.
- **Alignment**: all components share the exact grid (100 Development
  ordinals × 124 sector codes; identical signal dates and snapshot). Future
  runs must hard-align on `(ordinal, signal_date, sector_code)`; no outer
  join with fill, no forward-fill, no nearest-date, no silent universe
  shrink — else `COMPONENT_ALIGNMENT_BLOCKER`.

## 7. FUSION SEMANTICS — exact formal formula (audited from code)

The prompt's shorthand "0.25·pred10 + 0.50·pred40 + 0.25·pred120" is **not**
the formal implementation. Per the prompt's own precedence rule the formal
code is authoritative
(`strategies/sw_sector_rotation/src/model/model.py::CrossSectionalRidgeModel.fuse_periods`,
module SHA-256 `61fed9e6…86785ba`). Exact semantics, frozen:

1. For each date, take the three horizon score vectors from the component
   models' **raw Ridge outputs** (no per-horizon transform before fusion).
2. Universe = **intersection** of sectors scored by all three horizons
   (expected U0=124; a coverage mismatch emits a warning and still fuses on
   the intersection; an empty intersection or a missing horizon yields no
   fused ranking).
3. Per horizon, per date: pre-scale by `m = max(1, max|scores|)`, then
   cross-sectional **z-score** with population std (ddof=0):
   `z_h(s) = (v_h(s)/m − mean(v_h/m)) / std(v_h/m)`; if `std ≤ 1e-12/m`,
   that horizon contributes `z = 0`. (The pre-scale cancels in the z-score:
   the transform is affine-invariant.)
4. `fusedScore(s) = (0.25·z10(s) + 0.50·z40(s) + 0.25·z120(s)) / (0.25+0.50+0.25)`
   with weights `{"short":0.25,"medium":0.50,"long":0.25}`.
5. Ranking: fused score descending; exact ties broken by **sector code
   ascending**. Top5 = first five of the fused ranking.

Frozen weights: **h10 0.25 / h40 0.50 / h120 0.25** — the only weights
permitted. No other combination may ever be tested in this research line
without a new preregistration.

**Fusion scale invariance**: because step 3 z-scores each component
cross-sectionally per date, the fused score/ranking is invariant to any
per-component, per-date affine transform of raw scores. Component scale
differences therefore do **not** bias the fused result, and
`RAW_COMPONENT_SCALE_DEPENDENCE_WARNING` does **not** apply (see the
descriptive scale audit in the sources manifest: component stds differ up
to ~40×). The only scale-related edge is the degenerate-std fallback
(§7.3). No normalization, clipping, or rescaling may be added on top.

## 8. Evaluation contract (exact reuse of the frozen D2/C0 contract)

Authority: `research/sector_development_baseline.py::evaluate_date` (module
SHA-256 `50f92983…16dbb108`) and
`research/development_iteration1_protocol.py::COMPARISON_WEIGHTS`
(module SHA-256 `556de462…0b45c9f8`). Frozen:

- Evaluation labels: absolute forward return `close[t+h]/close[t] − 1` on
  the common calendar, `label_end = calendar[t+h]`; no shift/fill on
  missing endpoints; per-horizon complete case (124 valid score/label
  pairs) required, else null metrics with reason.
- The 15-metric contract per date: `IC_h`, `RankIC_h` (Pearson /
  average-tie Spearman on **raw per-horizon component scores** vs labels),
  `Top5_forward_return_h` (mean label over the **fused** Top5),
  `Universe_forward_return_h`, `Top5_minus_universe_h`, for h ∈ {10,40,120}.
- Aggregates: mean / median / population std (ddof=0) / min / max /
  validDates / nullDates per metric.
- Primary metrics: `Weighted_RankIC = 0.25·meanRankIC10 + 0.50·meanRankIC40
  + 0.25·meanRankIC120` and `Weighted_Spread = 0.25·meanTop5MinusUniverse10
  + 0.50·…40 + 0.25·…120`. No new composite score may be created.
- The same frozen 15-metric contract and primary metrics apply to F0, F1
  and F2 identically.

## 9. Advancement rules (frozen; applied to F1/F2 only)

1. **LEVEL 1 (basic)**: `Weighted_RankIC > 0 AND Weighted_Spread > 0`
   (strictly greater; equality fails) → else `FUSION_NOT_ADVANCED`.
2. **F1 vs F0 (Pareto)**: `F1 WR > F0 WR AND F1 WS >= F0 WS`, **OR**
   `F1 WS > F0 WS AND F1 WR >= F0 WR` → else `F1_RELATIVE_GATE_FAIL`.
3. **F2 vs F0 (Pareto)**: same rule against F0 → else `F2_VS_F0_GATE_FAIL`.
4. **F2 vs F1 (incremental H40)**: same rule against F1 → else
   `H40_INCREMENTAL_REPLACEMENT_NOT_SUPPORTED`. F2 advances only when
   LEVEL 1 **and** vs F0 **and** vs F1 all pass.
5. **Horizon red-flag guard**: if any of mean RankIC10 / RankIC40 /
   RankIC120 < **−0.02** (frozen research-discipline threshold), the
   candidate is blocked from `FUSION_ADVANCED_FOR_FURTHER_REVIEW` even if
   rules 1-4 pass → substatus `HORIZON_RED_FLAG`.
6. **Temporal gate** (F1/F2; design discipline, not statistical truth):
   using fixed blocks B1=E001-025, B2=E026-050, B3=E051-075, B4=E076-100
   and block Weighted metrics built with the same 0.25/0.50/0.25 weights
   over per-horizon block means: at least **3/4** blocks with block
   Weighted RankIC > 0, and at most **1/4** blocks with block Weighted
   RankIC < −0.02 → else `FUSION_TEMPORAL_STABILITY_GATE_FAIL`.
   Block Weighted Spread is **reported but not gated** (no post-hoc extra
   spread-block gate).

Allowed status labels only: `CONTROL_NOT_A_CANDIDATE` (F0),
`FUSION_ADVANCED_FOR_FURTHER_REVIEW`, `FUSION_NOT_ADVANCED`, with
substatuses `LEVEL1_PASS/FAIL`, `VS_F0_PASS/FAIL`, `VS_F1_PASS/FAIL`
(F2 only for VS_F1), `TEMPORAL_PASS/FAIL`, `HORIZON_RED_FLAG`,
`MINIMAL_REPLACEMENT_PREFERENCE`. Forbidden anywhere: WINNER, BEST,
VALIDATED, PRODUCTION, TRADABLE, LIVE_READY.

All three schemes are computed in every future run; F2 is evaluated even if
F1 fails (no adaptive execution).

## 10. Minimal replacement preference (simplicity)

If **both** F1 and F2 pass every gate and simultaneously
`|F2 WR − F1 WR| < 0.01` and `|F2 WS − F1 WS| < 0.01`, prefer **F1** with
label `MINIMAL_REPLACEMENT_PREFERENCE`: one replaced component is lower
research complexity and H40_S's evidence is weak. This is a tie-break
discipline, **not** statistical significance; raw metrics are always
reported separately.

## 11. F0 reproducibility design (frozen now)

A future formal run must reproduce the original C0 fused output **before**
any F1/F2 evaluation, against the frozen reference artifacts (§5 manifest
`f0ReferenceArtifacts`):

- `fused_score`: identity within 1e-12 (bit-exact expected: components are
  bit-exact D2 reproductions and `fuse_periods` is deterministic),
- `fused_rank`: exact, `top5`: exact (per ordinal × sector, vs
  `D2/per_date_predictions.csv` SHA-256 `e39d8368…a00e1`),
- primary metrics identity within 1e-12 (vs `D2/aggregate_metrics.json`
  SHA-256 `cc7f9b57…7c86b4`), daily metrics vs `D2/per_date_metrics.csv`
  SHA-256 `4ee1f100…030a42`.

Failure → `FUSION_CONTROL_REPRODUCTION_BLOCKER`. This identity level is
fixed here, not after results.

## 12. Future result schema (frozen)

Run directory `reports/research/shenwan_sector_index/horizon_component_replacement_v1_<timestamp>_utc/`
following repo convention, containing at least: `metadata.json`,
`candidate_summary.json`, `aggregate_metrics.json`, `per_date_metrics.csv`,
`per_date_predictions.csv`, `block_stability.csv`,
`component_source_integrity.json`, `fusion_integrity.json`,
`advancement_decision.json`, `integrity.json`. Future `metadata.json` must
carry at least: researchType `HORIZON_COMPONENT_REPLACEMENT_V1`,
phase=DEVELOPMENT, preregistrationCommit, protocolHash,
executionGitCommit, sourceResultCommit `de8b77a8da3aeac99fa5ac1fd52d6431cedf2d62`,
sourceHandoffCommit `98dfe5c9c256fe31339a2c3ca63ea1753180a7cc`,
splitPolicyHash, sectorSnapshotId, developmentIds `E001-E100`, candidate
IDs, component mapping, fusion weights, `noWeightSearch=true`,
`noRetraining=true`, validation=SEALED, finalOos=SEALED, strictPit=false,
classification=FIXED_CLASSIFICATION_RESEARCH, executable=false,
tradable=false, `DEVELOPMENT_REUSE_WARNING=true`,
`H40_NO_STRONG_STABILITY_EVIDENCE=true`,
`NEUTRALITY_INDUCED_LOW_FLIP_CAVEAT=true`.

## 13. Immutable warnings

- `H40_NO_STRONG_STABILITY_EVIDENCE=true` — retained forever, even if a
  future F2 looks good.
- `NEUTRALITY_INDUCED_LOW_FLIP_CAVEAT=true` — H40_S/H120_S (vc) and H10_S
  (p5) selection keys reflect neutral training direction, not proven
  directional stability.
- `DEVELOPMENT_REUSE_WARNING=true` (§1).
- H120_C / H120_S remain `HORIZON_NOT_ADVANCED`; no reinterpretation
  ("H120_C 其实也不错" is forbidden) — H120 stays C0_H120.

## 14. Prohibitions (complete)

No weight search / grid / random / manual tuning; no dynamic fusion; no
drop-horizon; no H120 replacement; no H40-only candidate; no component
search (H10_C2, H40_C, alternate/conditional/regime-switch components,
dynamic horizon selectors); no parameter search; no model search (Ridge
alpha tuning, ElasticNet, Lasso, LightGBM, XGBoost, NN, ensembles); no new
factors; no sign flips/inversions; no retraining drift; no post-hoc
component combination enumeration (`POST_HOC_COMPONENT_SEARCH_BLOCKER`);
no Validation / Final OOS access (`SEALED_OR_NON_DEVELOPMENT_ACCESS_BLOCKER`
on any E101+ or sealed-phase touch); no portfolio, ETF, QMT,
Dashboard/API; no push/merge. No formal component-replacement result may be
generated during this preregistration.

## 15. Protocol identity and drift

Machine config: `research/configs/horizon_component_replacement_v1.json`.
Source manifest: `research/configs/horizon_component_replacement_v1_sources.json`.
Selection trace:
`docs/research/shenwan_horizon_component_replacement_v1_selection_trace.md`.
Protocol module: `research/horizon_component_replacement_v1_protocol.py`
(fail-closed). The canonical SHA-256 protocol identity covers: exact
candidate IDs, component mappings, exact factor lists, fusion weights and
semantics, source-manifest identity (hashes), advancement rules, horizon
red flag, block/temporal gate, minimal-replacement preference, the
evaluation contract identity, prohibitions, and the byte hashes of this
document, the selection trace, both JSON configs and both modules (self
hash normalized). Any later drift must raise
`HORIZON_COMPONENT_REPLACEMENT_PROTOCOL_HASH_MISMATCH` — it is never a
license to update the hash after seeing results.

## 16. Future NEXT_RESEARCH_GATE (frozen values)

After a future authorized formal run only these values may be used:
`COMPONENT_REPLACEMENT_SUPPORTED_FOR_FURTHER_REVIEW`,
`H10_REPLACEMENT_ONLY_SUPPORTED`, `H10_H40_REPLACEMENT_SUPPORTED`,
`COMPONENT_REPLACEMENT_NOT_SUPPORTED`, `MIXED_COMPONENT_REPLACEMENT_EVIDENCE`,
`DIAGNOSTIC_INCONCLUSIVE`. Never `PARAMETER_RESEARCH_READY` or
`VALIDATION_READY`. Any further research requires human review and a new
preregistration.

## 17. Execution sequencing and stop point

This commit is **preregistration only**: no fused prediction, no fused
RankIC, no fused Spread, no Top5 comparison, no F0/F1/F2 run. The only
next authorized action is human review, then a separate instruction to run
Horizon Component Replacement V1 under this frozen protocol. Component
scale audit during preregistration was descriptive only (distributions of
existing artifacts; §5 manifest) and produced no fused output of any kind.
