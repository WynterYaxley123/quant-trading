# Shenwan Level-2 ETF mapping and tradability admission

Status: **ETF_DATA_GAP / ETF_MAPPING_NOT_ADMISSIBLE**. This is a data-access
and execution-capacity audit, **not** a strategy run or performance result.
No LEVEL B, Baseline, parameter search or OOS lock was performed.

## Provenance and existing mapping audit

The verified sector universe is the 124-row official Level-2 canonical catalog,
snapshot `872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`.
The strategy's existing `sector_etf_mapping.py` contains ranking-to-ETF matching
and duplicate-ETF handling, but **no validated product table**. Its YAML
example contains 25 static sector-name relationships to 17 ETF codes. It is
marked `LEGACY REFERENCE ONLY / REQUIRES REVALIDATION`, has no effective
dates, tracking-index IDs, source evidence or listing-date proof, and is
excluded from canonical admission. Four example ETF codes recur across three
sectors each: 512660, 159997, 159852 and 512400. The separate legacy document
has 48 older rows and even identifies an invalid airport→software proxy.
Neither file establishes a historical primary ETF. There are no evidenced
multiple-candidate sectors; this means **unknown**, not that alternatives do
not exist. The example calls 159745 an 易方达 product, while local Hikyuu
metadata calls it 国泰; this conflict is not silently reconciled.

The new evidence schema is `sector_code/name`, `etf_code/name`, `market`,
`tracking_index_code/name`, `mapping_status`, `mapping_effective_from/to`,
`etf_listing_date`, `source_provider/url/file/retrieved_at/sha256`,
`evidence_type`, `is_primary`, and `notes`. A validated row needs an
explicit primary designation, a dated relationship, a listing date, a
tracking index and auditable source. A local source file's SHA256 is checked.
Two primaries for one sector are rejected; unresolved alternatives must be
`MULTIPLE_CANDIDATES`. A shared ETF may map to several sectors and remains
one ETF in the unchanged portfolio deduplication helper. ETF listing is **not**
used to invent `mapping_effective_from`; today's relationship is never
backfilled. The generated 124 rows are explicitly `UNKNOWN`, not fake
negative findings of `NO_SUITABLE_ETF`.

## Local ETF inventory and evidence gap

Frozen `stock.db` contains eight type-5 ETF records, matched by eight
existing HDF5 daily-bar tables. `stock.startDate` equals the first locally
observed bar in this snapshot, but neither proves an **official listing date**.
All eight `listing_date` values therefore remain null. All local series end
on 2026-09-18:

| ETF | Hikyuu start / local first bar | Bars |
|---|---|---:|
| sh510300 | 2012-05-28 | 3,481 |
| sh510500 | 2013-03-15 | 3,285 |
| sh512400 | 2017-09-01 | 2,197 |
| sh512660 | 2016-08-08 | 2,458 |
| sh588000 | 2020-11-16 | 1,420 |
| sz159745 | 2021-06-18 | 1,277 |
| sz159915 | 2011-12-09 | 3,589 |
| sz159934 | 2013-12-16 | 3,105 |

Of the 17 codes in the **unverified** example, only 159745, 512400 and
512660 have local bars. The other 14 example codes are 159616, 159840,
159852, 159883, 159997, 512200, 512480, 512690, 512800, 512880,
515030, 515050, 515220 and 515790. These are *candidate evidence/data
gaps*, **not** approved primary selections or an automatic download list.
In particular, 801193 证券Ⅱ has no validated primary; example 512880 has
no local bars. Official fund issuer fact sheets, tracking-index disclosures
and exchange product/listing records are candidate sources. Collecting fresh
records or history would require separate authorization; none was requested
or fetched here.

## Daily semantics and coverage

For each sector signal session, the audit separately records sector factor
bar validity and ETF mapping activity, official listing, next-session local
bar presence, positive valid OHLC/open and execution capacity. No missing
bar is filled. The signal-date bar cannot stand in for the next session's
execution bar. When no next local session exists (including 2026-09-18),
new execution is unproven. A valid ETF bar cannot repair an invalid or
missing sector-index bar. Local OHLC alone does **not** distinguish a
suspension, price-limit queue or other microstructure constraint; this is a
conservative daily data-availability approximation, not proof of fills.

| Measure | Result |
|---|---:|
| Mapped / 124 Level-2 sectors | 0 / 124 (0%) |
| Unmapped sectors | 124; explicit list in generated admission JSON |
| Validated primary relationships / unique ETFs | 0 / 0 |
| Canonical duplicate ETFs across sectors / unresolved multi-candidate sectors | 0 / 0 |
| Official listing-date completeness | 0 / 8 local ETFs |
| Primary mapping effective-from and source completeness | 0 / 0; no primary rows exist |
| Latest common-date executable sectors / 124 | 0 / 124 |
| Sector-only candidate sessions | 239 |
| Candidate-period executable sectors, min / median / mean / max | 0 / 0 / 0 / 0 |
| Candidate-period executable coverage ratio, min / median / mean / max | 0% / 0% / 0% / 0% |
| Sessions with executable sectors ≥5 / <5 | 0 / 239 |

These zeros describe **verified mapping capacity in this snapshot**, not the
number of ETFs or industry products existing in the market. The 801193 sector
index is missing 336 of the 1,158 common sessions, but no candidate-period
session; its ETF's presence must never fill its index gap.

The sector-only candidate interval remains **2025-04-02..2026-03-27**.
The existing calculation starts from the 2021-12-13..2026-09-18 common
calendar, requires 120 preceding sessions of valid sector features, six
calendar months of training and a 120-session label/purge boundary, then
reserves 120 future sessions for the largest forward label. Thus the
2026-09-18 sector data endpoint does not become the candidate endpoint.
The next-session execution bar is checked separately here; the prior
sector-only date algorithm did **not** reserve an additional execution
session beyond its 120-session label allowance. This potential conservatism
or boundary interaction should be reviewed before a split is designed,
not silently changed now. The sector-plus-ETF candidate start/end are both
**null**, because no date has five verified executable sector mappings.
No Development/Validation/OOS dates are locked.

## Admission and reproducibility

ETF mapping admission is **ETF_MAPPING_NOT_ADMISSIBLE**: no local record
proves a primary tracking relationship, historical mapping effective date
or official ETF listing date. Even partial admission would require actual
validated rows, not the example. Sector admission remains
`FIXED_CLASSIFICATION_RESEARCH`, `strict_pit=false`.
**NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST.**
The 20 source-invalid sector OHLC rows are unchanged and independently
guarded by the existing sector loader.

Generated, gitignored files are in `data/processed/shenwan_etf_mapping/`:
`etf_mapping_evidence.csv`, `etf_local_metadata.csv`,
`etf_daily_availability.csv`, `etf_daily_coverage.csv`, and
`etf_mapping_admission.json`. Inputs are the existing SHA256-verified
Shenwan canonical files and read-only Hikyuu `stock.db`/HDF5 files.
Rebuild with `docker compose exec quant-research python
scripts/data/admit_shenwan_etf_mapping.py`. No network, data initialization,
image build, dependency change or strategy run is performed.

Next prerequisite: acquire and audit official, historically timed
tracking/listing documents and—only after explicit authorization—any
missing ETF daily histories; resolve the 159745 identity conflict and
deterministically designate primary ETFs. This moves the admission tooling
closer to LEVEL B, but **does not authorize LEVEL B**.
