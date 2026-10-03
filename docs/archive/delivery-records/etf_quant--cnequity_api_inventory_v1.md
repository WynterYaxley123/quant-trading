# ETF-Quant V1 — CNEquity API Inventory (v1)

**Audit type:** READ-ONLY source audit. No production adapter was implemented.
**Owning task:** ETF-Quant V1 — CNEquity data contract / ETF mapping / benchmark audit.
**Baseline commit (main worktree):** `bd13d278b25eace66a7eae287307413f930effd9`

This document is the **evidence inventory**. The binding contract derived from it is
[`etf_quant_cnequity_data_contract_v1.md`](etf_quant_cnequity_data_contract_v1.md).
Every claim below is bound to repository / commit / file path / identifier, per the task's
citation requirement. README marketing claims were not used as contract evidence.

---

## 0. Audited artifact

| Item | Value |
|---|---|
| Repository | `https://github.com/rootSunc/CNEquity` |
| Official docs | `https://rootsunc.github.io/CNEquity/` (mkdocs: `mkdocs.yml`) |
| Clone | `D:\QuantForge\temp\cnequity-audit-v1\repo` (outside the main repo) |
| **Audited commit** | **`1650e384a3fd1f67a70144a489acc91432f1df27`** |
| Branch | `main` |
| `git describe --tags` | `v0.11.0-1-g1650e38` (exactly 1 docs commit after tag `v0.11.0`) |
| Declared version | **`0.11.0`** (`pyproject.toml:7`) |
| Licence | Apache-2.0 (`LICENSE`); code only — does not license upstream data |
| Install name / CLI | `cnequity` / `cne` (`pyproject.toml:6`, `:113`) |
| Python requirement | **`>=3.10`** (`pyproject.toml:11`); classifiers list 3.10–3.14 (`:35-40`) |
| Registry size | **42 registered datasets** — 39 curated + 3 derived (`docs/datasets/catalog.md:3`) |

### 0.1 Versioned contract artifact

`pyproject.toml:118-123` ships `contracts/v0.10.0.json` and `contracts/v0.11.0.json` as release-governance
data-files. Findings from reading `contracts/v0.11.0.json` (164,181 bytes):

| Finding | Value |
|---|---|
| Top-level keys | `contract_version`=1, `version`=1, `format`=`"cnequity.dataset-contract"`, `fingerprint`=`f77ea572c82ad3e50884da281b9fa881840965484d7a7b9fd29350014159fb8b`, `pit_contract`, `datasets` |
| Internal release identity | **NONE** — no `generator`, no `"0.11.0"` string, no `release` field. The version exists only in the filename. |
| `v0.11.0.json` vs `v0.10.0.json` | **byte-identical** (both 164,181 bytes, identical SHA-256) — v0.11.0 carries no dataset change |
| Datasets in contract | 42 |
| **Occurrences of `etf` / `benchmark` / `tracking` / `underlying` / `basket` / `nav` / `index_name`** | **0 each** |
| Keys absent from contract but present in `DatasetSpec` | `supplementary_sources`, `session_scope`, `shallow_reconciliation_lookback_days`, `dtypes`, `required_columns` |
| `unit_contract` polymorphism | literal string `"canonical"` for `adj_factors`, `instruments`, `trading_calendar`, `trading_status`, `industry_members`; a column→unit map for `daily_bars`, `index_bars`, `industry_index`, `sector_bars`, `index_constituents` |
| `date_col` | `null` for all 10 audited datasets (the effective date column is exposed as `query_date_col`) |

> **The exported contract does not cover ETF, tracking index, or benchmark semantics at all.**
> Anything ETF-related in this audit is therefore derived from the `DatasetSpec` registry and
> adapter source, not from the shipped contract, and must be treated as **not release-governed**.

---

## 1. Capability matrix (all 24 requested items)

Legend: **YES** available · **PARTIAL** available with material caveats · **NO** unavailable · **UNKNOWN** not determinable from source.

| # | Requested capability | Status | Dataset / entrypoint | Key caveat |
|---|---|---|---|---|
| 1 | trading calendar | **YES** | `trading_calendar`; `cnequity.steps.common.list_trading_dates` | — |
| 2 | ETF daily bars | **PARTIAL** | `daily_bars` | **Excluded by default** — `[universe].ingest="all_a"` |
| 3 | ETF metadata | **PARTIAL** | `instruments` | Only 6 identity columns; no fund fields |
| 4 | ETF listing date | **PARTIAL** | `instruments.list_date` | Nullable; EM-supplied for ETF/LOF |
| 5 | ETF delisting / status | **PARTIAL** | `instruments.delist_date`, `trading_status.status` | Historical `delisted` rows deliberately not backfilled |
| 6 | ETF name / code | **YES** | `instruments.name` / `.symbol` | — |
| 7 | ETF OHLC | **PARTIAL** | `daily_bars` | Conditional on ingest scope |
| 8 | ETF volume | **PARTIAL** | `daily_bars.volume` (unit **share**) | Conditional on ingest scope |
| 9 | ETF amount | **PARTIAL** | `daily_bars.amount` (unit **CNY**) | Conditional on ingest scope |
| 10 | ETF adjustment | **YES** | `adj_factors` (derived) | ETF/LOF read Sina field `s`, stocks read `f` |
| 11 | stock bars | **YES** | `daily_bars` | — |
| 12 | Shenwan classification | **PARTIAL** | `industry_members`, `classification_system="sw"` | Reconstructed monthly from **2020**; `industry_name` is a code alias |
| 13 | historical / PIT membership | **PARTIAL** | `industry_members` + `backfill_source="sw"` | Monthly as-of snapshots; `pit_quality` = **not_applicable** |
| 14 | industry index | **PARTIAL** | `industry_index` (derived) | **Returns only — no OHLC, no volume** |
| 15 | derived industry returns | **YES** | `industry_index.ret` (fraction, `equal`/`amount`) | 19-factor frame incompatible (see §4) |
| 16 | sector bars | **PARTIAL** | `sector_bars` | Full OHLCV, but **THS taxonomy** (`881xxx`/`885xxx`) |
| 17 | index bars | **YES** | `index_bars` | `volume`/`amount` = `source_native`, unusable as money |
| 18 | benchmark data | **PARTIAL** | `index_bars` | **CSI 300 only**; NASDAQ & S&P 500 absent |
| 19 | provenance | **YES** | `source`, `data_version`, `fetched_at` on every curated row | — |
| 20 | source | **YES** | `source` column | — |
| 21 | data_version | **YES** | `data_version` column | Semantics change bumps it (e.g. `volume` v1→v2) |
| 22 | fetched_at | **YES** | `fetched_at` (timestamp[us, **UTC**]) | Observation time, not availability |
| 23 | available_at | **PARTIAL** | bitemporal column on **5 PIT datasets only** | **ABSENT for `daily_bars`, `index_bars`, `industry_members`, `industry_index`, `sector_bars`** |
| 24 | source_published_at | **PARTIAL** | same 5 PIT datasets | Same absence |
| 25 | announce_date | **YES** | PIT axis: `financial_statement_items`, `announcement_index` | Not applicable to price/industry data |
| 26 | update_time | **NO** | — | Not a lake column; exists only in the upstream SW XLS as `更新日期`, **dropped in parsing** |

**Item 26 evidence:** `src/cnequity/adapters/sw/industry_history.py:117-124` renames the upstream
`更新日期` column to `update_time`, and `:132-138` then builds rows containing only
`symbol`, `start_date`, `industry_code` — `update_time` is **discarded** before it ever reaches
the lake. The upstream "last updated" fact is therefore not recoverable downstream.

---

## 2. Per-capability details

All entries give: API / arguments / return schema / primary key / source identity /
time semantics / limitations.

### 2.1 `trading_calendar` — item 1

| Field | Value |
|---|---|
| API | `load("trading_calendar", start=..., end=...)` |
| Return schema | `DAILY_BARS`-independent: `trade_date` (Date), `is_trading` (Boolean), `source`, `data_version`, `fetched_at` — `domain/schemas.py:150-156` |
| Primary key | `(trade_date)` — `docs/datasets/schema.md:58` |
| Partition | `trade_date` (by **year**) — `domain/datasets.py:640-641` |
| Source identity | primary `tdx_protocol`; backup `exchange` (exchange CSV files) — `domain/datasets.py:636-642` |
| Time semantics | Session flag only. No publication timestamp. |
| Limitations | Seed range 2016–2027 from TDX; outside that, the exchange CSV backup is the only path (`docs/datasets/catalog.md:195`) |

### 2.2 `daily_bars` — items 2, 7, 8, 9, 11

| Field | Value |
|---|---|
| API | `load("daily_bars", start=, end=, symbols=, adjust=, universe=, strict_adj=)`. Note `universe` accepts only `"all_a"` / `"all_a_sh_sz"` (`docs/reference/python-api.md:20`) — **not an ETF universe**. |
| Return schema | `symbol`, `trade_date`, `open`, `high`, `low`, `close`, `volume` (int64, **share**), `amount` (float64, **CNY**), `source`, `data_version`, `fetched_at` — `domain/schemas.py:40`, `docs/datasets/schema.md:138-152` |
| Primary key | `(symbol, trade_date)` — `docs/datasets/schema.md:60` |
| Partition | `trade_date` (by **day**); `hive_partitioning=true` is **safe** here — `docs/datasets/schema.md:872` |
| Unit contract | `price: CNY/share`, `volume: share`, `amount: CNY` — `domain/datasets.py:62-66` |
| Source identity | primary `tdx_protocol`; backup `eastmoney`; supplementary `exchange`, `bse`, `sina`, `ths`, `ths_official`, `baostock` — `domain/datasets.py:686-692` |
| Coverage mode | `session_dense` — a missing interior session is a derivation hole, not natural sparsity (`domain/datasets.py:705`) |
| Reconciliation | `reconciliation_lookback_days=5`, `shallow=1`, mode `trading_day` (`domain/datasets.py:695-704`) |
| **ETF limitation** | ETF/LOF prefixes `51/52/56/58/15/16` are **retained** in `instruments`/`daily_bars` but **excluded from the `all_a` research pool**, and are not ingested under the default `ingest="all_a"` — `docs/datasets/sources.md:24-25`, `docs/getting-started/configuration.md:161-170`. Enabling them costs ~25% of fetch budget and risks the coverage gate rejecting the whole day's write. |
| **Volume-unit hazard** | Contract is **always shares**; adapters convert at their own boundary. Native units differ: `tdx_protocol`=手 (×100), `ths`=股, `baostock`=股, `eastmoney`=手 (*not independently verified*). Only `data_version=v2` guarantees shares — `docs/datasets/schema.md:154-181`. Mixing them errs by exactly 100×, which "足以毁掉一切换手率/流动性因子" while passing row-count and OHLC checks. |
| **Suspension representation** | Suspended days keep OHLCV **with `volume=0, amount=0`** — `docs/datasets/schema.md:13`. A row may exist and still not be a trade. |

### 2.3 `instruments` — items 3, 4, 5, 6

| Field | Value |
|---|---|
| API | `load("instruments")` |
| Return schema | `INSTRUMENTS_SCHEMA` — `symbol`, `name`, `exchange`, `asset_type`, `list_date`, `delist_date`, `prev_symbol`, `source`, `data_version`, `fetched_at` — `domain/schemas.py:137-148` |
| Primary key | `(symbol)` — `docs/datasets/schema.md:57` |
| Partition | **none** (merge-style single table) — `domain/datasets.py:631` |
| `asset_type` values | **`stock` / `etf` / `cdr`** — verified from all three producers: `steps/delisted.py:426-434`, `adapters/baostock/instruments.py:78-86`, `adapters/tdx_protocol/client.py:291-296`. **No source emits `index`.** `docs/datasets/schema.md:85` lists `stock/etf/index` and is **stale** (doc-drift, see §8). |
| ETF identification | `is_etf_symbol(code, exchange)` (`domain/symbols.py:178-189`) — **code-prefix only**. `ETF_PREFIXES` (`:34-52`): SH `501,502,510-518,52,53,56,58`; SZ `15,16`. ETFs are deliberately excluded from `PREFIX_WHITELIST` (`:5-11`, rationale `:21-24`). |
| **ETF vs LOF** | **Not distinguished.** `is_etf_symbol` returns True for LOF prefixes too, so both land in `asset_type="etf"` (`SH_LOF_PREFIXES = ("501","502")`, `:32`). |
| **ETF product class** | **Not stored.** Bond (511), cross-border (513) and gold (518) ETFs are indistinguishable in the lake except by decoding the prefix yourself. |
| Source identity | primary `tdx_protocol` (built-in security list); backup `baostock` (delisted recovery, `cne backfill instruments` only); supplementary `bse` (BJ listing + 证券简称), `sina` (code-space sweep) — `domain/datasets.py:621-634` |
| Time semantics | `availability_col` inferred as **`list_date`** for this dataset (`domain/datasets.py:564-565`) |
| **Absent fields** | tracking index code/name, fund type, fund company, management fee, AUM/size, inception date. None exists anywhere in the 42-dataset registry. |
| Limitations | ~25% of rows are ETF/LOF/fund quote codes (`docs/getting-started/configuration.md:167`). `list_date` for ETF/LOF comes from EastMoney's separate ETF/LOF `clist` (`docs/datasets/catalog.md:194`). Delisted-code recovery requires the baostock backfill; live boards only list what trades today (`domain/datasets.py:618-620`). |

### 2.4 `trading_status` — item 5

| Field | Value |
|---|---|
| Return schema | `symbol`, `trade_date`, `is_trading` (Boolean), `status` (`normal`/`suspended`/`delisted`), `risk_warning` (Boolean, nullable), provenance — `domain/schemas.py:162+`, `docs/datasets/schema.md:105-114` |
| Primary key | `(symbol, trade_date)` |
| Partition | `trade_date` (**monthly**) — `docs/datasets/schema.md:44` |
| Source identity | primary `eastmoney`; backup `exchange`; supplementary `derived`, `bse` — `domain/datasets.py:643+`, `docs/datasets/sources.md:45` |
| Time semantics | **Per-day observed fact.** Historical `delisted` rows are deliberately **not** backfilled: "某一天的状态是当时观测到的事实，用今天的退市日期倒填会凭空造出当时并不存在的 point-in-time 事实" — `docs/datasets/schema.md:135-136` |
| Limitations | `status` and `risk_warning` are orthogonal and must stay two columns (`domain/schemas.py:158-161`). BJ has no free historical ST source (`docs/datasets/sources.md:53`). |

### 2.5 `adj_factors` — item 10

| Field | Value |
|---|---|
| API | `load("daily_bars", adjust="hfq"\|"qfq", strict_adj=bool)` — factors are applied at **query time**, not stored on bars |
| Dataset schema | `symbol`, `trade_date`, `adjust_type`, `factor`, provenance — `domain/schemas.py:198`, `docs/datasets/schema.md:345-355` |
| Primary key | `(symbol, trade_date, adjust_type)` — `docs/datasets/schema.md:65` |
| Source identity | `sina` (default); backup `baostock` (derived from raw/hfq close ratio) — `docs/datasets/sources.md:132-133` |
| Stored form | **`hfq` only.** `adjust_types` default `["hfq"]`; qfq is derived at query time — `docs/getting-started/configuration.md:114`, ADR-0004 |
| Formula | `adj_close = close * factor` (`docs/datasets/sources.md:137`); qfq factor = `1/sina_qfq_factor`, hfq = `sina_hfq_factor` (`docs/datasets/schema.md:352`) |
| **ETF/LOF** | Stocks read Sina field `f`; **ETF/LOF read field `s`** (`docs/datasets/catalog.md:212`, `docs/datasets/sources.md:138`). Different upstream field, same lake column. |
| **Critical default** | `strict_adj=False` by default → rows lacking a factor are returned at **`factor=1.0`**, i.e. **raw prices appear inside an hfq result**, flagged only by `adj_is_exact=False` (`docs/datasets/sources.md:139`). `strict_adj=True` raises instead but is not the default because newly listed names always lack a factor initially. |

### 2.6 `industry_members` — items 12, 13

| Field | Value |
|---|---|
| API | `load("industry_members")`; backfill `cne backfill industry_members` |
| Return schema | `INDUSTRY_MEMBERS_SCHEMA` — `symbol`, `classification_system`, `industry_code`, `industry_name`, `as_of_date`, provenance — `domain/schemas.py:416`, `docs/datasets/schema.md:553-564` |
| Primary key | `(symbol, classification_system, as_of_date)` — `docs/datasets/schema.md:74` |
| Partition | `as_of_date` (**monthly**) — `docs/datasets/schema.md:48` |
| Fetch semantics | `snapshot` (`domain/datasets.py:1086`) |
| Source identity | primary `eastmoney` (daily snapshot, `classification_system="eastmoney"`); **backfill `sw`** (Shenwan, `classification_system="sw"`) — `domain/datasets.py:1081-1089` |
| `classification_system` values | `sw` (Shenwan SwClass2021) and `eastmoney` (3/4-digit EM board codes — "a different taxonomy entirely", `derive/industry_index.py:64-66`) |
| Upstream | **`https://www.swsresearch.com/swindex/pdf/SwClass2021/StockClassifyUse_stock.xls`** (`adapters/sw/industry_history.py:33-35`) |
| Upstream columns used | `股票代码`→`code`, `计入日期`→`start_date`, `行业代码`→`industry_code`, `更新日期`→`update_time` (**then discarded**) — `:117-138` |
| PIT construction | Interval rows with an **entry date only**. `expand_sw_industry_as_of` takes, per symbol per as-of date, the row with the greatest `start_date <= as_of` — `:148-176`. **There is no `effective_to` upstream and none stored**: `INDUSTRY_MEMBERS_SCHEMA` (`domain/schemas.py:416-425`) has no end column. |
| Snapshot derivation | `as_of_date` is a **synthesised last-trading-day-of-each-calendar-month** label (`steps/structure.py:374-376` via `_month_end_trading_days` `:44-52`), not a vendor publication timestamp. Months yielding fewer than 1000 symbol rows are **dropped rather than published** (`_MIN_DAILY_INDUSTRY_MEMBER_SYMBOLS = 1000`, `:38`, applied `:400-414`). |
| **Monthly resolution consequence** | Resolution is **monthly**, so a spell effective mid-month is only reflected from the **next month-end label onward** — in `expand_sw_industry_as_of` and in downstream `_members_as_of` (`derive/industry_index.py:225-236`, a backward as-of join that drops days before the first snapshot; pinned by `tests/unit/test_industry_index.py:79-83`). |
| History depth | **Monthly as-of snapshots from 2020-01** — `_INDUSTRY_HISTORY_START = date(2020, 1, 1)` (`steps/structure.py:35`), effective floor `max(BACKFILL_START=2016-01-01, 2020-01-01)` (`:363`). The first emitted snapshot is the last trading day of **January 2020** (exact date data-dependent — **UNKNOWN** from source). Registry agrees: `domain/datasets.py:1087-1088`; `derive/industry_index.py:9-12`, `:380`. |
| Second population | The table also holds daily EastMoney snapshots under `classification_system="eastmoney"` with `as_of_date` = the run date (`steps/structure.py:341-358`) — a **different taxonomy** ("3/4-digit codes", `derive/industry_index.py:64-66`). `industry_index` filters to `source == "sw"` only (`:83`). |
| **Trap 1** | `industry_name` is written as **`pl.col("industry_code").alias("industry_name")`** — `:174`, with the comment "Official name map is a separate SW publish; code is stable for joins." It is **a code, not a name.** |
| **Trap 2** | Symbols are normalised through `is_all_a_symbol`, so **ETF/LOF codes are filtered out** — `:80-85`. Industry membership covers **stocks only**. |
| **Trap 3** | `更新日期` → `update_time` is renamed at `:122` and then **never used** — emitted rows carry only `symbol`, `start_date`, `industry_code` (`:127-138`). The one upstream field that could date the *publication* of a classification is discarded at the adapter boundary, so **no publication-time evidence survives anywhere in the lake**. |
| **Trap 4** | TLS: swsresearch.com serves a 1-deep chain. A public DigiCert intermediate (`geotrust_g2_tls_cn_rsa4096.pem`) is shipped to complete it. `verify=False` was explicitly rejected — `:39-58`. If SW rotates CAs this file goes stale. |
| `pit_quality` | **`not_applicable`** — the registry sets `pit` only for the 5 disclosure datasets, and `__post_init__` assigns `not_applicable` when neither `pit` nor a snapshot-without-backfill applies (`domain/datasets.py:525-540`) |

### 2.6a A keyed ETF endpoint exists but is never called

`ths_official` (the keyed 同花顺 API) contains a dedicated **ETF** historical-bar endpoint:

| Item | Value | Evidence |
|---|---|---|
| Endpoint constant | `ETF_ENDPOINT = "/api/fund/market/historical"` | `adapters/ths_official/bars.py:75-76` |
| Window cap | `ETF_MAX_WINDOW_DAYS = 365 * 4` | `adapters/ths_official/bars.py:76` |
| Switch | `etf: bool = False` parameter, endpoint selected at `:135`, window at `:136` | `adapters/ths_official/bars.py:115` |
| Turnover field | `item.get("turnover")` — nullable | `adapters/ths_official/bars.py:187` |
| **Callers passing `etf=True`** | **NONE in `src/`** | `steps/bars.py:4522`, `:4676` call `fetch_daily_bars(...)` without it; the verify path filters to `asset_type == "stock"` at `:4654` |

Recorded because it is the **only** ETF-specific data capability found anywhere in the project, and because
ADR-0008 states `ths_official` "从不拥有任何一行" (never owns a curated row) — it exists for arbitration
snapshots and known-gap repair, never as a primary source. Enabling it requires the optional
`HITHINK_FINANCE_API_KEY` (§5) and a separate explicit decision (`backfill = true`). **Not enabled, not
recommended by this audit** — noted only so a future task does not rediscover it and mistake it for an
available path.

### 2.7 `industry_index` — items 14, 15

| Field | Value |
|---|---|
| API | `load("industry_index", start=, end=)`; recompute `cne derive industry_index` |
| Return schema | `INDUSTRY_INDEX_SCHEMA` — `trade_date`, `industry_code`, `level`, `weighting`, `ret`, `n_members`, `n_priced`, `n_excluded`, `amount`, provenance — `domain/schemas.py:600-620` |
| Primary key | `(trade_date, industry_code, level, weighting)` — implied by `dedupe_by_primary_key(frame, "industry_index")` (`derive/industry_index.py:399`) and `schemas.py:683` |
| Partition | `trade_date` (by **year**) — `domain/datasets.py:1253-1254` |
| Layer | **`derived`** (`domain/datasets.py:1252`), tier **L5** |
| `level` values | `L1` (2-digit), `L2` (4-digit), `L3` (6-digit) — `LEVELS = {"L1": 2, "L2": 4, "L3": 6}` (`derive/industry_index.py:51`) |
| `weighting` values | `equal`, `amount` — `WEIGHTINGS` (`:52`) |
| `ret` unit | `fraction` (`domain/datasets.py:173`) |
| `amount` unit | `source_native` (`domain/datasets.py:173`) |
| Source identity | `derived` — computed from `industry_members(source="sw")` × `daily_bars` hfq (`domain/datasets.py:1250`, `derive/industry_index.py:1-7`) |
| Computation | `pct_change().over("symbol")` on **hfq** closes, then per industry: `ret_equal` = mean of member returns; `ret_amount` = `Σ(ret×amount)/Σ(amount)`, **null when no member has a non-null amount** — `:168-175`, `:284-298` |
| Default start | `date(2020, 1, 1)` when no watermark — `:378-382` |
| **NO OHLC** | The schema has **no `open`/`high`/`low`/`close`/`volume`**. Only `ret` and `amount`. |
| **NO price level** | `ret` is a per-session fractional return. There is no index level. |
| Design rationale | "a fetched board index and a separately fetched membership list describe slightly different baskets … Computing the index from the membership we hold makes the two consistent *by construction*" — `:3-7` |

### 2.8 `sector_bars` — item 16

| Field | Value |
|---|---|
| Return schema | `SECTOR_BARS_SCHEMA` — `sector_code`, `sector_name`, `board_type`, `trade_date`, `open`, `high`, `low`, `close`, `volume`, `amount`, `change_pct`, provenance — `domain/schemas.py:516`, `docs/datasets/schema.md:758-775` |
| Primary key | `(sector_code, trade_date)` — `docs/datasets/catalog.md:299` |
| Partition | `trade_date` (**monthly**) — `domain/datasets.py:1131` |
| Fetch semantics | `snapshot`; backfill and daily both via THS board-kline — `domain/datasets.py:1133-1141` |
| Source identity | primary `ths`; repair `ths_official`. **No second source** — `docs/datasets/catalog.md:299` |
| Unit contract | `price: index_point`, `volume: source_native`, `amount: source_native` — `domain/datasets.py:162-166` |
| Board taxonomy | **`881xxx` = 行业, `885xxx` = 概念** (`adapters/ths/boards.py:19`). `board_type` ∈ `{industry, concept}`. |
| Upstream | `https://d.10jqka.com.cn/v6/line/bk_{code}/01/{part}.js` (per-year JSONP) — `adapters/ths/boards.py:58` |
| Depth | **行业 back to 2007-08, 概念 to 2014**, "on a single consistent index base" — `adapters/ths/boards.py:10-13` |
| Sanitisation | Bars with any OHLC ≤ 0 are dropped; bars where `volume>0` but `high<max(open,close)` or `low>min(open,close)` are dropped — `:348-351` |
| `change_pct` | **Not shipped by THS**; derived on the fetched series, so the window's first bar is **null** rather than guessed — `:371-384` |
| Provenance note | The previous lake spliced TDX history against EastMoney daily rows under one `sector_code`, producing a **fake +79% median jump** on the splice date; this dataset now uses a single consistent base to avoid exactly that — `:11-13` |

### 2.9 `index_bars` — items 17, 18

| Field | Value |
|---|---|
| Return schema | Same as `daily_bars` plus `frequency` (default `1d`) and `asset_type=index` — `docs/datasets/schema.md:185` |
| Primary key | `(symbol, trade_date, frequency)` — `docs/datasets/schema.md:61` |
| Partition | `trade_date` (by **year**); `hive_partitioning` **must be false** — `docs/datasets/schema.md:882-884` |
| Unit contract | `price: index_point`, `volume: source_native`, `amount: source_native` — `domain/datasets.py:67-71` |
| Source identity | primary `tdx_protocol`; backup `eastmoney`; supplementary `ths` — `domain/datasets.py:707-720` |
| Available indices | TDX seed: `000001.SH`, `399001.SZ`, `399006.SZ`, `000688.SH`, `000016.SH`, **`000300.SH`**, `000905.SH`, `000852.SH` (`adapters/tdx_protocol/client.py:53-62`); THS map adds deep history (`adapters/ths/index_bars.py:44-52`) |
| **CSI 300** | `000300.SH`; THS code `399300`; history **from 2005-01-04** (`adapters/ths/index_bars.py:47`) |
| **Offshore** | **Only COMEX gold** `GC0.CMX` via `commodity_bars` (`adapters/sina/global_futures.py:31`); "外盘 v1 仅黄金；不进 A 股回测引擎" (`docs/datasets/schema.md:309`). **No NASDAQ Composite, no S&P 500.** |
| **Volume/amount unusable** | `volume` is not shares and could not be reconciled: index `amount` was 77% of the sum of constituent `amount`, while `volume` differed by ~300×. Both `index_bars`/`sector_bars` remain `data_version=v1` — `docs/datasets/schema.md:187` |
| **Deliberate exclusion** | `000852.SH` (中证1000) is **absent from the THS map**: both candidate THS codes return a series closing 2015 at 10614 against the index's actual ~8378 and starting in 2005 though the index was published in 2014. "A benchmark that is quietly the wrong series is worse than a missing one." — `adapters/ths/index_bars.py:39-43` |

See [`benchmark_source_audit_v1.md`](benchmark_source_audit_v1.md) for the full benchmark verdicts.

---

## 3. Provenance, source identity and time semantics (items 19–26)

### 3.1 Provenance columns (all curated rows)

| Column | Type | Meaning |
|---|---|---|
| `source` | string | source label |
| `data_version` | string | source version/batch |
| `fetched_at` | timestamp[us, **UTC**] | when the row was fetched |

Evidence: `docs/datasets/catalog.md:176-180`, `docs/datasets/schema.md:12`.

### 3.2 Bitemporal columns — 5 datasets only

Per `docs/datasets/schema.md:20`, the four optional bitemporal columns apply **only** to:
`announcement_index`, `financial_statement_items`, `share_structure`, `shareholder_counts`, `top_holders`.

| Column | Meaning | Constraint |
|---|---|---|
| `available_at` | when the fact became available at source | **unknown ⇒ must be null**; must not be replaced by the report period |
| `source_published_at` | actual source publication time | usually unknown for EM historical backfill |
| `observed_at` | when the lake observed the row | legacy files derive it from `fetched_at` |
| `revision_id` | stable fact/version identity | 96-bit (24 hex chars) truncated SHA-256 over business + provenance fields, **excluding** observation timestamps |

> **Critically: `daily_bars`, `index_bars`, `adj_factors`, `industry_members`, `industry_index` and
> `sector_bars` carry NONE of these.** For the ETF-Quant industry and ETF price paths there is **no
> stored column that proves when a value became knowable.**

### 3.3 `pit_quality` values and assignment

`PitQuality` ∈ `{strict, reconstructed, snapshot_only, not_applicable}` (`domain/datasets.py:449-454`).
Inference when unset (`:525-540`):

| Condition | Assigned |
|---|---|
| `pit_grade == "partial"` | `reconstructed` |
| `pit == True` | `strict` |
| `fetch_semantics == "snapshot"` and no `backfill_source` | `snapshot_only` |
| otherwise | **`not_applicable`** |

`not_applicable` is the deliberate default for by-date data: "This used to default to `strict` so the
exported contract stayed total, which published the strongest possible claim for every table nobody
had considered — 29 of the 30 `strict` datasets, `daily_bars` among them." (`:532-539`)

Datasets explicitly set to `reconstructed`: `financial_statement_items` (`:897`), `share_structure` (`:925`),
`shareholder_counts` (`:938`), `top_holders` (`:961`).

### 3.4 `as_of` semantics

`load(..., as_of=...)` filters **`announce_date` AND `fetched_at.date()`**, both ≤ as_of, and for the same
item takes the version then in effect (`docs/reference/python-api.md:41`). `pit_mode`:
`strict` excludes `reconstructed` backfill; `best_effort` keeps it but returns `pit_is_exact=False`;
omitting it keeps 0.x compatibility behaviour and "不代表严格 PIT" (`:47`).

**This mechanism is available only for PIT datasets.** It does not give the price/industry datasets a
point-in-time guarantee.

---

## 4. 19-factor compatibility (prerequisite — full analysis in the contract doc)

The frozen F1 factor set is exactly (`research/horizon_component_replacement_v1_protocol.py:32-35`):

```
d5 d10 d20 d60 d120  p5 p10 p20 p60 p120  align  v5 v20 vc  rev5 rev10  dd20 dd60  rsi
```

The frozen implementation requires a **canonical market frame containing all six OHLCVA columns**,
enforced by `validate_market_frame` (`strategies/sw_sector_rotation/src/factors/sector_rotation.py:64, 86-109`):
`CANONICAL_COLUMNS = ("open","high","low","close","volume","amount")`, plus finite-only values,
strictly positive OHLC, non-negative volume/amount, and a strictly ascending duplicate-free `DatetimeIndex`.

Measured factor semantics (`:117-188`) — **all 19 are functions of `close` alone**; `volume`/`amount`
are validated for presence but not consumed:

| Group | Formula | Line |
|---|---|---|
| `d{n}` | `(close − MA_n(close)) / MA_n(close)` | `:126-128` |
| `p{n}` | `((close − min_n) / (max_n − min_n)).clip(0,1)` | `:129-132` |
| `align` | `((MA5>MA10)*3 + (MA10>MA20)*2 + (MA20>MA60)*1) / 6` | `:136-147` |
| `v5`,`v20` | rolling std of `close.pct_change(fill_method=None)`, windows 5/20 | `:156-159` |
| `vc` | `v5 / (v20 + 1e-10)` where `_EPS = 1e-10` | `:70`, `:160` |
| `rev5`,`rev10` | `− rolling_mean(pct_change, n)` | `:166-169` |
| `dd20`,`dd60` | `close / rolling_max(close, n) − 1` | `:177-178` |
| `rsi` | `100 − 100/(1+RS)`, `RS = mean(gains,14)/(mean(losses,14)+1e-10)` | `:184-188` |

**Financial semantics of `volume`/`amount` (the task's flagged v5/v20/vc question):**
`v5`, `v20` and `vc` are **price-return volatility**, not volume factors. `volatility` here means the
standard deviation of daily **returns**, so **no volume or amount input enters them at all**. The
`VOL_FEATURES` name is about return volatility. Consequently the v5/v20/vc question reduces entirely to
*"does the candidate source provide a usable daily close series?"* — not to whether a board's
volume/amount is financially interpretable.

Industry-level `volume` has **no clean financial meaning** in any candidate source: for a board index it
is a sum of member volumes in mixed units, which is why CNEquity declares `sector_bars.volume` as
`source_native` and explicitly warns the identity `amount ≈ close × volume` is meaningless for boards
(`docs/datasets/schema.md:172`). Fortunately the frozen factor set never consumes it.

Compatibility verdict:

| Source | 19-factor status | Reason |
|---|---|---|
| `industry_index` | **BLOCKED** | No `open/high/low/close/volume` columns at all; only `ret` + `amount`. Cannot build a canonical frame. |
| `sector_bars` | **SEMANTICALLY_CHANGED** | Full OHLCV present (frame constructible), but THS taxonomy ≠ Shenwan, and `volume`/`amount` are `source_native` board aggregates. |
| PIT Shenwan membership + stock `daily_bars` | **DERIVABLE** | Frame must be **constructed** by aggregating member OHLCVA; then all 19 are exact. |

---

## 5. Credentials

`CEQUITY_CREDENTIAL_REQUIREMENTS`:

| Environment variable | Required? | Scope | Storage recommendation |
|---|---|---|---|
| `TUSHARE_TOKEN` | **Optional** | Tushare Pro: BJ historical ST evidence (`stock_st` from 2017-01-01; `bak_basic` 2016 names) | Env var **preferred over config** — `docs/getting-started/configuration.md:81` |
| `HITHINK_FINANCE_API_KEY` | **Optional** | 同花顺 official API (`fuyao.aicubes.cn`), header `X-api-key`; arbitration snapshots + deep-history source swap. **Never owns a curated row** (ADR-0008) | Env var **preferred over config** — `docs/getting-started/configuration.md:92` |
| `HTTPS_PROXY` | **Optional** | EastMoney egress only; mainland networks do not need it | Env var — `:88` |

Code evidence: `src/cnequity/config/loader.py:625` (`os.environ.get("TUSHARE_TOKEN")`),
`:627` (`os.environ.get("HITHINK_FINANCE_API_KEY")`), config fallbacks at `:663-669`.
Both credential fields are declared `repr=False` (`:112`, `:118`) so they cannot leak through a
dataclass repr; the comments state they are "never written to manifests, checkpoints" (`:110-118`).

**No secret value was read or printed during this audit.**

### 5.1 Public-GitHub-safe configuration pattern

```toml
# configs/cnequity.toml  — COMMITTABLE. Contains no secrets.
[data]
root = "/data/cnequity"
[sources.tushare]
enabled = false          # off unless BJ historical ST is needed
# token intentionally omitted → read from TUSHARE_TOKEN
[sources.ths_official]
enabled = false          # optional
verify  = true           # safe: writes only meta/source_snapshots, never curated
backfill = false         # must be an explicit decision
# api_key intentionally omitted → read from HITHINK_FINANCE_API_KEY
```

`docs/getting-started/configuration.md:91` states the three decisions are separate: holding a
credential, enabling the source, and permitting it to change data.

**Lake-side redaction (strong positive control).** `[raw_archive]` is enabled by default and stores
compressed raw responses under `meta/raw`, but "**请求凭证、代理设置、Cookie 和 authorization 头一律不存档**"
(request credentials, proxy settings, cookies and authorization headers are never archived) —
`docs/getting-started/configuration.md:318`, implemented via `storage/raw_archive.py` (redacts request
secrets before archiving, per `config/loader.py:264`). This is the property that makes a
`meta/raw` archive safe to retain.

**GitHub implication:** the config template is secret-free by construction; credentials arrive only
through environment variables. However, `meta/raw` archives of *data responses* and the Parquet lake
still carry **upstream data-licensing** obligations that Apache-2.0 does not grant — see §6.

---

## 6. Source-licensing posture (relevant to publishing anything)

`docs/legal/source-matrix.md:20-33` is explicit that the matrix is a conservative operational register,
**not a licence grant**, and that unverified facts must be the literal `unknown` rather than a plausible
guess. Current status:

| Source | `commercial_use` | `redistribution` | Review date |
|---|---|---|---|
| `eastmoney` | `written_permission_required` | `prohibited_without_written_permission` | 2026-08-29 |
| `ths` | `written_permission_required` | `prohibited_for_free_products` | 2026-08-29 |
| all others (incl. `sw`, `tdx_protocol`, `sina`, `baostock`, `exchange`, `bse`, `cninfo`, `cni`, `pboc`) | `unknown` | `unknown` | `unknown` |

The registry defaults every unverified permission field to `unknown`, and `unknown` "一律产生待审阅/阻断结果"
(`:31`). The Shenwan source (`sw`) that would back the industry signal is reviewed as **`unknown`** on
all permission fields (`sources/SOURCES.yml:144-158`).

> **A derived dataset does not acquire upstream rights.** `sources/SOURCES.yml:189`:
> "使用权取决于所有输入来源，不能视为 CNEquity 授权."

**Consequence for ETF-Quant:** `industry_index` derives from `industry_members(source="sw")` ×
`daily_bars`, and `sector_bars` comes from `ths` with no second source. Neither path can be assumed
redistributable. Any future publication (GitHub, reports, shared snapshots) must be reviewed against
the actual upstream terms — this audit does not grant that permission and does not claim it.

---

## 7. Doc ↔ code drift found during this audit

These are recorded because the task requires binding conclusions to source rather than prose. In every
case below, **the code is authoritative and this audit used the code.**

| # | Document claim | Code reality | Evidence |
|---|---|---|---|
| D1 | `docs/datasets/schema.md:85` — `asset_type` is `stock/etf/index` | Emitted set is **`{stock, etf, cdr}`**; **no producer emits `index`** | `steps/delisted.py:426-434`, `adapters/baostock/instruments.py:78-86`, `adapters/tdx_protocol/client.py:291-296` |
| D2 | ADR-0011:106-121 — `pit_quality` falls back to literal `strict` for 29 datasets | Code emits `not_applicable` / `snapshot_only`; contract shows 29 `not_applicable`, 8 `snapshot_only`, 4 `reconstructed`, 1 `strict` | `domain/datasets.py:525-540`; `CHANGELOG.md:697` |
| D3 | `docs/datasets/contract.md:29` — lists 3 `pit_quality` values | Four values exist; the same file's warning block at `:34-44` lists all four | `domain/pit.py:38-43` |
| D4 | `docs/modules/domain.md:119` — `is_etf_symbol()` covers "SH `51/52/56/58`, SZ `15/16`" | The prefix set is wider: SH `501,502,510-518,52,53,56,58`; SZ `15,16` | `domain/symbols.py:34-52` |
| D5 | `domain/universe_profiles.py:66` documents `include_etf` as a profile dimension | **No code reads `include_etf`** — repo-wide the identifier appears only in its declaration (`:66`), serialization (`:106`), and the four `False` literals. It is inert. | exhaustive grep |
| D6 | `steps/bars.py:1171-1175` — "daily_bars does not carry the ETF and LOF quote codes that instruments also lists" | True **only** under the default `ingest="all_a"`; `steps/bars.py:3048-3051` documents the opposite under `all_instruments` | both sites |
| D7 | `derive/industry_index.py:1,111-112` — "Daily hfq returns" | Returns are computed from **raw** `close`, not `adj_close` | `:169`, `:173` (see the contract doc §3.1) |

**Contract consequence:** no conclusion in these four documents rests on a prose claim alone. Where a
document and the code disagreed, the code won and the drift is listed here.

---

## 8. Reproduce

```bash
git clone https://github.com/rootSunc/CNEquity.git D:/QuantForge/temp/cnequity-audit-v1/repo
cd D:/QuantForge/temp/cnequity-audit-v1/repo
git rev-parse HEAD       # 1650e384a3fd1f67a70144a489acc91432f1df27
git describe --tags      # v0.11.0-1-g1650e38

grep -n "requires-python" pyproject.toml
grep -n "INDUSTRY_INDEX_SCHEMA" -A 21 src/cnequity/domain/schemas.py
grep -n "LEVELS\|WEIGHTINGS\|_MIN_TRADED_AMOUNT" src/cnequity/derive/industry_index.py
grep -n "is_all_a_symbol" src/cnequity/adapters/sw/industry_history.py
grep -n "OFFSHORE_CONTRACTS" -A 1 src/cnequity/adapters/sina/global_futures.py
grep -n "include_etf" src/cnequity/domain/universe_profiles.py
python -c "import json;d=json.load(open('contracts/v0.11.0.json'));print(len(d['datasets']))"
```

No network request was made to any data source, no dependency was installed, and no production adapter
was implemented during this audit.
