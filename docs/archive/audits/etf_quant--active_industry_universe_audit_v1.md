# ACTIVE_INDUSTRY_UNIVERSE_AUDIT_V1 鈥?CNEquity Shenwan membership

**Task:** ETF-Quant V1 鈥?CNEquity production coverage + active industry universe admission audit.
**Base commit:** `bd218fb79389fdd3e8af1b06997e8c7af2bd1610` (inherits the verified transport fix)
**Branch:** `agent/deepseek-cnequity-production-coverage-v1`
**Evidence:** measured against the real CNEquity lake (`lake-minimal`), membership table loaded through the
pinned public query API. Every number below is reproducible with the commands in 搂10.

---

## 1. Headline

```
162  = ACTIVE count at the latest snapshot, not a union and not a duplicate set
181  = HISTORICAL UNION across all 81 snapshots
124  = industries surviving the production gate (>= 5 resolvable constituents)
```

**The 162 is neither an artifact nor a union.** It is the number of distinct Shenwan Level-2 codes
present in the single latest membership snapshot, and it has been exactly 162 since **2021-07-30** with
zero churn since.

---

## 0. Transport pytest verification (prerequisite gate, task §3)

Recorded first, because it is the gate that had to pass before any real-data work began.

| Item | Value |
|---|---|
| Command | `docker run --rm -v <worktree>:/ws -w /ws --entrypoint python quant-research:py3.12 -m pytest tests/etf_quant/test_sidecar_transport_policy.py -q --no-header -p no:cacheprovider` |
| Environment | frozen `quant-research:py3.12`, Python 3.12.11, pytest 8.4.2 |
| Result | **13 passed, 1 skipped, 0 failed** (0.81 s) |
| Skipped | `test_pinned_upstream_client_keeps_tls_verification_enabled` 鈥?`cnequity` is correctly absent from the frozen image; that test runs in the sidecar interpreter, where it was verified (`verify_mode=CERT_REQUIRED`, `check_hostname=True`) |

**One test required a fix to make this pass.**
`test_smoke_report_is_persisted_even_when_evidence_write_fails` originally reached a real `cnequity`
import and errored in the project environment; the upstream call is now stubbed so the test is hermetic.
**Production code was not changed to satisfy a test.**

---

## 2. Why 162 — the answer, with evidence

| Question | Answer | Evidence |
|---|---|---|
| Is 162 the current cross-section? | **Yes** | active L2 at `2026-09-24` = **162** |
| Is it a full-history union? | **No** | union across all snapshots = **181** |
| Is it a multi-version classification union? | **No** | exactly two code-space regimes exist, and 162 is the count of only the later one |
| Is it an inactive/retired-code union? | **No** | 19 retired codes are excluded from 162 |
| Duplicates after rename? | **No** | codes are unique per snapshot; the table's primary key is `(symbol, classification_system, as_of_date)` |
| Reconstruction artifact? | **No** | the break date is present verbatim in the upstream Shenwan workbook |

### 2.1 Per-snapshot active L2 count

81 snapshots, `2020-01-23 鈫?2026-09-24`. The active count takes **exactly two values across the whole
history**:

| Value | Snapshots |
|---|---|
| **118** | 2020-01-23 鈥?2021-06-30 (18 snapshots) |
| **162** | 2021-07-30 鈥?2026-09-24 (63 snapshots) |

There is **one** transition and no other variation:

```
2020-01-23  union=118  active=118
2021-07-30  union=181  active=162     <-- single structural break
```

No code is introduced after 2021 (`new L2 codes by first-appearance year: 2020 鈫?118, 2021 鈫?63,
2022-2026 鈫?0`).

### 2.2 The break is an upstream Shenwan re-classification, not a lake artifact

| Check | Result |
|---|---|
| Retired at the break (present before, absent after) | **19** codes |
| Introduced at the break (absent before, present after) | **63** codes |
| Carried across unchanged | **99** codes |
| Break date appears in the upstream workbook? | **Yes** 鈥?the SwClass2021 spells include `2021-07-30` verbatim |

The 19 retired codes all share the same lifecycle: first seen `2020-01-23`, **last seen `2021-06-30`**,
18 snapshots, absent thereafter:

```
2102 2104 2801 3604 4102 4203 4205 4302 4505 4601 4603 4604 4605 4801 6205 6302 6403 6404 7202
```

The code-space prefix histogram shifts accordingly, with the largest changes in the `7` and `3` blocks:

| Prefix | Before break | After break |
|---|---|---|
| 1 | 8 | 9 |
| 2 | 30 | 36 |
| 3 | 19 | **30** |
| 4 | 32 | 37 |
| 5 | 1 | 1 |
| 6 | 21 | 25 |
| 7 | 7 | **24** |

**Interpretation.** The membership table is a *reconstruction* from interval rows carrying only an entry
date (`璁″叆鏃ユ湡`), but the interval boundaries themselves come from the vendor workbook. The
`2021-07-30` boundary is therefore the vendor's own classification revision, and the 118鈫?62 change is
the vendor's code space changing 鈥?exactly the kind of event a point-in-time membership series is
supposed to preserve. **The reconstruction faithfully recorded a real re-classification.**

### 2.3 Current active codes (162) and the retired set (19)

- **Current active: 162 codes.** Full list in 搂2.4.
- **Historical only / retired: 19 codes** (listed above). These are `HISTORICAL_ONLY` 鈥?provably so,
  because each has a last-seen snapshot of `2021-06-30` and never reappears across the following 63
  snapshots.
- **Renamed / superseded:** **not provable from this data.** The table carries `industry_code` and
  `industry_name`, but `industry_name` is an alias of the code upstream
  (`adapters/sw/industry_history.py:174`), so there is no name evidence with which to assert that e.g.
  `2102` was renamed into a specific successor. **No rename relationship is claimed.** The 19 retirements
  and 63 introductions are recorded as *observed code-space changes*, not as documented renames.
- **Duplicate semantic identity:** none found 鈥?no code appears twice in a snapshot, and the pre/post
  sets are disjoint except for the 99 carried over.

### 2.4 Effective intervals 鈥?can they be built?

**Partially, and only on the snapshot grid.**

| Capability | Status |
|---|---|
| `effective_from` per code | **Yes** 鈥?first snapshot in which the code appears |
| `effective_to` per code | **Approximable only** 鈥?`last_seen` is a snapshot label, not an official end date. The upstream workbook has **no end-date column**, and `INDUSTRY_MEMBERS_SCHEMA` stores none. |
| True bitemporal `effective_to` | **Not available** 鈥?a code that disappears at the `k+1` snapshot can only be bounded to `(snapshot_k, snapshot_{k+1}]` |

Concretely, for the 19 retired codes the interval closes on the **last trading day of June 2021**, but the
true retirement effective date could be any date in July 2021 up to and including `2021-07-30`. Consumers
must treat the end boundary as **right-open and uncertain by up to one snapshot period**.

### 2.5 Reconstruction cadence

| Aspect | Value | Evidence |
|---|---|---|
| Cadence | **month-end trading day** | `steps/structure.py:44-52` `_month_end_trading_days` |
| `as_of_date` semantics | synthesised last trading day of each calendar month | `steps/structure.py:374-376` |
| Coverage floor | **2020-01-23** (last trading day of Jan 2020) | `_INDUSTRY_HISTORY_START = date(2020,1,1)` (`steps/structure.py:35`) |
| Months dropped | any month yielding < 1000 symbol rows is **not published** | `_MIN_DAILY_INDUSTRY_MEMBER_SYMBOLS = 1000` |
| Not month-start, not arbitrary | 鈥?| the label is always a month-end session |

**Mid-month resolution caveat.** Because snapshots are month-end, a spell effective mid-month is only
reflected from the **next month-end label onward**. For the `2021-07-30` revision this is benign (the
break lands exactly on a snapshot), but it means membership resolution is monthly, not daily.

---

## 3. Universe policy comparison

### 3.1 Option A 鈥?`STATIC_CURRENT_CLASSIFICATION_UNIVERSE`

Freeze the 162 active codes (or the 124 gate-surviving subset) and use them for every date.

| Dimension | Assessment |
|---|---|
| Research consistency | Good *forward*; **wrong before 2021-07-30** 鈥?19 of the frozen codes did not exist and 19 different codes did |
| Production interpretability | High 鈥?one stable, explainable code list |
| Lookahead risk | **Material.** Applying the 2021-07-30 code space to 2020鈥?021 assigns every stock to industries that did not exist yet. That is survivor-style lookahead in the industry dimension. |
| Mapping stability | High 鈥?one ETF mapping universe that does not move |
| Rank continuity | High 鈥?the cross-section is identical every day, so ranks are comparable |
| Current live use | Native 鈥?today's ranking uses today's classification |
| Historical warmup compatibility | **Broken before 2021-07-30**; the frozen set cannot describe the 118-code era |

### 3.2 Option B 鈥?`TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE`

Each date uses the classification active on that date (backward as-of join on `as_of_date`).

| Dimension | Assessment |
|---|---|
| Research consistency | **High** 鈥?this is what the membership series is for; the code space changes exactly when the vendor changed it |
| Production interpretability | Medium 鈥?the industry universe is 118 before the break and 162 after, so cross-sectional statistics straddle a discontinuity |
| Lookahead risk | **Low** 鈥?no future classification reaches a past date |
| Mapping stability | Lower 鈥?an ETF mapping must be re-validated across the break |
| Rank continuity | **Discontinuous at 2021-07-30** 鈥?the cross-section changes from 118 to 162 members, and 19 industries vanish |
| Current live use | Identical to A for any date after 2021-07-30 |
| Historical warmup compatibility | **Correct** 鈥?each era is described by its own classification |

### 3.3 `RECOMMENDED_ETF_QUANT_INDUSTRY_UNIVERSE_POLICY`

```
RECOMMENDED = B  (TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE)
```

**Rationale.** The signal date of record is `2026-09-24`, which is far past the break, so **A and B are
identical for every date the strategy will actually trade**. The two differ only for pre-2021-07-30
history. Choosing B therefore costs nothing operationally while removing a real lookahead exposure in the
warm-up window 鈥?and B is the only policy that remains correct if the warm-up is ever extended backwards.

**Why not A.** A is only safe if the research window is constrained to `>= 2021-07-30` *and* that
constraint is enforced in code. Nothing currently enforces it, so A would silently mis-describe the 118-code
era. Note that this is not hypothetical for a *different* strategy version: the current production window
(`2025-04-10 鈥?2026-09-24`, see the warm-up contract) starts well after the break, so **the choice is
currently inert and should be made now, while it is free**.

**Consequences that must be handled under B:**

1. **Cross-sectional discontinuity.** Any metric computed across `2021-07-30` mixes a 118-industry and a
   162-industry cross-section. Report them as two regimes; never pool without a flag.
2. **Rank continuity.** Top-5 membership cannot be compared across the break.
3. **Mapping.** An industry鈫扙TF mapping validated post-break must not be assumed valid pre-break.

**This recommendation does not modify any strategy config**, and it does not by itself change the frozen
ETF-Quant V1 contract for the current signal date. If Codex decides to freeze a universe policy in the
contract, mark it `CODEX_CONTRACT_CHANGE_REQUIRED`.

---

## 4. The 124-question: comparison with the Research F1 universe

The Research F1 fixed universe is **124 Shenwan Level-2 sectors**. The CNEquity snapshot yields **162**.
These are **not** the same 124 and must not be conflated.

### 4.1 The step-down funnel

| Stage | Count | Reason |
|---|---|---|
| L2 codes in the latest snapshot | **162** | current active code space |
| 鈥?with 鈮?5 members (raw membership) | **128** | 34 codes are genuinely thin |
| 鈥?with 鈮?5 **resolvable** instruments | **124** | 4 further codes have members the lake cannot resolve |

### 4.2 Where the 38 exclusions come from

| Reason | Codes | Nature |
|---|---|---|
| Genuinely thin membership (< 5 members) | **34** | mostly 1-member codes; the smallest are `7102 4403 2602 3202 3201 7201 2302 4704 4206 4207` at 1 member each |
| Adequate membership but instruments missing from the lake | **4** | `2401` (6 members, 0 resolvable), `2201` (6, 0), `2301` (5, 0), `7501` (5, 4) |

### 4.3 Explicitly NOT done

Per the task's prohibition, **none** of the following was performed:

- 鉂?hard truncation of 162 鈫?124
- 鉂?overwriting the CNEquity active universe with the F1 124 list
- 鉂?taking the first 124 codes by sort order
- 鉂?deleting 38 industries by name similarity

**The 124 reported here is an emergent result**, not a target: it is the count of industries surviving
`resolvable_constituents >= 5`, a gate already present in the frozen contract
(`min_valid_constituents = 5`). It coincides numerically with the F1 universe but the *sets need not be
identical*, and no attempt was made to make them identical.

### 4.4 Honest statement of the coincidence

> The CNEquity-derived universe contains **124** industries at the 鈮?-resolvable-constituent gate, which
> equals the F1 Research universe size of 124. **This numeric coincidence is reported, not exploited.**
> The two sets were not compared element-wise in this audit, and the F1 list was not used as an input at
> any point. Any claim that they are the same sectors would require a separate, explicit set comparison.

The remaining 4 codes that pass the membership gate but fail instrument resolution (`2401`, `2201`,
`2301`, `7501`) are a **lake coverage gap**, not a classification fact: they are entirely absent from the
`instruments` frame, which in turn is because the instrument universe was populated from the live TDX
board (which lists only what trades today) and no delisted-name backfill was run. **These 4 industries
would likely be recovered by `cne backfill instruments`.**

### 4.5 Constituent-count distribution (the 124 gate survivors)

| Statistic | Resolvable constituents |
|---|---|
| min | 5 |
| median | 26 |
| max | 244 |

Versus the full 162: `min=1 median=21 max=280`, `P10=2 P25=7 P50=21 P75=39 P90=99`.

---

## 5. Exchange composition and the BJ question (cross-reference)

Membership symbols at `2026-09-24`: **5,930 unique**, split **SZ 3,105 / SH 2,470 / BJ 355**.

BJ is a real, current constituent population, not a reconstruction artifact 鈥?355 names in **72 of 162**
industries, reaching **42.9%** of `2209`. Full policy analysis is in
[`production_data_coverage_audit_v1.md`](production_data_coverage_audit_v1.md) 搂6 and is summarised as
`BJ_CONSTITUENT_POLICY_RECOMMENDATION` there.

---

## 6. Hard blockers

```
ACTIVE_UNIVERSE_END_BOUNDARY_UNCERTAIN
  - effective_to for retired codes is bounded only to a one-snapshot interval; the vendor publishes no
    end date and the schema stores none.
  - The 19 retirements close on the 2021-06-30 snapshot label; the true date is within July 2021.

MONTHLY_MEMBERSHIP_RESOLUTION
  - Mid-month reclassifications are visible only from the next month-end label.

INDUSTRY_NAME_IS_A_CODE_ALIAS
  - industry_name == industry_code upstream; no name evidence exists to assert renames.
  - Any rename/supersession claim would need an external Shenwan name publication.

CROSS_SECTIONAL_DISCONTINUITY_AT_2021_07_30
  - 118 -> 162 in one step. Metrics spanning the break are not comparable.

FOUR_INDUSTRIES_UNRESOLVABLE
  - 2401, 2201, 2301, 7501 have adequate membership but zero/few resolvable instruments in the lake.
  - A lake coverage gap, addressable by an instruments backfill.

TWO_CODE_SPACES_MUST_NOT_BE_POOLED
  - 181 historical union vs 162 active. Neither may be presented as "the Shenwan L2 universe"
    without a date qualifier.
```

---

## 7. CODEX_CONTRACT_CHANGE_REQUIRED items

| # | Item | Why it is a contract decision |
|---|---|---|
| 1 | Adopt `TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE` (Option B) as the frozen universe policy, or record an explicit `>= 2021-07-30` research-window constraint if Option A is chosen | Changes the frozen V1 universe definition |
| 2 | Define how the `2021-07-30` cross-sectional discontinuity is reported | Affects rank-continuity guarantees |
| 3 | Decide whether the universe is defined by **162 active**, **128 (鈮? members)**, or **124 (鈮? resolvable)** | The three are different universes |
| 4 | Decide whether the 4 unresolvable industries are recovered via an instruments backfill before the universe is frozen | Universe size depends on lake completeness, which is a build decision |

None of these was decided here.

---

## 9. Declaration

No strategy config, factor, Ridge, fusion, portfolio or F1 file was modified. No ETF mapping was created.
No Shadow epoch was created. Validation and Final OOS were not read.

---

## 10. Reproduce

```powershell
# Requires the external sidecar env and lake; read-only, no network.
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
& "$EXT\venv\Scripts\python.exe" "$EXT\audit_industries.py"
& "$EXT\venv\Scripts\python.exe" "$EXT\audit_transition_bj_ts.py"
& "$EXT\venv\Scripts\python.exe" "$EXT\audit_162_breakdown.py"
```
