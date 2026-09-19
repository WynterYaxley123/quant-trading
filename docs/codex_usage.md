# Codex 使用说明（本仓库）

本文件说明如何在本仓库中使用 Codex。

## 启动方式

在本仓库根目录启动 Codex，使其能读取 `AGENTS.md` 约束：

```powershell
cd D:\quant-trading
codex
```

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

进入容器：

```bash
docker compose run --rm quant-research bash
```

## 提示词建议

在本阶段，向 Codex 提需求时应明确环境边界，例如：

```
只修改 Docker 配置相关文件，不要创建任何策略或回测代码。
改动后运行 pytest tests/test_environment.py 验证。
```

## 后续阶段

进入策略研究阶段后，本文件会补充策略开发、回测、验证相关的工作流说明。
当前阶段不涉及。
