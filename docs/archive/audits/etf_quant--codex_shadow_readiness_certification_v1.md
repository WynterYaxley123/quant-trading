# ETF-QUANT V1 Shadow 技术就绪认证

结论（2026-09-29）：`SHADOW_DRY_RUN=PASS`，`TECHNICAL_SHADOW_READINESS=PARTIAL`，`ETF_QUANT_PROXY_READY_FOR_SHADOW=false`，`SHADOW_EPOCH_CREATED=false`。用户批准的是 B40 执行政策，不是启动 Shadow；此结论没有把合成测试当成官方数据准入。

## 隔离 dry-run

入口：`tests/etf_quant/test_b40_runtime_dry_run.py`。全部使用合成行情、合成官方 JSON 和 pytest 临时目录 `DRY_RUN_ONLY/runtime`；不写 `D:\QuantForge\runtime\etf-quant-v1\proxy-runtime-final`（检查为不存在），不写正式 latest/state。测试了 T 日 Strict+Proxy+Cash 五槽与持久化 ETF 意图、T+1 raw open 买入及较晚记账、Cash→Proxy、Proxy→Cash 卖出、Proxy→Strict、Strict 到期→Proxy、Proxy A→B、全 Cash、成员不变不因分数/权重交易；还覆盖未来证据、同日边界、上市日、20 日窗口、权重不足、官方来源哈希、伪官方主机、未来分类、缺失 T+1 bar 和拒绝 T+2 补执行。dry-run 内产生的模拟 epoch/fill 仅在临时目录；新增正式 epoch、signal、intent、order、fill、holding、NAV、PnL 均为 **0**。

## 就绪 gate

| Gate | 结论 |
|---|---|
| 冻结模型、Source-C、19 因子、Ridge、H10/H40/H120、Fusion、CSI300、L2 Top5 | PASS（未改） |
| Strict 默认映射、五成员断言、默认 `required_assets=5` | PASS |
| B40 ≥40%、最大 L2、Strict > Proxy > Cash | PASS（合成状态机） |
| Cash 原权重保留、不再分配、不产生证券订单 | PASS（合成状态机） |
| PIT 时间与已消费证据哈希检查 | PASS（合成状态机） |
| **现有真实官方证据转成可逐日准入的 PIT book** | **BLOCKED：尚无合格包** |
| 上市与 20 日流动性 | PASS（合成状态机）；真实未来 T 须重新核对 |
| ETF/Cash/Strict/Proxy 成员变更 | PASS（合成状态机） |
| 唯一冻结 35% cap、T+1 持久化意图、真实 raw open、延迟记账 | PASS（合成状态机） |
| 候选清单哈希/权重/政策重读 | PASS |
| 只读 API、Dashboard、测试与安全 | PASS |

H30463 `UNRESOLVED_FAIL_CLOSED` → 3706 Cash 是预期政策输出，**不是**这次技术阻断。整体 ETF 数据覆盖与 `SOURCE_LICENSING_UNRESOLVED` 是已知限制，不作法律结论。唯一决定性的就绪阻断是尚未证明真实官方权重和逐证券申万 L2 归属在未来每个 T 的可得时间；不能以研究 snapshot_date 代替 evidence_available_at。

## 回归、候选及停止点

ETF Python 413 passed / 1 skipped（基线 395 / 1，新增 17 个 B40 dry-run 测试及 1 个 readiness 完整性测试）；只读 API 58 passed（基线 57）；前端 96 passed / 3 skipped（基线 95 / 3）；typecheck、lint、build PASS。测试未删减或放宽。Docker daemon 仍 DOWN；使用已有隔离 Python 与现有 Node 依赖，未安装、升级、重建或拉取。全仓 Python 含封存研究和仓外历史 artifact，未以读取封存数据的方式求取“绿色”，故不声称全仓通过。

候选 `ETF_QUANT_V1_PROXY_EXECUTION_CANDIDATE_20260929_01` 保持 `POLICY_APPROVED_TECHNICAL_INTEGRATION_PENDING`、`production_ready_from=null`；历史 2026-09-24 参考组合与 65% 风险资产/35% Cash 不变，不是未来正式信号。机器可读细节见 `reports/etf_quant/codex_b40_cash_runtime_readiness_v1.json`。下一安全动作是提交并独立核验 PIT-native 官方权重与分类证据包，再在**未来合法交易日 T** 重算准入和 readiness；即便届时 PASS，也须用户另行授权启动 Shadow。不得回填历史或读取 Validation/Final OOS。
