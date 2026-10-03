# ETF-QUANT V1：B40_WITH_CASH Runtime 接线

日期：2026-09-29。用户已批准 B40 政策，但**本轮没有启动正式 Shadow**。此文只描述已提交的运行契约及仍缺少的生产证据。

## 双路径与冻结边界

`runtime/cli.py` 默认 `--execution-policy STRICT_TOP5`；`runtime/shadow.py::daily_cycle` 默认也是 `STRICT_TOP5`。默认路径仍调用原 `mapping.registry.select_mappings`、原 `rebalance_decision`、原 `size_targets(required_assets=5)`；严格五成员断言、策略哈希及既有 T+1 行为未改变。显式 `--execution-policy B40_WITH_CASH` 还必须同时提供 `--pit-evidence` 和 `--pit-source-root`，否则在触碰正式 runtime 状态前拒绝。

B40 路径复用原模型：完成的 T 日输入 → 冻结 F1/Source-C/H10-H40-H120/Fusion → 原 Top5 排名 → `mapping/pit.py::select_pit_mappings` → 五个原始执行槽（Strict、Proxy 或 Cash）→ `rebalance_decision_v2` → 持久化 T 日 ETF 目标意图 → T+1 真实日线开盘价 → 证据可用后延迟记账。先排名再映射；purity、流动性不改 final_score，也不把 Top4 重新满仓。

## PIT 证据适配

外部 `POINT_IN_TIME_EXECUTION_EVIDENCE_V1` book 必须提供完整官方 JSON 权重原始字节、单独的申万分类原始字节及 SHA256；抽取出的成分/分类列表必须与哈希核对后的原始 JSON 精确相同。来源 URL 只接受规定的官方 HTTPS 主机；不调用网络、不关闭 TLS、不读取任意未核对本地文件。一个版本分别记录成分生效日、权重生效日、官方发布时间、观察时间、可用时间及有效截止日，满足 `publication <= observed <= available <= T decision`，且有效期覆盖 T+1。分类记录有逐证券生效日和可用时间；缺少归属的权重不分摊给已知 L2，权重集不完整则不准入。

严格映射仍通过原哈希验证 registry 与 `active()` 时点检查。两类工具均通过现有 `assess_liquidity`：T 日止的连续 20 个交易日，每日真实 amount/价格/成交量，上市日必须覆盖窗口，不能借用未来 bar、drop-null 或用 volume 代替 amount。一个行业若有当时有效的 Strict 映射，不能降级使用 Proxy；Proxy 必须目标 L2 ≥40%、为最大 L2、完整权重且 20 日流动性通过，否则该槽 Cash。H30463 没有专用例外代码，只是没有合格完整证据而普通 fail-closed。

已消费的外部证据和严格 registry 记录按实际决策时间锁定哈希。决策之后同日才可用的新记录可在**下一个**交易日准入，不会倒填当日意图；已经消费的记录删改会阻断。持久化的 T 日 Proxy 意图在 T+1 仍核对相同证据哈希、时点和有效期；当前 T+1 的新排名不会反过来改写该意图。

## Cash / 再平衡 / T+1

唯一冻结 `size_targets` 先按**全部五个原始 L2 分数**生成带 35% 上限的目标权重，再把每个可执行槽的原权重映射到 ETF；不执行槽的权重记作 `cash_retained_weight`。目标风险资产 + 目标 Cash 必须为 1。Cash 是状态字段，不是证券代码、TargetPosition 或买单；全 Cash 也不伪造初始 epoch。每次信号在只读映射视图中保留五槽、证据、原因、流动性及目标 Cash；账户实际 Cash 仍以模拟账本为准。

新 `rebalance_decision_v2` 仅比较最终 ETF 成员集合，保留“分数/权重变化但成员未变不交易”的冻结规则。ETF→Cash 产生下一交易日卖出目标；Cash→ETF 买入；Proxy→Strict、Strict 到期→Proxy、Proxy A→B 均按成员变更处理。slot 迁移原因写入隔离测试账本的 `rebalance_events`。没有合格 T+1 bar、错过 T+1、或先看到开盘价后想补造 T 意图，均阻断且不推进 latest 指针。

经济时间是 T+1 09:30 的真实 raw open；原 `rebalance_at_open` 和手续费、滑点、整数手约束不改。B40 fill 另明确 `economic_execution_at < evidence_available_at <= processed_at`、`DELAYED_T1_OPEN_ACCOUNTING` 与 `NOT_REALTIME_EXECUTION_EVIDENCE`，不能解释为实时执行证明。只读 API 对 B40 五槽/Cash 守恒与成交时间关系增加核验；Dashboard 只显示执行类型和**目标** Cash，不增加控制入口。

## 生产证据缺口

当前仓外研究材料**不是**上述生产 book：官方 CSI reverse JSON 按证券反查，字段为 `data/total/securityCode`，并非可直接核对的完整单基准 PIT 权重包；`stock_to_l2_v1.json` 有整体 `reference_date`、`snapshot_date` 和证券→L2 值，却没有逐证券 `available_at`/`effective_date`。不能因为它们针对 2026-09-24 研究参考日，就断言 2026-09-24 当时已知，也不能自行填一个“合法”发布时间。需独立审计并提供满足新 loader 的外部证据包，方可重新计算技术就绪。2026-09-24 始终只是 `HISTORICAL_ENGINEERING_REFERENCE_DATE`。

`SOURCE_LICENSING_UNRESOLVED` 保留。未改 CNEquity pin、模型、Strict V1 或已批准 40%/主导性/Cash 契约；未接入其他行情源。
