# Shenwan Alpha Stability & Regime Audit V1 — preregistration

Status: **PREREGISTERED; NO FORMAL AUDIT RESULT YET**. Machine contract:
`research/configs/alpha_stability_regime_audit_v1.json`; implementation identity:
`research/alpha_stability_regime_audit_v1_protocol.py`. The canonical SHA-256
of the protocol payload, including the exact parsed machine config, is
`7bdf79df7c95134cdbdedb04ce825614c35a2bc72b4f757dd09ecf5e588fb4c1`.
Neither file may change after the preregistration commit. The document is the
human-readable interpretation of that exact machine contract.

## Scope and research status

This is **POST-V2 DEVELOPMENT DIAGNOSTIC RESEARCH**, designed after viewing
Iteration-1, Factor Alpha Audit V1 and Factor Set V2 Development results.
It is **NOT INDEPENDENT VALIDATION**, **NOT OOS**, not validated alpha and not
executable or tradable. Validation and Final OOS are SEALED. Only Development
E001–E100 (split-policy dates expected 2025-04-02 through 2025-08-26) and
fixed U0 of 124 sector indexes may be evaluated. The three horizons are
10/40/120 project trading sessions. The four *existing* schemes are C0=D2
(all 19 frozen factors), V2_A=(v20), V2_B=(v5,v20), and
V2_D=(d20,p60,align,v20,rev5,dd20). No candidate is created or selected.
Purged and sealed ordinals cannot enter any evaluation path; label prices are
read only through E100's 120-session Purge-1 endpoint.

## Training relationship and transfer

For each Development signal date `s`, horizon `h` and factor `f`, derive the
legal label cutoff and six-calendar-month feature window through the frozen
`SWSectorRotationCore.boundaries` path. Legal training dates are the exact
intersection of realized-label dates across all fixed 124 sector panels,
within `[train_start,label_cutoff]`, as in the formal V2 runner; the minimum
is 30 dates. The signal-date feature panel sees only bars `<=s`. Training
labels on origin `d` end at the project calendar `d+h<=s`; no approximation,
shift, fill, interpolation or future-aware universe shrink is permitted.
For each legal training date, correlate the 124 signed raw factor values with
their realized absolute forward returns using the frozen Factor Alpha Audit
V1 Pearson IC/Spearman RankIC helper (average-rank ties, pairwise-finite,
minimum 30 pairs). Summarize valid dates by mean and median IC and RankIC,
and count valid dates. The formal Ridge training target is same-date
cross-sectional *excess* return; subtracting a common constant from a
single-date return cross-section does not change either correlation.

At `s`, evaluation IC/RankIC uses signed `factor(s)` versus the absolute
return `close[calendar[s+h]]/close[s]-1`. A missing sector endpoint is null,
never shifted or filled; fewer than 30 finite pairs yields null. Across
E001–E100 use complete valid signal-date pairs to report mean/median train
and evaluation RankIC, Pearson and Spearman correlation of train-mean
RankIC versus evaluation RankIC, mean absolute error, and mean signed
`evaluation-train` delta. Constant or fewer-than-two paired series have
null correlation, not zero. Exact-zero signs are separate in raw sign
agreement; the denominator is paired valid dates.

## Descriptive direction and temporal stability

POSITIVE means RankIC `>+0.02`, NEGATIVE means `<-0.02`; inclusive
`[-0.02,+0.02]` is NEUTRAL. A hard flip is POSITIVE→NEGATIVE or
NEGATIVE→POSITIVE only. For every factor × horizon produce a complete 3×3
train/evaluation transition matrix, counts and paired-date rates. For the
evaluation RankIC series report mean, median, population std (`ddof=0`),
min/max, positive/neutral/negative counts, raw sign-change count between
adjacent valid observations, and direction-class change count. Pearson
autocorrelations at lags 1/5/10/20 use aligned non-null pairs; forward labels
overlap, so these are **NOT INDEPENDENT OBSERVATIONS; DESCRIPTIVE ONLY**.
Use only B1 E001–025, B2 E026–050, B3 E051–075 and B4 E076–100 for
block means, median evaluation RankIC, raw sign agreement and hard flips.
No bull/bear, volatility, macro or other after-the-fact regime partition.

## Frozen Ridge replay and coefficients

Replay each formal scheme with exactly its factor order, the same legal
training rows, raw unstandardized X, the same same-date-demeaned training
target, `NumPyRidge(alpha=0.01,fit_intercept=True)`, and the same signal-date
features. Sampled reconstructed predictions must match the existing formal
V2 predictions within `1e-10`; otherwise stop. No new model is fitted for
selection or scored as a candidate. For each factor × scheme × horizon,
report valid dates, positive/negative/exact-zero beta shares, adjacent sign
changes/persistence, and beta mean/median/population std/min/max. Raw beta
magnitudes are not comparable across factors of different raw scales.
`scaleAdjustedBeta = beta * population_std(legal stacked X_train column)`
is a **DIAGNOSTIC_ONLY** comparison; it never enters training or prediction.
Report its mean/median/std, sign persistence and median absolute adjacent
change. Compare beta's raw sign separately with marginal train-mean RankIC
and realized evaluation RankIC, including a beta→future hard-flip rate.
Partial Ridge effects need not have marginal-IC signs.
The beta→future hard flip uses the exact nonzero beta sign opposite a
non-NEUTRAL evaluation RankIC class; beta magnitude never uses the ±0.02
RankIC threshold. Rates use all paired valid dates, including neutral
evaluation dates in the denominator.

## Contribution decomposition

For every scheme/date/horizon/sector/factor compute
`centered_c_ij = beta_j * (x_ij - mean_sector(x_j))`.
`sum_j centered_c_ij` must equal the formal prediction minus its sector
mean within `1e-10`; intercept/common shifts cannot affect ranks. Per factor
and date report population cross-sectional std, mean absolute centered
contribution and absolute share
`sum_i |centered_c_ij| / sum_{i,j}|centered_c_ij|`; a zero total is null,
not an invented allocation. Factor shares sum to one when the denominator
is positive. The per-sector cancellation ratio is
`clip(1-|sum_j centered_c_ij|/(sum_j|centered_c_ij|+1e-12),0,1)`.
The per-date diversification ratio is
`std_sector(sum_j centered_c_ij)/(sum_j std_sector(centered_c_ij)+1e-12)`.
Report mean/median/std/min/max cancellation by scheme/horizon (ALL) and the four
fixed blocks, diversification by scheme/horizon/ALL/block, and mean daily
cross-sectional Spearman matrices of centered contributions for C0, V2_B
and V2_D. V2_A cancellation should be approximately zero (floating epsilon).
These describe prediction decomposition, not causal alpha contributions.

## Identity, integrity and decision discipline

Factor identity samples E001/E050/E100 × 19 factors × first 10 sector codes;
target identity samples the same dates × three horizons × ten sectors and
checks the exact calendar endpoint, direct arithmetic and frozen D0 artifact.
Training-window identity samples E001/E025/E050/E075/E100 × three horizons:
the exact legal-date set via the frozen core, cutoff, first/last date and
observation count must match V2 formal diagnostics. Coefficient identity
samples E001/E050/E100 × three horizons × four schemes against formal V2
predictions; contribution identity uses the same samples. All checks fail
closed. The audit is run twice from an unchanged preregistration commit;
every non-metadata artifact must be byte-identical. Separately recompute
transfer, transitions, beta persistence, shares, cancellation and blocks
from persisted daily artifacts; numerical differences must be floating-only.

Existing C0/V2 model RankIC/spread may be read for temporal association,
not recomputed as a new performance experiment. The final interpretation
must compare v20's contemporaneous versus legal train→future 40d behavior,
C0 versus V2 contribution/cancellation, and 40d versus 120d block structure.
Choose one next gate only: ALPHA_DISCOVERY_REQUIRED,
HORIZON_SPECIFIC_HYPOTHESIS_READY, REGIME_AWARE_HYPOTHESIS_READY, or
DIAGNOSTIC_INCONCLUSIVE. Findings cannot directly trigger V3, factor/sign
selection, horizon/fusion/alpha/TopK tuning, Validation or Final OOS.
