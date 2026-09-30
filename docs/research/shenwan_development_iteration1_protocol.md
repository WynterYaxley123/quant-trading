# Shenwan sector-index Development Iteration-1 preregistration

Status: **PREREGISTERED, NOT RUN**. This document and
`research/development_iteration1_protocol.py` freeze the complete four-member
candidate family before any D1/D2/D3 performance is calculated. They do not
authorize a candidate run. The protocol identity is
`development_iteration1_protocol_hash =
f2080f56a3f4a77ff983d5b9cc14c0f1427f4d2c84fb1d9fc89b9a2a3cb12125`.

## Research identity and reason

This remains `SECTOR_INDEX_RESEARCH_ONLY`, `executable=false`,
`strict_pit=false`, and `FIXED_CLASSIFICATION_RESEARCH` on the frozen sector
snapshot `872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`.
It is **NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST**. ETF execution,
LEVEL B, and synthetic portfolio construction remain disabled.

The D0 Development baseline at commit
`c901e30fa3061de0463b90edd057589bd25ca6c7` has weak/negative
prediction evidence. The independent integrity audit preserved at commit
`5e6d396` found no label, feature/target, training-window, Ridge, ranking, or
metric implementation artifact. Iteration-1 therefore asks only two
predeclared methodological questions: whether per-training-window feature
scale affects Ridge, and whether an absolute-return versus same-date
cross-sectional excess-return training target affects the frozen prediction
contract. Neither question licenses score inversion or a new trading rule.

## Candidate family and budget

Exactly **four configurations total**, including control D0; **three new
candidates**. No D4, D5, quick check, or post-result variation may be added.
The family budget closes after the separately authorized Iteration-1 run; any
later family requires its own preregistration.

| ID | X preprocessing | Ridge training target | Change versus D0 |
| --- | --- | --- | --- |
| D0 | NONE | ABSOLUTE_FORWARD_RETURN | Exact frozen baseline control; no change |
| D1 | TRAIN_ONLY_COLUMN_STANDARDIZATION | ABSOLUTE_FORWARD_RETURN | X scaling only |
| D2 | NONE | CROSS_SECTIONAL_EXCESS_FORWARD_RETURN | Training target only |
| D3 | TRAIN_ONLY_COLUMN_STANDARDIZATION | CROSS_SECTIONAL_EXCESS_FORWARD_RETURN | Both declared changes |

All four use higher predicted score as better, descending ranking with sector
code ascending to break exact ties. Top5 is the highest five **fused** scores.
D2/D3 predictions represent predicted cross-sectional excess return; D0/D1
predictions represent predicted absolute return. No score is negated.

## Exact transformations and anti-leakage rules

For every signal date × horizon independently, D1/D3 compute each feature's
arithmetic mean and **population** standard deviation (`ddof=0`) from that
window's legally selected `X_train` only. Apply `(X−training_mean)/training_std`
to both `X_train` and `X_predict`. Never refit or adjust the scaler on the
signal-date prediction cross-section, all dates globally, later prices,
Validation, or Final OOS. If a training column has zero standard deviation,
the scaled column is exactly zero for both matrices, regardless of the
prediction value. Each future candidate run must record `scaler_training_rows`,
all 19 training means/stds, and `zero_std_features` (full structured values or
their verifiable hashes). No other feature scaling, clipping, or selection is
allowed.

D2/D3 first form the unchanged raw label
`raw_y(t,s,h) = close[t+h,s]/close[t,s] − 1`. At each **training feature date**
and horizon, compute the arithmetic mean only over sectors whose rows were
already admitted to that date/horizon's legal training sample and whose raw
labels are realized. Then set
`y_excess(t,s,h) = raw_y(t,s,h) − mean_admissible_raw_y(t,h)`.
There is no cross-date/global demeaning, prediction-date universe substitution,
or sealed-phase universe reference. With one legal sector its excess target is
zero; with none there is no training row. The mean excess target within every
nonempty training-date group must be zero to floating tolerance. Every feature
date and label endpoint entering training must be no later than its signal
date. The six-calendar-month window remains anchored to the per-horizon label
cutoff, not to the signal date.

Only the **training** target changes for D2/D3. Evaluation continues to use
the original realized **absolute** forward-return label and the existing
frozen 15-metric prediction contract. No new candidate-performance metric or
synthetic return series is authorized.

## Frozen common configuration

- Universe `U0_FIXED_124`, exactly 124 sectors, fixed classification admission,
  frozen snapshot and Development ordinals E001–E100.
- Ordered 19 factors: `d5,d10,d20,d60,d120,p5,p10,p20,p60,p120,align,v5,v20,vc,rev5,rev10,dd20,dd60,rsi`;
  `rsi` is RSI14. No factor sign or definition changes.
- Existing NumPyRidge implementation, alpha `0.01`; horizons `10,40,120`
  trading sessions; fusion weights `0.25,0.50,0.25`; TopK `5`.
- Six calendar months of training per horizon from its label cutoff; minimum
  30 valid training dates. Fixed original missing-data and SOURCE_INVALID
  policies; no fill, replacement, future-aware universe shrink, or sample
  weighting. RSRS, macro, and flow remain outside training.
- Original `split_policy_hash =
  3b6b2d754211169039439c8b377fd9eb26d5cb5db0f80d62cffc1d19c81a7038`
  and `prediction_config_hash =
  64d5fabe6f194f416c6576d4da9cd5e2fb2ad1e699e2c074047960addaa0ed8c`
  remain unchanged. The Iteration-1 hash is a **new** identity, not an alias
  for either baseline hash.

## Evaluation, comparison, and promotion

The only allowed per-date metrics remain IC, RankIC, Top5 forward sector
return, Universe forward sector return, and Top5-minus-Universe, each at
10/40/120 sessions: 15 metrics total. IC uses the corresponding horizon
prediction. Top5 uses the fused score; every evaluation label is the original
absolute forward return. Multi-date means use the existing equal-date
aggregation. Missing horizon means make the weighted comparison unavailable
and the candidate ineligible; they are not replaced with zero.

Predeclared **primary** comparison:

`Weighted_RankIC = 0.25×mean(RankIC_10) + 0.50×mean(RankIC_40) + 0.25×mean(RankIC_120)`.

Predeclared **secondary tie-break**:

`Weighted_Spread = 0.25×mean(Top5_minus_universe_10) + 0.50×mean(Top5_minus_universe_40) + 0.25×mean(Top5_minus_universe_120)`.

No best horizon/date, maximum return, 120-day outlier, or visual preference
may select a candidate. An exact tie on both weighted measures does not force
an arbitrary winner.

Promotion eligibility requires **`Weighted_RankIC > 0 AND Weighted_Spread > 0`**.
Only then may a candidate be labeled
`DEVELOPMENT_CANDIDATE_FOR_FURTHER_REVIEW`. If none satisfy both, the result
is `NO_ITERATION1_CANDIDATE_PROMOTED`; do not advance the least-bad candidate.
Eligibility leads only to a separately authorized Development robustness
review, **not** automatic Validation admission, validated alpha, or trading.

## Seals, prohibitions, and execution gate

This preregistration itself runs **no** candidate performance. Any future
runner must check the exact committed Iteration-1 hash, candidate ID, and
phase/ordinal guards before doing work. Development E001–E100 is the only
potential future evaluation set. Purge 1 E101–E220 cannot emit metrics;
Validation E221–E280 is **SEALED**; Purge 2 E281–E400 cannot emit metrics;
Final OOS E401–E460 is **SEALED**. Opening either sealed phase needs a
separate later protocol and explicit authorization.

Forbidden in this family: inverse score, Bottom5, long-short, new/removed/
re-signed factors, alpha or model search, alternate horizons/fusion/TopK/
universe/window, recency or sample weights, winsorization, clipping, PCA,
feature selection, synthetic portfolio, transaction costs, ETF mapping,
Sharpe, CAGR, drawdown, win rate, turnover, or portfolio-return calculations.

The machine-readable payload is generated by
`research.development_iteration1_protocol.development_iteration1_payload()`.
Its hash uses the repository's `canonical_hash`: UTF-8 JSON with sorted keys,
compact separators, non-ASCII preserved, and NaN disallowed, then SHA-256.
It includes candidate IDs/transforms, all common frozen settings, both
comparison formulas, the strict promotion rule, and phase guards. The
committed hash constant and tests must hard-fail on semantic mutation. Pure
transformation tests use synthetic arrays only; this document creates no
candidate-performance runner and grants no permission to run D1–D3.
