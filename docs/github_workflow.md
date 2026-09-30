# GitHub 工作流规划

> 状态：**规划文档。账号当前 suspended，不登录、不配置 remote、不 push。**
> 最后更新：2026-09-19

---

## 1. 当前状态

- GitHub 账号：**suspended**
- 当前只使用 **Local Git**
- **不登录、不创建 remote、不 push、不绕过限制**

但项目必须保持 **GitHub-ready**。

---

## 2. GitHub-ready 的含义

即使当前无 remote，项目结构仍需满足：

| 项 | 要求 | 状态 |
|----|------|------|
| `.gitignore` 完整 | 凭证、数据、日志不入库 | 已完成 |
| `.env.example` 模板 | 所有凭证项为空值 | 已完成 |
| README 完整 | 项目说明、架构、使用方式 | 已完成 |
| 目录结构规范 | 与规划一致 | 已完成 |
| 无硬编码凭证 | 全库扫描 | 已完成 |
| commit 历史清晰 | 语义化提交信息 | 持续保持 |
| 无大文件 | 数据/模型不入库 | 已完成 |

---

## 3. 账号恢复后的流程

```
Local Git
    ↓
创建 Private Repository
    ↓
配置 remote
    ↓
Push
```

**注意：** 账号恢复前不得尝试任何绕过手段。

---

## 4. GitHub 未来作用

1. 代码版本管理
2. 策略展示
3. 因子研究记录
4. 回测报告
5. 项目 README Dashboard
6. GitHub Actions
7. 研究历史

---

## 5. README Dashboard 规划

未来 README 可展示：

| 字段 | 说明 |
|------|------|
| Strategy | 策略名称 |
| Version | 版本号 |
| Status | 状态（研究中 / 已验证 / 已废弃） |
| Annual Return | 年化收益 |
| Max Drawdown | 最大回撤 |
| Sharpe | 夏普比率 |
| Validation | RQAlpha 交叉验证结果 |
| Report | 报告链接 |

**当前不要填写虚假收益。** 该表格在产生真实回测结果前保持空白或标注"未开始"。

---

## 6. 报告归档规划

回测报告随代码入库，路径：

```
reports/backtests/<strategy>/<run_id>/
```

大文件（行情数据、模型权重）**不入库**，由 `.gitignore` 排除。

---

## 7. 分支策略

| 分支 | 用途 | 状态 |
|------|------|------|
| `main` | 稳定环境 + 已验证成果 | 现行 |
| `dev` | 开发主线 | 现行 |
| `experiment/<name>` | 试验性工作 | 按需 |

**不创建** `live` / `production` / `trading` 等任何实盘相关分支。
