# ETF proxy mapping and temporal admission policy

Status: **historical point-snapshot diagnostics; no historical proxy is admitted**. This
policy does not change the strategy, direct mapping evaluator, or the formal
ETF execution universe. It does not authorize LEVEL B or a backtest.

The 2025–2026 re-admission and publication-time audit is in
[`shenwan_historical_proxy_readmission.md`](shenwan_historical_proxy_readmission.md).
The earlier current-only candidate table below is retained as its acquisition
baseline, not as a statement that no historical report has since been found.

## Two independent mapping paths

`DIRECT_MAPPING` requires official ETF/index-to-Shenwan-Level-2 equivalence,
a validated primary relationship and historical effective timing. Its current
`VALIDATED` count remains **0**; `DERIVED_STRONG_PROXY` is never renamed to
`VALIDATED`.

`PROXY_MAPPING` is a separately reported, derived ETF execution exposure. It
does **not** claim that the ETF tracks a Shenwan index. The local Layer-2 file
has zero `OFFICIAL_DIRECT_EQUIVALENCE` rows. Its PCF/Top10 comparisons are
`DERIVED_PROXY_EVIDENCE`, not official direct equivalence. The direct
`MappingEvidence` rows and `mapping_admission()` are unchanged; the proxy
audit lives in the existing admission entrypoint and never feeds the direct
resolver or order-generation logic.

The current observed status describes only the supplied composition sample:

| Evidence | Descriptive current status rule | Limitation |
|---|---|---|
| Official ETF PCF basket | `PROXY_CURRENT_STRONG` only when ≥90% of observed names are in the candidate Level-2, no unclassified names, and at most 10% observed other Level-2 names | PCF creation/redemption basket is neither ETF holdings nor full index constituents; present files lack constituent index weights |
| Official index Top10 | `PROXY_CURRENT_STRONG` only when ≥80% of observed Top10 names and ≥85% of observed Top10 weight are in the candidate Level-2, with at most one unclassified name | Both percentages describe only Top10, not the full index |
| No constituents | `PROXY_CURRENT_INSUFFICIENT` | No current exposure conclusion |

These are **descriptive labels, not admission thresholds**. They replace no
missing weight with zero and do not inherit the earlier 70% description rule.
`PROXY_CURRENT_MIXED` remains diagnostic only. A strong current label alone
never authorizes historical execution.

## Point-in-time rule for a research signal date *t*

The audit keeps three dates separate: (1) when the ETF→index relationship was
effective, (2) when composition was observed and made available, and (3) the
dates for which proxy validity is actually proven. An earliest prospectus or
official listing date is **not** an evidenced relationship effective-from.
`NO_CHANGE_EVENT_FOUND_IN_SEARCHED_OFFICIAL_RECORDS` is **not** proof that the
relationship continued unchanged.

`historical_proxy_admissible(t)` is true only if **all** conditions hold:

1. The row is `PROXY_MAPPING`, not a direct-equivalence claim. Official index
   methodology is available **and its version/effective interval is proven for
   t**, with publication no later than the signal. A current official
   basic-info page alone is insufficient.
2. Official **full index constituents with weights** establish the candidate
   industry's composition. An ETF PCF basket and Top10 excerpt can support a
   diagnosis but cannot substitute for the full index under this policy.
3. For the complete index, both candidate Level-2 name share and weight share
   are at least **90%**, no constituent is unclassified, and at most 10% of
   names belong to other Level-2 sectors. These conservative, pre-backtest
   thresholds are policy choices, not fitted to returns. The other-sector
   distribution and thematic breadth must be disclosed; a broad theme is not
   silently made single-sector by its name.
4. Composition `as_of_date ≤ t` and documented `available_at ≤ t`. The source
   must explicitly cover t through an official valid-from/to interval; a
   point snapshot without such an interval covers **only its own date**. For
   same-day evidence, publication **before the signal** must be proven. A
   later download or current snapshot cannot validate an earlier t.
5. The ETF→index `relationship_effective_from ≤ t` is independently evidenced,
   any end date is respected, and continuity is affirmatively
   `PROVEN_CONTINUOUS` **through t** using documents already available at t. A search that
   found no change notice is not enough.
6. The constituent-to-Shenwan-Level-2 classification is historically valid
   and available by t. The present 2026-09-23 `component_stocks` snapshot is
   fixed/current evidence, not historical PIT classification.

For methodology, relationship and classification records too, a same-day
date without proof of publication before the signal is insufficient.

Even if these evidence gates eventually pass, **daily ETF availability and
tradability must still be checked before execution**. The proxy execution
resolver is deliberately disabled in this phase. The present sector data
admission remains `FIXED_CLASSIFICATION_RESEARCH`, `strict_pit=false`; proxy
evidence cannot upgrade it to strict PIT.

## Pre-acquisition current-only evaluation of the six local candidates

At this pre-acquisition baseline, all composition dates below are 2026-09-23
where a source exists; the source was first retrieved that day. All six had only
`EARLIEST_RELATIONSHIP_CONFIRMED_CONTINUITY_INCOMPLETE`. Their candidate
listing/tradable dates are kept separate from formal proxy effective dates,
which remain null. No historical composition snapshot in the sector-only
research interval (2025-04-02..2026-03-27) was then present. The later
periodic-report snapshots are audited separately above.

| ETF → candidate L2 | Evidence coverage | Observed concentration | Current status | Historical status |
|---|---|---|---|---|
| 512480 → 801081 半导体 | SSE PCF basket, 87 names | 80/87 = 91.95% names; index weights unavailable | `PROXY_CURRENT_STRONG` | insufficient; not admissible |
| 512880 → 801193 证券Ⅱ | SSE PCF basket, 49 names | 49/49 = 100% names; index weights unavailable | `PROXY_CURRENT_STRONG` | insufficient; not admissible |
| 515790 → 801735 光伏设备 | SSE PCF basket, 50 names | 32/50 = 64%; 18 names spread across 电力、其他电源设备Ⅱ、电网设备、自动化设备、金属新材料 | `PROXY_CURRENT_MIXED` | excluded from single-sector proxy acquisition priority |
| 159840 → 801737 电池 | no constituent file | no observed concentration | `PROXY_CURRENT_INSUFFICIENT` | insufficient; defer acquisition priority |
| 159852 → 801104 软件开发 | CSI official Top10 only | 8/10 names; 87.5% of observed Top10 weight | `PROXY_CURRENT_STRONG` | insufficient; not admissible |
| 159883 → 801153 医疗器械 | CSI official Top10 only | 9/10 names; 95.19% of observed Top10 weight; one unclassified | `PROXY_CURRENT_STRONG` | insufficient; not admissible |

Current strong count **4**, mixed **1**, insufficient **1**. Formal current
admissible **0**, historical backtest admissible **0**, direct validated **0**,
formal executable universe **0**. All six remain in a **candidate diagnostic
universe** only. In particular, the 2026-09-23 observations cannot be used
for any date from 2025-04-02 through 2026-03-27.

## Minimum next-round evidence request, not an instruction to download now

This is the original pre-acquisition request. The later periodic reports fill
some observation-date gaps but do not replace archived full-index interval or
publication-time evidence; see the re-admission audit linked at the top.

The official CSI basic-info files for H30184, 399975, 930601 and H30217
describe **semiannual** index adjustment. They do not specify the historical
effective days or rule out temporary adjustments. Do not sample at the
strategy's 10-session rebalance cadence. For **each** of the four current
strong candidates, request the following official evidence covering the
entire 2025-04-02..2026-03-27 interval:

| ETF / index | Historical composition source and minimum coverage | Full constituents / weights? |
|---|---|---|
| 512480 / H30184 | CSI archived constituent-and-weight files for the interval effective on 2025-04-02 and every subsequent semiannual or temporary change through 2026-03-27; SSE dated PCFs may corroborate ETF basket only | Yes / yes |
| 512880 / 399975 | Same CSI interval files and event history; SSE dated PCFs only corroborate the 2026 basket | Yes / yes |
| 159852 / 930601 | CSI full 30-name historical constituent-and-weight files at those intervals; historical Top10 alone is never sufficient | Yes / yes |
| 159883 / H30217 | CSI full historical constituent-and-weight files at those intervals; historical Top10 alone is never sufficient | Yes / yes |

Conditional minimum per index is **three interval snapshots**: the one
effective immediately before/on 2025-04-02, the next scheduled adjustment,
and the following adjustment that carries through 2026-03-27. This minimum
assumes the stated semiannual cycle and **no** temporary changes; official
effective-day and publication records must confirm the intervals. Every
additional temporary adjustment requires another dated snapshot. Do not
invent June/December effective dates from “semiannual.” Also obtain the
official methodology version effective in each interval, index adjustment
notices/change logs, and timestamps sufficient to prove each file was
available before the applicable signal.

For each ETF, separately obtain official fund/index tracking agreements or
dated issuer filings confirming the relationship start **and continuity**
through the interval. A negative change-event search is insufficient. Obtain
historically dated Shenwan Level-2 constituent assignments (and their
publication/effective timing) for **every** index constituent in each
interval. This is required even if all four full-index files become available:
the current fixed classification cannot validate past industry membership.

515790's observed multi-sector breadth makes it unsuitable as a single-L2
proxy under the current policy; do not prioritize a historical harvest merely
to increase mapping coverage. 159840 first needs official current
methodology and full constituents/weights to establish whether it is even a
plausible narrow proxy. That still would not solve its historical timing, so
it is lower priority than the four current-strong candidates.
