# SHENWAN ALPHA STABILITY & REGIME AUDIT V1 REPORT

## 1. STALE TEST FIX

The pre-existing V2 test treated *absence of formal V2 directories in the current filesystem* as a permanent preregistration invariant. That was obsolete after the lawful preregistration (`b836f27e33987ea3d987b8683a38acc442cb2cdd`) and formal result (`8803f618e4a7a5ea5c65d550ecf71063182782e6`) commits. It was not a corrupt result or research failure. The fix retains the real preregistration-time result-leak guard, tests it against synthetic empty/leaking/unrelated roots, and separately checks historical Git ancestry, frozen-file immutability and discovered V2 artifact hashes/provenance. No result was removed, changed, skipped or marked xfail. Changed: `research/factor_set_v2_preregistration_guard.py` and `tests/test_factor_set_v2_protocol.py`. Fix commit: `89b0f78e36deb5cc4d2981e5199773432e4fec23`. V2-targeted tests were 33 passed; after that isolated fix, the offline baseline was 551 passed, 2 skipped, 17 deselected, 0 failed.

## 2. RESEARCH STATE

This is **POST-V2 DEVELOPMENT DIAGNOSTIC RESEARCH**, not a backtest, strategy result, factor promotion or investable outcome. The frozen V2 candidates were not advanced. The study asks whether relationships learned on legal historical windows transfer to future Development cross-sections, and how existing C0/V2 score decompositions differ. It does not create a fifth scheme.

## 3. SOURCE EVIDENCE

Inputs were the frozen 19-factor `SWSectorRotationCore`, `NumPyRidge`, the local Shenwan sector-index snapshot, the split policy, the prior Iteration-1 D0 identity artifact, Factor Alpha Audit V1 (including raw-factor Spearman), and V2 formal run `factor_set_v2_20260925_090958_520718_utc`. The V2 predictions, training diagnostics and model per-date metrics were checked against V2 metadata SHA-256 before use; the cited prior Factor Audit raw-correlation CSV also matched its metadata SHA-256. Source V2 protocol hash: `3fbba8e5b41c0b5b839dab2788f1e000b9add95406bb14cbaf4c13f31664b4f4`. No new online data, dependencies, Docker image or strategy core changes were used.

## 4. PREREGISTRATION

Human protocol: `docs/research/shenwan_alpha_stability_regime_audit_v1.md`; exact machine config: `research/configs/alpha_stability_regime_audit_v1.json`; guard/hash implementation: `research/alpha_stability_regime_audit_v1_protocol.py`. Frozen canonical payload SHA-256: `7bdf79df7c95134cdbdedb04ce825614c35a2bc72b4f757dd09ecf5e588fb4c1`. Pre-result commit: `111cb8d21bcd1ba053cbf06691c6dc5851a17ae2`. No formal Alpha result existed when that commit was made. The first execution and its immediate repeat both used this clean HEAD and passed the pre-run gate.

## 5. SAMPLE

Only Development E001–E100, 2025-04-02 through 2025-08-26, fixed U0 of 124 sector indexes, frozen 19 factors, horizons 10/40/120 project trading sessions, and existing C0/V2_A/V2_B/V2_D schemes. B1–B4 are fixed ordinal quarters of 25 dates; no post-hoc market-regime definition is used. Labels end no later than the Development E100 120-session Purge-1 endpoint (2026-03-02). Validation and Final OOS remained **SEALED**. Snapshot ID: `872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`; split hash: `3b6b2d754211169039439c8b377fd9eb26d5cb5db0f80d62cffc1d19c81a7038`.

## 6. TRAINING WINDOW IDENTITY

All E001–E100 windows were checked against the V2 C0 training diagnostics: six calendar months, frozen cutoff, exact labelled-date intersection, first/last origin, valid-day count and 124-sector observation count. The E001/E025/E050/E075/E100 × three-horizon exact date-set checks against the core all passed (15 cases, zero date differences). Training labels were independently required to be realized by the signal date; no future factor bar entered a training panel.

## 7. FACTOR IDENTITY

E001/E050/E100 × 19 factors × first 10 sector codes: 570 comparisons to an independent frozen feature recomputation, all passed. Maximum absolute difference `1.60e-14`, tolerance `1e-9`; frozen column order matched.

## 8. TARGET IDENTITY

E001/E050/E100 × 10/40/120 × first 10 sector codes: 90 comparisons, all passed against direct `close[t+h]/close[t]-1` arithmetic and the hash-locked D0 control artifact. Maximum direct difference `0`; maximum D0 difference `1.11e-16`, tolerance `1e-12`. Endpoints used the common project calendar and were not shifted or filled.

## 9. COEFFICIENT IDENTITY

The existing raw-X, same-date cross-sectionally de-meaned target and `NumPyRidge(alpha=0.01, fit_intercept=True)` were replayed for *all* 100 × 3 × 4 scheme/horizon cases, exceeding the required three-date sample. All 148,800 sector prediction comparisons matched formal V2 scores; maximum absolute difference `2.02e-16` versus `1e-10` tolerance. This is a model-identity replay, not a new candidate fit or parameter search.

## 10. CONTRIBUTION IDENTITY

For every scheme/date/horizon/sector, the sum of `beta_j * (x_ij - cross_section_mean(x_j))` equalled the formal prediction minus its sector mean. All 148,800 comparisons passed; maximum difference `1.87e-16` versus `1e-10` tolerance. The per-date factor absolute shares sum to one when the denominator is positive.

## 11. FACTOR TRANSFER SUMMARY

`factor_transfer_daily.csv` contains 5,700 factor/date/horizon rows, with legal-window train IC/RankIC and realized Development evaluation IC/RankIC. `factor_transfer_summary.csv` has all 57 factor/horizon summaries. A useful pre-specified case is v20:

| Horizon | Mean train RankIC | Mean future RankIC | Transfer Pearson | Raw sign agreement | Hard flips |
|---:|---:|---:|---:|---:|---:|
| 10 | -0.0093 | +0.0713 | +0.0141 | 48% | 28/100 |
| 40 | -0.0453 | +0.1867 | +0.1312 | 20% | 77/100 |
| 120 | +0.1370 | +0.2164 | +0.2107 | 84% | 7/100 |

The positive contemporaneous 40-day v20 RankIC is real within this Development sample, but the legal *past* training relationship commonly has the opposite sign. A positive future marginal IC cannot retrospectively authorize flipping a learned sign.

## 12. TRANSITION MATRICES

Complete 3×3 POSITIVE/NEUTRAL/NEGATIVE matrices are in `factor_transfer_transition.csv` (513 cells). For v20 at 40 days, NEGATIVE-train → POSITIVE-future occurred 76/100 dates; POSITIVE-train → NEGATIVE-future occurred once. The opposite-direction 120-day cell had only 2 dates, and POSITIVE → POSITIVE had 76. Direction means RankIC `>+0.02`, `<-0.02`, or inclusive neutral band; no after-result threshold change was made.

## 13. RANKIC AUTOCORRELATION

All 19 × 3 × four registered lags are in `factor_rankic_autocorrelation.csv`. v20 lag-1 autocorrelation was 0.763/0.705/0.919 at 10/40/120 days; lag-5 was 0.165/0.014/0.694. Forward labels overlap, especially at 120 sessions: **NOT INDEPENDENT OBSERVATIONS; DESCRIPTIVE ONLY**. These figures are not p-values or evidence of persistence outside this window.

## 14. BLOCK TRANSFER

The fixed B1–B4 table is `factor_block_transfer.csv` (228 rows). v20 40-day hard-flip rates were 20%/88%/100%/100%; its future marginal RankIC remained positive in each block (0.202/0.138/0.238/0.169). Across the *fixed 19 factors*, mean hard-flip rates at 40 days were approximately 29%/32%/81%/80%. This temporal concentration is descriptive and was not used to create a market-regime classifier.

## 15. V20 CASE STUDY

V2_A is v20-only. At 40 days its beta was negative on 81% of dates, had only one adjacent sign change, agreed with the past train RankIC sign on 99%, but agreed with realized future RankIC on only 21%; beta-to-future hard flip rate was 78%. Thus a stable coefficient can stably express the *wrong* Development-era direction when historical and future marginal relationships invert. V2_A formal 40-day model RankIC was -0.0963 despite v20's +0.1867 standalone future RankIC. At 120 days beta was positive on 90%, future sign agreement 81%, hard flip 15%, and V2_A model RankIC +0.1509. This is a temporal-transfer diagnosis, not proof of a causal volatility mechanism.

## 16. COEFFICIENT STABILITY

`coefficient_daily.csv` contains 8,400 beta rows, and `coefficient_stability_summary.csv` has 84 scheme/horizon/factor summaries: positive/negative/exact-zero shares, mean/median/population std/min/max, adjacent sign changes and persistence. C0's mean factor sign persistence was 0.977 at 40 days and 0.980 at 120 days; V2_A v20 was 0.990 at both. Consequently the 40-day result reversal is **not** explained by wholesale beta sign oscillation. `beta * population_std(legal stacked training X)` is separately saved as `scale_adjusted_beta`, **DIAGNOSTIC_ONLY**, with no training standardization.

## 17. BETA ALIGNMENT

`coefficient_alignment_summary.csv` separates beta-vs-past and beta-vs-future comparisons. At 40 days, v20 future sign agreement was C0 73%, V2_A 21%, V2_B 28%, V2_D 81%; C0's v20 past sign agreement was 43% versus V2_A's 99%. These differences reflect *conditional* Ridge coefficients, not a superior standalone v20 factor. In the 120-day fits, the corresponding future sign agreements were 91%/81%/79%/91%. Beta-to-future hard flips follow the registered non-neutral RankIC-class rule, without applying ±0.02 to beta magnitude.

## 18. CONTRIBUTION STRUCTURE

`contribution_daily_summary.csv` and `contribution_factor_summary.csv` distinguish coefficient size from actual centered score contribution. At 40 days, mean v20 absolute share was C0 2.26%, V2_A 100%, V2_B 61.65%, V2_D 8.72%. C0's largest shares were d20 20.82%, rsi 9.60% and dd60 8.91%; at 120 days they were d120 17.93%, d20 12.27% and d60 11.25%. Shares are *absolute* score decomposition, not signed benefit or causal alpha attribution.

## 19. CANCELLATION

Mean per-sector centered-contribution cancellation at 40 days was C0 0.835, V2_A effectively zero (`7.37e-9`), V2_B 0.115 and V2_D 0.637; at 120 days C0 0.853, V2_A effectively zero, V2_B 0.158 and V2_D 0.669. The registered `1e-12` denominator stabilizer gives tiny nonzero single-factor values. C0's higher cancellation coexists with both positive 120-day and unstable 40-day results, so it is **not** an ex-post performance explanation by itself. ALL/B1–B4 statistics are in `contribution_block_summary.csv`.

## 20. DIVERSIFICATION

At 40 days mean per-date `std(total centered score)/sum factor std` was C0 0.157, V2_A ~1, V2_B 0.919, V2_D 0.365; at 120 days it was 0.132/~1/0.864/0.306. This describes covariance/cancellation of score components, not trade diversification or investable risk. For C0 at 40 days the B1–B4 ratios were 0.158/0.120/0.133/0.216: B4's poor model RankIC is not explained by unusually low score dispersion.

## 21. CONTRIBUTION CORRELATION

Full daily-mean cross-sectional Spearman matrices are in `contribution_correlation.csv` (1,203 rows). The prior Factor Audit V1 *raw-feature* v5–v20 mean correlation was +0.630. Their 40-day *centered contributions* were -0.182 in C0 and +0.355 in V2_B, because fitted conditional beta signs/scales change the score decomposition. Raw correlation, marginal IC, conditional beta and realized contribution are different objects; none alone identifies a causal driver.

## 22. C0 VS V2 DIAGNOSIS

The **existing** V2 formal weighted RankIC/weighted spread were C0 +0.0881/+0.0372, V2_A +0.0056/-0.0142, V2_B +0.0177/-0.0079, V2_D +0.0373/-0.0099. C0 did not win every horizon (V2_A/B had higher 10-day mean RankIC), but it had the strongest pre-existing weighted Development diagnostics. The V2_A/B 40-day loss is consistent with dominant v20 exposure trained with the opposite sign to its future marginal relationship. C0 assigned v20 only 2.26% mean absolute share at 40 days, and its conditional v20 beta more often agreed with future sign. V2_D changed that exposure and reached +0.0103 at 40 days, but remained below C0's +0.0497 and had negative late-block RankIC. This is a coherent *within-sample association*, not proof that 19 factors or cancellation cause superior generalization.

## 23. 40D VS 120D

Formal C0 40-day mean RankIC by B1–B4 was +0.240/+0.262/-0.118/-0.185; C0 120-day was +0.273/+0.202/+0.253/+0.183. The mean 19-factor train→future Pearson transfer was -0.304 at 40 days versus +0.506 at 120; mean factor hard-flip rates were 55.4% versus 26.9%. C0 beta sign persistence was similarly high (97.7% versus 98.0%), while its mean cancellation (0.835 versus 0.853) and diversification ratio (0.157 versus 0.132) do not by themselves account for the model divergence. The late 40-day blocks, particularly B3/B4, coincide with frequent factor-direction flips; the 120-day relationship and model ranks were more consistently positive. Overlapping long labels, one fixed sample and post-V2 selection prevent inference of an external regime or a durable horizon advantage. No horizon, fusion weight or alpha was changed.

## 24. PRIMARY MODEL DIAGNOSIS

The strongest observed failure mode is **time-local sign transfer**, especially 40-day v20 and the B3/B4 40-day factor panel: legal historical relationships and stable fitted betas did not reliably match realized future cross-sectional directions. The 120-day C0 score was positive in each fixed block, but still contains factor-level disagreements and cannot be called validated alpha. Conditional coefficients and contribution correlations show why neither v20's strong contemporaneous IC nor a simple “more factors is better” explanation is sufficient.

## 25. NEXT_RESEARCH_GATE

**HORIZON_SPECIFIC_HYPOTHESIS_READY**. This means only that a human may design a *new, separately preregistered* research hypothesis about horizon-dependent sign transfer and late-block stability. It is not permission to launch V3, flip signs, select factors, tune 10/40/120, alter fusion/TopK, or open Validation/OOS. No scheme is promoted.

## 26. ARTIFACTS

First run: `reports/research/shenwan_sector_index/alpha_stability_regime_audit_20260925_103645_877103_utc/`. Immediate repeat: `reports/research/shenwan_sector_index/alpha_stability_regime_audit_20260925_104205_090058_utc/`. Each has `metadata.json`, 14 registered CSV tables, `audit_summary.json`, and `integrity.json` (17 files total). The additional `contribution_sector_daily.csv` preserves 148,800 per-sector diagnostic rows for independent cancellation checks. The large outputs remain under ignored `reports/`; this tracked report identifies their exact paths and content hashes are in each metadata file.

## 27. DETERMINISM

The repeat's `determinismRepeatOf` points to the first run. All **16 non-metadata** artifact SHA-256 values are identical; separate independent file-hash checks found zero metadata/content mismatches in either run. Metadata differs only in run identity/time and repeat pointer. This proves repeatability for the frozen environment/data/code, not external reproducibility.

## 28. METRIC INTEGRITY

Both runs independently recomputed selected transfer, sign agreement, hard flips, 3×3 transitions, beta persistence, contribution shares, cancellation and block aggregates from persisted daily CSVs: `PASS`. There were 4,191 comparisons; largest absolute difference `1.33e-15`, tolerance `1e-12`. All identity gates also passed. No fabricated missing value was replaced with zero.

## 29. TESTS

Before preregistration: targeted Alpha tests 19 passed; full offline suite **570 passed, 2 skipped, 17 deselected, 0 failed**. After both formal runs and this report: targeted Alpha tests **19 passed**; full offline suite **570 passed, 2 skipped, 17 deselected, 0 failed**, with two pre-existing runtime warnings from legacy mapping/target tests. No test was deleted, skipped or weakened to force a pass.

## 30. SELECTION BIAS

**POST-V2 DEVELOPMENT DIAGNOSTIC RESEARCH. NOT INDEPENDENT VALIDATION. NOT OOS.** The questions and comparisons were designed after viewing Iteration-1, Factor Audit V1 and V2 Development results. The 100 adjacent signals and forward horizons overlap substantially; no p-values, independent-sample claims or generalization probabilities are reported. `horizon_stability_summary.csv` repeats its *all-19-factor reference* transfer means across schemes; it is not a scheme-specific factor-transfer statistic. Scheme comparisons above use factor-level transfer tables plus scheme-specific beta/contribution tables. This interpretive caveat is non-blocking but must accompany any downstream use of that convenience table.

## 31. RESEARCH COMPLIANCE

No Validation, Final OOS, Portfolio, ETF, transaction-cost model, executable backtest, live trading, new signal, Ridge hyperparameter change, factor sign change, or core-algorithm edit. Fixed historical classification remains `FIXED_CLASSIFICATION_RESEARCH` with `strictPit=false`; this is not a point-in-time tradability claim. No V2 formal artifact or preregistration file was modified. Reports are research diagnostics, not strategy performance or account returns.

## 32. ENVIRONMENT_CHANGED

`false`. Existing Docker image `sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5`; no build, pull, install or dependency adjustment.

## 33. COMMITS

- Lifecycle test fix: `89b0f78e36deb5cc4d2981e5199773432e4fec23`.
- Alpha audit preregistration: `111cb8d21bcd1ba053cbf06691c6dc5851a17ae2`.
- Alpha audit result: the Git commit that introduces **this report** (`git log -1 --format=%H -- docs/research/shenwan_alpha_stability_regime_audit_v1_report.md`); its full SHA is given in the final handoff, avoiding a self-referential commit hash inside its own content.

## 34. NEXT AUTHORIZED ACTION

**DESIGN NEXT RESEARCH HYPOTHESIS AFTER HUMAN REVIEW**. Stop here; no automatic next phase.

## 35. FINAL STATUS

**ALPHA STABILITY & REGIME AUDIT V1 COMPLETE WITH NON-BLOCKING WARNINGS**. The warnings are the unavoidable post-V2 Development selection bias, overlapping labels/fixed non-PIT classification, and the explicitly scoped all-factor convenience fields in the horizon summary. They do not invalidate the identity, determinism or metric-integrity gates.
