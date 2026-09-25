# SHENWAN FACTOR SET V2 FORMAL DEVELOPMENT RUN REPORT

Status: **FACTOR SET V2 FORMAL DEVELOPMENT RUN COMPLETE**.
POST-AUDIT DEVELOPMENT RESEARCH — not independent validation, not OOS
evidence, not validated alpha, not tradable. All three V2 candidates are
`V2_NOT_ADVANCED`; the frozen C0 control remains the best tested scheme.

## 1. RESEARCH STATE

- Branch: `experiment/sw-sector-index-research-baseline`
- HEAD before: `b836f27e33987ea3d987b8683a38acc442cb2cdd` (preregistration)
- HEAD after: the commit introducing this report
  (`research: run factor set v2`); full SHA in the accompanying research
  summary
- Working tree: clean at start, clean at both runs (the runner's pre-run
  gate allows only the untracked V2 runner + tests), clean at commit

## 2. PREREGISTRATION

- Commit: `b836f27e33987ea3d987b8683a38acc442cb2cdd`
- Protocol path: `docs/research/shenwan_factor_set_v2_preregistration.md`
- Protocol hash (re-verified before and during execution):
  `3fbba8e5b41c0b5b839dab2788f1e000b9add95406bb14cbaf4c13f31664b4f4`
- Config path: `research/configs/factor_set_v2_candidates.json`
- Confirmed: preregistration commit in HEAD ancestry; the four frozen
  files unchanged since the preregistration commit (diff-checked by the
  pre-run gate); protocol hash matched the frozen constant.

## 3. SAMPLE

- Development E001-E100 (ordinals 1-100), date range **2025-04-02 to
  2025-08-26** read from the split policy (not hardcoded)
- Universe U0 = 124 Shenwan Level-2 sector indexes (snapshot
  `872bcbc2…4e500`)
- Horizons 10 / 40 / 120 trading sessions; one shared factor set per
  candidate across all horizons
- Training window 6 calendar months anchored to per-horizon legal label
  cutoff, minimum 30 valid training days; labels realized only inside the
  audited label window (Purge 1 boundary), Validation / Final OOS sealed

## 4. CONTROL

C0 = D2 exactly (19 frozen factors, raw X, cross-sectional excess target,
Ridge 0.01). Cited from the existing Iteration-1 artifact and reproduced
**bit-exactly** in this run (maxAbsDiff **0.0** across all 15 metrics;
C0 artifact SHA-256s equal the frozen D2 hashes):

| metric | C0 = D2 (frozen = rerun) |
| --- | --- |
| Weighted RankIC | 0.08810651455546813 |
| Weighted Spread | 0.037216498377093545 |
| RankIC 10 / 40 / 120 | 0.02544617 / 0.04969240 / 0.22759509 |
| Spread 10 / 40 / 120 | 0.00529746 / 0.01278765 / 0.11799324 |

## 5. CANDIDATES

- **V2_A** `["v20"]` (1 factor) — run
- **V2_B** `["v5", "v20"]` (2 factors) — run
- **V2_D** `["d20", "p60", "align", "v20", "rev5", "dd20"]` (6 factors) — run
- **V2_C** — **NOT RUN** (NOT_ADMISSIBLE; forbidden and absent; budget not
  back-filled)

Run order followed the machine config: C0, V2_A, V2_B, V2_D in one
deterministic pass.

## 6. FORMAL RESULTS TABLE

| Candidate | Factors | Weighted RankIC | Weighted Spread | Level 1 | Level 2 | Horizon Red Flag | Advancement Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C0 (control) | 19 | +0.088107 | +0.037216 | — | — | no | CONTROL_NOT_A_CANDIDATE |
| V2_A | 1 | +0.005550 | -0.014205 | FAIL | FAIL | **YES (40d: -0.0963)** | V2_NOT_ADVANCED |
| V2_B | 2 | +0.017750 | -0.007935 | FAIL | FAIL | **YES (40d: -0.0770)** | V2_NOT_ADVANCED |
| V2_D | 6 | +0.037336 | -0.009888 | FAIL | FAIL | no | V2_NOT_ADVANCED |

LEVEL 1 requires Weighted_RankIC > 0 AND Weighted_Spread > 0: all three
candidates have negative Weighted_Spread. LEVEL 2 (relative to C0) also
fails for all three. Only the allowed labels appear
(`V2_NOT_ADVANCED` / `CONTROL_NOT_A_CANDIDATE`); no WINNER/BEST/PRODUCTION/
VALIDATED/TRADABLE label exists anywhere in the artifacts.

## 7. HORIZON RESULTS

| candidate | h | meanIC | meanRankIC | medianRankIC | stdRankIC | minRankIC | maxRankIC | meanSpread |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | 10 | -0.0174 | +0.0254 | -0.0021 | 0.1965 | -0.3305 | +0.5789 | +0.0053 |
| C0 | 40 | +0.0217 | +0.0497 | +0.0574 | 0.2362 | -0.3748 | +0.4983 | +0.0128 |
| C0 | 120 | +0.2392 | +0.2276 | +0.2463 | 0.1325 | -0.1602 | +0.5104 | +0.1180 |
| V2_A | 10 | +0.0574 | +0.0639 | +0.0284 | 0.1860 | -0.3072 | +0.5081 | +0.0005 |
| V2_A | 40 | -0.1043 | -0.0963 | -0.1418 | 0.1931 | -0.3646 | +0.4995 | -0.0173 |
| V2_A | 120 | +0.1579 | +0.1509 | +0.1821 | 0.2151 | -0.3693 | +0.5873 | -0.0228 |
| V2_B | 10 | +0.0713 | +0.0690 | +0.0261 | 0.2113 | -0.3402 | +0.5198 | +0.0033 |
| V2_B | 40 | -0.0840 | -0.0770 | -0.1315 | 0.2021 | -0.3989 | +0.5016 | -0.0077 |
| V2_B | 120 | +0.1585 | +0.1559 | +0.1675 | 0.1949 | -0.3544 | +0.5623 | -0.0195 |
| V2_D | 10 | -0.0079 | -0.0063 | -0.0271 | 0.2088 | -0.3964 | +0.6584 | -0.0033 |
| V2_D | 40 | -0.0227 | +0.0103 | -0.0320 | 0.2671 | -0.4420 | +0.5741 | -0.0166 |
| V2_D | 120 | +0.1421 | +0.1350 | +0.1273 | 0.2542 | -0.3277 | +0.5538 | -0.0031 |

## 8. DELTA VS C0

| comparison | ΔW RankIC | ΔW Spread | ΔRankIC10 | ΔRankIC40 | ΔRankIC120 | ΔSpread10 | ΔSpread40 | ΔSpread120 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V2_A − C0 | -0.082556 | -0.051422 | +0.038408 | **-0.145985** | -0.076663 | -0.004749 | -0.030062 | -0.140814 |
| V2_B − C0 | -0.070357 | -0.045151 | +0.043603 | **-0.126686** | -0.071659 | -0.002022 | -0.020532 | -0.137519 |
| V2_D − C0 | -0.050770 | -0.047104 | -0.031734 | -0.039360 | **-0.092626** | -0.008556 | -0.029380 | -0.121100 |

Where the (negative) difference comes from: V2_A/V2_B give back a small
gain at 10d (+0.038/+0.044) but lose heavily at 40d (-0.146/-0.127 — the
red-flag horizon) and 120d (-0.077/-0.072). V2_D loses at every horizon,
worst at 120d (-0.093), where C0's advantage lives. No candidate improves
on any weighting of the frozen comparison.

## 9. BLOCK STABILITY

Mean RankIC per frozen block (B1=E001-025, B2=E026-050, B3=E051-075,
B4=E076-100):

| candidate | h | B1 | B2 | B3 | B4 |
| --- | --- | --- | --- | --- | --- |
| C0 | 10 | +0.1793 | +0.0251 | -0.0145 | -0.0881 |
| C0 | 40 | +0.2400 | +0.2615 | -0.1177 | -0.1851 |
| C0 | 120 | +0.2726 | +0.2016 | +0.2529 | +0.1833 |
| V2_A | 10 | +0.2368 | -0.0233 | +0.0473 | -0.0054 |
| V2_A | 40 | +0.1601 | -0.1379 | -0.2381 | -0.1693 |
| V2_A | 120 | +0.3720 | +0.1062 | +0.1262 | -0.0007 |
| V2_B | 10 | +0.2320 | +0.0450 | +0.0116 | -0.0124 |
| V2_B | 40 | +0.1864 | -0.1246 | -0.2389 | -0.1309 |
| V2_B | 120 | +0.3704 | +0.0953 | +0.1334 | +0.0247 |
| V2_D | 10 | +0.1635 | +0.0565 | -0.0857 | -0.1595 |
| V2_D | 40 | +0.2456 | +0.2397 | -0.1791 | -0.2649 |
| V2_D | 120 | +0.4172 | +0.2643 | -0.1780 | +0.0364 |

(Block mean spreads mirror the same pattern; see
`block_stability.csv`.) Nothing is carried by a single block only — but
every scheme is regime-split: gains live in B1-B2 and turn negative in
B3-B4 at 10/40d (V2_A/B 40d even runs negative from B2 onward). C0's
promotion is not uniformly stable either: its 40d block means flip
negative in B3/B4, and its standing rests mainly on 120d (+0.2276, the
only horizon positive in all four blocks, though decaying B1→B4 in the
compact candidates). Block results were not used to modify any candidate.

## 10. SIMPLICITY PREFERENCE

**Not triggered.** With zero advanced candidates there is nothing to
compare; `tiedPairs = []`, `preferred = null`. Raw metrics (§6-§8) and the
simplicity rule are reported separately; no tie-break was applied.

## 11. ADVANCEMENT DECISION

Frozen rule applied verbatim to each candidate:

- **V2_A**: W_RankIC +0.0056 > 0 but W_Spread -0.0142 ≤ 0 → LEVEL 1 FAIL;
  LEVEL 2 FAIL (neither option A nor B); horizon red flag at 40d
  (mean RankIC -0.0963 < -0.02) → `V2_NOT_ADVANCED`.
- **V2_B**: W_Spread -0.0079 ≤ 0 → LEVEL 1 FAIL; LEVEL 2 FAIL; red flag at
  40d (-0.0770) → `V2_NOT_ADVANCED`.
- **V2_D**: W_Spread -0.0099 ≤ 0 → LEVEL 1 FAIL; LEVEL 2 FAIL (all deltas
  vs C0 negative); no red flag → `V2_NOT_ADVANCED`.

The -0.02 red-flag threshold, the LEVEL 2 options and the 0.01/0.01 tie
bands are exactly the preregistered values; nothing was adjusted after
seeing results.

## 12. MODEL DIAGNOSIS

**Primary: E. V2_DID_NOT_IMPROVE_C0.**

Evidence:

1. No candidate passes LEVEL 1 or LEVEL 2; every weighted delta versus C0
   is negative on both metrics (-0.051..-0.083 W_RankIC,
   -0.045..-0.051 W_Spread). De-redundified and volatility-only inputs are
   strictly worse than the 19-factor control on the frozen comparison.
2. A MIXED horizon/block conflict is present in all candidates and is the
   mechanism: V2_A/V2_B run positive at 10d and 120d but invert at 40d
   (red flag), and every scheme's 10/40d gains sit in B1-B2 while B3-B4
   turn negative. Walk-forward Ridge coefficients are estimated on
   trailing windows whose factor-return relation lags the evaluation
   window's relation.
3. Q5 is answered against the dilution hypothesis: Audit V1's
   contemporaneous single-factor IC (v20 RankIC40 +0.1867, 4/4 blocks)
   massively overstates harvestable walk-forward signal (V2_A RankIC40
   -0.0963; only 21/100 positive dates). Removing redundancy did not
   unlock the volatility information — it removed the diversification
   that made C0 relatively robust. The earlier
   MODEL_EXTRACTION_WEAK lean is revised by this run: the binding
   constraint is the regime lag between training-window and
   evaluation-window relations, not redundant inputs, and not the target
   (identical across all schemes by design).

Q1 (de-redundancy helps): **No.** Q2 (v20-only baseline): interpretable
but insufficient; fails at 40d. Q3 (v5 adds stable increment): marginal
(+0.012 W_RankIC over V2_A), not stable. Q4 (cross-family reps help):
V2_D > V2_A/V2_B on W_RankIC (+0.0373) but still < C0 and fails LEVEL 1.
No claim about future profitability is made or implied.

## 13. PARAMETER_RESEARCH_GATE

**PARAMETER_RESEARCH_GATE = NOT_READY.**

Reasoning: the preregistered READY condition (at least one candidate
clearly improving on C0 with no red flag and robust blocks) is not met —
all candidates fail the relative gate and two carry horizon red flags.
The NOT_READY condition ("no V2 candidate clearly improves C0") is
literally satisfied. Entering parameter search now would tune a pipeline
whose input-reduction hypothesis just failed; the correct next step is a
re-evaluation of the Alpha Hypothesis / Factor Discovery level — with the
new constraint that contemporaneous single-factor IC overstates
walk-forward harvestable signal in this sample.

## 14. ARTIFACTS

- First formal run: `reports/research/shenwan_sector_index/factor_set_v2_20260925_090958_520718_utc/`
- Determinism rerun: `reports/research/shenwan_sector_index/factor_set_v2_20260925_091616_084266_utc/`
- File list (each run): `metadata.json`, `candidate_summary.json`,
  `block_stability.csv`, `integrity.json`, and per scheme
  (C0/V2_A/V2_B/V2_D): `predictions.csv`, `per_date_metrics.csv`,
  `per_date_predictions.csv`, `aggregate_metrics.json`,
  `training_diagnostics.csv`, `data_quality_diagnostics.json`,
  `transformation_diagnostics.json`
- Generated research output stays untracked per repo convention
  (`/reports/research/` gitignored); provenance via protocol hash, commits
  and recorded SHA-256s.

## 15. DETERMINISM

Rerun with unchanged inputs: all 30 non-metadata artifacts **byte-identical**
(identical SHA-256; the `--repeat-of` check enforces this and would raise
`FACTOR_SET_V2_DETERMINISM_BLOCKER`). Representative hashes (identical in
both runs): `candidate_summary.json feb0727d…dddb9bf4`,
`block_stability.csv ba4e085a…e7b0b05`, `integrity.json 7b4180b0…5ef2e21`,
`V2_A/aggregate_metrics.json e402caaf…abe526`,
`V2_B/aggregate_metrics.json b121bc09…776a1497`,
`V2_D/aggregate_metrics.json 8df64302…eadb171fc`. C0 artifacts are
additionally byte-identical to the frozen Iteration-1 D2 artifacts
(`aggregate_metrics.json cc7f9b57…`, `predictions.csv b2191cdc…`,
`per_date_metrics.csv 4ee1f100…`).

## 16. FACTOR IDENTITY

**PASS** — sampled Ridge-input factor values (3 Development dates: E001,
E050, E100 × all 19 pipeline factors — a superset of every V2 factor —
× 10 sectors = 570 comparisons) versus independent recomputation:
max abs diff **1.60e-14** (tolerance 1e-9, floating-point only).

## 17. TARGET IDENTITY

**PASS** — sampled labels (3 dates × 3 horizons × 10 sectors = 90
comparisons) versus (a) direct common-calendar arithmetic and (b) the
frozen Iteration-1 D2 artifact: max abs diff **0.00e+00** (direct) and
**1.11e-16** (artifact) within tolerance 1e-12. Endpoint semantics
`label_end = calendar[t+h]` confirmed on every sampled row; no shift, fill
or interpolation anywhere. Excess target applies only to training targets
(same-date cross-sectional demeaning; residual group means < 1e-12);
evaluation labels remain absolute forward returns.

## 18. METRIC INTEGRITY

Independent recompute of IC/RankIC/spread/weighted metrics from
`predictions.csv` versus `candidate_summary`/`aggregate_metrics`:
**PASS**, max abs diff **1.39e-17** (tolerance 1e-12). C0 reproduction
control: **PASS**, max abs diff **0.0** versus the frozen D2 metrics.

## 19. TESTS

- Targeted (`tests/test_factor_set_v2_protocol.py` 16 +
  `tests/test_factor_set_v2_run.py` 15): **passed 31, failed 0,
  skipped 0**. Coverage includes exact prereg commit, protocol hash,
  exact candidates, V2_C forbidden, candidate budget, factor identity,
  target identity, Development-only guards, Validation/OOS sealed, excess
  target demeaning, raw X, alpha 0.01, 6-month window, 10/40/120, shared
  factor set across horizons, fusion 0.25/0.50/0.25, Top5 semantics,
  weighted metric weights, advancement LEVEL 1/LEVEL 2/red flag,
  simplicity tie-break, block slicing, deterministic ordering/bytes,
  artifact schema, result labels, selection-bias flags, determinism
  drift detection.
- Full suite: **passed 549, failed 0, skipped 2, deselected 17**
  (integration marker policy).

## 20. SELECTION BIAS

**POST-AUDIT DEVELOPMENT RESEARCH. NOT INDEPENDENT VALIDATION. NOT OOS.**
V2 candidates were designed after inspecting Factor Alpha Audit V1 on the
same E001-E100; these results are therefore not independent confirmation
of anything, regardless of sign. They are not "validated alpha", not an
OOS result, not "ready for trading", and they do not open Validation.

## 21. RESEARCH COMPLIANCE

Development only ✓ · Validation untouched (SEALED) ✓ · Final OOS
untouched (SEALED) ✓ · no candidate adaptation (lists/settings identical
to preregistration) ✓ · no parameter search ✓ · no factor search ✓ · no
sign optimization ✓ · no model replacement ✓ · no Docker change ✓ · no
dependency change ✓ · no Hikyuu change ✓ · no Dashboard/API change ✓ · no
portfolio ✓ · no ETF ✓ · no QMT ✓ · preregistration protocol/config/hash
unmodified ✓ · existing Iteration-1 / Audit V1 artifacts read-only and
hash-verified ✓.

## 22. ENVIRONMENT_CHANGED

**false** — frozen container `quant-research:py3.12`, image
`sha256:57858238…02e5` verified by the pre-run gate; all execution via
`docker compose exec quant-research`.

## 23. RESULT COMMIT

The commit introducing this report (`research: run factor set v2`),
containing the V2 runner, runner tests and this report; full SHA recorded
in the accompanying research summary. No push, no merge.

## 24. NEXT AUTHORIZED ACTION

**RETURN TO ALPHA / FACTOR HYPOTHESIS DESIGN AFTER HUMAN REVIEW**
(per the preregistered NOT_READY path). Not executed automatically.

## 25. FINAL STATUS

**FACTOR SET V2 FORMAL DEVELOPMENT RUN COMPLETE**

(No non-blocking warnings: the extreme-date sensitivity method WAS defined
in the frozen protocol and was executed as specified; all integrity and
determinism gates passed.)
