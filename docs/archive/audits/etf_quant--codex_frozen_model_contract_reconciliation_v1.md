# 冻结模型合同对齐与生产输入闭环

**PRODUCTION_USABLE=TRUE，MODEL_READINESS=PASS，SHADOW_START_GATE=ARMED_FOR_NEXT_ELIGIBLE_T。** 上一轮 `FROZEN_SOURCE_C_CONTRACT_CHANGE_REQUIRED` 结论 **OVERTURNED**。实际成功的冻结工程路径已使用既有的 107 行业模型准入集合；生产入口遗漏这项 binding，并存在历史会员 bootstrap 与完整快照替换的实现偏差。修复生产适配器即可恢复一致性，无需修改冻结策略。

本报告取代 `codex_final_data_pipeline_closure_v1.md` 中模型合同不兼容、生产不可用与 `BLOCKED_HARD` 的结论。原报告的数据流水线、身份、fingerprint、BJ/CA/finalization 认证继续有效。本轮没有重新研究数据流水线、刷新 lake 或读取 sealed performance。

## 真实冻结 reference

- `services/cnequity-sidecar/coverage_matrix.py::audit/classify/valid_bar`（第 128 行）；代码 SHA-256 见 JSON。
- `strategies/etf_quant/data/membership.py::session_universe`（第 117 行）；代码 SHA-256 见 JSON。
- `strategies/etf_quant/data/source_c.py::industry_date`（第 133 行）；代码 SHA-256 见 JSON。
- `scripts/audit_etf_quant_readiness.py::advance_source_c + diagnostic_common_universe`（第 56 行）；代码 SHA-256 见 JSON。
- `scripts/audit_etf_quant_models.py::fit_retrospective_horizon + audit`（第 42 行）；代码 SHA-256 见 JSON。
- `docs/etf_quant/common_model_universe_v1.md::107 model-universe admission`（第 1 行）；代码 SHA-256 见 JSON。
- `strategies/etf_quant/domain/industry_level.py::current frozen explicit L2 taxonomy`（第 1 行）；代码 SHA-256 见 JSON。

实际 9/24 Source-C/模型权威是上述工程 producer、sealed factor matrix 与成功 Ridge artifact，并由 9/28 `COMMON_MODEL_UNIVERSE_V1` admission 明确允许工程验证及 forward warmup 使用。原 F1 的固定官方指数研究输入与获准 ETF Source-C ASOF constituent 重建输入具有不同 artifact binding；不能仅从旧 F1 primitive 推断 ETF 模型应当换成固定历史分类或允许 partial 截面。

三个原始只读 artifact 保持 bytes：

- readiness：`D:\QuantForge\runtime\etf-quant-v1\codex-final-completion\reports\etf_quant_readiness_20260928T091309Z_0d2dfbc6.json`。
- 19 因子矩阵：`D:\QuantForge\runtime\etf-quant-v1\codex-final-completion\reports\etf_quant_factor_readiness_20260928T091309Z_0d2dfbc6.csv`；SHA-256 `6771e6c352df00d9a9f2e6bc98b3b0c20b1614f93bdea8e0e3e813e133bbb482`。
- 实际成功工程 Ridge：`D:\QuantForge\runtime\etf-quant-v1\codex-final-completion\reports\etf_quant_engineering_ridge_20260928T123624Z_828fad6e.json`；SHA-256 `75d21fd4f02e63df26f2be85f1b661f7ebed0965710f7f4d5e1cfe8c01610b68`。
- 冻结 snapshot：`D:\QuantForge\runtime\etf-quant-v1\codex-final-completion\engineering-exports\c085168103a7e8206009018e9b0cbc7f1e74b0e03dfed6c9f4ad12896af48995`；manifest SHA-256 `4deb4c71da68fef9f6a0a37f77f39c23ac9027b15ffe04ade7f3e2474052d595`。

模型绑定文件 `strategies/etf_quant/config/common_model_universe_v1.json` 固定相同 107 列表、warmup 起点及上述 bytes hashes。原 admission 未修改；当前正式 L2 taxonomy 已在本轮开始前解决早期文档描述的 L3 差异，本轮保留其显式映射。

## Contract Diff

| Semantic | Frozen reference | Old production behavior | Fixed production behavior | Status |
|---|---|---|---|---|
| 行业层级 | 显式冻结 SWS L2 taxonomy | L2 已正确 | 保留；未回退到早期文档的 L3 描述 | UNCHANGED |
| 模型行业集合 | 已准入的固定 107 行业 | 未绑定 admission，使用全部 162 taxonomy 行业 | hash 绑定相同 107 列表；全部 162 Source-C 仍计算和审计 | FIXED |
| 历史分类 | TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE | backward-asof 模式 | 保留 ASOF；禁止偷偷替换成固定分类或当前执行分类 | UNCHANGED |
| 会员快照替换 | 全量最近快照替换 constituent set | 逐证券合并，已移出证券残留 | 完整快照替换；不虚构 constituent | FIXED |
| warmup bootstrap | 2025-04-10 起，使用此前 2025-03-31 会员快照 | 短 export 缺前置快照，延后起点 | 只读 hash-verified 冻结历史 seed；之后使用当前 export 快照 | FIXED |
| 个股有效价格 | positive OHLC/volume、stock/CDR 身份；真实 adjacent adjusted return | 价格/adj 检查存在，instrument/CDR 排除未完全一致 | 与实际 coverage_matrix reference 一致；未补造价格 | FIXED |
| Source-C date gate | 每行业每日期有效成分 >=5、coverage>=80% | 同门槛、每行业每日期 | 保持原门槛与真实 denominator，含 BJ | UNCHANGED |
| 递归前缀 | 每行业独立；断裂后永不 restart/rebase | 已经是每行业独立 | 保持；不把旧故障错误解释成 global prefix failure | UNCHANGED |
| 历史 publication | 重建输入；历史 PIT 未证明，available_at=null | 保持 UNKNOWN/null | 保留；当前观察时间不冒充历史发布时间 | UNCHANGED |
| 训练 observation | date × sector；每行等权 | date × sector；每行等权 | 相同；完整日期包含固定 107 个 sector rows | UNCHANGED |
| 完整横截面 | admitted 107 内完整日期 | 以 162 全 taxonomy 检查，三期限均 0 日 | 107 内仍整日拒绝 partial 截面；非准入行业不能否决 | FIXED |
| 训练 maturity | T-h；各自 mature cutoff 往前六个月 | 相同 maturity/window | 相同；模型日历对齐真正冻结 warmup sessions | ALIGNED |
| minimum training | 每期限 >=30 unique valid dates | 30 日 | 30 日；29 日明确 FAIL；不以 observation 数代替日期 | UNCHANGED |
| 因子 NA | 19 因子定义不变；H10 5 维、H40/H120 19 维；不填 NA | 相同定义 | 保留；全部 19 factor mask 与数值 parity PASS | UNCHANGED |
| Ridge/target | alpha=.01、raw X；同日期同模型集合超额收益 | 相同数学 | 相同；不在 partial 横截面重新求均值 | UNCHANGED |
| z-score/fusion/ranking | 三期限同 107 集合各自 z-score；.25/.50/.25；Top5/ties | 被错误的 162 input gate 截断 | 共享冻结模型数学；9/24 raw/z-score/Top5 parity | FIXED_BINDING |
| 执行 PIT/配置 | 当前生产 PIT + Strict > Proxy > Cash/B40 | 既有冻结 guard | 保留；历史模型 bootstrap 不替代执行 PIT | UNCHANGED |
| Formal timing | 当前真实 T、finalized、forward-only；T0 Epoch，T+1 intent | 既有同日/forward guard | 保留；readiness reference 不写 Formal namespace | UNCHANGED |

旧生产对 162 taxonomy 行业作全截面检查，9/30 当前有效 close 为 110，但 H10/H40/H120 的完整训练日全部为 0。冻结工程证据早已记录“162 完整训练日=0；107 admitted 完整训练日通过”。本轮没有重新按当前数据挑选行业，也没有允许 admitted universe 内按 sector 独立丢行：任何 107 截面缺列仍整日拒绝。

历史 export 的 `2025-03-31` 会员 seed 只用于既有 `2025-04-10` warmup 起点。原始 seed bytes、manifest、代码与 artifact hashes 均自动校验；之后所有会员变化来自当前 export。完整会员快照替换移出的证券，禁止逐证券 merge 保留不存在的 constituent。Source-C 仍独立计算、审计全部 162 行业；per-sector prefix 已经正确，未被当成 global prefix bug 再次重写。

## 9/24 真实 parity

重新构建同一冻结工程输入并与 sealed artifacts 逐项比较，未读取收益表现：Source-C 有效状态 mismatch **0**，有效 close 比较 **38,684** 个，最大绝对误差 `4.55e-13`；19 因子有限值状态 mismatch **0**，最大绝对误差 `1.42e-14`。三个期限训练日期数和 observation 数一致，raw prediction 最大误差 `1.64e-15`，z-score 最大误差 `2.94e-14`。差异仅在浮点舍入范围。

reference Top5 `3706 / 3703 / 4901 / 4803 / 3701` 完全重现。它只证明 reference parity，没有作为正式信号复用。数值摘要在 `D:\QuantForge\runtime\etf-quant-v1\frozen-model-reconciliation-v1\reference_parity.json`。

## 9/30 finalized snapshot 的非正式 readiness

真实最新 factual cutoff **2026-09-30**，immutable snapshot `5f593d4e16d5becc354d3e5f6411e9cbc6f6033a9c75a1a3845ad39b6859afde`；manifest SHA-256 `c5608d3dd6910ba062201a97dc3bd5a22cc65eee9155d974156e3926b2625463`。同一生产 Source-C/input builder 的当前有效行业为 **107**，共享生产训练 row builder、NumPy Ridge 与冻结 fusion：

| Horizon | Valid observations | Unique valid dates | Valid sectors | Mature cutoff | Minimum requirement | Status |
|---|---:|---:|---:|---|---|---|
| H10 | 13,589 | 127 | 107 | 2026-09-15 | 30 unique dates | PASS |
| H40 | 12,733 | 119 | 107 | 2026-08-04 | 30 unique dates | PASS |
| H120 | 12,947 | 121 | 107 | 2026-04-08 | 30 unique dates | PASS |

以下仅为 `MODEL_READINESS_REFERENCE` 的非正式排名，未产生 mapping、target weight、Epoch、signal 或 intent：

| Rank | L2 | Fused score |
|---:|---|---:|
| 1 | 3703 | 2.0639817967038 |
| 2 | 3706 | 1.91787754551354 |
| 3 | 4804 | 1.52771697314373 |
| 4 | 4803 | 1.46894975246415 |
| 5 | 3405 | 1.4597284494211 |

完整数学 artifact 位于 `D:\QuantForge\runtime\etf-quant-v1\frozen-model-reconciliation-v1\latest_model_readiness.json`；`formal_signal=false`、`historical_available_at=null`、`historical_membership_pit_proven=false`。readiness 函数复用正式生产样本构建与数学，未绕过 Formal 写入入口的真实时钟与 snapshot availability guard。

## 行业与证据层

当前最近会员快照 **2026-09-24**：162 个 active L2；历史 union 181，其中 19 个 retired/historical-only code 均在当前 162 之外。131 个当前 code 在冻结 official taxonomy 中有名称证据，31 个 hierarchy 已知但名称 publication 未证明，unknown hierarchy 0；这不是完整官方 master classification 的新认证，也没有据此重选 107 模型行业。全部 admitted 107 当前 active。逐 code 小型审计在 `D:\QuantForge\runtime\etf-quant-v1\frozen-model-reconciliation-v1\universe_audit.json`。

Layer A 是历史 ASOF constituent/feature 重建，historical classification PIT 保持未证明；Layer B 是当前真实 finalized snapshot 的模型输入与观察时点；Layer C 是独立生产执行 PIT。A 的历史 seed 不进入 C 的执行证据，不能补造发布时间。Strict/PIT 仍 fail closed 到 Cash；SWS 继续 `PASS_WITH_KNOWN_LIMITATION`，限制为 `OFFICIAL_L2_INDEX_CONSTITUENTS_NOT_MASTER_CLASSIFICATION_TABLE`。

## 正式启动与唯一入口

实际 one-shot 已连续两次运行，均返回：`status=READY_NO_SIGNAL`、`data_cutoff=2026-09-30`、`shadow_runtime_armed=true`、`shadow_start_gate=ARMED_FOR_NEXT_ELIGIBLE_T`，`refresh_attempted=false`。没有测试时钟或历史 override。

readiness 认证完成时真实上海日期已经是 **2026-10-01**。正式日历认定当日休市，下一交易日 **2026-10-08**。当前 finalized 9/30 export 的 `created_at=2026-09-30T14:13:35.323862+00:00`；Formal gate 仍要求当前同日真实 T，不因为 T+1 尚未来临而补造 9/30 Epoch/signal/intent。**无剩余工程 blocker；只等待下一合法 T 的 finalized factual data。**

唯一正式 one-shot 命令：

```powershell
& D:/QuantForge/external/cnequity-etf-quant-v1/venv/Scripts/python.exe -B D:/quant-worktrees/etf-quant-v1-shadow-autonomous-final/services/etf-quant-runner/one_shot.py --config D:/QuantForge/runtime/etf-quant-v1/autonomous-control-v1/config.json
```

一次调用自动执行环境/完整性、正式 forward 更新、finalized gate、frozen model、PIT、Strict/Proxy/Cash、sizing、T0 Formal Epoch、signal 与 T+1 simulation intent。reference snapshot 会由入口自动验证 hash 并只读挂载，用户无需手工串联 smoke/audit 脚本。无 daemon；缺证据、全 Cash 与等待 T+1 open 均沿既有冻结语义处理。

仓外 Formal runtime 当前无 `latest.json`、无 committed runs、无 Epoch/signal/intent/fill/holding/NAV。旧 failed attempt diagnostics 仅保留历史记录，不是最新 one-shot 状态；control 的 `latest_observation.json` 为正式结构化结果。

## 验证与本地交付

- targeted：**128 passed / 0 skipped / 0 failed**，涵盖 path/adapter、reference parity 规则、T0 lifecycle、one-shot、PIT/Strict/Proxy/Cash、daily/rebalance/T+1。
- API/security：**68 passed / 0 skipped / 0 failed**。
- full ETF：**610 passed / 1 skipped / 0 failed**；较本轮 baseline 595 新增 15 项有意义的合同 regression。
- 新测试覆盖非准入行业与 retired row 的隔离、admitted partial date 仍拒绝、各期限 29/30 unique dates、per-sector 5/80% 与 prefix、完整会员快照替换、未知历史 publication、不允许固定分类替换、执行 PIT 未降低与 seed bytes 防篡改。

本轮 continuation base `b6980e077d8bba6ba8fbae76ecdbb53f773e6439`；测试通过的实现提交 `042154268563d595f23d81e760d251e67f701aea`。最终文档提交 SHA 见仓外 `D:\QuantForge\runtime\etf-quant-v1\frozen-model-reconciliation-v1\final_delivery_state_v1.json` 与最终响应。修改只在 `integration/etf-quant-v1-shadow-autonomous-final`；其余全部 branch refs 与开工记录相同。code integrity extension 新增适配器/准入 binding hashes，Candidate bytes 不变。

安全核验：main、旧 integration、DeepSeek、MiMo 未修改；F1、19 factors、Ridge .01、H10/H40/H120、fusion、Top5/ties、Source-C 真实规则、5/80%、30 日、Strict、B40 40%/target-largest、35% cap、20d liquidity、Strict > Proxy > Cash、Cash allocation、fees、T+1、Candidate 与 PIT policy 均保持。未读 Validation/Final OOS performance，无历史证据倒填、无 retroactive intent、无真实 broker/order/money、无杠杆/做空；CNEquity pin `1650e384a3fd1f67a70144a489acc91432f1df27` 与 vendor 源未改变。无第三方行情 fallback、无 destructive Git、无新安装/升级或全局配置变更、无大型 raw/runtime/secret 提交，**push=FALSE**。
