# Shenwan sector-index research baseline preparation

Status: **SECTOR_INDEX_RESEARCH_ONLY**, `executable=false`, `strict_pit=false`,
`sector_data_admission=FIXED_CLASSIFICATION_RESEARCH`.

**NOT A TRADABLE PORTFOLIO BACKTEST. NOT LEVEL B. NOT ETF PERFORMANCE. NOT
EXECUTION VALIDATION.** This preparation does not run the final baseline or
fit Ridge. It separates the question “does the Shenwan Level-2 cross-sectional
ranking signal merit further research?” from “what could a tradable ETF
strategy earn?” Only the first question is in scope.

## Why execution remains blocked

Direct ETF mapping has zero `VALIDATED` primary mappings. Historical ex-ante
proxy coverage is zero, and a later published composition cannot be used at
an earlier decision. ETF→index continuity is not evidenced as known at every
historical decision. Fixed Shenwan classification is non-PIT; 159852 also
fails the independent single-sector purity screen. The formal executable
universe remains **0**. Neither ETF mapping, listing, prices, tradability,
proxy evidence, order/fill logic, nor ETF costs enter this signal study.

## Canonical data and quality

The read-only preparation entry point is
`python -m research.sector_index_baseline`, run in the existing
`quant-research` container. It uses only the SHA-verified Shenwan sector
catalog/panel and `sector_admission.json`; it neither downloads data nor
writes a report. Sector returns, when a later runner is authorized, must
come from canonical sector-index close prices.

The official-sector union calendar has **1,158** sessions in the common
`2021-12-13..2026-09-18` range. There are **124** Level-2 sectors. Only
**822** sessions have all 124 valid bars. The other **336** incomplete
sessions are observable as 801193 证券Ⅱ missing sessions; the last is
`2023-09-26`. The uninterrupted complete stretch begins `2023-09-27`.
The **20** `SOURCE_INVALID` OHLC rows remain unchanged and are outside this
common range; none is silently repaired. No forward fill, backfill,
interpolation, clamping, or row-shift of a missing sector endpoint is allowed.
Any missing/invalid bar propagates to eligibility, feature, label, coverage
and exclusion diagnostics.

## Independently audited signal-only eligible range

The old candidate range and the independently derived signal-only
*evaluation* range are both **2025-04-02..2026-03-27**, 239 sessions. The old
range was already sector-only; inspection found **no** ETF listing, mapping,
tradability, or next-session execution delay in its derivation. The audit
keeps its conservative all-124-sector continuity rule. This is an offline
evaluation-data range; future label availability must never be used by the
model when scoring at a historical decision date.

| Step | Derivation on the verified trading calendar |
|---|---|
| Raw common window | `2021-12-13..2026-09-18`, 1,158 sessions |
| Last incomplete session | `2023-09-26`; next all-sector-valid session `2023-09-27` |
| First eligible signal | `2025-04-02` (calendar index 799) |
| Long-horizon purge | Last training-origin date = signal index − 120 = `2024-09-30` |
| Six-month rolling train start | `2024-09-30` − six calendar months = `2024-03-30`; first session `2024-04-01` |
| Long-horizon training count | 123 sessions with complete 19-factor features and realized labels, above the frozen minimum 30 |
| Feature warmup | 120 prior sessions before first training session, beginning `2023-09-27` |
| Why not `2025-04-01` | Its warmup would start `2023-09-22` and include three incomplete sessions |
| Final eligible signal | `2026-03-27` (calendar index 1037) |
| Longest realized-label endpoint | Final signal + 120 sessions = common end `2026-09-18` |

The 10/40/120 horizons are **prediction/label lengths**, not an ETF holding
period. At the first signal, the 10-session training cutoff is `2025-03-19`
and the 40-session cutoff is `2025-02-05`; each horizon has its own six-month
window and purge. Read-only factor/label checks found all **124** sectors
feature-ready on the first signal and **118/119/123** valid training dates for
short/medium/long respectively. No Ridge fit or return evaluation was run.
The longest horizon controls the conservative range edges.
An additional ETF next-session delay is **not** deducted. The 120 sessions
after the final signal are for *realizing labels* in retrospective evaluation,
not for an execution fill.

For a sector with valid close prices on both endpoints,
`label_h(t)=close[t+h]/close[t]-1`. At prediction time `t`, training origins
must end at or before `t-h`; `close[t+h]` is never exposed to the model.
Missing endpoints produce unavailable labels, not shifted endpoints or filled
prices. For date-level performance evaluation, overlapping forward labels
must not be presented as independent observations. No Dev/Validation/OOS
split or final OOS lock is made here.

## Frozen signal model and future runner boundary

The preparation reads existing constants without modifying strategy core:
19 price factors, Ridge `alpha=0.01`, 10/40/120 session horizons,
0.25/0.50/0.25 fusion, Top5, six-calendar-month rolling training, and at
least 30 valid training days. Target: **absolute forward close-to-close
sector-index return**. RSRS is excluded from training; macro and flow are
disabled. RiskState is record-only. These are not tuned results.

A later authorized runner should:

1. Read only SHA-verified canonical Shenwan sector OHLCVA and the 124-code
   catalog. Preserve the common calendar and missing-date diagnostics.
2. On each chosen signal date, construct sector frames using prices no later
   than that date; apply existing horizon-specific label cutoff and rolling
   training rules. Require all three horizons before fusion. Keep Top5 tie
   ordering deterministic and resolve sector names from the catalog.
3. Copy only signal outputs into `SectorResearchResult`: dates, rankings,
   selected sector codes/names, model/horizon/fused scores, later-realized
   forward sector returns, coverage, missing/invalid diagnostics, and
   metadata. The optional research equity curve and theoretical turnover
   remain `null` in this preparation.
4. Do **not** promote the core's optional ETF candidates or score-derived
   `sector_weights` to orders or an executable portfolio. No Hikyuu or
   RQAlpha execution path is involved.

`SectorResearchResult` is a separate, non-executable output contract, not a
Hikyuu `BacktestResult`. Future research reports belong under
`reports/research/shenwan_sector_index/<run_id>/`, never under
`reports/backtests/`. The planned output is one metadata record plus dated
ranking/score, realized-forward-return, coverage and diagnostic records;
`research_equity_curve` and `turnover` may stay `null`. No such report is
generated by this preparation.

If a later study explicitly defines a sector-selection cadence and holding
convention *before* observing results, a Top5 equal-weight sector-index
return may be reported as `SYNTHETIC_SECTOR_INDEX_RETURN`. It remains
`executable=false`, contains no ETF commission, slippage, minimum fee,
orders or fills, and cannot claim achievable ETF performance. Prediction
horizons alone do not define a portfolio holding period. Until that separate
methodology is fixed, an equity curve is withheld rather than fabricated.

This baseline can evaluate ranking quality and the relationship between
sector-index scores and subsequently realized sector-index returns under
the stated fixed-classification limitation. It cannot establish actual ETF
returns, achievable turnover/costs, execution reliability, or strict
point-in-time classification validity.
