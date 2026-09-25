# Four-proxy historical evidence: availability-time re-admission

Status: **PROXY MAPPING NOT ADMISSIBLE**. This is an offline data-admission
audit, not a backtest, LEVEL B run, or strategy-return assessment. No strategy
core, Docker image, dependencies, original evidence, or Hikyuu data changed.

Reproduce with `python scripts/data/audit_historical_proxy_evidence.py` in the
existing `quant-research` container. It verifies all 67 indexed raw files by
SHA-256 and size; reconciles the 19 historical source rows, 12 composition
rows, official URLs, and PDF cover dates; then emits
`data/processed/shenwan_etf_mapping/four_proxy_{publication_audit.csv,session_audit.csv,readmission.json}`.
The report-date transcription is tracked in
[`shenwan_historical_proxy_publications.csv`](shenwan_historical_proxy_publications.csv).
All 12 dates were read from the official PDF first-page `送出日期` and checked
against the date in the official SSE/CNINFO source URL. All source files were
retrieved locally on 2026-09-23; that retrieval time is **not** substituted for
historical availability. Six `four_proxy_historical_sources.csv` `as_of_date`
fields contain the SSE URL publication date rather than the composition date,
and six CNINFO rows have no `as_of_date`; the reviewed PDF/report dates, not
those sidecar fields, are used. Raw files and source rows were not rewritten.

## Publication evidence and temporal semantics

| ETF | 2024-12-31 report published | 2025-06-30 report published | 2025-12-31 report published |
|---|---|---|---|
| 512480 | 2025-03-31 | 2025-08-29 | 2026-03-31 |
| 512880 | 2025-03-29 | 2025-08-30 | 2026-03-30 |
| 159852 | 2025-03-28 | 2025-08-29 | 2026-03-30 |
| 159883 | 2025-03-28 | 2025-08-28 | 2026-03-31 |

Each date is day-level evidence only; no intraday publication time was proven.
For a signal on the same date, the audit conservatively requires earlier-day
publication. The composition `snapshot_as_of_date` is the report period end,
not the publication date. The 2025-12-31 reports were **not published by the
candidate-range end of 2026-03-27**. The ETF `指数投资` sleeves establish their
observed holdings on the snapshot date. They are neither full-index
constituent-and-weight archives nor proof that the same basket held throughout
a prior or subsequent semiannual interval.

The index calendar provides four regular announcement/effect pairs:

| Announced | Effective after close | First affected trading session |
|---|---|---|
| 2024-11-29 | 2024-12-13 | 2024-12-16 |
| 2025-05-30 | 2025-06-13 | 2025-06-16 |
| 2025-11-28 | 2025-12-12 | 2025-12-15 |
| 2026-05-29 | 2026-06-12 | 2026-06-15 |

Advance notice proves that an adjustment date could be known. The saved
notices are broad CSI announcements with **partial** attachments; they do not
prove complete constituents/weights for these four specific indices or the
ETF sleeve's concentration before a decision. The historical CSV's new
interval beginning *on* 2025-06-13 or 2025-12-12 also ignores the notice's
“after close” semantics. It is retained as a nominal claim, never as an
admitted validity interval.

## Corrected denominator and coverage

The former `1436/1436` is `4 ETF × 359` **half-open calendar days**. It is not
1436 trading sessions. The project candidate range 2025-04-02 through
2026-03-27 has **360 inclusive calendar dates**, **239 trading sessions**, and
**956 ETF×sessions**. The former half-open arithmetic omitted the final
research date and treated a single snapshot in each nominal interval as if it
covered every date in that interval. This is not point-in-time coverage.

| ETF | Published prior snapshot present, but no interval proof | Ex-ante point coverage | Ex-post *point* diagnostic | Strict admitted sessions |
|---|---:|---:|---:|---:|
| 512480 | 239/239 | 0/239 | 2/239 | 0/239 |
| 512880 | 239/239 | 0/239 | 2/239 | 0/239 |
| 159852 | 239/239 | 0/239 | 2/239 | 0/239 |
| 159883 | 239/239 | 0/239 | 2/239 | 0/239 |
| Total ETF×sessions | 956/956 | 0/956 | 8/956 | 0/956 |

The two ex-post diagnostic dates per ETF are **2025-06-30 and 2025-12-31**;
their reports were published later. They do not imply an executable interval.
On 2025-04-02 all four 2024 reports had been published, so an earlier sleeve
observation and a dated ETF→index relationship statement were available.
Neither proves that the composition/relationship continued through that
decision date. Thus none can legitimately be selected for formal proxy
execution on 2025-04-02. Each
`earliest_ex_ante_proxy_admissible_date` is `null`.

## Purity is independent of timing

The pre-backtest numeric screen remains at least 90% candidate Level-2 **of
all observed names**, at least 90% candidate weight, at most 10% other-sector
names, and **zero unclassified names**. It is not fitted to strategy returns.
Even a numeric pass in an ETF sleeve is not a formal full-index/PIT pass.

| ETF → candidate L2 | Snapshot numeric passes | Reason and final status |
|---|---:|---|
| 512480 → 801081 半导体 | 3/3 | 90.80–91.86% names, 94.53–95.93% weight; snapshot-only, no interval/PIT; not admitted |
| 512880 → 801193 证券Ⅱ | 2/3 | First report has 1 unclassified name carrying 5.53% weight, despite `candidate_l2_count_share=100%` **of classified names**; later two 100/100; not admitted |
| 159852 → 801104 软件开发 | 0/3 | 56.67–60% names and 65.04–70.46% weight; fails single-sector purity, not merely timing; not admitted |
| 159883 → 801153 医疗器械 | 0/3 | First weight 91.14% but 1 unclassified; later weight 89.09/89.12% and 1/2 unclassified; not admitted |

Only 512480 and 512880 pass the numeric screen on the two within-range
ex-post point dates. That is a diagnostic, **not** `FIXED_PROXY_RESEARCH`
interval admission. A point observation cannot be extended across trading
sessions. Both `proxy_ex_ante_candidate_start/end` and
`fixed_proxy_research_start/end` remain `null`.

The 2024 reports establish that an ETF→index relationship was *documented*
before 2025-04-02 for all four ETFs. The later set of reports supports an
**ex-post** continuity narrative. It does not establish affirmative
`relationship_continuity_known_at_t` through every historical decision, so
that stricter field is false for all 239 sessions per ETF. Absence of a found
change notice is not affirmative continuity proof.

Formal direct mapping remains `ETF_MAPPING_NOT_ADMISSIBLE`; ex-ante proxy
mapping is `NOT_ADMISSIBLE`; the formal executable universe is **0**. The
Shenwan classification comparison remains `FIXED_CLASSIFICATION_RESEARCH`,
`strict_pit=false`: **NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST**.
Historical ETF bars/tradability cannot override the evidence gate.

Further acquisition would be required for admission, but is **not authorized
in this audit**: versioned, archived full-index constituents/weights with
effective and publication times; index-specific adjustment history (including
temporary changes); relationship documents affirmatively continuous and
available by each decision date; and historical Shenwan L2 assignments with
their own effective/publication timing. For 159852, additional timing alone
cannot repair the observed single-sector purity failure. No threshold is
relaxed to increase coverage.
