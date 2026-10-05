# Strategy packages

| Package | Scope and current status |
| --- | --- |
| `sw_sector_rotation/` | Migrated historical Shenwan sector-rotation research; no completed tradable backtest claimed. |
| `etf_quant/` | Frozen V1 economic/model contracts; verified shared runtime infrastructure; first formal Shadow epoch not yet created. |
| `etf_quant_v2/` | Independently frozen alpha-30 RAW 12-month research candidate, separate mapping and CNY 10,000 forward account; provisional historical status. |

V2 has a deliberate one-way dependency on V1-compatible domain, factor vocabulary,
NumPy Ridge, ranking/mapping policy, lot-rounded accounting and shared publication
primitives. V1 does not import V2. Candidate, mapping, account and control namespaces
remain separate. Reusing the production accounting primitive avoids an economic
fork; a complete copy of V1 would duplicate contracts and defects.

`STRATEGY_FREEZE != RUNTIME_CODE_IMMUTABILITY`: economic contracts remain frozen,
while verified locking/storage/recovery/isolation maintenance receives explicit
source-transition and regression evidence. Shared abstractions require an actual
need; no new strategy, backtest or model search is authorized by these guidelines.
See the [strategy contract](../docs/strategy.md), [V2 protocol](../docs/etf-quant-v2-protocol.md)
and [repository rules](../AGENTS.md).
