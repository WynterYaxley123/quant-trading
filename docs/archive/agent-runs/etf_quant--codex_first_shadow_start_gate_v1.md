# ETF-Quant V1 最终整合与首次 Shadow 启动门槛

审计时间：2026-09-30 12:57:55（Asia/Shanghai）。**最终认证整合通过，但当前无合法首个 T；没有创建 Epoch、正式 signal、intent、fill、holding 或 NAV。** `READY_FOR_FUTURE_SHADOW` 是候选认证状态，不等于已启动模拟周期。

## 线性整合和候选冻结

独立分支 `integration/etf-quant-v1-shadow-ready-final` 从 `42eb601bfc80991847e301f14387cdff77323b96` 建立，并以 `--ff-only` 到 MiMo 认证 `61a87e32a212584e75eb85b49db5329aae18626d`。仓内候选 `ETF_QUANT_V1_PROXY_EXECUTION_CANDIDATE_20260929_01` 的实际 SHA-256 为 `e743bedb846a286c83870202c4514c80504c74409779b24f2968740914c2eb89`，与 MiMo readiness pin 一致；`READY_FOR_FUTURE_SHADOW`、`B40_WITH_CASH`、`technical_shadow_readiness=PASS`、`ready_for_shadow=true`、`production_pit_evidence_ready=true`、`shadow_epoch_created=false` 均已重读。候选文件没有因本次审计改变。候选是不可变认证输入；未来 Epoch 若合法创建，只能引用其哈希，不得回写候选。

生产 PIT 精简登记册 SHA-256 `81cf6d44831736c81966d3f5275bb0fd0c7d56c4652320821e4fc34143f172dc`，仓外完整索引虽因压缩格式字节不同，共享元数据、权重包集合和暴露包集合一致。仓外适配器证据簿 SHA-256 `ac730d6475528d494515eec841b7c49f8be55d667449fc8208f534058a907b79` 与 manifest 一致；Strict registry SHA-256 `37a9b81cbc07c3255d18b514eef733d4497f98cca19ba855f8626031a66afb37`；政策 SHA-256 `8c210b3fe99cf1e9518ebeb6bcea2014c4e2ac154eb7905d051045ba5a4b3b20`；CNEquity pin 未改（`1650e384a3fd1f67a70144a489acc91432f1df27`）。申万成员证据仍为 `PASS_WITH_KNOWN_LIMITATION`，来源形态不是分类主表；`SOURCE_LICENSING_UNRESOLVED` 保留。

DeepSeek 后置 `45241b1`、`60de605` **INTENTIONALLY_OMITTED**：MiMo 已独立记录 5220 证券、0 冲突、2 只缺口的结论；并行提交另加静态快照计数测试与 MiMo 之前的 handoff SHA。没有整体合并 DeepSeek 分支，也没有修改任何旧 worktree。

## 当前没有合法 T

项目已有正式交易日历将 9 月 29、30 日标记为交易日。生产 PIT 最早在 9 月 29 日 **22:05:26 上海时间**才可用，晚于该日收盘，不能倒填 9 月 29 日 signal；9 月 24 日永远只是历史工程参考日。审计时上海时间 **12:57:55**，9 月 30 日尚未收盘，也没有已完成并 finalized 的当日导出；已找到的最新不可变行情导出仍截止 **2026-09-24**（snapshot `4c82b062149dd4aa49b97b932fe3314b662154d046f15b45a87391d13dd0e071`）。故 `SHADOW_START_GATE=WAITING_FOR_FINALIZED_T`，未运行正式 `daily_cycle`，也没有为制造新 cutoff 启动未完成日线的更新。仓外正式 `shadow/` 目录不存在。

下一必要条件：未来合法 A 股交易日 T 收盘后，现有 **CNEquity-only** 正式 pipeline 发布覆盖 T 的完整、finalized、不可变导出；再核对代码/候选/证据哈希、T 时点可得性、上市、20/20 日流动性与模拟专用配置。届时必须用冻结模型基于真实 T 数据重新排名，先得 Top5，再逐槽 Strict > Proxy > Cash；不可复用历史工程 Top5，不可补造过去意图。仅在全部门槛通过时允许一次手动的 simulation-only 首轮，不启用 broker、真实订单或常驻任务。

**首轮 Epoch 生命周期尚未在正式路径实测**：现有合成 runtime 把内部账户 `epoch` 建在 T+1 延迟记账时，T 日仅持久化信号视图和意图；本任务要求的正式 T0 Epoch manifest（引用冻结 Candidate hash）是更严格的启动契约。本轮没有合法 T，故没有运行或宣称该门槛通过。在任何后续正式首轮之前，必须先核对并在必要时最小修正这项 T0/T+1 语义差异，验收 Epoch 对 Candidate 的哈希引用，不能把现有 T+1 账户 Epoch 冒称为 T0 正式 Epoch。

## 回归与安全

现有 `quant-research:py3.12` 镜像内，checkout 与仓外真实证据均只读挂载：目标 PIT/Strict/B40/候选 **130 passed、0 failed**；完整 ETF + 顶层两文件 **534 passed、1 skipped、0 failed**，达到 MiMo 基线。为可重复在 Docker 中运行，仅给 5 个测试文件增加仓外 runtime 根的环境配置，并把一项交叉核对测试的输出改到 pytest 临时目录；未改业务门槛、未弱化断言，生产 package 未被测试写入。API、前端没有变化且正式状态未创建，本轮未重复运行。没有读取 Validation performance 或 Final OOS；没有推送、市场大表入 Git、真实账户、杠杆或做空。
