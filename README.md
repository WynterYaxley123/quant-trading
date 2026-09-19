# quant-trading — A股/ETF 量化研究环境

> Environment Setup 阶段。当前仓库只包含研究环境，**不含任何策略、回测或交易代码**。

## 项目用途

面向 A 股 / ETF 的量化研究环境。目标是把研究用的 Python 依赖全部收敛进 Docker 容器，
Windows 宿主机只保留工具链（Git / VS Code / Docker / Codex），不在宿主机装任何量化依赖。

## 当前技术栈

| 组件 | 角色 | 状态 |
|------|------|------|
| Hikyuu | 主研究框架 | 待接入 |
| RQAlpha | 独立验证框架 | 待接入 |
| AKShare | 数据获取 | 待接入 |
| Docker | 环境隔离 | 本阶段 |
| Codex | 编码助手 | 本阶段 |
| Git | 本地版本控制 | 本阶段 |

## 未来规划

- Hikyuu —— 主研究框架
- RQAlpha —— 独立验证框架（与 Hikyuu 交叉验证，互为参照）
- JoinQuant —— 模拟盘
- QMT / MiniQMT —— 未来实盘执行层

## 当前明确边界

```
NO STRATEGY
NO BACKTEST
NO PAPER TRADING
NO LIVE TRADING
```

本阶段只做环境搭建与依赖验证，不产生任何交易逻辑。

## 远程仓库状态

```
GitHub remote currently unavailable due to account suspension.
Project currently uses local Git only.
```

GitHub 账号处于 suspended 状态，因此本仓库**没有配置任何远程仓库**。
这是预期状态，不视为部署失败。账号恢复后再补 remote。

## 环境搭建

### 宿主机前置

- Git for Windows
- VS Code（扩展：Python / Pylance / Docker / Dev Containers / Jupyter）
- Docker Desktop（WSL2 后端）
- Codex
- GitHub Desktop（已安装，未登录）

### 构建容器

```bash
docker compose build
```

### 进入容器

```bash
docker compose run --rm quant-research bash
```

### VS Code 开发容器

在 VS Code 中执行 `Dev Containers: Reopen in Container`，进入后：

- 工作目录为 `/workspace`
- Python 解释器为容器内的 `/usr/local/bin/python`
- 可使用 Hikyuu / RQAlpha / AKShare
- 可运行 `pytest`
- 可启动 Jupyter

**不要建立 .venv** —— 所有 Python 依赖统一在容器内。

### 运行环境测试

```bash
docker compose run --rm quant-research pytest -v
```

## 目录结构

```
quant-trading/
├─ docker/
│  └─ Dockerfile           固定 Python 3.11，仅装依赖
├─ .devcontainer/
│  └─ devcontainer.json    Reopen in Container 配置
├─ data/                   行情数据（挂载，不进 Git）
├─ logs/                   运行日志（不进 Git）
├─ notebooks/              Jupyter 笔记本（当前只有说明）
├─ src/                    源码占位
├─ tests/
│  └─ test_environment.py  仅验证依赖可导入
├─ docs/                   研究文档
├─ .gitignore
├─ .dockerignore
├─ docker-compose.yml      服务名 quant-research
├─ requirements.txt
├─ README.md
└─ AGENTS.md
```

## 版本管理规则

| 分支 | 用途 |
|------|------|
| `main` | 稳定环境版本 |
| `dev` | 当前开发环境 |

**不创建** `live` / `production` / `trading` 等任何实盘相关分支。

## 安全声明

- `.env`、`data/`、`logs/`、`secrets/` 永不进入 Git
- 不在宿主机全局 Python 环境安装量化依赖
- 不配置任何真实账号、Token、Cookie
- 不接入任何券商接口
