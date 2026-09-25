# quant-trading — A股/ETF 量化研究项目

> **ENVIRONMENT + QUANT WORKFLOW FOUNDATION COMPLETE**
> 环境已部署验证通过，开发工作流已定型。当前仓库**不含任何策略、回测或交易代码**。

## 项目定位

面向 A 股 / ETF 的量化研究项目。研究用的 Python 依赖全部收敛进 Docker 容器，
Windows 宿主机只保留工具链（Git / VS Code / Docker / ChatGPT），
不在宿主机装任何量化依赖。

## 角色分工

| 角色 | 承担方 | 状态 |
|------|--------|------|
| 主要代码开发 | Windows ChatGPT | 现行 |
| 环境与自动化编排 | Hermes | 现行 |
| 主研究框架 | Hikyuu | 已部署，未开始使用 |
| 独立验证框架 | RQAlpha | 已部署，未开始使用 |
| 数据获取 | AKShare | 已部署 |
| 交互研究界面 | JupyterLab | 已部署 |
| 备用工具 | WSL codex-cli | 可选 |
| 模拟盘 | JoinQuant | 未来 |
| 通知推送 | 飞书 | 未来 |
| 代码与成果同步 | GitHub | 未来（账号 suspended） |
| 实盘执行 | QMT / MiniQMT | 未来 |

**Hermes 默认不修改核心量化逻辑**（`strategies/` 下的策略包、`research/`）。
详见 `AGENTS.md` 与 `docs/architecture.md`。

## 开发架构

```
User
 │
 ▼
Windows ChatGPT                 ← 主要开发入口
 │
 ▼
D:\quant-trading                ← 项目根目录
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

完整说明见 `docs/architecture.md`。

## 执行原则

ChatGPT 执行量化 Python 代码**必须**通过 `quant-research` 容器：

```bash
docker compose exec quant-research python <script.py>
docker compose exec quant-research pytest tests -q
```

**不使用 Windows 全局 Python。**

### Windows 侧 Docker CLI 路径

`C:\Program Files\Docker\Docker\resources\bin` 已在 Machine PATH 注册表中。
若当前进程继承旧环境快照而找不到 `docker` 命令，使用完整路径：

```
"C:\Program Files\Docker\Docker\resources\bin\docker.exe" compose ps
```

**PATH 缺失不代表 Docker 不可用。**
重启 ChatGPT/Codex 应用后 PATH 生效，即可直接使用 `docker`。

## 当前技术栈

| 组件 | 角色 | 版本 |
|------|------|------|
| Python | 运行时 | 3.12.11 |
| Hikyuu | 主研究框架 | 2.8.2 |
| RQAlpha | 独立验证框架 | 6.4.0 |
| AKShare | 数据获取 | 1.18.88 |
| NumPy | 数值计算 | 2.3.5 |
| Pandas | 数据处理 | 2.3.3 |
| SciPy | 科学计算 | 1.16.3 |
| JupyterLab | 交互研究界面 | 4.4.9 |
| Docker 镜像 | 环境隔离 | `quant-research:py3.12` |

**以上版本为稳定基线，除确有必要外不得修改。**
依赖冲突的解决记录见 `docs/dependency_conflicts.md`。

## 当前明确边界

```
NO STRATEGY
NO FACTOR
NO DATA DOWNLOAD
NO BACKTEST
NO PAPER TRADING
NO LIVE TRADING
```

本阶段只做项目结构、角色定义、工作流、文档与接口骨架。

## 远程仓库状态

```
GitHub remote currently unavailable due to account suspension.
Project currently uses local Git only.
```

GitHub 账号处于 suspended 状态，本仓库**没有配置任何远程仓库**。
这是预期状态，不视为部署失败。账号恢复后再补 remote。
项目保持 **GitHub-ready** 结构，详见 `docs/github_workflow.md`。

## 文档索引

| 文档 | 用途 |
|------|------|
| `AGENTS.md` | 强制约束与角色定义 |
| `docs/architecture.md` | 项目架构与角色定义 |
| `docs/chatgpt_workflow.md` | ChatGPT 标准工作流 |
| `docs/joinquant_import.md` | 聚宽策略导入流程 |
| `docs/strategy_specification.md` | 策略规格模板 |
| `docs/report_schema.md` | 报告输出标准 |
| `docs/feishu_integration.md` | 飞书集成规划 |
| `docs/github_workflow.md` | GitHub 工作流规划 |
| `docs/future_quant_api.md` | 未来 API / MCP 规划 |
| `docs/environment_setup_report.md` | 环境验收报告 |
| `docs/dependency_conflicts.md` | 依赖冲突记录 |
| `docs/codex_usage.md` | WSL codex-cli 备用工具说明 |


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

### 启动服务

```bash
docker compose up -d
```

启动两个容器：

| 容器 | 作用 | 端口（仅绑定 Windows localhost） |
|------|------|--------------------------------|
| `quant-research` | 研究环境（常驻 bash） | 9200 / 9201（hikyuu 行情服务预留） |
| `quant-jupyter` | JupyterLab 交互界面 | 8888 |

### 进入容器

```bash
docker exec -it quant-research bash
```

### JupyterLab

#### 配置密码

Jupyter 使用**密码认证**。宿主机 `.env` 中只存密码的 argon2 哈希（不存明文），
该文件已被 `.gitignore` 忽略，不会进入 Git。

配置步骤：

```bash
# 1. 生成密码哈希（把 <你的密码> 换成自己要设的密码）
docker exec quant-jupyter python -c \
  "from jupyter_server.auth import passwd; print(passwd('<你的密码>'))"

# 2. 写入 .env（注意：哈希中的每个 $ 必须写成 $$，否则会被 compose 插值破坏）
#    JUPYTER_PASSWORD=argon2:$$argon2id$$v=19$$m=10240,t=10,p=8$$xxxx$$yyyy
```

`.env.example` 中的 `JUPYTER_PASSWORD` 保持为空，仅作模板，不填任何真实值。

#### 为什么哈希里的 `$` 要写成 `$$`

Docker Compose 会对 `.env` 中的值做变量插值，`$argon2id`、`$v` 这类片段会被
当成变量名展开成空字符串，导致哈希被静默破坏、密码永远校验失败。写成 `$$`
后 compose 输出单个 `$`，哈希还原正确。

验证方法（应输出 105 和 5，即长度 105、含 5 个 `$`）：

```bash
docker exec quant-jupyter bash -c \
  'v="$JUPYTER_PASSWORD"; echo "len=${#v} dollars=$(printf %s "$v" | tr -cd "$" | wc -c)"'
```

#### 访问

启动服务后，在 Windows 浏览器打开：

```
http://localhost:8888/lab
```

- 首次访问跳出登录页，输入密码即可
- 浏览器会记住会话，之后直接访问 `localhost:8888/lab` 无需重复输入
- 未认证访问 `/lab` 返回 302（跳登录页）
- 工作目录为 `/workspace`（对应宿主机 `D:\quant-trading`）

#### 安全边界

- 端口映射为 `127.0.0.1:8888:8888`，**仅监听 Windows 本机回环地址**
- 局域网内其他设备无法访问（端口不绑定 `0.0.0.0`）
- 不使用无认证模式；密码哈希存于 `.env`，不进 Git
- 容器内监听 `0.0.0.0:8888` 是端口映射的必要条件（服务只绑 loopback 时宿主机转发不进来），
  对外暴露面由宿主机侧 `127.0.0.1` 绑定限定

### VS Code 开发容器

在 VS Code 中执行 `Dev Containers: Reopen in Container`，进入后：

- 工作目录为 `/workspace`
- Python 解释器为容器内的 `/opt/conda/bin/python`
- 可使用 Hikyuu / RQAlpha / AKShare
- 可运行 `pytest`

**不要建立 .venv** —— 所有 Python 依赖统一在容器内。

### 运行环境测试

```bash
docker exec quant-research pytest tests -v
```

## 目录结构

```
quant-trading/
├─ docker/
│  └─ Dockerfile           固定 Python 3.12（Ubuntu 24.04 底座），仅装依赖
├─ .devcontainer/
│  └─ devcontainer.json    Reopen in Container 配置
├─ src/
│  ├─ strategies/
│  │  ├─ imported/
│  │  │  └─ joinquant/     原始聚宽代码（只读，不覆盖）
│  │  ├─ hikyuu/           Hikyuu 实现（主研究）
│  │  └─ rqalpha/          RQAlpha 验证版（独立验证）
│  ├─ factors/             因子计算
│  ├─ signals/             信号生成
│  ├─ risk/                风控指标（TGT / TR / RGrid / ZMB / SL）
│  ├─ portfolio/           组合与仓位管理
│  ├─ adapters/            框架适配层
│  ├─ reporting/           报告生成
│  ├─ notifications/       通知（飞书骨架已就位）
│  ├─ common/              通用工具
│  └─ data/                数据获取与清洗
├─ research/
│  └─ factors/             因子研究笔记
├─ reports/
│  ├─ strategies/          策略规格汇总
│  ├─ backtests/           回测结果
│  ├─ factors/             因子研究结果
│  ├─ comparisons/         双框架交叉验证
│  └─ daily/               日常研究记录
├─ scripts/
│  └─ automation/          自动化脚本（Hermes 维护）
├─ notebooks/              Jupyter 笔记本（当前只有说明）
├─ data/                   行情数据（挂载，不进 Git）
├─ logs/                   运行日志（不进 Git）
├─ secrets/                敏感配置（不进 Git）
├─ tests/
│  └─ test_environment.py  仅验证依赖可导入
├─ docs/                   项目文档
├─ .gitignore
├─ .dockerignore
├─ docker-compose.yml      服务: quant-research + quant-jupyter
├─ requirements.txt
├─ README.md
└─ AGENTS.md
```

## 版本管理规则

| 分支 | 用途 |
|------|------|
| `main` | 稳定环境 + 已验证成果 |
| `dev` | 开发主线 |
| `experiment/<name>` | 试验性工作 |

**不创建** `live` / `production` / `trading` 等任何实盘相关分支。

当前 `main` 与 `dev` 均指向稳定基线。GitHub 账号恢复前不使用远程仓库。

## 安全声明

- `.env`、`data/`、`logs/`、`secrets/` 永不进入 Git
- `.env.example` 所有凭证项保持空值，仅作模板
- 不在宿主机全局 Python 环境安装量化依赖
- 不配置任何真实账号、Token、Cookie
- 不接入任何券商接口
- 所有端口映射仅绑定 `127.0.0.1`，不对局域网暴露
- Jupyter 使用密码认证（argon2 哈希存于 .env），不使用无认证模式
- 飞书凭证项仅留空值模板，不填真实值
- 回测报告不编造数据，未产生结果为 `null`

## 下一阶段（尚未开始）

以下事项**均未开始**，需用户明确指令后启动：

- 行情数据准备
- Hikyuu 数据导入
- 策略开发
- 因子开发
- 回测
- RQAlpha 交叉验证
- JoinQuant 模拟盘

