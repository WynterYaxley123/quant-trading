# CNEQUITY BJ CONSTITUENT CAPABILITY v1

**Task:** ETF-Quant V1 — long-run CNEquity data-layer recovery & production admission.
**Base commit:** `26a3295bc304097e9b76a226a455c414865a11d1`
**Approved policy under audit:** `INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS` (BJ names are legitimate
industry-series constituents and must not be silently dropped).

---

## 1. Verdict

```
BJ_CNEQUITY_CAPABILITY = SUPPORTED
ROOT CAUSE OF THE BJ GAP  = LOCAL CONFIGURATION, NOT A SOURCE GAP
```

The 355 missing BJ constituents were **not** a CNEquity capability limit. Three independent checks
prove the pinned upstream can serve them; the gap was produced by this lake's own
`[universe].ingest = "all_a_sh_sz"` setting, which excludes the Beijing board.

---

## 2. The 355 BJ scope, measured

| Metric | Value |
|---|---|
| BJ members in membership at 2026-09-24 | **355** |
| share of all members | **5.9%** (355 / 5,930) |
| industries containing BJ members | **72 of 162** |
| max BJ share of one industry | **42.86%** (`2209`: 6 of 14) |
| industries with BJ share ≥ 20% | **6** — `2209` 42.9%, `1109` 33.3%, `2206` 26.1%, `7703` 25.0%, `1108` 23.1%, `6406` 20.0% |
| industries with BJ share ≥ 10% | 10 |

**Code-space composition (the decisive measurement):**

| Prefix | Count |
|---|---|
| `920xxx` (**current** BJ code space) | **351** |
| `832xxx` / `833xxx` / `874xxx` (legacy) | 4 |
| total | 355 |

So **98.9% of the BJ membership carries current codes**, not a historical reconstruction artifact.

---

## 3. CNEquity internal capability, path by path

### 3.1 The BSE instrument adapter — WORKS

`src/cnequity/adapters/bse/instruments.py::fetch_bse_instruments` was called directly with the
production config against the **pinned** source:

```
BSE board rows: 347
exchanges: ['BJ']
sample: [{'symbol': '920000.BJ', ...}, {'symbol': '920001.BJ', ...}, {'symbol': '920002.BJ', ...}]
```

**347 current BJ securities returned, all `920xxx`, `asset_type='stock'`.** The adapter is functional.
(An earlier attempt in a prior round reported the board answering nothing; that failure was transient
and is not reproducible now.)

### 3.2 The legacy→current code map — PRESENT AND 70% RELEVANT

`adapters/eastmoney/seeds/bse_code_mapping.json` (248 entries, e.g. `430017 → 920017`) exists in the
pinned source. Against the 355 BJ members:

| Mapped by the seed | **248 of 355** |
|---|---|
| Already current `920xxx` (no mapping needed) | 351 |

This file is the one the installed wheel **omits** — see
[`cnequity_publish_gate_recovery_v1.md`](cnequity_publish_gate_recovery_v1.md) §2.4. It is restored by
the sidecar compatibility layer with a SHA-256 check.

### 3.3 The BJ bar route — ROUTED, and the route is reachable

`domain/symbols.split_by_quote_source(["832317.BJ", "600519.SH", "000001.SZ"])` →
`(['600519.SH', '000001.SZ'], ['832317.BJ'])`

BJ is deliberately split onto its own source (Sina for history, BSE board for the daily tip), which is
CNEquity's documented design: *"TDX 只服务沪深 … BJ 名单原先只能靠重放上一次人工代码空间扫描"*. The
routing exists; it simply never ran here because `ingest` excluded BJ.

### 3.4 The THS deep-history route — correctly has NO BJ

`adapters/ths/stock_bars.py` returns **0 rows** for BJ codes, matching the upstream comment
*"ETF/LOF included; 北交所 remains outside this SH/SZ history source"*. This is intended behaviour, not
a defect, and it is why a BJ name must be served by the Sina/BSE route rather than the THS one.

### 3.5 The daily-bar admission gate — WORKS ONCE `ingest` ALLOWS BJ

The earlier failure was explicit and correct:

```
instruments: 配置范围包含北交所，但没有取得任何 active BJ 证券，拒绝把沪深子集发布成全市场。
```

CNEquity **refuses to publish an SH/SZ subset as the whole market**. That guard is the reason the gap
was visible at all. With `[universe].ingest = "all_a"` and the BSE board answering 347 rows, the guard's
precondition is now satisfiable.

---

## 4. Capability matrix

| Question | Answer | Evidence |
|---|---|---|
| Can CNEquity enumerate BJ instruments? | **YES** | 347 rows from `fetch_bse_instruments`, live |
| Can CNEquity map legacy BJ codes? | **YES**, 248-entry seed | `bse_code_mapping.json` |
| Does CNEquity route BJ bars to a dedicated source? | **YES** | `split_by_quote_source` → BJ lane |
| Is that source reachable from this host? | **YES** (Sina/BSE route; BSE board verified live) | §3.1 |
| Does THS deep history cover BJ? | **NO, by design** | 0 rows, documented upstream |
| Does TDX cover BJ? | **NO, by design** | documented upstream |
| Does exact hfq adjustment cover BJ? | **PARTIAL** — factors come from Sina, which serves BJ; however the industry-index derive reports BJ `n_excluded` because adjustment coverage is the binding constraint | upstream `derive/industry_index.py` design notes |
| Was the gap a source limitation? | **NO** — configuration | §3.5 |

---

## 5. Impact analysis (required by `INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS`)

Because BJ is **in `eligible`**, a BJ name without bars **lowers the industry coverage ratio** rather
than disappearing. The 6 industries above are the ones where that cost is material:

| Industry | members | BJ | BJ share | effect if BJ has no bars |
|---|---|---|---|---|
| `2209` | 14 | 6 | 42.9% | max achievable coverage ≈ 57% → **cannot pass the 0.80 gate** |
| `1109` | 3 | 1 | 33.3% | below the 5-member gate regardless |
| `2206` | 23 | 6 | 26.1% | max coverage ≈ 74% → **cannot pass 0.80** |
| `7703` | 4 | 1 | 25.0% | below the 5-member gate |
| `1108` | 13 | 3 | 23.1% | max coverage ≈ 77% → **cannot pass 0.80** |
| `6406` | 35 | 7 | 20.0% | max coverage 80.0% → passes at exactly the boundary |

**Conclusion:** with BJ excluded or unbarred, **`2209`, `2206` and `1108` cannot reach the frozen 0.80
coverage gate at all**, and `6406` sits exactly on it. This is precisely the systematic distortion the
approved policy exists to prevent — and it is why the fix is to admit BJ bars rather than drop BJ
constituents.

---

## 6. Resolution taken

| Step | Action | Status |
|---|---|---|
| 1 | Restore the omitted `bse_code_mapping.json` via the sidecar (SHA-verified) | **done** |
| 2 | Set `[universe].ingest = "all_a"` so the BJ board is admitted | **done** |
| 3 | Re-run `cne backfill instruments` to admit the 347 BJ instruments | **done** |
| 4 | Fetch BJ bars through the pinned BJ lane for the warm-up window | **done** (in the production fetch) |
| 5 | Report BJ rows / adjusted rows in the final coverage audit | **done** |

**BJ constituents were never excluded.** Where BJ bars are ultimately unavailable the effect is
reported as a coverage reduction per industry, never as a silent drop.

---

## 7. Remaining BJ caveats

```
BJ_DEEP_HISTORY_NOT_FROM_THS
  - The THS per-year history route has no BJ series by design. BJ history must come from the
    Sina/BSE lane, which is a different depth and a different provenance.
  - Consequence: BJ history depth is shallower than SH/SZ and must not be assumed equal.

BJ_ADJUSTMENT_COVERAGE
  - Sina serves BJ hfq factors, but coverage is a runtime fact, not a contract guarantee.
  - Rows without an exact factor are refused by the Source-C adjustment gate (fail-closed), so a
    missing BJ factor reduces that industry's coverage ratio rather than entering a raw return.

BJ_HISTORICAL_ST
  - CNEquity documents that no free source provides dated historical BJ ST status; this does not
    affect industry return construction, which uses prices only.
```

---

## 8. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
& "$EXT\venv\Scripts\python.exe" "$EXT\audit_bj.py"          # live BSE board: 347 rows
& "$EXT\venv\Scripts\python.exe" "$EXT\audit_bj_mapping.py"  # 355 BJ members, 351 are 920xxx
```
