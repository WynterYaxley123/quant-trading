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
for signal date t and horizon h, target_i(t,h) = R_i(t,t+h) - mean_{j in FAMILY_FROZEN_UNIVERSE} R_j(t,t+h). Each R is the exact h-session compounded return. V1 centers over its 107 industries; V2 centers over its own dynamically verified frozen universe. Taxonomy-only industries and the common intersection never enter primary target centering.
Ridge alpha, factors, mature-label windows, raw/standardized specification, eligibility,
fusion and industry-code deterministic ties stay unchanged. V2 normally refits
coefficients using mature facts at alpha 30, 12 months, raw X and H10/H40/H120;
this is the frozen rolling fit, with no search or retuning. V1 retains alpha .01,
six months, raw X and its existing factors/fusion. Research budgets, phase gates,
Validation isolation and consumed/sealed Final-OOS rules remain in force.

## Publication and maturity

The [transition](../config/research/swl2-industry-forecast-transition.json) identifies
the change before merge without inventing its final SHA. The runner resolves the
verified first-parent main integration commit that introduced it and its repository-observed integration/committer timestamp (%cI), never the contributor author timestamp. A separate
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
reuse atomic generations, OS mutexes, containment and hash checks. Event bodies are immutable content-hashed objects (each at most 512 KiB);
generations contain only binding plus hash-linked references. The bounded index
allows 10,000 events / 16 MiB and never duplicates full bodies into every generation.
Reaching a hard limit blocks without deleting history. Namespace/ancestor symlink
escapes fail before reads, locks or writes. No old ETF ledger is migrated. A source/model binding mismatch fails closed and requires a
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
A raw realized-return mismatch fails closed. Centered scientific targets do not need to match between families because their frozen centering universes differ;
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

State-mutating/current-productization legacy ETF commands fail closed with `SWL2_ETF_PRODUCTIZATION_RETIRED`; historical
read-only inspection remains available; writer regression is available only through an explicitly isolated synthetic
temporary namespace. Legacy APIs remain read-only, with retirement metadata.
The default dashboard uses `/api/industry-forecast/` and no ETF/account endpoint.

See [operations](operations.md), [deployment](deployment.md), [testing](testing.md)
and [source transition evidence](engineering/swl2-industry-forecast-transition.md).
Live deployment promotion, scheduler enabling and real forecast publication are
outside this engineering delivery. The scheduler template remains disabled.

## Inventory and current API contract

The pinned classification artifact contains 134 current SWCLASS2021 Level-2 identities
and 63 PRE_2021_OR_UNMAPPED_LEGACY identities retained for historical parsing.
Current taxonomy size is therefore 134, independent of the model universe.
V1 excludes 27 current taxonomy identities; V2 excludes 10. These are
`NOT_IN_FROZEN_MODEL_UNIVERSE` and never become null/zero ranking rows.

Registry resolution reads and verifies each `frozen_universe_reference`: the unchanged
V1 COMMON_MODEL_UNIVERSE_V1 and the public identity-only V2 warmup projection,
which is bound to the original warmup metadata/panel hashes. It derives
`taxonomy_universe_size`, `model_universe_size`, `model_universe_hash` and excluded
identities. A forecast adds `forecast_row_count` and the exact transition binding.
No model-count constant in the dashboard is an authority. With no publication,
the API reports zero published rows, while model size remains visible.

Common comparison returns per-date shared counts, common RankIC, rank errors,
Top5 overlap and raw-return compatibility. The 107 shared identities are a
comparison-only diagnostic universe; family-native targets and primary metrics
remain unchanged. `centered_target_equality_required=false` is explicit.

Read-only API projections expose `event_hash` (the SHA256 of the original stored body) and `event_type`. These projection fields never rewrite or self-hash the immutable body. Mature evaluations additionally bind the consumed factual prefix through maturity; a later revision of any evaluated prefix fails closed.
