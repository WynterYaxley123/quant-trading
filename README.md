# Quant Trading / ETF-Quant

面向中国 A 股行业与 ETF 的研究平台，集成可复核的因子研究、冻结的 ETF-Quant V1 向前 Shadow 模拟，以及一个连接两套只读 API 的本地 Dashboard。

**SIMULATION_ONLY · NO_BROKER · NO_REAL_ORDER_PATH · NO_LEVERAGE · NO_SHORT**

[启动控制台](#quick-start) · [架构](#architecture) · [策略规格](#etf-quant-v1-strategy) · [文档](#documentation)

## Overview

Quant Trading 将研究、运行和观察分开：研究层保存获准的 Development 产物；ETF-Quant V1 在真实、已 finalized 的数据上运行向前模拟；Dashboard 通过只读 API 展示两者，不发起训练、刷新数据或执行交易。

项目关注数据可用时间、模型标签成熟度、ETF 映射证据与模拟账务的可追溯性。代码、配置、测试和安全元数据保存在 Git 中，行情、研究产物和运行状态由仓外环境管理。克隆代码不会自动取得市场数据或创建模拟账户。

| 层 | 职责 | 边界 |
| --- | --- | --- |
| Research | 申万行业指数预测研究与 Development 候选对比 | Validation / Final OOS 封存，不可交易 |
| ETF-Quant V1 | 冻结模型、行业排名、ETF 映射、forward Shadow | 内部模拟，无券商连接 |
| Operations console | 一个 Dashboard、ETF Quant API、Research API | 只读，不启动 runner |
| External runtime | 数据入口、immutable exports、PIT 证据、模拟状态 | 仓外保存，不纳入 Git |

V1 的量化语义已冻结；运行是否就绪、数据截止日、下一合法交易日和正式 Shadow 状态，以控制台实时读取的证据为准。[验收记录](reports/etf_quant/etf_quant_v1_final_release_v1.json)是带日期的工程快照，不是永久运行状态或收益证明。

## Key Capabilities

- **行业因子研究**：19 因子体系、独立的 H10 / H40 / H120 Ridge 模型，以及获准的 Development 候选分析。
- **ETF 执行映射**：行业排名通过 Strict / Proxy / Cash 政策映射到符合证据与流动性要求的 ETF。
- **PIT 与成熟度门控**：验证数据、分类与映射证据的可用时间，不将历史研究分类宣称为严格历史 PIT。
- **Forward Shadow**：T finalized close 形成正式信号与 T+1 模拟意图，真实 finalized T+1 open 到达后才处理模拟成交账务。
- **统一观察界面**：ETF 总览、准备状态、持仓、排名、模型、映射、成交、基准、健康，以及 Research 六个页面。
- **可复核工程**：确定性 runner、产物哈希、独立 API DTO 校验、冻结镜像测试和仓库安全审计。

## Architecture

~~~mermaid
flowchart TD
    M["外部事实行情 / pinned CNEquity"] --> P["immutable exports / Source-C / Candidate / PIT"]
    P --> R["获准的行业指数 Research 工作流"]
    P --> Q["ETF-Quant V1 冻结因子与模型"]
    R --> A["Development Research artifacts"]
    A --> RA["Research API · GET /api/v1"]
    Q --> K["行业排名 → Strict / Proxy / Cash → 权重"]
    K --> S["Forward Shadow runtime · T / T+1"]
    S --> EA["ETF Quant API · GET /api/etf-quant/v1"]
    RA --> D["统一 Dashboard · 只读"]
    EA --> D
    C["PowerShell console launcher"] -. "启动与健康检查" .-> RA
    C -. "启动与健康检查" .-> EA
    C -. "启动与健康检查" .-> D
~~~

Research API 读取研究产物；ETF Quant API 验证仓外运行快照和 control 元数据。两个服务保持独立的数据合同，共用一个观察界面。启动器只管理这三个进程，不调用量化计算链路。浏览器直接请求 loopback API，不使用 Vite proxy。API 地址集中配置，production build 使用构建时的 Vite 环境变量。

Python 量化执行使用冻结 Docker 镜像。既有宿主机 sidecar 只承担 transport / metadata 入口，正式模型与账务在 Docker 内执行。Hikyuu 是主研究框架，RQAlpha 用于独立验证。

## ETF-Quant V1 Strategy

ETF-Quant V1 是 **industry-first** 的 A 股行业 / 主题 ETF 模拟策略，标识为 `ETF_QUANT_V1`，初始预算为 CNY 10,000，冻结范围为 107 admitted industries。

| 项目 | 冻结合同 |
| --- | --- |
| 输入 | Source-C 内部等权 constituent-return series，不是官方行业指数 |
| 因子 | 19 因子注册表；H10 使用 d10、p5、align、vc、dd20；H40 / H120 使用冻结的全部 19 因子 |
| 模型 | 各期限独立 Ridge，alpha = 0.01，raw X |
| 训练 | 各期限成熟标签截止日前六个日历月；至少 30 个有效训练日期；完整行业截面 |
| 融合 | 各期限横截面 population z-score，权重 0.25 / 0.50 / 0.25，冻结排名与并列规则 |
| 选择与映射 | Top5 行业；Strict > Proxy > Cash；B40 Proxy 要求目标 L2 暴露至少 40%，且目标为最大暴露 |
| 流动性 | 20 个交易日流动性门控；不以当前可交易性推断历史可交易性 |
| 权重 | 冻结 softmax；单 ETF 目标权重上限 35%；不可执行 slot 保留原权重为 Cash |
| 重平衡 | 可执行成员集合 / 可执行性变化时重平衡，不下扫替换 Top5 |
| 时序 | T finalized close 信号 → T+1 模拟意图 → 实际 finalized T+1 open → 延迟账务 |
| 可交易性 | ETF_BAR_DERIVED_TRADABILITY_V1 |
| 成本 | 单边佣金 3 bps、滑点 5 bps；印花税和最低佣金为 0 |
| 基准 | CSI 300 仅展示，不进入模型；美股基准暂缓 |

缺少映射、PIT 或执行证据时保留 Cash，可能得到 100% Cash。预算不等于已存在的账户资产：正式账务尚未开始时，资产、持仓、NAV 和 PnL 保持 null / 空。

完整规则见[冻结模型对账](docs/etf_quant/codex_frozen_model_contract_reconciliation_v1.md)、[Proxy / Cash 政策](docs/etf_quant/proxy_execution_policy_v1.md)和[T+1 合同](docs/etf_quant/t1_execution_contract_final_v1.md)。

## Research Layer

Research 是独立的申万行业指数预测研究。获准的 Iteration-1 Development 使用固定 124 行业研究宇宙与 D0–D3 候选；它与 ETF V1 的 107 行业生产准入合同各有用途，不可混用。

| 数据阶段 | 用途 | Dashboard / API 权限 |
| --- | --- | --- |
| Development | 候选比较、预测、诊断与研究完整性 | 只读获准产物 |
| Validation | 独立验证阶段 | SEALED，不提供性能预览或解封入口 |
| Final OOS | 最终样本外评价 | SEALED，不读取或返回性能 |

Research API 校验元数据、schema、内容哈希和路径 containment。它不修改 F1、训练模型、运行研究、更新行情或写入 Shadow。IC、RankIC、forward labels 与 spread 是预测研究指标，不是 ETF 账户收益。

Research 产物是可选输入。没有获准产物时，服务正常运行，界面显示 **Research API 已连接 / 未配置获准的 Development 研究产物**。连接失败、损坏产物和哈希错误仍显示相应错误，不切换到 mock 或填入虚构数据。

## Shadow Trading

Shadow 是基于真实 finalized 数据的向前内部模拟，不是券商 paper account、历史回填或真实资金交易。

首次合法 T 在信号决策时创建 Formal Shadow Epoch，并绑定 Candidate、代码和 PIT / Strict 证据。T+1 open 未 finalized 时没有模拟 fill；不会先读取开盘价，再倒补 T 日意图。历史 warmup、工程排名与 model-readiness reference 不构成历史 Shadow 信号或账户业绩。

只读控制台不会创建 Epoch、Signal、Intent、Fill 或 NAV。正式 one-shot 由操作人员使用独立命令运行，没有常驻交易 daemon 或自动调度器。

## Safety Boundaries

- **NO BROKER / NO REAL ORDER PATH**：无券商账号、真实订单提交或真实账户状态读取路径。
- **NO LEVERAGE / NO SHORTING**：冻结 V1 不支持杠杆与做空。
- **NO HISTORICAL SHADOW BACKFILL**：不补造过去的 Epoch、信号、意图、成交或 NAV。
- **SEALED VALIDATION / FINAL OOS**：API 与控制台不开放封存性能。
- **READ-ONLY DASHBOARD**：不能训练、刷新市场数据、触发 one-shot 或编辑模拟状态。
- **FAIL CLOSED**：缺少执行证据保留 Cash；完整性失败保留真实阻断状态。

## System Components

| 路径 | 职责 |
| --- | --- |
| [services/etf-quant-api](services/etf-quant-api/README.md) | 无外部依赖的 Node 只读 runtime / current observer |
| [services/research-api](services/research-api/README.md) | Hono / TypeScript Development artifact adapter |
| [services/etf-quant-runner](services/etf-quant-runner/README.md) | 正式 one-shot transport 与冻结门控 |
| [dashboard](dashboard/README.md) | React / TypeScript / Vite 统一只读界面 |
| [strategies](strategies/README.md) | 自包含策略包，ETF V1 与既有研究包 |
| [research](research) | 研究协议、数据阶段与非执行研究逻辑 |
| [src](src/README.md) | 框架基础设施与既有数据入口 |
| [tests](tests) | Python 环境、框架、策略与证据测试 |
| [scripts](scripts) | 控制台启动、诊断与明确授权的数据工具 |

## Quick Start

### Portable contributor start

首次贡献无需生产行情或仓外 runtime。默认 `.devcontainer` 提供独立的
Python 3.12.11 / Node 24.19.0 / pnpm 11.25.0 开发环境；完整依赖固定在
`requirements-dev.lock.txt`，不修改冻结生产镜像。容器内从仓库根目录执行：

~~~sh
ruff check .
ruff format --check .
python scripts/engineering/typecheck.py
python -m pytest -m "not external_runtime"
python -m examples.minimal_demo
~~~

示例标记为 **SYNTHETIC DEMO ONLY**，复用既有 Ridge、成熟度、融合、排名与
权重函数；不需要真实数据，不产生账户或交易记录。Mypy 使用明确的遗留问题
清单与严格新代码检查；通过 staged gate 不表示历史类型问题已经全部清零。
安装与 Git hooks 见[贡献指南](CONTRIBUTING.md)，运行环境配置见[工程指南](docs/engineering/README.md)。

### Requirements

使用已验收的 Windows / PowerShell 环境：

- Node.js 24+、pnpm 11.25，以及与各组件 lockfile 对应的既有依赖。
- 冻结 Docker 镜像 `quant-research:py3.12`；控制台不安装或升级镜像与依赖。
- 仓外 ETF runtime、control 配置、immutable exports、PIT 证据与 pinned CNEquity。
- 可选的获准 Development 研究产物。

`D:/QuantForge` 路径是既有本地部署示例。克隆后需要配置自己的外部运行环境，仓库不分发行情或账户状态。参阅[启动说明](docs/unified_console.md)和[runner 配置模板](services/etf-quant-runner/one_shot.config.example.json)。

### Start the read-only console

在 checkout 根目录运行：

~~~powershell
& ./scripts/Start-EtfQuantConsole.ps1
~~~

启动器根据脚本位置定位仓库，管理三个后台服务，进行有限超时健康检查：

| 服务 | 地址 |
| --- | --- |
| Dashboard | [http://127.0.0.1:5173/etf-quant/overview](http://127.0.0.1:5173/etf-quant/overview) |
| ETF Quant API | [http://127.0.0.1:3312/api/etf-quant/v1/current](http://127.0.0.1:3312/api/etf-quant/v1/current) |
| Research API | [http://127.0.0.1:8787/api/v1/health](http://127.0.0.1:8787/api/v1/health) |

不需要三个终端。健康的同 checkout / 同配置服务会被安全复用；不属于该实例的端口冲突会明确报错，不终止任意 Python / Node 进程。日志与进程身份记录在仓外 control root 的 `console-logs/`。

配置过的机器会自动连接本机获准的 Development 工作区，核验批准清单、阶段、metadata 与内容 Hash，并提供只读运行选择。Validation / Final OOS 始终封存，不重新生成历史研究结果。其他机器没有获准产物时仍正常启动，Research 明确显示 `NOT_CONFIGURED`。不要指向任意研究目录；显式覆盖也必须通过批准和完整性校验。配置与优先级见[Research 工作区指南](docs/research_workspace.md)。

**启动控制台 ≠ 执行 Shadow cycle。** 启动过程不刷新行情、不训练模型、不运行 one-shot。

### Run one authorized Shadow cycle

正式操作使用既有 runtime checkout 与原分支门禁。当前部署的官方入口是：

~~~powershell
& D:/QuantForge/external/cnequity-etf-quant-v1/venv/Scripts/python.exe `
  -B D:/quant-worktrees/etf-quant-v1-shadow-autonomous-final/services/etf-quant-runner/one_shot.py `
  --config D:/QuantForge/runtime/etf-quant-v1/autonomous-control-v1/config.json
~~~

这是既有隔离 transport 解释器，不是 Windows 全局量化 Python；正式量化执行交给 Docker。正式 checkout 必须 committed、clean，保留 `integration/etf-quant-v1-shadow-autonomous-final` 分支名。控制台更改不改变 runner 门禁。

命令会按照日历与证据推进合法的新周期。不要将新 eligible finalized T 当作工程 smoke test 消耗。完整前置条件见[runner 说明](services/etf-quant-runner/README.md)。

## Operational Workflow

1. 外部数据环境向前更新事实数据，提交完整 immutable finalized snapshot。
2. readiness 验证冻结输入、训练成熟度、数据覆盖、Candidate 与证据完整性。
3. 独立 H10 / H40 / H120 模型形成分数，经横截面标准化与融合得到行业排名。
4. Strict / Proxy / Cash 与流动性门控形成目标权重。
5. 合法 T 生成正式信号和 T+1 模拟意图，重复运行保持幂等。
6. finalized T+1 open 到达后处理模拟账务，API 和 Dashboard 只读观察结果。

| 常见状态 | 含义 |
| --- | --- |
| READY_NO_SIGNAL | 非交易日，正常等待 |
| ARMED_FOR_NEXT_ELIGIBLE_T | 已武装，等待下一合法 finalized T |
| WAITING_FOR_MARKET_CLOSE / WAITING_FOR_FINALIZED_DATA | 当日条件尚未满足 |
| WAITING_FOR_PROVIDER_DATA | 有界重试后供应端暂不可用 |
| STARTED / AWAITING_T1_OPEN | 正式信号已存在，等待真实 T+1 open |
| SHADOW_CASH_ONLY | 合法的全 Cash 结果 |
| ALREADY_PROCESSED | 当日正式事件已处理，保持幂等 |
| BLOCKED_* | 工程或完整性门控，需要检查证据 |

## Testing

测试使用既有依赖和隔离夹具。真实 Development integration 只在显式配置获准 root / API 时运行，不为测试读取 Validation 或 Final OOS。

~~~powershell
pnpm --dir dashboard test --maxWorkers=1
pnpm --dir dashboard typecheck
pnpm --dir dashboard lint
pnpm --dir dashboard build

pnpm --dir services/research-api test
pnpm --dir services/research-api typecheck
pnpm --dir services/research-api build

node --test services/etf-quant-api/tests/*.test.mjs services/etf-quant-runner/security-audit.test.mjs
node --test scripts/tests/console.test.mjs
node services/etf-quant-runner/security-audit.mjs
~~~

完整 ETF 测试在冻结镜像内运行。以下为已部署路径的只读外部夹具约定；替换源码路径时保留挂载与隔离选项：

~~~powershell
& "C:/Program Files/Docker/Docker/resources/bin/docker.exe" run --rm --network none `
  --env PYTHONDONTWRITEBYTECODE=1 `
  --env ETF_QUANT_EXTERNAL_RUNTIME_ROOT=/external-runtime `
  --mount "type=bind,source=D:/quant-worktrees/unified-research-console-readme-final,target=/workspace,readonly" `
  --mount "type=bind,source=D:/QuantForge/runtime/etf-quant-v1,target=/external-runtime,readonly" `
  --workdir /workspace `
  sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5 `
  python -B -m pytest -q -p no:cacheprovider tests/etf_quant `
  tests/test_etf_evidence_diagnostics.py tests/test_etf_proxy_mapping_policy.py
~~~

测试数量随工程演进，不作为永久能力声明。具体结果保存在[验收报告](docs/unified_console_acceptance_20261002.md)，历史记录保持原样。

## Repository Structure

~~~text
quant-trading/
├── dashboard/                 React 界面与组件测试
├── services/
│   ├── etf-quant-api/          ETF current / runtime observer
│   ├── research-api/           Development artifact adapter
│   ├── etf-quant-runner/        正式 one-shot transport
│   └── cnequity-sidecar/        pinned 数据 transport 合同
├── strategies/
│   ├── etf_quant/              冻结 ETF V1 自包含包
│   └── sw_sector_rotation/     既有行业研究包
├── research/                  研究协议与非执行研究逻辑
├── src/                       框架基础设施
├── tests/                     Python 测试与证据验证
├── scripts/                   控制台启动与受控工具
├── docs/                      合同、操作文档与审计索引
└── reports/etf_quant/          安全元数据与工程报告
~~~

## Data & Runtime Separation

Git 保存源码、锁定配置、文档、测试和审查过的安全元数据。原始行情、curated bars、研究运行产物、runtime DB、Shadow account payloads、NAV / trades 历史、日志、凭证和 `.env` 不进入 Git。

外部 CNEquity checkout 与科学计算环境按既有 pin 使用，不由前端或 API 更新。研究服务宿主端口保持 `127.0.0.1:19200 → 9200` 和 `127.0.0.1:19201 → 9201`；控制台不修改 Docker、WSL 或系统网络。

## Security

三个控制台服务只绑定 loopback。API 提供 GET / HEAD / OPTIONS，拒绝写方法；CORS 使用明确的本地 origin。原始 URL、标识符、文件 realpath、schema 和内容哈希在各自 API 边界校验。

生产控制台使用真实 API 模式。Mock 是显式选择的开发 / 测试适配器，界面标记合成数据；连接失败不会切换到 mock。浏览器看不到私有模拟状态、宿主凭证或真实金融账户信息。见[Research API 安全合同](services/research-api/docs/api-contract.md)。

## Known Limitations

- 历史固定研究分类的 publication PIT 未证明；warmup 不能描述为严格历史 classification PIT 业绩。
- 生产 SWS 证据来自官方 L2 指数成分，不是完整 master classification table。
- 行情许可和再分发权需要按来源条款单独审查。
- Shadow 依据 finalized 日频事实数据，不是实时行情或券商撮合环境。
- 外部数据、control / runtime 与冻结依赖必须已存在，仓库不提供自动下载式数据 quick start。
- 零 Epoch 和高 Cash 都可能合法，不伪造持仓或基准曲线。
- CSI 300 是 V1 唯一展示基准；NASDAQ / S&P 500 暂缓。
- V1 无实盘、通知推送、浏览器研究执行或封存集解封功能；新增能力需独立授权。

## Documentation

- [活跃文档入口](docs/README.md) · [历史审计逻辑归档](docs/archive/README.md)
- [贡献与质量检查](CONTRIBUTING.md) · [合成示例](examples/minimal_demo/README.md)

- [统一控制台操作说明](docs/unified_console.md)
- [ETF V1 合同与历史审计索引](docs/etf_quant/README.md)
- [冻结模型对账](docs/etf_quant/codex_frozen_model_contract_reconciliation_v1.md)
- [数据时间语义](docs/etf_quant/production_time_semantics_v1.md)
- [PIT 证据注册表](docs/etf_quant/production_pit_evidence_registry_v1.md)
- [行业 / ETF 映射合同](docs/etf_quant/industry_etf_mapping_contract_v1.md)
- [Shadow 准备门控](docs/etf_quant/shadow_start_readiness_final_v1.md)
- [Research API / OpenAPI](services/research-api/README.md)
- [Dashboard](dashboard/README.md)
- [环境与依赖记录](docs/dependency_conflicts.md)

工程修改需保持 V1 策略冻结、封存数据隔离与仓外数据边界。使用隔离 checkout、对应质量检查和正常 PR 工作流，不改写历史审计证据或强制推送。

## License / Data Rights

仓库自有代码和文档采用 [MIT License](LICENSE)。第三方版权和许可声明继续保留，根目录 MIT 授权不改变第三方条款。

第三方组件保留各自许可证，参见[第三方声明](THIRD_PARTY_NOTICES.md)和[Dashboard notices](dashboard/THIRD_PARTY_NOTICES.md)。市场数据权利与软件许可分开，数据再分发 clearance 保持 **REVIEW_REQUIRED**；本仓库不宣称来源数据的再分发权。
