# SWL2 industry forecasting

The canonical family registry is [swl2-ridge-families.json](../config/research/swl2-ridge-families.json).
SWL2-Ridge-V1 is the frozen baseline; SWL2-Ridge-V2 is a provisional historical
research candidate. Both have role `INDUSTRY_FORECAST_RESEARCH` and ETF
productization status `RETIRED`. `ETF_QUANT_V1` / `ETF_QUANT_V2` remain historical
identities in immutable artifacts. SWL1-Ridge-V1 is reserved and `NOT_YET_RESEARCHED`.

## Frozen universes and targets

Publish every industry actually emitted by the frozen implementation, never just
Top5 and never fabricated scores for unadmitted industries. The V1 admitted
[universe contract](../strategies/etf_quant/config/common_model_universe_v1.json)
contains **107 industries**. The V2 byte-pinned warmup metadata contains **124**.
Taxonomy inventory, admitted model universe and historical ETF mapping coverage
are different quantities. Expanding V1 to 124 changes its training cross-sections,
target centering and ranks; this transition preserves its 107-industry contract.

`SCIENTIFIC_TARGET` is the frozen same-date cross-sectional excess industry return:
an industry's exact H-session compounded return minus its frozen-universe mean.
Ridge alpha, factors, mature-label windows, raw/standardized specification, eligibility,
fusion and industry-code deterministic ties stay unchanged. V2 normally refits
coefficients using mature facts at alpha 30, 12 months, raw X and H10/H40/H120;
this is the frozen rolling fit, with no search or retuning. V1 retains alpha .01,
six months, raw X and its existing factors/fusion. Research budgets, phase gates,
Validation isolation and consumed/sealed Final-OOS rules remain in force.

## Publication and maturity

The [transition](../config/research/swl2-industry-forecast-transition.json) identifies
the change before merge without inventing its final SHA. The runner resolves the
actual first-parent main commit that introduced it and its commit time. A separate
immutable runtime binding freezes the merged source, model hash and activation
time. The first legal session is strictly after both merge and freeze dates, using
the verified exchange calendar; its factual snapshot must be observed after 15:05
Shanghai time on that same session. No date is hardcoded. Missing a day does not
authorize later backfill. An initial invocation can freeze the namespace but cannot
publish a same-day forecast. Dry-run/preflight never freezes or writes anything.

Full forecasts store raw horizon predictions, population z-scores, horizon ranks,
fused score/rank, actual industry names, taxonomy, provenance, source commit and
model hash. They are immutable original publications, distinct from later
evaluation events. Duplicate runner retries skip fitting/publication and return
`NOOP_ALREADY_PUBLISHED`. Journal recovery restores the original byte-verified
publication after a crash. Independent `industry-forecast/<family_id>` namespaces
reuse atomic generations, OS mutexes, containment and hash checks. No old ETF
ledger is migrated. A source/model binding mismatch fails closed and requires a
separately reviewed operational source transition.

H10/H40/H120 count exchange sessions, not calendar days. Outcomes remain `PENDING`
until the exact maturity session and every required factual point are finalized.
There is no provisional result, carry-forward price, gap bridge or estimated close.
Evaluations append a reference to the immutable forecast hash and retain their own
finalized provenance. Revised published signal facts fail closed.

## Realized series and descriptive metrics

The admitted sources establish `RECONSTRUCTED_SWL2_EQUAL_WEIGHT`: exact-adjusted
constituent returns aggregated by the existing Source-C membership/coverage rules,
with the frozen V2 factual prefix preserved. Taxonomy provenance is official;
these price series **are not official Shenwan index bars**. Read-only inspection
of the V2 warmup metadata established 124 industry identities and the already
released warmup panel hash; it did not read performance or reopen OOS. No licensed
official/authorized SWL2 bar source is established in the current admitted adapters.
Local research admission grants no redistribution rights for upstream data.

For each matured date/horizon, Spearman RankIC correlates average-tie ranks of raw
predictions with the frozen scientific target. Display ranks use industry-code ties.
Top5 and Bottom5 means use raw realized industry returns selected by that horizon's
forecast rank; spread is their difference. Other diagnostics are realized Top5,
overlap count/rate and mean/median absolute display-rank error. Fused Top5 outcome
is a separate research diagnostic, not the horizon-specific model evaluation.
The baseline is the same-date frozen SWL2 universe equal-weight return.

Aggregates report mean/median RankIC, positive fraction, matured-date count and
mean spreads. Empty/undefined metrics are null. Constant prediction/target vectors
have null RankIC and are excluded from its valid-date denominator. Rolling means
use 20 matured dates; worst interval means minimum 20-date average spread. Fewer
than 20 dates has `INSUFFICIENT_FORWARD_EVIDENCE`; larger samples remain
`DESCRIPTIVE_ONLY_OVERLAPPING_OBSERVATIONS`. No p-value, confidence interval or
significance victory is claimed for overlapping horizons.

`COMMON_FORWARD_WINDOW` uses only genuinely published common dates with the same
matured horizon and compatible target provenance. It never combines historical
sealed baseline or consumed challenger OOS. Its COMMON_INDUSTRY_CROSS_SECTION_DIAGNOSTIC computes an additional shared-industry
intersection because the frozen universes are 107 and 124. Equal realized returns
are required (rtol 1e-10, atol 1e-12); primary metrics keep their original universe.
Any target mismatch fails closed;
the difference is descriptive, with no statistical winner declaration.

## Visual diagnostics

The dashboard shows current Top5, the entire actual admitted ranking, maturity,
full predicted/realized rank comparisons and common-date comparisons. Selected
matured Top5 industry paths start at 1.0 and are explicitly
`VISUAL_TREND_DIAGNOSTIC` / `NORMALIZED_RESEARCH_INDEX` /
`NON_TRADABLE_RESEARCH_DIAGNOSTIC`. Model scores and realized path levels use
separate views. Each signal's horizon outcome is independent; daily overlapping
forecasts are not chained into a pretend tradable performance curve.

No matured observations is an honest empty state. Historical evidence is never
repackaged into forward history. Optional CSI300 remains display-only and is not
needed for current evaluation.

## ETF retirement and operation

The historical ETF product layer established inadequate reliable executable
coverage relative to Level-2 granularity. That measured coverage is a
`HISTORICAL_PRODUCTIZATION_RESULT`, not current model ability. Mapping registries,
evidence, releases, runtime ledgers, certificates, consumed results and sealed
regions retain their bytes and identities. Current source does not expand mappings
or create ETF targets, intents, fills, account events or NAV points. Money, initial
capital, position caps, lot rounding and trading costs have no active role.

Legacy ETF commands fail closed with `SWL2_ETF_PRODUCTIZATION_RETIRED`; historical
writer regression is available only through an explicitly isolated synthetic
temporary namespace. Legacy APIs remain read-only, with retirement metadata.
The default dashboard uses `/api/industry-forecast/` and no ETF/account endpoint.

See [operations](operations.md), [deployment](deployment.md), [testing](testing.md)
and [source transition evidence](engineering/swl2-industry-forecast-transition.md).
Live deployment promotion, scheduler enabling and real forecast publication are
outside this engineering delivery. The scheduler template remains disabled.
