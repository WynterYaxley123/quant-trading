# SWL1-Ridge-V1 frozen protocol

This is a separately authorized **Shenwan Level-1** Ridge generation, independent
of both frozen SWL2 generations. Its role is `INDUSTRY_FORECAST_RESEARCH`; ETF
productization is `NOT_STARTED`. The [protocol](../../config/research/swl1-ridge-v1-protocol.json)
was committed before the first real Development metric. Its SHA256 is
`3d148ba7adc4846cd3fa951a46dc224f34a5070a8dd5cfa50523bca4a0c5222e`.

## Factual admission

The official [SWCLASS2021 code table](https://www.swsresearch.com/swindex/pdf/SwClass2021/SwClassCode_2021.xls)
was parsed dynamically: **31** current Level-1 identities. Parent assignments use
the explicitly named parent rows, including an out-of-order child row, rather
than code-prefix guesses. The [publisher's version announcement](https://wxweb.swsresearch.com/swsreport/2021_08/328340.pdf)
supports the 2021-07-31 version boundary. Earlier classification is excluded.
The current table's Level-2/3 inventory matches the previously pinned 2021 table.
This establishes version-specific reconstruction, not proof of every historical
publication or independent historical assignment accuracy.

The read-only pinned CNEquity source is
`1650e384a3fd1f67a70144a489acc91432f1df27`. Its official stock-classification
workbook supplies 12,925 effective-dated spells across 5,930 symbols. Latest
effective spell at each date is resolved through explicit SWCLASS2021 hierarchy.
Legacy/unmapped spells remain excluded. Unknown listing dates cannot be invented.
Provider receipts and source hashes are verified; no upstream or runtime is edited.

Membership evidence follows existing terminology: A requires contemporaneous
availability and completeness; B requires verified historical reconstruction;
C is retrospective reconstruction; D is unsupported and excluded. Here A=0,
B=0, C=6,515,140, D=1,406 **listed stock/exchange-session rows**. Observation in
October 2026 does not imply historical availability. Annual rosters were not used
to promote industry assignment confidence. Confidence remains `RECONSTRUCTED`.

Primary series is `RECONSTRUCTED_SWL1_EQUAL_WEIGHT`, never an official index bar.
For each adjacent exchange session, exact source event factors are joined backward
as-of and multiplied by closes. Positive adjacent volume, valid adjustment,
listing/delisting intervals and finite returns are required; absolute stock moves
above 50% are quarantined. At least five valid constituents and 80% coverage are
required against the admitted classified denominator. Suspensions/missing facts
stay missing; no future factor, interpolation or forward-fill is introduced.

The recursive series cannot restart after a factual gap. All post-seed industry
days must therefore pass admission. **30** industries are frozen; 综合 (`510000`)
is excluded for one invalid industry day. This decision used coverage only, before
performance. The preliminary all-31 feasibility calculation was not a research
trial; its private factual audit is retained. No market matrices enter Git.
See [feasibility aggregates](../../reports/research/swl1_ridge_v1/data_feasibility.json),
[identity universe](../../config/research/swl1-ridge-v1-universe.json) and
[factor mechanics audit](../../reports/research/swl1_ridge_v1/factor_audit.json).

## Frozen model and chronology

All existing 19 close-based factors apply to Level-1 reconstructed series. They
use backward windows and retain NaN warmup. No new factors or IC-guided exclusions
were introduced. RSI's 0–100 scale differs from fractional returns and bounded
position factors: scaling is **STANDARDIZED**, fitted on training rows only.
Constant training feature scales use one. Raw versus standardized is not searched.

H10/H40/H120 targets are exact compounded raw industry returns minus their complete
frozen-universe mean at the same (t,h). Incomplete cross sections are invalid.
Ridge intercept is unpenalized; each horizon has its own mature cutoff T−h,
12/24 calendar-month lower boundary and at least 30 complete training dates.
No hidden shorter window is permitted. Fusion remains population-z weighted
0.25/0.50/0.25. Top5/Bottom5 use stable industry-code ties.

Search is exactly 5 alphas (0.1/1/10/30/100) × 2 windows (12/24 months) ×
2 policies (A: 5/19/19 factors; B: 19/19/19) = **20**. Both windows share the
24-month-eligible Development interval for comparable selection. Dates were
chosen using availability counts only. The 252-signal policy cannot meet minimum
Development coverage; the preregistered 126-signal fallback applies.

| Phase | First signal | Last signal | Eligible signals |
| --- | --- | --- | --- |
| Development | 2023-08-02 | 2024-03-25 | 156 |
| Purge | after Development | before Validation | 120 exchange sessions |
| Validation | 2024-09-20 | 2025-04-01 | 126 |
| Purge | after Validation | before Final OOS | 120 exchange sessions |
| Planned Final OOS | 2025-09-24 | 2026-04-08 | 126 |

Factual history is 2021-08-02–2026-09-30 (1,253 exchange sessions); latest fully
mature H120 signal is 2026-04-08. Purges ensure previous phase's H120 labels end
strictly before the next signal phase. Calendar days are never substituted.

## Selection, access and failure

Development admission requires ≥90% valid phase signals at all horizons, no mean
RankIC below −0.02, and intact provenance/universe contracts. Selection maximizes
0.25/0.50/0.25 mean horizon RankIC. Primary numerical ties (1e−12) prefer the
higher minimum horizon mean, shorter window, larger alpha and lexical policy.
One candidate is byte-frozen before one exclusive Validation claim.

Validation requires all: composite and median weighted daily horizon IC >0,
weighted positive fraction ≥0.55, weighted raw Top5−Bottom5 spread >0, at least
two positive horizon means, none below −0.03, at least 3/4 positive chronological
equal-count blocks, sufficient samples and no integrity failure. Failure closes
V1 permanently, leaves Final OOS unopened and disables forward publication.

Only PASS may seal Final OOS with candidate/protocol/data/universe/source lineage.
An exclusive consumed claim precedes calculation; retries cannot reopen it.
The frozen protocol defines STRONG_POSITIVE/POSITIVE/MIXED/NEGATIVE diagnostics.
They are directional labels, not significance claims. Daily horizons overlap;
independent statistical confidence remains LIMITED, with no IID p-value gate.
Only PASS plus positive Final OOS could establish forward research eligibility.
No scheduler, official forward event, ETF mapping, portfolio or broker is created.

See [actual closed result](swl1-ridge-v1-results.md). Public source reproduces
contracts and synthetic tests; the private factual panel requires authorized
local data and matching hashes. MIT source licensing grants no data rights.
