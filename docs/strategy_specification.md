# Strategy Specification 模板

> 本文档为统一策略规格模板。Hikyuu 实现与 RQAlpha 验证版**必须遵循同一份规格**。
> 复制本文件内容生成具体策略的规格，存放于 `docs/specs/<strategy-name>.md`。

---

## Strategy Name

（策略名称）

## Version

（版本号，如 v0.1.0）

## Source

（来源：聚宽策略链接 / 论文 / 自研。若来自聚宽，原始代码存于
`src/strategies/imported/joinquant/`）

## Universe

（标的池：如沪深300成分股 / 全部 ETF / 指定 ETF 列表）

## Market

（市场：A股 / ETF / 其他）

## Data Frequency

（数据频率：日线 / 分钟线 / tick）

## Required Data

（所需数据字段：开高低收、成交量、复权方式、财务数据等）

## Signal Logic

（信号逻辑：因子计算、指标定义、窗口长度、阈值）

## Entry Rules

（入场规则：触发条件、执行时点、订单类型）

## Exit Rules

（出场规则：触发条件、执行时点）

## Rebalance

（调仓规则：频率、权重计算方式、调仓触发条件）

## Position Sizing

（仓位管理：单标的上限、总仓位、分批建仓规则）

## Risk Control

（风控规则：止盈 TGT / 移动止盈 TR / 分批建仓 RGrid /
硬止损 ZMB / 止损 SL。需明确各指标参数）

## Transaction Cost

（交易成本：手续费率、印花税、最低佣金）

## Slippage

（滑点假设：固定值 / 比例 / 无）

## Benchmark

（基准：如沪深300 / 中证500 / 等权组合）

## Backtest Range

（回测区间：起止日期）

## Out-of-sample Range

（样本外区间：起止日期）

## Known Limitations

（已知局限：框架差异、数据限制、未考虑的极端情况、
Hikyuu 与 RQAlpha 实现差异说明）

---

## 填写要求

1. **每项必须填写**，不适用时写"不适用"并说明原因
2. 参数必须**具体化**，禁止写"适当""合理"等模糊表述
3. 若来自聚宽策略，**必须**在 Source 中注明，并完成未来函数检查
4. Hikyuu 与 RQAlpha 双方实现的任何差异，**必须**记入 Known Limitations
5. 规格一旦确定，框架实现不得偏离；如需偏离须先更新本规格

---

## 未来函数检查项（迁移策略必查）

| 检查项 | 说明 |
|--------|------|
| `shift(-n)` | 是否使用了未来数据 |
| 当日收盘价决策当日交易 | 是否用收盘价做当日信号 |
| 财务数据发布时点 | 是否使用了未公布的财务数据 |
| 指数成分股变更 | 是否使用了事后成分股名单 |
| 停牌股处理 | 停牌期间是否被错误交易 |
| 涨跌停处理 | 涨跌停时是否假设能成交 |
| 复权方式 | 前复权 / 后复权是否一致 |
