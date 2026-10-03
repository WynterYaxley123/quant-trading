# ETF-QUANT V1 Proxy 最终集成报告

日期：2026-09-29。结论：`CODEX_PROXY_FINAL_INTEGRATION_COMPLETE`；用户批准 `B40_WITH_CASH`，但 `TECHNICAL_SHADOW_READINESS=PARTIAL`，不允许据此启动 Shadow。

## 谱系与审计

- 本地 `integration/etf-quant-v1-proxy-final` 从 `7e1931627aa3d5061ec78e43c14dec63ed682ee2` 建立，经祖先与 merge-base 审计后，`--ff-only` 集成 DeepSeek `465c83139e6e1593b981aaabf8dadab592d9abc9`；无冲突、无 cherry-pick 复制。
- DeepSeek handoff 中的 `6885bb6` 是较早提交；以实际 Git final SHA `465c831` 为准。DeepSeek 原始策略/比较/候选的 SHA256 与 manifest 一致，四个仓外关键审计 artifact 的 SHA256 也与 handoff manifest 一致；仓外原始行情未写入 Git。
- 冻结 CNEquity pin `1650e384a3fd1f67a70144a489acc91432f1df27`；严格 registry SHA256 `37a9b81cbc07c3255d18b514eef733d4497f98cca19ba855f8626031a66afb37`。未改研究模型、19 因子、Ridge、H10/H40/H120、Fusion、Source-C gate、行业 ranking。
- `D:\quant-trading`、旧 `integration/etf-quant-v1-final` 和 DeepSeek worktree 仅只读核验，未修改；无 push、无 main merge。

## 已修复、仍未接通

DeepSeek 政策文档引用 `rebalance_decision_v2`、`select_mappings_partial`，原代码却只有名称常量。Codex 在独立模块补了显式 opt-in 的纯函数，并加固 B40 证据、流动性、数值有效性 gate；全部不可执行时允许 100% Cash。旧严格函数、默认五成员及唯一冻结 cap 分配器保持原状。对 40% 边界、主导性、Strict > Proxy > Cash、ETF 去重、Cash 不再分配、不产订单资产、ETF↔Cash 变更和畸形证据增加回归。

尚未接通的是正式 `runtime/shadow.py::daily_cycle`：它仍调用 `mapping.registry.select_mappings`、旧 `rebalance_decision` 和默认 `size_targets`。新兄弟函数没有从官方完整权重和当时可得的 ETF 流动性构造逐日 PIT 候选池，也没有形成经过认证的持久化意图及未来 T+1 执行接线。不能把历史 2026-09-24 工程参考映射直接硬编码到未来。此缺口独立于 H30463；即使 3706 Cash 判定已经确定，技术 Shadow readiness 仍为 PARTIAL。下一步只能设计并测试显式 B40 runtime adapter、证据时点 gate、Cash 对现有模拟账户/T+1 记账的守恒与状态迁移；需另获用户批准启动 Shadow。

## Candidate 冻结及完整性

`reports/etf_quant/etf_quant_v1_proxy_final_candidate_manifest.json` 是 metadata-only：`policy_approved=true`、`candidate_status=POLICY_APPROVED_TECHNICAL_INTEGRATION_PENDING`、`production_ready_from=null`、`historical_reference_only=true`、`H30463=UNRESOLVED_FAIL_CLOSED`、`3706=CASH_UNEXECUTABLE_SIGNAL`。它单列 DeepSeek SHA、Codex 代码 SHA、CNEquity pin、严格 mapping SHA、Proxy 政策/比较/候选及流动性证据 SHA；`actual_l2_exposure` 用原始候选文件哈希与 JSON pointer 定位，不伪造子对象哈希。新测试会重新打开 manifest，核对来源文件 SHA、Top5、四只不重复 ETF、权重 0.65+0.35=1、Cash 无 ETF 身份及原始候选逐项映射。完整性为 `CANDIDATE_INTEGRITY_PASS`。

## 逐项就绪审查

| 项目 | 结果 | 理由 |
|---|---|---|
| 冻结模型、Source-C、19 因子、H10/H40/H120、Fusion、CSI300、L2 contract | PASS（未改） | 本轮不重训、不读封存收益；旧代码/证据谱系保持 |
| Strict V1 独立结论和默认路径 | PASS | 4/134，仍不可执行；五成员断言及默认值未改 |
| Proxy 历史证据与 B40 政策 | PASS | 40% + 最大 L2 + 完整权重/流动性 gate；用户已批准 |
| H30463 / 3706 | PASS（fail-closed） | 官方证据不足，3706 确定保留 Cash，不视为政策阻断 |
| Cash、cap、实际 L2 exposure、ETF 唯一性、ETF↔Cash 纯契约 | PASS | 原权重保留；单一冻结 cap 算法；独立回归覆盖 |
| 历史参考 ETF 数据和 20d 流动性 | PASS（仅历史参考） | 四只标的均为 `LIQUIDITY_ADMISSION_PASS`，不能外推未来 |
| Future PIT mapping / Shadow runtime 接线 | PARTIAL | 主循环仍为 Strict；无逐日 B40 官方证据 adapter |
| T+1 延迟记账旧严格契约 | PASS（未改） | 未创建新 epoch 或填单；B40 路径尚未接线认证 |
| Candidate metadata 完整性 | PASS | 独立读取/哈希/权重验证 |
| Read-only API、Dashboard | PASS（回归） | 未加入交易控制，也未把提案展示成活跃 Shadow |
| Security / licensing | PARTIAL | 无 secret/原始行情入 Git；`SOURCE_LICENSING_UNRESOLVED` 保留 |

## 回归与环境

ETF Python 全套、只读 API、Frontend tests/typecheck/lint/build 均完成且无失败；准确数量见最终 candidate manifest 和最后一次测试输出。前端初次在并发负载下出现 4 个 5 秒超时，空闲复跑为 95 passed / 3 skipped，17 个测试文件通过、1 个跳过；没有修改、跳过或弱化这些测试。Docker Desktop daemon 不可用，因此使用已有隔离 Python 和现有 Node 依赖作回归，没有安装/升级依赖、重建镜像或改变 Compose。全仓含仓外研究 artifact 的测试未作为绿色声明；不读取封存 Validation / Final OOS 来制造通过。

## 安全与停止线

本次仅创建策略执行层代码、测试、审查文档与 metadata-only candidate。Shadow epoch、正式 signal/order/fill/holding/NAV/PnL 均未创建；Validation performance 与 Final OOS 未读取；无真实交易、broker、凭证、push、市场行数据提交。现金不伪装 ETF，不产生订单，不以收益率 0% 冒充无风险收益。正式技术接线完成前 `ETF_QUANT_PROXY_READY_FOR_SHADOW=false`。即使未来为 true，也必须等未来交易日 T 收盘及输入 PIT 可得并由用户另行授权，不能从 2026-09-24 回填。
