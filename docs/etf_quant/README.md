# ETF-Quant V1 当前文档索引

截至 2026-10-01：工程、数据、模型输入均已认证，生产可用于 **Shadow simulation only**。
动态状态入口为 `/api/etf-quant/v1/current`；静态 release metadata 明确 as_of / generated_at。

| 文档 | 定位 |
|---|---|
| [首页](../../README.md) | Quick Start、架构、冻结参数、运行状态、限制 |
| [Release metadata](../../reports/etf_quant/etf_quant_v1_final_release_v1.json) | 当前静态认证与最终测试 |
| [Frozen model reconciliation](codex_frozen_model_contract_reconciliation_v1.md) | 当前模型合同权威；旧阻断 OVERRULED/OVERTURNED |
| [107 admission](common_model_universe_v1.md) | 原行业准入；早期 L3 描述以现有 explicit L2 contract 为准 |
| [API](../../services/etf-quant-api/README.md) | 独立只读聚合与兼容 endpoint |
| [Dashboard](../../dashboard/README.md) | 观察界面与环境 |
| [One-shot](../../services/etf-quant-runner/README.md) | 唯一正式入口 |
| [历史数据闭环](codex_final_data_pipeline_closure_v1.md) | 事实层 PASS 有效；模型不可用 / BLOCKED_HARD 结论 SUPERSEDED |

历史 JSON 审计保留，release `authority.historical_superseded` 标记被推翻的结论。
旧 MODEL_WARMUP_INCOMPLETE 不覆盖 current；未来真实的新失败不会被旧认证隐藏。
历史 reference Top5 不能当 Formal Signal。启动 console 与运行 one-shot 均见首页，无额外 repair TODO。
