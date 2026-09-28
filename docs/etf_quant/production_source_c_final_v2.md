# PRODUCTION SOURCE-C FINAL v2 (v1 kept as historical record)

**Series identity:** `INTERNAL_EQUAL_WEIGHT_SHENWAN_SERIES_V1` — internal
equal-weight Shenwan L2 series, **NOT an official Shenwan index**.
**Rules (frozen, unmodified):** `TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE`;
date gate `valid >= 5` and `valid/eligible >= 0.80`; missing member =
denominator YES, numerator NO; exact-adjusted calendar-adjacent returns only;
recursive base-1000 level, broken prefix never restarts.

## 1. Recompute on final data (post `601318.SH` repair)

Evidence: `etf_quant_readiness_20260928T091309Z_0d2dfbc6.json` over the sealed
coverage matrix `..._20260928T091144Z_288178d0.csv`.

| Measure | Value |
|---|---:|
| Industry-days (358 × 162) | 57,996 |
| Strict member-return date-gate valid | **40,800 (70.35%)** |
| Recursive Source-C level usable | **38,684 industry-sessions** |
| Source-C level usable at cutoff 2026-09-24 | **107 / 162 industries** |
| All-19-factors finite at cutoff | 107 / 162 |
| Before (DeepSeek handoff, legacy semantics) | 40,799 / 57,996 (70.35%) |

The +1 industry-day (40,799 → 40,800) is the measured total effect of the
`601318.SH` official repair. The legacy-sparse-prior semantics reproduce 40,838;
the strict calendar-adjacent contract (previous session must be the immediately
preceding calendar session) reports 40,800 — no silent last-available-bar
substitution.

## 2. Why the gap is not pursued to a fake 100%

See `production_data_gap_final_v2.md` §2: 83.0% of invalid industry-days carry
stored post-delist member gaps (structural, expected); the dominant reason is
`MEMBERSHIP_ONLY_NO_MARKET_DATA` over delisted/suspended members. Gates were
never relaxed.

## 3. Downstream consumers

- Factor matrix (19 factors, all 57,996 keys, values null where not computable):
  `etf_quant_factor_readiness_20260928T091309Z_0d2dfbc6.csv` (sealed hash).
- Model universe: `common_model_universe_v1.md` (107 codes).
- Engineering models: `etf_quant_engineering_ridge_20260928T123624Z_828fad6e.json`
  (final re-fit; classification `HISTORICAL_ENGINEERING_VALIDATION_ONLY`).

## 4. Declarations

No non-exact return entered a Source-C numerator; no raw-price fallback; no
forged `adj_is_exact`; CDR `689009.SH` remained denominator-visible; BJ tip
identities were not back-stamped; historical membership publication timing
remains `HISTORICAL_MEMBERSHIP_PIT_UNPROVEN`; no coverage threshold relaxed.
