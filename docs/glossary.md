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
| Validation | A reserved chronological phase, unopened in this project task. |
| Final OOS | Final out-of-sample phase, unopened and excluded from selection. |
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

| Canonical public term | Legacy identifier | Compatibility reason |
| --- | --- | --- |
| Internal equal-weight constituent return series | `Source-C` / `SOURCE_C` | Historical series/evidence identity; never an official Shenwan index. |
| Original five highest-ranked industries | `Top5` / `FrozenTop5` | Historical selection/evidence wording; ranking and skipped weights are unchanged. |
| 40% industry-exposure proxy with cash fallback | `B40_WITH_CASH` | Frozen candidate, API schema and historical evidence identity. |
| Direct tracking mapping | `Strict` | Serialized mapping category; distinguish it from strict historical PIT. |
| Mapping contract pending | `PENDING_DEEPSEEK_CONTRACT` | Existing state/reason strings; canonical Python name is `MAPPING_CONTRACT_PENDING`. |
| Public integration review pending | `PENDING_MIMO_AUDIT` | Existing state strings; canonical Python name is `PUBLIC_INTEGRATION_REVIEW_PENDING`. |

The two older Python constant imports remain aliases. Required historical files keep
their original names and bytes; the naming gate permits only exact pinned exceptions.
