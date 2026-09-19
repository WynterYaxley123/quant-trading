# Environment Setup 验收报告

**日期**：2026-09-19
**项目**：quant-trading（A股/ETF 量化研究环境）
**状态**：**ENVIRONMENT SETUP COMPLETE**

---

## 1. Dev Container

**结果：成功**

使用现有 `.devcontainer/devcontainer.json`，经 `@devcontainers/cli 0.89.0` 实测
`devcontainer up` 完整流程（等效于 VS Code 的 "Reopen in Container"）：

```json
{"outcome":"success",
 "remoteUser":"mambauser",
 "remoteWorkspaceFolder":"/workspace"}
```

postCreateCommand 输出 `deps ok`（五库导入验证通过）。

| 检查项 | 要求 | 实测 | 结果 |
|--------|------|------|------|
| Reopen / Attach | 正常 | outcome=success | 通过 |
| 容器内工作目录 | /workspace | /workspace | 通过 |
| Python Interpreter | 容器内 3.12 | /opt/conda/bin/python → 3.12.11 | 通过 |
| 终端可用 | 是 | /bin/bash，PATH 首位 /opt/conda/bin | 通过 |
| import hikyuu | 成功 | 2.8.2 | 通过 |
| import rqalpha | 成功 | 6.4.0 | 通过 |
| import akshare | 成功 | 1.18.88 | 通过 |

**本次修正的两处配置错误**（修正前无法正常工作）：

| 项 | 原值 | 修正为 | 原因 |
|----|------|--------|------|
| `python.defaultInterpreterPath` | `/usr/local/bin/python` | `/opt/conda/bin/python` | 原路径在容器内不存在 |
| `remoteUser` | `root` | `mambauser` | 与镜像默认用户一致，避免挂载目录属主混乱 |

未改动任何 Python / Hikyuu / RQAlpha / NumPy 版本。

---

## 2. main / dev 分支

**结果：main 为稳定基线，dev 已对齐并保留**

### 核对过程

| 项 | 结果 |
|----|------|
| dev 是否为 main 的祖先 | 是（dev 无独有提交） |
| dev 独有的有效环境配置 | 无 |
| 需要合并的内容 | 无 |

dev 分支原有两个文件在 main 中不存在，经核对均**不属于当前阶段的有效环境配置**：

| 文件 | 性质 | 处理 |
|------|------|------|
| `docs/strategy_notes.md` | 策略研究日志模板，属下一阶段 | 未合并（当前阶段禁止策略内容） |
| `requirements.lock.txt` | 早期 pip freeze 输出，UTF-16 + CRLF 编码异常，已被 requirements.txt 取代 | 未合并 |

两个文件仍可从旧提交 `3d15f60` 取回，未真正丢失。

### 最终状态

```
  dev  2e16af7  docs(codex): record actual WSL architecture and sandbox-mode findings
* main 2e16af7  docs(codex): record actual WSL architecture and sandbox-mode findings
```

- 两分支均指向 `2e16af7`，main 为当前稳定环境基线
- dev 保留，作为后续开发分支
- 未配置任何远程仓库（GitHub 账号 suspended，符合预期）

---

## 3. Codex 可用性

**结果：可用，但必须显式指定沙箱模式**

### 实际架构（与原始设想不同）

实测发现 Codex **运行在 WSL 侧**，不是 Windows 宿主机：

```
Codex（WSL，codex-cli 0.146.0）
  → /mnt/d/quant-trading  （= Windows D:\quant-trading，已验证同一目录）
  → docker compose exec -T quant-research ...
  → 容器内量化 Python 环境
```

Windows 侧未安装 Codex（`%APPDATA%\npm` 为空）。已按实际架构更新
`docs/codex_usage.md`，未为了让 Codex「住进容器」而改动环境设计。

### 沙箱模式实测（关键发现）

| 模式 | 读写文件 | 调用 Docker / 容器 | 适用场景 |
|------|---------|-------------------|---------|
| 默认（read-only） | 只读 | **失败** | 纯阅读 |
| `-s workspace-write` | 可写 | **失败** | 改文件 |
| `-s danger-full-access` | 可写 | **成功** | 操作容器 |

受限沙箱下调用 Docker 报错：

```
<3>WSL (2 - ) ERROR: UtilBindVsockAnyPort:309: socket failed 1
```

原因：沙箱阻断 WSL 与 Docker Desktop 的 vsock 通道。
**结论：需要 Codex 操作容器时必须加 `-s danger-full-access`。**

### 逐项验收

| 检查项 | 实测结果 | 结果 |
|--------|---------|------|
| 读取 D:\quant-trading | 通过 /mnt/d/quant-trading 正常访问 | 通过 |
| 看到 Git 状态与历史 | 正确输出 3 条提交、工作区干净 | 通过 |
| 读取 README.md / AGENTS.md | 正确读取并总结项目阶段 | 通过 |
| 修改普通/临时文本文件 | read-only 下失败；workspace-write 下成功创建并验证 | 通过（需可写模式） |
| 调用 Docker / docker compose | danger-full-access 下成功 | 通过（需完整权限模式） |
| 容器内 `python --version` | Python 3.12.11 | 通过 |
| 容器内 `pytest tests -q` | 14 passed in 2.38s | 通过 |
| 容器内三库 import | OK 2.8.2 / 6.4.0 / 1.18.88 | 通过 |

### 附带修正

WSL 内 `docker`（无 `.exe` 后缀）会触发 Docker Desktop 的 WSL 集成检查并拒绝执行，
实际二进制为 `docker.exe`。已在 `~/bin/docker` 建立 wrapper（含 WSL→Windows 路径转换），
devcontainer CLI 与 Codex 均通过它正常调用 Docker。

---

## 4. 环境基线汇总

| 项 | 值 |
|----|-----|
| 稳定 commit | `2e16af7` |
| 分支 | main = dev = `2e16af7` |
| Git 工作区 | clean |
| Docker 镜像 | `quant-research:py3.12`（3.17 GB） |
| 容器 | `quant-research`（9200/9201）、`quant-jupyter`（8888），均 running |
| 端口绑定 | 全部 `127.0.0.1`，不对局域网暴露 |
| Python | 3.12.11（`/opt/conda/bin/python`） |
| Hikyuu | 2.8.2 |
| RQAlpha | 6.4.0 |
| AKShare | 1.18.88 |
| NumPy | 2.3.5 |
| pandas | 2.3.3 |
| SciPy | 1.16.3 |
| JupyterLab | 4.4.9（密码认证，哈希存于 .env） |

---

## 5. 下一阶段尚未开始（明确未执行）

以下事项**均未开始**，本阶段未执行任何一项：

- 行情数据准备
- Hikyuu 数据导入
- 策略开发
- 回测
- RQAlpha 交叉验证
- JoinQuant 模拟盘

---

## 6. 遗留待定项

一项需用户决定，非阻塞：

- `docs/strategy_notes.md`（策略日志模板）保留在旧提交 `3d15f60` 中。
  若希望作为下一阶段占位文档提前纳入 main，需用户明确指示后添加。

---

**ENVIRONMENT SETUP COMPLETE**

