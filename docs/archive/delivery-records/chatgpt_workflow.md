# ChatGPT 标准工作流

> 2026-10-02 索引说明：以下保留基础环境阶段的开发流程。
> 当前产品的只读启动命令、Research 空状态与三个服务的进程管理见[统一控制台](unified_console.md)。
> 量化执行仍使用冻结 Docker 环境；本次控制台启动不触发 runner。

> 本文件定义 Windows ChatGPT 在本项目中的标准作业流程。
> 状态：规划文档。当前阶段**不执行**任何策略开发或回测。

---

## 1. 环境前置

### 正式开发链路

```
User
  ↓
Windows ChatGPT            （主要开发 Agent）
  ↓
D:\quant-trading           （Windows 侧项目路径）
  ↓
Docker Desktop             （Windows named pipe）
  ↓
quant-research             （量化执行容器，/workspace）
  ↓
Hikyuu / RQAlpha / AKShare
```

### 关键事实：Windows named pipe

Windows 端 ChatGPT 调用 Docker Desktop，走的是 **Windows named pipe**：

```
npipe:////./pipe/dockerDesktopLinuxEngine
```

**不经过 WSL vsock。**

因此以下 WSL 专有内容，**都不是** Windows ChatGPT 主工作流的必要条件：

| WSL 专有内容 | 说明 |
|--------------|------|
| `-s danger-full-access` | WSL 沙箱阻断 vsock 才需要 |
| `UtilBindVsockAnyPort` 报错 | WSL 特有 |
| `~/bin/docker` wrapper | WSL → docker.exe 路径转换才需要 |

这些只保留在备用文档 `docs/codex_usage.md` 中，不出现在主流程的必备步骤里。

### 前置检查

```bash
cd D:\quant-trading
docker compose up -d
docker compose exec quant-research python --version
```

**不要使用 Windows 全局 Python。**

### Docker CLI 路径

`C:\Program Files\Docker\Docker\resources\bin` 已在 Machine PATH 注册表中。
若当前进程继承旧环境快照而找不到 `docker`，使用完整路径：

```
"C:\Program Files\Docker\Docker\resources\bin\docker.exe" compose ps
"C:\Program Files\Docker\Docker\resources\bin\docker.exe" compose exec quant-research python --version
```

重启 ChatGPT/Codex 应用后，PATH 生效即可直接使用 `docker`。
**PATH 缺失不代表 Docker 不可用。**

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
| 5 | 创建实验分支 | `experiment/<strategy-name>` |
| 6 | 创建自包含策略包 | `strategies/<strategy_name>/` |
| 7 | 实现 Hikyuu 版本 | 策略包内 `src/` |
| 8 | Docker 运行 pytest | 测试通过 |
| 9 | Docker 运行 Hikyuu 回测 | 回测结果 |
| 10 | 分析结果 | 结果分析 |
| 11 | 编写 RQAlpha 验证版 | 策略包内 `src/` |
| 12 | Docker 运行 RQAlpha 验证 | 验证结果 |
| 13 | 比较结果 | 差异分析 |
| 14 | 生成报告 | `reports/backtests/<strategy>/<run_id>/` |
| 15 | 飞书推送 | 通知（未来） |
| 16 | Git commit | 版本记录 |
| 17 | GitHub push | 远程归档（未来，账号恢复后） |

---

## 3. 原始聚宽代码处理规则

**必须保留原始版本。**

- 存放位置：策略包内 `strategies/<strategy_name>/src/original/`
  （原始聚宽代码，**只读，不覆盖**）
- **ChatGPT 不直接覆盖原始代码**
- 迁移后的实现写入策略包内 `src/`，与原始版本分离

---

## 4. 策略实现目录约定

每个策略是**自包含策略包**：

| 内容 | 目录 |
|------|------|
| 原始聚宽代码（保留原样，只读） | `strategies/<name>/src/original/` |
| 迁移实现（Hikyuu） | `strategies/<name>/src/` |
| RQAlpha 验证版 | `strategies/<name>/src/`（框架 adapter） |
| 策略配置 | `strategies/<name>/config/` |
| 策略测试 | `strategies/<name>/tests/` |
| 策略文档 | `strategies/<name>/docs/` |

策略包之间互相独立，共同位于顶层 `strategies/`。
框架基础设施在顶层 `src/`，两者分离。参见 `strategies/README.md`。

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
