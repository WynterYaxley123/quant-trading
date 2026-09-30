# 工作流定型验收报告

**日期**：2026-09-19
**项目**：quant-trading
**状态**：**ENVIRONMENT + QUANT WORKFLOW FOUNDATION COMPLETE**

---

## 1. 本轮目标

将项目正式整理为：

> Windows 端 ChatGPT 负责后续所有量化代码开发，
> Hermes 负责环境与自动化编排，
> Hikyuu 负责主研究，
> RQAlpha 负责独立验证，
> 未来飞书负责结果推送，
> 未来 GitHub 负责代码与研究成果同步展示。

**本轮只做：项目结构、角色定义、Workflow、文档、接口骨架、未来规划。**
未执行任何策略开发、回测、数据下载或交易相关操作。

---

## 2. 最终项目架构

```
User
 │
 ▼
Windows ChatGPT                 ← PRIMARY DEVELOPMENT AGENT
 │
 ▼
D:\quant-trading
 │
 ├──────────────┬───────────────┐
 ▼              ▼               │
Local Git  Docker Desktop       │
                │               │
                ▼               │
         quant-research         │
                │               │
        ┌───────┴───────┐       │
        ▼               ▼       │
     Hikyuu          RQAlpha    │
    Main Research   Validation  │
        └───────┬───────┘       │
                ▼               │
            Reports             │
                │               │
        ┌───────┴───────┐       │
        ▼               ▼       │
      Feishu         GitHub     │
   Notification     Archive     │
     (future)       (future)    │
```

---

## 3. 角色定义

| 角色 | 承担方 |
|------|--------|
| PRIMARY CODE AGENT | Windows ChatGPT |
| AUTOMATION / INFRASTRUCTURE | Hermes |
| RESEARCH | Hikyuu |
| VALIDATION | RQAlpha |
| OPTIONAL FALLBACK TOOL | WSL codex-cli |
| SIMULATION | JoinQuant（未来） |
| NOTIFICATIONS | Feishu（未来） |
| REMOTE / ARCHIVE | GitHub（未来） |
| EXECUTION | QMT / MiniQMT（未来） |

**核心边界：Hermes 默认不得与 ChatGPT 并行修改核心策略代码。**

---

## 4. 目录所有权

### ChatGPT（核心研究代码）

```
src/strategies/
src/factors/
src/signals/
src/risk/
src/portfolio/
research/
```

### Hermes（基础设施）

```
docker/
.devcontainer/
scripts/automation/
docs/environment/
src/notifications/
CI 配置
```

---

## 5. 目录结构变更

| 变更 | 说明 |
|------|------|
| `factors/` → `src/factors/` | git mv，历史保留 |
| `risk/` → `src/risk/` | git mv，历史保留 |
| `strategies/` → `src/strategies/` | git mv，历史保留 |
| `backtests/` 移除 | 功能由 `reports/backtests/` 承担 |
| 新建 `src/{signals,portfolio,adapters,reporting,notifications,common,data}/` | 占位 |
| 新建 `src/strategies/{imported/joinquant,hikyuu,rqalpha}/` | 三方分离 |
| 新建 `research/factors/` | 因子研究笔记 |
| 新建 `reports/{strategies,backtests,factors,comparisons,daily}/` | 结果输出 |
| 新建 `scripts/automation/report_schema/` | schema 模板 |

---

## 6. 新增文档

| 文档 | 内容 |
|------|------|
| `docs/architecture.md` | 架构与角色定义 |
| `docs/chatgpt_workflow.md` | ChatGPT 标准工作流（16 步） |
| `docs/strategy_specification.md` | 统一策略规格模板 |
| `docs/joinquant_import.md` | 聚宽导入流程 |
| `docs/feishu_integration.md` | 飞书集成规划 |
| `docs/github_workflow.md` | GitHub 工作流规划 |
| `docs/future_quant_api.md` | quant-mcp / API 规划 |
| `docs/report_schema.md` | 报告输出标准 |

## 7. 更新文档

| 文档 | 变更 |
|------|------|
| `AGENTS.md` | 重写：角色 + 所有权 + 硬约束 |
| `README.md` | 补角色分工、架构图、执行原则、文档索引 |
| `src/README.md` | 更新为集中式结构说明 |
| `docs/codex_usage.md` | 重写为备用工具说明（降级） |
| `.env.example` | 补飞书空值模板，修正 Jupyter 注释 |
| `.vscode/settings.json` | 修正解释器路径 |

---

## 8. WSL codex-cli 定位（降级）

**OPTIONAL FALLBACK TOOL**，不是主开发入口。

保留的技术记录：

- `codex-cli 0.146.0` 运行在 WSL
- 普通 sandbox 无法访问 Docker Desktop
- 仅 `-s danger-full-access` 可调用 Docker
- 受限沙箱报 `UtilBindVsockAnyPort:309: socket failed 1`
- `~/bin/docker` wrapper 完成 WSL → Windows Docker 兼容

**`danger-full-access` 已从主工作流移除**，仅在备用场景说明中记录。

---

## 9. 接口骨架

| 项 | 状态 |
|----|------|
| `src/notifications/feishu.py` | 骨架完成，dry-run 优先 |
| 未配置凭证行为 | 返回 `not_configured`，不抛异常、不阻塞 |
| 指标为空时 | 显示空值，**不使用 0 或估计值** |
| 真实发送 | **未实现**（需用户明确指令） |
| `FEISHU_WEBHOOK` / `APP_ID` / `APP_SECRET` | 仅 `.env.example` 空值模板 |

---

## 10. 报告结构

目录规范：`reports/backtests/<strategy>/<run_id>/`

Schema 模板位于 `scripts/automation/report_schema/`：
`metadata.json` / `metrics.json` / `comparison.json`，
所有值为空或 `null`，**无任何虚构数据**。

---

## 11. Git

| 项 | 值 |
|----|-----|
| 分支 | `experiment/chatgpt-workflow` → 已合并 `dev` |
| `main` | `a1f7ff9`（**未自动合并**，按用户要求） |
| `dev` | `1b62e6c` |
| 工作区 | clean |

### Commits

```
1b62e6c docs: plan future quant API interface
84e9a1e docs: plan Feishu and GitHub integrations
ca3d437 chore: align agent responsibilities
d174233 docs: define ChatGPT-first quant workflow
```

---

## 12. 稳定环境验证（未改变）

| 项 | 基线值 | 实测 |
|----|--------|------|
| Python | 3.12.11 | 3.12.11 ✓ |
| Hikyuu | 2.8.2 | 2.8.2 ✓ |
| RQAlpha | 6.4.0 | 6.4.0 ✓ |
| AKShare | 1.18.88 | 1.18.88 ✓ |
| NumPy | 2.3.5 | 2.3.5 ✓ |
| Pandas | 2.3.3 | 2.3.3 ✓ |
| SciPy | 1.16.3 | 1.16.3 ✓ |
| JupyterLab | 4.4.9 | 4.4.9 ✓ |
| pytest | 14 passed | 14 passed ✓ |
| Docker 镜像 | `quant-research:py3.12` | 未重建 ✓ |

**未重新安装环境、未重新构建依赖、未修改任何版本。**

---

## 13. 安全核对

| 检查项 | 结果 |
|--------|------|
| 硬编码凭证 | 无 ✓ |
| `.env` 被忽略 | 是 ✓ |
| `data/` `logs/` `secrets/` 被忽略 | 是 ✓ |
| 策略代码 | 0 个 ✓ |
| 因子代码 | 0 个 ✓ |
| 假回测结果 | 0 个 ✓ |
| hikyuu-mcp 实现 | 无 ✓ |
| MCP 服务实现 | 无 ✓ |

---

## 14. 下一阶段尚未执行

以下事项**均未开始**，需用户明确指令后启动：

- 行情数据准备
- Hikyuu 数据导入
- 策略开发
- 因子开发
- 回测
- RQAlpha 交叉验证
- JoinQuant 模拟盘
- QMT / MiniQMT 接入
- 飞书真实通知发送
- GitHub remote 配置与 push
- quant-mcp / API 实现

---

**ENVIRONMENT + QUANT WORKFLOW FOUNDATION COMPLETE**
