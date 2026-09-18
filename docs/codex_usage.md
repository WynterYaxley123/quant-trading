# Codex 使用说明（本仓库）

本文件说明如何在本仓库中使用 Codex 进行量化策略开发。

## 启动方式

在本仓库根目录启动 Codex，使其能读取 `AGENTS.md`：

```powershell
cd D:\quant-trading
codex
```

Codex 会自动读取仓库根目录的 `AGENTS.md`，其中包含本项目的强制约束。

## 必须遵守的规则（摘自 AGENTS.md）

1. 任何修改先在 `dev` 或 `experiment/*` 分支进行
2. 禁止直接修改 `live`
3. 禁止读取、提交或输出真实账户密码、Token
4. 禁止将 `.env`、`data/`、`logs/`、`secrets/` 提交 Git
5. 新策略必须经过：单元测试 -> 历史回测 -> 样本外验证 -> 仿真 -> 用户确认
6. 回测必须考虑：T+1、100股一手、手续费、印花税、滑点、停牌、涨跌停
7. 不允许未来数据产生交易信号
8. 不允许为提高回测结果明显过拟合
9. 每次重大策略修改都应生成策略变更说明

## 推荐的 Codex 工作流

```powershell
# 1. 切到 dev 并同步
git checkout dev
git pull

# 2. 创建实验分支
git checkout -b experiment/etf-rotation

# 3. 用 Codex 开发
codex

# 4. 跑测试
.venv\Scripts\python.exe -m pytest tests/ -v

# 5. 提交前安全检查
git status
git diff --cached --name-only

# 6. 提交
git add <files>
git commit -m "feat: add etf rotation strategy"

# 7. 推送（首次需先完成 GitHub 登录）
git push -u origin experiment/etf-rotation
```

## 提示词模板

给 Codex 的指令应包含约束，例如：

```
在 experiment/etf-rotation 分支实现一个 ETF 轮动策略。

要求：
- 遵守仓库根目录 AGENTS.md 的全部规则
- 回测必须考虑 T+1、100股一手、手续费、印花税、滑点、停牌、涨跌停
- 因子计算禁止使用未来数据
- 配套单元测试放在 tests/
- 不要修改 main / live 分支
- 不要读取或输出任何 .env 内容
```

## 安全提醒

- Codex 不得直接把未经验证的新策略部署到实盘
- 涉及凭证的操作用户必须手动完成
- 提交前务必确认 `git status` 中无 `.env`、`secrets/`、`data/`、`logs/`
