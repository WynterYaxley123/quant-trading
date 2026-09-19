# AGENTS.md — 项目强制约束

本文件对本仓库内的所有自动化助手（Windows ChatGPT / Hermes / Codex / Claude Code 等）
具有强制效力。每次在仓库内工作前必须先读本文件。

---

## 一、阶段

当前项目处于 **ENVIRONMENT + QUANT WORKFLOW FOUNDATION** 阶段。
环境已部署完成并验证通过，工作流已定型。**尚未进入策略研究阶段。**

---

## 二、角色定义

| 角色 | 承担方 | 状态 |
|------|--------|------|
| PRIMARY CODE AGENT | Windows ChatGPT | 现行 |
| AUTOMATION / INFRASTRUCTURE | Hermes | 现行 |
| RESEARCH | Hikyuu | 已部署 |
| VALIDATION | RQAlpha | 已部署 |
| OPTIONAL FALLBACK TOOL | WSL codex-cli | 备用 |
| SIMULATION | JoinQuant | 未来 |
| NOTIFICATIONS | Feishu | 未来 |
| REMOTE | GitHub | 未来（suspended） |
| EXECUTION | QMT / MiniQMT | 未来 |

详见 `docs/architecture.md`。

---

## 三、代码所有权与协作边界

### 默认属于 ChatGPT 的目录

```
src/strategies/
src/factors/
src/signals/
src/risk/
src/portfolio/
research/
```

**Hermes 未经用户明确要求，不得主动修改上述核心研究代码。**

### 由 Hermes 维护的目录

```
docker/
.devcontainer/
scripts/automation/
docs/environment/
通知系统（src/notifications/）
CI 配置
工作流配置
基础设施
```

### 硬约束

**Hermes 默认不得与 ChatGPT 并行修改核心策略代码。**
如需改动核心研究代码，必须由用户明确指示。

---

## 四、代码开发入口

**主要开发入口：Windows 端 ChatGPT。**

执行路径：

```
ChatGPT
  → D:\quant-trading
  → docker compose exec quant-research ...
  → 容器内 Python
```

**禁止使用 Windows 全局 Python 执行量化代码。**

WSL codex-cli 仅为**可选备用工具**，其 `-s danger-full-access` 用法
**不属于主工作流前置要求**。详见 `docs/architecture.md` 第 7 节。

---

## 五、禁止事项（硬约束）

1. **未经用户明确指令，禁止创建交易策略**
2. **禁止运行回测**
3. **禁止模拟交易**
4. **禁止真实交易**
5. **禁止接入真实券商**
6. **禁止读取或保存真实金融账户凭证**
7. **禁止提交**下列内容到 Git：

```
.env
data/
logs/
secrets/
Token
密码
Cookie
账号
```

8. **禁止**部署 PostgreSQL / MySQL / MongoDB / Redis 等数据库
9. **禁止**在 Windows 宿主机全局 Python 环境安装量化依赖
10. **禁止**使用 `.venv` —— 宿主机不建虚拟环境
11. **禁止**登录 JoinQuant、配置 JoinQuant 账号
12. **禁止**登录 GitHub、创建 remote、push（账号 suspended 期间）
13. **禁止**安装 Qlib、vn.py、WonderTrader、Freqtrade、Backtrader、
    QUANTAXIS、ZVT、QMT、MiniQMT、PTrade、easytrader、EasyXT
14. **禁止**实现 hikyuu-mcp 或任何 MCP 服务

---

## 六、稳定环境基线（不得无必要修改）

| 项 | 值 |
|----|-----|
| 项目路径 | `D:\quant-trading` |
| 容器内路径 | `/workspace` |
| Python | 3.12.11（`/opt/conda/bin/python`） |
| Hikyuu | 2.8.2 |
| RQAlpha | 6.4.0 |
| AKShare | 1.18.88 |
| NumPy | 2.3.5 |
| Pandas | 2.3.3 |
| SciPy | 1.16.3 |
| JupyterLab | 4.4.9 |
| Docker 镜像 | `quant-research:py3.12` |

**不要重新解决已经解决过的依赖问题。**

依赖冲突的完整记录见 `docs/dependency_conflicts.md`。

---

## 七、技术栈定位

- Hikyuu —— **PRIMARY RESEARCH FRAMEWORK**（主研究框架）
- RQAlpha —— **INDEPENDENT VALIDATION FRAMEWORK**（独立验证框架）
- JoinQuant —— **SIMULATION**（未来模拟环境）

RQAlpha **不作为**第二套主开发框架。

---

## 八、版本控制

- GitHub 当前不可用（账号 suspended）
- 当前**只允许本地 Git 版本控制**
- **不配置任何远程 Git 仓库**
- 分支：`main`（稳定） / `dev`（开发） / `experiment/<name>`（试验）
- **不创建** `live` / `production` / `trading` 等实盘相关分支

---

## 九、Hikyuu 与 RQAlpha 一致性要求

两框架**必须遵循同一份 Strategy Specification**
（模板见 `docs/strategy_specification.md`）。

不得在两侧写入不同参数、不同标的池或不同风控规则。
若因框架差异必须不同，须记入 Specification 的 `Known Limitations`。

---

## 十、报告输出标准

回测结果统一输出到：

```
reports/backtests/<strategy>/<run_id>/
```

完整 schema 见 `docs/report_schema.md`。

**禁止手工编造指标数据。** `null` 表示尚未产生结果，
不得用 0 或估计值替代。

---

## 十一、未来集成

- **飞书**：通知与结果推送。骨架见 `src/notifications/feishu.py`，
  配置模板见 `docs/feishu_integration.md`。当前不发真实通知。
- **GitHub**：代码与研究成果同步展示。规划见 `docs/github_workflow.md`。
  当前不登录、不 push。
- **quant-mcp / API**：未来规划见 `docs/future_quant_api.md`。
  当前不实现。

---

## 十二、相关文档索引

| 文档 | 用途 |
|------|------|
| `docs/architecture.md` | 项目架构与角色定义 |
| `docs/chatgpt_workflow.md` | ChatGPT 标准工作流 |
| `docs/joinquant_import.md` | 聚宽策略导入流程 |
| `docs/strategy_specification.md` | 策略规格模板 |
| `docs/report_schema.md` | 报告输出标准 |
| `docs/feishu_integration.md` | 飞书集成规划 |
| `docs/github_workflow.md` | GitHub 工作流规划 |
| `docs/future_quant_api.md` | 未来 API 规划 |
| `docs/dependency_conflicts.md` | 依赖冲突记录 |
| `docs/environment_setup_report.md` | 环境验收报告 |
| `docs/codex_usage.md` | codex-cli 备用工具说明 |
