# src/ — 源码目录

本目录存放项目自有 Python 源码。

## 当前阶段

项目处于 **Environment Setup 阶段**，本目录为占位，**不含任何策略、因子或交易代码**。

## 后续规划（待用户明确指令）

| 子目录（计划） | 用途 |
|----------------|------|
| `src/data/` | 数据获取与清洗（AKShare） |
| `src/factors/` | 因子计算（如 MAPP） |
| `src/risk/` | 风控指标（TGT / TR / RGrid / ZMB / SL） |
| `src/backtest/` | 回测引擎（当前阶段禁止） |

## 约束

参见根目录 `AGENTS.md`。未经用户明确指令，不得在此创建策略或回测代码。
