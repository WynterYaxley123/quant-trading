# SHENWAN HORIZON COMPONENT REPLACEMENT V1 FORMAL DEVELOPMENT RUN REPORT

## 1. FINAL STATUS

**HORIZON COMPONENT REPLACEMENT V1 FORMAL DEVELOPMENT RUN COMPLETE WITH NON-BLOCKING WARNINGS.** This is post-audit Development hypothesis refinement, not independent Validation, Final OOS, strategy validation, a tradable portfolio, or a claim of statistical significance.

## 2. RESEARCH STATE

- Branch: `experiment/sw-sector-index-research-baseline`.
- HEAD at start: `d28e42bf7bb09fcc5b9faa19ab3ff0a96429c1cd`.
- Clean execution implementation commit and execution HEAD: `fb207b8b868a3aaceed568d4a8e1b62340371bff`.
- Result commit: the commit containing this report; its full SHA is recorded in the separate handoff and final task response. A committed file cannot contain its own commit SHA.
- Final HEAD: the later handoff commit, if created; the final task response is authoritative for that self-referential value.
- Worktree: clean at preflight, execution, and post-run artifact audit. Ignored `reports/research/` artifacts are not tracked modifications.

## 3. PREREGISTRATION

Preregistration `95e54ee6461b315b51f5ca7cc17cd985caa96a1d`; preregistration handoff `d28e42bf7bb09fcc5b9faa19ab3ff0a96429c1cd`. Protocol: `docs/research/shenwan_horizon_component_replacement_v1.md`, frozen hash `4267d73f38fc8353002459b24640148cc49c4e5777b364eb14ca84404aef9fa7`. Machine config: `research/configs/horizon_component_replacement_v1.json`, hash `4c2f18815e47f9352a34f4f6bba222a260cbfff73cf6c49fc3e55438dc78adf6`. Source manifest: `research/configs/horizon_component_replacement_v1_sources.json`, hash `35af45f03a8c04490c5bb5ce009476fac266b0ae0027b2b9db9d50d9d6786c3f`. Runtime protocol verification passed. Git diff from preregistration over frozen protocol, config, manifest, selection trace, protocol module, and preregistration report is empty.

## 4. SOURCE PROVENANCE

Source Horizon-Specific Alpha V1 result commit `de8b77a8da3aeac99fa5ac1fd52d6431cedf2d62`; source handoff `98dfe5c9c256fe31339a2c3ca63ea1753180a7cc`; source protocol hash `d598efd34fe2a6c03832e3faaeadd738cc63a604e5da4c8f1a3740c33e69b8d4`. Both source roots are under `reports/research/shenwan_sector_index/`:

- First: `horizon_specific_alpha_v1_20260925_130230_272283_utc/`.
- Rerun: `horizon_specific_alpha_v1_20260925_131549_730952_utc/`.

For **each root**, append the table's component and file suffix to obtain the complete source paths. The two copies of every listed file are byte-identical; all ten hashes were recomputed before use and independently checked after the formal run. Each component prediction grid has 12,400 rows (E001–E100 × U0=124), aligned dates/sectors/names and identical same-horizon evaluation labels.

| Component | Source file under both roots | SHA-256 |
|---|---|---|
| C0_H10 | `C0_H10/predictions.csv` | `3922081c9ca15bf49102d38c0098b33b198e464e55fa978cf11ffe42ef580781` |
| C0_H10 | `C0_H10/aggregate_metrics.json` | `36568fb873f97135fa427989874eb53c5feda23615ebd78fff6ce6130ab3f07e` |
| C0_H40 | `C0_H40/predictions.csv` | `737ba02766c2afea9848c432e9aa13910dd8119cb02f317846be5e19e0d5960a` |
| C0_H40 | `C0_H40/aggregate_metrics.json` | `8e9dc07117f5f83b2c4556ee1bb5f9b1ee5315415c1f7a9228447e2cc1e23bbc` |
| C0_H120 | `C0_H120/predictions.csv` | `e41df4f8214520a56eb8f5e585eda5fc641f70cb2bda6d6cc76ac24cb721c5d6` |
| C0_H120 | `C0_H120/aggregate_metrics.json` | `ccc6dcb2b9e995cc44c935c803882e0636a088bf2328ef958d9921d7d872a91b` |
| H10_C | `H10_C/predictions.csv` | `e50c405b8178f4b1afa2ec2e8bca1e8e1b68e0e9afc57f2f700d07c22120ab59` |
| H10_C | `H10_C/aggregate_metrics.json` | `1777f47b498dd5f622c1a0aa2338f95ac94f66c7e294bb8afd12a1e59761e010` |
| H40_S | `H40_S/predictions.csv` | `dd9b8277bd02bbf3b510e8d6cad297a6982a001255800e33dd697183c19aae07` |
| H40_S | `H40_S/aggregate_metrics.json` | `09307319def853cb58d9013ee6164a22fbcbc0e1c2fdef44d6c73137f156ca9f` |

## 5. ENVIRONMENT

Existing `quant-research` container, image `sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5`. **ENVIRONMENT_CHANGED=false**. No image rebuild, dependency installation, Hikyuu change, or source-data download.

## 6. SAMPLE

Development E001–E100 only, 2025-04-02 through 2025-08-26, fixed U0 of 124 Shenwan Level-2 sector indexes; sector snapshot `872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`, split policy hash `3b6b2d754211169039439c8b377fd9eb26d5cb5db0f80d62cffc1d19c81a7038`. Validation and Final OOS remain SEALED. This is fixed-classification sector-index research (`strictPit=false`, `executable=false`, `tradable=false`).

## 7. FORMAL FUSION SEMANTICS

The runner calls the existing `CrossSectionalRidgeModel.fuse_periods` implementation, not a replacement fusion. For each date and horizon, intersect the three sector-code sets; use `m=max(max(abs(prediction)),1)`, scale by `m`, then cross-sectional z-score with population standard deviation (`ddof=0`); a horizon with `std <= 1e-12/m` contributes zeros. Fuse `(0.25*z10 + 0.50*z40 + 0.25*z120)/(0.25+0.50+0.25)`. Sort fused score descending, break exact ties by sector code ascending, Top5 = first five. It is **not** a raw linear combination of unstandardized prediction scores. Evaluation uses raw horizon scores for IC/RankIC and fused Top5 for forward-return/spread metrics.

## 8. CANDIDATE DEFINITIONS

| Scheme | H10 | H40 | H120 | Fixed weights |
|---|---|---|---|---|
| F0_CONTROL | C0_H10 | C0_H40 | C0_H120 | 0.25/0.50/0.25 |
| F1_H10_REPLACEMENT | H10_C `[d10,p5,align,vc,dd20]` | C0_H40 | C0_H120 | 0.25/0.50/0.25 |
| F2_H10_H40_REPLACEMENT | H10_C | H40_S `[vc]` | C0_H120 | 0.25/0.50/0.25 |

C0 components use the frozen 19-factor model. All three schemes were executed unconditionally after F0 passed. No model retraining occurred.

## 9. WHY NO H40-ONLY

The frozen budget has only two new hypotheses. F2−F1 isolates H40_S's incremental effect with H10_C already fixed; a fourth H40-only candidate was not preregistered or run.

## 10. WHY NO H120 REPLACEMENT

The source Horizon-Specific audit did not advance H120_C or H120_S on its relative gate. Both F1 and F2 therefore preserve C0_H120; high H120_C RankIC cannot retroactively waive its spread deterioration.

## 11. F0 REPRODUCTION

**PASS before F1/F2 calculation or artifact writing.** Against byte-hash-verified D2/C0 historical reference: 100 dates × 124 sectors; fused-score maximum absolute difference 0; fused-rank mismatches 0; Top5 mismatches 0; daily metric, aggregate mean, and weighted-primary maximum absolute differences 0 (tolerance `1e-12`). A second read-only verifier reloaded the written F0/D2 CSVs and found fused-score difference 0 and exact rank/Top5 identity.

## 12. FORMAL RESULT TABLE

Values are descriptive Development estimates, not a validation result. Weighted metrics use the frozen 0.25/0.50/0.25 horizon weights; spread is the fused Top5 mean forward return minus U0 mean forward return.

| Scheme | Weighted RankIC | Weighted Spread | RankIC10 / 40 / 120 | Spread10 / 40 / 120 | Level1 | vs F0 | vs F1 | Temporal | Red flag | Final status |
|---|---:|---:|---|---|---|---|---|---|---|---|
| F0_CONTROL | 0.08810651455546813 | 0.037216498377093545 | 0.025446168 / 0.049692400 / 0.227595090 | 0.005297457 / 0.012787646 / 0.117993243 | N/A | N/A | N/A | N/A | N/A | CONTROL_NOT_A_CANDIDATE |
| F1_H10_REPLACEMENT | 0.09349328088119589 | 0.044456330026128345 | 0.046993234 / 0.049692400 / 0.227595090 | 0.007442231 / 0.019832662 / 0.130717766 | PASS | PASS | N/A | PASS | none | FUSION_ADVANCED_FOR_FURTHER_REVIEW |
| F2_H10_H40_REPLACEMENT | 0.09486741148701808 | 0.015939832916397074 | 0.046993234 / 0.052440661 / 0.227595090 | 0.008362188 / 0.014117614 / 0.027161916 | PASS | FAIL | FAIL | PASS | none | FUSION_NOT_ADVANCED |

F2's frozen gate substatus is `F2_VS_F0_GATE_FAIL`; its vs-F1 incremental check also fails. F0 is a control, not a candidate for advancement.

## 13. F1 VS F0

Exact primary deltas: Weighted RankIC `+0.005386766325727765`; Weighted Spread `+0.0072398316490348`. Both improve, so the strict Pareto-relative gate passes.

## 14. F2 VS F0

Exact primary deltas: Weighted RankIC `+0.006760896931549951`; Weighted Spread `-0.02127666546069647`. The spread deterioration fails the frozen relative gate despite the RankIC increase.

## 15. F2 VS F1

Exact incremental deltas: Weighted RankIC `+0.0013741306058221853`; Weighted Spread `-0.02851649710973127`. The H40 replacement's incremental relative gate fails; it is not supported by this fixed-fusion Development comparison.

## 16. PER-HORIZON RESULTS

The table in §12 gives all three mean RankIC and fused-Top5 spread values per scheme. F1 changes H10 RankIC from 0.025446168 to 0.046993234 while leaving H40/H120 RankIC unchanged. F2 changes H40 RankIC from 0.049692400 to 0.052440661 but materially lowers the H120 evaluation spread through a changed fused Top5, despite keeping the H120 component itself unchanged. These are descriptive, correlated within the same Development sample.

## 17. B1–B4 STABILITY

Each block is 25 fixed Development ordinals. Cells show weighted RankIC / weighted spread.

| Scheme | B1 E001–025 | B2 E026–050 | B3 E051–075 | B4 E076–100 |
|---|---|---|---|---|
| F0 | 0.2329834146 / 0.1161073790 | 0.1874432101 / 0.0933905356 | 0.0007463729 / −0.0170816217 | −0.0687469394 / −0.0435502994 |
| F1 | 0.2262189142 / 0.1226174602 | 0.1868847836 / 0.0889924443 | 0.0044237293 / −0.0165498502 | −0.0435543037 / −0.0172347341 |
| F2 | 0.1252396538 / 0.0253667198 | 0.0810014162 / 0.0415976408 | 0.0886911094 / −0.0119299543 | 0.0845374666 / 0.0087249254 |

F1 has three positive weighted-RankIC blocks and one below −0.02, satisfying the frozen temporal gate but with a late weak block. F2 has four positive blocks and also passes temporal; temporal passage does not override relative-gate failure.

## 18. HORIZON RED FLAGS

The frozen red-flag threshold is mean horizon RankIC `< -0.02`. Neither F1 nor F2 triggers it; all three horizon RankIC means are positive. This does not remove the separate H40 evidence-quality caveat.

## 19. MINIMAL REPLACEMENT PREFERENCE

The formal near-tie preference flag is **false**: it only activates when *both* F1 and F2 pass all gates and both primary deltas between them are `<0.01`. F2 does not advance and its spread decrement is approximately 0.02852. `H10_REPLACEMENT_ONLY_SUPPORTED` follows from F1's advancement and F2's failure, not from a near-tie override.

## 20. H40 WEAK-EVIDENCE WARNING

`H40_NO_STRONG_STABILITY_EVIDENCE=true` remains in both run metadata and summary. The source H40_S selection had weak directional-stability evidence; F2's failure does not license retrospective component selection or a revised H40 hypothesis.

## 21. NEUTRALITY CAVEAT

`NEUTRALITY_INDUCED_LOW_FLIP_CAVEAT=true` remains. Low hard-flip counts for the prior H40_S `[vc]` source were tied to NEUTRAL training direction, not proven directional alpha stability.

## 22. DEVELOPMENT REUSE WARNING

`DEVELOPMENT_REUSE_WARNING=true`. This is **POST-AUDIT DEVELOPMENT HYPOTHESIS REFINEMENT** on E001–E100, already used in earlier research. All observed improvements are selection-sensitive Development descriptions, not independent confirmation.

## 23. PRIMARY RESEARCH DIAGNOSIS

Within the frozen fixed-fusion comparison, replacing only H10 preserves and modestly improves both primary metrics. Adding H40_S increases weighted RankIC slightly but sharply degrades weighted spread; it does not clear either F2 relative benchmark. No profits, trading signals, or execution performance are inferred from these sector-index prediction metrics.

## 24. NEXT_RESEARCH_GATE

`H10_REPLACEMENT_ONLY_SUPPORTED` — support **for further human review of Development evidence only**. It is not permission to open Validation, Final OOS, a new search, or a trading workflow.

## 25. SOURCE INTEGRITY

**PASS**: five first/rerun component prediction and aggregate files each match their frozen SHA-256; same-horizon labels and the 100×124 aligned grid match. Full paths and hashes are in §4 and `component_source_integrity.json`.

## 26. FUSION IDENTITY

**PASS**: direct independent z-score arithmetic on F0/F1/F2 at E001/E025/E050/E075/E100, all 124 sectors each (1,860 sector comparisons), max fused-score absolute difference 0 at `1e-12` tolerance; F0 historical fused-score comparison covers all 12,400 sector-date rows. All long/wide fused-score values also agree (max difference 0).

## 27. TOP5 IDENTITY

**PASS**: exact sector IDs and order for 15 independent scheme/date samples, exact F0 historical Top5 over all dates, and all 100-date long/wide Top5 flags agree for each scheme.

## 28. METRIC INTEGRITY

**PASS**: independent recomputation of 15 daily IC/RankIC/Top5/universe/spread metrics per date and scheme, all 100 dates, followed by mean/median/population std/min/max, primary weighted metrics and fixed-block aggregates. First and rerun both pass; maximum daily absolute difference `2.220446049250313e-16`, maximum aggregate difference `2.7755575615628914e-17` (`1e-12` tolerance). No null metric was replaced with zero.

## 29. ADVANCEMENT LOGIC INTEGRITY

**PASS**: the separate verifier reconstructed Level1, both relative comparisons, horizon red flags, B1–B4 temporal rule, minimal-replacement preference, final statuses and `NEXT_RESEARCH_GATE` without trusting runner status fields; all match.

## 30. DETERMINISM

First and immediate rerun use the same clean implementation commit, image and source. Both independent verifications pass. Each run has **21 non-metadata files**; independently recomputed SHA-256 for every corresponding file has **0 mismatches**. Metadata differs intentionally in `runId` and `determinismRepeatOf`; no non-metadata file differs.

## 31. PRE-RUN TESTS

Baseline before implementation: targeted **24 passed**; full offline **623 passed, 2 skipped, 17 deselected, 0 failed**. Final implementation before clean commit: targeted **32 passed**; full offline **631 passed, 2 skipped, 17 deselected, 0 failed**. Two existing warnings concern a legacy target without symbol and an unmapped ETF in separate tests.

## 32. POST-RUN TESTS

Targeted `tests/test_horizon_component_replacement_v1.py` plus runner tests: **32 passed**. Full offline suite: **631 passed, 2 skipped, 17 deselected, 0 failed**, same two pre-existing warnings. No test deleted or skipped to obtain this result.

## 33. HISTORICAL IMMUTABILITY

**PASS**: Git diff from the preregistration handoff to execution commit contains only the three new runner/verifier/test files. Earlier Iteration-1, Factor Audit V1, Factor Set V2, Alpha Stability, Horizon-Specific prereg/formal, and Component Replacement prereg files were not edited. D2 reference and Horizon-Specific source artifacts still match their frozen content hashes. The ignored historical report files were read, never overwritten.

## 34. PROTOCOL IMMUTABILITY

**PASS**: frozen protocol, config, source manifest, selection trace, module constants and preregistration report are unchanged from `95e54ee6461b315b51f5ca7cc17cd985caa96a1d`; the protocol hash was re-derived at each gate. No result-driven semantic repair or weight change occurred.

## 35. ARTIFACTS

- First run: `reports/research/shenwan_sector_index/horizon_component_replacement_v1_20260925_161027_956244_utc/`.
- Rerun: `reports/research/shenwan_sector_index/horizon_component_replacement_v1_20260925_161123_854691_utc/`.
- In **each** run root: `metadata.json`, `candidate_summary.json`, `aggregate_metrics.json`, `per_date_metrics.csv`, `per_date_predictions.csv`, `block_stability.csv`, `component_source_integrity.json`, `fusion_integrity.json`, `advancement_decision.json`, `integrity.json`.
- Under **each** of `F0_CONTROL/`, `F1_H10_REPLACEMENT/`, `F2_H10_H40_REPLACEMENT/`: `predictions.csv`, `per_date_predictions.csv`, `per_date_metrics.csv`, `aggregate_metrics.json`.

These 22 files per run (21 excluding metadata) are intentionally ignored by Git under `/reports/research/`; the first-run metadata records the SHA-256 of every non-metadata file.

## 36. SELECTION BIAS

**POST-AUDIT DEVELOPMENT HYPOTHESIS REFINEMENT; DEVELOPMENT_REUSE_WARNING=true; NOT INDEPENDENT VALIDATION; NOT OOS.** No p-value, confidence interval, independent alpha claim or strategy return is reported. F1's Development advancement is only a preregistered research gate.

## 37. RESEARCH COMPLIANCE

Development only; Validation and Final OOS untouched and SEALED. No fusion-weight or parameter search, component adaptation, H120 replacement, new factor, sign inversion, model replacement, Docker/dependency/Hikyuu change, dashboard/API work, Portfolio/ETF/QMT work, strategy backtest, simulation or trade.

## 38. ENVIRONMENT_CHANGED

`false`; the frozen image identity matched before the first run and was reused unchanged for rerun and tests.

## 39. COMMITS

Implementation: `fb207b8b868a3aaceed568d4a8e1b62340371bff`. Result: the commit adding this report (`research: run horizon component replacement v1`); full SHA in subsequent handoff. Handoff: separate pure-documentation commit, if created; final response gives the full SHA. Neither Git history nor frozen preregistration was amended.

## 40. NEXT AUTHORIZED ACTION

**HUMAN REVIEW REQUIRED BEFORE NEXT RESEARCH DESIGN.** A separate decision and preregistration would be needed for any future work. No Validation or Final OOS access is authorized by this result.

## 41. FINAL STATUS

**HORIZON COMPONENT REPLACEMENT V1 FORMAL DEVELOPMENT RUN COMPLETE WITH NON-BLOCKING WARNINGS.** Stop after the report, result commit and integrity-checked handoff.
