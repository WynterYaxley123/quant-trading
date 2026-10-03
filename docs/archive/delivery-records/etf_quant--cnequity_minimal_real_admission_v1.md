# CNEquity minimal real-data admission (v1)

**Task:** ETF-Quant V1 — CNEquity runtime transport root-cause audit + minimal real-data admission.
**Baseline commit (integration):** `594d04c76f31c25d0f147fc175f564b487830cd5`
**Prerequisite:** [`cnequity_runtime_transport_audit_v1.md`](cnequity_runtime_transport_audit_v1.md) — transport gate `CNEQUITY_TRANSPORT_PASS`.

---

## 1. Status

```
PRIMARY   : CNEQUITY_MINIMAL_REAL_ADMISSION_PASS
SECONDARY : SMOKE_SCOPE_ONLY
```

An immutable snapshot of **real CNEquity data** was produced through the approved pinned sidecar path.
It is a **bounded smoke scope**, not a production full snapshot, and is labelled as such.

> **`SMOKE_SCOPE_ONLY`** — this is not `PRODUCTION_FULL_SNAPSHOT`. The universe, date range and symbol
> coverage are deliberately minimal. No mapping, liquidity, Source-C research admission, Shadow epoch,
> NAV or trade was produced.

---

## 2. Snapshot identity

| Field | Value |
|---|---|
| `snapshot_id` | `93e11ee69cd08992893b509e1ae4f374e286bad49aa50a1d8cc99424b03b567b` |
| `manifest_sha256` | `b82da92b91e236a43f0a23b1b84539bd6c024709f08041ab457f78704847bb02` |
| Provider | `CNEQUITY_PINNED_SIDECAR` |
| `source_commit` | `1650e384a3fd1f67a70144a489acc91432f1df27` (**pin unchanged**) |
| `source_version` / `cnequity_version` | `0.11.0` / `0.11.0` |
| `source_identity` | `CNEQUITY_LOCAL_LAKE_V1` |
| `classification_version` | `SWCLASS2021` |
| `data_cutoff` | **2026-09-24** (a real trading session, and the last one with data) |
| `created_at` | 2026-09-27T13:53:07Z |
| `lake_fingerprint_sha256` | `d0e4f7c82f2616cfb8647cff43f8155b908bf7713e26523291fd310953dd485a` |
| `adjustment_exact_rows` | **1,086** |
| `adjustment_rejected_rows` | **0** |
| `available_at` / `source_published_at` | `null` (never fabricated) |
| Location | `D:\QuantForge\external\cnequity-etf-quant-v1\export-minimal\<snapshot_id>\` — **outside Git** |

### 2.1 Independent re-validation

The snapshot was re-opened **through `ExportProvider`**, which recomputes every file hash and
re-applies the full admission contract independently of the writer:

```
OPENED OK; sessions = 285  2026-08-03 -> 2027-09-27
cutoff = 2026-09-24 in sessions: True
```

Re-validation enforces: manifest hash, per-file SHA-256, exact column sets, primary-key uniqueness,
no row dated after `data_cutoff` (except the announced calendar), `fetched_at <= created_at`,
volume-unit `v2`, OHLC sanity, session-final `fetched_at`, `adj_is_exact` for every stock bar row,
`classification_system == "sw"` and `source == "sw"` for membership, CSI 300 identity/frequency/price,
and calendar membership for every dated row. **All passed.**

---

## 3. Dataset-by-dataset status

| # | Dataset | Status | Rows | Range | Notes |
|---|---|---|---|---|---|
| 1 | `trading_calendar` | **ADMITTED** | 423 | 2026-08-01 → 2027-09-27 | Announced future sessions only; never future prices |
| 2 | `stock_bars` | **ADMITTED** | 1,086 | 2026-08-03 → 2026-09-24 | 29 symbols; `source=tdx_protocol`; `data_version=v2`; `adj_is_exact` **true for 100%** |
| 3 | `industry_membership` | **ADMITTED** | 11,844 | 2026-08-31 → 2026-09-24 | **162 L2 industries**; `source=sw`, `classification_system=sw`; monthly PIT snapshots |
| 4 | `instruments` | **ADMITTED** | 7,365 | — | **5,222 stocks / 2,142 ETFs / 1 CDR**; real `list_date` for the selected ETFs |
| 5 | `etf_bars` | **ADMITTED** | 117 | 2026-08-03 → 2026-09-24 | `510300.SH`, `510500.SH`, `159915.SZ`; `amount` present on **117/117** rows |
| 6 | `trading_status` | **ADMITTED (EMPTY)** | 0 | — | Header-only. See §3.1 |
| 7 | `benchmark_csi300` | **ADMITTED** | 39 | 2026-08-03 → 2026-09-24 | `000300.SH`, `frequency=1d`, `close>0` |

All seven contract-required datasets are **present in the snapshot**. The export gate rejects any
missing key outright, so "present" is enforced, not asserted.

### 3.1 `trading_status` is admitted but empty — and why that is honest

Two separate facts, both recorded rather than papered over:

1. **The scope-limited backfill was rejected by upstream.** `cne backfill trading_status --symbols`
   failed with a scope-resolution error for the ETF symbols. The lake therefore holds `trading_status`
   only for the 5 initial demo symbols, and the export's ETF-scoped query returned **zero rows**.
2. **An empty table is the correct representation.** The export wrote a header-only CSV. It was **not**
   back-filled with fabricated `is_trading=true` rows, and the snapshot does **not** claim ETF trading
   status. `is_trading` for ETFs must remain unknown until a working scope is established.

This is a **must-fix before any execution logic** that gates tradability on `trading_status`, but it does
not invalidate the admission: the contract requires the dataset to be present and schema-valid, and it is.

### 3.2 Known scope limitations (all deliberate)

| Limitation | Consequence |
|---|---|
| `stock_bars` covers **29 symbols**, not the full 5,930-member universe | Source-C returns are thin cross-sections, not a real industry index |
| `[universe].ingest = all_a_sh_sz` | **BJ names are outside scope** — the Beijing board endpoint returned no active securities from this host |
| Membership window is 2026-08-31 → 2026-09-24 | PIT monthly snapshots; a longer history needs a bounded backfill |
| `adj_factors` begins 2026-08-14 | Pre-existing lake horizons may lack exact factors; `strict_adj=True` would then raise |
| `index_bars` is `data_version=v1` | CSI 300 volume/amount are `source_native` and must **not** be used as a benchmark turnover measure |

---

## 4. Adjustment gate (`strict_adj`) — required by the task

The task requires that a requested adjusted series must never silently degrade to raw.

| Check | Result |
|---|---|
| Export query used | `adjust="hfq", strict_adj=True` (`runner.py:92-93`) |
| Real `adj_is_exact` true | **1,086 / 1,086** |
| `adjustment_rejected_rows` | **0** |
| `adj_close <= 0` rows | 0 |
| Independent check on admitted CSV | `adj_is_exact` all true: **True**; `adj_close > 0` all: **True** |
| Would a raw fallback have passed? | **No** — `_validate` raises `ADJUSTMENT_SEMANTICS_BLOCKER` if any row has `adj_is_exact != True` |

`ADJUSTMENT_EXACTNESS_BLOCKER` was **not** triggered because the requested adjustment was genuinely
exact. The adjusted values are materially different from raw, confirming a real factor was applied:

```
000030.SZ 2026-08-03   raw close 4.37   ->   adj_close 19.230520647916734
000039.SZ 2026-08-03   raw close 8.75   ->   adj_close 454.94399413540793
```

Note that the frozen `industry_index` derive reads the **raw** `close` column despite requesting
`adjust="hfq"` (recorded in `cnequity_api_inventory_v1.md` §7 D7 / the data contract §3.1). This
admission does **not** use that path: Source C is built by the consumer from `adj_close`.

---

## 5. Source-C construction smoke

Real-data engineering smoke over the **admitted export only** (not the raw lake), using PIT membership
with a backward as-of join on `as_of_date`:

| Check | Result |
|---|---|
| Sessions with a usable cross-section | **19** |
| Industry-days emitted | **133** |
| Distinct Shenwan L2 industries | **7** |
| Members per industry-day | min **1**, max **8** |
| `ret_equal` finite | **True** |
| `ret_amount` finite | **True** |
| Index recursion (cumulative equal-weight level) | finite for all sampled industries |

Sample output (first session):

```
trade_date  industry_l2  n_members  n_priced  ret_equal   ret_amount
2026-08-31  2802         8          8          0.004033   -0.010436
2026-08-31  3405         2          2         -0.000861   -0.000233
2026-08-31  4803         1          1          0.006009    0.006009
```

**Honest interpretation.** This proves the construction path works end to end on real admitted data:
membership resolves point-in-time, returns are finite, and the index recursion is stable. It is **not** a
usable industry signal — the cross-sections are far too thin (1–8 members against a real 124-sector
universe averaging ~48 members), and 7 of 162 L2 industries are represented. No cross-sectional ranking,
no Ridge, no fusion, and no portfolio construction was attempted.

**One construction note for whoever implements Source C properly:** in this smoke `ret_amount` weights
same-day returns by **same-day** `amount`, so the two weightings diverge (e.g. `2802`: `+0.40%` equal
vs `−1.04%` amount-weighted on the same session). Upstream's `industry_index` has the same property
(`Σ(ret×amount)/Σ(amount)` over the current row). Whether turnover weighting should use the same session
or the prior session is a design decision that must be fixed explicitly, not defaulted.

---

## 6. ETF smoke

| Check | Result |
|---|---|
| ETF rows in `instruments` | **2,142** |
| Selected symbols | `510300.SH` (300ETF), `510500.SH` (500ETF), `159915.SZ` (创业板) |
| Real `list_date` present | 2012-05-28, 2013-03-15, 2011-12-09 — from the real instrument frame, not inferred from first local bar |
| `etf_bars` rows | **117** over 2026-08-03 → 2026-09-24 |
| OHLC sanity | enforced by `CNE_PRICE_SCHEMA_BLOCKER`; passed |
| `amount` present | **117 / 117** (no nulls) |
| `volume` unit | `data_version=v2` → **shares** (enforced; a non-v2 row raises `CNE_VOLUME_UNIT_BLOCKER`) |
| Trading status | **not available** (§3.1) |

**No production mapping was constructed, and no name-similarity was treated as verified.** The three ETF
identities came from the real `instruments` frame; the mapping relation itself remains
`MAPPING_SOURCE_GAP` / `MANUAL_VERIFICATION_REQUIRED` exactly as audited previously. 20-day liquidity
selection was **not** exercised as a production rule.

---

## 7. CSI 300 smoke

| Check | Result |
|---|---|
| Symbol | `000300.SH` |
| Rows | **39**, 2026-08-03 → 2026-09-24 |
| `frequency` | `1d` (enforced by `BENCHMARK_IDENTITY_BLOCKER`) |
| `close > 0` | True |
| Source | `tdx_protocol`, `data_version=v1` |
| Benchmark history generated? | **No** — only a data smoke, per the task |

No dashboard benchmark history was produced and no immutable production benchmark snapshot was created.

---

## 8. What was deliberately NOT done

| Prohibited / gated action | Status |
|---|---|
| Shadow epoch / positions / NAV / trades | **Not created** |
| Historical or simulated performance presented as Shadow performance | **None** |
| Production ETF mapping | **Not constructed** |
| 20-day liquidity production rule | **Not exercised** |
| Source-C research admission | **Not granted** — smoke only |
| Strategy logic, factors, Ridge, fusion, portfolio sizing | **Untouched** |
| Frozen F1 / Validation / Shenwan canonical data | **Untouched** |
| Frozen Docker / Compose / images | **Unchanged** |
| Third-party data provider fallback | **None** — CNEquity only, and its own upstreams only |
| `verify=False` or any TLS bypass | **Never used** |
| Git push / merge / rebase / amend | **None** |
| Snapshot committed to Git | **No** — it lives outside the repository |

---

## 9. Remaining blockers

```
TRADING_STATUS_EMPTY
  - ETF-scoped trading_status could not be backfilled (upstream scope resolution rejected it).
  - The admitted table is header-only, so ETF tradability is unknown, not "clean".
  - Also note the independent finding that the EastMoney trading-status path cannot mark an ETF halted
    and asserts risk_warning=false for SH/SZ ETFs. Do not treat ETF risk_warning=false as evidence.

UNIVERSE_TOO_THIN_FOR_SIGNAL
  - 29 stock symbols and 7 of 162 L2 industries. Fine for engineering validation; unusable for a signal.
  - A real Source-C admission needs a bounded but representative member backfill.

BJ_OUT_OF_SCOPE
  - [universe].ingest = all_a_sh_sz because the Beijing board endpoint is unreachable from this host.

ADJUSTMENT_HORIZON
  - adj_factors begin 2026-08-14; strict_adj=True will raise for earlier windows until a bounded
    factor backfill runs.

HISTORICAL_MEMBERSHIP_PIT_UNPROVEN
  - Carried verbatim from the pinned contract. Historical use is limited to MODEL_WARMUP,
    TRAINING_INPUT and ENGINEERING_VALIDATION - never ex-ante research performance.
  - available_at / source_published_at remain null and were not fabricated.

SOURCE_LICENSING_UNRESOLVED
  - Quality flag carried through. No lake or export file may be published, and the Apache-2.0 software
    licence grants no market-data rights.

CLI_PROXY_POLICY
  - The real `cne` CLI still fails on a host with malformed NO_PROXY; this admission applied the same
    explicit policy through an external, untracked helper. A permanent CLI-level policy is a larger
    decision and was not made here.

SHADOW_AND_MAPPING_GATES
  - Unchanged and uncrossed. Mapping admission and the full production dataset each need their own gate.
```

---

## 10. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
$SIDE = "D:\quant-worktrees\deepseek-cnequity-runtime-audit\services\cnequity-sidecar\runner.py"

# 1. Transport gate (must pass first)
& "$EXT\venv\Scripts\python.exe" $SIDE verify --root $EXT
& "$EXT\venv\Scripts\python.exe" $SIDE smoke  --root $EXT

# 2. Admission (reads the populated lake only; downloads nothing)
& "$EXT\venv\Scripts\python.exe" $SIDE export --root $EXT --config "$EXT\export-minimal.toml"

# 3. Independent re-validation
& "$EXT\venv\Scripts\python.exe" "$EXT\verify_snapshot.py" `
  "$EXT\export-minimal\93e11ee69cd08992893b509e1ae4f374e286bad49aa50a1d8cc99424b03b567b"
```

The lake was populated in bounded steps (`init --profile demo`, then explicit `backfill` calls for
`instruments`, `industry_members`, `trading_status`, `daily_bars`, `index_bars`, and
`derive adj_factors`), each run under the audited direct-egress proxy policy. No full-market
initialization was performed.

---

## 11. Declaration

**MAIN WORKTREE WAS NOT MODIFIED**
**ETF-QUANT INTEGRATION WORKTREE WAS NOT MODIFIED**
**FROZEN F1 WAS NOT MODIFIED**
**VALIDATION PERFORMANCE WAS NOT READ**
**SHENWAN CANONICAL DATA WAS NOT MODIFIED**
**FROZEN DOCKER WAS NOT MODIFIED**
**TLS VERIFICATION WAS NOT DISABLED**
**NO THIRD-PARTY DATA FALLBACK WAS INTRODUCED**
**NO SHADOW EPOCH WAS CREATED**
**NO HISTORICAL PERFORMANCE WAS PRESENTED AS SHADOW PERFORMANCE**
**NO SECRET VALUE WAS EXPOSED**
**NO GITHUB PUSH WAS PERFORMED**
