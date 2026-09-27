# ETF-Quant V1 — CNEquity Data Contract (v1)

**Audit type:** READ-ONLY source audit + docs-only result. **No production adapter was implemented.**
**Owning task:** ETF-Quant V1 — CNEquity data contract / ETF mapping / benchmark audit.
**Baseline commit (main worktree):** `bd13d278b25eace66a7eae287307413f930effd9`

Companion documents:
[API inventory](cnequity_api_inventory_v1.md) ·
[Industry→ETF mapping contract](industry_etf_mapping_contract_v1.md) ·
[Benchmark source audit](benchmark_source_audit_v1.md)

## Audited artifact

| Item | Value |
|---|---|
| Repository | `https://github.com/rootSunc/CNEquity` |
| **Audited commit** | **`1650e384a3fd1f67a70144a489acc91432f1df27`** |
| `git describe` | `v0.11.0-1-g1650e38` |
| Declared version | **`0.11.0`** |
| Python requirement | **`>=3.10`** |
| Licence | Apache-2.0 (code only) |

---

## 0. Scope and product constraints assumed

ETF-Quant is `SIMULATION_ONLY`. Initial capital ¥10,000. External market data source is
**CNEquity ONLY**, behind an internal `DataAdapter` abstraction. Pipeline:

```
CNEquity industry data → industry factors → H10/H40/H120 independent Ridge
  → cross-sectional z-score → 0.25/0.50/0.25 fusion → Top5 industries
  → industry→ETF mapping → tradable ETF portfolio
```

Explicitly **not** factor-ranking all ETFs directly. Multi-ETF industries resolve by highest
20-trading-day average `amount` among admitted ETFs. Sizing is `softmax(final_score)` with a single-ETF
cap of 35%. Rebalance only when the Top5 membership set changes. Execution is T-close signal → T+1 open
simulated fill. Costs: commission 3 bps, slippage 5 bps per side, stamp duty 0, minimum commission 0 —
all to become configurable.

**This document defines only the data contract.** No strategy, no backtest, no execution was built.

---

## 1. Frozen F1 reference (read-only confirmation)

Confirmed against the working tree at the baseline commit; **nothing was modified.**

| Parameter | Value | Evidence |
|---|---|---|
| Ridge alpha | `0.01` | `strategies/sw_sector_rotation/src/model/model.py`; `research/development_iteration1_protocol.py:82` |
| Rolling window | `6` calendar months | `research/development_iteration1_protocol.py`; `spec.md:169` |
| Minimum valid training days | `30` | `spec.md:172` (`min_train_dates = 30`) |
| Horizons | `10 / 40 / 120` trading days | `research/horizon_component_replacement_v1_protocol.py:44` |
| Fusion weights | `0.25 / 0.50 / 0.25` | `:43` `FUSION_WEIGHTS = {"h10": 0.25, "h40": 0.50, "h120": 0.25}` |
| Top K | `5` | `model.py:36-37` (`top_n = 5`) |
| H10 factor set | `d10, p5, align, vc, dd20` | `:40` |
| 19-factor set (H40/H120 controls) | `d5 d10 d20 d60 d120 p5 p10 p20 p60 p120 align v5 v20 vc rev5 rev10 dd20 dd60 rsi` | `:32-35` |
| Fusion semantics | per-date **cross-sectional z-score**, then weighted average | `research/horizon_component_replacement_v1_protocol.py:181-182`; `tests/test_horizon_component_replacement_v1.py:108-110` |

The frozen frame contract requires **all six** OHLCVA columns
(`strategies/sw_sector_rotation/src/factors/sector_rotation.py:64`), validated by
`validate_market_frame` (`:86-109`): finite-only, strictly positive OHLC, non-negative
volume/amount, strictly ascending duplicate-free `DatetimeIndex`.

---

## 2. Declaration of the three industry-signal candidates

These are **three different things** and must never be called "申万指数" collectively.

| # | Candidate | Dataset | Taxonomy | Nature |
|---|---|---|---|---|
| **A** | CNEquity **derived** industry index | `industry_index` (derived, L5) | **Shenwan** (`801xxx` → 2/4/6-digit levels) | Locally computed **return** series |
| **B** | CNEquity / **THS** sector bars | `sector_bars` (curated, L7) | **同花顺** `881xxx` 行业 / `885xxx` 概念 | Vendor board **OHLCVA** price index |
| **C** | **PIT Shenwan membership × stock bars**, self-constructed | `industry_members(source="sw")` + `daily_bars` | **Shenwan** | To be constructed by the consumer |

### 2.1 Strict source semantics (required distinction)

| Class | Meaning | Evidence |
|---|---|---|
| `OFFICIAL_SHENWAN_CLASSIFICATION` | The Shenwan **membership/classification** fact: which stock is in which industry, as of a date. It is **not** a price series. | `industry_members` where `classification_system="sw"`, upstream `SwClass2021/StockClassifyUse_stock.xls` (`adapters/sw/industry_history.py:33-35`) |
| `CNEquity DERIVED INDUSTRY INDEX` | A **locally computed return** series over that membership. Reproducible from the lake; not a published index. | `derive/industry_index.py:1-7` |
| `THS SECTOR BARS` | 同花顺's **own** board index, a third taxonomy with no in-repo crosswalk to Shenwan. | `adapters/ths/boards.py:19`, `:58` |
| `ETF BARS` | Fund price/volume rows in `daily_bars` where `instruments.asset_type='etf'`. | `domain/schemas.py:137-148` |
| `STOCK BARS` | Individual equity rows in `daily_bars`. | same |

### 2.2 Permitted use, per class

| Class | industry factors | PIT membership | ranking | mapping | portfolio valuation | benchmark |
|---|---|---|---|---|---|---|
| `OFFICIAL_SHENWAN_CLASSIFICATION` | **No** (not a price series) | **Yes** (its purpose) | No | No (stocks only) | No | No |
| `CNEquity DERIVED INDUSTRY INDEX` | **No** — no OHLC (§4) | No | **Blocked** | No | No | No |
| `THS SECTOR BARS` | **Yes for price factors** — full OHLCVA | **No** — no membership at all | Partial (wrong taxonomy) | No | Only if the ETF tracks THS boards | No |
| `ETF BARS` | No | No | No | **Yes** (tradable leg) | **Yes** | No |
| `STOCK BARS` | Only as input to candidate C | No | No | No | No | No |

---

## 3. Candidate comparison

| Dimension | **A** `industry_index` | **B** `sector_bars` | **C** membership × stock bars |
|---|---|---|---|
| **PIT correctness** | **Good** — backward `join_asof` on `as_of_date` (`derive/industry_index.py:225-236`), monthly snapshots from 2020-01 (`:9-12`) | **None** — no membership concept; a board's constituents are whatever THS says today | **Good, same mechanism**, and under the consumer's control |
| **Source provenance** | `derived`; inputs `sw` + `tdx_protocol`/`sina` | `ths` only, **no second source** (`docs/datasets/catalog.md:299`) | `sw` + `daily_bars` sources |
| **OHLC** | **ABSENT** | **PRESENT** (open/high/low/close) | **Constructible** |
| **volume** | **ABSENT** | present, `source_native`, unit unreconciled | present per constituent (unit **shares**, contract-enforced) |
| **amount** | present, `source_native`, summed over priced members | present, `source_native` | present per constituent (unit **CNY**) |
| **Historical stability** | from 2020-01 (membership floor) | **行业 from 2007-08**, single consistent index base explicitly chosen to avoid a splice artefact that once produced a **fake +79% median jump** (`adapters/ths/boards.py:10-13`) | from 2020-01 |
| **Daily update** | `cne derive industry_index` (derived step) | `ths` board-kline; daily row is a snapshot, history via one-time backfill (`docs/datasets/catalog.md:305-306`) | consumer-driven |
| **Reproducibility** | **High** — deterministic function of lake contents; index and constituents "consistent *by construction*" (`:3-7`) | Medium — depends on THS's evolving board definitions; `change_pct` must be re-derived and the window's first bar is null (`boards.py:371-384`) | **High** |
| **19-factor compatibility** | **BLOCKED** (§4) | **SEMANTICALLY_CHANGED** | **DERIVABLE** |
| **Production suitability** | Not for this factor model | Viable **only** if the strategy is redefined around THS boards | **Best fit** |

### 3.1 A blocking defect in candidate A's price basis

`industry_index` returns are computed from **raw (unadjusted) `close`**, not adjusted close.

`derive/industry_index.py:132-140` requests adjusted bars:

```python
bars = load("daily_bars", start=start, end=end, adjust="hfq", symbols=symbols,
            strict_adj=False, config=config)
```

but the return series is then built from the **raw** column (`:168-175`):

```python
out = (
    bars.select("symbol", "trade_date", "close", "amount")   # <-- raw `close`
    .sort("symbol", "trade_date")
    .with_columns(
        pl.col("trade_date").shift(1).over("symbol").alias("_prev_trade_date"),
        pl.col("close").pct_change().over("symbol").alias("ret"),   # <-- raw pct_change
    )
)
```

`load(..., adjust="hfq")` appends `adj_open/adj_high/adj_low/adj_close/adj_is_exact`
(`docs/reference/python-api.md:56`). The code **never references `adj_close`**; `adjust="hfq"` serves
here only as a *coverage gate* — rows where `adj_is_exact` is false are dropped (`:143-155`). Since
`daily_bars` stores **unadjusted** prices and the lake derives adjustment at query time (ADR-0004), the
emitted `ret` is a **raw-price return**.

**Consequence:** ex-dividend and ex-rights price gaps are **not removed** from industry returns. Every
corporate action injects a spurious negative return into that member's contributor series and hence into
the industry mean. This is a silent, systematic bias — small per event, cumulative across a 124-industry
cross-section over years, and exactly the kind of contamination that `strict_adj` exists to prevent
elsewhere (`:124-128`). It also contradicts the module docstring's own claim to compute from "hfq stock
bars" (`:1`) and the registry comment "industry_members × hfq daily_bars" (`domain/datasets.py:1250`).

**This defect alone disqualifies candidate A** for a momentum/volatility factor model, independent of the
missing-OHLC problem in §4.

### 3.2 Other candidate-A limitations (for completeness)

- **Weighting caveat:** free-float market cap (the Shenwan convention) is unavailable because
  `valuation_metrics.float_mv` is only ~69% populated; only `equal` and `amount` are stored
  (`derive/industry_index.py:17-22`).
- **Coverage distortion is recorded, not corrected:** `n_members`/`n_priced`/`n_excluded` exist because
  BJ names (~5.6% of members overall, up to **43%** of some small industries) cannot enter the index
  without an adjustment factor (`:24-27`). A consumer must not ignore `n_excluded`.
- **Suspended-session guard:** `volume=0` rows are dropped so a carried-forward close cannot inject a
  fake zero return into the equal-weight mean (`:158-167`).
- **Gap-bridging guard:** `pct_change` would otherwise bridge a missing session and label a two-session
  move as one-day; the first row after a gap is dropped against the trading calendar (`:177-203`).
- **Degenerate-turnover guard:** `_MIN_TRADED_AMOUNT = 1.0`, because "a broken feed can report values
  like 5.9e-39 that are positive but not money" (`:46-47`, `:212-222`).
- **Null-not-zero rule:** a weighted average over no weights yields **null**, not 0 (`:289-294`).

These are genuinely good engineering choices. They do not remedy §3.1 or §4.

### 3.3 Candidate B limitations

- **Taxonomy mismatch.** Board codes are `881xxx` (行业) / `885xxx` (概念) — 同花顺's taxonomy, **not**
  Shenwan `801xxx` (`adapters/ths/boards.py:19`). No crosswalk ships with CNEquity.
- **Single source.** `ths` only; "该数据集**无第二个源**；失败即缺口" (`docs/datasets/catalog.md:299`).
  A single-source industry signal is a single point of failure with no reconciliation path.
- **Unit ambiguity.** `volume`/`amount` are `source_native` and the `amount ≈ close × volume` identity is
  explicitly declared meaningless for boards (`docs/datasets/schema.md:172`).
- **Selection/survivorship.** THS boards are a vendor product whose membership and existence can change;
  there is no dated membership history, so historical board composition is not auditable.
- **Sanitisation is aggressive and silent:** bars with any OHLC ≤ 0 are dropped, and bars where
  `volume>0` but `high<max(open,close)` or `low>min(open,close)` are dropped (`:348-351`). Dropping is
  correct, but a consumer counting rows must not assume a complete session series.

### 3.4 Candidate C requirements and cost

Constructing candidate C reproduces F1's own design: aggregate PIT Shenwan members' hfq bars into an
industry OHLCVA frame, then run the frozen 19 factors unchanged. Requirements:

1. PIT membership via backward as-of on monthly `as_of_date` snapshots — same mechanism as
   `_members_as_of` (`derive/industry_index.py:225-236`), which is sound.
2. **Adjusted** closes per constituent — must use `adj_close` (or `strict_adj=True`), **not** the raw
   `close` that candidate A mistakenly uses.
3. Explicit aggregation rules for `open`/`high`/`low`/`close`/`volume`/`amount` across members, and an
   explicit policy for `n_excluded` names.
4. Honest handling of the membership floor: **2020-01**.

Cost: this is construction work by the consumer, not a dataset CNEquity already provides.

---

## 4. 19-factor compatibility (item-by-item)

Status vocabulary: **DIRECT** · **DERIVABLE** · **SEMANTICALLY_CHANGED** · **UNAVAILABLE** · **BLOCKED**.

Because `validate_market_frame` requires all six OHLCVA columns, factor status depends on whether a
canonical frame can be built from the candidate at all.

### 4.1 Candidate A — `industry_index`

All 19 factors are **BLOCKED**. `INDUSTRY_INDEX_SCHEMA` (`domain/schemas.py:600-620`) contains
`trade_date, industry_code, level, weighting, ret, n_members, n_priced, n_excluded, amount` + provenance.
There is **no `open`, `high`, `low`, `close` or `volume`**, and no price level at all — only a fractional
`ret`. A canonical frame cannot be constructed, so `validate_market_frame` cannot pass. Additionally the
price basis is raw (§3.1).

### 4.2 Candidate B — `sector_bars`

Frame constructible (full OHLCV present). Factors whose status is **SEMANTICALLY_CHANGED**:
all, because the underlying series is a 同花顺 board index rather than a Shenwan industry, and
`volume`/`amount` are `source_native` board aggregates whose unit is unreconciled.

### 4.3 Candidate C — membership × stock bars

All 19 are **DERIVABLE**, exactly, provided the frame is built with adjusted prices.

### 4.4 Item-by-item table

| # | Factor | Frozen formula (line refs in `factors/sector_rotation.py`) | A | B | C | Notes |
|---|---|---|---|---|---|---|
| 1 | `d5` | `(close−MA5)/MA5` `:126-128` | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | needs `close` |
| 2 | `d10` | `(close−MA10)/MA10` | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | H10_C member |
| 3 | `d20` | `(close−MA20)/MA20` | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | |
| 4 | `d60` | `(close−MA60)/MA60` | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | |
| 5 | `d120` | `(close−MA120)/MA120` | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | needs 120 sessions |
| 6 | `p5` | `((close−min5)/(max5−min5)).clip(0,1)` `:129-132` | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | H10_C member |
| 7 | `p10` | as above, n=10 | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | |
| 8 | `p20` | n=20 | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | |
| 9 | `p60` | n=60 | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | |
| 10 | `p120` | n=120 | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | |
| 11 | `align` | `((MA5>MA10)*3+(MA10>MA20)*2+(MA20>MA60)*1)/6` `:136-147` | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | H10_C member |
| 12 | `v5` | `std(pct_change(close), 5)` `:156-159` | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | **price-return vol — no volume input** |
| 13 | `v20` | `std(pct_change(close), 20)` | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | **price-return vol — no volume input** |
| 14 | `vc` | `v5/(v20+1e-10)`, `_EPS=1e-10` `:70`, `:160` | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | **ratio of return vols — no volume input**; H10_C member |
| 15 | `rev5` | `−mean(pct_change, 5)` `:166-169` | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | |
| 16 | `rev10` | `−mean(pct_change, 10)` | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | |
| 17 | `dd20` | `close/max(close,20)−1` `:177-178` | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | H10_C member |
| 18 | `dd60` | `close/max(close,60)−1` | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | |
| 19 | `rsi` | `100−100/(1+RS)`, `RS=mean(gain,14)/(mean(loss,14)+1e-10)` `:184-188` | BLOCKED | SEMANTICALLY_CHANGED | **DERIVABLE** | |

### 4.5 The `v5` / `v20` / `vc` question — financial semantics of volume/amount

This is the task's explicit focus, so it is answered directly.

**`v5`, `v20` and `vc` contain no volume or amount term.** They are functions of `close` only:

```python
r = frame["close"].pct_change(fill_method=None)   # :156
out["v5"]  = r.rolling(5).std()                   # :158
out["v20"] = r.rolling(20).std()                  # :159
out["vc"]  = out["v5"] / (out["v20"] + _EPS)      # :160
```

The `VOL_FEATURES` name denotes **return volatility** (realised volatility of the industry series), not
volume. So the "volume/amount semantics" question does **not** affect v5/v20/vc at all. It reduces to a
single question: *does the candidate supply a usable daily close series?* For A: no. For B: yes, but on
the wrong taxonomy. For C: yes, exactly.

**What volume/amount mean in each candidate, and where they *would* matter:**

| Candidate | `volume` | `amount` | Usable as… |
|---|---|---|---|
| A | **absent** | sum of member amounts where `amount ≥ 1.0` else null (`:217-222`) | an industry **turnover proxy**, at the `amount` weighting only |
| B | THS board aggregate, `source_native`, unit **unreconciled** | THS board aggregate, `source_native` | **not** money; `amount ≈ close × volume` is declared meaningless for boards (`docs/datasets/schema.md:172`) |
| C | sum of constituent `volume`, unit **shares** (contract-enforced, `data_version=v2`) | sum of constituent `amount`, unit **CNY** | genuine industry turnover |

Note the volume-unit hazard: `daily_bars.volume` is contractually **shares**, but native units differ by
source (`tdx_protocol`=手 ×100, `ths`=股, `baostock`=股, `eastmoney`=手 *unverified*), and only
`data_version=v2` guarantees shares (`docs/datasets/schema.md:154-181`). A 100× error survives row-count
and OHLC checks and "足以毁掉一切换手率/流动性因子". Candidate C must therefore pin `data_version=v2` or
run CNEquity's own `daily_bars_volume_unit` quality check (`quality/unit_checks.py:172`).

**Where volume/amount legitimately enter the frozen strategy:** the risk module's
*Volume Concentration* red light uses the Top5 industries' **amount share > 0.35** (`spec.md:207`,
`test_risk.py:219`). That is a candidate-A/C `amount` consumer. Under candidate B its `amount` is
`source_native` and the share computation would be over unreconciled units. This is the one place the
volume/amount semantics question has real consequences — and it is outside the 19-factor model.

---

## 5. `RECOMMENDED_ETF_QUANT_INDUSTRY_SIGNAL_SOURCE`

```
RECOMMENDED_ETF_QUANT_INDUSTRY_SIGNAL_SOURCE = C
  PIT Shenwan membership (industry_members, classification_system="sw")
  × stock daily_bars with ADJUSTED closes, aggregated into an industry OHLCVA frame
```

### 5.1 Why C, and why not A or B

1. **A is blocked twice over.** It emits no OHLC at all, so the frozen frame validator cannot pass; and
   its returns are built from raw prices, so even a cumulated "level" would carry unremoved ex-date gaps
   (§3.1). It cannot support the 19-factor model.
2. **B is the wrong taxonomy.** Its OHLCVA is complete and its history is deeper (2007-08), but it
   describes 同花顺 boards (`881xxx`), not Shenwan industries (`801xxx`), with no crosswalk in-repo and
   no dated membership. Adopting B would silently **redefine the strategy's universe**, which is a strategy
   change, not a data-source substitution. B also has a single source with no reconciliation path.
3. **C preserves every frozen property.** Same Shenwan taxonomy as F1, same PIT as-of mechanism, an exact
   canonical frame, all 19 factors computed with the frozen code unchanged, `volume`/`amount` in
   contract-enforced real units, and full reproducibility from the lake.
4. **C is what F1 already requires.** The strategy consumes `{industry: canonical OHLCVA DataFrame}` and
   the core deliberately contains no data-download code (`spec.md:55-58`). C is the intended integration
   point; A and B would both require changing the frame contract.
5. **Honest cost of C:** membership begins **2020-01**, so roughly 5.7 years of history at the audit date,
   and the consumer must implement and validate the aggregation. The BJ exclusion distortion must be
   surfaced via `n_excluded`-style accounting rather than hidden.

**Not implemented.** This is a recommendation only. No aggregation code was written.

---

## 6. TIME / PIT CONTRACT

### 6.1 Verdict

```
TIME_SEMANTICS_BLOCKER
```

A **`NO LOOKAHEAD` guarantee cannot be proven from stored columns** for the datasets ETF-Quant needs.

### 6.2 Why

For `daily_bars`, `trading_calendar`, `industry_members`, `index_bars`, `industry_index` and `sector_bars`
the **only timestamp is `fetched_at`** — the lake's observation time, stored in UTC
(`docs/datasets/schema.md:12`). It is not an availability time, and it is **refreshed on reconciliation**
(the canonical layer sorts by `fetched_at` and keeps the last per primary key,
`domain/canonical.py:58-60,93`). So `fetched_at` cannot establish when a value became knowable: a row
observed today may describe a fact knowable last week, or a value revised today may replace one from last
month.

**A second, subtler trap:** even `observed_at` does not fix this. It is the **latest** lake observation,
not the first — `fetched_at`/`observed_at` are intentionally excluded from the compact business digest
precisely so a re-fetch does not manufacture a new revision (`storage/parquet.py:29`; `domain/pit.py:89-117`).
So `observed_at <= as_of` is not a "first seen" proof.

The bitemporal columns that would settle this — `available_at`, `source_published_at`, `observed_at`,
`revision_id` — are defined as exactly four columns (`domain/pit.py:48-53`) and apply **only** to the five
PIT disclosure datasets: `financial_statement_items`, `announcement_index`, `share_structure`,
`shareholder_counts`, `top_holders` (`domain/pit.py:72-80`). Enforcement is explicit: for any other
dataset `normalize_pit_storage_columns` returns the frame **unchanged** (`domain/pit.py:159-160`), and the
reader normalises only for `PIT_DATASETS` (`query/reader.py:427-428`). Of the four columns, **`available_at`
and `source_published_at` are written but always `null`** — no adapter supplies them (ADR-0011:81-83); only
`observed_at` (aliased from legacy `fetched_at`, `domain/pit.py:169-170`) and `revision_id` (a deterministic
96-bit hash, `REVISION_ID_HEX_CHARS = 24`, `domain/pit.py:67`) carry values.

Confirmed in the exported contract: `pit` = `false`, `pit_storage_columns` = `[]`, `pit_quality` =
`"not_applicable"` for every one of `daily_bars`, `index_bars`, `adj_factors`, `instruments`,
`trading_calendar`, `trading_status`, `industry_members`, `industry_index`, `sector_bars`,
`index_constituents`.

**`availability_col` is a naming convention, not evidence.** For these datasets the registry infers
`availability_col` from the business date column itself: `daily_bars`/`trading_calendar`/`index_bars`/
`industry_index`/`sector_bars` → `"trade_date"`; `industry_members`/`index_constituents` → `"as_of_date"`
(`domain/datasets.py:557-568`, `:578-580`). Declaring the trade date as the availability date is a
convention about when data is *expected* to be usable, not a stored observation of when it became
knowable.

**The one partial exception, and why it matters.** `trading_status` alone carries a per-row evidence class
computable from stored columns (`domain/trading_status.py:183-200`, columnar twin `:203-246`): rank 2
`EVIDENCE_POINT_IN_TIME` iff `source ∈ {eastmoney, eastmoney_cached, tdx_protocol}` **and** the Shanghai
date of `fetched_at` equals `trade_date` **and** the time is ≥ 15:00 (`SESSION_FINAL_AT`, `:147-149`); rank
1 for `source == "derived_bar_gap"` (explicitly reconstructed knowledge); rank 0 otherwise (a restatement
of a session it did not observe). Canonical selection uses this rank **before** recency
(`domain/canonical.py:31-42,51-57`). This is the pattern the other datasets lack — and its existence is
what proves the guarantee is absent elsewhere rather than merely undocumented.

Full PIT quality distribution across all 42 datasets (`domain/datasets.py:525-540`, verified against
`contracts/v0.11.0.json`): `strict` = 1 (`announcement_index`); `reconstructed` = 4
(`financial_statement_items`, `share_structure`, `shareholder_counts`, `top_holders`); `snapshot_only` = 8
(`analyst_consensus`, `economic_calendar`, `flash_news_wire`, `fund_flow`, `hot_rank`, `news_headlines`,
`sector_fund_flow`, `sector_members`); `not_applicable` = 29 (everything else, including every dataset in
the ETF-Quant path).

### 6.3 `as_of` does not help — it is silently ignored

`load(..., as_of=...)` is consumed **only** inside `if dataset in PIT_DATASETS:` (`query/reader.py:746`),
and `PIT_DATASETS` is derived from `PIT_DATASET_NAMES` — exactly the five disclosure datasets
(`domain/pit.py:72-80`, `reader.py:58`). For any other dataset, `as_of` is parsed at `:744` and then
**never used**: no error, no warning. (For the five PIT datasets it *does* enforce the argument — `:747-748`
raises when it is missing — which makes the silence for everything else easy to miss.)

**Consequence:** passing `as_of=` to a `daily_bars` or `industry_members` query gives a false sense of a
point-in-time restriction. A pipeline written that way would appear PIT-correct and not be.

### 6.4 The only dataset with a stored-column PIT ranking

As established in §6.2, `trading_status` is the sole dataset whose per-row PIT-ness is derivable from
stored columns, via the three-level `evidence_rank` (`domain/trading_status.py:183-200`). This is the model
to imitate — and its uniqueness is the proof that the others lack the property.

### 6.4.1 Documented drift recorded during this audit

Two in-repo documents describe pre-0.9 behaviour and should not be relied on:

- **ADR-0011 §"Known naming debt" (lines 106-121)** still states that `pit_quality` falls back to the
  literal `strict` for 29 datasets. The code now emits `not_applicable`/`snapshot_only`
  (`domain/datasets.py:525-540`); the migration to `not_applicable` is recorded in `CHANGELOG.md:697`.
  `contracts/v0.11.0.json` confirms the current distribution (29 `not_applicable`, 8 `snapshot_only`,
  4 `reconstructed`, 1 `strict`).
- **`docs/datasets/contract.md:29`** lists only three of the four `pit_quality` values, while its own
  warning block at `:34-44` lists all four.

Neither affects the ETF-Quant path directly, but both are examples of why this contract cites code rather
than prose.

### 6.5 Required contract (imposed on the consumer)

| Moment | Definition | Enforceable? |
|---|---|---|
| **T signal generation** | After T's close, using only sessions ≤ T | Yes **by convention**, on the trading calendar — not provable from columns |
| **T+1 open execution** | Fill at the T+1 session open | Yes — `daily_bars.open` at T+1, gated by `trading_status` |
| **Valuation time** | T close mark | Yes — `daily_bars.close` at T |

Because lookahead-freedom is not provable, the consumer must **assert it structurally**:

1. Build the frame from an explicit session list from `trading_calendar`; never infer sessions from the
   presence of rows.
2. Truncate by index position on that calendar, not by a timestamp comparison.
3. Compute `vc`'s denominator guard and all rolling windows strictly over past rows — the frozen
   implementation already does this (see `assert_no_lookahead` and the `[t-m, t)` z-score window,
   `spec.md:113-114`, `:290`).
4. Record `fetched_at` per run in the consumer's own manifest so a future revision can be detected, and
   treat any `fetched_at` change on an already-consumed session as a **revision event requiring review**.
5. Never pass `as_of=` to a non-PIT dataset and believe it did something.

### 6.6 Lookahead-free status by dataset

| Dataset | Only timestamp | Lookahead-free provable from columns? |
|---|---|---|
| `daily_bars` | `fetched_at` (UTC, refreshed) | **NO** |
| `trading_calendar` | `fetched_at` | **NO** — `is_trading` is only re-derived from weekday + a hard-coded holiday list (`domain/schemas.py:1050-1064`, `adapters/calendar/holidays_cn.py`) |
| `industry_members` | `fetched_at` (+ `as_of_date`) | **NO** — `as_of_date` is a *synthesised* month-end trading day for SW rows (`steps/structure.py:374-376`, `:44-52`), and `fetched_at` is the backfill time |
| `index_bars` | `fetched_at` | **NO** |
| `industry_index` | `fetched_at` | **NO** |
| `sector_bars` | `fetched_at` | **NO** |
| `trading_status` | `source` + `fetched_at` + `trade_date` | **PARTIAL YES** — `evidence_rank` 2 is a genuine point-in-time proof; rank 1 is explicitly reconstructed; rank 0 is a restatement |
| 5 PIT disclosure datasets | `available_at`, `source_published_at`, `observed_at`, `revision_id` | **YES**, with `pit_mode` — but note `available_at`/`source_published_at` are always null (§6.2) |
| `corporate_actions` | `fetched_at` | **NO** — and it is **not** a PIT dataset (`domain/datasets.py:835-852`), so `as_of` does not apply to it either |

### 6.7 Runtime gates that exist but are not stored proof

CNEquity does enforce session finality **at ingest time**, which is worth recording because it explains why
the lake's data is usually clean even though it cannot prove it after the fact:

| Gate | Value | Evidence |
|---|---|---|
| Daily-bar ingest cutoff | `A_SHARE_FINAL_AT = time(15, 5)` Asia/Shanghai — a 5-minute buffer after the 15:00 closing auction | `domain/market_time.py:11-13`; `steps/bars.py:64`, `:75-103` refuses to stage a window whose newest bar is still forming |
| Evidence cutoff | `SESSION_FINAL_AT = time(15, 0)` — a current-state board read at/after 15:00 on the session's own date counts as point-in-time | `domain/trading_status.py:147-149` |
| Post-hoc audit | Flags `volume > 0` bars whose Shanghai `fetched_at` is before 15:00 on their own `trade_date` as `daily_bar_preclose_observation` | `quality/bar_finality.py:33-42` |
| Timezone | `SHANGHAI_TZ` is a **fixed UTC+8 offset**, deliberately not an IANA database | `domain/market_time.py:8-10` |

These are **behavioural** guarantees, not per-row evidence. They tell the consumer that the lake tried to
avoid pre-close observations; they do not let a consumer prove, row by row and after the fact, that a given
historical value was knowable at a given `as_of`.

---

## 7. PRICE_ADJUSTMENT_CONTRACT

### 7.1 Storage

| Layer | Basis | Evidence |
|---|---|---|
| `daily_bars` (stored) | **UNADJUSTED** (`open/high/low/close` raw) | `docs/datasets/schema.md:144-147`; ADR-0004 |
| `adj_factors` (stored) | **`hfq` only**; `adjust_types` default `["hfq"]` | `docs/getting-started/configuration.md:114` |
| `qfq` | **derived at query time** | ADR-0004 |
| `index_bars` / `sector_bars` | indices/boards are **not adjusted**; `00` path keeps one convention | `adapters/ths/index_bars.py:8-9` |
| `industry_index.ret` | **raw-price** return, despite requesting hfq (§3.1) | `derive/industry_index.py:169,173` |

### 7.2 Formulas

| Query | Factor | Result |
|---|---|---|
| `adjust="hfq"` | `factor = sina_hfq_factor` | `adj_close = close × factor` |
| `adjust="qfq"` | `factor = 1 / sina_qfq_factor` | `adj_close = close × factor` |

Added columns: `adj_open, adj_high, adj_low, adj_close, adj_is_exact`
(`docs/reference/python-api.md:56`). Source: `sina`, backup `baostock`
(`docs/datasets/sources.md:132-133`).

### 7.3 The `strict_adj` trap — mandatory reading

`strict_adj=False` is the **default**. Rows lacking an adjustment factor are returned at **`factor = 1.0`**,
meaning **unadjusted prices appear inside an hfq result**, flagged only by `adj_is_exact=False`
(`docs/datasets/sources.md:139`). `strict_adj=True` raises `ReaderError` instead, but is not the default
because newly listed names always lack a factor at first (`:140`).

### 7.4 Contract rules for ETF-Quant

1. **Always** request adjusted prices explicitly and **always** check `adj_is_exact`.
2. **Never** mix bases within one series. In particular, never place candidate A's raw-price `ret`
   alongside an hfq-derived series.
3. Individual equities: `strict_adj=True` is recommended for a fixed historical research window (fail
   closed). For an expanding live window, use `strict_adj=False` **plus** an explicit
   `adj_is_exact` filter — exactly the pattern `derive/industry_index.py:143-155` uses.
4. ETFs: `adj_factors` covers ETF/LOF via Sina field **`s`**, while stocks use **`f`**
   (`docs/datasets/catalog.md:212`). Same lake column, different upstream field. Do not assume an ETF
   factor is comparable in derivation to a stock factor.
5. `index_bars`/`sector_bars` are **point levels**, not prices; the `amount ≈ close × volume` identity is
   meaningless there (`docs/datasets/schema.md:172`). Never apply a factor to them.
6. **Never** use `verify=False` anywhere.

---

## 8. MISSING DATA CONTRACT

Principles are absolute: **NO INTERPOLATION · NO SYNTHETIC HISTORY · NO SILENT REPAIR.**

The lake already models "absent" distinct from "zero", and the contract follows it:

| Situation | Lake representation | Required consumer behaviour |
|---|---|---|
| **Newly listed ETF** | `instruments.list_date` set; bars begin later | Exclude from ranking until a full 20-session window exists. Never rank on a partial window. |
| **Insufficient history** | Fewer rows than the window | Exclude. **Never** shorten the window — that is a silent methodology change. |
| **Missing trading day** | Row **absent** (source publishes nothing) | Do not forward-fill. Require coverage against `trading_calendar`. `coverage_mode="session_dense"` exists precisely to make an interior gap a defect (`domain/datasets.py:705`). |
| **Suspension** | Row may exist with **`volume=0, amount=0`** (`docs/datasets/schema.md:13`); `trading_status.status='suspended'` | Treat as non-trading. A suspended session is not a 0% return. |
| **`volume = 0`** | Explicit suspension/carried-forward marker | Exclude from returns and from liquidity averaging. |
| **`amount = 0`** | Same | Exclude. |
| **NaN** | Possible from a zero/invalid prior close | Insufficient data ⇒ **null, never 0** — the lake's own rule: "a weighted average over no weights is not zero" (`derive/industry_index.py:289-294`). Non-finite returns are dropped at the row boundary (`:210`). |
| **Degenerate feed values** | Whole-universe `amount ≈ 5.9e-39` observed once (`:212-216`) | Apply CNEquity's `_MIN_TRADED_AMOUNT = 1.0` floor (`:46-47`). A sub-yuan turnover is not money. |
| **Duplicate rows** | Compact dedupes by primary key, keeping max `fetched_at` (`docs/datasets/schema.md:860-862`) | Rely on the dataset contract. Do not add a second dedupe that could mask a contract violation. |
| **Rename** | `instruments.prev_symbol` (`docs/datasets/schema.md:88`) | Follow `prev_symbol`; never treat a rename as delist + relist. |
| **Delist** | `instruments.delist_date`; `trading_status.status='delisted'`, `is_trading=false`, `source='derived_delisted'` (`docs/datasets/sources.md:51`) | Exclude from the tradable set. Historical `delisted` rows are deliberately **not** backfilled (`docs/datasets/schema.md:135-136`) — a fact observed then must not be overwritten with today's knowledge. |
| **Survivorship** | Live boards list only what trades today; delisted codes require `cne backfill instruments` via baostock (`domain/datasets.py:618-620`) | A universe built only from the live feed is survivorship-biased. The baostock backfill is mandatory for any historical study. |
| **Adjustment factor missing** | `adj_is_exact=False` | Drop or fail closed (§7.3). Never treat as `factor=1.0` silently. |
| **Single-bar irreproducibility** | 1m bars: ~0.6% of bars differ in `volume`/`amount` on re-fetch (boundary attribution jitter); **session aggregates are exact** (`docs/datasets/schema.md:218-222`) | Out of scope — ETF-Quant is daily — but recorded so nobody later builds an intraday feature on single bars. |

### 8.1 Provenance requirement

Every consumed row must retain `source`, `data_version`, `fetched_at`
(`docs/datasets/catalog.md:176-180`). The consumer's own snapshot must pin:

- the CNEquity **commit** (`1650e384…` or later, explicitly recorded),
- the lake `data_version` per dataset,
- the **`daily_bars.data_version`** specifically, because only `v2` guarantees `volume` in shares (§4.5),
- per-dataset `coverage_start`/`coverage_end` from `list_datasets()` (`docs/reference/python-api.md:99-101`).

---

## 9. `CNEQUITY_CREDENTIAL_REQUIREMENTS`

| Environment variable | Required? | Scope | Storage recommendation |
|---|---|---|---|
| `TUSHARE_TOKEN` | **Optional** | Tushare Pro: BJ historical ST evidence (`stock_st` from 2017-01-01; `bak_basic` 2016 names) | Env var preferred over TOML (`docs/getting-started/configuration.md:81`) |
| `HITHINK_FINANCE_API_KEY` | **Optional** | 同花顺 official API (`fuyao.aicubes.cn`), header `X-api-key`; arbitration snapshots / deep-history swap. **Never owns a curated row** (ADR-0008) | Env var preferred over TOML (`:92`) |
| `HTTPS_PROXY` | **Optional** | EastMoney egress only; mainland networks need none | Env var (`:88`) |

**ETF-Quant needs none of them.** The entire recommended path (candidate C) runs on free sources:
`tdx_protocol` / `eastmoney` for bars, `sw` for Shenwan membership, `sina` for adjustment factors,
`tdx_protocol` / `exchange` for the calendar.

Code evidence: `config/loader.py:625` (`os.environ.get("TUSHARE_TOKEN")`), `:627`
(`os.environ.get("HITHINK_FINANCE_API_KEY")`), config fallbacks `:663-669`. Both fields are `repr=False`
(`:112`, `:118`) so they cannot leak via dataclass repr and are "never written to manifests,
checkpoints" (`:110-118`). **No secret value was read or printed during this audit.**

### 9.1 `PUBLIC_GITHUB_SAFE_CONFIG_PATTERN`

```toml
# configs/cnequity.toml — COMMITTABLE, contains no secrets
[data]
root = "/data/cnequity"

[sources.tushare]
enabled = false          # off unless BJ historical ST evidence is needed
# token omitted → read from TUSHARE_TOKEN

[sources.ths_official]
enabled  = false         # optional
verify   = true          # safe: writes only meta/source_snapshots, never curated rows
backfill = false         # must be a separate, explicit decision
# api_key omitted → read from HITHINK_FINANCE_API_KEY
```

`docs/getting-started/configuration.md:91` states the three decisions are independent: holding a
credential, enabling the source, and permitting it to modify data.

**Lake-side redaction (positive control).** `[raw_archive]` is enabled by default and stores compressed
raw responses under `meta/raw`, but **"请求凭证、代理设置、Cookie 和 authorization 头一律不存档"**
(`docs/getting-started/configuration.md:318`; `config/loader.py:264`, `storage/raw_archive.py`). This is
what makes a retained raw archive safe.

**Public-GitHub implication.** The config template is secret-free by construction and credentials arrive
only via environment variables, so publishing the *configuration* is safe. Publishing the **lake** is a
different question: Apache-2.0 licenses CNEquity's *code*, not upstream *data*, and `SOURCES.yml:189`
states a derived dataset does not acquire upstream rights. `eastmoney` is
`commercial_use: written_permission_required` / `redistribution: prohibited_without_written_permission`,
`ths` is `redistribution: prohibited_for_free_products` (both reviewed 2026-08-29), and the Shenwan source
`sw` is `unknown` on every permission field (`SOURCES.yml:144-158`). The registry treats `unknown` as
blocking (`docs/legal/source-matrix.md:31`). **No data snapshot may be published without a separate
licensing review.** This audit grants no such permission.

---

## 10. SIDECAR CONTRACT (recommendation — not implemented)

### 10.1 The frozen environment cannot host CNEquity

Measured against the frozen `quant-research:py3.12` container (read-only `importlib.metadata` query):

| CNEquity requirement (`pyproject.toml:46-80`) | Frozen container | Verdict |
|---|---|---|
| `polars>=1.0` | **ABSENT** | missing |
| `pyarrow>=15.0` | **ABSENT** | missing |
| `duckdb>=1.0` | **ABSENT** | missing |
| `baostock>=0.8` | **ABSENT** | missing |
| `snownlp>=0.12` | **ABSENT** | missing |
| `fastapi>=0.110`, `uvicorn>=0.27` | **ABSENT** | missing |
| `httpx>=0.25` | `0.28.1` | satisfied |
| `click>=8.1` | `8.5.0` | satisfied |
| `pandas>=2.0` | `2.3.3` | satisfied |
| `openpyxl>=3.0` | `3.1.5` | satisfied |
| `xlrd>=2.0` | `2.0.2` | satisfied |
| `PyYAML>=6.0` | `6.0.3` | satisfied |
| `curl_cffi>=0.7` | `0.16.3` | satisfied |
| `tomli>=2` (py<3.11 only) | `2.4.1` | n/a on 3.12 |
| (not required) `numpy` | `2.3.5` | — |
| (not required) `requests` | `2.34.2` | — |

**Six hard dependencies are absent.** Installing them into `quant-research` is forbidden by this task and
would violate the project's frozen-baseline rule (AGENTS.md §六) and the no-pip-install rule (§五.9).

### 10.2 Recommended environment boundary

```
┌─────────────────────────────────────────────┐
│ quant-research:py3.12   (FROZEN, untouched) │
│  Python 3.12.11 / Hikyuu / RQAlpha          │
│  NO CNEquity, NO polars/pyarrow/duckdb      │
│  Reads ONLY the export boundary (Parquet)   │
└──────────────────▲──────────────────────────┘
                   │  read-only, file-based export
                   │  Parquet + JSON manifest, no sockets, no client lib
┌──────────────────┴──────────────────────────┐
│ cnequity-sidecar   (SEPARATE image/env)     │
│  cnequity==0.11.0 + its own dependency set  │
│  Own data lake root, own meta/raw archive   │
│  Network egress allowed ONLY here           │
└─────────────────────────────────────────────┘
```

Rules:

1. **Separate image**, version-pinned, never merged into `quant-research:py3.12`.
2. **Separate data lake** root (own `[data].root`) — never inside `D:\quant-trading\data`.
3. **Export boundary is files, not a client library.** The frozen side must not `import cnequity`.
4. **One-way dependency:** sidecar → export → frozen. The frozen environment never writes back.
5. The frozen container's network policy stays as-is; CNEquity egress lives only in the sidecar.

### 10.3 Export boundary

| Aspect | Requirement |
|---|---|
| Format | Parquet (columnar, typed, hashable) |
| Read-only | Export directory mounted read-only into `quant-research` |
| Provenance | `source`, `data_version`, `fetched_at` retained **verbatim** on every row |
| Manifest | Side-by-side JSON: CNEquity commit, per-dataset `coverage_start`/`coverage_end`, row counts, export timestamp, SHA-256 per file, and `daily_bars.data_version` |
| Schema | One exported table per dataset; **no renaming** of lake columns (renaming destroys the audit trail) |
| Immutability | Exports are append-only generations; never rewrite an exported generation in place |

### 10.4 Read-only adapter boundary (inside the frozen environment)

The `DataAdapter` abstraction the product requires should be implemented on the **frozen side** over the
export, not over a CNEquity client:

- No network calls, no `pip` dependency on CNEquity.
- Validate schema against the manifest's recorded contract before use.
- Reject rather than repair: a schema mismatch, missing required column, or manifest hash mismatch is a
  hard failure.
- `verify=False` and any TLS-disabling path are forbidden.

### 10.5 Provenance fields required at the boundary

`dataset`, `source`, `data_version`, `fetched_at` per row; plus record-level `cnequity_commit`,
`export_id`, `export_created_at`, `file_sha256`, and for price data the `adj_is_exact` flag **whenever
adjusted prices are exported**.

### 10.6 Snapshot requirements

- Pin the CNEquity **commit SHA**, not just the version string — the v0.11.0 contract artifact is
  byte-identical to v0.10.0 and carries **no internal release identity** (§0.1), so the version number
  alone identifies nothing.
- Pin `daily_bars.data_version` (must be `v2` for shares).
- Record membership coverage floor (2020-01) explicitly in the manifest so downstream cannot mistake it
  for full history.
- Record `n_excluded`-equivalent member-coverage accounting so BJ exclusions stay visible.

**Not implemented.** This section is a recommendation.

---

## 11. Hard blockers

```
TIME_SEMANTICS_BLOCKER
  - daily_bars / trading_calendar / industry_members / index_bars / industry_index / sector_bars carry
    NO available_at / source_published_at / observed_at / revision_id.
  - The 4 bitemporal columns exist for exactly 5 disclosure datasets (domain/pit.py:48-53, 72-80);
    normalize_pit_storage_columns returns non-PIT frames UNCHANGED (pit.py:159-160).
  - Their only timestamp is fetched_at (UTC lake observation time), refreshed on reconciliation
    (domain/canonical.py:58-60, 93).
  - Their declared availability_col IS the business date itself (trade_date / as_of_date) — a naming
    convention, not stored evidence (domain/datasets.py:557-568, 578-580).
  - Even observed_at would not fix it: it is the LATEST observation, not the first
    (storage/parquet.py:29 excludes it from the business digest).
  - available_at / source_published_at are NEVER WRITTEN by any adapter — always null (ADR-0011:81-83).
  - as_of= is SILENTLY IGNORED for every non-PIT dataset (query/reader.py:746); the PIT set is exactly
    5 disclosure datasets (domain/pit.py:72-80).
  - trading_status is the ONLY dataset with a stored-column PIT ranking (evidence_rank,
    domain/trading_status.py:183-200); that uniqueness is the proof the others lack it.
  - => NO LOOKAHEAD cannot be proven from stored columns; it must be asserted structurally by the
    consumer, and ingest-time gates (A_SHARE_FINAL_AT 15:05, SESSION_FINAL_AT 15:00) are behavioural
    guarantees only, not per-row evidence.

PIT_QUALITY_DOC_DRIFT (informational)
  - ADR-0011:106-121 still documents the pre-0.9 pit_quality fallback to literal "strict" for 29 datasets;
    code now emits not_applicable / snapshot_only (domain/datasets.py:525-540, CHANGELOG.md:697).
  - docs/datasets/contract.md:29 lists 3 of the 4 pit_quality values while its own warning block lists 4.
  - Cite code, not these prose passages.

INDUSTRY_SIGNAL_SOURCE_BLOCKER (candidate A)
  - industry_index has NO open/high/low/close/volume -> a canonical 19-factor frame cannot be built.
  - industry_index returns are computed from RAW close (derive/industry_index.py:169,173) even though
    adjust="hfq" is requested at :136; adj_close is never referenced. Ex-date gaps are not removed.

MAPPING_SOURCE_GAP
  - No ETF tracking-index field, no fund-metadata dataset, no industry_code -> etf_code link.
  - All four universe profiles set include_etf=False; no ETF universe profile exists.
  - [universe].ingest defaults to "all_a", excluding ETF/LOF bars; enabling it has documented
    fetch-budget and coverage-gate costs.

BENCHMARK_SOURCE_GAP
  - NASDAQ Composite: not provided by CNEquity (no source label, no adapter, no symbol).
  - S&P 500: same. Only offshore instrument in the whole project is COMEX gold (GC0.CMX).
  - CSI 300 IS available (index_bars 000300.SH).

ENVIRONMENT_ISOLATION_BLOCKER
  - Frozen quant-research:py3.12 lacks 6 required CNEquity dependencies
    (polars, pyarrow, duckdb, baostock, snownlp, fastapi/uvicorn).
  - Installing them is forbidden; a separate sidecar environment is required.

SOURCE_LICENSING_UNRESOLVED
  - sw (Shenwan) permissions are "unknown" on every field; eastmoney and ths are restrictive.
  - A derived dataset does not acquire upstream rights (SOURCES.yml:189).
  - No data snapshot may be published without a separate licensing review.

CONTRACT_ARTIFACT_GAP
  - contracts/v0.11.0.json is byte-identical to v0.10.0.json and contains ZERO internal release identity.
  - It mentions ETF / benchmark / tracking index 0 times.
  - ETF-Quant's ETF and benchmark semantics are therefore NOT release-governed by CNEquity.
```

---

## 12. Codex prerequisites

Before any Codex implementation task may begin:

| # | Prerequisite | Status |
|---|---|---|
| 1 | User decision on the two missing benchmarks (accept CSI 300 only / authorise another source / mark null) | **OPEN** |
| 2 | User decision to adopt candidate **C** as the industry signal source (a strategy-preserving choice, but explicit) | **OPEN** |
| 3 | A separate CNEquity sidecar environment approved and created — never inside `quant-research` | **OPEN** |
| 4 | Sidecar pinned to a CNEquity commit with the export manifest contract defined | **OPEN** |
| 5 | ETF ingest scope decided (`all_instruments` vs a dedicated ETF scope) with its fetch-budget cost accepted | **OPEN** |
| 6 | `mapping_effective_from` / Layer-2 evidence for at least 5 ETFs, or an explicit decision to run with an empty tradable universe | **BLOCKED** — 0/124 validated today |
| 7 | Consumer-side lookahead assertions specified (structural, since columns cannot prove it) | **OPEN** |
| 8 | Acknowledgement that `industry_index` is unusable for this factor model, so it must not be used as a shortcut | **RECORDED** |
| 9 | Licensing review before publishing any data snapshot | **OPEN** |
| 10 | Confirmation that no F1 code, no Validation artefact, and no Shenwan canonical data is touched | **MANDATORY** |

None of these is satisfied by this audit. This audit produced **documents only**.

---

## 13. Reproduce

```bash
git clone https://github.com/rootSunc/CNEquity.git D:/QuantForge/temp/cnequity-audit-v1/repo
cd D:/QuantForge/temp/cnequity-audit-v1/repo
git rev-parse HEAD     # 1650e384a3fd1f67a70144a489acc91432f1df27

# Candidate A's raw-price return defect:
sed -n '132,140p;168,175p' src/cnequity/derive/industry_index.py
# Candidate A's schema has no OHLC:
grep -n "INDUSTRY_INDEX_SCHEMA" -A 21 src/cnequity/domain/schemas.py
# as_of is PIT-only:
grep -n "PIT_DATASET_NAMES" -A 9 src/cnequity/domain/pit.py
grep -n "if dataset in PIT_DATASETS" src/cnequity/query/reader.py
# 19 frozen factor semantics:
sed -n '117,188p' D:/quant-worktrees/deepseek-cnequity/strategies/sw_sector_rotation/src/factors/sector_rotation.py
# Frozen 19-factor list:
sed -n '32,44p' D:/quant-worktrees/deepseek-cnequity/research/horizon_component_replacement_v1_protocol.py
```

No network request was made to any data source, no dependency was installed, no Docker image or
configuration was changed, and no production adapter was implemented.
