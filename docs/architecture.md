# 项目架构与角色定义

> 本文件定义 quant-trading 项目的正式开发架构与各方职责边界。
> 状态：**ENVIRONMENT + QUANT WORKFLOW FOUNDATION COMPLETE**
> 最后更新：2026-09-19

---

## 1. 正式开发架构

```
User
 │
 ▼
Windows ChatGPT                    ← PRIMARY DEVELOPMENT AGENT
 │
 ▼
D:\quant-trading                   ← 项目根目录（WSL: /mnt/d/quant-trading）
 │
 ├────────────────┬────────────────┐
 ▼                ▼                │
Local Git   Docker Desktop         │
 │                │                │
 │                ▼                │
 │         quant-research          │
 │                │                │
 │      ┌─────────┴─────────┐      │
 │      ▼                   ▼      │
 │   Hikyuu              RQAlpha   │
 │  Main Research      Validation  │
 │      │                   │      │
 │      └─────────┬─────────┘      │
 │                ▼                │
 │            Reports              │
 │                │                │
 │      ┌─────────┴─────────┐      │
 │      ▼                   ▼      │
 │   Feishu               GitHub   │
 │ Notification      Code / Archive│
 │  (future)            (future)   │
```

---

## 2. 角色定义

| 角色 | 承担方 | 状态 |
|------|--------|------|
| PRIMARY CODE AGENT | Windows ChatGPT | 现行 |
| AUTOMATION / INFRASTRUCTURE | Hermes | 现行 |
| RESEARCH | Hikyuu | 已部署，未开始使用 |
| VALIDATION | RQAlpha | 已部署，未开始使用 |
| OPTIONAL FALLBACK TOOL | WSL codex-cli | 备用 |
| SIMULATION | JoinQuant | 未来 |
| NOTIFICATIONS | Feishu | 未来 |
| REMOTE / ARCHIVE | GitHub | 未来（账号 suspended） |
| EXECUTION | QMT / MiniQMT | 未来 |

---

## 3. Windows ChatGPT 职责

**定位：主要代码开发入口。**

以下工作原则上全部由 Windows 端 ChatGPT 完成：

- 策略开发
- 因子开发
- Hikyuu 实现
- RQAlpha 验证版实现
- 测试编写
- 回测执行与分析
- 研究分析
- 报告生成
- 代码维护

**执行路径（必须遵守）：**

```
ChatGPT
  → D:\quant-trading
  → docker compose exec quant-research ...
  → 容器内 Python
```

**禁止：** 使用 Windows 全局 Python 执行量化 Python 代码。
所有量化依赖只存在于 Docker 容器内。

---

## 4. Hermes 职责

**定位：环境与自动化编排，不是策略开发 Agent。**

Hermes 负责：

- 环境部署与维护
- Docker 维护
- 服务检查
- 自动化任务与调度
- 飞书集成
- GitHub 集成
- 日志
- 通知
- 后续 Workflow 编排

**Hermes 默认不得主动修改核心量化逻辑。**

### 目录所有权

以下目录**默认属于 ChatGPT**，Hermes 未经用户明确要求不得主动修改：

```
strategies/              策略包集合（自包含）
research/                研究草稿
```

策略包是自包含的：每个策略含自己的 `src/`、`config/`、`tests/`、`docs/`，
不依赖顶层 `src/`。

以下目录**由 Hermes 维护**：

```
docker/
.devcontainer/
scripts/automation/
docs/environment/
通知系统
CI 配置
工作流配置
基础设施
```

**硬约束：Hermes 默认不得与 ChatGPT 并行修改核心策略代码。**
如需改动核心研究代码，必须由用户明确指示。

---

## 5. Hikyuu 职责

**PRIMARY RESEARCH FRAMEWORK（主研究框架）**

未来负责：

- 策略研究
- 指标
- 信号
- 因子
- ETF 轮动
- 股票筛选
- 资金管理
- 风控
- 组合
- 主历史回测

---

## 6. RQAlpha 职责

**INDEPENDENT VALIDATION FRAMEWORK（独立验证框架）**

未来负责：

- 独立复现核心交易逻辑
- 验证成交逻辑
- 验证交易成本
- 验证持仓
- 验证收益曲线
- 检查框架差异

**RQAlpha 不作为第二套主开发框架。**

---

## 7. WSL codex-cli 定位

**OPTIONAL FALLBACK TOOL（可选备用工具）**

当前环境已存在 `codex-cli 0.146.0`，运行在 WSL。

**它不是未来主要开发入口。** 主入口是 Windows ChatGPT。

### 保留的技术事实

以下技术事实经实测确认，全部保留供备用场景参考：

- 普通 sandbox 无法访问 Docker Desktop
- 只有 `-s danger-full-access` 才能通过 WSL → Docker Desktop 正常调用 Docker
- 受限沙箱下调用 Docker 报错：

```
<3>WSL (2 - ) ERROR: UtilBindVsockAnyPort:309: socket failed 1
```

- `~/bin/docker` wrapper 完成 WSL → Windows Docker Desktop 兼容调用

### 为什么需要 docker wrapper

WSL 内直接调用 `docker`（无 `.exe` 后缀）会触发 Docker Desktop 的 WSL 集成检查
并拒绝执行；实际二进制为 `docker.exe`。wrapper 位于 `~/bin/docker`，负责：

1. 调用真实二进制 `docker.exe`
2. 把 WSL 路径参数（`/mnt/d/...`）转换成 Windows 路径（`D:\...`）

**在 README 或主工作流中，不得把 `codex -s danger-full-access`
写成普通开发的前置步骤。** 它只属于 WSL codex-cli 的备用使用场景。

---

## 8. 稳定环境基线

**以下为已验证的稳定基线，除确有必要外不得修改。**

| 项 | 值 |
|----|-----|
| 项目路径 | `D:\quant-trading` |
| 容器内工作路径 | `/workspace` |
| WSL 路径 | `/mnt/d/quant-trading` |
| 操作系统 | Ubuntu 24.04 |
| Python | 3.12.11（`/opt/conda/bin/python`） |
| Hikyuu | 2.8.2 |
| RQAlpha | 6.4.0 |
| AKShare | 1.18.88 |
| NumPy | 2.3.5 |
| Pandas | 2.3.3 |
| SciPy | 1.16.3 |
| JupyterLab | 4.4.9 |
| Docker 镜像 | `quant-research:py3.12` |
| 服务 | `quant-research`、`quant-jupyter` |
| 端口 | 8888 / 9200 / 9201（全部仅绑 `127.0.0.1`） |
| pytest | 14 passed |
| Dev Container | PASS |
| Remote User | `mambauser` |
| Git | main = dev |
| 稳定 commit | `a1f7ff9` |
| GitHub | 账号 suspended，仅本地 Git |

---

## 9. Docker 执行原则

ChatGPT 进行量化 Python 执行时**必须使用 `quant-research` 容器**，
不得使用 Windows 全局 Python。

```bash
docker compose exec quant-research python ...
docker compose exec quant-research pytest
```

---

## 10. Dev Container 定位

保留现状（PASS）：

- 工作目录 `/workspace`
- Python `/opt/conda/bin/python`
- User `mambauser`

用途：

- 用户手工查看
- VS Code 开发
- Debug
- Notebook
- 手工终端

**不是 Windows ChatGPT 开发的强制前提。**

---

## 11. Jupyter 定位

保持现状：

- 地址 `http://localhost:8888/lab`
- 仅绑定 `127.0.0.1`
- 密码认证
- 工作目录 `/workspace`

用途：

- 人工探索
- Notebook 研究
- 数据可视化
- 因子研究

**当前不创建正式策略 Notebook。**
