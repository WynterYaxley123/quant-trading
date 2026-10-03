# H10/H40/H120 Ridge — final post-repair engineering audit v2

The actual final fit artifact is repo-external
`D:\QuantForge\runtime\etf-quant-v1\codex-final-completion\reports\etf_quant_engineering_ridge_20260928T123624Z_828fad6e.json`,
SHA-256 `75d21fd4f02e63df26f2be85f1b661f7ebed0965710f7f4d5e1cfe8c01610b68`.
It classifies itself `HISTORICAL_ENGINEERING_VALIDATION_ONLY`, names the
107-code common universe, and includes every coefficient, intercept, raw
prediction, z-score and fused ranking. It is not a backtest or a 2026-09-24
available signal: processing occurred on 2026-09-28 and historical
membership publication timing remains unknown.

| Horizon | Features | Mature complete dates | Actual training observations | Prediction industries |
|---|---:|---:|---:|---:|
| H10 | 5 | 128 | 13,696 | 107 |
| H40 | 19 | 119 | 12,733 | 107 |
| H120 | 19 | 118 | 12,626 | 107 |

The frozen alpha is 0.01; six-calendar-month training windows, minimum 30
valid dates, same-date cross-sectional excess targets, and raw unstandardized
features are unchanged. The three model fits are independent. Fusion is
0.25/0.50/0.25 after each horizon's cross-sectional z-score. The final
engineering Top5 L2 codes are `3706, 3703, 4901, 4803, 3701` in that
order. These are not ETFs, orders, holdings or performance. The full 162-code
cross-section has zero complete model-training dates; forward production
model readiness is therefore not claimed.
