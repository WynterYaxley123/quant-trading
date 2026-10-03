# ETF-Quant V1 — Benchmark Source Audit (CNEquity)

**Audit type:** READ-ONLY source audit. No production adapter was implemented.
**Owning task:** ETF-Quant V1 — CNEquity data contract / ETF mapping / benchmark audit.
**Baseline commit (main worktree):** `bd13d278b25eace66a7eae287307413f930effd9`

## Audited artifact

| Item | Value |
|---|---|
| Repository | `https://github.com/rootSunc/CNEquity` |
| Clone location | `D:\QuantForge\temp\cnequity-audit-v1\repo` (outside the main repo) |
| Audited commit | `1650e384a3fd1f67a70144a489acc91432f1df27` |
| Branch | `main` |
| `git describe` | `v0.11.0-1-g1650e38` (exactly one docs commit after tag `v0.11.0`) |
| Declared version | `0.11.0` (`pyproject.toml:7`) |
| Licence | Apache-2.0 |

---

## 1. Required benchmarks and verdict

ETF-Quant V1 requires three benchmarks: **CSI 300**, **NASDAQ Composite**, **S&P 500**.
The frozen product requirement is that **all benchmark data is preferentially sourced from CNEquity**, and any unsupported benchmark must be reported as a GAP — never silently substituted from another provider.

| Benchmark | Status | CNEquity API | Symbol / code | Source |
|---|---|---|---|---|
| **CSI 300** (沪深300) | **AVAILABLE** | `load("index_bars", symbols=["000300.SH"])` | `000300.SH` (lake symbol) | `tdx_protocol` primary; `eastmoney` backup; history as far back as **2005-01-04** via `ths` |
| **NASDAQ Composite** | **NOT_AVAILABLE** | — | — | — |
| **S&P 500** | **NOT_AVAILABLE** | — | — | — |

**Two of the three required benchmarks are `BENCHMARK_SOURCE_GAP`.**

---

## 2. CSI 300 — AVAILABLE

### 2.1 Evidence

| Field | Value | Evidence |
|---|---|---|
| Dataset | `index_bars` | `src/cnequity/domain/datasets.py:67` (unit contract), `:708` (spec) |
| Primary key | `(symbol, trade_date, frequency)` | `docs/datasets/schema.md:61` |
| Partition | `trade_date` (by **year**) | `docs/datasets/schema.md:41` |
| Columns | `symbol, trade_date, open, high, low, close, volume, amount, frequency, source, data_version, fetched_at` | `docs/datasets/schema.md:183-187` |
| Lake symbol | `000300.SH` | `src/cnequity/adapters/tdx_protocol/client.py:59`, `src/cnequity/adapters/ths/index_bars.py:47` |
| THS mapping | `000300.SH` → `399300` (同花顺 code) | `src/cnequity/adapters/ths/index_bars.py:47` |
| History floor | **2005-01-04** | `src/cnequity/adapters/ths/index_bars.py:47` (comment: `沪深300, from 2005-01-04`) |
| Primary source | `tdx_protocol` | `docs/datasets/catalog.md:205` |
| Backup source | `eastmoney` | `docs/datasets/sources.md:74` |
| Frequency | daily (`frequency = "1d"`) | `src/cnequity/adapters/ths/index_bars.py:85` |

`000300.SH` is in the explicit TDX index seed list (`INDEX_SYMBOLS`, `src/cnequity/adapters/tdx_protocol/client.py:53-62`), so it is fetched by the daily `index_bars` step, and it is in the THS index map, so deep history is backfillable per year.

### 2.2 Documented limitations (must be carried into the contract)

1. **Lake `index_bars` starts 2016** with the primary TDX path; the THS backfill is what deepens it to the index base date (`src/cnequity/adapters/ths/index_bars.py:3-6`). A benchmark series that is silently short at the start will bias every relative statistic computed over the early window.
2. **`index_bars.volume` is NOT shares, and `amount` is NOT rescaled.** The unit contract is `price: index_point`, `volume: source_native`, `amount: source_native` (`src/cnequity/domain/datasets.py:67-71`). `docs/datasets/schema.md:187` states explicitly that `index_bars`/`sector_bars` retain the raw TDX `index()` values and that the unit could not be reconciled — the index `amount` was 77% of the sum of SH constituent `amount`, while `volume` differed by ~300×. Both datasets therefore remain `data_version=v1`. **Consequence: CNEquity's CSI 300 volume/amount must not be used as a benchmark turnover measure.** Close/OHLC in index points is usable.
3. **`399001.SZ` has 18 verified holes (1991–1995)** that both TDX and THS fail to return (`docs/datasets/sources.md:77`). This affects 深证成指, not CSI 300, but it demonstrates that index history in this lake is not guaranteed gap-free at the deep end. CSI 300 was not reported as having such holes.
4. The lake symbol for CSI 300 is `000300.SH`, which is **not** the exchange's own numeric identity ambiguity-free: `000300` is also a valid SZ-listed stock code space, and `000001.SH` (上证综指) collides numerically with `000001.SZ` (平安银行). The exchange suffix is load-bearing and must always be carried.

### 2.3 Verdict

**CSI 300 = AVAILABLE**, usable as a daily close/OHLC benchmark in index points from 2005-01-04 (after THS backfill) and from 2016 (TDX-only). Do **not** use its volume/amount.

---

## 3. NASDAQ Composite — NOT_AVAILABLE

### 3.1 Evidence of absence

The claim is an absence claim, so it is supported by exhausting the candidate surface rather than by one citation.

**(a) The source-policy registry contains 14 source labels, and none is a US equity venue.**

`docs/legal/source-matrix.md:9` states the matrix source set is derived from every `DatasetSpec`'s `primary_source`, `backup_source` and `backfill_source`. Enumerating `sources/SOURCES.yml`: `tdx_protocol`, `baostock`, `exchange`, `eastmoney`, `sina`, `eastmoney_kline+sina_global`, `cninfo`, `cni`, `sw`, `pboc`, `derived`, `ths`, `bse`, `ths_official` — **14 labels, all China-domestic** (exchanges, Chinese vendors, Chinese regulators, or local derivation). There is no NASDAQ, NYSE, CBOE, ICE, or any non-Chinese market-data publisher.

**(b) The only offshore instrument in the entire project is COMEX gold.**

`src/cnequity/adapters/sina/global_futures.py:31`:

```python
OFFSHORE_CONTRACTS: tuple[tuple[str, str, str, str], ...] = (("GC0.CMX", "GC", "COMEX黄金", "CMX"),)
```

This is a single-entry tuple. The module docstring (`:1-4`) calls it "Sina global futures daily K-line (offshore)" and says "currently COMEX gold continuous". `docs/datasets/catalog.md:211` confirms `commodity_bars` offshore coverage is "COMEX金 `GC0.CMX`" and `docs/datasets/schema.md:309` states "外盘 v1 **仅黄金**；不进 A 股回测引擎" (offshore v1 is **gold only**; not admitted into the A-share backtest engine).

**(c) The TDX index seed list is eight China indices only.**

`src/cnequity/adapters/tdx_protocol/client.py:53-62` (`INDEX_SYMBOLS`): `000001.SH`, `399001.SZ`, `399006.SZ`, `000688.SH`, `000016.SH`, `000300.SH`, `000905.SH`, `000852.SH`. All are SSE/SZSE indices.

**(d) The THS index-code map is seven China indices only.**

`src/cnequity/adapters/ths/index_bars.py:44-52` (`INDEX_CODE_MAP`): `000001.SH`, `000016.SH`, `000300.SH`, `000688.SH`, `000905.SH`, `399001.SZ`, `399006.SZ`. The module raises `KeyError` for any unmapped symbol (`:105-107`) rather than guessing — so a NASDAQ symbol cannot be quietly fetched through this path.

**(e) A full-text search across the repository for overseas equity-index identifiers returns no implementation.**

Searching all `.py/.toml/.yml/.yaml/.md/.json` for `NASDAQ|Nasdaq|nasdaq|S&P 500|SP500|GSPC|IXIC|.DJI|道琼斯|标普|纳斯达克|恒生|HSI|HSTECH` returns only three hits, all in test files and none an adapter:

- `tests/unit/test_minute_bars_step.py:97` — `cfg.minute_bars_scope = "sp500"`, a unit-test fixture exercising minute-bar scope *parsing*, not S&P 500 data.
- `tests/unit/test_ths_official_client.py:142,152` — the literal `https://o.thsi.cn/x`, an incidental substring match on `x`, not an index symbol.

**(f) `macro_indicators` carries no overseas equity series.** Its adapters are `eastmoney` + `pboc` (`src/cnequity/domain/datasets.py:1091-1098`); `src/cnequity/adapters/macro/indicators.py` reads SHIBOR, LPR, PMI, money supply and social financing. `docs/datasets/catalog.md:288` lists the source as `eastmoney / pboc（社融）`.

### 3.2 Verdict

**NASDAQ Composite = NOT_AVAILABLE.** No API, no symbol, no adapter, no source label. This is a **`BENCHMARK_SOURCE_GAP`**.

---

## 4. S&P 500 — NOT_AVAILABLE

Identical evidence basis to §3: the same 14-label China-only source registry, the same single-entry COMEX-gold-only offshore contract, the same eight/six-entry index symbol maps, and the same nil full-text result. `macro_indicators` carries no US index series.

### 4.1 Verdict

**S&P 500 = NOT_AVAILABLE.** This is a **`BENCHMARK_SOURCE_GAP`**.

---

## 5. Benchmark gaps (consolidated)

```
BENCHMARK_SOURCE_GAP: NASDAQ Composite — not provided by CNEquity (no source label, no adapter, no symbol)
BENCHMARK_SOURCE_GAP: S&P 500           — not provided by CNEquity (no source label, no adapter, no symbol)
```

### 5.1 Consequences for ETF-Quant V1

1. **Two of three mandated benchmarks cannot be satisfied inside the CNEquity-only data boundary.**
2. The frozen requirement forbids silently substituting another provider to fill these gaps. Therefore NASDAQ Composite and S&P 500 must remain **unpopulated** until the user makes an explicit decision. This audit does **not** make that decision and does **not** introduce any fallback source.
3. **Do not** treat COMEX gold (`GC0.CMX`) as a substitute for either equity benchmark — different asset class, different session calendar, and explicitly excluded from the A-share backtest path by CNEquity's own schema documentation.
4. The metrics that depend on these two benchmarks (overseas relative strength, cross-market regime comparison) are **blocked**, not merely degraded. The CSI 300 leg is unaffected.

### 5.2 Options that do not violate the no-silent-fallback rule

These are recorded as options for a future explicit decision; none is implemented or recommended here:

| Option | Effect | Caveat |
|---|---|---|
| Accept CSI 300 as the only benchmark for V1 | Removes two gaps by narrowing scope | Requires an explicit user amendment to the frozen benchmark requirement |
| Add a separately-licensed non-CNEquity source for the two US indices | Satisfies the requirement literally | Directly contradicts "no third-party fallback"; needs explicit user authorization and its own source-policy review |
| Report relative metrics against CSI 300 only and mark cross-market metrics null | Honest and immediate | Cross-market conclusions become unavailable |

Any of these requires a **user decision**. This audit records the gap and stops.

---

## 6. Timezone / calendar note (applies if the gaps are ever filled)

CNEquity's global convention is that all `trade_date` and business timestamps are `Asia/Shanghai`, and all lake symbols are `{code}.{SH|SZ|BJ}` (`docs/datasets/schema.md:9-11`). A US equity series has a different session calendar and a different publication clock. Injecting one into this lake would require an explicit alignment policy — CNEquity already models this problem for `commodity_bars`, which carries `trade_date` as "源交易所会话日（外盘为 COMEX 日历；与 A 股对齐在研究侧 as-of）" (`docs/datasets/schema.md:295`) — i.e. alignment is explicitly deferred to the research side, not baked into the lake. Any future US benchmark ingestion must copy that approach and must not silently re-stamp US sessions as A-share sessions.

---

## 7. Reproduce

```bash
# Clone (outside the main repo)
git clone https://github.com/rootSunc/CNEquity.git D:/QuantForge/temp/cnequity-audit-v1/repo
cd D:/QuantForge/temp/cnequity-audit-v1/repo
git rev-parse HEAD          # 1650e384a3fd1f67a70144a489acc91432f1df27
git describe --tags         # v0.11.0-1-g1650e38

# Absence checks (no network, read-only)
grep -rn "OFFSHORE_CONTRACTS" src/cnequity/adapters/sina/global_futures.py
grep -n  "INDEX_SYMBOLS"      src/cnequity/adapters/tdx_protocol/client.py
grep -n  "INDEX_CODE_MAP"     src/cnequity/adapters/ths/index_bars.py
grep -rn "NASDAQ\|SP500\|GSPC\|IXIC" --include=*.py --include=*.md --include=*.toml .
```

No network request was made and no dependency was installed during this audit.
