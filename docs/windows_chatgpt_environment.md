# Windows ChatGPT / Codex 环境说明

> 本文件记录 Windows 端 ChatGPT/Codex 应用的配置事实与风险提示。
> **本轮只记录，不修改任何配置。**

---

## 1. 应用信息

| 项 | 值 |
|----|----|
| 应用类型 | Windows 端 ChatGPT / Codex 桌面应用 |
| Appx 包名 | `OpenAI.Codex_2p2nqsd0c76g0` |
| 安装目录 | `C:\Users\Lenovo\AppData\Local\OpenAI\Codex\` |
| 版本 | `codex-cli 0.155.0-alpha.2.6` |
| 配置目录 | `C:\Users\Lenovo\.codex\` |
| 配置文件 | `C:\Users\Lenovo\.codex\config.toml` |

---

## 2. config.toml 当前状态（只记录）

当前 `config.toml` 中包含：

```toml
sandbox_mode = "danger-full-access"
```

以及：

```toml
model_reasoning_effort = "high"
```

### 风险说明

`sandbox_mode = "danger-full-access"` 是**全局配置**，
意味着该应用在**所有项目**中都继承高权限执行能力，
而不仅是本量化项目。

**建议：**

- 未来可按项目或按需收紧该设置
- 尤其是当 ChatGPT 被用于处理外部来源代码（如聚宽导入策略）时，
  应评估是否需要更严格的沙箱

**本轮决定：**

- 不修改 `config.toml`
- 不改变 ChatGPT 当前执行权限

---

## 3. 对量化项目的实际影响

对本项目（`D:\quant-trading`）而言，高权限是**便利的**：

| 操作 | 是否需要放开沙箱 |
|------|-----------------|
| 读写 `D:\quant-trading` 文件 | 需要（常规） |
| 调用 `docker compose exec` | **需要**（沙箱会阻断） |
| 执行容器内 Python | 需要（经由 docker 命令） |

对比 WSL codex-cli：WSL 侧必须显式加 `-s danger-full-access`
才能通过 vsock 调用 Docker；而 Windows 端是全局已放开。
这是两者行为差异的根源，详见 `docs/codex_usage.md`。

---

## 4. 相关文档

| 文档 | 用途 |
|------|------|
| `docs/chatgpt_workflow.md` | ChatGPT 标准工作流与开发链路 |
| `docs/codex_usage.md` | WSL codex-cli 备用工具说明 |
| `AGENTS.md` 第四节 | 代码开发入口强制规则 |
