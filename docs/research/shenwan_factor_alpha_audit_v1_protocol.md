# Shenwan factor alpha audit V1 preregistration

Status: **PREREGISTERED, NOT RUN**. This document and
`research/factor_alpha_audit_v1_protocol.py` freeze the complete Factor Alpha
Audit V1 design before any audit result is calculated. They do not authorize
the audit run itself; the run requires the separately recorded post-commit
execution step. The protocol identity is
`factor_alpha_audit_v1_protocol_hash` (frozen constant in the protocol
module; also recorded in every audit `metadata.json`).

## 1. Purpose and non-purpose

This audit is **diagnostic research**. It measures whether the frozen 19
price factors themselves contain cross-sectional predictive information on
Development data, and characterizes sign, temporal stability, horizon decay,
redundancy, and missingness.

This audit is explicitly **NOT**: model tuning, feature selection, a new
candidate search, a promotion contest, direction optimization, or a
portfolio/backtest exercise.

Hard prohibitions during and after this audit, until separately authorized:
deleting factors, flipping factor signs, redefining momentum, changing
horizons, Ridge alpha, train window, fusion weights, TopK, trying other
models (ElasticNet / LightGBM / XGBoost / CatBoost / neural nets),
automatic factor-combination search, highest-IC subset selection, creating
D4/D5/D6 candidates, opening Validation, opening Final OOS, portfolio
backtest, ETF mapping, QMT execution, Dashboard/API changes.

Any t-statistic reported anywhere in this audit is **DESCRIPTIVE ONLY** and
must never drive selection or promotion. No p-value ranking, t-threshold
promotion, or multiple-testing winner selection is performed.

## 2. Research identity

Unchanged from the frozen baseline: `SECTOR_INDEX_RESEARCH_ONLY`,
`phase=DEVELOPMENT`, `executable=false`, `tradable=false`,
`strict_pit=false`, `FIXED_CLASSIFICATION_RESEARCH`, universe `U0_FIXED_124`
(124 Shenwan Level-2 sector indexes), frozen sector snapshot
`872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`.
ETF execution `DISABLED / NOT ADMISSIBLE`, synthetic portfolio `DISABLED`,
LEVEL B `DISABLED`. Validation `SEALED`; Final OOS `SEALED`. It remains
**NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST**, **NOT VALIDATED
ALPHA**, and **NOT TRADABLE PERFORMANCE**.

Metadata of every run must include `NO_PARAMETER_SELECTION=true`,
`NO_FACTOR_SELECTION=true`, `DIAGNOSTIC_ONLY=true`.

## 3. Audit sample

Only formal Development signal dates `E001-E100` (ordinals 1-100 of the
frozen Policy C eligible signal calendar) are used. The date range is read
from the split policy artifact at run time (expected `2025-04-02` to
`2025-08-26`, asserted but never hardcoded as input). Purge 1, Validation,
Purge 2, and Final OOS dates are forbidden as signal dates.

Forward label realization for Development signals may read prices after the
signal date **only** to realize the label endpoint, exactly as in the frozen
baseline adapter. Label endpoints must stay inside the audited label window
ending at `development_last_120_label_endpoint` (inside Purge 1, before
E221); no Validation or Final OOS price may enter factor or label frames.

All evaluation requests must pass `guard_evaluation("development", ...)`.
Any non-Development ordinal is a hard error.

## 4. Factors (frozen)

The audit uses exactly the frozen 19 price features in the frozen order
`d5, d10, d20, d60, d120, p5, p10, p20, p60, p120, align, v5, v20, vc, rev5,
rev10, dd20, dd60, rsi` (= `TRAIN_FEATURES_PRICE` = `EXPECTED_FEATURES`,
frozen feature hash
`ee1b70d4623b566451eae8c8a0c4878720049e506b05f4cd94b9d7c806e54c59`).

Factor values must be **identical** to the Ridge pipeline's factor inputs:
same implementation (`compute_all_price_features` via the frozen strategy
core `build_panel`, `include_rsrs=False`), same per-signal-date visible
window construction (`warmup = first_train - FEATURE_WARMUP` sessions,
window `[warmup, signal]`), same column order. No second factor definition
may be written. A mismatch is `FACTOR_IDENTITY_BLOCKER` (see §10).

Non-finite factor values are treated as **missing**: excluded from that
date's pairs. Missing values are never imputed, filled, zeroed, or
interpolated.

## 5. Audit labels (frozen)

Horizons: 10, 40, 120 trading sessions. Label
`label(t,s,h) = close[t+h,s]/close[t,s] − 1` using the common project
trading calendar and the `t+h` endpoint semantics of the frozen baseline
target implementation (`make_forward_label`). If a sector has no bar at the
endpoint, the endpoint is **never** moved and no fill/interpolation occurs;
the label is missing and that (date, sector, horizon) pair is excluded.

Labels are absolute forward returns for all audit statistics. The audit does
not demean, standardize, invert, or otherwise transform factors or labels.

## 6. Single-factor IC / RankIC audit

For every factor (19) × horizon (3) × Development signal date (100):

- Valid pair = finite factor value AND finite forward label at that
  horizon. The date is **skipped** for that factor×horizon if valid pairs <
  `MIN_VALID_SECTOR_PAIRS = 30` (recorded with reason, never silently
  dropped).
- Pearson cross-sectional IC and Spearman rank IC (average ranks for ties)
  are computed on the valid pairs, per date, with **signed** results.
- Zero cross-sectional variance in factor or label on a date yields a null
  metric for that date with reason, not a fabricated 0.
- Negative RankIC is a possibly stable negative-direction signal. Results
  are never multiplied by −1, and no post-hoc direction optimization exists
  anywhere in this audit.

Per factor × horizon the summary reports validDates, skippedDates, and for
both IC and RankIC: mean, median, std (population, ddof=0, consistent with
the frozen baseline aggregation), min, max; plus
positiveRankIcDates / negativeRankIcDates / zeroRankIcDates (zero means
exactly 0.0), Q5−Q1 mean (§8), quantile monotonicity (§8), and a
descriptive t-stat `mean/(sample_std(ddof=1)/sqrt(n))`, marked
DESCRIPTIVE ONLY (null when n<2 or sample std is 0).

## 7. RankIC stability blocks (frozen)

Block layout is fixed before results and never adapted to market regimes:

| Block | Ordinals | IDs |
| --- | --- | --- |
| 1 | 1-25 | E001-E025 |
| 2 | 26-50 | E026-E050 |
| 3 | 51-75 | E051-E075 |
| 4 | 76-100 | E076-E100 |

Per factor × horizon × block: block mean RankIC, block median RankIC, valid
dates in block. Also per factor × horizon: full Development mean RankIC and
its sign, and `sameSignBlockCount` = number of blocks whose mean RankIC has
the same sign as the full Development mean (strictly positive product;
exactly-zero block means never count; if the full mean is null or exactly 0
the count is null). The count is out of 4 blocks. **Descriptive diagnostic
only** — never an automatic promotion or removal rule.

## 8. Quantile / group return audit

Per Development date, per factor, per horizon, on the same valid pairs as
§6 (date valid iff ≥30 pairs):

1. Sort sectors by raw factor value **ascending**.
2. Deterministic tie-break: sector code ascending.
3. Assign exactly 5 contiguous quantiles Q1..Q5 (Q1 = lowest factor
   values). Sizes are as equal as possible: each gets `n//5`, and the first
   `n%5` quantiles in Q1→Q5 order each receive one extra element. Quantile
   count is never changed after results.
4. Per quantile: mean forward return of its members. Q5−Q1 = Q5 mean − Q1
   mean on that date. Original direction is preserved; no statement about
   whether high or low factor values "should be bought" is derived or
   applied.

Per factor × horizon: aggregate Q1..Q5 means and Q5−Q1 mean are equal-date
means of the per-date values over valid dates.
`quantileMonotonicity` = Spearman correlation between quantile index [1..5]
and the five aggregate quantile mean returns. This is a **descriptive**
measure only and never drives promotion.

## 9. Factor redundancy audit

Not pooled correlation. For every Development date and every ordered factor
pair (including identical pairs on the diagonal), compute the cross-sectional
Spearman correlation between the two factor values over sectors valid for
**both** factors that date (ties averaged). A date is valid for a pair if
≥ `MIN_VALID_SECTOR_PAIRS = 30` common finite sectors; otherwise that
pair-date is skipped. Per pair the audit reports the mean of the daily
Spearman correlations and the count of valid dates.

A pair is flagged redundant iff `|mean daily Spearman| >= 0.80`
(`REDUNDANCY_THRESHOLD = 0.80`, frozen here before results). The matrix
keeps the diagonal for completeness; redundancy flags cover **distinct**
factor pairs only (factor_a precedes factor_b in the frozen order). Flags
are diagnostics only; no factor is automatically deleted.

## 10. Missingness / coverage audit

Per factor (and per factor×horizon) report: Development dates total (100),
valid factor observations (finite values over the 100×124 grid), missing
observations, valid sectors per date (min / median / max), valid
factor-label pairs summed over dates, and skipped IC dates (dates with
<30 valid pairs). Missing is never filled with 0 and never imputed.

## 11. Identity tests (run-time hard gates)

**Factor identity** (`FACTOR_IDENTITY_BLOCKER` on failure): sample the
first, middle and last Development dates by ordinal (E001, E050, E100) ×
all 19 factors × the first 10 sector codes ascending. The audit-recorded
factor value must equal an independent recomputation
(`compute_all_price_features` on an independently windowed full visible
frame through the signal date) within `1e-9` absolute tolerance
(floating-point tolerance only), and the audit factor column order must
equal the frozen order. The independent recomputation is the only second
computation path; no alternative factor definition is introduced.

**Target identity** (`TARGET_IDENTITY_BLOCKER` on failure): sample the same
3 dates × 3 horizons × the first 10 sector codes ascending. The audit
forward return must equal (a) an independent direct calendar-arithmetic
recomputation `close[calendar[pos+h]]/close[t] − 1`, and (b) the frozen
Iteration-1 D0 control artifact `predictions.csv` realized forward return
for the same (date, sector, horizon), each within `1e-12` absolute
tolerance. Endpoint semantics must match the recorded `label_end`. The D0
artifact's SHA-256 is verified against the Iteration-1 run metadata before
use. Endpoint shifting of any kind is forbidden.

Either failure stops the audit before any conclusion is produced.

## 12. Determinism

After the formal run, the audit is re-run with unchanged inputs. Every
non-metadata data artifact must be **byte-identical** (same SHA-256) between
runs; only run timestamps/run IDs inside `metadata.json` may differ. A
mismatch is `FACTOR_AUDIT_DETERMINISM_BLOCKER`. Artifacts are written with
the frozen canonical writers (sorted-key JSON, `%.17g` CSV floats, fixed
column orders, fixed row orders).

## 13. Artifacts

Output root: `reports/research/shenwan_sector_index/factor_alpha_audit_<timestamp>_utc/`
(generated research output; per repo convention this directory is not
tracked by Git — provenance is carried by the protocol hash, commit SHAs and
the recorded artifact hashes):

- `metadata.json`
- `factor_horizon_summary.csv`
- `factor_daily_metrics.csv`
- `factor_quantile_summary.csv`
- `factor_quantile_daily.csv`
- `factor_stability_blocks.csv`
- `factor_correlation_spearman.csv`
- `factor_redundancy_flags.csv`
- `factor_coverage.csv`
- `audit_summary.json`

`metadata.json` must contain at least: researchLabel, phase=DEVELOPMENT,
auditType=FACTOR_ALPHA_AUDIT_V1, gitCommit, protocolHash, sectorSnapshotId,
splitPolicyHash, factorOrder, horizons, development eligible IDs
(E001-E100), minimum valid sector pairs = 30, quantileCount = 5,
redundancyThreshold = 0.80, strictPit=false,
classification=FIXED_CLASSIFICATION_RESEARCH, executable=false,
tradable=false, validation=SEALED, finalOos=SEALED,
NO_PARAMETER_SELECTION=true, NO_FACTOR_SELECTION=true,
DIAGNOSTIC_ONLY=true.

## 14. Statistical interpretation rules

The final interpretation must layer conclusions as raw factor information →
temporal stability → horizon stability → quantile structure → redundancy →
coverage → Ridge diagnosis, and must not crown a single "best factor".

Ridge diagnosis rule (preregistered): if individual factors show
non-trivial signed RankIC with block stability and quantile structure while
the frozen D0-D3 model RankIC remains weak, the conclusion leans to
`MODEL_EXTRACTION / COMBINATION PROBLEM`; only if individual factors are
uniformly near-zero, block-unstable, and quantile-flat may the conclusion
lean to `CURRENT FACTOR SET HAS WEAK DEVELOPMENT PREDICTIVE CONTENT`. No
conclusion may claim "the market has no alpha"; scope is limited to the
current data, current factor definitions, and the current Development
sample.

## 15. Parameter Research Gate

The final report must state `PARAMETER_RESEARCH_GATE` ∈
{READY, NOT_READY, CONDITIONAL}, judged from Iteration-1 **plus** this
audit together, never from a single highest RankIC:

- READY: at least one factor group shows non-trivial signed RankIC,
  reasonable block stability, quantile structure, and cross-horizon
  interpretability, and evidence indicates the Ridge/representation/target
  combination still has room to improve.
- NOT_READY: the 19 factors are collectively near-zero, highly unstable,
  and quantile-flat → next step is Alpha Discovery, not Ridge tuning.
- CONDITIONAL: some factor information exists, but redundancy / regime
  instability / horizon inconsistency is substantial → next step is
  Factor Set V2 / Alpha Hypothesis V2 design, not mass parameter search.

The gate is a research judgment, not trading authorization.

## 16. Execution sequencing (preregistration proof)

1. Commit this document, `research/factor_alpha_audit_v1_protocol.py`,
   `research/factor_alpha_audit_v1_run.py` and their tests
   (`research: preregister factor alpha audit v1`) after the targeted test
   suite passes, **before** any audit result exists.
2. Run the audit from that clean frozen commit; the run's `metadata.json`
   records that commit as `gitCommit`.
3. Re-run for determinism (§12).
4. Commit the final report (`research: run factor alpha audit v1`).

Protocol commit SHA < run timestamp proves the protocol predated results.

## 17. Targeted test requirements

The preregistration commit must include synthetic tests covering: factor
order frozen; Development-only ordinals; no Validation/OOS evaluation;
endpoint semantics; minimum valid pairs = 30; Spearman RankIC; Pearson IC;
deterministic sector-code tie-break; quintile assignment incl. remainder
allocation; Q5−Q1; the 4 fixed blocks; daily factor correlation
computation; redundancy threshold 0.80; missingness never imputed; no
automatic direction flip; deterministic artifact ordering; protocol hash
self-consistency; factor identity check; target identity check. Both the
full existing suite and these targeted tests run only via
`docker compose exec quant-research`.
