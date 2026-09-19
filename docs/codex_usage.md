# Codex 使用说明（本仓库）

本文件说明如何在本仓库中使用 Codex。

## 实际架构（经 2026-09-19 实测）

Codex 运行在 **WSL 侧**（`codex-cli 0.146.0`，位于 `/home/hermes/.nvm/.../bin/codex`），
不是 Windows 宿主机。项目通过 `/mnt/d/quant-trading` 访问，该路径与
Windows 的 `D:\quant-trading` 是同一个目录（已验证内容一致）。

```
Codex（WSL）
  → /mnt/d/quant-trading（= D:\quant-trading）
  → docker compose exec -T quant-research ...
  → 容器内量化 Python 环境
```

## 启动方式

```bash
cd /mnt/d/quant-trading
codex
```

## 关键前提：沙箱模式（必读）

Codex 默认运行在 **read-only 沙箱**，只能读不能写，且**无法调用 Docker**。

实测三种模式的行为：

| 模式 | 读写文件 | 调用 Docker / 容器 | 适用场景 |
|------|---------|-------------------|---------|
| 默认（read-only） | 只读 | 失败 | 纯阅读代码 |
| `-s workspace-write` | 可写工作区 | **失败** | 改文件 |
| `-s danger-full-access` | 可写 | 成功 | 需要操作容器时 |

在受限沙箱下调用 Docker 会报：

```
<3>WSL (2 - ) ERROR: UtilBindVsockAnyPort:309: socket failed 1
```

这是沙箱阻断了 WSL 与 Docker Desktop 的 vsock 通道，不是容器或依赖的问题。

**因此：需要让 Codex 操作容器时，必须显式指定可访问模式：**

```bash
codex exec -s danger-full-access "docker compose exec -T quant-research pytest tests -q"
```

交互式使用：

```bash
codex -s danger-full-access
```

注意：`danger-full-access` 会放开沙箱限制。当前项目处于 Environment Setup
阶段、禁止策略与回测，风险可控；进入策略开发阶段后应重新评估该模式的
使用范围。

## 当前阶段约束（重要）

项目处于 **Environment Setup 阶段**。Codex 在本仓库内工作时：

**允许：**
- 修改 Docker 配置（`docker/Dockerfile`、`docker-compose.yml`）
- 修改 devcontainer 配置
- 调整 `requirements.txt` 依赖
- 更新 `README.md` / `AGENTS.md` / `docs/`
- 运行环境测试 `pytest tests/test_environment.py`

**禁止：**
- 创建任何交易策略代码
- 运行回测
- 创建模拟盘或实盘相关代码
- 接入券商接口
- 提交 `.env` / `data/` / `logs/` / `secrets/`

完整约束以根目录 `AGENTS.md` 为准，Codex 每次工作前应先读该文件。

## 环境说明

所有 Python 量化依赖只装在 Docker 容器内。
宿主机（Windows）不装量化依赖，**不使用 .venv**。

进入容器（执行单条命令，脚本化场景推荐加 `-T`）：

```bash
docker compose exec -T quant-research bash
```

## 提示词建议

在本阶段，向 Codex 提需求时应明确环境边界，例如：

```
只修改 Docker 配置相关文件，不要创建任何策略或回测代码。
改动后运行 pytest tests -q 验证。
```

## 后续阶段

进入策略研究阶段后，本文件会补充策略开发、回测、验证相关的工作流说明。
当前阶段不涉及。
