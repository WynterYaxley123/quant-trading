# quant-trading — A股/ETF 量化研究环境

> Environment Setup 阶段。当前仓库只包含研究环境，**不含任何策略、回测或交易代码**。

## 项目用途

面向 A 股 / ETF 的量化研究环境。目标是把研究用的 Python 依赖全部收敛进 Docker 容器，
Windows 宿主机只保留工具链（Git / VS Code / Docker / Codex），不在宿主机装任何量化依赖。

## 当前技术栈

| 组件 | 角色 | 版本/状态 |
|------|------|------|
| Hikyuu | 主研究框架 | 2.8.2（已接入） |
| RQAlpha | 独立验证框架 | 6.4.0（已接入） |
| AKShare | 数据获取 | 1.18.88（已接入） |
| JupyterLab | 交互研究界面 | 4.4.9（随服务启动） |
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
├─ data/                   行情数据（挂载，不进 Git）
├─ logs/                   运行日志（不进 Git）
├─ notebooks/              Jupyter 笔记本（当前只有说明）
├─ src/                    源码占位
├─ tests/
│  └─ test_environment.py  仅验证依赖可导入
├─ docs/                   研究文档
├─ .gitignore
├─ .dockerignore
├─ docker-compose.yml      服务: quant-research + jupyter
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
- `.env.example` 所有凭证项保持空值，仅作模板
- 不在宿主机全局 Python 环境安装量化依赖
- 不配置任何真实账号、Token、Cookie
- 不接入任何券商接口
- 所有端口映射仅绑定 `127.0.0.1`，不对局域网暴露
- Jupyter 使用密码认证（argon2 哈希存于 .env），不使用无认证模式
