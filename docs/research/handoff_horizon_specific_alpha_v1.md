# Handoff — Horizon-Specific Alpha Hypothesis V1 (for the next Codex)

Concise continuation package. Companion machine-readable file:
`docs/research/handoff_horizon_specific_alpha_v1.json`. Full narrative:
`docs/research/shenwan_horizon_specific_alpha_hypothesis_v1_run_report.md`.

## A. CURRENT GIT STATE

- Branch: `experiment/sw-sector-index-research-baseline`
- HEAD at handoff authoring: the result commit in §B (this handoff file is
  added by the immediately following docs commit — re-read
  `git log --oneline -5` to confirm the real HEAD before any work)
- Working tree: clean after both commits; `/reports/research/` is
  untracked by convention (`.gitignore`)

## B. COMMITS

- Preregistration commit: `4d0ee982a0cd4ff1efe76c9fee4c2de807643ac2`
  (`research: preregister horizon specific alpha hypothesis v1`)
- Result commit: `de8b77a8da3aeac99fa5ac1fd52d6431cedf2d62` (`research: run horizon specific
  alpha hypothesis v1` — runner + runner tests + run report)
- Handoff commit: the commit adding this file
  (`docs: record horizon specific alpha v1 handoff`)
- No other commits; no maintenance commits were needed this round.

## C. PROTOCOL

- Path: `docs/research/shenwan_horizon_specific_alpha_hypothesis_v1.md`
- Protocol hash: `d598efd34fe2a6c03832e3faaeadd738cc63a604e5da4c8f1a3740c33e69b8d4`
- Machine config: `research/configs/horizon_specific_alpha_hypothesis_v1.json`
  (hash `ddaaa1c761bf1ab37d86bd5228ad306d54af66575fbe2c06ed4df576e01446ec`)
- Selection trace:
  `docs/research/shenwan_horizon_specific_alpha_hypothesis_v1_selection_trace.md`
- Verification entry point:
  `research.horizon_specific_alpha_hypothesis_v1_protocol.verify_protocol()`

## D. FORMAL ARTIFACTS

- First run: `reports/research/shenwan_sector_index/horizon_specific_alpha_v1_20260925_130230_272283_utc/`
- Determinism rerun: `reports/research/shenwan_sector_index/horizon_specific_alpha_v1_20260925_131549_730952_utc/`
- 57 non-metadata artifacts per run (per-scheme folders: predictions,
  per_date_metrics, aggregate_metrics, training_diagnostics,
  data_quality_diagnostics, transformation_diagnostics; root:
  candidate_summary.json, block_stability.csv, integrity.json,
  metadata.json)

## E. EXACT CANDIDATES

- H10_S `[p5]` · H10_C `[d10, p5, align, vc, dd20]`
- H40_S `[vc]` · H40_C `[d120, p60, align, vc, rev5, dd20]`
- H120_S `[vc]` · H120_C `[d5, p20, vc, rev10, dd60, rsi]`
- Controls: C0_H10 / C0_H40 / C0_H120 (19 frozen factors each, same-horizon
  only). V2_C-style extras: none.

## F. RESULT TABLE (horizon-local metrics; no fusion)

| scheme | meanIC | meanRankIC | medianRankIC | meanSpread | medianSpread | validDates |
|---|---|---|---|---|---|---|
| C0_H10 | -0.017436 | +0.025446 | -0.002143 | -0.000047 | -0.001602 | 100 |
| H10_S | +0.002697 | +0.004797 | -0.010334 | +0.000133 | +0.000086 | 100 |
| H10_C | +0.035714 | +0.046993 | +0.033750 | +0.002836 | -0.000564 | 100 |
| C0_H40 | +0.021682 | +0.049692 | +0.057410 | +0.003865 | +0.005963 | 100 |
| H40_S | +0.055242 | +0.052441 | +0.059868 | +0.007790 | -0.001454 | 100 |
| H40_C | -0.016143 | +0.005299 | +0.026581 | -0.012996 | -0.024324 | 100 |
| C0_H120 | +0.239157 | +0.227595 | +0.246279 | +0.161804 | +0.088274 | 100 |
| H120_S | -0.015065 | -0.000130 | +0.020120 | -0.032598 | -0.048934 | 100 |
| H120_C | +0.263193 | +0.242679 | +0.260261 | +0.128892 | +0.139604 | 100 |

## G. ADVANCEMENT STATUS

- **H10_C — HORIZON_ADVANCED_FOR_FURTHER_REVIEW** (L1/L2/temporal all pass;
  ΔvsC0_H10 RankIC +0.0215, Spread +0.0029)
- **H40_S — HORIZON_ADVANCED_FOR_FURTHER_REVIEW** (L1/L2/temporal all pass;
  ΔvsC0_H40 RankIC +0.0027, Spread +0.0039; warnings retained)
- H10_S — NOT_ADVANCED (Level 2 fail) · H40_C — NOT_ADVANCED (L1/L2/temporal
  fail) · H120_S — NOT_ADVANCED (L1 fail) · H120_C — NOT_ADVANCED (Level 2
  spread-Pareto fail despite ΔRankIC +0.015)
- Simplicity preference: NOT_TRIGGERED (no horizon with both S and C advanced)

## H. NEXT_RESEARCH_GATE

**MIXED_HORIZON_EVIDENCE** — two candidates passed all frozen gates, four
failed with clearly different mechanisms. Human review required before any
next research design. Validation stays SEALED.

## I. TEST STATUS

- Targeted: 29 passed / 0 failed / 0 skipped
  (14 prereg + 15 runner tests)
- Full offline suite: 599 passed / 0 failed / 2 skipped / 17 deselected

## J. INTEGRITY STATUS

| gate | status | key figures |
|---|---|---|
| factor identity | PASS | 570 samples, max 1.60e-14 |
| target identity | PASS | 90 samples, 0.00e+00 / 1.11e-16 |
| training-window identity | PASS | 405 field checks, 15/15 combos |
| C0 reproduction | PASS | predictions bit-exact vs D2; max 1.01e-16 |
| Top5 identity | PASS | 54 exact checks |
| metric recompute | PASS | max 2.22e-16 |
| advancement logic | PASS | 6/6 candidates agree |
| determinism | PASS | 57/57 byte-identical |

## K. ENVIRONMENT

- Image: `sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5`
  (`quant-research:py3.12`)
- ENVIRONMENT_CHANGED = **false**; all execution via
  `docker compose exec quant-research`

## L. KNOWN WARNINGS

1. Neutrality-induced low flip caveat: H40_S/H120_S (`vc`) and H10_S (`p5`)
   were selected on zero hard flips whose training direction was NEUTRAL
   (vc@40 and p5@10: 100/100 dates; vc@120: 99/100) —
   NEUTRALITY_INDUCED_LOW_FLIP_RATE, not proven DIRECTIONAL_STABILITY.
2. Development reuse: five studies inspected the same E001-E100 sample
   (`DEVELOPMENT_REUSE_WARNING=true`).
3. H40 weak-evidence warning `NO_STRONG_STABILITY_EVIDENCE` must stay even
   though H40_S advanced.
4. Two pre-artifact implementation bugs were found and fixed during the
   first run attempt (training-window gate horizon assumption; D2 aggregate
   key `valid_dates` vs `validDates`) — see report §35 warning 1. No formal
   artifact was affected.
5. CSV read precision: recompute tie-sensitive rank metrics from CSVs with
   `float_precision="round_trip"`; default parsing perturbs ~1e-16 and
   breaks ties (report §28).
6. `/reports/research/` artifacts are untracked; provenance = protocol
   hash + commits + content hashes.

## M. DO NOT ASSUME (re-read these yourself)

- current HEAD and worktree cleanliness (`git status`, `git rev-parse HEAD`)
- Docker container running state and image identity
- exact latest test counts (run the suites yourself)
- artifact directory existence and content hashes (they are untracked)
- that the numbers in this handoff still match the artifacts (re-verify via
  `candidate_summary.json` / `integrity.json`)
- any authorization for Validation, OOS, fusion redesign, parameter search,
  or new candidates — none exists

## N. NEXT SAFE ENTRY POINT (read-only verification first)

```bash
git -C D:\quant-trading status
git -C D:\quant-trading branch --show-current
git -C D:\quant-trading rev-parse HEAD
git -C D:\quant-trading log --oneline -8
git -C D:\quant-trading diff --stat 4d0ee982a0cd4ff1efe76c9fee4c2de807643ac2 HEAD -- docs/research/shenwan_horizon_specific_alpha_hypothesis_v1.md research/configs/horizon_specific_alpha_hypothesis_v1.json research/horizon_specific_alpha_hypothesis_v1_protocol.py research/horizon_specific_alpha_hypothesis_v1_selection.py
docker compose exec quant-research python -c "from research.horizon_specific_alpha_hypothesis_v1_protocol import verify_protocol, FROZEN_PROTOCOL_HASH; verify_protocol(); print(FROZEN_PROTOCOL_HASH)"
docker compose exec quant-research pytest tests/test_horizon_specific_alpha_hypothesis_v1.py tests/test_horizon_specific_alpha_v1_run.py -q
ls reports/research/shenwan_sector_index/ | grep horizon_specific_alpha_v1
```

Only after these confirm the frozen state should the next task begin, under
a fresh human instruction.
