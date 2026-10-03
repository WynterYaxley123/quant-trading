# WSL codex-cli 备用工具说明

> **定位：OPTIONAL FALLBACK TOOL（可选备用工具）**
>
> 本文件**不是**主工作流文档。
> 项目主要开发入口是 **Windows 端 ChatGPT**，详见 `docs/chatgpt_workflow.md`。
>
> 本文档记录 WSL codex-cli 的技术事实，仅供备用场景参考。

---

## 1. 为什么不作为主入口

- 主要开发工作由 Windows ChatGPT 承担
- codex-cli 在 WSL 内运行，需特殊模式才能调用 Docker
- 其 `-s danger-full-access` 会放开沙箱限制

**因此，不得在 README 或主工作流中把 `codex -s danger-full-access`
写成普通开发的前置步骤。**

### 与 Windows ChatGPT 的对比

| 项 | Windows ChatGPT（主） | WSL codex-cli（备用） |
|----|----------------------|----------------------|
| Docker 通道 | Windows named pipe | WSL vsock |
| 是否需要 danger-full-access | **否** | 是 |
| 是否需要 `~/bin/docker` wrapper | **否** | 是 |
| 是否主工作流 | **是** | 否 |

Windows 端走 `npipe:////./pipe/dockerDesktopLinuxEngine`，
不经过 WSL vsock，因此上表右列的所有 WSL 专有配置对主工作流**均不适用**。

---

## 2. 实际架构（经 2026-09-19 实测）

```
codex-cli（WSL，0.146.0）
  → /mnt/d/quant-trading  （= Windows D:\quant-trading，已验证同一目录）
  → docker compose exec -T quant-research ...
  → 容器内量化 Python 环境
```

二进制位置：`/home/hermes/.nvm/versions/node/v22.22.3/bin/codex`
Windows 宿主机**未安装** Codex。

---

## 3. 沙箱模式技术事实

| 模式 | 读写文件 | 调用 Docker / 容器 | 适用场景 |
|------|---------|-------------------|---------|
| 默认（read-only） | 只读 | **失败** | 纯阅读 |
| `-s workspace-write` | 可写工作区 | **失败** | 改文件 |
| `-s danger-full-access` | 可写 | 成功 | 需操作容器时 |

受限沙箱下调用 Docker 报错：

```
<3>WSL (2 - ) ERROR: UtilBindVsockAnyPort:309: socket failed 1
```

原因：沙箱阻断 WSL 与 Docker Desktop 的 vsock 通道，
不是容器或依赖的问题。

---

## 4. docker wrapper 技术记录（保留）

WSL 内直接调用 `docker`（无 `.exe` 后缀）会触发 Docker Desktop
的 WSL 集成检查并拒绝执行，报：

```
The command 'docker' could not be found in this WSL 2 distro.
```

实际二进制为 `docker.exe`。wrapper 位于 `~/bin/docker`，职责：

1. 调用真实二进制
   `/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe`
2. 把 WSL 路径参数（`/mnt/d/...`）转换成 Windows 路径（`D:\...`）

原因：`docker.exe` 是 Windows 程序，收到 `/mnt/d/...` 会误解析为
`D:\mnt\d\...`，导致 devcontainer CLI 等工具报路径不存在。

**该 wrapper 是 devcontainer CLI 与 codex-cli 能正常调用 Docker 的前提。**

---

## 5. 备用场景示例

仅在主入口不可用时使用：

```bash
cd /mnt/d/quant-trading
codex exec -s danger-full-access "docker compose exec -T quant-research pytest tests -q"
```

交互式：

```bash
codex -s danger-full-access
```

注意：`danger-full-access` 放开沙箱限制。当前项目禁止策略与回测，
风险可控；进入策略开发阶段后应重新评估使用范围。

---

## 6. 常规使用（只读/改文件）

不需要容器时，用普通模式即可：

```bash
codex                          # 只读
codex -s workspace-write       # 可写工作区文件
```

---

## 7. 相关文档

| 文档 | 用途 |
|------|------|
| `docs/architecture.md` | 架构与角色定义（含 codex-cli 定位） |
| `docs/chatgpt_workflow.md` | 主开发工作流 |
| `docs/environment_setup_report.md` | 环境验收报告 |
