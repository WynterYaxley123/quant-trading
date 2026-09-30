# CDR 689009 COVERAGE IMPACT v1

**Task:** ETF-Quant V1 — long-run downstream completion to shadow-ready.
**Base commit:** `e8c2f2198784d108630ef2c55797b838db951b8e`
**Contract:** [`CDR_COVERAGE_IMPACT_AUDIT_689009_V1`]

---

## 1. Verdict

```
CDR_FACTOR_SUPPORT_DEFERRED
CDR_ADJUSTMENT_CONTRACT_REQUIRED = NO
```

`689009.SH` does **not** break any industry-date. It is retained as a
**`VISIBLE_UNAVAILABLE_CONSTITUENT`** — visible in the coverage denominator, excluded from the return
numerator — and Source-C proceeds. **No threshold was relaxed and no exactness was forged.**

---

## 2. Identity

| Property | Value |
|---|---|
| symbol | **`689009.SH`** |
| name | 九号公司 |
| `asset_type` | **`cdr`** (the only CDR among 7,702 instruments) |
| Shenwan membership | **yes** — 72 SW snapshots |
| industry (L2) | **`2804`**, on **358 of 358** production sessions |
| non-exact bar rows | **358** — the entire 2025-04-10 → 2026-09-24 window |
| cause of non-exactness | `derive/adj_factors.py:441` filters the factor universe to `asset_type ∈ {stock, etf}`, deliberately omitting CDRs |

---

## 3. The eight required questions, answered

| # | Question | Answer |
|---|---|---|
| 1 | Which dates / which L2 industry? | **`2804`** on **all 358 sessions** |
| 2 | Daily eligible constituent count | recorded per industry-date in the coverage matrix |
| 3 | Valid constituent count when it is not exact | excluded from `valid`; the ratio drops by exactly one name |
| 4 | Daily coverage ratio | `valid / eligible` with the CDR **in** `eligible` |
| 5 | Any industry-date pushed below **0.80** *by the CDR alone*? | **NO — 0 industry-dates** |
| 6 | Any date pushed below **valid < 5** by the CDR alone? | **NO** |
| 7 | Does it change structural eligibility? | **NO** |
| 8 | Treatment | `VISIBLE_UNAVAILABLE_CONSTITUENT` |

### 3.1 The counterfactual was measured, not assumed

For every industry-date the audit computed the industry return **twice** — once with the CDR in the
eligible set, once with it removed — and compared the gate verdicts:

```
industry-dates where the CDR alone flips BLOCK -> PASS : 0
```

So the CDR consumes one unit of coverage ratio in `2804` and **never** decides an admission. Removing it
from the denominator would change no verdict, which is precisely why removing it would be the wrong
move: it would hide a constituent without changing any outcome.

---

## 4. Visibility semantics applied

| Rule | Application |
|---|---|
| non-exact constituent **stays in the denominator** | `689009.SH` remains in `eligible` |
| non-exact constituent **excluded from the numerator** | `constituent_return` returns `(None, REASON_NOT_EXACT)` |
| gate decides admission | frozen `valid >= 5` ∧ `valid/eligible >= 0.80`, **unmodified** |
| no raw fallback | the read path fills `factor = 1.0` and flags `adj_is_exact = false`; Source-C refuses it |
| no synthetic factor | none created |
| no interpolation | none |
| no future factor | factor join remains backward as-of |

---

## 5. Global exactness gate — semantics resolution

The `STRICT_ADJUSTMENT_GATE_BLOCKER` in the prior round conflated two different things:

| Mechanism | Behaviour | Correct? |
|---|---|---|
| `load(..., strict_adj=True)` | a **global** fail-closed switch: one missing factor raises for the whole read | correct for its purpose (a research read that must be wholly exact), but **not** the Source-C contract |
| Source-C `constituent_return` | per-row: non-exact rows are excluded and the **coverage ratio** decides | **this is the frozen contract** |

**Resolution:** Source-C correctly uses per-row exclusion plus the ratio gate. It does **not** require a
100.0000% globally-exact table, because a row that never enters any return numerator is not a coverage
failure. The 0.80 threshold and the 5-constituent minimum were **not** touched — the prior round's
"one non-exact row blocks everything" reading was an artefact of applying the global research switch to a
coverage question, and this audit corrects the *reading*, not the *gate*.

---

## 6. Measured Source-C position with the CDR visible

| Metric | Value |
|---|---|
| industry-days evaluated | **57,996** |
| **valid industry-days** | **39,657** |
| valid ratio | **0.6838** |
| industries with ≥1 valid day | **113** of 162 |
| adjustment exactness on production bars | **1,848,649 / 1,849,007 = 0.999806** |

For comparison, the state before the adjustment recovery was **111 valid industry-days (0.0019)**. The
recovery therefore moved Source-C from **0.19% → 68.38%** of industry-days.

The remaining ~31.6% invalid industry-days are attributable to the still-missing constituents
(principally **355 BJ** plus 16 legacy non-BJ codes), not to the CDR — that is Phase B/C work.

---

## 7. Why no CDR adjustment engine was built

1. **Impact is zero on every gate verdict** (§3.1), so there is no coverage justification.
2. **CNEquity has no CDR factor capability by design** — the exclusion at `derive/adj_factors.py:441` is
   deliberate, not an oversight.
3. Building one would require a CDR factor series from a source the pin does not use, i.e. a provider
   decision, not a data-layer fix.
4. The visibility contract already produces the correct outcome: the gap is recorded, bounded, and
   surfaced in the ratio.

If a future contract decides CDRs must be fully exact, the correct status is
**`CODEX_CONTRACT_CHANGE_REQUIRED`**, and it is **not required today**.

---

## 8. Tests

`tests/etf_quant/test_visible_unavailable_constituent.py` (synthetic only):

* a non-exact constituent **stays** in `eligible`;
* it is **excluded** from `valid` and from the mean;
* coverage `>= 0.80` with `valid >= 5` ⇒ `SOURCE_C_DATE_VALID`;
* coverage `< 0.80` ⇒ invalid, and no mean is published;
* `valid < 5` ⇒ invalid;
* no raw-price fallback and no forged `adj_is_exact` on any path.

---

## 9. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
& "$EXT\venv\Scripts\python.exe" "$EXT\cdr_impact.py"
# report: D:\QuantForge\runtime\etf-quant-v1\final-readiness\reports\cdr_impact.json
```
