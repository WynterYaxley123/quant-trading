# ETF-Quant V1 自主续跑交付

审计：2026-09-30T17:22:52.406880+08:00（Asia/Shanghai）。工程完成，`SHADOW_START_GATE=ARMED_FOR_NEXT_ELIGIBLE_T`。无剩余工程 blocker，只等待合法 finalized data。正式 Epoch、signal、intent、fill、holding、NAV 均未创建。

续用 `integration/etf-quant-v1-shadow-autonomous-final` 的真实最新基点 `9886451c12fb28c537773ba8710d509a8634d3c5`，保留全部上一轮提交；没有回退到 dd96a3a。执行代码与本轮测试 SHA 均为该基点，最终本地提交仅增加本文和小型机器报告，最终 SHA 以 `git rev-parse HEAD` 为准。

## 数据湖与 Windows 路径

迁移记录证明：可恢复同盘 rename 前后均为 **160,072** 文件，根目录 file ID `1407374883938004`、文件身份清单摘要、curated/derived 字节指纹均一致。已发布字节指纹为 `520f175faf951c7758fe6a96f291390163a06bdc6021ccabbaac516440ab5422`。

上一轮随后已恢复正式 SDK 写入。本轮再次暂停新写入进行独立核验：物理根 `D:/QuantForge/etf-lake` 和旧逻辑路径均为 **162,701** 文件，missing=0、extra=0、identity_mismatch=0；同卷身份与根 file ID 一致。新增 2,629 文件来自上轮迁移验证后的正式刷新，不能错误地当作迁移额外文件。原路径仍为指向同一物理目录的 junction，没有复制第二份 lake。全部清单留在仓外，没有写进 Git。

原不可变导出的 **7** 个文件均与 manifest 的存储字节哈希一致。固定 SDK 的真实 `_safe_archive_path` containment guard 只读探针通过，lexical/resolved 最坏路径均为 **240 UTF-16 单元**，无 extended prefix；未写入探针数据，未修改 SDK、registry、ACL、全局 Python、Docker/WSL 设置。

## 正式刷新与启动门槛

首次续跑通过正常 observation 完成 9 月 28 日全部上游门槛；`corporate_actions` 在 9 月 28、29 日均成功，原 extended-path 异常关闭。9 月 29 日出现真实供应数据不足：全市场范围下无法取得 active BJ 证券，且 TDX 未返回 9 只请求证券的日线。上游保持全市场及完整批次门槛，未发布不完整数据。

本轮最后一次 one-shot 复用成功的 9 月 28 日 run，使用公开 `retry_failed_only` 恢复 9 月 29 日失败批次；保留 105 个成功日线 batch，没有全量重抓。最终仍为 `WAITING_FOR_DATA`，最新收据 `20260930T091624_cd01e8e72a7a`。不再循环重试，不缩减 universe，不换供应源，不手补价格。

最新通过正式完整不可变导出准入的 cutoff：**2026-09-24**。9 月 30 日已收盘，但没有覆盖当日的 finalized export，因此没有创建正式 Shadow。9 月 25 日休市；正式项目日历的下一交易日为 **2026-10-08**。9 月 24、28、29 日仍不得补造 Formal Epoch 或历史 intent。部分源发布、收盘时间及 Cash 合法性均不能替代 finalized gate。

`ENGINEERING_COMPLETE=TRUE`；路径、T0 lifecycle、one-shot、生产 PIT、Candidate integrity 均 `PASS`。仓外 `armed_delivery_state_v1.json` 保存结构化 ARMED 交付状态；正式 `shadow/` 目录不存在，也未创建空账户或伪造 NAV。等待结果没有残留 transport lock、source job 或 daemon。

## 唯一后续入口

只需再次调用已有正式入口，无需新开发或手工串联脚本。使用已有隔离 CNEquity 解释器；量化模型、分配和账务继续只在固定 Docker 镜像执行：

```powershell
Set-Location D:/quant-worktrees/etf-quant-v1-shadow-autonomous-final
& D:/QuantForge/external/cnequity-etf-quant-v1/venv/Scripts/python.exe -B services/etf-quant-runner/one_shot.py --config D:/QuantForge/runtime/etf-quant-v1/autonomous-control-v1/config.json
```

当前合法 T finalized 后，该入口按原合同执行 frozen daily cycle，T0 Formal Epoch 引用不可变 Candidate/code/PIT/Strict hashes，再持久化正式 signal 与按组合决定的 T+1 simulation intent；全 Cash 不下单，T+1 open 未可得时不提前 fill。缺证据逐槽 fail-closed 到 Cash，不改变 Top5、不重新分配 Cash。

## 最终验证

- targeted：**73 passed / 0 skipped / 0 failed**。
- API/security：**68 passed / 0 skipped / 0 failed**。
- full ETF（含顶层证据诊断与政策测试）：**566 passed / 1 skipped / 0 failed**，698.68 秒。保留原条件 artifact skip；没有弱化断言。

checkout 与仓外证据只读挂载；Docker 镜像仍为 `quant-research:py3.12` / `sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5`。未安装、升级、pull、rebuild 或修改 lockfile。

## 冻结与安全确认

main、旧 integration、DeepSeek、MiMo 分支与旧 worktree 未修改。F1、19 factors、Ridge alpha=0.01、H10/H40/H120、0.25/0.50/0.25 fusion、Source-C、industry ranking 未修改；Validation performance 与 Final OOS 未读取。

`ETF_QUANT_V1 / SIMULATION_ONLY / NO_BROKER / NO_REAL_ORDER_PATH / NO_LEVERAGE / NO_SHORT`、初始 CNY10,000、Strict > Proxy > Cash、B40_WITH_CASH、40% threshold、target-largest、35% cap、20d liquidity、commission 3bps、单边 slippage 5bps、stamp/minimum commission=0、CSI300 均保持冻结。

Strict 未降低；没有历史证据倒填，没有将旧工程 Top5 当作正式 signal；Cash 未伪装 ETF、未重新分配。无 broker、真实订单、真实资金、杠杆、做空、retroactive intent。CNEquity pin `1650e384a3fd1f67a70144a489acc91432f1df27` 未改，无项目新增第三方行情 fallback。无 destructive Git、raw 数据或 secret 提交，未 push，未 merge main。

生产 PIT 保持 PASS；SWS membership 保留 `PASS_WITH_KNOWN_LIMITATION / OFFICIAL_L2_INDEX_CONSTITUENTS_NOT_MASTER_CLASSIFICATION_TABLE`，不重新开展研究或认证。
