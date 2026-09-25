# Handoff — Horizon Component Replacement V1 preregistration (for the next Codex)

Companion machine file:
`docs/research/handoff_horizon_component_replacement_v1_prereg.json`.
Narrative report:
`docs/research/shenwan_horizon_component_replacement_v1_preregistration_report.md`.

## A. CURRENT GIT STATE

- Branch: `experiment/sw-sector-index-research-baseline`
- HEAD at handoff authoring: the preregistration commit in §B (this handoff
  file is added by the immediately following docs commit — re-read
  `git log --oneline -5` to confirm real HEAD before any work)
- Working tree: clean after both commits; `/reports/research/` untracked
  by convention

## B. PREREGISTRATION COMMIT

- Full SHA: `95e54ee6461b315b51f5ca7cc17cd985caa96a1d`
  (`research: preregister horizon component replacement v1` — protocol,
  selection trace, machine config, source manifest, protocol module,
  targeted tests, preregistration report)
- Handoff commit: the commit adding this file
  (`docs: record horizon component replacement v1 preregistration handoff`)

## C. PROTOCOL

- Path: `docs/research/shenwan_horizon_component_replacement_v1.md`
- SHA-256 (canonical protocol identity):
  `4267d73f38fc8353002459b24640148cc49c4e5777b364eb14ca84404aef9fa7`
- Verification entry point:
  `research.horizon_component_replacement_v1_protocol.verify_protocol()`

## D. CONFIG

`research/configs/horizon_component_replacement_v1.json` (canonical hash
`4c2f18815e47f9352a34f4f6bba222a260cbfff73cf6c49fc3e55438dc78adf6`).

## E. SOURCE MANIFEST

`research/configs/horizon_component_replacement_v1_sources.json` (canonical
hash `35af45f03a8c04490c5bb5ce009476fac266b0ae0027b2b9db9d50d9d6786c3f`)
— five component sources with recomputed SHA-256s, first/rerun identity,
and the descriptive scale audit.

## F. SOURCE RESULT

`de8b77a8da3aeac99fa5ac1fd52d6431cedf2d62` (Horizon-Specific Alpha
Hypothesis V1 formal run; components C0_H10/H40/H120, H10_C, H40_S).

## G. SOURCE HANDOFF

`98dfe5c9c256fe31339a2c3ca63ea1753180a7cc` (audited: handoff files only).

## H. EXACT CANDIDATES

- `F0_CONTROL` = C0_H10 + C0_H40 + C0_H120 (control; equals original D2 fused)
- `F1_H10_REPLACEMENT` = H10_C `[d10,p5,align,vc,dd20]` + C0_H40 + C0_H120
- `F2_H10_H40_REPLACEMENT` = H10_C + H40_S `[vc]` + C0_H120
- No H40-only; no H120 replacement (H120_C/S formally NOT_ADVANCED)

## I. FUSION WEIGHTS

h10 **0.25** / h40 **0.50** / h120 **0.25** — frozen; no weight search.
Exact fusion: **per-date cross-sectional z-score of each component, then
weighted average** (`model.py::fuse_periods`), descending rank with
sector-code tie-break, Top5 from the fused ranking. The raw-linear-combination
shorthand is superseded — see warnings.

## J. ADVANCEMENT RULES

Level1 (WR>0 AND WS>0) → F1-vs-F0 Pareto → F2-vs-F0 Pareto → F2-vs-F1
Pareto (F2 needs all three) → horizon red flag (any mean RankIC_h < −0.02
blocks) → temporal gate (≥3/4 block Weighted RankIC>0, ≤1/4 < −0.02).
Minimal-replacement preference: both pass + both |Δ|<0.01 → prefer F1.
Labels: CONTROL_NOT_A_CANDIDATE / FUSION_ADVANCED_FOR_FURTHER_REVIEW /
FUSION_NOT_ADVANCED (+ gate substatuses).

## K. WARNINGS

1. Fusion semantics finding: formal fusion z-scores components per date
   (code authoritative over the raw-shorthand prompt formula).
2. Component scales differ up to ~40× but fusion is affine-invariant —
   `RAW_COMPONENT_SCALE_DEPENDENCE_WARNING` does NOT apply (justified).
3. `H40_NO_STRONG_STABILITY_EVIDENCE=true` — immutable.
4. `NEUTRALITY_INDUCED_LOW_FLIP_CAVEAT=true` — immutable (vc/p5 selected
   on neutral training direction).
5. `DEVELOPMENT_REUSE_WARNING=true` — POST-AUDIT DEVELOPMENT RESEARCH,
   not independent validation, not OOS.
6. `reports/research/` untracked; provenance = hashes + commits.
7. CSV recomputation of tie-sensitive rank metrics needs
   `float_precision="round_trip"`.

## L. TEST STATUS

- Targeted: 24 passed / 0 failed / 0 skipped
- Full offline suite: 623 passed / 0 failed / 2 skipped / 17 deselected

## M. RESULT LEAK STATUS

**NO FORMAL COMPONENT-REPLACEMENT RESULTS GENERATED.** Live scan of
`reports/research/shenwan_sector_index/` clean for
`horizon_component_replacement_v1_*` / `component_replacement_v1_*` /
`fusion_replacement_v1_*`. Runtime gate:
`protocol.guard_no_formal_results(reports_root)`.

## N. ENVIRONMENT

Image `sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5`
(`quant-research:py3.12`); ENVIRONMENT_CHANGED = **false**; only
`docker compose exec quant-research` used.

## O. NEXT SAFE ENTRY POINT (read-only verification first)

```bash
git -C D:\quant-trading status
git -C D:\quant-trading branch --show-current
git -C D:\quant-trading rev-parse HEAD
git -C D:\quant-trading log --oneline -6
docker compose exec quant-research python -c "from research.horizon_component_replacement_v1_protocol import verify_protocol, FROZEN_PROTOCOL_HASH; verify_protocol(); print(FROZEN_PROTOCOL_HASH)"
docker compose exec quant-research pytest tests/test_horizon_component_replacement_v1.py -q
docker compose exec quant-research python -c "from pathlib import Path; from research.horizon_component_replacement_v1_protocol import guard_no_formal_results; print(guard_no_formal_results(Path('reports/research/shenwan_sector_index')))"
```

Only after these confirm the frozen state should the next task begin, under
a fresh human instruction.

## P. DO NOT ASSUME

- current HEAD / worktree cleanliness (re-read git)
- Docker container running state and image identity
- exact latest test counts (run the suites yourself)
- source artifact existence or hashes (untracked; re-verify via the
  manifest's SHA-256s)
- that any authorization exists for formal F0/F1/F2 runs, weight research,
  parameter research, horizon deletion, Validation or OOS — none exists
- that the numbers here still match the artifacts (re-verify from
  `candidate_summary.json` of the source run)
