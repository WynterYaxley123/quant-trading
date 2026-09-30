# ETF-Quant H10/H40/H120 Ridge engineering audit

Status: **HISTORICAL_ENGINEERING_VALIDATION_ONLY**. The data cutoff is fixed
at 2026-09-24; the model was **processed on 2026-09-28**, after that date.
The report must never be represented as a signal actually available on
2026-09-24, a strategy backtest, a Validation result, an order, or
performance. Shenwan membership publication timing is unknown.

Input: the hashed, repo-external factor matrix documented in
`factor_readiness_final_v1.md`. Output:
`D:\QuantForge\runtime\etf-quant-v1\codex-final-completion\reports\etf_quant_engineering_ridge_20260928T085038Z_df896aab.json`.
This includes all coefficients, intercepts, raw predictions, per-horizon
cross-sectional z-scores, fused ranking, engineering Top20/Top5, training
windows and hashes. No realized ranking returns or performance metrics were
read or generated.

| Horizon | Frozen features | Six-month window start | Label cutoff | Mature complete dates | Observations on diagnostic 107 |
|---|---:|---|---|---:|---:|
| H10 | 5 | 2026-03-10 | 2026-09-10 | 128 | 13,696 |
| H40 | 19 | 2026-01-30 | 2026-07-30 | 119 | 12,733 |
| H120 | 19 | 2025-10-02 | 2026-04-02 | 118 | 12,626 |

Every training date is retained only with the **same complete 107-industry
cross-section**, finite input features, a positive Source-C close at start
and structural label end, and a mature forward label. Target is the frozen
same-date cross-sectional excess forward return. Actual `NumPyRidge` with
`alpha=0.01`, raw X and no train-standardization was fit independently for
all three horizons. The existing z-score fusion applied 0.25 / 0.50 / 0.25;
ties are code-ascending. No model parameter tuning or performance-based
universe selection occurred.

The fixed 162-industry taxonomy had **zero** full-cross-section training
dates for H10, H40 and H120: the corresponding 162-universe model is not
ready. A deterministic *diagnostic* intersection of industries with finite
cutoff features and at least 30 individually mature observations at **each**
horizon yields 107 codes; all 128/119/118 window dates happen to be complete
on that subset. This intersection is **not an adopted formal universe policy**.

Engineering Top5 industry codes (not ETF mappings): `3706`, `3703`, `4901`,
`4803`, `3701`. The exact raw/z/fused values and Top20 are in the external
report. These codes do not imply five verified, liquid or distinct ETFs.

`fit_horizon`/`current_predictions` is intentionally **not** invoked with a
backdated `available_at`: the real current lake observation occurred after
the hypothetical signal date, so its strict production temporal gate must
remain closed. The engineering audit reuses the frozen Ridge and fusion math
under an explicitly retrospective label. A formal current-signal fit remains
blocked until temporally valid production data and a model-universe policy
are admitted.
