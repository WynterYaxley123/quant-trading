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
