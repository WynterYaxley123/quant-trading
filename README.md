# quant-trading

[English](README.md) | [简体中文](README.zh-CN.md)

quant-trading studies **Shenwan Level-2 industry forecasts** with frozen multi-horizon
Ridge models, point-in-time facts and immutable forward observations. Its current
families are **SWL2-Ridge-V1** (frozen baseline) and **SWL2-Ridge-V2** (provisional
historical research candidate). Both have role `INDUSTRY_FORECAST_RESEARCH`.
ETF productization is `RETIRED`. SWL1-Ridge-V1 is reserved, `NOT_YET_RESEARCHED`.

## Current research status

The [canonical registry](config/research/swl2-ridge-families.json) binds names,
legacy identities, actual admitted universes and frozen model hashes. V1 emits all
**107** admitted industries; V2 emits all **124** from its byte-pinned warmup.
Expanding V1 would alter its training and target centering, so it retains 107.
There are no forward forecasts or matured observations created by this delivery.
Missing quantitative metrics are **null**, with honest empty dashboard states.

V1 Validation and Final OOS remain sealed. V2 is
`PROVISIONAL_HISTORICAL_RESEARCH_CANDIDATE`: the original Validation failed and
the Validation-informed revision consumed its one original Final OOS.
Historical directional Final OOS is `STRONG_POSITIVE`; independent statistical
confidence is `LIMITED`, membership is `RECONSTRUCTED`, and historical ETF
execution validation is `NOT_ESTABLISHED`. Consumed OOS cannot be resealed into
unseen evidence. Historical classifications and bytes remain intact.

## Frozen scientific contracts

| Contract | SWL2-Ridge-V1 | SWL2-Ridge-V2 |
| --- | --- | --- |
| Admitted universe | 107 | 124 |
| Ridge alpha / window | 0.01 / 6 months | 30.0 / 12 months |
| Features | Frozen 5 for H10; 19 for H40/H120 | Same frozen factor sets |
| Input mode | Raw X | S2A-RAW-m12-a30 |
| Horizons | H10 / H40 / H120 trading sessions | H10 / H40 / H120 trading sessions |
| Fusion | Population z-score, 0.25 / 0.50 / 0.25 | Population z-score, 0.25 / 0.50 / 0.25 |
| Role | Frozen baseline industry research | Provisional historical industry candidate |

Rolling coefficients use only mature eligible labels. This transition performs no
model search, retuning, new Validation or OOS evaluation. The scientific target
remains each exact H-session industry return minus that date's frozen-universe
mean. Research budget means an experiment/phase budget; money and account sizing
are absent from the active industry path.

## Forward observations and evaluation

The actual merge identity is resolved from main; a separate immutable runtime
binding freezes source, model and activation time. The first eligible forecast is
on an official session strictly after both merge and activation dates, using
current finalized facts observed after 15:05 Shanghai time. Missing sessions
cannot be backfilled. Preflight and dry-run never write or freeze anything.

Each immutable publication stores the entire admitted cross-section: industry
name/code, raw H10/H40/H120 prediction, z-score, horizon rank, fused score/rank,
data cutoff, source commit, model hash and provenance. Duplicate retries skip
refitting; atomic generations, OS mutexes and verified journals recover crashes.

Horizon evaluation stays `PENDING` until the exact exchange-session maturity and
all required points finalize. No provisional close, gap bridge or future value
is used. Descriptive diagnostics include Spearman RankIC, horizon Top5/Bottom5
returns and spread, actual Top5 overlap, rank errors, rolling 20-date means and
the worst 20-date spread interval. Empty metrics are null. Overlapping horizons
receive no statistical winner or significance claim.

`COMMON_FORWARD_WINDOW` matches real common dates and matured horizons. Because
universes differ, its additional `COMMON_INDUSTRY_CROSS_SECTION_DIAGNOSTIC`
recomputes diagnostics on the industry intersection with equal realized returns;
each family's primary frozen-universe metrics remain separate.

## Realized series and visual diagnostics

Current admitted Source-C facts reconstruct exact-adjusted constituent industry
returns using existing dated membership/coverage rules. The explicit type is
`RECONSTRUCTED_SWL2_EQUAL_WEIGHT`. Official taxonomy provenance does not make these
official index bars. No authorized official SWL2 index-bar source is established
in the admitted adapters. Local evidence does not grant redistribution rights.

The dashboard defaults to Industry Forecast: complete rankings, Top5, signal
history, maturity, predicted/realized comparisons and common-window diagnostics.
Matured paths start at 1.0 and are `VISUAL_TREND_DIAGNOSTIC`,
`NORMALIZED_RESEARCH_INDEX`, `NON_TRADABLE_RESEARCH_DIAGNOSTIC`. They are independent
signal outcomes, with a SWL2 universe equal-weight baseline, never a chained
tradable NAV. Scores and realized trend paths have separate views.

## Historical ETF productization

ETF availability, exposure purity and execution evidence proved insufficient for
reliable Level-2 product coverage. That is a `HISTORICAL_PRODUCTIZATION_RESULT`.
Current industry forecasts require no ETF mappings, portfolio targets, cash slots,
initial capital, position caps, lots, costs, fills or account events.

Historical `ETF_QUANT_V1` / `ETF_QUANT_V2` configs, mappings, releases, Shadow
artifacts, reports, certificates and ledgers retain their identities and hashes.
Legacy APIs/pages remain read-only audit views with retirement metadata. Writer
commands fail closed; legacy writer regression requires an isolated synthetic
temporary namespace. No real orders, brokers, leverage or shorting are enabled.

## Architecture and layout

```mermaid
flowchart LR
 F[External pinned PIT facts] --> M[Frozen Ridge industry adapters]
 M --> L[Immutable full forecast ledger]
 F --> E[Exact mature industry outcomes]
 L --> E
 E --> A[Read-only Industry Forecast API]
 L --> A
 A --> D[Industry Forecast Dashboard]
```

| Path | Purpose |
| --- | --- |
| strategies/swl2_ridge/ | Registry, adapters, ledger, maturity and descriptive metrics |
| services/industry-forecast-runner/ | Docker-only forward runner and disabled scheduler template |
| services/industry-forecast-api/ | Bounded read-only API |
| dashboard/ | Default industry research UI; historical audit routes |
| config/research/ | Canonical family and transition contracts |
| docs/industry-forecast.md | Scientific, factual and operational contracts |
| tests/ | Portable synthetic regression and marked external integrations |
| reports/ | Public-safe immutable evidence and chained source certificates |
| docs/archive/ | Byte-preserved historical documents |

## Data-free quick start

Use the independent developer image, never the deployed image or host quant Python.

```sh
docker build -f .devcontainer/Dockerfile -t quant-trading-dev:local .
docker run --rm -v "${PWD}:/workspace" quant-trading-dev:local python -m examples.industry_forecast_demo
docker run --rm -v "${PWD}:/workspace" quant-trading-dev:local python -m pytest -q -m "not external_runtime"
```

Inside the developer container, use `pnpm --dir dashboard install --frozen-lockfile`,
then test/typecheck/lint/build. `node services/industry-forecast-api/server.mjs`
serves an honest empty state without runtime configuration. The runner requires
clean merged source and explicit external read-only facts; engineering does not
invoke it against live facts. The scheduler template is disabled; this delivery
promotes no live deployment and creates no business events.

## Documentation and contribution

Start with [industry forecast](docs/industry-forecast.md), [documentation index](docs/index.md),
[development](docs/development.md), [testing](docs/testing.md),
[data/PIT](docs/data-and-pit.md), [deployment](docs/deployment.md),
[operations](docs/operations.md), [reproducibility](docs/reproducibility.md),
[research status](docs/research-status.md) and [contributing](CONTRIBUTING.md).
The [historical strategy contract](docs/strategy.md) remains auditable.

SWL1-Ridge-V1 needs an independent universe, preregistered protocol, Development,
Validation and unopened Final OOS. This task trains no SWL1 model and does not
repurpose SWL2 consumed evidence for it. Source is [MIT licensed](LICENSE);
[third-party notices](THIRD_PARTY_NOTICES.md) and [data-rights policy](docs/data/market_data_policy.md)
apply independently. See [security reporting](SECURITY.md).
