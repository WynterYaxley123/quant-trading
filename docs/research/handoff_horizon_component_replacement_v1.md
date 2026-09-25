# Handoff — Horizon Component Replacement V1

Companion machine-readable package: `docs/research/handoff_horizon_component_replacement_v1.json`. Full formal report: `docs/research/shenwan_horizon_component_replacement_v1_run_report.md`. This is **Development-only sector-index prediction research**, not a strategy backtest or independent validation.

## A. CURRENT GIT STATE

- Branch: `experiment/sw-sector-index-research-baseline`.
- HEAD at handoff authoring: result commit `91b89a97a9a2b54e133d2979c695d7c3da22626e`. The handoff itself is added by the following docs-only commit; re-read Git to learn the final HEAD. A file cannot embed its own commit SHA.
- Working tree: clean after result commit; expected clean again after handoff commit. `reports/research/` is ignored by convention, not missing or fabricated.

## B. COMMITS

- Preregistration: `95e54ee6461b315b51f5ca7cc17cd985caa96a1d`.
- Preregistration handoff: `d28e42bf7bb09fcc5b9faa19ab3ff0a96429c1cd`.
- Execution implementation: `fb207b8b868a3aaceed568d4a8e1b62340371bff` (`research: implement horizon component replacement v1 runner`).
- Result report: `91b89a97a9a2b54e133d2979c695d7c3da22626e` (`research: run horizon component replacement v1`).
- Handoff: the commit containing this file (`docs: record horizon component replacement v1 handoff`); full SHA must be read from Git. No maintenance commit was needed.

## C. PROTOCOL

`docs/research/shenwan_horizon_component_replacement_v1.md`; frozen hash `4267d73f38fc8353002459b24640148cc49c4e5777b364eb14ca84404aef9fa7`. Re-derive with `research.horizon_component_replacement_v1_protocol.verify_protocol()` before any future action. Protocol, selection trace and frozen constants are unchanged from preregistration.

## D. CONFIG

`research/configs/horizon_component_replacement_v1.json`, hash `4c2f18815e47f9352a34f4f6bba222a260cbfff73cf6c49fc3e55438dc78adf6`. Exactly F0/F1/F2; fixed fusion 0.25/0.50/0.25. No extra candidate, retuning, H120 replacement, or retraining.

## E. SOURCE MANIFEST

`research/configs/horizon_component_replacement_v1_sources.json`, hash `35af45f03a8c04490c5bb5ce009476fac266b0ae0027b2b9db9d50d9d6786c3f`. Source result commit `de8b77a8da3aeac99fa5ac1fd52d6431cedf2d62`; source handoff `98dfe5c9c256fe31339a2c3ca63ea1753180a7cc`. All complete source paths and per-file hashes are in formal report §4 and first-run `component_source_integrity.json`.

## F. SOURCE ARTIFACT HASH STATUS

**PASS**: C0_H10, C0_H40, C0_H120, H10_C and H40_S prediction/aggregate pairs (10 files) each match frozen SHA-256 in both source first/rerun roots, with 10/10 byte-identical pairs. Each prediction grid is 100 × 124 and same-horizon labels align. No source artifact was changed.

## G. F0/F1/F2 EXACT DEFINITIONS

| Scheme | H10 | H40 | H120 |
|---|---|---|---|
| F0_CONTROL | C0_H10 (19 factors) | C0_H40 (19 factors) | C0_H120 (19 factors) |
| F1_H10_REPLACEMENT | H10_C `[d10,p5,align,vc,dd20]` | C0_H40 | C0_H120 |
| F2_H10_H40_REPLACEMENT | H10_C | H40_S `[vc]` | C0_H120 |

Existing `CrossSectionalRidgeModel.fuse_periods`: per-date/per-horizon cross-sectional z-score (population std, small-variance zero) over common U0, then fixed weighted average; fused score descending, exact ties by sector code ascending, Top5 first five. All schemes run after F0 reproduction passed; no raw-score linear combination or weight search.

## H. FORMAL RESULTS

E001–E100, 2025-04-02 to 2025-08-26, fixed U0=124, Validation/Final OOS SEALED. Descriptive Development primary metrics:

| Scheme | Weighted RankIC | Weighted Spread | Status |
|---|---:|---:|---|
| F0_CONTROL | 0.08810651455546813 | 0.037216498377093545 | CONTROL_NOT_A_CANDIDATE |
| F1_H10_REPLACEMENT | 0.09349328088119589 | 0.044456330026128345 | FUSION_ADVANCED_FOR_FURTHER_REVIEW |
| F2_H10_H40_REPLACEMENT | 0.09486741148701808 | 0.015939832916397074 | FUSION_NOT_ADVANCED |

F1−F0: RankIC `+0.005386766325727765`, spread `+0.0072398316490348`. F2−F0: RankIC `+0.006760896931549951`, spread `−0.02127666546069647`. F2−F1: RankIC `+0.0013741306058221853`, spread `−0.02851649710973127`. The full per-horizon and B1–B4 tables are in the formal report, not inferred from trading returns.

## I. ADVANCEMENT STATUS

F0 is a control. F1 passes Level1, vs-F0, temporal and horizon-red-flag gates. F2 passes Level1 and temporal with no horizon red flag, but fails both vs-F0 and vs-F1 spread-Pareto comparisons; frozen substatus `F2_VS_F0_GATE_FAIL`. Minimal near-tie preference flag `false` because both candidates did not advance.

## J. NEXT_RESEARCH_GATE

`H10_REPLACEMENT_ONLY_SUPPORTED` — further **human review of Development evidence only**. It does not authorize Validation, OOS, search, backtest or execution.

## K. FIRST RUN PATH

`reports/research/shenwan_sector_index/horizon_component_replacement_v1_20260925_161027_956244_utc/` (ignored by Git). Metadata includes all non-metadata artifact hashes and implementation commit.

## L. RERUN PATH

`reports/research/shenwan_sector_index/horizon_component_replacement_v1_20260925_161123_854691_utc/` (ignored by Git). `determinismRepeatOf` names the first run.

## M. DETERMINISM

**PASS**: 21 non-metadata files in each run, 21/21 byte-identical by independently recomputed SHA-256, zero mismatches. Metadata differs only by run identity/repeat reference. Both runs independently verified.

## N. METRIC INTEGRITY

**PASS**: independent read-only recalculation of all 15 daily metrics × 100 dates × 3 schemes, aggregate statistics, weighted primaries and fixed blocks. Max daily absolute difference `2.220446049250313e-16`, aggregate `2.7755575615628914e-17`, both below `1e-12`; full long/wide fused-score difference 0. Advancement decisions and next gate independently match.

## O. F0 REPRODUCTION

**PASS before F1/F2 and before artifact writing**: historical D2 fused-score max difference 0 over 100 × 124, zero rank/Top5 mismatches, zero daily/aggregate/weighted-primary difference. A second read-only artifact-level verifier also passed.

## P. POST-RUN TESTS

Targeted: **32 passed, 0 failed**. Full offline: **631 passed, 2 skipped, 17 deselected, 0 failed**. Two pre-existing warnings concern legacy target symbol and unmapped ETF test fixtures. Pre-run final implementation had the same counts.

## Q. ENVIRONMENT

Existing Docker image `sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5`; `ENVIRONMENT_CHANGED=false`. No Docker rebuild, dependency install, Hikyuu modification or source-data download.

## R. SEALED PHASES

Validation SEALED; Final OOS SEALED. Fixed-classification sector-index research, `strictPit=false`, `executable=false`, `tradable=false`, `INDEPENDENT_VALIDATION=false`, `OOS=false`. No simulated/real trades, Portfolio/ETF/QMT, or strategy return claim.

## S. WARNINGS

- `H40_NO_STRONG_STABILITY_EVIDENCE=true` remains, irrespective of F2's outcome.
- `NEUTRALITY_INDUCED_LOW_FLIP_CAVEAT=true` for the H40_S source.
- `DEVELOPMENT_REUSE_WARNING=true`: POST-AUDIT DEVELOPMENT HYPOTHESIS REFINEMENT, not independent Validation/OOS.
- Ignored `/reports/research/` files require local existence and hash recheck, not an assumption from Git alone.
- CSVs must be read with round-trip float precision for tie-sensitive fusion/rank verification.
- Immutable committed handoff cannot contain its own future commit SHA; use Git for actual final HEAD.

## T. DO NOT ASSUME / NEXT SAFE ENTRY POINT

Before any future design, re-read `AGENTS.md`, the frozen protocol/config/manifest and formal report; check branch/HEAD/working tree, Docker image/state, first/rerun artifact existence and hashes, protocol hash, and current offline tests. Read-only entry points: `git status --short`, `git rev-parse HEAD`, `git log --oneline -5`, Docker inspect of `quant-research`, `python -m research.horizon_component_replacement_v1_verify <first-run>` and the same for rerun **inside the existing container**. Do not open Validation or Final OOS. **HUMAN REVIEW REQUIRED BEFORE NEXT RESEARCH DESIGN.**
