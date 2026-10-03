# ETF 20-session liquidity — final V1 admission audit

**Status: NOT_REACHED.** The pinned CNEquity engineering export at fixed
cutoff 2026-09-24 contains `etf_bars.row_count=0` and
`trading_status.row_count=0`, both with manifest query status
`NO_VERIFIED_ETF_SCOPE`. No formally verified mapping was admitted, so no
ETF selection universe exists. This is missing evidence, **not** zero
liquidity.

The frozen rule requires 20 distinct completed trading sessions per ETF with
real open/close/volume/**amount**; missing amount is exclusion, never
`close × volume`. The larger average actual amount wins where multiple
verified ETFs map to one industry. Suspension, duplicate symbol and effective
mapping times must be resolved independently. None of these conditions can
be certified from an empty ETF bar table.

| Measure | Result |
|---|---:|
| Verified ETF candidates entering 20-session gate | 0 |
| ETF candidates with 20/20 admissible sessions | 0 |
| Liquidity representatives selected | 0 |
| Distinct executable ETF count | 0 |
| Formal target weights | null |

No 20-session rule or 35% weight cap was relaxed. No duplicate ETF was used
to fake a five-name portfolio. An official, scoped CNEquity ETF ingest may be
considered only after candidate/mapping evidence gates; this audit does not
authorize third-party market data, a broker, or Shadow execution.
