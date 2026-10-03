# TRADING_STATUS_EMPTY_ROOT_CAUSE — audit v1

**Task:** ETF-Quant V1 — CNEquity production coverage + active industry universe admission audit.
**Base commit:** `bd218fb79389fdd3e8af1b06997e8c7af2bd1610`
**Evidence:** pinned CNEquity source at `1650e384a3fd1f67a70144a489acc91432f1df27`, plus the real lake.

---

## 1. Headline

```
TRADING_STATUS_EMPTY_ROOT_CAUSE = INGESTION_SCOPE_NOT_A_SOURCE_FAILURE
```

`trading_status` was admitted empty in the previous round because of **my own bounded ingestion scope**,
not because CNEquity lacks the capability. The native dataset **is** produced and **is** populated in the
lake — for the 5 symbols the demo profile ever fetched.

**But there is a second, genuine and separate finding:**

```
NATIVE_ETF_TRADING_STATUS = STRUCTURALLY_UNAVAILABLE
```

`trading_status` cannot cover ETFs at all. That is a real contract gap, not a scope accident.

These are two different problems and the previous round's single `TRADING_STATUS_EMPTY` blocker conflated
them. They are separated below.

---

## 2. Dataset provenance

| Layer | Value | Evidence |
|---|---|---|
| Registration | `DatasetSpec("trading_status", ...)` | `src/cnequity/domain/datasets.py` |
| Primary source | **`eastmoney`** | registry; the daily feed is EastMoney's current-state board |
| Backup source | `exchange` | both exchanges publish every listed security with OHLC and 证券简称 |
| Supplementary | `derived`, `bse` | `derived_bar_gap` / `derived_delisted`; BSE route for Beijing |
| Backfill source | `baostock` | the per-day `isST` sweep |
| Producer step | `@register_step("trading_status", group="core")` → `step_trading_status` | `src/cnequity/steps/reference.py:522` |
| Daily adapter | `fetch_trading_status_eastmoney` | `src/cnequity/adapters/eastmoney/trading_status.py:133` |
| Columns | `symbol, trade_date, is_trading, status, risk_warning, source, data_version, fetched_at` | `domain/schemas.py` |
| Status values | `normal` / `suspended` / `delisted`; `risk_warning` is orthogonal and nullable | `domain/trading_status.py` |

The dataset is **fully implemented**. No placeholder, no unfinished path.

---

## 3. Actual lake state

| Metric | Value |
|---|---|
| Rows | **12,447** |
| Symbols | **5** — `000001.SZ 000858.SZ 300750.SZ 600519.SH 601318.SH` |
| Date range | **2016-01-04 → 2026-09-24** |
| Source | **`baostock` 12,447 / 12,447** |
| `status` | `normal` 12,447 / 12,447 |
| `risk_warning` | (all-A stock rows; no ETF rows exist) |

So the table is **not empty in the lake**. It was empty **in the export**, because the export queries
`trading_status` scoped to the three ETF symbols — and there are no ETF rows to return.

### 3.1 Why the date range starts at 2016

`baostock` ST evidence begins 2016 for SH/SZ (`docs/datasets/sources.md`). The 12,447 rows are the
baostock `isST` sweep for the 5 demo symbols, all resolving to `normal`.

---

## 4. Root cause, precisely

Three independent facts compound:

### 4.1 The demo profile only ever fetched 5 symbols

`cne init --profile demo` created a 5-symbol lake. **Every** subsequent `trading_status` write in this
lake descends from that scope, because both the daily feed and the ST backfill read the lake's symbol
universe.

### 4.2 The ST backfill resolver rejects ETFs by construction

`src/cnequity/steps/reference.py:905-920`:

```python
def _resolve_explicit_st_symbols(config: Config, raw: list[str]) -> list[str]:
    ...
        if len(candidates) != 1 or not _is_all_a(candidates[0]):
            raise ValueError(
                f"trading_status ST backfill cannot resolve {value!r} "
                f"to exactly one all-A instrument"
            )
```

and the default universe path (`:923-933`):

```python
    universe = current_st_universe(config, start=start, end=end)
    if not universe:
        universe = [symbol for symbol in load_symbols(config) if _is_all_a(symbol)]
```

This is the observed failure verbatim:

```
ValueError: trading_status ST backfill cannot resolve '510300.SH' to exactly one all-A instrument
```

### 4.3 The daily EastMoney board cannot contain an ETF either

`src/cnequity/adapters/eastmoney/trading_status.py:124-130` builds the suspension set and filters it:

```python
        if is_all_a_symbol(code, exch):
            symbols.add(format_symbol(code, exch))
```

so **no ETF can ever enter the suspended set**, and `is_trading` for an ETF from this path would be
`True` unconditionally (`:158`). The ST set is built the same way, so `risk_warning` for an SH/SZ ETF
resolves to `False` (`:160`) — an *asserted* clean reading from a board that structurally cannot contain
the instrument. (This "asserted clean" trap was independently recorded in
[`industry_etf_mapping_contract_v1.md`](industry_etf_mapping_contract_v1.md) §8.1.)

### 4.4 The daily feed never ran at all in this lake

The demo config carries no `[job.daily.groups]` section, so `cne run daily --group ...` is rejected
("未知调度组"). Only the explicit `backfill` path ran. **Every day-path producer of `trading_status` is
therefore untested in this lake.**

---

## 5. Why empty — the eight questions answered

| # | Question | Answer |
|---|---|---|
| 1 | Why is the dataset empty? | It is not empty in the lake (12,447 rows); it was empty **in the export**, because the export scope was ETFs and ETFs are unsupported |
| 2 | Does the current source not provide it? | **It does.** EastMoney (daily), exchange boards, baostock ST, derived bar-gap, BSE — all implemented |
| 3 | Wrong query scope? | **Yes** — the export asked for ETF symbols the dataset cannot hold |
| 4 | Wrong date range? | **No** — the range 2026-08-01…2026-09-24 is inside the produced range |
| 5 | Ingestion flag off? | **Effectively yes** — no daily group is configured, so only the backfill path ran |
| 6 | Schema placeholder? | **No** — one of the most developed schemas in the lake |
| 7 | Only certain instruments? | **Yes, decisively** — all-A **stocks** only; ETFs are excluded at every path |
| 8 | Unfinished implementation? | **No** |

---

## 6. Is native trading status available?

```
NATIVE_TRADING_STATUS_AVAILABLE_FOR_STOCKS = YES
NATIVE_TRADING_STATUS_AVAILABLE_FOR_ETFS   = NO (STRUCTURALLY)
```

### 6.1 For stocks (the Source-C constituents) — YES, and recoverable

Fully recoverable with no contract change. Two supported routes:

| Route | Command | Notes |
|---|---|---|
| baostock ST backfill, scoped | `cne backfill trading_status --symbols <all-A membership symbols>` | per-symbol sweep; **works** (proved by the 12,447 existing rows) |
| daily EastMoney feed + exchange backup | `cne run daily --group core` with a full config | the intended production path; also gives day-level halt detection |

Because the ETF-Quant **stock universe is all-A** (SH/SZ/BJ stocks, excluding funds), the native dataset
covers it. **`TRADING_STATUS_EMPTY` is therefore NOT a genuine blocker for Source-C construction** — it
was a scope artifact. It only becomes a blocker for ETF executability.

### 6.2 For ETFs (the execution leg) — NO, and not fixable by scope

ETF trading status cannot be produced by any registered path:

| Path | ETF coverage |
|---|---|
| EastMoney suspension board | excluded by `is_all_a_symbol` |
| EastMoney ST board | excluded by `is_all_a_symbol` (`risk_warning=False` asserted) |
| baostock ST backfill | rejected by `_is_all_a` resolver |
| `derived_bar_gap` | **asset-agnostic — would cover an ETF that has bars** |
| `exchange` board backup | **covers ETFs** (`_keep_symbol` = `is_all_a_symbol or is_etf_symbol`) |
| `derived_delisted` | **asset-agnostic** — covers any symbol with a `delist_date` |

So ETFs are not *universally* unsupported: the **derived** and **exchange** paths can carry them, but the
primary daily path cannot, and the backfill refuses to accept them as input. There is **no supported
command** that produces ETF trading status today.

---

## 7. `PROPOSED_TRADABILITY_FALLBACK_CONTRACT`

### 7.1 Status

```
NOT APPROVED
```

This is a proposal for a Codex contract decision. It is **not implemented**, not wired into any runtime,
and not used by any audit result in this repository. The task's prohibition is respected: nothing in this
round treats "bar exists" as tradable, and no `open > 0 and amount > 0` rule was applied anywhere.

### 7.2 The gap

The frozen contract requires `trading_status` for tradability. For ETFs that requirement is unsatisfiable
natively. Leaving it unmet means **ETF execution cannot be gated at all** for the chosen universe.

### 7.3 Proposed contract (for review only)

```
ETF is TRADABLE on session T+1  iff ALL of:
  1. instruments.asset_type == "etf"                       (identity)
  2. instruments.list_date <= T                            (listed at signal time)
  3. instruments.delist_date is null or > T+1              (not delisted)
  4. a daily_bars row exists for (etf, T+1)                (session actually traded)
  5. that row has open > 0 and high/low/close > 0          (real prices, not a placeholder)
  6. that row has amount > 0                               (turnover actually occurred)
  7. that row has volume > 0                               (agrees with amount)
otherwise NOT tradable.
```

Explicitly **required** properties, each of which must be stated in any approved version:

| Requirement | Reason |
|---|---|
| This is a **proxy**, not the vendor trading-status fact | It infers tradability from the bar, and it must be labelled as inferred |
| It must be **fail-closed**: any missing field ⇒ NOT tradable | A missing bar must never mean "traded fine" |
| It must **not** override native status where native exists | For stocks, native `trading_status` remains authoritative |
| `volume > 0` is load-bearing | Suspension is represented as a carried-forward row with `volume=0, amount=0`; without this clause a suspended ETF would look tradable |
| It cannot detect a **price-limit queue with no fill** | A limit-up ETF can have a valid bar and still be unbuyable. The proxy cannot see this |
| It cannot detect a **halt declared after the close** | Intrada suspension announcements are not in this lake |
| T+1 is a **lower bound** on execution | Per the frozen F1 contract, `execution_date` is a lower bound, not a guarantee |

### 7.4 Known holes, stated plainly

| Hole | Consequence |
|---|---|
| No suspension flag for ETFs | An ETF suspended on T+1 has no bar ⇒ clause 4 fails ⇒ NOT tradable. **Correct by accident**, which is acceptable but must be understood |
| Limit-up / limit-down queues | **Undetectable.** The proxy will call such an ETF tradable |
| Intraday halts (临时停牌) | **Undetectable** at daily frequency |
| Pre-open suspensions announced same day | **Undetectable** at this granularity |
| `amount` null on the Sina route | Clause 6 fails ⇒ fail-closed ⇒ **an ETF whose bars came from Sina would be permanently non-tradable**. This interacts directly with the amount-coverage finding in the coverage audit |

### 7.5 Consequence if the proposal is rejected

If no ETF tradability contract is approved, then either:

- the ETF execution leg cannot be gated and **no Shadow epoch may be started** (correct outcome), or
- the universe must be restricted to instruments with native status — i.e. **stocks**, which cannot be
  bought as the strategy's execution vehicle.

Either way this is a **contract decision**, recorded as `CODEX_CONTRACT_CHANGE_REQUIRED`.

---

## 8. Hard blockers

```
TRADING_STATUS_EMPTY (reclassified)
  - NOT a source failure and NOT a blocker for Source-C stock construction.
  - It was an ingestion-scope artifact of the bounded demo lake.
  - Recoverable for stocks by a scoped backfill; no contract change needed.

NATIVE_ETF_TRADING_STATUS_UNAVAILABLE
  - ETFs are excluded from the EastMoney daily board (suspended + ST sets) and rejected by the
    baostock ST backfill resolver.
  - The derived_bar_gap and exchange paths are asset-agnostic and could carry ETFs, but no supported
    command produces ETF rows today.
  - Consequence: ETF executability has no native gate.

ETF_RISK_WARNING_IS_AN_ASSERTED_FALSE
  - For an SH/SZ ETF the EastMoney path would publish risk_warning=false from a board that cannot
    contain it. Consumers must NOT read ETF risk_warning=false as evidence of anything.

DAILY_FEED_UNEXERCISED
  - The demo config has no [job.daily.groups], so no day-path producer of trading_status has been
    run in this lake. The backfill path is the only one proven here.
```

---

## 9. CODEX_CONTRACT_CHANGE_REQUIRED

| # | Item |
|---|---|
| 1 | Approve, amend or reject `PROPOSED_TRADABILITY_FALLBACK_CONTRACT` for ETFs (currently `NOT APPROVED`) |
| 2 | Decide whether ETF tradability may be inferred from bars at all, and if so record the inference as a first-class quality flag |
| 3 | Decide whether the exchange-board path should be promoted to produce ETF trading status natively |
| 4 | Decide how `risk_warning=false` for ETFs is represented (the current value is an asserted false, not an unknown) |

None of these was decided here.

---

## 10. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"

# Lake state (source = baostock, 5 symbols, all-A):
& "$EXT\venv\Scripts\python.exe" -c @"
import os
for k in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy'): os.environ.pop(k,None)
import polars as pl
from cnequity.query import load
ts = load('trading_status', data_root=r'$EXT\lake-minimal')
print(ts.height, ts['symbol'].n_unique(), ts['source'].unique().to_list())
"@

# The ETF rejection, verbatim:
& "$EXT\venv\Scripts\python.exe" "$EXT\cne_cli_direct.py" backfill trading_status `
    --config "$EXT\cnequity.demo.toml" --symbols "510300.SH"
# -> ValueError: trading_status ST backfill cannot resolve '510300.SH' to exactly one all-A instrument
```
