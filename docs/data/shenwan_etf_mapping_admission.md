# Shenwan Level-2 ETF mapping: second admission

Status: **ETF_MAPPING_NOT_ADMISSIBLE**. This is an offline data/evidence audit, not
a strategy run, backtest, performance result, or permission to start LEVEL B.

## Reconciled provenance

The existing `scripts/data/verify_etf_evidence.py` gate reports **INTEGRITY:
PASS**: 29 PDFs on disk, 29 manifest entries, 22 catalog ETFs, 22/22 catalog
primary-document, SHA256 and URL matches, no duplicates or orphans. The
admission entrypoint additionally reads `evidence_sources.csv`, verifies all
29 field-level document links against the registered manifest, and checks the
21 independent raw ETF CSVs against their SHA256, size, row count, columns and
date range. Those raw files contain 40,445 rows. The evidence inputs are
read-only and remain under `data/raw/etf_evidence/`, `data/raw/etf/` and
`data/processed/shenwan_etf_mapping/` (gitignored).

The official catalog contains 22 unique ETFs. Official fund identity, listing
date, establishment date and tracking-index name are complete for 22/22;
tracking-index code is present for 11/22. Supporting official documents may
prove individual fields: not every field must come from the same primary PDF.
These documents prove **Layer 1** (ETF → currently disclosed tracking index).
They do not prove **Layer 2** (tracking index → one specific Shenwan Level-2
sector). A matching product or index name is insufficient. Historical
`mapping_effective_from` and `mapping_effective_to` are both 0/22. An official
listing date is not a mapping start date; a `CURRENT_RELATIONSHIP_ONLY`
disclosure is not backfilled.

| Official evidence status | ETFs | Formal execution mapping |
|---|---:|---|
| VALIDATED | 0 | none |
| PARTIAL_EVIDENCE | 6 | candidate only; not admitted for backtest |
| NOT_DIRECT_MAPPING | 15 | excluded |
| CONFLICT | 1 | excluded |
| UNVERIFIED | 0 | excluded |

The six partial candidates are evidence-acquisition leads, **not** validated
primary mappings:

| ETF | Official tracking index | Candidate Shenwan Level-2 | Official listing | Missing evidence |
|---|---|---|---|---|
| 512480 国联安半导体ETF | 中证全指半导体产品与设备指数 | 801081 半导体 | 2019-06-12 | Layer 2; historical effective-from |
| 512880 国泰中证全指证券公司ETF | 399975 中证全指证券公司指数 | 801193 证券Ⅱ | 2016-08-08 | Layer 2; historical effective-from |
| 515790 光伏ETF | 931151 中证光伏产业指数 | 801735 光伏设备 | 2020-12-18 | Layer 2; historical effective-from |
| 159840 锂电池ETF工银 | 国证新能源车电池指数 | 801737 电池 | 2021-08-20 | Layer 2; historical effective-from |
| 159852 嘉实中证软件服务ETF | 中证软件服务指数 | 801104 软件开发 | 2021-02-09 | Layer 2; historical effective-from |
| 159883 永赢中证全指医疗器械ETF | 中证全指医疗器械指数 | 801153 医疗器械 | 2021-04-30 | Layer 2; historical effective-from |

The 25 concluded legacy mapping reviews remain separate: 6 partial, 18 not
direct and 1 conflict. In particular, 计算机设备→159852 and IT服务Ⅱ→159852 remain
`NOT_DIRECT_MAPPING` despite that ETF's partial candidate for 软件开发. 159616
is an ETF-identity conflict (official 农牧, not legacy 智能电网); 159745 retains
the manager-name conflict and spans multiple Level-2 sectors; 512800's
legacy “银行” is not one canonical Level-2 sector. The 48 legacy reference
records are clues only, excluded from official coverage and execution; 21
remain `UNVERIFIED_OUTSIDE_INVESTIGATED_UNIVERSE`. No new investigation was
performed on them.

ETF 159915 has official identity/listing/tracking evidence and 3,589 local
Hikyuu bars starting 2011-12-09. It has **no independent raw refresh**. Its
official listing date comes from official evidence, not from its first local
bar. This broad-market ETF is `NOT_DIRECT_MAPPING` and cannot become a
Shenwan Level-2 primary merely because local market data exists.

## Strict admission versus candidate diagnostics

The unchanged mapping evaluator admits only `VALIDATED` primary rows with
auditable historical timing. The formal mapping remains 124 explicit
`UNKNOWN` sector rows: **0/124 validated sectors (0%)**, zero strict
executable sectors on the latest common date, and zero historical executable
sectors throughout the 239 candidate sessions. Candidate diagnostic coverage
is **6/124 (4.84%)**, separately labeled **CANDIDATE ONLY; NOT ADMITTED FOR
BACKTEST**. None of those six enters active mapping, Top-5 execution coverage,
or the formal executable universe.

Sector-only research eligibility remains **2025-04-02..2026-03-27**;
`sector_plus_etf_candidate_start/end` remain **null** because no validated
execution universe exists. The sector source retains
`FIXED_CLASSIFICATION_RESEARCH`, `strict_pit=false`:
**NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST.** Daily local bars and
positive OHLC alone also cannot prove absence of suspension, price-limit
queues or other execution constraints. No Development/Validation/OOS dates
were locked.

To reproduce, run the integrity gate first, then
`scripts/data/admit_shenwan_etf_mapping.py` inside the existing
`quant-research` container. The entrypoint writes only generated, gitignored
admission outputs (`etf_mapping_admission.json`, mapping evidence, ETF local
metadata, daily availability and coverage CSVs) to
`data/processed/shenwan_etf_mapping/`. It does not download, import Hikyuu
data, change a strategy, or run a backtest.

Next blocker: official second-layer index-methodology/constituent evidence
for **only the six candidates above**, plus separate historical evidence for
`mapping_effective_from`. These are prerequisites to another admission,
not authorization to proceed to LEVEL B.
