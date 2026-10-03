# ETF-Quant V2 research protocol

Status: **data admission blocked; date-specific protocol not frozen**. The result-free
search specification is preregistered in `research/etf_quant_v2/protocol.py` and its
hash is recorded in the [research summary](etf-quant-v2-development.md). There is no
Development-selected candidate. V1 remains the frozen forward baseline.

Formal data stays inside the existing CNEquity pin
`1650e384a3fd1f67a70144a489acc91432f1df27`. The effective research range is the
intersection of reliable calendar, historical membership, identities, exact stock
adjustments and bars. ETF bars, amount/liquidity and mapping evidence are additional
execution requirements. Nominal component ranges cannot substitute for this intersection.

The existing Shenwan adapter reconstructs monthly snapshots from a current interval
workbook. The pinned schema carries `as_of_date` and `fetched_at`, but does not prove
complete historical membership or historical publication/availability. No such
snapshot is admitted to formal V2 selection. Retain weaker observations privately as
an inventory, with `MEMBERSHIP_UNSUPPORTED`; never backstamp current constituents.

Before fitting any market candidate, require dated source-backed membership evidence,
complete historical-universe evidence, valid listing boundaries, finalized bars and
exact adjustments. Record a stable data snapshot hash, reconstruct V1 boundaries
from protocol metadata only, and freeze a separate date-specific V2 plan. No result
reader is used to establish a split. V1 sealed signals start on 2026-03-03; conservatively
exclude that date and all subsequent dates from V2 Development, including label outcomes.

The date utility reserves chronological Development, at least 120 maturity sessions,
120 Validation signals, a second 120-session isolation, 120 Final-OOS signals and a
120-session label tail. It rejects inadequate history rather than shortening windows.
Warmup and all 24-calendar-month training history must exist. Four common chronological
Development folds require at least 120 eligible signals each. Real eligibility and
phase dates remain unassigned until data is admitted.

| Dimension | Closed specification |
| --- | --- |
| Factors | Frozen V1 H10 five factors; frozen 19 factors for H40/H80/H120 |
| Target | Same-date cross-sectional excess forward return, retaining the ETF model vocabulary |
| Scaling | Raw; training-only column standardization (population std; reject zero/invalid variance) |
| Alpha | 0.001, 0.01, 0.1, 1, 10 |
| Window | 6, 12, 24 calendar months before each horizon's mature label cutoff |
| Family A | H10/H40/H120, 0.25/0.50/0.25 |
| Family B | H10/H40/H120, 0.30/0.60/0.10 |
| Family C | H10/H40, 1/3 and 2/3 |
| Family D | H10/H40/H80, 0.25/0.50/0.25 |
| Total | 120 specifications before feasibility pruning |

Compute factual trailing features once. Cache identity includes data/factor hashes,
date range and preprocessing configuration. The V2 pure fit uses the existing V1
numerical Ridge solver and prediction z-score without changing V1 defaults. Require
at least 30 mature training dates and complete dated cross sections; persist the
transformation for each fit. No future normalization or arbitrary factor search.

Before performance search, diagnose feature scales/correlation/eigenvalues/conditioning,
per-industry target autocorrelation, positive-sequence temporal ESS, horizon-block
counts, missingness and mature label counts. Compare raw alpha 0.01 against OLS using
coefficient norms/signs and prediction differences. Use moving-block uncertainty
(120 sessions, 1,000 replications, fixed seed); do not treat stacked industries as
independent temporal samples. Diagnostics are not sufficient proof of profitability.

Selection uses H40 daily RankIC and fixed top-five-minus-bottom-five spreads across
four preregistered chronological folds. Gate aggregate positivity, positivity in
three folds, maximum 60% positive contribution from one fold, worst-fold RankIC at
least -0.05, finite fits and coefficient norm CV at most 1. Included long horizons
must add at least 0.005 incremental RankIC and have prediction correlation below
0.95 against the short/medium combination. Prefer fold-median RankIC, fold-median
spread, worst-fold RankIC and coefficient stability, in that order. Effective ties
(RankIC 0.005, spread 0.001) prefer the baseline-like specification, then fewer
horizons, then deterministic candidate ID. No passing candidate means no freeze.

These criteria are a declared specification; a complete performance runner and
candidate freeze are blocked by admission. Synthetic model tests are engineering
evidence only. No Validation/Final-OOS metrics, portfolio result, epoch, signal,
intent, fill or NAV is created. Shadow integration needs a real Development-selected
candidate and separate future human launch authorization. V2 Shadow is not ready or started.
