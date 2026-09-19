# src/ — 源码目录

本目录存放项目自有 Python 源码。

## 当前阶段

项目处于 **Environment Setup + Workflow Foundation 阶段**。
本目录已建立结构，**不含任何策略、因子或交易代码**。

## 目录结构

```
src/
├─ strategies/           策略实现
│  ├─ imported/
│  │  └─ joinquant/      原始聚宽代码（只读，不覆盖）
│  ├─ hikyuu/            Hikyuu 实现（主研究）
│  └─ rqalpha/           RQAlpha 验证版（独立验证）
├─ factors/              因子计算
├─ signals/              信号生成
├─ risk/                 风控指标（TGT / TR / RGrid / ZMB / SL）
├─ portfolio/            组合与仓位管理
├─ adapters/             框架适配层
├─ reporting/            报告生成
├─ notifications/        通知（飞书骨架已就位）
├─ common/               通用工具
└─ data/                 数据获取与清洗
```

## 所有权

以下目录**默认属于 ChatGPT**（主要开发 Agent）：

```
src/strategies/
src/factors/
src/signals/
src/risk/
src/portfolio/
```

**Hermes 未经用户明确要求，不得主动修改上述核心研究代码。**

`src/notifications/` 属于基础设施，由 Hermes 维护。

## 约束

参见根目录 `AGENTS.md`。
未经用户明确指令，不得在此创建策略或回测代码。

## 相关文档

| 文档 | 用途 |
|------|------|
| `docs/architecture.md` | 架构与角色定义 |
| `docs/chatgpt_workflow.md` | 开发工作流 |
| `docs/strategy_specification.md` | 策略规格模板 |
