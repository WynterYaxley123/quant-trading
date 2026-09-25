# Shenwan Factor Set V2 / Alpha Hypothesis V2 preregistration

Status: **PREREGISTERED, NOT RUN**. This document,
`research/configs/factor_set_v2_candidates.json` and
`research/factor_set_v2_protocol.py` freeze the complete Factor Set V2
candidate family, control identity, comparison metrics and advancement
rules BEFORE any Factor Set V2 result exists. This round produced no V2
predictions, no V2 metrics, and no V2 artifacts.

- Protocol path: `docs/research/shenwan_factor_set_v2_preregistration.md`
- Machine config: `research/configs/factor_set_v2_candidates.json`
- Protocol hash (canonical payload SHA-256, frozen constant):
  `3fbba8e5b41c0b5b839dab2788f1e000b9add95406bb14cbaf4c13f31664b4f4`

**POST-AUDIT DEVELOPMENT RESEARCH.** Every V2 hypothesis below derives from
Development results already observed in Factor Alpha Audit V1 (E001-E100).
Factor Set V2 results on the same E001-E100 can never count as independent
validation or OOS evidence. Its role is hypothesis refinement, redundancy
reduction, and model-input design only.

## 1. Background

The frozen Development baseline (Iteration-1, run
`iteration1_20260924_163607_787266_utc`, protocol hash
`f2080f56a3f4a77ff983d5b9cc14c0f1427f4d2c84fb1d9fc89b9a2a3cb12125`)
showed that train-only X standardization is ineffective (D1≈D0, D3≈D2) and
that switching the Ridge training target to same-training-date
cross-sectional excess forward return produces the entire improvement (D2
and D3 promoted under the preregistered conjunction). Factor Alpha Audit V1
(primary run `factor_alpha_audit_20260925_071934_967164_utc`, protocol hash
`87e6e9c3ac79f1f41239d8c91080b16fd142343dea470084226e23512286b815`,
determinism rerun byte-identical) then characterized the frozen 19 price
factors themselves. Both artifacts were re-read and re-verified at the start
of this round; all values cited below come from those formal artifacts.

## 2. Factor Alpha Audit V1 evidence (re-verified this round)

- v20 signed RankIC 0.0713 / 0.1867 / 0.2164 (10/40/120), quantile
  monotonicity 1.0 at every horizon, block stability 4/4 at every horizon;
  standalone Weighted_RankIC **+0.1653** versus the D2 control's +0.0881.
- v5 signed RankIC 0.0270 / 0.1129 / 0.1503, monotonicity 1.0, blocks
  3/4 (10d) and 4/4 (40/120); standalone Weighted_RankIC +0.1008.
- v5 ↔ v20 mean daily cross-sectional Spearman = **0.6298417623918176**
  (below the frozen 0.80 threshold) — the V2-B complementarity premise is
  artifact-supported; no V2_HYPOTHESIS_ARTIFACT_MISMATCH.
- 16 factor pairs at |mean daily Spearman| >= 0.80, all inside the
  d/p/rev/dd/rsi clusters (trend-position duplicates, reversal-vs-trend
  negatives, rsi-vs-d20, p20/dd20, p60/dd60). v5/v20 sit outside all
  flagged pairs.
- Systematic regime flip: trend/position/oscillator/drawdown factors run
  negative in blocks 1-2 and positive in blocks 3-4, reversal mirrors;
  almost all non-volatility factors are 2/4 same-sign with obvious sign
  flips (v20 is the only 4/4 factor at all horizons; v5 4/4 at 40/120).
- Coverage is perfect (12,400/12,400 finite observations per factor, 0
  skipped dates); factor identity and target identity gates passed.
- Audit V1 conclusion: Ridge diagnosis leaned
  MODEL_EXTRACTION_WEAK; PARAMETER_RESEARCH_GATE = CONDITIONAL with the
  prescribed next step "Factor Set V2 / Alpha Hypothesis V2 first".

## 3. Why V2 exists

D2 fixes the target but still extracts far less than the available
volatility information (D2 weighted RankIC 0.088 vs v20-alone 0.165; D2
RankIC40 0.050 vs v20-alone 0.187). The audit attributes the gap to input
redundancy (16 pairs ≥ 0.80, ~6-7 independent dimensions behind 19
columns), regime-unstable majority inputs, and signal dilution — not to the
target. V2 isolates the factor set as the ONLY permitted change: if a
de-redundified input lets Ridge approach the single-factor evidence, the
extraction hypothesis is supported and Parameter Research becomes
justified on the V2 input design; if not, the remaining gap needs Alpha
Discovery, not tuning.

## 4. Research hypotheses (preregistered questions)

- **Q1**: removing redundant / regime-unstable inputs lets Ridge use the
  observed volatility information more effectively (tested by V2-B/V2-D
  versus C0).
- **Q2**: v20-only is a simple, interpretable baseline (tested by V2-A
  versus C0).
- **Q3**: v5+v20 provides stable incremental information over v20-only
  (tested by V2-B versus V2-A).
- **Q4**: adding a few preregistered, low-redundancy, cross-family
  representatives improves volatility-only (V2-C is NOT ADMISSIBLE — see
  §7; tested structurally by V2-D versus V2-B/V2-A).
- **Q5**: D2's weakness versus single-factor diagnostics stems from
  redundant features / unstable signs / signal dilution rather than target
  failure (target identical across C0 and all candidates; only the factor
  set varies).

Out of scope this cycle: best alpha, best train window, best fusion
weights, best TopK, best model — all reserved for future Parameter
Research.

## 5. Frozen control C0

C0 is exactly the promoted D2 configuration and counts as control, not as
a new candidate:

- 19 frozen factors in frozen pipeline order
  (`d5, d10, d20, d60, d120, p5, p10, p20, p60, p120, align, v5, v20, vc,
  rev5, rev10, dd20, dd60, rsi`)
- raw X (no standardization), cross-sectional excess forward-return target,
  NumPyRidge alpha 0.01

Cited metrics from the existing artifact only (no new C0 was run this
round):

| metric | value |
| --- | --- |
| Weighted_RankIC | 0.08810651455546813 |
| Weighted_Spread | 0.037216498377093545 |
| RankIC_10 / _40 / _120 | 0.025446168371361138 / 0.049692399685287166 / 0.22759509047993703 |
| Spread_10 / _40 / _120 | 0.005297457266283392 / 0.01278764643554297 / 0.11799324337100485 |

All V2 candidates must share with C0 the exact same Development dates,
universe, target semantics, train window, Ridge implementation, alpha,
horizons, fusion, ranking, Top5 and metric contract. The **only** allowed
difference is the factor list. The future V2 run must re-run C0 in the same
harness as a reproduction control and match the frozen values above within
floating tolerance (`C0_REPRODUCTION_BLOCKER` otherwise); advancement
comparisons use the frozen values.

## 6. Candidate budget

- Maximum **4 new candidates**; with C0 at most **5 schemes total**.
- Actual admitted this preregistration: **3 new** (V2_A, V2_B, V2_D) + C0.
- V2-C is NOT ADMISSIBLE (§7) and is deliberately NOT replaced. The budget
  is not back-filled; the limit of 4 is a ceiling, not a quota. This
  constraint is disclosed here as required.
- Forbidden: adding a fifth new candidate, post-result candidate creation,
  adaptive search, greedy forward selection, backward elimination,
  exhaustive subset search, random subset search. The budget closes with
  this preregistration.

## 7. Exact candidate factor lists

All candidate factor lists appear machine-readably in
`research/configs/factor_set_v2_candidates.json`, in deterministic frozen
pipeline order, and are frozen by protocol hash.

**V2-A — V20 ONLY.** `["v20"]` (1 factor). Simplest volatility-only
benchmark on the canonical 20-session realized volatility. Tagged
**POST-AUDIT DEVELOPMENT HYPOTHESIS** — it is derived from observed Audit
V1 evidence and does not pretend to be independent alpha discovery.

**V2-B — V5 + V20.** `["v5", "v20"]` (2 factors). Short-window versus
medium-window volatility complementarity. Premise re-verified from formal
artifacts: v5 ↔ v20 mean daily Spearman = 0.6298417623918176 < 0.80.
(If any future verification disagrees, stop with
`V2_HYPOTHESIS_ARTIFACT_MISMATCH`.)

**V2-C — VOLATILITY + ONE COMPLEMENTARY FAMILY: NOT ADMISSIBLE.** The
designed form was `[v5, v20, X]` with X from a non-volatility family,
selected by the preregistered priority: (1) not highly redundant with
v20/v5, (2) clear economic meaning, (3) interpretable horizon behavior,
(4) complete coverage, (5) not reliant on direction flip, (6) different
family. Candidate pool and exclusions (all facts from Audit V1 artifacts):

| X pool (non-volatility family) | family | max abs corr vs v20/v5 | blocks sameSign 10/40/120 | verdict |
| --- | --- | --- | --- | --- |
| d5 | TREND_MOMENTUM | 0.099 | 2/2/2 | EXCLUDED: criterion 5 + regime rule (block sign flip) |
| d10 | TREND_MOMENTUM | 0.218 | 2/2/2 | EXCLUDED: criterion 5 + regime rule |
| d20 | TREND_MOMENTUM | 0.283 | 2/2/2 | EXCLUDED: criterion 5 + regime rule |
| d60 | TREND_MOMENTUM | 0.241 | 2/2/2 | EXCLUDED: criterion 5 + regime rule |
| d120 | TREND_MOMENTUM | 0.274 | 3/2/2 | EXCLUDED: criterion 5 + regime rule |
| p5 | RANGE_POSITION | 0.061 | 3/2/2 | EXCLUDED: criterion 5 + regime rule |
| p10 | RANGE_POSITION | 0.090 | 3/2/2 | EXCLUDED: criterion 5 + regime rule |
| p20 | RANGE_POSITION | 0.121 | 2/2/2 | EXCLUDED: criterion 5 + regime rule |
| p60 | RANGE_POSITION | 0.107 | 2/2/2 | EXCLUDED: criterion 5 + regime rule |
| p120 | RANGE_POSITION | 0.204 | 2/2/2 | EXCLUDED: criterion 5 + regime rule |
| align | OSCILLATOR_ALIGNMENT | 0.171 | 3/2/2 | EXCLUDED: criterion 5 + regime rule |
| rsi | OSCILLATOR_ALIGNMENT | 0.169 | 2/2/2 | EXCLUDED: criterion 5 + regime rule |
| rev5 | REVERSAL | 0.201 | 2/2/2 | EXCLUDED: criterion 5 + regime rule |
| rev10 | REVERSAL | 0.282 | 2/2/2 | EXCLUDED: criterion 5 + regime rule |
| dd20 | DRAWDOWN | 0.328 | 1/2/2 | EXCLUDED: criterion 5 + regime rule |
| dd60 | DRAWDOWN | 0.252 | 2/2/2 | EXCLUDED: criterion 5 + regime rule |
| vc | VOLATILITY | 0.687 | 2/3/2 | EXCLUDED: volatility family (criterion 6) and criterion 5 |

Every pool member passes criteria 1-4 (none is redundant with v20/v5; all
have complete coverage) but fails criterion 5 — each carries a Development
block sign flip — and therefore also fails the §10 regime rule for core
additions. Rather than hard-fit an X, **V2-C = NOT_ADMISSIBLE**.

**V2-D — FAMILY REPRESENTATIVE COMPACT SET.** `["d20", "p60", "align",
"v20", "rev5", "dd20"]` (6 factors; within the suggested 3-6 range and the
hard cap 6). Exactly one representative per factor family. Selection uses
**zero return-performance metrics**: families are processed in frozen
pipeline first-appearance order; within a family the canonical-window
preference order is tried first (20-session canonical, then longer, then
shorter; RSI before align; rev10 before rev5; v20 before v5 before vc); a
member is skipped if it is HIGH_REDUNDANCY (|mean daily Spearman| >= 0.80)
with any already-selected representative. Selection trace (also frozen in
the config):

| step | family | tried | decision | reason |
| --- | --- | --- | --- | --- |
| 1 | TREND_MOMENTUM | d20 | SELECTED | canonical monthly deviation; no prior selections |
| 2 | RANGE_POSITION | p20 | SKIPPED | spearman with d20 = 0.8413 >= 0.80 |
| 3 | RANGE_POSITION | p60 | SELECTED | max abs spearman with selected 0.6861 |
| 4 | OSCILLATOR_ALIGNMENT | rsi | SKIPPED | spearman with d20 = 0.8647 >= 0.80 |
| 5 | OSCILLATOR_ALIGNMENT | align | SELECTED | max abs spearman with selected 0.6551 |
| 6 | VOLATILITY | v20 | SELECTED | canonical medium-window vol; max abs spearman 0.1405 |
| 7 | REVERSAL | rev10 | SKIPPED | spearman with d20 = -0.8937, abs >= 0.80 |
| 8 | REVERSAL | rev5 | SELECTED | max abs spearman with selected 0.6995 |
| 9 | DRAWDOWN | dd20 | SELECTED | canonical monthly drawdown; max abs spearman 0.7045 |

All 15 internal pairs of the resulting set are below 0.80 (max internal
abs = 0.7045). The set is also robust to the family processing order: the
cascade under pipeline-order and volatility-first processing selects the
same members.

**REGIME_UNSTABLE labels on V2-D:** `d20, p60, align, rev5, dd20` (only
v20 is 4/4 stable). Justification (non-result-driven): these five enter
solely as canonical dimension representatives of their price-information
families under the frozen family-mapping and redundancy-cascade rules,
which reference no IC / return / block metric. Their block signs are
disclosed as regime-dependent; Ridge learns coefficients on raw signed
factors and no direction is fixed or flipped by design. The V2-D
hypothesis is structural (does a de-redundified cross-family input improve
extraction?), not per-factor alpha.

## 8. Factor family mapping

| factor | family | definition summary | redundancy notes (>= 0.80 pairs) | stability notes (sameSign 10/40/120) | V2 eligibility |
| --- | --- | --- | --- | --- | --- |
| d5 | TREND_MOMENTUM | (close-MA5)/MA5 | d10, p5 | 2/2/2 | not selected |
| d10 | TREND_MOMENTUM | (close-MA10)/MA10 | d5, d20, p10, rev5, rev10 | 2/2/2 | not selected |
| d20 | TREND_MOMENTUM | (close-MA20)/MA20 | d10, p20, rev10, rsi | 2/2/2 | **V2-D rep (REGIME_UNSTABLE)** |
| d60 | TREND_MOMENTUM | (close-MA60)/MA60 | d120, p60 | 2/2/2 | not selected (cascade) |
| d120 | TREND_MOMENTUM | (close-MA120)/MA120 | d60, p120 | 3/2/2 | not selected (cascade) |
| p5 | RANGE_POSITION | 5d range position | d5, p10 | 3/2/2 | not selected |
| p10 | RANGE_POSITION | 10d range position | d10, p5, p20 | 3/2/2 | not selected |
| p20 | RANGE_POSITION | 20d range position | d20, p10, dd20 | 2/2/2 | skipped (redundant with d20) |
| p60 | RANGE_POSITION | 60d range position | d60, dd60 | 2/2/2 | **V2-D rep (REGIME_UNSTABLE)** |
| p120 | RANGE_POSITION | 120d range position | d120 | 2/2/2 | not selected (cascade) |
| align | OSCILLATOR_ALIGNMENT | MA-ordering score /6 | none | 3/2/2 | **V2-D rep (REGIME_UNSTABLE)** |
| v5 | VOLATILITY | 5d return std | none (v20 = 0.63 < 0.80) | 3/4/4 | **V2-B** |
| v20 | VOLATILITY | 20d return std | none | 4/4/4 | **V2-A, V2-B, V2-D rep** |
| vc | VOLATILITY | v5/(v20+eps) ratio | none | 2/3/2 | not selected (family preference) |
| rev5 | REVERSAL | -mean 5d return | d10 | 2/2/2 | **V2-D rep (REGIME_UNSTABLE)** |
| rev10 | REVERSAL | -mean 10d return | d10, d20 | 2/2/2 | skipped (redundant with d20) |
| dd20 | DRAWDOWN | close/rolling20d high-1 | p20 | 1/2/2 | **V2-D rep (REGIME_UNSTABLE)** |
| dd60 | DRAWDOWN | close/rolling60d high-1 | p60 | 2/2/2 | not selected (cascade) |
| rsi | OSCILLATOR_ALIGNMENT | RSI14 | d20 | 2/2/2 | skipped (redundant with d20) |

Family mapping rationale: 19 factors form six price-information dimensions
— trend strength (MA deviation), range position, volatility (level and
shape), reversal, drawdown, and bounded oscillators of trend state. The
mapping follows factor definitions only.

## 9. Redundancy rule

Frozen threshold carried over from Audit V1: `|mean daily cross-sectional
Spearman| >= 0.80` = HIGH REDUNDANCY. The 16 flagged pairs are frozen in
the machine config (with their exact values). V2-D must not contain a
flagged pair (it does not); if any future design ever must, it requires an
explicit written reason — "both factors looked good historically" is never
a reason. No factor is ever deleted automatically.

## 10. Regime instability rule

Frozen blocks E001-E025 / E026-E050 / E051-E075 / E076-E100. A factor with
only 2/4 same-sign blocks AND an obvious block sign flip cannot be a core
addition to V2-C/V2-D unless a strong non-result-driven theoretical reason
exists; if retained it must carry the `REGIME_UNSTABLE` label and a written
justification. V2-D's five labeled members are the only retained case
(§7). Nothing may be selected or dropped dynamically from block behavior
during the future run.

## 11. Frozen model settings

Model `NumPyRidge`, alpha **0.01**, training window **6 calendar months**
anchored to the per-horizon label cutoff (purged), minimum valid training
days **30**, prediction order higher-score-first with sector code ascending
tie-break. No ElasticNet / LightGBM / XGBoost / CatBoost / neural nets.

## 12. Frozen target

`CROSS_SECTIONAL_EXCESS_FORWARD_RETURN`: raw label `close[t+h]/close[t]-1`
on the common project trading calendar (t+h endpoint; missing endpoint
stays missing — no shift, no fill), demeaned within the same training
feature date and horizon over admissible realized rows only. Evaluation
continues on absolute realized forward returns with the unchanged frozen
15-metric prediction contract. Identical for C0 and every candidate.

## 13. Frozen horizons

10 / 40 / 120 trading sessions. Every candidate uses ONE shared factor set
across all three horizons; per-horizon factor sets are forbidden.

## 14. Frozen fusion

`0.25 * pred10 + 0.50 * pred40 + 0.25 * pred120` on the fused score. No
weight tuning.

## 15. Frozen Top5

The formal Top5 is the highest five **fused** scores (sector code ascending
breaks exact ties). Per-horizon Top5 misuse is forbidden. TopK = 5.

## 16. Development-only sample

Development signal dates E001-E100 only (ordinals 1-100 of the frozen
Policy C eligible calendar; split policy hash
`3b6b2d754211169039439c8b377fd9eb26d5cb5db0f80d62cffc1d19c81a7038`).
Universe U0 fixed 124 Shenwan Level-2 sector indexes (snapshot
`872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`).
All evaluation requests must pass `guard_evaluation("development", ...)` /
`guard_factor_set_v2_scope`. Purge 1 prices appear only to realize
Development labels inside the audited label window, exactly as in the
frozen baseline adapter.

## 17. Metrics

- `Weighted_RankIC = 0.25*meanRankIC10 + 0.50*meanRankIC40 +
  0.25*meanRankIC120`
- `Weighted_Spread = 0.25*meanSpread10 + 0.50*meanSpread40 +
  0.25*meanSpread120`

Pre-registered comparison set (no "highest value wins" selection):
Weighted_RankIC, Weighted_Spread, each-horizon mean RankIC, each-horizon
mean spread, each-horizon median RankIC, stability across the four
Development blocks, extreme-date sensitivity, and candidate simplicity
(factor count).

Extreme-date sensitivity (frozen definition, descriptive only): recompute
Weighted_RankIC / Weighted_Spread excluding the 5 lowest and 5 highest
Development dates by U0 mean realized 120-session forward return (ties by
ordinal ascending); sensitivity = full minus extreme-excluded.

## 18. Advancement rules (frozen)

**LEVEL 1 — BASIC:** `Weighted_RankIC > 0 AND Weighted_Spread > 0`,
otherwise `V2_NOT_ADVANCED`.

**LEVEL 2 — RELATIVE TO C0:** at least one of
- (A) `Weighted_RankIC > C0 AND Weighted_Spread >= C0`, or
- (B) `Weighted_Spread > C0 AND Weighted_RankIC >= C0`.

**HORIZON RED FLAG (frozen threshold):** any horizon mean RankIC <
**-0.02** blocks advancement regardless of LEVEL 1/2 ("obviously reversed"
is defined exactly this way and never adjusted after results).

`V2_ADVANCED_FOR_FURTHER_REVIEW` requires LEVEL 1 AND LEVEL 2 AND no red
flag. Advancement is Development research status only — never validation
admission.

## 19. Simplicity rule (frozen)

`SIMPLICITY_PREFERENCE = true`. Between advanced candidates, if
`|ΔWeighted_RankIC| < 0.01` AND `|ΔWeighted_Spread| < 0.01`, prefer the
candidate with fewer factors; at equal factor count prefer the lower
candidate ID order (V2_A, V2_B, V2_D). This is a discipline guard against
buying trivial Development differences with complexity — not statistical
truth.

## 20. No-adaptive-search rule

The candidate budget closes with this preregistration. Forbidden before or
during the future run: 19-choose-k brute force, "top N by RankIC",
"top N by Weighted RankIC", Q5-Q1 sorting, t-stat ranking, per-horizon
factor sets, block-based dynamic selection, regime switching, factor
timing, factor/target weighting, adaptive candidate addition. (For full
list see `prohibitions` in the machine config.)

## 21. No parameter tuning

Alpha, train window, fusion weights, TopK, horizons, target and
preprocessing are frozen for the entire V2 cycle. Any tuning is future
Parameter Research under separate authorization.

## 22. No sign flip

Factor definitions and signs stay exactly as frozen. Negative-direction
relationships (e.g., dd60, rev10) are never multiplied by -1, redefined, or
converted to inverse factors; Ridge learns its own coefficients. No sign
normalization exists anywhere in the V2 design.

## 23. No Validation / Final OOS

Validation and Final OOS remain SEALED. No V2 design, code, test or
preview may read them; ordinal/phase guards enforce this. Any code path
that would require them is `SEALED_PHASE_DEPENDENCY_BLOCKER`.

## 24. Known post-audit selection caveat (selection-bias disclosure)

V2-A/V2-B/V2-D are **POST-AUDIT DEVELOPMENT HYPOTHESIS / POST-AUDIT
DEVELOPMENT RESEARCH**: they were derived after inspecting Factor Alpha
Audit V1 results on E001-E100. Factor Set V2 results on the same E001-E100
are therefore NOT independent validation and NOT OOS evidence, regardless
of outcome. Their evidential role is limited to: refining the hypothesis,
reducing redundancy, and designing model inputs. The redundancy cascade
itself uses the Audit V1 factor-factor correlation structure (input
structure, not return performance); no IC/return/block metric entered any
candidate selection. Genuine validation can only come from the sealed
phases under future separate authorization.

## 25. Future execution plan (not authorized by this round)

Next round, after human review: implement `research/factor_set_v2_run.py`
reusing the frozen baseline adapter and the D2 transform, with factor
subset routing via `factor_indices`; run C0 reproduction control + V2_A +
V2_B + V2_D on Development E001-E100 in one pass (no early stopping);
factor/target identity gates; deterministic artifact writing to
`reports/research/shenwan_sector_index/factor_set_v2_<timestamp>_utc/`;
determinism rerun with byte-identical non-metadata artifacts; report the
§17 comparison set and the Q1-Q5 diagnostics; evaluate advancement via the
frozen §18 rules only. Authorized action wording after review: **RUN FACTOR
SET V2 UNDER FROZEN PROTOCOL AFTER HUMAN REVIEW**.

## 26. Stop conditions

- `V2_HYPOTHESIS_ARTIFACT_MISMATCH` — any frozen evidence premise (e.g.,
  v5↔v20 = 0.6298417623918176) fails re-verification against artifacts.
- `C0_REPRODUCTION_BLOCKER` — the future C0 re-run does not reproduce the
  frozen D2 metrics within floating tolerance.
- `SEALED_PHASE_DEPENDENCY_BLOCKER` — any path needs Validation/OOS.
- `FACTOR_IDENTITY_BLOCKER` / `TARGET_IDENTITY_BLOCKER` — subset factor
  values or labels diverge from the frozen pipeline definitions.
- `FACTOR_SET_V2_DETERMINISM_BLOCKER` — rerun artifacts not byte-identical.
- `PREREGISTRATION_RESULT_LEAK_BLOCKER` — V2 formal results found before
  the preregistration commit (checked this round: none).
- `RESEARCH_WORKTREE_DIRTY_BLOCKER` / `ENVIRONMENT_STABILITY_BLOCKER` —
  P0 conditions.

---

Preregistration sequencing: this document, the machine config, the
protocol module and their tests are committed together
(`research: preregister factor set v2`) with NO V2 result artifacts in
existence; that commit is the frozen starting point for any future V2 run.
This round stops here.
