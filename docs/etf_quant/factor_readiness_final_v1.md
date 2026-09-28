# ETF-Quant 19-factor readiness, fixed cutoff 2026-09-24

Status: **RETROSPECTIVE ENGINEERING AUDIT ONLY; NOT FORMAL SOURCE-C/PIT ADMISSION**.
The repo-external, SHA-256-verified constituent matrix was read in a
memory-bounded pass in the existing `quant-research:py3.12` Docker image.
The audit calls the frozen `strategies.etf_quant.data.source_c.industry_date`
five-name/80% date gate and feeds its level series into the existing
`compute_close_factors` implementation; it does not implement alternative
factor formulas or backfill gaps. Frozen runtime semantics are mirrored:
unstarted series may initialize at 1000 on a sufficient current-bar date,
but a started series with one failed adjacent-date gate has a broken
recursive prefix and never silently rebases. The matrix's first day lacks a
prior return, so a base initialization and a strict return-day gate are
reported separately.

Evidence outside Git:

- `D:\QuantForge\runtime\etf-quant-v1\codex-final-completion\reports\etf_quant_readiness_20260928T084825Z_a9adc37f.json`
- `D:\QuantForge\runtime\etf-quant-v1\codex-final-completion\reports\etf_quant_factor_readiness_20260928T084825Z_a9adc37f.csv`

The factor matrix contains every one of 57,996 `(trade_date, industry_code)`
keys, the Source-C usability/close, contiguous-120-session lookback flag,
all 19 actual factor values and finite flags, all-required verdict, and an
invalid reason. Values remain null where missing; no forward fill, zero fill,
future price, or synthetic OHLCVA was used. The CSV hash is sealed in the
readiness JSON.

| Measure | Result |
|---|---:|
| Fixed sessions / industries | 358 / 162 |
| Strict member-return date gate valid | 40,763 / 57,996 |
| Recursive Source-C level usable | 38,669 / 57,996 |
| All 19 factors finite | 25,710 / 57,996 |
| Source-C level usable at cutoff | 107 / 162 industries |
| All 19 factors finite at cutoff | 107 / 162 industries |
| Unresolved identities with an actual market bar | 0 member-sessions |

`align` alone is finite on all 57,996 rows because the frozen formula casts
early NaN comparisons to false; this is **not** 60/120-day factor readiness.
The complete 19-factor predicate correctly waits for all required rolling
outputs, including the 120-session factors. Representative finite counts:
`d5` 38,209, `d60` 32,190, `d120` 25,710, `v20` 36,426,
`rsi` 37,086. The full per-factor counts are in the JSON.

The 107-industry cutoff intersection is a *data-availability diagnostic*.
It does not alter the frozen 162-industry taxonomy, lower the Source-C gate,
or claim historical publication/available-at evidence. The 55 missing
industries and 46 never-valid industries remain visible. A formal production
universe choice requires an approved, evidence-based admission rule; the
existing runtime currently requires a full finite `series.universe` on each
training date.
