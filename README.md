# ETF-Quant V1

**A-share industry/theme ETF research + forward Shadow simulation system。**
使用真实、forward-only finalized factual data 运行内部模拟，提供只读操作控制台。

**SIMULATION_ONLY · NO_BROKER · NO_REAL_ORDER_PATH · NO_LEVERAGE · NO_SHORT**

Shadow 是向前运行的内部模拟，不是历史回测，也不是券商 paper account。
模型信号、模拟意图和延迟账务全部仓外保存；控制台不能下单、连接券商或编辑持仓。

## 当前交付状态

以下为 **as of 2026-10-01（Asia/Shanghai）** 的认证。静态 README 不是永久实时状态；
动态日历、latest finalized cutoff、runner receipt 与正式 Epoch 以 `/api/etf-quant/v1/current` 为准。

| 项目 | 状态 |
|---|---|
| Engineering / Factual Pipeline | PASS / PASS |
| Data-lake identity / Windows path | PASS / PASS |
| Frozen F1 / Source-C parity | PASS |
| Production model adapter / H10/H40/H120 readiness | PASS |
| Production PIT evidence | PASS |
| Production usable for Shadow | TRUE |
| Shadow Runtime | ARMED_FOR_NEXT_ELIGIBLE_T |
| First Formal Shadow Epoch | 尚未创建；正常初始状态 |
| Broker / real orders | DISABLED / DISABLED |

最新已认证 finalized factual cutoff 为 **2026-09-30**。当前处于休市周期，READY_NO_SIGNAL 是正常输出；
下一 eligible 日期由正式交易日历动态计算。不得历史补造 Formal Shadow，也不能仅凭收盘时间判断 finalized。

当前权威为 [Frozen model reconciliation](docs/etf_quant/codex_frozen_model_contract_reconciliation_v1.md)、
[最终 release metadata](reports/etf_quant/etf_quant_v1_final_release_v1.json) 与
[文档索引](docs/etf_quant/README.md)。旧数据流水线报告的模型合同阻断结论已 **OVERTURNED**；
其审计正文保留并标记 SUPERSEDED，事实层 PASS 继续有效。

## Quick Start

使用既有冻结 Docker `quant-research:py3.12`、Node ≥22 和锁定的 pnpm 环境。
Python 量化仅在 Docker 执行；宿主机只使用现有隔离 sidecar 的 transport / metadata 入口。
本轮未安装、升级依赖或重建镜像。新部署前端可按已提交的 pnpm-lock.yaml 恢复依赖，不改 lockfile。
`D:/QuantForge` 是当前 Windows deployment 布局示例，不是 GitHub 文档链接。

```powershell
docker version
docker info
docker ps
```

**A. 打开只读控制台**，在当前 checkout：

```powershell
& ./scripts/Start-EtfQuantConsole.ps1
```

访问 [ETF 总览](http://127.0.0.1:5173/etf-quant/overview)。helper 启动 loopback ETF API3312 与 Vite5173，
日志仓外保存，不调用 runner。ETF 路由不打开 Research artifacts，也不依赖 Research API。
手工启动见 [API](services/etf-quant-api/README.md)、[Dashboard](dashboard/README.md)。

**B. 运行一次正式 Shadow cycle**：

```powershell
& D:/QuantForge/external/cnequity-etf-quant-v1/venv/Scripts/python.exe `
  -B ./services/etf-quant-runner/one_shot.py `
  --config D:/QuantForge/runtime/etf-quant-v1/autonomous-control-v1/config.json
```

这是唯一正式入口，自动完成 environment/integrity → forward update → finalized gate → frozen model → PIT →
Strict/Proxy/Cash → sizing → T0 Formal Epoch → signal → T+1 simulation intent。
不需手工串联 repair/audit 脚本，无 daemon/scheduler。正式运行前 checkout 必须 committed、clean，
且分支为 integration/etf-quant-v1-shadow-autonomous-final；PR merge 不改变已有 runner branch guard。

## Runner 状态

| 状态 | 含义 |
|---|---|
| READY_NO_SIGNAL | 当日休市，正常等待 |
| ARMED_FOR_NEXT_ELIGIBLE_T | wrapper start gate；下一真实合法 T 重跑同一入口 |
| WAITING_FOR_MARKET_CLOSE | 正式交易日尚未到 finalization 观察时间 |
| WAITING_FOR_PROVIDER_DATA | bounded retry 后供应端暂不可用 |
| WAITING_FOR_FINALIZED_DATA | 当前 T 尚无完整 immutable admission |
| STARTED / AWAITING_T1_OPEN | T0 Formal 已创建；真实 T+1 open 尚未可用时 fill=0 |
| SHADOW_CASH_ONLY | 全 Cash 信号合法，不产生 ETF order intent |
| ALREADY_PROCESSED | 同日正式事件已处理，不重复 signal/intent |
| BLOCKED_INTEGRITY / BLOCKED_CODE_INTEGRITY / BLOCKED_DATA_INTEGRITY | 实际完整性/工程 gate，fail closed |

Current API 区分静态认证、最新 receipt 与 HISTORICAL 失败。历史 9/24 engineering Top5、
9/30 MODEL_READINESS_REFERENCE 都不能显示成 Formal Signal。

## 架构与时序

```text
External factual sources → pinned CNEquity warehouse → immutable finalized snapshot
  → Frozen Source-C → H10/H40/H120 Ridge → per-horizon z-score + fusion → Top5 L2
  → Strict > Proxy > Cash → frozen allocator → T0 Formal Epoch + signal + T+1 intent
  → actual finalized T+1 open → delayed accounting
```

T finalized close 形成 signal，并在 **T0** 创建 Formal Epoch。Epoch 引用 Candidate / code / PIT / Strict hashes；
Candidate 不回写 runtime Epoch ID。真实 T+1 open 才允许 fill，禁止先看 open 后补造 T intent。
Formal Epoch 与 T+1 accounting/internal account epoch 分别观察。没有账务 Epoch 时，equity、holding、NAV、PnL
为 null/空，不把 CNY10,000 初始预算当作已经存在的账户资产。

## 冻结模型与执行政策

- 固定 **107 admitted industries**；TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE。
- Source-C 是内部等权 constituent return series，不是官方指数；industry×date ≥5 valid constituents、coverage≥80%，
  真实 calendar-adjacent adjusted returns。每行业独立递归前缀，断裂不 restart/rebase，不填 NA、不制造 OHLC。
- Ridge alpha=.01，raw X；各 maturity cutoff 往前六个月；至少 **30 unique valid training dates**。
  107 内保留日期必须完整截面，date×sector 每行等权。
- H10：d10,p5,align,vc,dd20；H40/H120 冻结全部 19 因子。各 horizon population z-score → .25/.50/.25 → Top5。
- **Strict > Proxy > Cash / B40_WITH_CASH**：Proxy target L2≥40%，且 target-largest；单 ETF cap35%。
  未执行 slot 保留原权重为 Cash，不重新分配、不下扫替换 Top5。
- 初始资本 CNY10,000；commission3bps、slippage5bps each side、stamp0、minimum commission0。
  20-session liquidity、T+1、rebalance 与 tie policy 均保持冻结。

9/24 parity 已通过。9/30 readiness：H10 **13,589 /127**、H40 **12,733 /119**、H120 **12,947 /121**
observations /unique dates，各 107 sectors；这是输入认证，不是历史账户收益或 Formal Signal。

## 证据与已知限制

- SOURCE_LICENSING_UNRESOLVED：软件许可不是行情再分发许可，raw market/runtime 数据不进入 Git。
- SWS：PASS_WITH_KNOWN_LIMITATION / OFFICIAL_L2_INDEX_CONSTITUENTS_NOT_MASTER_CLASSIFICATION_TABLE。
- 历史分类 publication PIT 未证明：**NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST**。
  历史 warmup 与当前 production execution PIT 分层；缺执行证据 fail closed 到 Cash。
- PIT coverage / liquidity 可能导致较高 Cash，包括 100% Cash，均为合法输出。
- CSI300 为 display benchmark；US benchmarks 仍 DEFERRED，无第三方 fallback 或虚构曲线。

独立 Shenwan Research 产品的 F1、official data、protocol/seals 保持原样；Validation / Final OOS performance 仍 SEALED。
ETF 控制台不执行或读取 Research performance。AGENTS.md 的历史默认限制适用于未授权工作；
Shadow 与标准 GitHub PR 同步来自明确用户授权。

## 验证

本轮最终结果见 release metadata 的 tests.current_closure，收尾时同步以下摘要；不伪造 CI badge。
既有 baseline：targeted128、API/security68、full ETF610 passed /1 skipped /0 failed。

```text
Docker: python -B -m pytest -q -p no:cacheprovider tests/etf_quant tests/test_etf_evidence_diagnostics.py tests/test_etf_proxy_mapping_policy.py
ETF API/security: node --test services/etf-quant-api/tests/*.test.mjs services/etf-quant-runner/tests/*.test.mjs
Research API: pnpm --dir services/research-api test:unit && pnpm --dir services/research-api typecheck
Frontend: pnpm --dir dashboard test --maxWorkers=1
Frontend: pnpm --dir dashboard typecheck && pnpm --dir dashboard lint && pnpm --dir dashboard build
```

没有明确真实 Development fixture 时，可选 artifact integration tests 保持既有 skip；不为验收读取 sealed performance。

## 开发者入口与安全同步

| 目录 | 职责 |
|---|---|
| services/etf-quant-runner | 唯一正式 one-shot、既有 transport |
| strategies/etf_quant | 冻结模型、PIT、执行、模拟账务 |
| services/etf-quant-api | 独立只读 current/runtime observer |
| services/research-api | 独立 Research API；sealed firewall |
| dashboard | 只读观察，无真实交易控制面 |
| tests | Python 认证；API/frontend 各有测试目录 |
| docs/etf_quant、reports/etf_quant | 合同、审计、小型 release metadata |

按 normal push → PR → default branch 同步；不 force、不绕过 protection/review、不删除历史 agent branches。
不提交凭证、.env、raw data、runtime DB/NAV/trades/logs 或大型事实数据。
见 [第三方声明](THIRD_PARTY_NOTICES.md) 与 [文档索引](docs/etf_quant/README.md)。
