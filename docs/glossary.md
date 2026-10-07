> Current role: INDUSTRY_FORECAST_RESEARCH (SWL2-Ridge-V1 / SWL2-Ridge-V2). ETF productization is RETIRED. Historical ETF formulas, commands and observations below are audit context; writer entry points fail closed. See [current industry contracts](industry-forecast.md).

# Project glossary

This is the canonical terminology reference for research, ETF-Quant V1, V2 research,
the runner, APIs and dashboard. Serialized historical identifiers remain compatible.

| Term | Meaning |
| --- | --- |
| Factor | A numerical feature calculated from information available at a decision date. |
| Ridge | Linear regression with an L2 penalty on coefficients; the intercept is unpenalized. Alpha must be interpreted relative to feature scale. |
| Horizon, H10/H40/H80/H120 | A forward label covering that many exchange trading sessions. H80 belongs only to the registered V2 experiment. |
| Feature standardization | Subtract each feature's training mean and divide by its training population standard deviation; persist and reuse those parameters. V1 uses raw features. |
| Cross-sectional z-score | Standardize a horizon's predictions across industries on one signal date, using population variance. This is separate from feature standardization. |
| Fusion | Combine the independently standardized horizon predictions using declared weights. |
| RankIC | Spearman rank correlation between industry predictions and the declared forward target on one date. |
| PIT (point in time) | Evidence that the facts and universe were available at the historical decision time. Effective date alone does not prove availability. |
| Walk-forward | Refit chronologically using only earlier features and labels already matured at each signal. |
| Development | The sole phase allowed for model specification comparison and selection. |
| Validation | Reserved chronological evidence evaluated after candidate freeze. V1 remains sealed; V2 opened once and failed. |
| Validation-informed revision | One Development revision after Validation diagnosis; independent status requires its separately frozen Final-OOS result. |
| Tier A | Official historical membership with historical availability evidence. |
| Tier B | Real effective-dated historical reconstruction with sufficient source/roster coverage; historical availability can be unknown. |
| Tier C | Weaker or retrospective historical reconstruction, explicitly identified for sensitivity analysis. |
| Tier D | Unsupported/unclassifiable records excluded from modeling. |
| High-confidence research | Uses eligible A/B records under the declared coverage policy. |
| Extended-history research | Also admits explicitly labelled C records; does not imply strict PIT. |
| Final OOS | Final out-of-sample phase, excluded from selection. V1 remains sealed; V2 opened once under the preregistered gate, with no subsequent retuning. |
| Purge / maturity isolation | Separate signal phases so forward labels cannot cross into the next evaluation phase. |
| Effective sample size (ESS) | An assumption-dependent estimate of temporal information under dependence. Cross-sectional rows are not additional independent time periods. |
| Universe | The industries or instruments eligible on a specific date, with explicit membership evidence. |
| Provenance | Source identity, publication/observation/availability instants, version and content hashes. |
| Shadow | Future simulated operation on genuine newly finalized dates. Synthetic tests and historical simulations do not create formal Shadow history. |
| Intent | A recorded proposed simulated transaction, preceding eligible execution evidence. |
| Delayed T+1 accounting | A finalized T-close decision is accounted for only after its genuine future T+1 raw opening evidence is finalized. |
| Industry-to-ETF mapping | Evidence-backed association between a ranked industry and an executable ETF. |
| Direct tracking ETF | An ETF with admitted direct industry-tracking evidence; historical mapping category `Strict` is retained. This does not by itself certify historical data PIT. |
| Industry-exposure proxy ETF | An ETF admitted through complete official weights, target exposure, dominance, PIT and liquidity evidence. |
| Cash fallback | Preserve the original unexecutable slot's weight as unallocated capacity; do not redistribute it or treat cash as an ETF. |
| Historical gate identifier | `PASS_STRONG` / `PASS_WEAK` are immutable original gate decisions, not current statistical validation claims. Current V2 is provisional: direction STRONG_POSITIVE, statistics LIMITED, membership RECONSTRUCTED, historical ETF execution NOT_ESTABLISHED. |
| Forward experimental Shadow | `EXPERIMENTAL_UNVALIDATED_RESEARCH_SHADOW`: the required public label after Final-OOS failure; still simulation only. |
| Armed launch | Persisted configuration and readiness for the next eligible date, with no manufactured epoch, intent or NAV. |

| Canonical public term | Legacy identifier | Compatibility reason |
| --- | --- | --- |
| Internal equal-weight constituent return series | `Source-C` / `SOURCE_C` | Historical series/evidence identity; never an official Shenwan index. |
| Original five highest-ranked industries | `Top5` / `FrozenTop5` | Historical selection/evidence wording; ranking and skipped weights are unchanged. |
| 40% industry-exposure proxy with cash fallback | `B40_WITH_CASH` | Frozen candidate, API schema and historical evidence identity. |
| Direct tracking mapping | `Strict` | Serialized mapping category; distinguish it from strict historical PIT. |
| Direct industry tracker | `DIRECT_INDUSTRY_TRACKER` / `STRICT_MAPPING` | V2 canonical class and legacy compatibility alias. |
| Verified industry proxy | `VERIFIED_INDUSTRY_PROXY` / `PROXY_EXPOSURE` | Complete primary weights, dominant exposure and current liquidity admission. |
| No reliable mapping | `NO_RELIABLE_MAPPING` / `CASH_UNEXECUTABLE_SIGNAL` | Preserve the original industry's assigned cash capacity. |
| Mapping contract pending | `PENDING_DEEPSEEK_CONTRACT` | Existing state/reason strings; canonical Python name is `MAPPING_CONTRACT_PENDING`. |
| Public integration review pending | `PENDING_MIMO_AUDIT` | Existing state strings; canonical Python name is `PUBLIC_INTEGRATION_REVIEW_PENDING`. |

The two older Python constant imports remain aliases. Required historical files keep
their original names and bytes; the naming gate permits only exact pinned exceptions.

## Current industry terminology

- SCIENTIFIC_TARGET: exact H-session industry return minus its same-date frozen-universe mean.
- VISUAL_TREND_DIAGNOSTIC: separate normalized realized path, never model score or tradable NAV.
- RECONSTRUCTED_SWL2_EQUAL_WEIGHT: admitted adjusted constituent-return reconstruction; not official index bars.
- COMMON_FORWARD_WINDOW: genuinely published shared dates with identical matured horizon.
- COMMON_INDUSTRY_CROSS_SECTION_DIAGNOSTIC: additional intersection-universe comparison; frozen primary metrics stay separate.
- Research budget: experiment/phase constraints. Monetary budget, sizing and costs are retired.
- HISTORICAL_PRODUCTIZATION_RESULT: preserved ETF evidence, not current forecast capability.

## Current forecasting vocabulary

Taxonomy universe: current classification inventory (134), independent of fitted model identities. Model universe: complete pinned family cross-section (107/124). Forecast row: actually published admitted industry. Scientific target: exact h-session return minus native universe mean. Raw realized return: uncentered industry outcome. Maturity: exact finalized exchange-session endpoint. Common forward window: shared genuine dates/horizons plus compatible raw returns on shared industries. Historical productization: retired ETF engineering lineage. SWL1-Ridge-V1 remains NOT_YET_RESEARCHED.

## SWL1 research terms

SWL1 means Shenwan Level-1; SWL2 means Level-2. Generation numbers are independent within each family. A model universe is fixed factual admission, distinct from current taxonomy inventory. A purged split separates signal phases by exact exchange sessions to avoid horizon label overlap. Candidate freeze binds parameters before Validation. A phase consumption claim cannot be reopened. Directional labels are descriptive; overlapping horizons limit independent confidence. Forward eligibility is a protocol gate, not evidence of live predictions.
