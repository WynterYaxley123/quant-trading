# ETF-Quant V1 — Repo / Dashboard / Research-API 盘点（Inventory）

- 任务类型：READ-ONLY AUDIT + DOCS-ONLY（本文件为唯一产出之一）
- 基线 commit：`bd13d278b25eace66a7eae287307413f930effd9`
- 执行分支：`agent/mimo-etf-quant-inventory-v1`
- 执行 worktree：`D:\quant-worktrees\mimo-etf-inventory`
- 主 worktree（`D:\quant-trading`）全程只读，未做任何修改
- 本文所有结论均来自实际代码/文件核对，未读取任何 Validation performance / Final OOS 内容
- 状态：**INVENTORY ONLY**。不实现 ETF-Quant、不写 UI、不写 API、不动现有模块

背景（来自任务书，未从数据侧核验）：Shenwan F1 Research 冻结中；
Validation readiness = 23/60；Validation = SEALED / UNSEEN；Final OOS = SEALED。
ETF-Quant 为新产品线：SIMULATION_ONLY、无券商、无真实订单、初始资金 ¥10,000、
未来数据源 CNEquity、未来新增顶层 Dashboard 页面。

---

## 0. 一个重要的仓库事实（影响全部三项盘点）

**`services/research-api/` 与 `dashboard/` 不在基线分支上。**
基线 `bd13d27`（`experiment/sw-sector-index-research-baseline`）的 252 个 tracked 文件中
不含这两个目录；它们存在于本仓库的其它分支（各有独立 worktree）：

| 分支 | 内容 | worktree（已存在，本次只读） |
|------|------|------------------------------|
| `feature/research-api-v1` | `services/research-api/` | `D:/QuantForge/worktrees/research-api-v1` |
| `feature/research-dashboard-v1` | `dashboard/` | `D:/QuantForge/worktrees/research-dashboard-v1` |
| `integration/research-dashboard-v1` | `dashboard/` + `services/`（集成态） | `D:/QuantForge/worktrees/research-dashboard-integration` |

盘点时通过 `git show <branch>:<path>` / `git ls-tree` 只读读取这些分支的文件内容，
未切换分支、未改动任何 worktree。本文 Task B/C 的结论以
`integration/research-dashboard-v1`（dashboard）与 `feature/research-api-v1`（API）为准。

---

## 1. TASK A — Repo Inventory

### 1.1 基线 tracked 布局（252 个文件）

```
quant-trading/
├─ AGENTS.md / README.md               强制约束与项目总览
├─ docker-compose.yml / docker/        quant-research + quant-jupyter 两容器
├─ .devcontainer/ .vscode/ .dockerignore
├─ .env.example                        凭证模板（全部空值）
├─ .gitignore
├─ requirements.txt / pytest.ini
├─ docs/
│  ├─ architecture.md 等               架构、工作流、报告规范、未来集成规划
│  ├─ data/                            数据政策：market_data_policy、shenwan_* 准入/更新/TLS 等 11 篇
│  ├─ environment/                     环境验收
│  └─ research/                        Shenwan 研究协议/报告/handoff（约 40 篇）
├─ src/                                框架基础设施
│  ├─ data/                            providers / loaders / adapters / calendar / schema / certs
│  ├─ backtesting/                     回测 runner（hikyuu_runner 等）
│  ├─ notifications/                   飞书骨架
│  └─ strategies/                      第三方策略导入插槽（myquant 预留）
├─ strategies/sw_sector_rotation/      自包含策略包（src/config/tests/docs）
├─ research/                           Shenwan 研究协议与运行脚本 + configs/
├─ scripts/
│  ├─ data/                            Shenwan/ETF/Hikyuu 数据管线脚本（9 个）
│  ├─ automation/                      Hermes 侧 report_schema
│  └─ quant.py                         统一 CLI（backtest/strategies/frameworks）
├─ tests/                              框架/数据/研究协议测试
├─ reports/{backtests,comparisons,daily,factors,strategies}/.gitkeep
└─ notebooks/README.md
```

### 1.2 当前 repo 数据流（实际代码路径）

```
[外部数据源]
 申万官方文件（浏览器手动下载，免登录）      Hikyuu/KLine（pytdx 导入）      ETF 证据材料
        │                                        │                          │
        ▼                                        ▼                          ▼
data/raw/shenwan/{sector_catalog,             data/hikyuu/{stock.db,      data/raw/etf/
  sector_history,sector_history_append}         sh_day.h5,sz_day.h5}      data/raw/etf_evidence/
        │  scripts/data/import_shenwan_official.py /                        │  scripts/data/
        │  update_shenwan_official.py（append-only + 原子替换）               │  verify_etf_evidence.py
        ▼                                                                    ▼
data/staging/（更新暂存，原子替换）                     data/processed/shenwan_etf_mapping/
        │                                                                    │
        ▼                                                                    ▼
data/processed/shenwan/（canonical）                     data/processed/shenwan_snapshots/（哈希快照）
  sector_catalog.csv / sector_ohlcva.csv /                                data/manifests/（运行审计：
  stock_classification_canonical.csv / 质量报告                              update_manifest/result.json 等）
        │
        ▼
src/data/loaders/{panel_loader,shenwan_sector_loader}.py
src/data/{schema,calendar}.py + adapters/to_market_frame.py
（canonical frame；DataIntegrityError 严格校验；TradingCalendar 唯一日历）
        │
        ▼
research/*.py（协议 + run 脚本，读 research/configs/*.json）
        │
        ▼
reports/research/<run>/（正式研究产物：JSON/CSV artifacts，.gitignore 排除）
        │  （仅被读取）
        ▼
services/research-api（其它分支）──HTTP 只读──▶ dashboard（其它分支）
        │
        ▼
reports/backtests/（回测产物，.gitignore 排除；scripts/quant.py backtest → hikyuu_runner）
```

数据政策底线（`docs/data/market_data_policy.md`，已生效强制）：
未复权价格、停牌不补不插、涨跌停不建模（metadata 必须声明）、
统一 `src.data.calendar.TradingCalendar`、禁止静默填充、"宁可报错，不可静默伪造"。

### 1.3 Research 边界

| 边界要素 | 位置 | 状态 |
|----------|------|------|
| 研究协议/运行代码 | `research/*.py`（protocol/run/verify/guard 三件套风格） | Shenwan F1 线，冻结 |
| 研究配置 | `research/configs/`（含 `f1_independent_validation_v1{,_candidate,_split}.json`） | Candidate/Split/Phase 冻结 |
| 研究文档 | `docs/research/`（preregistration / run_report / selection_trace / handoff） | 只增不改 |
| 研究产物 | `reports/research/`（gitignored） | Validation / Final OOS SEALED |
| 数据资产 | `data/processed/`、`data/manifests/`、快照哈希 | canonical，append-only |
| 时点护栏 | `strategies/sw_sector_rotation/src/common/temporal_integrity.py`（13 项） | 明令不得修改 |

Research 的输出物是 **formal artifacts**（reports/research 下的 JSON/CSV），
是 Dashboard/API 的唯一事实来源（source of truth = RESEARCH_ARTIFACTS）。

### 1.4 Dashboard 边界

- 独立前端工程（`dashboard/`，仅存在于 dashboard/integration 分支），不进 Docker Python 环境
- **render-only**：不重算指标、不直接读 `reports/`、不触碰 Docker/Hikyuu/AKShare
- 所有数据经 `ResearchDataPort`（`src/api/contracts.ts`）唯一接缝进入；
  real-api（默认）/ mock-api（显式开启）双适配器
- mock 需 `VITE_DATA_MODE=mock` 显式指定，API 失联显示 "API disconnected"，**无静默回退**
- UI 明确不做：订单、执行、券商、账户、ETF、P&L（`docs/architecture.md` 第 6 节自述）

### 1.5 API 边界

- 独立 Node 服务（`services/research-api/`，仅存在于 research-api/integration 分支），
  不 import Python、不跑 Hikyuu/RQAlpha
- 唯一文件系统权限：`RESEARCH_REPORT_ROOT`（默认 `<repo>/reports/research`），永不写入
- `/api/v1/*` 只读：仅 GET/HEAD/OPTIONS，写方法一律 405
- Validation / Final OOS 由路由中间件 `SEALED` 守卫拦截（403 SEALED_PHASE）
- 默认 `127.0.0.1:8787`，CORS 精确白名单（拒绝 `*`）

### 1.6 未来可供 ETF-Quant 复用的模块

| 模块 | 复用方式 |
|------|----------|
| `src/data/` 骨架（providers/base、schema、calendar、loaders 模式） | CNEquity provider 作为新 provider 落位；沿用 canonical frame 与 `DataIntegrityError` 纪律 |
| 报告规范（`docs/report_schema.md` + `scripts/automation/report_schema/`） | ETF-Quant 回测/研究报告沿用同一 schema 纪律（null 不编造） |
| research-api 的**模式**（envelope、只读守卫、路径穿越防护、sha256 校验、sealed 守卫） | 未来 `services/etf-quant-api/` 照抄该安全模式 |
| dashboard 外壳（router/nav/ui/charts/tables/hooks/lib） | 新增 ETF Quant 页面组直接复用 |
| `strategies/` 自包含策略包约定（src/config/tests/docs 四件套） | 未来 `strategies/etf_quant_*` 包按同一约定 |
| 测试布局（tests/{data,framework,integration} + pytest.ini） | 新增 etf_quant 测试同构 |
| Docker 执行链路（quant-research 容器）与文档体系 | 完全复用，不改环境基线 |

### 1.7 必须隔离的模块

| 模块 | 隔离理由 |
|------|----------|
| `strategies/sw_sector_rotation/**` | Shenwan F1 冻结；temporal_integrity 等明令不得修改 |
| `research/**`（Shenwan 协议与 configs） | Candidate/Split/Phase 冻结；Validation SEALED |
| `docs/research/**` | 冻结的研究记录，只增不改 |
| `data/processed/**`、`data/manifests/**`、快照 | canonical Shenwan 数据，append-only + 准入制 |
| Validation protocol / readiness 管线 | SEALED/UNSEEN，禁止读取 performance |
| `reports/research/`（Shenwan 产物） | 只读事实来源，任何 ETF-Quant 不得写入 |
| `services/research-api/` v1 契约 | 其章程明确排除 portfolio/ETF/execution，不得为 ETF-Quant 扩权 |

---

## 2. TASK B — Dashboard Inventory

### 2.1 技术栈（`dashboard/package.json`）

| 层 | 选型 |
|----|------|
| 框架 | React 19.3 + TypeScript 6 + Vite 8.3 |
| 样式 | Tailwind CSS 4.3（@tailwindcss/vite）+ class-variance-authority / clsx / tailwind-merge |
| 路由 | TanStack Router 1.170（config-based，`createAppRouter(history?)` 工厂） |
| 表格 | TanStack Table 8.21 |
| 图表 | recharts 3.10 |
| UI 原语 | Radix（collapsible/dialog/slot/tooltip）+ lucide-react 图标 |
| 校验 | zod 4.6（运行时校验 API 响应） |
| 测试 | Vitest 5 + Testing Library + jsdom；ESLint 10 |
| 包名 | `shenwan-research-dashboard` v1.0.0（private，"read-only, non-executable"） |

### 2.2 Router / Nav / Pages

- 路由（`src/app/router.tsx`）：`rootRoute` + 6 个业务路由 + notFound：
  `/`（overview）、`/candidates`、`/development`、`/sectors`、`/diagnostics`、`/integrity`
- 导航（`src/app/nav.ts`）：`NAV_GROUPS` 4 组 —— 概览 / 研究（候选对比、Development 探索、行业探索）/ 诊断 / 研究完整性；
  每项可挂 `capability` 开关（`/capabilities` 返回值控制可见性，加载期 fail-open）
- nav.ts 头注释明言：**V1 只有研究分区，无 Portfolio/Orders/Trading/Execution/Account/Broker/ETF/P&L 入口**，
  未来分区只写在 docs，不在 UI 造假
- 页面（`src/features/<name>/`）：OverviewPage、CandidateComparisonPage、
  DevelopmentExplorerPage、SectorExplorerPage、DiagnosticsPage、ResearchIntegrityPage

### 2.3 Components 清单

| 组 | 文件 | 性质 |
|----|------|------|
| `components/ui/` | badge, button, card, collapsible, dialog, select, skeleton, states, table, tooltip | shadcn 风格通用原语 |
| `components/charts/` | ChartFrame（Tremor 组合式：标题+单位说明+图+无障碍文本摘要）、GroupedBarChart、TimeSeriesChart | 通用图表包装 |
| `components/tables/` | DataTable（TanStack Table 薄封装；null 永远排最后、数字列默认降序） | 通用表格 |
| `components/research/` | CandidateCard、FilterBar、HashText、MockDataBanner、PageHeader、ResearchStatusBanner、StatusBadges（含 SealedBadge）、StatusCard、UnitHint | 领域组件 |

状态卡片：`StatusCard`（label/value/hint 三段式）+ `StatusCardGrid`（1/2/3/5 列自适应网格）。

### 2.4 API client / contracts / refresh

- `src/api/client.ts`：`ResearchApiClient`，仅 GET、10s 超时（AbortController）、
  query 编码、解 `{schemaVersion,data|error}` envelope、zod 校验、类型化错误
- `src/api/contracts.ts`：SCHEMA_VERSION 1.0.0 冻结契约（zod schema + TS 类型）：
  Health、Capabilities、ResearchStatus、RunSummary/RunDetail、Candidate（D0–D3）、
  Metrics（horizon 10/40/120 + ic/rankIc/top5*）、DailyMetric、Prediction、Diagnostics、Integrity
- `Capabilities` 已预留 `portfolio` / `execution` / `etf` 布尔位（现全 false）；
  `ResearchStatus` 含 `etf` 字段
- 适配器：`adapters/real-api.ts`（默认）/ `adapters/mock-api.ts`（`VITE_DATA_MODE=mock` 显式）；
  `VITE_RESEARCH_API_BASE_URL`（默认 `http://127.0.0.1:8787/api/v1`）
- refresh 机制：`src/hooks/useResource.ts` —— 按 `deps` 变化自动重取 + `retry()` 手动重试 + 卸载即 abort；
  **无轮询**；explorer 状态存 URL search params（run/candidate/date/metric/horizon，刷新/前进后退可还原）
- 全局壳层数据：`AppDataProvider`（capabilities/status/runs 一次性并行拉取），
  页面级数据由各页面自行 `useResource`
- 无障碍/单位纪律：图表必带文本摘要、状态不单靠颜色、IC 无量纲/收益率百分比（`lib/format.ts`）

### 2.5 现有 Research 页面 → 数据映射

| 页面 | API 端点 |
|------|----------|
| Overview | `/research/status`、`/capabilities`、`/runs`、`/runs/:id/candidates`、`/runs/:id/integrity` |
| 候选对比 | `/runs/:id/candidates`、`.../metrics` |
| Development 探索 | `.../daily-metrics` |
| 行业探索 | `.../daily-metrics`、`/predictions?date=` |
| 诊断 | `.../diagnostics` |
| 研究完整性 | `/runs/:id`、`/runs/:id/integrity` |

### 2.6 未来 ETF Quant 页 —— 插入方案（仅 inventory，不实现）

**最合理 route**：新增路由组 `dashboard/src/routes/etf-quant/*`，业务页放
`dashboard/src/features/etf-quant/*`，URL 采用顶级段 `/etf-quant`（子页
`/etf-quant/portfolio`、`/etf-quant/holdings`、`/etf-quant/nav`、
`/etf-quant/rankings/10d|40d|120d|fusion`、`/etf-quant/factors`、
`/etf-quant/ridge`、`/etf-quant/mapping`、`/etf-quant/trades`、
`/etf-quant/benchmarks`、`/etf-quant/health`）。
顶级段而非塞进「研究」组：ETF-Quant 是新产品线（SIMULATION_ONLY 组合视角），
与 Shenwan 研究分区并列，避免污染冻结的 Research 语义。

**最合理导航位置**：`src/app/nav.ts` `NAV_GROUPS` 新增顶级 NavGroup「ETF Quant」
（置于「研究」组之后），挂**新的** capability 开关（建议新增 `etfQuant`，
不复用现有的 `etf` 位——该位属于 Shenwan 研究契约字段），
capabilities 由未来 ETF API 的 `/capabilities` 提供，未就绪时整组不显示（沿用 fail-open→尊重返回值的现行逻辑）。

**可复用组件**：

- `components/ui/*` 全部（button/card/badge/table/select/dialog/tooltip/skeleton/states…）
- `components/charts/*`：ChartFrame + TimeSeriesChart（NAV/收益曲线、基准叠加）、GroupedBarChart（排名对比）
- `components/tables/DataTable`（Holdings/Trades/Rankings/Factors/Ridge/Mapping 全部适用）
- `components/research/` 中的通用件：`StatusCard`/`StatusCardGrid`（Overview/System health）、`PageHeader`、`FilterBar`、`HashText`
- `hooks/useResource`（+ 可选加轮询版用于 System health，当前无轮询机制，属未来小扩展）
- `lib/`：format（单位纪律）、labels、cn、hash；`useTheme`
- 模式级复用：URL search params 状态、`createAppRouter` 工厂、AppDataProvider 形态（未来 `EtfQuantDataProvider`）、
  mock/real 双适配器 + zod contracts 的接缝设计

**不应复用的 Research-specific 组件/资产**：

- `CandidateCard`（D0–D3 候选语义）、`ResearchStatusBanner`（Shenwan 研究标注）、
  `StatusBadges.SealedBadge`（Validation 封存语义）、`UnitHint`（IC/行业预测单位说明）
- `src/api/contracts.ts`（Shenwan 冻结契约）、`mocks/fixtures.ts`（Shenwan 合成数据）
- Overview 等 6 个研究页面本体
- 未来 ETF Quant 需自建：`src/api/etf-quant/contracts.ts`（含 Portfolio/NAV/Trade 等 schema）、
  自己的 mock fixtures、SIMULATION_ONLY 水位条（复用 MockDataBanner 形态但独立实现）

**未来页面 → 组件映射（要求清单对照）**：

| 要求页面 | 主要复用件 | 需新建 |
|----------|-----------|--------|
| Overview | StatusCardGrid + PageHeader | etf-quant 状态字段 |
| Portfolio / Holdings | DataTable + StatusCard | 持仓/组合 schema |
| NAV / return curve | TimeSeriesChart + ChartFrame | NAV 序列 schema |
| 10d/40d/120d/Fusion ranking | DataTable（可加 GroupedBarChart） | 排名 schema |
| Factors / Ridge coefficients | DataTable | 因子/系数 schema |
| Industry→ETF mapping | DataTable | 映射 schema |
| Trades | DataTable | 成交 schema（SIMULATION） |
| Benchmarks | TimeSeriesChart + DataTable | 基准序列 schema |
| System health | StatusCardGrid + useResource | 健康端点 |

---

## 3. TASK C — Research API Inventory

### 3.1 位置与技术栈

- 路径：`services/research-api/`（分支 `feature/research-api-v1`）
- `@quant-trading/research-api` v1.0.0，Node >= 24，pnpm 11.25，TypeScript 5.9
- 运行时依赖仅 4 个：hono 4.13、@hono/node-server 2.0.12、csv-parse 6.1、zod 3.25
- 测试：vitest 4（unit + integration，integration 需真实 artifacts）

### 3.2 启动入口与 route

- 入口：`src/index.ts` —— `serve()`（@hono/node-server），在 HTTP 边界先跑
  `rawUrlGuardResponse`（在 Node/Hono 归一化点段之前检查原始 URL），再进 `createApp`
- 应用：`src/app.ts` —— `ROUTE_PATHS` 11 个只读端点：

```
/api/v1/health                /api/v1/capabilities        /api/v1/research/status
/api/v1/runs                  /api/v1/runs/:runId         /api/v1/runs/:runId/candidates
/api/v1/runs/:runId/candidates/:candidateId/metrics
/api/v1/runs/:runId/candidates/:candidateId/daily-metrics
/api/v1/runs/:runId/candidates/:candidateId/predictions
/api/v1/runs/:runId/candidates/:candidateId/diagnostics
/api/v1/runs/:runId/integrity
```

### 3.3 schema

- `src/protocol.ts`（envelope + SCHEMA_VERSION 1.0.0）
- `src/schemas/artifacts.ts`、`src/schemas/csv.ts`（zod 校验 artifacts）
- `src/adapters/normalize.ts`（artifact → API 视图；不重算 IC/收益/排名/晋升，
  唯一聚合是训练诊断的 min/median/max 与计数）
- 契约文档：`docs/api-contract.md`；机器契约：`openapi/research-dashboard-api-v1.openapi.yaml`（OpenAPI 3.1）
- 响应：成功 `{schemaVersion,data}` / 错误 `{schemaVersion,error{code,message}}`，无时间戳/随机字段

### 3.4 文件/数据来源

- `RESEARCH_REPORT_ROOT`（env，默认 `<repo>/reports/research`）是**唯一**文件系统权限
- 目录只收录 `iteration1_*` 命名、DEVELOPMENT 元数据校验通过、D0–D3 家族的正式 run；
  legacy baseline 输出被刻意排除
- 只读取 `reports/research` 下的正式 JSON/CSV artifacts，永不写入

### 3.5 read-only 机制（多层）

1. 方法层：`/api/v1/*` 仅 GET/HEAD/OPTIONS，其余 405「Research API is read-only」
2. 封存层：`SEALED` 正则守卫拦截路径/查询值中的 validation/final_oos/oos 字样 → 403 SEALED_PHASE
3. 路径层：原始 URL 拒绝编码分隔符/反斜杠/点段（PATH_TRAVERSAL_BLOCKED）；
   `assertSafeSegment` 拒绝空段/点段/绝对路径/百分号编码；
   `realpath` 双重包含校验（防 symlink 逃逸）
4. 内容层：读文件前比对 `metadata.content_sha256`，不符即拒；v1 无缓存，每请求读当前字节
5. 标识层：run/candidate ID 封闭格式白名单
6. 网络层：默认 `127.0.0.1:8787`；CORS 精确 origin 白名单（`DASHBOARD_ORIGINS`，拒绝 `*`）
7. 错误层：稳定错误码，客户端不获知绝对文件系统路径（服务端留上下文日志）

### 3.6 Dashboard 调用方式

- `ResearchApiClient.get(path, zodSchema, query, signal)` → `http://127.0.0.1:8787/api/v1/...`
- base URL 来自 `VITE_RESEARCH_API_BASE_URL`（dashboard/.env.example）
- 契约双端各持一份 zod（API 端 protocol/schemas，UI 端 contracts.ts），以 OpenAPI 为规范源

### 3.7 未来 ETF Quant namespace 判断

**推荐：`/api/etf-quant/v1/...`，由独立新服务承载（如 `services/etf-quant-api/`），不塞进 research-api v1。**

理由（均来自现有契约文本）：

1. research-api 的章程明确写着它"不暴露 Validation/OOS、组合、ETF 或执行"——
   ETF-Quant 的 Portfolio/Trades/NAV 恰好是被该章程排除的能力，扩权等于破坏其冻结契约
2. 其 SEALED 守卫、目录白名单（只认 `iteration1_*` DEVELOPMENT run）都是 Shenwan 研究专用语义，
   对 ETF-Quant 是错误约束
3. 数据源不同：research-api 根锚定 `reports/research`；ETF-Quant 需要组合状态/NAV/成交/排名等新根
4. 现有安全模式（envelope、只读、路径守卫、哈希校验、精确 CORS）**整体照抄**即可，成本低

次选（若未来一定要单进程）：同一 Hono app 下加独立路由模块 `/api/etf-quant/*` + 独立 middleware 作用域，
但需显式重写其 charter 文档，且冻结面扩大 —— 不推荐。

Dashboard 侧对应：新增 `src/api/etf-quant/`（contracts + client/adapter），
与 `ResearchDataPort` 并列的 `EtfQuantDataPort`，互不引用。

---

## 4. README 未来应增补的小节（建议，本轮不改 README）

1. **ETF-Quant 产品线**：SIMULATION_ONLY、初始资金 ¥10,000、无券商/无真实订单、
   未来 CNEquity 数据源、与 Shenwan 研究线的隔离关系
2. **Dashboard — ETF Quant 页面**：顶级分区、capability 门控、页面清单
3. **API — `/api/etf-quant/v1`**：独立只读服务定位（或明确其未来读写的 SIMULATION 边界）
4. **公开发布安全基线**：链接 `docs/etf_quant/etf_quant_public_github_security_baseline_v1.md`
   与发布前 gates
5. **远程仓库状态勘误**：README 现称"没有配置任何远程仓库"，实际 `origin` 已存在且有已推送引用
   （见安全基线文档）——发布前必须先对齐表述
