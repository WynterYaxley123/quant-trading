# SHENWAN FACTOR ALPHA AUDIT V1 REPORT

Status: **FACTOR ALPHA AUDIT V1 COMPLETE WITH NON-BLOCKING WARNINGS**.
Development-only diagnostic research. Not validated alpha, not tradable
performance, not trading authorization.

## 1. RESEARCH STATE

- Branch: `experiment/sw-sector-index-research-baseline`
- HEAD before this task: `9c16c787eb3d638ee8683f2644ad01c0cfa21e39`
- HEAD after (preregistration commit): `786b8f11281a763e23fee969e1f1c37ece9e29c0`
- Audit result commit: the commit introducing this report
  (`research: run factor alpha audit v1`); its SHA is recorded in the
  accompanying research summary. All audit runs themselves executed at
  `gitCommit = 786b8f11281a763e23fee969e1f1c37ece9e29c0`.
- Working tree: clean at start, clean at preregistration, clean at both runs
  (the audit runner's pre-run gate enforces this).

## 2. ITERATION-1 ARTIFACT

- Formal run: `reports/research/shenwan_sector_index/iteration1_20260924_163607_787266_utc`
  (determinism repeat of `iteration1_20260924_163106_040404_utc`;
  `determinism = PASS_CONTENT_SHA256_IDENTICAL`)
- Iteration-1 git commit chain: preregistration `dc5626ac33da6953ae908eb0d1a0c01769474a7f`,
  run `ea26a8e23fd6cfa54eedc9e7cb8786d978c2ccc7`, fixes `67b9342`, `9c16c78`
- Iteration-1 protocol hash:
  `f2080f56a3f4a77ff983d5b9cc14c0f1427f4d2c84fb1d9fc89b9a2a3cb12125`
  (verified from artifact metadata, matches preregistration)
- Sector snapshot: `872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`
- Split policy hash: `3b6b2d754211169039439c8b377fd9eb26d5cb5db0f80d62cffc1d19c81a7038`
- D0 control provenance verified: all five frozen D0 artifact SHA-256 digests
  match the run metadata before any reuse.

## 3. ITERATION-1 D0-D3 RESULTS

Weighted_RankIC = 0.25·mean(RankIC10) + 0.50·mean(RankIC40) +
0.25·mean(RankIC120); Weighted_Spread analogously on
Top5-minus-universe. Independently recomputed from the frozen
`aggregate_metrics.json` files; identical to `candidate_summary.json`
(verified to <1e-15).

| Candidate | Weighted RankIC | Weighted Spread | Promotion (both > 0) |
| --- | --- | --- | --- |
| D0 raw X, absolute target | -0.040459 | -0.013685 | NOT PROMOTED |
| D1 std X, absolute target | -0.041072 | -0.015738 | NOT PROMOTED |
| D2 raw X, excess target | +0.088107 | +0.037216 | **PROMOTED** |
| D3 std X, excess target | +0.087714 | +0.036173 | **PROMOTED** |

Per-candidate detail (mean IC / mean RankIC / mean spread per horizon):

| Candidate | h | mean IC | mean RankIC | mean Top5-Univ |
| --- | --- | --- | --- | --- |
| D0 | 10 | -0.031823 | -0.000130 | -0.001543 |
| D0 | 40 | -0.127140 | -0.068164 | -0.022092 |
| D0 | 120 | -0.010393 | -0.025380 | -0.009011 |
| D1 | 10 | -0.031875 | -0.000012 | -0.001667 |
| D1 | 40 | -0.126727 | -0.068349 | -0.022700 |
| D1 | 120 | -0.012592 | -0.027578 | -0.015884 |
| D2 | 10 | -0.017436 | +0.025446 | +0.005297 |
| D2 | 40 | +0.021682 | +0.049692 | +0.012788 |
| D2 | 120 | +0.239157 | +0.227595 | +0.117993 |
| D3 | 10 | -0.017547 | +0.025495 | +0.004827 |
| D3 | 40 | +0.021782 | +0.049818 | +0.011672 |
| D3 | 120 | +0.237479 | +0.225726 | +0.116520 |

Deltas versus D0 (and D3 versus D2):

| Comparison | ΔWeighted RankIC | ΔWeighted Spread |
| --- | --- | --- |
| D1 - D0 (standardization alone) | -0.000613 | -0.002053 |
| D2 - D0 (target change alone) | +0.128566 | +0.050901 |
| D3 - D0 (both changes) | +0.128174 | +0.049858 |
| D3 - D2 (standardization on top of target) | -0.000392 | -0.001043 |

## 4. ITERATION-1 INTERPRETATION

**Standardization effect:** none measurable, slightly negative in both
target contexts (D1-D0 = -0.0006/-0.0021; D3-D2 = -0.0004/-0.0010). With
alpha=0.01 Ridge on correlated columns, train-only scaling only rebalances
effective per-column shrinkage; in this sample that effect is below noise
and directionally nil. D1/D0 and D3/D2 pairs are essentially coincident.

**Target effect:** the entire D2/D3 improvement comes from the training
target change. The Development sample is a one-directional market window —
universe mean forward returns are +1.96% / +7.41% / +18.60% at 10/40/120
sessions. Training Ridge on absolute forward return makes the model absorb
this dominant common component, leaving the cross-sectional ranking nearly
information-free (D0 weighted RankIC -0.040). Same-date cross-sectional
excess targets remove the common component and the ranking signal appears,
concentrated at 120d (D2 RankIC120 +0.228 vs D0 -0.025).

**Interaction:** none. D3 differs from D2 by less than 0.0004/0.0010 in the
opposite direction of improvement; the two changes are additive-nothing,
not synergistic.

**Where the improvement lives:** almost entirely the 120d horizon
(D2-D0 RankIC120 +0.253 of the +0.129 weighted total). At 10d the D2
ranking is barely positive (+0.025). Candidate ranking: D2 ≈ D3 (both
pass the preregistered conjunction), D0 ≈ D1 fail. Both promoted
candidates owe their promotion to the excess target, not to scaling.

## 5. PREREGISTRATION (Factor Alpha Audit V1)

- Protocol document: `docs/research/shenwan_factor_alpha_audit_v1_protocol.md`
- Protocol code: `research/factor_alpha_audit_v1_protocol.py`
- Protocol hash (canonical payload SHA-256, frozen constant):
  `87e6e9c3ac79f1f41239d8c91080b16fd142343dea470084226e23512286b815`
- Preregistration commit SHA: `786b8f11281a763e23fee969e1f1c37ece9e29c0`
  (`research: preregister factor alpha audit v1` — protocol + audit code +
  tests only; no audit result existed at this commit)
- Confirmation: both audit runs record `gitCommit = 786b8f11...` and run
  timestamps after the commit; the protocol content hash is identical in
  run metadata. Protocol verifiably predated result generation.

## 6. FACTOR AUDIT SAMPLE

- Development eligible IDs: E001-E100 (ordinals 1-100 of the frozen
  Policy C eligible signal calendar; guards reject purge/validation/OOS
  ordinals)
- Signal date range read from split policy: 2025-04-02 to 2025-08-26
  (asserted, not hardcoded)
- Sector universe: U0 fixed 124 Shenwan Level-2 sector indexes
- Horizons: 10 / 40 / 120 trading sessions
- Validity rules: finite factor AND finite label per (date, sector,
  horizon); <30 valid sector pairs marks the date skipped; no imputation,
  no fill, no endpoint shifting; labels realized only within the audited
  label window ending `development_last_120_label_endpoint` (inside
  Purge 1, before E221); Validation and Final OOS never touched.

## 7. FACTOR × HORIZON SUMMARY (19 × 3)

| factor | h | meanIC | meanRankIC | medianRankIC | stdRankIC | Q5-Q1 | monotony | pos/neg/zero | validDates |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d5 | 10 | -0.0015 | -0.0150 | 0.0003 | 0.2314 | 0.0001 | 0.1000 | 50/50/0 | 100 |
| d5 | 40 | 0.0546 | 0.0362 | 0.0534 | 0.2326 | 0.0149 | 0.9000 | 59/41/0 | 100 |
| d5 | 120 | 0.0497 | 0.0449 | 0.1103 | 0.2734 | 0.0318 | 1.0000 | 64/36/0 | 100 |
| d10 | 10 | 0.0054 | -0.0103 | 0.0086 | 0.2239 | 0.0017 | 0.5000 | 53/47/0 | 100 |
| d10 | 40 | 0.0778 | 0.0590 | 0.0962 | 0.2416 | 0.0240 | 0.9000 | 68/32/0 | 100 |
| d10 | 120 | 0.0663 | 0.0593 | 0.1513 | 0.2950 | 0.0375 | 0.9000 | 70/30/0 | 100 |
| d20 | 10 | -0.0126 | -0.0272 | 0.0036 | 0.2530 | 0.0008 | 0.3000 | 51/49/0 | 100 |
| d20 | 40 | 0.0951 | 0.0730 | 0.1286 | 0.2623 | 0.0321 | 1.0000 | 70/30/0 | 100 |
| d20 | 120 | 0.0642 | 0.0641 | 0.2140 | 0.3418 | 0.0448 | 1.0000 | 69/31/0 | 100 |
| d60 | 10 | 0.0329 | 0.0023 | 0.0465 | 0.2802 | 0.0040 | 0.4000 | 60/40/0 | 100 |
| d60 | 40 | 0.0600 | 0.0199 | 0.0516 | 0.2899 | 0.0282 | 1.0000 | 55/45/0 | 100 |
| d60 | 120 | -0.0136 | -0.0046 | 0.0700 | 0.3712 | 0.0053 | 0.8000 | 52/48/0 | 100 |
| d120 | 10 | 0.0001 | -0.0505 | -0.0446 | 0.1913 | -0.0009 | -0.3000 | 45/55/0 | 100 |
| d120 | 40 | 0.0046 | -0.0421 | -0.0660 | 0.2045 | 0.0109 | 0.6000 | 46/54/0 | 100 |
| d120 | 120 | -0.0400 | -0.0096 | -0.0040 | 0.2698 | -0.0091 | 0.2000 | 50/50/0 | 100 |
| p5 | 10 | 0.0036 | 0.0055 | -0.0088 | 0.2198 | 0.0020 | 0.5000 | 49/51/0 | 100 |
| p5 | 40 | 0.0218 | 0.0394 | 0.0576 | 0.2264 | 0.0167 | 0.3000 | 60/40/0 | 100 |
| p5 | 120 | 0.0236 | 0.0455 | 0.0751 | 0.2604 | 0.0286 | 0.7000 | 60/40/0 | 100 |
| p10 | 10 | 0.0173 | 0.0068 | 0.0371 | 0.2282 | 0.0038 | 0.7000 | 59/41/0 | 100 |
| p10 | 40 | 0.0451 | 0.0456 | 0.1000 | 0.2464 | 0.0228 | 0.7000 | 65/35/0 | 100 |
| p10 | 120 | 0.0365 | 0.0445 | 0.1231 | 0.2813 | 0.0268 | 0.7000 | 66/34/0 | 100 |
| p20 | 10 | 0.0090 | -0.0032 | 0.0339 | 0.2485 | 0.0031 | 0.1000 | 55/45/0 | 100 |
| p20 | 40 | 0.0656 | 0.0566 | 0.0722 | 0.2633 | 0.0267 | 0.7000 | 62/38/0 | 100 |
| p20 | 120 | 0.0430 | 0.0339 | 0.1148 | 0.3136 | 0.0190 | 0.1000 | 62/38/0 | 100 |
| p60 | 10 | 0.0206 | 0.0177 | 0.0574 | 0.2619 | 0.0033 | 0.2000 | 59/41/0 | 100 |
| p60 | 40 | 0.0083 | -0.0022 | 0.0128 | 0.2752 | 0.0144 | 0.2000 | 51/49/0 | 100 |
| p60 | 120 | -0.0238 | -0.0178 | 0.0628 | 0.3433 | -0.0130 | -0.4000 | 51/49/0 | 100 |
| p120 | 10 | 0.0151 | -0.0032 | 0.0144 | 0.1498 | 0.0014 | 0.7000 | 54/46/0 | 100 |
| p120 | 40 | 0.0426 | 0.0131 | 0.0085 | 0.1588 | 0.0161 | 0.7000 | 51/49/0 | 100 |
| p120 | 120 | 0.0232 | 0.0372 | 0.0831 | 0.2190 | 0.0066 | 0.4000 | 56/44/0 | 100 |
| align | 10 | 0.0218 | 0.0236 | 0.0387 | 0.1764 | -0.0013 | 0.1000 | 63/37/0 | 100 |
| align | 40 | 0.0574 | 0.0539 | 0.1010 | 0.2192 | 0.0002 | 0.3000 | 64/36/0 | 100 |
| align | 120 | 0.0380 | 0.0436 | 0.1369 | 0.2790 | -0.0252 | -0.3000 | 62/38/0 | 100 |
| v5 | 10 | 0.0137 | 0.0270 | 0.0436 | 0.1813 | 0.0059 | 1.0000 | 61/39/0 | 100 |
| v5 | 40 | 0.1139 | 0.1129 | 0.0970 | 0.1414 | 0.0395 | 1.0000 | 81/19/0 | 100 |
| v5 | 120 | 0.1520 | 0.1503 | 0.1520 | 0.1578 | 0.1253 | 1.0000 | 81/19/0 | 100 |
| v20 | 10 | 0.0771 | 0.0713 | 0.0792 | 0.1833 | 0.0119 | 1.0000 | 67/33/0 | 100 |
| v20 | 40 | 0.1911 | 0.1867 | 0.1822 | 0.1080 | 0.0592 | 1.0000 | 96/4/0 | 100 |
| v20 | 120 | 0.2236 | 0.2164 | 0.2120 | 0.1489 | 0.1782 | 1.0000 | 91/9/0 | 100 |
| vc | 10 | -0.0398 | -0.0345 | -0.0330 | 0.1601 | -0.0026 | -0.9000 | 41/59/0 | 100 |
| vc | 40 | -0.0114 | -0.0188 | -0.0412 | 0.1551 | -0.0008 | -0.4000 | 45/55/0 | 100 |
| vc | 120 | 0.0082 | 0.0019 | -0.0071 | 0.1756 | 0.0026 | 0.3000 | 49/51/0 | 100 |
| rev5 | 10 | -0.0036 | 0.0151 | 0.0057 | 0.2286 | -0.0017 | -0.3000 | 51/49/0 | 100 |
| rev5 | 40 | -0.0676 | -0.0484 | -0.0496 | 0.2333 | -0.0202 | -0.9000 | 37/63/0 | 100 |
| rev5 | 120 | -0.0619 | -0.0540 | -0.1189 | 0.2739 | -0.0340 | -0.9000 | 34/66/0 | 100 |
| rev10 | 10 | -0.0025 | 0.0068 | -0.0322 | 0.2378 | -0.0023 | -0.8000 | 44/56/0 | 100 |
| rev10 | 40 | -0.0885 | -0.0659 | -0.1175 | 0.2495 | -0.0270 | -1.0000 | 24/76/0 | 100 |
| rev10 | 120 | -0.0706 | -0.0640 | -0.1845 | 0.3229 | -0.0417 | -0.7000 | 29/71/0 | 100 |
| dd20 | 10 | 0.0066 | -0.0135 | 0.0380 | 0.2505 | -0.0019 | 0.0000 | 58/42/0 | 100 |
| dd20 | 40 | 0.0175 | 0.0068 | 0.0764 | 0.2479 | 0.0048 | 0.1000 | 55/45/0 | 100 |
| dd20 | 120 | -0.0385 | -0.0232 | 0.0646 | 0.3245 | -0.0465 | -0.9000 | 57/43/0 | 100 |
| dd60 | 10 | 0.0095 | 0.0030 | 0.0324 | 0.2797 | -0.0006 | -0.1000 | 57/43/0 | 100 |
| dd60 | 40 | -0.0286 | -0.0368 | -0.0353 | 0.2623 | -0.0020 | -0.4000 | 46/54/0 | 100 |
| dd60 | 120 | -0.1008 | -0.0823 | -0.0221 | 0.3535 | -0.0656 | -0.9000 | 50/50/0 | 100 |
| rsi | 10 | 0.0009 | -0.0118 | 0.0385 | 0.2359 | 0.0009 | 0.1000 | 57/43/0 | 100 |
| rsi | 40 | 0.0698 | 0.0504 | 0.1113 | 0.2437 | 0.0230 | 0.9000 | 70/30/0 | 100 |
| rsi | 120 | 0.0436 | 0.0354 | 0.1558 | 0.3229 | 0.0184 | 0.7000 | 65/35/0 | 100 |

All t-stats (in the artifacts) are DESCRIPTIVE ONLY and were never used for
selection. Signs are as measured; no direction was flipped.

## 8. STABILITY (4 fixed blocks)

Block mean RankIC (B1=E001-E025, B2=E026-E050, B3=E051-E075,
B4=E076-E100) and same-sign block count versus the full Development mean:

| factor | h | B1 | B2 | B3 | B4 | sameSign |
| --- | --- | --- | --- | --- | --- | --- |
| align | 10 | -0.1428 | 0.0002 | 0.1122 | 0.1249 | 3/4 |
| align | 40 | -0.0492 | -0.1411 | 0.2116 | 0.1944 | 2/4 |
| align | 120 | -0.1764 | -0.1911 | 0.2416 | 0.3001 | 2/4 |
| d10 | 10 | -0.1280 | -0.0230 | 0.0533 | 0.0564 | 2/4 |
| d10 | 40 | -0.0470 | -0.0498 | 0.1956 | 0.1372 | 2/4 |
| d10 | 120 | -0.0921 | -0.0811 | 0.2209 | 0.1893 | 2/4 |
| d120 | 10 | -0.2363 | -0.0965 | -0.0175 | 0.1484 | 3/4 |
| d120 | 40 | -0.2116 | -0.2189 | 0.0628 | 0.1993 | 2/4 |
| d120 | 120 | -0.2684 | -0.2306 | 0.1400 | 0.3206 | 2/4 |
| d20 | 10 | -0.2640 | -0.0826 | 0.1182 | 0.1196 | 2/4 |
| d20 | 40 | -0.1426 | -0.0758 | 0.2988 | 0.2118 | 2/4 |
| d20 | 120 | -0.2630 | -0.0989 | 0.3358 | 0.2824 | 2/4 |
| d5 | 10 | -0.0733 | 0.0031 | -0.0082 | 0.0184 | 2/4 |
| d5 | 40 | -0.0189 | -0.0295 | 0.1015 | 0.0919 | 2/4 |
| d5 | 120 | -0.0198 | -0.0497 | 0.1320 | 0.1169 | 2/4 |
| d60 | 10 | -0.2766 | -0.0309 | 0.1127 | 0.2039 | 2/4 |
| d60 | 40 | -0.2359 | -0.2306 | 0.2390 | 0.3072 | 2/4 |
| d60 | 120 | -0.4261 | -0.2774 | 0.2972 | 0.3879 | 2/4 |
| dd20 | 10 | -0.2663 | 0.0117 | 0.0929 | 0.1075 | 1/4 |
| dd20 | 40 | -0.2026 | -0.0794 | 0.1940 | 0.1152 | 2/4 |
| dd20 | 120 | -0.3952 | -0.0865 | 0.2484 | 0.1407 | 2/4 |
| dd60 | 10 | -0.1982 | -0.0435 | 0.1004 | 0.1534 | 2/4 |
| dd60 | 40 | -0.2138 | -0.2797 | 0.1289 | 0.2175 | 2/4 |
| dd60 | 120 | -0.4775 | -0.3526 | 0.2237 | 0.2773 | 2/4 |
| p10 | 10 | -0.1411 | 0.0174 | 0.0657 | 0.0853 | 3/4 |
| p10 | 40 | -0.0789 | -0.0487 | 0.1740 | 0.1360 | 2/4 |
| p10 | 120 | -0.0959 | -0.0620 | 0.1875 | 0.1485 | 2/4 |
| p120 | 10 | -0.1355 | -0.0375 | 0.0517 | 0.1083 | 2/4 |
| p120 | 40 | -0.0878 | -0.1260 | 0.0755 | 0.1906 | 2/4 |
| p120 | 120 | -0.1463 | -0.1610 | 0.1643 | 0.2919 | 2/4 |
| p20 | 10 | -0.2513 | -0.0313 | 0.1288 | 0.1409 | 2/4 |
| p20 | 40 | -0.1508 | -0.0874 | 0.2764 | 0.1883 | 2/4 |
| p20 | 120 | -0.2915 | -0.0895 | 0.2922 | 0.2244 | 2/4 |
| p5 | 10 | -0.0542 | 0.0040 | 0.0153 | 0.0568 | 3/4 |
| p5 | 40 | -0.0289 | -0.0353 | 0.1096 | 0.1121 | 2/4 |
| p5 | 120 | -0.0030 | -0.0401 | 0.1198 | 0.1051 | 2/4 |
| p60 | 10 | -0.2277 | -0.0286 | 0.1223 | 0.2047 | 2/4 |
| p60 | 40 | -0.2135 | -0.2567 | 0.1970 | 0.2646 | 2/4 |
| p60 | 120 | -0.3755 | -0.2965 | 0.2746 | 0.3260 | 2/4 |
| rev10 | 10 | 0.1745 | 0.0638 | -0.0888 | -0.1221 | 2/4 |
| rev10 | 40 | 0.0960 | 0.0667 | -0.2460 | -0.1803 | 2/4 |
| rev10 | 120 | 0.1591 | 0.0979 | -0.2719 | -0.2413 | 2/4 |
| rev5 | 10 | 0.1122 | 0.0096 | -0.0317 | -0.0295 | 2/4 |
| rev5 | 40 | 0.0223 | 0.0417 | -0.1501 | -0.1075 | 2/4 |
| rev5 | 120 | 0.0379 | 0.0771 | -0.1758 | -0.1552 | 2/4 |
| rsi | 10 | -0.2500 | -0.0549 | 0.1080 | 0.1498 | 2/4 |
| rsi | 40 | -0.1220 | -0.1105 | 0.2333 | 0.2006 | 2/4 |
| rsi | 120 | -0.2494 | -0.1279 | 0.2785 | 0.2405 | 2/4 |
| v20 | 10 | 0.1384 | 0.0233 | 0.0649 | 0.0587 | 4/4 |
| v20 | 40 | 0.2016 | 0.1379 | 0.2381 | 0.1693 | 4/4 |
| v20 | 120 | 0.3720 | 0.1062 | 0.1262 | 0.2613 | 4/4 |
| v5 | 10 | 0.0273 | -0.0359 | 0.0625 | 0.0542 | 3/4 |
| v5 | 40 | 0.1086 | 0.0422 | 0.2136 | 0.0873 | 4/4 |
| v5 | 120 | 0.2060 | 0.0401 | 0.1415 | 0.2137 | 4/4 |
| vc | 10 | -0.0712 | -0.0713 | 0.0003 | 0.0043 | 2/4 |
| vc | 40 | -0.0380 | -0.0497 | 0.0612 | -0.0488 | 3/4 |
| vc | 120 | -0.0543 | -0.0439 | 0.0686 | 0.0374 | 2/4 |

Highlights (diagnostic only, no winner selected): **4/4 same direction** —
v20 at all horizons, v5 at 40/120. **3/4** — v5(10), align(10), d120(10),
p5(10), p10(10), vc(40). **2/4 or worse** — every remaining factor/horizon.
The 2/4 pattern is systematic, not random: trend/position/rsi/drawdown
factors run negative in blocks 1-2 and positive in blocks 3-4, while the
reversal family is the exact mirror. Their full-sample means are averages
of two opposing sub-regimes and must not be read as stable alpha.

## 9. QUANTILE RESULTS

Selected Q1→Q5 aggregate mean forward returns (full table in
`factor_quantile_summary.csv` / `factor_quantile_daily.csv`):

| factor | h | Q1 | Q2 | Q3 | Q4 | Q5 | Q5-Q1 | monotony |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v20 | 10 | 0.0132 | 0.0185 | 0.0205 | 0.0211 | 0.0251 | 0.0119 | 1.0 |
| v20 | 40 | 0.0454 | 0.0592 | 0.0758 | 0.0867 | 0.1046 | 0.0592 | 1.0 |
| v20 | 120 | 0.0994 | 0.1533 | 0.1893 | 0.2142 | 0.2776 | 0.1782 | 1.0 |
| v5 | 120 | 0.1283 | 0.1631 | 0.1851 | 0.2028 | 0.2536 | 0.1253 | 1.0 |
| rev10 | 40 | 0.0892 | 0.0805 | 0.0698 | 0.0683 | 0.0622 | -0.0270 | -1.0 |
| rev10 | 120 | 0.2192 | 0.1914 | 0.1731 | 0.1687 | 0.1775 | -0.0417 | -0.7 |
| d20 | 120 | 0.1673 | 0.1743 | 0.1846 | 0.1931 | 0.2121 | 0.0448 | 1.0 |
| align | 120 | 0.1732 | 0.1997 | 0.2174 | 0.1904 | 0.1480 | -0.0252 | -0.3 |
| dd60 | 120 | 0.2053 | 0.2184 | 0.1909 | 0.1741 | 0.1397 | -0.0656 | -0.9 |

- v5/v20 show clean monotone Q1→Q5 structure at every horizon.
- rev10/rev5/dd20/dd60 show consistent **inverted** monotone structure at
  40/120 (original direction preserved; no statement of "buy high/low" is
  applied).
- align (a discrete 4-level factor) is non-monotone with inverted extreme
  groups at 120d (Q5-Q1 = -0.025 despite positive mean RankIC): only
  extreme-group differences, not a smooth monotone relation.
- Monotonicity is descriptive only; it never drove selection.

## 10. REDUNDANCY

16 distinct pairs with |mean daily Spearman| >= 0.80 (frozen threshold):

| factor_a | factor_b | meanSpearman | abs |
| --- | --- | --- | --- |
| d5 | d10 | 0.8106 | 0.8106 |
| d5 | p5 | 0.8666 | 0.8666 |
| d10 | d20 | 0.8283 | 0.8283 |
| d10 | p10 | 0.8565 | 0.8565 |
| d10 | rev5 | -0.8912 | 0.8912 |
| d10 | rev10 | -0.8009 | 0.8009 |
| d20 | p20 | 0.8413 | 0.8413 |
| d20 | rev10 | -0.8937 | 0.8937 |
| d20 | rsi | 0.8647 | 0.8647 |
| d60 | d120 | 0.8445 | 0.8445 |
| d60 | p60 | 0.8228 | 0.8228 |
| d120 | p120 | 0.8443 | 0.8443 |
| p5 | p10 | 0.8216 | 0.8216 |
| p10 | p20 | 0.8080 | 0.8080 |
| p20 | dd20 | 0.8828 | 0.8828 |
| p60 | dd60 | 0.9046 | 0.9046 |

Clusters: same-window trend/position pairs (d/p), reversal versus trend
(negative), rsi versus d20, and range-position versus drawdown (p20/dd20,
p60/dd60 — near-duplicates). v5 vs v20 is 0.63 (below threshold). The 19
columns carry roughly 6-7 independent dimensions. Flags are diagnostics
only; nothing was deleted.

## 11. COVERAGE

- Every factor: 12,400 / 12,400 finite observations over the 100×124
  Development grid; 0 missing; valid sectors per date min = median =
  max = 124.
- All 57 factor×horizon cells: 0 skipped IC dates (every date had all 124
  valid pairs), 0 missing factor-label pairs.
- Endpoint availability: complete (consistent with the frozen D0 run's
  0 label exclusions). No coverage or missingness distortion affects any
  result.

## 12. HORIZON DECAY / DIRECTION

- **Strengthening with horizon (consistent sign):** v20 (+0.071 → +0.187 →
  +0.216), v5 (+0.027 → +0.113 → +0.150). No decay, no reversal.
- **Sign reversal:** rev5 (+0.015 → -0.048 → -0.054) and rev10 (+0.007 →
  -0.066 → -0.064): mild reversal at 10d, momentum-continuation content at
  40/120d in this sample.
- **Decaying negative:** d120 (-0.051 → -0.042 → -0.010); vc
  (-0.035 → -0.019 → +0.002, to zero).
- **Growing negative:** dd60 (+0.003 → -0.037 → -0.082); dd20 (0 → +0.007 →
  -0.023).
- No horizon weights were refit; the frozen 0.25/0.50/0.25 fusion is
  untouched.

## 13. FACTOR IDENTITY AUDIT

- Result: **PASS** (`FACTOR_IDENTITY_BLOCKER` not triggered)
- Sample: 3 dates (E001=2025-04-02, E050=2025-06-17, E100=2025-08-26) ×
  19 factors × 10 sectors = 570 comparisons
- Max absolute difference vs the independent recomputation:
  **1.60e-14** (tolerance 1e-9)
- Column order matches the frozen order exactly; audit values were taken
  through the identical `build_panel` call path the Ridge pipeline uses.

## 14. TARGET IDENTITY AUDIT

- Result: **PASS** (`TARGET_IDENTITY_BLOCKER` not triggered)
- Sample: 3 dates × 3 horizons × 10 sectors = 90 comparisons against two
  independent references
- Max absolute difference vs direct close/calendar arithmetic: **0.0**;
  vs the frozen Iteration-1 D0 control artifact: **1.11e-16**
  (tolerance 1e-12)
- Endpoint semantics: `label_end == calendar[t+h]` confirmed on every
  sampled row; no endpoint shifting anywhere. D0 artifact SHA-256 verified
  before reuse (`b1e7da60…4869f1`).

## 15. RIDGE DIAGNOSIS

Primary tendency: **MODEL_EXTRACTION_WEAK** (a MIXED contribution from
factor-set redundancy is documented below; this is not
FACTOR_INFORMATION_WEAK).

Evidence:

1. Individual factors carry strong, stable, monotone information: v20 alone
   scores weighted RankIC **+0.1653** and v5 alone **+0.1008**, versus the
   best frozen model candidate D2 at **+0.0881**. The best single factor
   nearly doubles the model, and does so with 4/4 block stability and
   perfect quantile monotonicity.
2. D0/D1 weighted RankIC is negative (-0.040/-0.041) despite that
   availability → the absolute-return training target is mismatched to the
   cross-sectional task in this sample (dominant common market component).
3. Even after the target fix (D2/D3), the model retains only ~27% of v20's
   40d signal (RankIC40 0.050 vs 0.187) and ~36% at 10d (0.025 vs 0.071);
   it only matches the single factor at 120d (0.228 vs 0.216). Combination
   over 16 redundant, regime-unstable columns dilutes the stable volatility
   dimension.
4. Per the preregistered rule: stable individual factors + weak model ⇒
   MODEL EXTRACTION / COMBINATION PROBLEM, not "no factor alpha".

Mixed component: 17 of 19 factors are regime-unstable (2/4 blocks) or
near-zero, and the input set is heavily redundant — so part of the
extraction failure is input-set quality, not only the combiner. Scope:
current data, current factor definitions, current Development sample only;
no claim that "the market has no alpha" or that any signal will persist.

## 16. PARAMETER_RESEARCH_GATE

**PARAMETER_RESEARCH_GATE = CONDITIONAL**

Why not NOT_READY: an identifiable factor group (v5/v20, volatility) shows
non-trivial signed RankIC (0.11-0.22 at 40/120d), 4/4 block stability at
40/120d, monotone quantile structure (1.0), and consistent cross-horizon
direction; and D0→D2 (+0.129 weighted RankIC) proves material
representation/target headroom exists in the pipeline.

Why not READY: 17 of 19 factors are regime-unstable (2/4 blocks) or
near-zero; 16 pairs are redundant at |mean daily Spearman| >= 0.80;
several factors show systematic horizon sign flips; and the model extracts
only a fraction of the single-factor information. Entering mass parameter
search on the current frozen 19-factor pipeline would tune parameters
around regime noise and collinear duplicates.

Prescribed next step: design **Factor Set V2 / Alpha Hypothesis V2** first —
volatility-centric factor group with redundancy control, building on the
D2/D3 excess-target finding — and only then parameter research. This gate
is a research judgment, not trading authorization.

## 17. ARTIFACTS

Primary run: `reports/research/shenwan_sector_index/factor_alpha_audit_20260925_071934_967164_utc/`
(generated research output; per repo convention `/reports/research/` is not
tracked by Git — provenance carried by protocol hash, commits, and recorded
SHA-256s):

- `metadata.json`
- `factor_horizon_summary.csv`, `factor_daily_metrics.csv`
- `factor_quantile_summary.csv`, `factor_quantile_daily.csv`
- `factor_stability_blocks.csv`
- `factor_correlation_spearman.csv`, `factor_redundancy_flags.csv`
- `factor_coverage.csv`, `audit_summary.json`

Determinism rerun:
`reports/research/shenwan_sector_index/factor_alpha_audit_20260925_072304_642140_utc/`
(same file list; `determinism = PASS_CONTENT_SHA256_IDENTICAL`).

Content SHA-256 (identical in both runs):
`audit_summary.json 24de9d22…861821d`,
`factor_horizon_summary.csv 24587b98…5e43680`,
`factor_daily_metrics.csv f21415cd…18c322b42`,
`factor_quantile_summary.csv 3f48c70f…feb013ecf`,
`factor_quantile_daily.csv 37e08c7b…e850609b8972f3`,
`factor_stability_blocks.csv 42bde121…d0e830db7`,
`factor_correlation_spearman.csv 2bd2090a…c10c595b7`,
`factor_redundancy_flags.csv 05d22fc3…16ae1d36`,
`factor_coverage.csv 1269ff7d…bb9b685d`.

## 18. DETERMINISM

Re-run with unchanged inputs after the formal run. All nine non-metadata
data artifacts **byte-identical** (identical SHA-256, enforced by the
runner's `--repeat-of` check; only run_id/timestamps inside `metadata.json`
differ). No FACTOR_AUDIT_DETERMINISM_BLOCKER.

## 19. TESTS

Targeted (`tests/test_factor_alpha_audit_v1_protocol.py`,
`tests/test_factor_alpha_audit_v1_run.py`, 21 tests):
**passed 21, failed 0, skipped 0**. Coverage: factor order frozen;
Development-only ordinals; no Validation/OOS evaluation; endpoint
semantics; min valid pairs = 30; Pearson IC + Spearman RankIC vs SciPy
with ties; sector-code tie-break; quintile assignment incl. remainder
allocation; Q5-Q1; 4 fixed blocks + same-sign counting; daily factor
correlation; redundancy threshold 0.80; missingness never imputed; no
automatic direction flip; deterministic artifact ordering/bytes; protocol
hash freeze and drift detection; factor identity gate; target identity
gate; determinism drift detection.

Full suite (`docker compose exec quant-research pytest`, on the final
tree): **passed 518, failed 0, skipped 2, deselected 17** (integration
tests deselected by default marker policy).

## 20. RESEARCH COMPLIANCE

- Development only (E001-E100): confirmed by ordinal guards
- Validation untouched: SEALED (no ordinal >= 221 evaluated)
- Final OOS untouched: SEALED
- No parameter search; no factor selection; no sign optimization
- No Docker changes; no dependency changes; no Hikyuu data changes
- No ETF; no portfolio; no execution; no Dashboard/API changes
- Iteration-1 artifacts read-only (byte hashes re-verified, never modified)
- All quant execution via `docker compose exec quant-research` on the
  frozen `quant-research:py3.12` image (image ID
  `sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5`,
  verified by the pre-run gate)

## 21. ENVIRONMENT_CHANGED

**false** (both runs record `environment_changed = false`; the pre-run gate
compares the live image ID against the frozen expectation)

## 22. COMMITS

- Preregistration commit SHA: `786b8f11281a763e23fee969e1f1c37ece9e29c0`
  (`research: preregister factor alpha audit v1`)
- Audit result commit SHA: the commit introducing this report
  (`research: run factor alpha audit v1`) — SHA listed in the accompanying
  research summary, same branch
- Ordering proof: both audit runs carry `gitCommit = 786b8f11…` and UTC
  timestamps after that commit; the report is the only result-side change.

## 23. FINAL STATUS

**FACTOR ALPHA AUDIT V1 COMPLETE WITH NON-BLOCKING WARNINGS**

Non-blocking warnings:

1. Factor-order transcription note: the task text listed the frozen order
   with `rsi` before `dd20/dd60`; the frozen pipeline identity
   (`TRAIN_FEATURES_PRICE` = `EXPECTED_FEATURES`, feature hash
   `ee1b70d4623b566451eae8c8a0c4878720049e506b05f4cd94b9d7c806e54c59`)
   orders them `… rev5, rev10, dd20, dd60, rsi`. The audit follows the
   frozen pipeline order to preserve exact factor identity with the Ridge
   inputs (protocol requirement §4). No result depends on ordering.
2. Descriptive t-stats are present in artifacts and marked
   DESCRIPTIVE ONLY; they were not used for any judgment threshold.
