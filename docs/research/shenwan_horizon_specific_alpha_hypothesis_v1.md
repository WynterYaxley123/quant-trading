# Shenwan Sector Rotation — Horizon-Specific Alpha Hypothesis V1

**PREREGISTRATION ONLY. NO NEW FORMAL RESULT IS AUTHORIZED BY THIS DOCUMENT.**

## Research state, source identity and interpretation

This protocol is frozen on `experiment/sw-sector-index-research-baseline`, starting at `ff34ad5cc09ff419b1d12aad33ca7dfff4fe865e`. The formal evidence is Development E001–E100, fixed `U0_FIXED_124`, 2025-04-02 through 2025-08-26. Validation and Final OOS remain SEALED. This is **POST-AUDIT DEVELOPMENT HYPOTHESIS REFINEMENT**, **NOT INDEPENDENT VALIDATION**, **NOT OOS**. `DEVELOPMENT_REUSE_WARNING=true`: Iteration-1, Factor Audit, V2, Alpha Stability, and this design all inspect the same Development sample. A later attractive result on it does not become independent evidence merely because this candidate list was preregistered.

Existing formal evidence (paths relative to repository root, metadata SHA-256):

| Study | Preregistration / formal commit | Formal artifact | Metadata SHA-256 |
|---|---|---|---|
| Iteration-1 D2/C0 | `dc5626ac33da6953ae908eb0d1a0c01769474a7f` / `ea26a8e23fd6cfa54eedc9e7cb8786d978c2ccc7` | `reports/research/shenwan_sector_index/iteration1_20260924_163607_787266_utc/` | `25a9a637f9a3c7c48750057551b1975e780e8ffe212274d276550b479e5ee526` |
| Factor Alpha Audit V1 | `786b8f11281a763e23fee969e1f1c37ece9e29c0` / `5a7eb9f0e1d0d4a3fafd51cec7fcd278e1a9ed86` | `reports/research/shenwan_sector_index/factor_alpha_audit_20260925_071934_967164_utc/` | `ec7692a815559be09c87d4833c18472357b70c6efee28022d4ed1163776a894a` |
| Factor Set V2 | `b836f27e33987ea3d987b8683a38acc442cb2cdd` / `8803f618e4a7a5ea5c65d550ecf71063182782e6` | `reports/research/shenwan_sector_index/factor_set_v2_20260925_090958_520718_utc/` | `481febeb025854f4555d896de82fabfe43ff5594fb0fd6766de33ffa3dd1f908` |
| Alpha Stability & Regime Audit V1 | `111cb8d21bcd1ba053cbf06691c6dc5851a17ae2` / `ff34ad5cc09ff419b1d12aad33ca7dfff4fe865e` | `reports/research/shenwan_sector_index/alpha_stability_regime_audit_20260925_103645_877103_utc/` | `d1e7b9ba941a3ab58f97e9cdfe8a3ab05d1071012fe08bbe488a65ed358d0b11` |

These metadata hashes identify the existing reports; selection itself consumes only two source CSVs, with exact byte hashes in the [selection trace](shenwan_horizon_specific_alpha_hypothesis_v1_selection_trace.md) and machine module. The Alpha Stability formal protocol hash is `7bdf79df7c95134cdbdedb04ce825614c35a2bc72b4f757dd09ecf5e588fb4c1`; V2's is `3fbba8e5b41c0b5b839dab2788f1e000b9add95406bb14cbaf4c13f31664b4f4`.

The pre-existing V2 C0 weighted RankIC/spread are +0.08810651455546813/+0.037216498377093545; V2_A/B/D were not advanced and Parameter Research remained NOT_READY. These performance values motivate the question, **never rank factors** in this design. Alpha Stability found v20 at 40 days: mean legal training RankIC -0.0453, subsequent marginal evaluation RankIC +0.1867, and 77/100 hard flips. Existing C0 40-day B1–B4 model RankIC was +0.240/+0.262/-0.118/-0.185, versus 120-day +0.273/+0.202/+0.253/+0.183. The audit gate was `HORIZON_SPECIFIC_HYPOTHESIS_READY`, not proof of alpha. Overlapping labels and repeated Development inspection prevent statistical independence or a durable regime claim.

## Questions and hypotheses

Q1. Can pre-frozen, horizon-local factor hypotheses be formed without requiring one factor set at 10/40/120 days? Q2. Can factor choice reflect observed **train→future relationship stability**, not realized return magnitude? Q3. Does a stable single-factor hypothesis differ from a compact, cross-family hypothesis? Q4. Does 40-day evidence warrant a test despite its weakness, including a possible `NO_STRONG_STABILITY_EVIDENCE` conclusion after formal evaluation? Q5. Does the apparently steadier 120-day diagnostic survive an equally frozen horizon-local test? These are hypotheses to test, not claims already established.

## Frozen universe and selection rule

The exact 19 pipeline columns, in model-input order, are `d5,d10,d20,d60,d120,p5,p10,p20,p60,p120,align,v5,v20,vc,rev5,rev10,dd20,dd60,rsi`. Six frozen families and their members/order are imported unchanged from Factor Set V2: TREND_MOMENTUM (`d5,d10,d20,d60,d120`), RANGE_POSITION (`p5,p10,p20,p60,p120`), OSCILLATOR_ALIGNMENT (`align,rsi`), VOLATILITY (`v5,v20,vc`), REVERSAL (`rev5,rev10`), DRAWDOWN (`dd20,dd60`). No new factor, transform, negative copy, or changed formula is permitted.

For each factor × horizon, rank all 19 lexicographically by: (1) **lowest** Alpha Stability `hard_flip_rate`; (2) **highest** `raw_sign_agreement_rate`; (3) **highest** `transfer_spearman`; (4) **lowest** frozen pipeline index. Use source full-precision floats, not rounded display. Adjacent direction persistence is not an explicit field of `factor_transfer_summary.csv`, so no substitute is invented. All 57 rows must exist, be finite and have 100 valid dates; incomplete evidence raises `HORIZON_STABILITY_EVIDENCE_INCOMPLETE`. Mean evaluation RankIC (including its sign/magnitude), spread, Top5 return, V2 performance, Sharpe, drawdown and C0 attribution **are not selection keys**. Negative factor relationship is not automatically excluded; Ridge must learn its sign without manual inversion.

`SINGLE_STABLE` takes global rank 1. `COMPACT_STABLE` processes the six frozen families in order. Within each family it tries members by that horizon's same rank; reject a member if its absolute mean daily raw-factor Spearman correlation with **any** already selected factor is `>= 0.80`, then try the next member. This 0.80 threshold is inherited from Factor Audit V1. If all members fail, omit the family; do not backfill. At most one factor per family and six total. If the result collapses to one factor, keep and label `COMPACT_COLLAPSED_TO_SINGLE`. The final model-input list is ordered by the original factor pipeline, not by selection order. No manual override, subset search, factor-return tie-break or new archetype is allowed. Source content hashes are checked before selection.

## Exact candidate freeze and budget

The only new hypotheses are two per horizon; C0 is a same-horizon 19-factor reference and does not consume budget.

| Candidate | Horizon | Archetype | Exact factor list (model-input order) |
|---|---:|---|---|
| H10_S | 10 | SINGLE_STABLE | `[p5]` |
| H10_C | 10 | COMPACT_STABLE | `[d10,p5,align,vc,dd20]` |
| H40_S | 40 | SINGLE_STABLE | `[vc]` |
| H40_C | 40 | COMPACT_STABLE | `[d120,p60,align,vc,rev5,dd20]` |
| H120_S | 120 | SINGLE_STABLE | `[vc]` |
| H120_C | 120 | COMPACT_STABLE | `[d5,p20,vc,rev10,dd60,rsi]` |

The [selection trace](shenwan_horizon_specific_alpha_hypothesis_v1_selection_trace.md) records all 57 rank inputs and every compact family admission/redundancy exclusion. **H40 EVIDENCE QUALITY WARNING / NO_STRONG_STABILITY_EVIDENCE:** `vc` has zero hard flips, but the other 18 factors have rates at least 0.44. Five of H40_C's six selected factors have 0.45–0.59 hard-flip rates. More importantly, the pre-existing direction-transition table shows `vc`'s legal 40-day training RankIC was **NEUTRAL on all 100 dates**; at 120 days it was NEUTRAL on 99/100. H10_S `p5` was also training-NEUTRAL on all 100 dates. Thus zero hard flips can mean *no decisive past direction*, not a reliably transferred one. The secondary sign-agreement/Spearman inputs remain as registered, but this ranking limitation makes the single-factor evidence weak at all three horizons, especially H40. It is disclosed rather than repaired post hoc: candidates stay mechanically frozen, with no exclusion, sign inversion, or contrarian rule. Formal tests may fail; neither a neutral training relationship nor a zero flip count is validated Alpha.

## Future formal experiment semantics — not executed by this commit

Only after separate human authorization: each H10 candidate fits only h=10, each H40 only h=40, each H120 only h=120. All non-factor settings are the D2/C0 contract: raw X, no standardization; same-training-date cross-sectional excess forward-return **training** target; `NumPyRidge(alpha=0.01, fit_intercept=True)`; six calendar-month rolling window anchored to each horizon's legal label cutoff; minimum 30 valid training dates; only already-realized legal labels. Evaluation uses unchanged absolute forward return on the common trading calendar at `t+h`; no missing endpoint shift or price fill. At a signal date, rank sectors by that horizon's prediction descending, breaking ties by sector code ascending. Top5 is exactly the highest five; Spread = mean Top5 absolute forward return minus mean fixed-universe absolute forward return. No cross-horizon fused score or Top5.

Only Development E001–E100 may be used for a future authorized run. The frozen blocks are B1=E001–E025, B2=E026–E050, B3=E051–E075, B4=E076–E100. Primary metrics per candidate × its own horizon: mean RankIC and mean Top5-minus-Universe Spread. Secondary: mean IC, median RankIC, median Spread, population std, min, max, valid dates and B1–B4 block metrics. No weighted/fused primary metric or opaque composite score. A 10-day candidate may compare only with C0_H10, 40 with C0_H40, 120 with C0_H120; no cross-horizon winner is permitted.

The preregistered advancement rule is:

1. Level 1: candidate mean RankIC **> 0** AND mean Spread **> 0**, else `HORIZON_NOT_ADVANCED`.
2. Level 2: versus same-horizon C0, candidate RankIC **>** C0 RankIC and Spread **>=** C0 Spread, **OR** candidate Spread **>** C0 Spread and RankIC **>=** C0 RankIC; otherwise `HORIZON_NOT_ADVANCED`.
3. Temporal gate: at least **3/4** fixed blocks have mean RankIC **> 0**, and at most **1/4** blocks has mean RankIC **< -0.02**; otherwise `TEMPORAL_STABILITY_GATE_FAIL`. Passing all three gives `HORIZON_ADVANCED_FOR_FURTHER_REVIEW`, not Validation or deployment. Missing metrics block assessment.
4. If both S and C pass for the **same horizon**, and both absolute differences (mean RankIC and mean Spread) are **< 0.01**, prefer S for simplicity only. No significance claim. If not a near tie, report both statuses without an invented cross-horizon or global winner.

No fusion optimization, 0.25/0.50/0.25 comparison, sign flip, contrarian v20, horizon deletion, TopK change, alpha tuning, training-window/target change, standardization, replacement model, parameter search, new portfolio, ETF mapping, trading, dashboard/API or Validation/OOS opening is authorized. This document does not authorize any formal run at all. The only next authorized action is a **human review** followed by a separate instruction to run V1 under this frozen protocol.

## Machine identity and stop point

Machine config: `research/configs/horizon_specific_alpha_hypothesis_v1.json`. Selection-only helper: `research/horizon_specific_alpha_hypothesis_v1_selection.py`. Fail-closed protocol: `research/horizon_specific_alpha_hypothesis_v1_protocol.py`. Its deterministic canonical SHA-256 covers exact machine config, frozen constants, both source hashes, and byte hashes of this document, the selection trace, and both implementation modules (the self-referential hash assignment alone is normalized). A later mismatch must raise `HORIZON_SPECIFIC_PROTOCOL_HASH_MISMATCH`; it is not a license to update the hash after seeing results. The protocol has no formal runner. Commit preregistration, then stop.
