# ETF-Quant V1 contract

The frozen candidate uses a 40% industry-exposure proxy policy with cash fallback
(historical identifier `B40_WITH_CASH`). Configuration and regression tests are
the executable authority; this guide summarizes them without proposing new rules.

| Concern | Frozen rule |
| --- | --- |
| Universe | Admitted Shenwan 2021 Level-2 industries; explicit taxonomy |
| Input | Internal equal-weight constituent returns (historical Source-C identity) |
| Factors | H10: d10/p5/align/vc/dd20; H40/H120: frozen 19-factor registry |
| Model | Independent Ridge, alpha 0.01, raw X |
| Training | Six months before each mature label cutoff; at least 30 valid dates |
| Horizons/fusion | 10/40/120 sessions; population z-score; 0.25/0.50/0.25 |
| Selection | Original Top5; deterministic ties; no lower-ranked replacement |
| Mapping | Direct tracking > industry proxy > cash; complete evidence and liquidity |
| B40 proxy | At least 40% target exposure; target largest; available by decision |
| Sizing | Frozen capped softmax; 35% single-ETF target cap |
| Cash | Unallocated execution capacity; original skipped weight retained |
| Rebalance | Executable member set changes, including executability |
| Execution | Finalized T close to future T+1 finalized raw open; delayed accounting |
| Costs | 3 bps commission, 5 bps slippage; no stamp duty/minimum commission |
| Initial capital | CNY 10,000; no positions |
| Benchmark | CSI 300 display only, excluded from model |

Purity never rescales alpha. Cash is not an ETF and is never silently redistributed;
its policy-level return remains explicitly unmodeled.

A40_FULLY_INVESTED and B40_RENORMALIZED are historical comparative policies. A40
relaxes dominance, while complete weights, valid instrument identity and admitted
positive finite liquidity remain prerequisites. No qualifying candidate fails closed.
Positive liquidity amount never multiplies alpha weights. Mapping selection owns
strict precedence, collisions and deterministic fallback; the evaluator takes selected inputs.

Historical Source-C membership is not silently upgraded to strict historical PIT.
Later mapping evidence cannot be backdated. A missed T+1 retires the original intent
and its epoch as ABANDONED_MISSED_T1, without a retroactive fill. A new current-date
epoch may continue the preserved account. See [data and PIT](data-and-pit.md).

`STRATEGY_FREEZE != RUNTIME_CODE_IMMUTABILITY`: frozen factors, fitted-method
specifications, ranking/fusion, mapping/cash, sizing, costs and T/T+1 semantics are
economic contracts. Storage, lock recovery, version isolation and observation may
receive verified maintenance with an explicit source transition and regression
evidence. The infrastructure changes in `e69c6d7` are governed by this distinction.

V2 research does not change these rules. Its independent specification and current
Final-OOS verdict and independent prospective mapping are in the [V2 protocol](etf-quant-v2-protocol.md). The
[glossary](glossary.md) defines public terms and historical compatibility identifiers.
