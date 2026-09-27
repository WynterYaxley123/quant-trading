# ETF-Quant V1 — 公开 GitHub 安全基线审计（Public GitHub Security Baseline）

- 任务类型：READ-ONLY AUDIT + DOCS-ONLY（本文件为唯一产出之一）
- 基线 commit：`bd13d278b25eace66a7eae287307413f930effd9`
- 执行分支：`agent/mimo-etf-quant-inventory-v1`
- 执行 worktree：`D:\quant-worktrees\mimo-etf-inventory`
- 审计对象：全部 tracked 文件（基线 + 3 个服务分支）、主 worktree 未跟踪本地状态、
  全部 Git history（104 commits，含所有分支）、`origin` 远程状态、`.gitignore` 覆盖面
- 纪律：**全文不出现任何真实 secret 值**；命中一律以 `***REDACTED***` 呈现；
  未改写 history、未 reset/rebase/filter-repo、未改 `.gitignore`、未 push

---

## 1. 结论摘要

| 项 | 结果 |
|----|------|
| tracked 真实 secret | **0 个** |
| Git history 中的秘密/凭证 | **0 个**（.env 从未入库；无私钥、无 token、无大文件数据） |
| 未跟踪本地敏感文件 | `.env`（凭证键全空，已被 ignore）、`data/` 运行时数据（已被 ignore） |
| 远程状态 | **`origin` 已存在且有已推送引用** —— 与 README/AGENTS"未配置远程"表述不符（唯一的红色流程发现） |
| `.gitignore` 当前覆盖 | 生效且正确；对未来 ETF-Quant 运行时数据存在 4 类缺口（仅建议，本轮不改） |
| 总体 | **当前内容层面可公开**；发布前须完成第 7 节 gates，并先解决远程表述/历史同步决策 |

---

## 2. tracked 文件扫描（基线 + feature/research-api-v1 + feature/research-dashboard-v1 + integration/research-dashboard-v1）

### 2.1 敏感文件名模式（.env* / *.pem / *.p12 / *.pfx / *.key / *secret* / *credential* / id_rsa 等）

| path | 类型 | 判定 |
|------|------|------|
| `.env.example` | 凭证模板 | ✅ 安全：BROKER_ACCOUNT / BROKER_PASSWORD / API_TOKEN / MYQUANT_TOKEN / TUSHARE_TOKEN / JUPYTER_PASSWORD / FEISHU_WEBHOOK / FEISHU_APP_ID / FEISHU_APP_SECRET 全部为空值模板，文件头自带"禁止填真实值"警告 |
| `dashboard/.env.example`（分支） | 模板 | ✅ 安全：仅 `VITE_DATA_MODE`、`VITE_RESEARCH_API_BASE_URL` 两个非敏感配置 |
| `services/research-api/.env.example`（分支） | 模板 | ✅ 安全：RESEARCH_REPORT_ROOT / HOST / PORT / DASHBOARD_ORIGINS，无凭证 |
| `src/data/certs/geotrust_g2_tls_cn_2022.pem` | TLS 证书 | ✅ 安全：`-----BEGIN CERTIFICATE-----` 公开中间 CA 证书（GeoTrust G2 TLS CN），**非私钥**；配套 `.json` 仅含该公开证书的 sha256/subject/issuer/serial 元数据与验证记录（"Public intermediate, NOT a new root"） |

其余分支无任何 pem/p12/pfx/key/id_rsa 类文件。全部 4 个 ref 上均无 `.github/` CI 工作流。

### 2.2 内容模式扫描（关键字命中 → 逐一分类）

扫描命令只输出文件名与打码行。命中文件 41 个，逐类归因：

| 命中类 | 代表 path | 命中原因 | 判定 |
|--------|-----------|----------|------|
| 文档叙述 | `docs/data/shenwan_data_access.md`、`docs/research/handoff_*`、`docs/feishu_integration.md` 等 | 散文提及 Cookie/UA/密码/webhook 概念（TLS 诊断、飞书规划） | ✅ 无值 |
| 配置模板/声明 | `AGENTS.md`、`README.md`、`.env.example`、`docker-compose.yml` | 键名、空值模板、"不配置任何真实账号"声明 | ✅ 无值 |
| 代码标识符 | `research/factor_set_v2_protocol.py:251` | `BANNED_SIGN_KEYS = ***REDACTED***({"sign", ...})` —— frozenset 的键名字面量集合（符号操纵禁用名单） | ✅ 误报 |
| 代码引用 env 名 | `src/notifications/feishu.py`、`src/data/providers/shenwan_official_update.py`、`research/*.py`、`tests/*.py` | 读取 `FEISHU_*` / `*_TOKEN` 等环境变量名，不落值 | ✅ 无值 |
| npm 锁文件（分支） | `dashboard/package-lock.json` | 依赖包名 `cookie-es`、`tough-cookie` | ✅ 噪声 |
| 机器环境记录 | `docs/windows_chatgpt_environment.md:22-31` | 记录宿主机 `C:\Users\<user>\.codex\config.toml` 的 `sandbox_mode`（权限配置，非凭证） | ✅ 无值 |

赋值型模式专项（`KEY|TOKEN|SECRET|PASSWORD... = <8+字符值>`）：全 tracked 内容仅 1 处命中，即上表 frozenset，**无任何真实赋值**。
`Bearer <token>` 与 `-----BEGIN ... PRIVATE KEY` 专项：**0 命中**（含全 history 补丁扫描）。

### 2.3 tracked secret candidates 汇总

```
tracked secret candidates = NONE
仅存的"敏感文件名"命中均为：空值模板（.env.example ×3）+ 公开 CA 证书（.pem/.json）
```

---

## 3. 主 worktree 未跟踪本地状态（只读检查，`D:\quant-trading`）

| path | 内容 | 状态 |
|------|------|------|
| `.env` | 键名与模板一致。**非空值仅**：`ENV=***REDACTED***`、`LOG_LEVEL=***REDACTED***`、`TIMEZONE=***REDACTED***`、`JUPYTER_PORT=***REDACTED***`、`JUPYTER_PASSWORD=***REDACTED***`（argon2 哈希，README 设计如此）；**凭证键全部为空**：BROKER_ACCOUNT / BROKER_PASSWORD / API_TOKEN / MYQUANT_TOKEN / TUSHARE_TOKEN = 空 | ✅ 被 `.gitignore:17` 忽略；从未 tracked |
| `secrets/` | 仅 `README.md`（说明文件），无任何凭证文件 | ✅ 被 `/secrets/` 忽略 |
| `logs/` | 仅 `README.md` | ✅ 被 `/logs/` 忽略 |
| `data/` | 1128 个文件：`hikyuu/{stock.db,sh_day.h5,sz_day.h5}`（Hikyuu 运行时库+行情）、`raw/`、`staging/`、`processed/`（canonical CSV/JSON）、`manifests/`（运行审计 JSON） | ✅ 被 `/data/` 忽略；全部为研究数据，无账户/凭证内容 |

`.env` 中 `DISABLE_LIVE_TRADING` 非空（即安全开关已设置；值未打印）。

---

## 4. Git History 审计（104 commits，全分支）

| 检查 | 结果 |
|------|------|
| `.env`（真实值版本）是否曾入库 | ❌ 从未（`git log --all -- .env` 为空；仅 `.env.example` 模板有提交史） |
| 私钥（BEGIN ... PRIVATE KEY）曾出现在补丁 | ❌ 0 处 |
| Bearer/token 型值曾出现在补丁 | ❌ 0 处 |
| `KEY|TOKEN|SECRET|PASSWORD = <值>` 赋值曾出现在补丁 | ❌ 0 处 |
| 敏感文件名曾被 add 的完整清单 | 仅 `.env.example`、`dashboard/.env.example`、`services/research-api/.env.example`、`src/data/certs/geotrust_g2_tls_cn_2022.pem`（公开证书） |
| 大体积 blob（>500KB，raw data / runtime DB 特征） | ❌ 0 个 —— 历史上从未提交过原始数据或运行时数据库 |
| `secrets/` 目录曾入库 | ❌ 从未 |
| runtime DB（*.db/*.sqlite/*.h5）曾入库 | ❌ 从未（现有 stock.db 等仅存在于被忽略的 `data/`） |

**未做**（按禁令）：history 改写、filter-repo、BFG、reset、rebase。本轮只报告。

---

## 5. 远程（origin）状态 —— 唯一红色流程发现

```
origin  <https 远程 URL，未打印>（fetch/push）
scheme=https
URL 内嵌凭证：无（无 user:pass@ 形态）✅
```

| 引用 | 状态 |
|------|------|
| `origin/main` | = 本地 `main` = `a1f7ff9`（architecture.md 所载"稳定 commit"；落后基线 87 个 commit） |
| `origin/experiment/sw-sector-index-research-baseline` | 落后本地同名分支 **16 个 commit**（历史快照） |

**风险定性：流程/表述漂移（非 secret 泄露）。**
README（"远程仓库状态"节）与 AGENTS.md（第八节）均声明"没有配置任何远程仓库 / GitHub suspended 不 push"，
但仓库实际配置了 `origin` 并存在已推送引用。含义：

1. GitHub 侧已持有 `a1f7ff9` 及更早的 experiment 分支快照（账号 suspended 冻结中）
2. 若未来公开前恢复账号并 push，将一次性发布 87+ 个未推送 commit 的全部内容
3. 该漂移必须在公开前由用户决策：保留 origin 重新对齐表述，或按 AGENTS.md 移除远程配置

---

## 6. `.gitignore` 审计（只建议，本轮不修改）

### 6.1 现有覆盖（已验证生效，`git check-ignore --no-index`）

| 模式 | 覆盖 |
|------|------|
| `/data/` `/logs/` `/secrets/` | 根目录运行数据/日志/敏感配置（前导斜杠防误伤 `src/data/`、`scripts/data/`、`docs/data/`——注释记录了已踩过的坑） |
| `/reports/backtests/` `/reports/research/` | 回测产物与正式研究产物（`reports/*/.gitkeep` 为刻意 tracked 占位） |
| `.env` `.env.*` `!.env.example` | 任意层级环境变量文件，模板除外 |
| Python/venv/测试/notebook 缓存、`*.log`、`.vscode/*`（放行 settings.json）、`docker/*.log` | 常规噪声 |

分支侧子工程：`dashboard/.gitignore`（node_modules/dist/coverage/*.local/.env/.env.*/*.log，放行 .env.example）、
`services/research-api/.gitignore`（node_modules/dist/coverage/.env/*.log）。

### 6.2 未来应排除项的缺口分析（ETF-Quant 视角）

| 未来资产 | 现状 | 建议（届时再落，本轮不动） |
|----------|------|------------------------------|
| `data/etf_quant/{raw,staging,curated}/` | 已被 `/data/` 整体覆盖 | 若布局保持在 `/data/` 下则无需新增；**若逃逸出根 data/ 必须补显式规则** |
| CNEquity cache | 无文件、无规则 | 引入时补 `**/.cnequity/`、`**/cnequity_cache/` 之类路径规则 |
| 运行时 DB（组合状态 / 全量 NAV DB） | **全局无 `*.db`/`*.sqlite*`/`*.h5` 规则**——现有 hikyuu 库仅因在 `/data/` 下而被忽略 | 建议补全局二进制库模式，或对 `services/etf-quant*/state/`、`data/etf_quant/runtime/` 补显式规则；否则 ETF-Quant 若在 `/data/` 外落库即有入库风险 |
| fill / order 日志、portfolio state | 无文件（SIMULATION_ONLY 尚未启动） | 建议届时补 `**/fills*.log`、`**/orders*.log`、`**/portfolio_state*` 类规则 |
| 凭证 | `.env*`/`secrets/` 已覆盖 | 补充：未来密钥类文件用**路径规则**（如 `**/*.p12`、`**/*.pfx`、`**/id_rsa*`），**不要**全局忽略 `*.pem`——`src/data/certs/` 下公开 CA 证书是刻意 tracked |
| 本地 sidecar 状态（research-api 的 `RESEARCH_REPORT_ROOT` 外置产物） | `/reports/research/` 已覆盖 | 保持 |
| `services/research-api/.gitignore` | 只有 `.env`，无 `.env.*` | 建议对齐 dashboard 的 `.env` + `.env.*` + `!.env.example` 三行式（防 `.env.local` 类文件） |

---

## 7. 公开发布门（Recommended public-release gates）

1. **全 history + 全分支 secret 扫描**：用 gitleaks/trufflehog 类工具对 104+ commits 与全部分支
   （含 `feature/research-api-v1`、`feature/research-dashboard-v1`、`integration/research-dashboard-v1`、
   `agent/*`）复扫；本轮手工扫描通过不能替代工具复扫
2. **远程决策**：先解决第 5 节漂移——对齐 README/AGENTS 表述与实际 `origin` 状态；
   决定公开时推送哪些分支/历史；推送前重跑第 1 条
3. **研究 IP 内容评审（产品决策，非 secret）**：公开将一并暴露
   `docs/research/**`（Shenwan F1 协议/报告/handoff）与 `strategies/sw_sector_rotation/**`（完整策略实现）。
   注意约束：**Validation / Final OOS 为 SEALED/UNSEEN，其 performance 内容必须确认从未进入仓库**
   （本审计未读取任何 performance 内容，只核对了 tracked 文件清单层面的存在性）
4. **运行时数据零入库复核**：`data/`、`logs/`、`secrets/`、`reports/backtests/`、`reports/research/`
   保持 ignore + 从未 tracked（本轮已验证，发布前重验）
5. **隐私小项**：文档含机器路径/用户名（如 `C:\Users\<user>\.codex\config.toml`、
   `docs/windows_chatgpt_environment.md`），公开前可脱敏（非阻断）
6. **发布物补齐**：LICENSE 未见于 tracked 文件；`dashboard/THIRD_PARTY_NOTICES.md` 已有，
   公开前补仓库级 LICENSE 与依赖声明
7. **安全声明保持**：`.env.example` 全空值纪律、`DISABLE_LIVE_TRADING=true` 语义、
   端口仅绑 127.0.0.1、Jupyter 密码哈希不入库 —— 发布后不得回退
8. **未来 ETF-Quant 数据边界**：SIMULATION_ONLY 期间的组合状态/成交/NAV 运行数据
   按第 6.2 节规则排除后再公开

---

## 8. 本轮未做事项（合规声明）

- 未改写 Git history / 未 filter-repo / 未 BFG / 未 reset / 未 rebase / 未 push
- 未修改 `.gitignore`（缺口仅建议）
- 未打印任何真实 secret 值（含 `.env` 值、远程 URL、证书序列号以外的敏感元数据）
- 未读取 Validation performance / Final OOS 内容
- 未修改任何 tracked 文件（本目录 2 个新文档除外）
