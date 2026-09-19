# ChatGPT 标准工作流

> 本文件定义 Windows ChatGPT 在本项目中的标准作业流程。
> 状态：规划文档。当前阶段**不执行**任何策略开发或回测。

---

## 1. 环境前置

所有量化 Python 执行必须通过 `quant-research` 容器：

```bash
cd D:\quant-trading
docker compose up -d
docker compose exec quant-research python --version
```

**不要使用 Windows 全局 Python。**

---

## 2. 典型流程：聚宽策略迁移

### 用户输入示例

```
分析这份聚宽策略并迁移到项目。
```

### ChatGPT 执行步骤

| 步骤 | 动作 | 产出 |
|------|------|------|
| 1 | 阅读原始代码 | 理解策略逻辑 |
| 2 | 解释策略 | 策略原理说明 |
| 3 | 检查未来函数 / 偏差 | 偏差检查结论 |
| 4 | 生成 Strategy Specification | `docs/strategy_specification.md` 填充版 |
| 5 | 创建实验目录 | `experiment/<strategy-name>` |
| 6 | 实现 Hikyuu 版本 | `src/strategies/hikyuu/` |
| 7 | Docker 运行 pytest | 测试通过 |
| 8 | Docker 运行 Hikyuu 回测 | 回测结果 |
| 9 | 分析结果 | 结果分析 |
| 10 | 编写 RQAlpha 验证版 | `src/strategies/rqalpha/` |
| 11 | Docker 运行 RQAlpha 验证 | 验证结果 |
| 12 | 比较结果 | 差异分析 |
| 13 | 生成报告 | `reports/backtests/<strategy>/<run_id>/` |
| 14 | 飞书推送 | 通知（未来） |
| 15 | Git commit | 版本记录 |
| 16 | GitHub push | 远程归档（未来，账号恢复后） |

---

## 3. 原始聚宽代码处理规则

**必须保留原始版本。**

- 存放位置：`src/strategies/imported/joinquant/`
- **ChatGPT 不直接覆盖原始代码**
- 迁移逻辑写入 `src/strategies/hikyuu/`，与原始版本分离

---

## 4. 策略实现目录约定

| 内容 | 目录 |
|------|------|
| 原始聚宽代码（保留原样） | `src/strategies/imported/joinquant/` |
| Hikyuu 实现 | `src/strategies/hikyuu/` |
| RQAlpha 验证版 | `src/strategies/rqalpha/` |

---

## 5. 双框架一致性要求

Hikyuu 实现与 RQAlpha 验证版**必须遵循同一份 Strategy Specification**。

不得在两侧写入不同的参数、不同的标的池或不同的风控规则。
若因框架差异必须不同，需在 Specification 的 `Known Limitations` 中记录。

---

## 6. 常用命令

```bash
# 启动服务
docker compose up -d

# 容器内 Python
docker compose exec quant-research python <script.py>

# 运行测试
docker compose exec quant-research pytest tests -q

# 进入交互式 shell
docker compose exec quant-research bash

# 查看服务状态
docker compose ps
```

---

## 7. 约束

当前阶段（Environment Setup + Workflow Foundation）**禁止**：

- 策略开发
- 因子开发
- 行情数据下载
- Hikyuu 数据导入
- 历史回测
- RQAlpha 回测
- JoinQuant 登录 / 模拟盘
- QMT / MiniQMT
- 券商接口
- 真实交易
- Qlib
- 机器学习模型

本文件当前只定义流程，**不要求执行**。

---

## 8. 相关文档

| 文档 | 用途 |
|------|------|
| `AGENTS.md` | 强制约束 |
| `docs/architecture.md` | 架构与角色定义 |
| `docs/strategy_specification.md` | 策略规格模板 |
| `docs/joinquant_import.md` | 聚宽导入流程 |
| `docs/feishu_integration.md` | 飞书通知规划 |
| `docs/github_workflow.md` | GitHub 工作流规划 |
| `docs/future_quant_api.md` | 未来 API 规划 |
