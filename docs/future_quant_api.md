# 未来量化 API / MCP 规划

> 状态：**纯规划文档。当前不实现任何 MCP 或 API。**
> 最后更新：2026-09-19

---

## 1. 当前明确不开发

**不开发 `hikyuu-mcp`。**

原因：Windows ChatGPT 可以直接完成：

```
项目代码
    ↓
Docker
    ↓
Hikyuu
```

不需要 MCP 就能开发。

---

## 2. 未来触发条件

当以下任一方需要调用量化系统时，才考虑实现统一接口：

- Hermes
- 飞书
- 其他 Agent

---

## 3. 统一设计方向

**统一设计为 `quant-mcp` 或 `Quant API Gateway`。**

关键约束：**面向整个 quant-trading 项目，不绑定单一 Hikyuu。**

```
quant-mcp / Quant API Gateway
        │
        ├─ Hikyuu
        ├─ RQAlpha
        ├─ 报告系统
        └─ 项目状态
```

---

## 4. 未来可能暴露的接口

| 接口 | 用途 |
|------|------|
| `get_project_status` | 项目当前状态 |
| `list_strategies` | 列出策略 |
| `get_latest_report` | 获取最新报告 |
| `run_validation` | 触发验证 |
| `get_run_status` | 查询运行状态 |
| `get_environment_status` | 环境状态 |
| `send_report` | 发送报告通知 |

---

## 5. 禁止开放的接口

以下能力**一律禁止**通过 MCP / API 暴露：

| 禁止项 | 原因 |
|--------|------|
| 任意 shell | 远程代码执行风险 |
| 任意 Python exec | 同上 |
| 密码 | 凭证泄露 |
| Token | 凭证泄露 |
| 真实券商直接交易能力 | 资金安全 |

---

## 6. 设计原则（未来实现时）

1. **白名单接口**：只暴露预定义操作，不接受任意代码
2. **只读优先**：查询类接口不改变项目状态
3. **副作用接口需确认**：`run_validation` 等需明确触发
4. **凭证隔离**：API 层不持有券商凭证
5. **审计日志**：所有调用记录到 `logs/`

---

## 7. 当前行动

**只写本规划文档。不实现 MCP，不建立 API 服务，不添加依赖。**

未来实现时需用户明确指令。
