> Current role: INDUSTRY_FORECAST_RESEARCH (SWL2-Ridge-V1 / SWL2-Ridge-V2). ETF productization is RETIRED. Historical ETF formulas, commands and observations below are audit context; writer entry points fail closed. See [current industry contracts](industry-forecast.md).

# Data and point-in-time evidence

CNEquity is external and pinned. Raw/curated/runtime market data does not belong in Git.
Factual exports carry hashes, schemas, cutoff, retrieval instants, adjustments and
source identity. The internal equal-weight constituent series (historical Source-C
identity) is not an official index.

Effective date, issuer publication, system observation and system availability are
different facts. Later observation never proves earlier availability. Official tracking,
complete weights and explicit classification establish a mapping package. Unknown
classification and incomplete weights fail closed; missing mass is not renormalized.

B40 additionally requires dominance, 40% target exposure, twenty valid liquidity
sessions and availability at decision time. Unavailable Top5 slots stay cash. Current
routing identity cannot prove historical trading; engineering reference dates create no history.

CSV booleans are explicit true/false. NumPy scalar booleans serialize canonically;
nullable missing values remain invalid evidence. Built-in bool identity after JSON/schema
validation is deliberate. `UNPARSEABLE` remains a historical serialized reason token
for invalid instants; compatibility requires preserving it.

Research API reads at most 32 MiB per artifact, with descriptor stat and bounded reads.
Approved artifact hash keys are strict. MIT source licensing grants no market-data rights;
redistribution clearance remains unverified. See [market-data policy](data/market_data_policy.md).

V2 distinguishes strict historical availability (Tier A), verified effective-dated
reconstruction (B), weaker/retrospective reconstruction (C) and excluded unsupported
rows (D). Later observation never upgrades reconstructed rows to strict PIT.
Annual independent public stock rosters check symbol coverage, not industry accuracy.
Current membership alone cannot be backfilled. Unknown denominators remain null;
absent bars/amounts stay missing. V2 roots are independent of V1 and outside Git.
See the [executed V2 protocol](etf-quant-v2-protocol.md) and [glossary](glossary.md).

## Current industry outcome boundary

Taxonomy scope SWCLASS2021 has 134 current identities and 63 historical parsing identities. Model sizes come from pinned universe references (107/124), never taxonomy count. Realized series is RECONSTRUCTED_SWL2_EQUAL_WEIGHT from existing Source-C adjusted constituent returns and dated membership. Official classification provenance does not establish official price bars. Revised consumed factual prefixes fail closed. Scientific targets center exact h-session returns over each complete family universe.

## SWL1 factual admission

The [Level-1 protocol](research/swl1-ridge-v1-protocol.md) dynamically discovers 31 current identities and admits 30 with continuous exact equal-weight history after the 2021 version boundary. Explicit parent-name/code relations establish hierarchy; current codes are not backfilled before 2021-07-31. Effective-dated stock spells remain retrospective, Tier A=0. Aggregation does not upgrade confidence. The series is RECONSTRUCTED_SWL1_EQUAL_WEIGHT, not an official index. Unsupported membership, suspension and missing adjacent adjusted prices remain excluded/missing.

SWL1-Ridge-V2 retained this exact panel/universe and target before results.
Official L1 index performance never entered target selection. V1 outcomes
through its last H120 maturity, 2025-09-23, are seen. V2's first Validation
endpoint is 2025-09-23, first outcome 2025-09-24: all 378 `(t,t+h]` intervals
were outside the declared V1 consumed outcome interval. This arithmetic does not
certify historically unseen numeric access: the old executors materialized full
panels. Historical isolation remains NOT_CERTIFIED, with zero certified unseen
sessions. The unopened V1 OOS plan overlaps 125/126 signals,
with one earlier endpoint; exact-range repurpose is false. Verified public/
private lineage and absence of V1 OOS claims/results allowed authorized partial
reuse as V2 Validation. Its single failed Validation makes those outcomes seen
for later research; no historical Final OOS is available to V2. See
[actual closure](research/swl1-ridge-v2-results.md).

The new [data-first assessment](research/swl1-data-first-feasibility.md) keeps
historical Tier A=0/B=0/C=reconstructed. Publication, effective, observation,
ingestion and revision times are distinct. Metadata watermarks do not establish
rights, contemporary availability or adjustment/delisting completeness. Formal
source admission remains blocked; revisions require immutable new generations.
