# ETF-QUANT V1：B40_WITH_CASH 最终政策审查

日期：2026-09-29。范围仅为执行层政策与 2026-09-24 工程参考组合；不是新研究、正式交易或 Shadow 运行。

## 决议及边界

用户已批准 `B40_WITH_CASH`：目标申万 L2 占比至少 40%，且必须是 ETF 基准中占比最大的 L2；完整官方权重、可核验的行业归属、20 个交易日流动性及工具准入也必须通过。严格映射优先于 Proxy；不合格行业保留原模型目标权重为 Cash，不向其余行业再分配。Cash 是 `UNALLOCATED_EXECUTION_CAPACITY`，不是第五只 ETF、现金替代品或订单标的；本轮不定义现金收益率。

原严格路径的 `rebalance_decision`、五成员断言及 `size_targets(required_assets=5)` 默认值保持不变。新增的 `select_mappings_partial` 与 `rebalance_decision_v2` 仅在显式传入 `B40_WITH_CASH` 时可用。前者在已核验证据候选池中按 STRICT > PROXY > Cash 选择，保留五个原始信号及分数；后者比较 0–5 个真实 ETF 成员，ETF→Cash 和 Cash→ETF 均触发变更。二者是纯契约，**尚未接入正式 `runtime/shadow.py::daily_cycle`**，也不获取或推断未来 PIT 证据。现有 Shadow 主循环仍调用严格选择器及严格五成员再平衡，因此政策批准不等于运行就绪。

`portfolio/policy.py` 的 B40 谓词现在本身拒绝不完整权重、未知/不通过的流动性、非有限金额或占比、错误 mapping 类型和不存在的基准；不能只靠展示用拒绝理由挡住错误资产。全部五个信号均不可执行时返回 100% Cash、0 风险资产，不伪造 Cash 订单。权重上限仍委托冻结 `size_targets`，没有第二套活跃的 capped 权重分配算法。Proxy 的 purity、dominance、liquidity 不进入 `final_score`、Ridge、Fusion 或行业排序。研究级 `grade=UNSUITABLE` 使用另一显示阈值，并非获批准入门槛；B40 是否合格只以冻结的 40% + 主导性及证据/流动性 gate 判定。

## H30463 / 517990.SH 最后核验

核验了[中证指数 H30463 官方事实表](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/H30463factsheet.pdf)、[基金管理人 517990 官方产品页及 PCF 入口](https://static.cmfchina.com/web/fundDetail/517990/index.html)、[上交所 ETF 申赎清单披露入口](https://www.sse.com.cn/disclosure/fund/etflist/)及[上交所发布的基金招募说明书](https://www.sse.com.cn/disclosure/fund/announcement/c/new/2023-05-08/517990_20230508_NIPJ.pdf)。这些路径能证明指数/基金身份和跨境成分背景，但本次取得的材料没有提供同一有效时点的**完整官方成分权重与港股成分可审计申万 L2 归属**。指数自己的医疗行业分类不能直接当作申万 L2 3706；不能按名称猜测或把未观测港股权重补给 3706。

最终 `H30463_EVIDENCE_UNRESOLVED`，执行状态 `UNRESOLVED_FAIL_CLOSED`：不接纳 517990.SH，3706 保留 Cash。这不是 B40 政策阻断项，也不需要无期限继续搜索。既有完整证据中，000913/512010.SH 对 3706 为 37.16%（低于 40%）；399989/512170.SH 为 44.83%，但 3705 为 49.43%（3706 非最大），同样不能接纳。H50006、L11515 可保留为未来工具供给观察项，当前不映射、不自动监控。

## 冻结工程参考组合

下表来自哈希核验后的 `reports/etf_quant/proxy_execution_candidate_v1.json`，仅代表 2026-09-24 历史工程参考，不是可复用的未来逐日 mapping 或订单。

| L2 | 类型 | ETF / Cash | 目标 L2 占比 | 20d 流动性 | 原模型目标权重 | ETF 权重 | 保留 Cash |
|---|---|---|---:|---|---:|---:|---:|
| 3706 医疗服务 | 不可执行 | Cash | 未获证明 | 不适用 | 35.0000% | 0 | 35.0000% |
| 3703 生物制品 | Proxy | 159643.SZ | 46.40% | PASS | 26.0437% | 26.0437% | 0 |
| 4901 证券Ⅱ | Strict | 512880.SH | 100.00% | PASS | 14.1910% | 14.1910% | 0 |
| 4803 股份制银行Ⅱ | Proxy | 159887.SZ | 41.48% | PASS | 12.5684% | 12.5684% | 0 |
| 3701 化学制药 | Proxy | 159992.SZ | 45.98% | PASS | 12.1969% | 12.1969% | 0 |

风险资产 65%，Cash 35%，最大单只 ETF 26.0436961183%，加权目标 L2 purity 57.072012%，leakage 42.927988%，再分配偏差 0。最大的非目标 L2 为 4802 国有大型银行Ⅱ，占账户约 3.696366%。`actual_l2_exposure` 是 ETF 权重乘完整基准 L2 权重并求和；未归属权重不按比例摊回已知行业。3706 从其他 ETF 的偶然泄漏约 8.34% 不代表执行了 3706 信号。Strict V1 的 4/134 覆盖与 `NOT_EXECUTABLE_UNDER_CURRENT_ETF_SUPPLY` 结论保留。

## 技术判定

政策及纯函数契约通过；H30463 fail-closed 判定确定。但未来 Shadow 缺少将当日官方完整权重、PIT 可得性、ETF 20d 流动性与候选池接入 `daily_cycle` 的显式 B40 模式。若现在启动，它仍会使用严格五成员路径。故 `TECHNICAL_SHADOW_READINESS=PARTIAL`、`ETF_QUANT_PROXY_READY_FOR_SHADOW=false`、`production_ready_from=null`。原始 DeepSeek 提案里的 `production_ready_from` 是提案生成时刻，不能作为本次获批候选的运行就绪时间。

没有创建 Shadow epoch、正式 signal/order/fill/holding/NAV/PnL，Validation 与 Final OOS 未读取。`SOURCE_LICENSING_UNRESOLVED` 保留；不作法律授权推断。
