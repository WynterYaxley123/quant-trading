# Horizon-specific Alpha Hypothesis V1 — selection trace (preregistration only)

This is a design trace over previously published Development diagnostics, **not** a new model or performance result. Exact numeric values and tie resolution use the source CSV bytes, not the six-decimal display below. Source SHA-256:

- `alpha_stability_regime_audit_20260925_103645_877103_utc/factor_transfer_summary.csv`: `ae6f052926fbc2bdf128d89082dcd0f3709ed6af6adb37c672cb6c5692aa69c4`
- `factor_alpha_audit_20260925_071934_967164_utc/factor_correlation_spearman.csv`: `2bd2090af103b37f9db26d9114f04679e55723a4cb21de1aae38ee9b10c595b7`

Each row is `rank | factor | family | hardFlipRate | rawSignAgreementRate | transferSpearman | zero-based pipeline index`. Family abbreviations: TM = TREND_MOMENTUM, RP = RANGE_POSITION, OA = OSCILLATOR_ALIGNMENT, VOL = VOLATILITY, REV = REVERSAL, DD = DRAWDOWN. Rank is lexicographic: flip ascending, agreement descending, Spearman descending, pipeline index ascending. No return or future RankIC magnitude is a key. All 57 source rows have 100 valid signal dates.

## H10: all 19 rank inputs

| Rank | Factor | Family | Flip | Agreement | Transfer ρ | Index |
|---:|---|---|---:|---:|---:|---:|
| 1 | p5 | RP | 0.000000 | 0.490000 | +0.080492 | 5 |
| 2 | d10 | TM | 0.000000 | 0.470000 | -0.050321 | 1 |
| 3 | rev5 | REV | 0.030000 | 0.450000 | -0.120492 | 14 |
| 4 | d5 | TM | 0.040000 | 0.460000 | -0.099706 | 0 |
| 5 | vc | VOL | 0.140000 | 0.520000 | -0.257162 | 13 |
| 6 | p10 | RP | 0.160000 | 0.590000 | -0.067063 | 6 |
| 7 | rev10 | REV | 0.170000 | 0.430000 | -0.078680 | 15 |
| 8 | dd20 | DD | 0.200000 | 0.420000 | -0.286877 | 16 |
| 9 | align | OA | 0.220000 | 0.280000 | -0.423006 | 10 |
| 10 | p20 | RP | 0.230000 | 0.270000 | -0.446685 | 7 |
| 11 | v20 | VOL | 0.280000 | 0.480000 | +0.014527 | 12 |
| 12 | rsi | OA | 0.310000 | 0.330000 | -0.502714 | 18 |
| 13 | v5 | VOL | 0.350000 | 0.420000 | +0.042280 | 11 |
| 14 | d120 | TM | 0.420000 | 0.550000 | -0.383986 | 4 |
| 15 | d20 | TM | 0.450000 | 0.390000 | -0.301494 | 2 |
| 16 | p120 | RP | 0.480000 | 0.460000 | -0.451209 | 9 |
| 17 | dd60 | DD | 0.520000 | 0.430000 | -0.150339 | 17 |
| 18 | d60 | TM | 0.560000 | 0.400000 | -0.129505 | 3 |
| 19 | p60 | RP | 0.570000 | 0.410000 | -0.229307 | 8 |

`H10_S = [p5]`. The existing transition table has p5's legal training direction NEUTRAL on 100/100 dates, so its zero hard-flip rate does not establish directional persistence. Compact family admission, fixed family order:

| Family | Consideration and outcome |
|---|---|
| TM | d10 selected |
| RP | p5 selected |
| OA | align selected |
| VOL | vc selected |
| REV | rev5 rejected: ρ(rev5,d10)=-0.8911830055074745; rev10 rejected: ρ(rev10,d10)=-0.8009117230527144; family omitted |
| DD | dd20 selected |

Selection order `[d10,p5,align,vc,dd20]`; pipeline order `H10_C = [d10,p5,align,vc,dd20]`.

## H40: all 19 rank inputs

| Rank | Factor | Family | Flip | Agreement | Transfer ρ | Index |
|---:|---|---|---:|---:|---:|---:|
| 1 | vc | VOL | 0.000000 | 0.590000 | +0.277096 | 13 |
| 2 | dd60 | DD | 0.440000 | 0.540000 | -0.691473 | 17 |
| 3 | d120 | TM | 0.450000 | 0.540000 | -0.820618 | 4 |
| 4 | p120 | RP | 0.480000 | 0.490000 | -0.688509 | 9 |
| 5 | p60 | RP | 0.480000 | 0.490000 | -0.769313 | 8 |
| 6 | d60 | TM | 0.530000 | 0.450000 | -0.828599 | 3 |
| 7 | d5 | TM | 0.530000 | 0.410000 | +0.099598 | 0 |
| 8 | dd20 | DD | 0.540000 | 0.450000 | -0.145143 | 16 |
| 9 | rev5 | REV | 0.570000 | 0.370000 | +0.002268 | 14 |
| 10 | p5 | RP | 0.580000 | 0.400000 | +0.208341 | 5 |
| 11 | p20 | RP | 0.590000 | 0.380000 | -0.460294 | 7 |
| 12 | align | OA | 0.590000 | 0.360000 | -0.661542 | 10 |
| 13 | p10 | RP | 0.630000 | 0.350000 | +0.012457 | 6 |
| 14 | v5 | VOL | 0.630000 | 0.320000 | +0.032859 | 11 |
| 15 | d20 | TM | 0.660000 | 0.300000 | -0.627507 | 2 |
| 16 | rsi | OA | 0.660000 | 0.300000 | -0.705839 | 18 |
| 17 | d10 | TM | 0.670000 | 0.320000 | -0.102754 | 1 |
| 18 | rev10 | REV | 0.730000 | 0.240000 | -0.418878 | 15 |
| 19 | v20 | VOL | 0.770000 | 0.200000 | +0.109019 | 12 |

`H40_S = [vc]`. Compact family admission:

| Family | Consideration and outcome |
|---|---|
| TM | d120 selected |
| RP | p120 rejected: ρ(p120,d120)=+0.8442580751974756; p60 selected |
| OA | align selected |
| VOL | vc selected |
| REV | rev5 selected |
| DD | dd60 rejected: ρ(dd60,p60)=+0.9045865020932743; dd20 selected |

Selection and pipeline order `H40_C = [d120,p60,align,vc,rev5,dd20]`.

**H40 EVIDENCE QUALITY WARNING / NO_STRONG_STABILITY_EVIDENCE:** `vc` has zero hard flips but its legal training direction was NEUTRAL on 100/100 dates; 18 of 19 factors have flip rates at least 0.44, and five of six compact representatives have rates 0.45–0.59. This is descriptive, not a selection exclusion or sign inversion. The future formal test may fail.

## H120: all 19 rank inputs

| Rank | Factor | Family | Flip | Agreement | Transfer ρ | Index |
|---:|---|---|---:|---:|---:|---:|
| 1 | vc | VOL | 0.000000 | 0.540000 | +0.096694 | 13 |
| 2 | p20 | RP | 0.010000 | 0.820000 | +0.535782 | 7 |
| 3 | p60 | RP | 0.060000 | 0.840000 | +0.841176 | 8 |
| 4 | rsi | OA | 0.060000 | 0.600000 | +0.364080 | 18 |
| 5 | v20 | VOL | 0.070000 | 0.840000 | +0.178230 | 12 |
| 6 | p10 | RP | 0.130000 | 0.670000 | +0.239316 | 6 |
| 7 | p5 | RP | 0.140000 | 0.550000 | +0.164524 | 5 |
| 8 | v5 | VOL | 0.160000 | 0.740000 | -0.114275 | 11 |
| 9 | align | OA | 0.310000 | 0.620000 | +0.765845 | 10 |
| 10 | dd20 | DD | 0.320000 | 0.610000 | +0.606781 | 16 |
| 11 | dd60 | DD | 0.380000 | 0.530000 | +0.870195 | 17 |
| 12 | d5 | TM | 0.380000 | 0.360000 | +0.136790 | 0 |
| 13 | p120 | RP | 0.390000 | 0.440000 | +0.838680 | 9 |
| 14 | d20 | TM | 0.400000 | 0.310000 | +0.517139 | 2 |
| 15 | d10 | TM | 0.400000 | 0.300000 | +0.247537 | 1 |
| 16 | rev10 | REV | 0.420000 | 0.290000 | +0.352595 | 15 |
| 17 | d120 | TM | 0.480000 | 0.500000 | +0.904026 | 4 |
| 18 | rev5 | REV | 0.490000 | 0.340000 | +0.182850 | 14 |
| 19 | d60 | TM | 0.510000 | 0.480000 | +0.903510 | 3 |

`H120_S = [vc]`. Its existing training direction was NEUTRAL on 99/100 dates: zero hard flips are not, by themselves, evidence of a stable non-neutral relationship. Compact family admission:

| Family | Consideration and outcome |
|---|---|
| TM | d5 selected |
| RP | p20 selected |
| OA | rsi selected |
| VOL | vc selected |
| REV | rev10 selected |
| DD | dd20 rejected: ρ(dd20,p20)=+0.8828444948312163; dd60 selected |

Selection order `[d5,p20,rsi,vc,rev10,dd60]`; pipeline order `H120_C = [d5,p20,vc,rev10,dd60,rsi]`. Factor order is frozen in pipeline order for model input.
