# src/ — 可复用基础设施

`src/` 提供数据/provider、通知、回测框架适配和应用编排。
具体策略与产品代码位于顶层自包含的 `strategies/` 包中；共享 OHLC
primitive 位于 `quant_primitives/`，由基础设施和策略共同使用。

ETF-Quant V1 已完成工程准备，模型规格已冻结，模拟/Shadow 运行路径已就绪；
首个正式 Shadow epoch 尚未创建，没有 Shadow 绩效结果，也没有真实交易路径。

| 目录 | 当前职责 |
|---|---|
| `data/` | 数据 schema、日历、provider 与兼容入口 |
| `notifications/` | 通知基础设施 |
| `backtesting/`、`application/` | 框架适配、元数据发现与调用编排 |
| `strategies/` | 第三方导入相关基础设施，产品策略仍在顶层策略包 |

参见[项目说明](../README.md)、[架构](../docs/architecture.md)、
[开发流程](../docs/development.md)和[仓库约束](../AGENTS.md)。
