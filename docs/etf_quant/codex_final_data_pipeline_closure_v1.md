# ETF-Quant V1 最终数据流水线闭环核验

> **SUPERSEDED BY [codex_frozen_model_contract_reconciliation_v1](codex_frozen_model_contract_reconciliation_v1.md)**：下文模型合同不兼容、PRODUCTION_USABLE=FALSE 与 BLOCKED_HARD 结论已被后续真实 reference parity 推翻。事实层 PASS 有效，原审计正文保留。

事实流水线的本地工程根因已闭环，正式 finalized cutoff 已连续推进至 **2026-09-30**。定向、API/security 和完整 ETF 测试均无失败。第一 Formal Shadow 没有创建。

**生产可用性结论：FALSE。** 不能将冻结模型的输入障碍包装成供应端临时错误，也不能声称只等下一个交易日就会启动。此次交付保留 runner 的 fail-closed 能力；当前源输入与冻结 Source-C 全横截面要求存在实际不兼容，继续启动需要触及用户禁止修改的核心合同。普通本地工程 blocker 为 0，Formal Shadow 交付评估为 `BLOCKED_HARD`。

实际 one-shot 结果为 `WAITING_FOR_DATA / MODEL_WARMUP_INCOMPLETE`，运行模式仍为 `ARMED_FOR_NEXT_ELIGIBLE_T`；上述 `BLOCKED_HARD` 是生产交付评估，未伪改 runner receipt。

## 真实续跑基线

- 分支：`integration/etf-quant-v1-shadow-autonomous-final`。
- 本轮 continuation base：`ed6138539ed2b3098516add0359631b794dfba63`。
- 已完成真实 runner 与测试的代码 SHA：`72e198c6bfb11632cb8342f9779aeb25247d3b20`；最终文档提交的 SHA 以该分支最终 HEAD 为准。
- 没有 reset、clean、stash、rebase、squash、push 或 merge main。其他分支 refs 与续跑前一致。

## 为什么 9/28 成功但旧 cutoff 仍为 9/24

旧 adapter 先循环处理所有 session，只有全部任务完成才执行一次 export。9/28 的原生 receipt 成功，但 9/29 的后续失败提前返回，导致 9/28 没有 export/finalization receipt。host 又只接收完整 `REFRESH_EXPORTED`，因此遗漏已完成前缀。修复为每个 session 独立 immutable export 与 receipt，连续 cursor 单调推进；后续失败或异常仍将已完成前缀交给 host。

## 已关闭的根因

- `ALL_OR_NOTHING_EXPORT_AFTER_LATER_SESSION`：9/28 原生任务成功后，9/29 的失败使旧 adapter 在整个循环完成前返回；未执行 export，因此旧 cutoff 留在 9/24。 逐 session 发布、不可变 receipt、连续单调 cursor、部分成功对 host 可见。
- `WINDOWS_EXTENDED_PATH_CONTAINMENT`：extended prefix 与 SDK containment 不兼容，并曾被供应端通用错误掩盖。 同盘保身份物理短路径、逻辑 junction、lexical/resolved 双 guard；不改 SDK。
- `BSE_TIP_DATE_AND_FALSE_DELIST_INFERENCE`：当前 tip 请求历史 session 过滤为空，后续两次目录缺席推导出 347 个 BJ 假退市；旧成功 batch 的实际 ownership 为 0。 真实 tip session 的身份桥接、经官方活动目录与旧 byte-verified catalog 反证的限定 COW 纠正；历史价格仍用原生真实历史源。
- `CONTRADICTED_DERIVED_STATUS`：旧 derived_delisted 假证据仍影响 expected-bar admission。 项目 read guard 将限定矛盾记录视为 UNKNOWN，要求真实 bars，保留原 revision。
- `TERMINAL_RECEIPT_NOT_FACT_COVERAGE`：零 failed batch、旧 success receipt 或 stage 数据不等于正式数据完整。 精确 all-A ownership 与独立 no-bar 证据核对；finalization 仅承认 curated，按需一次正常 reobservation。
- `DOCKER_SNAPSHOT_BASENAME`：挂载 /snapshot 丢失快照 hash basename，触发既有 consumer identity guard。 挂载 /snapshot/<真实 snapshot hash>，保留原 guard。

本项目 adapter 调用固定 SDK 的 fetch / stage / settle / compact / derive / audit / publish，保留原生 receipt 和历史 revisions。没有直接改写旧 published 分区，没有手补价格、伪造停牌、推断真实退市或倒填 PIT。原生 SDK 已有的 Sina/Baostock/Eastmoney 属于既定来源合同，没有新增第三方 fallback。

## 连续事实发布

| 交易日 | expected / curated received | missing | BJ expected / received | 正式发布 |
|---|---:|---:|---:|---|
| 2026-09-28 | 5557 / 5557 | 0 | 347 / 347 | PASS |
| 2026-09-29 | 5558 / 5558 | 0 | 347 / 347 | PASS |
| 2026-09-30 | 5561 / 5561 | 0 | 348 / 348 | PASS |

各日全部必要原生 stages 与 corporate_actions 均 PASS。9/28 的旧 scope 标签曾包含 stage；本次独立重读三个日期的 curated 分区，证实全部 expected keys 已正式提交。9/29、9/30 finalized admission 直接使用 `CURATED_ONLY`，staged-but-unpublished 为 0。官方日历认定 9/25 休市，不存在待补的 9/25 session。

最新 immutable snapshot：`5f593d4e16d5becc354d3e5f6411e9cbc6f6033a9c75a1a3845ad39b6859afde`。三日完整 snapshot / run ID 与 hash 摘要见同名 JSON 报告；大 scope、receipt、原始行情和 runtime 全部仓外。

## 原 missing 9 与新增 3 个历史缺口

以下 9/29 状态来自带真实观察时间的原生独立状态源，全部为 `EXPECTED_NO_BAR`。没有用缺价格推断停牌，没有制造零价格 bar，没有写虚假 delist_date。

| 标的 | 名称 | 上市日期 | 状态源 | 核验日期 |
|---|---|---|---|---|
| 000016.SZ | *ST康佳A | 1992-03-27 | baostock | 2026-09-29 suspended |
| 002731.SZ | *ST萃华 | 2014-11-04 | baostock | 2026-09-29 suspended |
| 002860.SZ | 星帅尔 | 2017-04-12 | baostock | 2026-09-29 suspended |
| 300082.SZ | 奥克股份 | 2010-05-20 | baostock | 2026-09-29 suspended |
| 301139.SZ | 元道退 | 2022-07-08 | baostock | 2026-09-29 suspended |
| 601059.SH | 信达证券 | 2023-02-01 | eastmoney | 2026-09-29 suspended |
| 601198.SH | 东兴证券 | 2015-02-26 | eastmoney | 2026-09-29 suspended |
| 603400.SH | 华之杰 | 2025-06-20 | eastmoney | 2026-09-29 suspended |
| 688496.SH | *ST清越 | 2022-12-28 | eastmoney | 2026-09-29 suspended |
| 300527.SZ | 中船应急 | 2016-08-05 | baostock | 2026-09-29 suspended |
| 600293.SH | 三峡新材 | 2000-09-19 | baostock | 2026-09-29 suspended |
| 600363.SH | ST联光 | 2001-03-29 | baostock | 2026-09-29 suspended |

347 个旧 BJ 假退市经当前官方 board 身份与旧冻结目录反证后，在新原生 COW revision 纠正；同一历史日期需要真实 BJ bars。9/29 新 observation 得到 347 个 BJ 历史价格，9/30 得到 348 个；当前 tip 只用于身份与真实 tip 日期，未被重新贴成历史行情。

## 数据湖身份与 bytes

- 原 relocation 的 160,072 / 160,072 文件身份与 published byte fingerprint 保持一致。
- 本次授权正式更新后的物理/逻辑路径文件数：187,511 / 187,511；missing=0、extra=0、identity mismatch=0。
- root file ID：`1407374883938004`；volume identity：`16315591276170813369`。逻辑 junction 与物理短路径为同一 data lake，无复制。
- relocation published fingerprint：`520f175faf951c7758fe6a96f291390163a06bdc6021ccabbaac516440ab5422`；原 9/24 冻结 export 的 7 个 CSV bytes hash 与所有新 immutable export 均 PASS。
- 首轮复核观察到 SQLite `manifest.db-shm` 的 mtime 在只读 metadata 查询期间改变；不属于 published factual data。关闭查询后重做完整双路径统计，最终所有文件身份一致；未删除或忽略任何 published 文件。

## 尚未满足的冻结模型输入

真实诊断只检查当前 finalized snapshot 的输入覆盖，未读取 Validation performance 或 Final OOS。输入含 361 个实际交易日（2025-04-10 至 2026-09-30），Source-C 显式行业 universe 为 162，当前有效行业数为 110。没有任何一天具备完整有限值横截面。

| 期限 | mature cutoff | 有效训练日 / 既定最小值 |
|---|---|---:|
| H10 | 2026-09-15 | 0 / 30 |
| H40 | 2026-08-04 | 0 / 30 |
| H120 | 2026-04-08 | 0 / 30 |

例：1103 当前只有 4 个成分股，1109、3307 各 3 个，7703 为 4 个；均不足 Source-C 的既定最小 5 个。另有递归前缀断裂与覆盖不足。源数据的日线 batch 已完整，不等于冻结 Source-C 或模型输入可用。单纯下一交易日到来不会自动修复这些既有全横截面问题。

本轮保留 Source-C、行业 universe、递归前缀语义、训练成熟度及模型全部原样；没有删除不合格行业、降低 80% / 5 个门槛、重启递归序列、改 Top5 或以 all-Cash 冒充已计算的正式 signal。因此 Epoch、signal、intent、fill 都没有创建。继续满足正式启动目标涉及冻结核心规则，属于用户列出的 Hard Stop（需要改变冻结合同才能推进）。

## 运行与恢复验证

- 真实 one-shot 先逐日恢复 9/28→9/29→9/30，并在连续 finalized receipt 后使用正式 Docker consumer。最后两次同配置调用均没有再刷新行情，返回同一冻结模型输入 gate，没有正式 runtime generation 或重复业务状态。
- T0 创建 Formal Epoch、T+1 引用同一 Epoch、all-Cash 合法、immutable Candidate 和幂等 signal/intent 已由合成 lifecycle tests 验证；本轮没有把合成证明冒充真实 Epoch。
- crash/restart 回归涵盖 fetch、stage、derive、before export、export before receipt、receipt before cursor、after publish；真实 stale lock 只在操作系统证实旧 PID 已死后恢复。活进程或身份未知的锁不被抢占。
- kernel guard、source jobs 和 transport locks 已释放，无 daemon。

唯一正式入口，工作目录为该分支 worktree：

```powershell
& D:/QuantForge/external/cnequity-etf-quant-v1/venv/Scripts/python.exe -B services/etf-quant-runner/one_shot.py --config D:/QuantForge/runtime/etf-quant-v1/autonomous-control-v1/config.json
```

当前再次调用将继续按冻结模型输入 gate fail-closed；不能承诺“仅等待下一次 finalized 数据即可启动”。无需手工串 fetch/publish 脚本。

## 测试与安全

- targeted：100 passed / 0 skipped / 0 failed。
- API/security：68 passed / 0 skipped / 0 failed。
- full ETF：595 passed / 1 skipped / 0 failed。
- production PIT 与 Strict registry：PASS。SWS 既有结论保留 `PASS_WITH_KNOWN_LIMITATION / OFFICIAL_L2_INDEX_CONSTITUENTS_NOT_MASTER_CLASSIFICATION_TABLE`，没有重新认证。

Candidate hash：`e743bedb846a286c83870202c4514c80504c74409779b24f2968740914c2eb89`。PIT registry hash：`81cf6d44831736c81966d3f5275bb0fd0c7d56c4652320821e4fc34143f172dc`。

确认：main、旧 integration、DeepSeek、MiMo refs 未修改；F1、19 factors、Ridge .01、H10/H40/H120、fusion .25/.50/.25、Source-C、industry ranking、training maturity 未改；Validation performance / Final OOS 未读取。

Strict > Proxy > Cash、B40、40%、target-largest、35% cap、20d liquidity、Cash 不再分配、CNY10,000、commission3bps、slippage5bps each side、stamp0、minimum commission0、CSI300 均未改。旧工程 Top5 没有作为正式 signal，Cash 没有伪装 ETF，没有历史证据倒填或 retroactive intent。

SIMULATION_ONLY；无 broker、real order path、真实资金操作、杠杆或做空。CNEquity pin 与 vendor/source 未变；无依赖安装/升级、新数据 fallback、全局系统配置修改、破坏性 Git、raw/runtime/secret 提交；push=FALSE。

详细摘要：[JSON 报告](../../reports/etf_quant/codex_final_data_pipeline_closure_v1.json)。仓外审计目录：`D:/QuantForge/runtime/etf-quant-v1/autonomous-control-v1/root-cause-closure-v1`。
