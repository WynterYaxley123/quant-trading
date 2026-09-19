# src/ — 框架源码目录

本目录存放**框架级** Python 源码，即与具体策略无关的基础设施。

## 当前阶段

项目处于 **ENVIRONMENT + QUANT WORKFLOW FOUNDATION** 阶段。
框架已建立，策略开发尚未开始。

**策略代码不在这里。** 所有策略（含从 Legacy china-market-data 迁移的
SW Sector Rotation Core）位于顶层 `strategies/` 下的自包含策略包。

## 目录结构

```
src/
├─ notifications/        通知（飞书骨架已就位，框架基础设施）
├─ data/                 数据获取与清洗入口（预留）
└─ strategies/           第三方策略导入插槽
   └─ myquant/           掘金量化策略（预留，含 Token 管理规范）
```

## 与 strategies/ 的分工

| 目录 | 职责 |
|------|------|
| `src/` | 框架基础设施：通知、数据入口、第三方导入插槽 |
| `strategies/` | 各个自包含策略包，每个含自己的代码/配置/测试/文档 |

**原则**：有真实职责才保留目录。不为"未来可能使用"保留空骨架。

复用需求出现**之前**不做共享抽象。若将来两个以上策略需要同一份逻辑，
再考虑提升到框架层。

## 所有权

- `src/notifications/` 属于基础设施，由 Hermes 维护。
- `strategies/` 下的策略包默认属于 ChatGPT（主要开发 Agent）。
- **Hermes 未经用户明确要求，不得主动修改策略代码。**

## 约束

参见根目录 `AGENTS.md`。
未经用户明确指令，不得在此创建策略或回测代码。

## 相关文档

| 文档 | 用途 |
|------|------|
| `AGENTS.md` | 项目强制约束（含目录所有权） |
| `docs/architecture.md` | 架构与角色定义 |
| `docs/chatgpt_workflow.md` | 开发工作流 |
| `strategies/README.md` | 策略包索引 |
