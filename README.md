# Quant Trading

A股 / ETF 量化策略研究与开发工作区。

## 用途

- A股 / ETF 量化策略研究
- 聚宽（JoinQuant）策略学习与向本地迁移
- 掘金量化（MyQuant）回测 / 仿真
- Codex 辅助策略开发
- GitHub 版本管理与协作

## 目录结构

```
quant-trading/
|-- strategies/          交易策略
|   `-- myquant/         掘金量化策略（预留）
|-- factors/             因子计算
|-- risk/                仓位管理、止损、风控
|-- backtests/           回测
|   |-- configs/         回测参数配置
|   `-- results/         回测结果
|-- tests/               自动化测试
|-- docs/                策略说明与研究日志
|   `-- strategy_notes.md
|-- data/                本地行情数据（不入 Git）
|-- logs/                运行日志（不入 Git）
|-- secrets/             本地敏感配置（不入 Git）
|-- .env.example         环境变量模板
|-- .gitignore
|-- requirements.txt
`-- AGENTS.md            Codex 协作规则
```

## 开发流程

```
策略想法
  -> Codex 实现（dev / experiment 分支）
  -> 本地测试（pytest）
  -> 本地回测
  -> 结果分析
  -> Git Commit
  -> Push GitHub
  -> 仿真
  -> 人工审核
  -> 实盘
```

## 安全声明

> **Codex 不得直接把未经验证的新策略部署到实盘。**

任何策略上线实盘前，必须依次通过：

1. 单元测试
2. 历史回测
3. 样本外验证
4. 仿真
5. 用户人工确认

## 分支规范

| 分支 | 用途 |
|------|------|
| `main` | 稳定代码 |
| `dev` | 日常开发 |
| `experiment/*` | 实验性策略 |
| `live` | 未来实盘策略，仅在明确批准后使用 |

当前阶段只使用 `main` 与 `dev`，**不创建任何实盘交易逻辑**。

Codex 修改策略时默认从 `dev` 创建实验分支：

```
experiment/etf-rotation
experiment/momentum
experiment/multi-factor
```

**禁止直接在 `live` 上自动修改。**

## 环境搭建

```bash
# 创建虚拟环境
python -m venv .venv

# 激活（Windows PowerShell）
.venv\Scripts\Activate.ps1

# 升级 pip 并安装依赖
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 环境变量

复制模板并填写（**仅本地**）：

```bash
cp .env.example .env
```

`.env` 已被 `.gitignore` 忽略，不会进入 Git。

## 测试

```bash
pytest
```

## 掘金量化（后续）

当前阶段**不配置真实 Token**，仅预留 `strategies/myquant/`。

后续计划：

1. 安装掘金 Python SDK
2. 配置回测
3. 配置仿真
4. 将策略迁移至 MyQuant
5. 后期再考虑实盘

## 当前阶段范围

已完成：Git + Python + GitHub + 项目结构 + Codex 开发环境

尚未开始（明确不做）：

- 配置真实证券账户
- 安装券商交易 API
- 自动下单
- QMT / MiniQMT / PTrade
- Freqtrade / vn.py / Qlib
- 大规模行情下载
- 数据库集群
- Web Quant Platform
- 云服务器
