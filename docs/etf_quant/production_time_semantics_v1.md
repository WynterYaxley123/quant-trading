# ETF-Quant V1 — 生产时间语义 v1（冻结）

**状态：FROZEN。** 本文件定义 ETF-Quant V1 生产链上每一个时间字段的含义、方向约束与
禁止用法。任何报告、manifest、Dashboard 字段或测试若与本文件冲突，以本文件为准。

---

## 0. 一句话

`2026-09-24` 是**历史工程参照日（HISTORICAL_ENGINEERING_REFERENCE_DATE）**，
不是真实 Shadow 起点。本轮验证出来的行业→ETF 映射、ETF 行情与流动性，
都是在该参照日**之后**才被观测到的，因此**不得**倒填成"9月24日当时已知"。

---

## 1. 三个必须分开的日期概念

| 概念 | 冻结值 / 规则 | 含义 |
|---|---|---|
| `HISTORICAL_ENGINEERING_REFERENCE_DATE` | `2026-09-24` | 冻结工程基线（Source-C / 19 因子 / Ridge H10/H40/H120 / CSI300）的最后一个 finalized 交易日。**只用于标注历史工程证据的截面。** |
| `evidence_observed_at` | 每条映射证据真实被观测到的时刻 | 本轮为 `2026-09-28` 或之后。**不得回填。** |
| `production_ready_from` | Production Candidate 被创建并自校验通过的日期 | 系统"从此刻起"具备启动前瞻 Shadow 的工程条件的起点。 |

`HISTORICAL_ENGINEERING_REFERENCE_DATE` **不是** Shadow epoch 起点，
**不是** 首个 signal date，**不是** 任何 order/fill/holding/NAV/PnL 的日期。

---

## 2. 六个时间字段的正确定义

| 字段 | 定义 | 允许为 NULL？ |
|---|---|---|
| `signal_date` | 产生该信号所用的、**已 finalize** 的交易日 T（收盘后）。 | 否（一旦有信号） |
| `economic_execution_at` | 该信号在经济意义上被执行的时点 = T+1 的实际开盘时刻（09:30，Asia/Shanghai）。 | 否（一旦有执行） |
| `effective_at` | 一条映射关系**在经济上生效**的起始日期。 | 否（VERIFIED 行） |
| `observed_at` | 数据/证据被**本系统**看到的时刻。 | 否 |
| `available_at` | 一条映射关系**可以被本系统合法使用**的最早时刻：必须 `>= observed_at`。 | 否（VERIFIED 行） |
| `processed_at` | 本系统实际完成落盘处理的时刻（真实墙钟）。 | 否 |
| `evidence_observed_at` | 映射/工具性证据（基金合同、指数公司资料等）被实际检索到的时刻。 | 否（VERIFIED 行） |

---

## 3. 排序约束（必须全部成立）

```
source_retrieved_at <= evidence_observed_at <= verified_at <= available_at
effective_at >= date(available_at)          # 不许把今天才知道的关系写成昨天生效
observed_at <= processed_at
economic_execution_at < evidence_available_at <= processed_at
```

第三条是本轮的核心防伪约束：**一条今天才验证出来的映射，其 `effective_at` 不得早于
`available_at` 的日期。** 否则系统会声称"9月24日当时已经拥有这个 verified mapping"，
而这是假的。

---

## 4. 本轮实际发生的时间事实（如实记录）

| 事实 | 时间 |
|---|---|
| 冻结工程参照截面 | `2026-09-24` |
| 冻结工程产物被处理 | `2026-09-28T12:36:24Z`（engineering ridge 报告 `processed_at`） |
| 行业→ETF 映射证据被观测 | `2026-09-28` 及以后（逐条记录 `evidence_observed_at`） |
| ETF 行情被摄取、compact 落盘 | `2026-09-28`（CNEquity lake `fetched_at`） |
| 流动性窗口（20 个交易日） | 以 `2026-09-24` 为最后一个交易日的最近 20 个交易日 |

**结论：** 本轮**没有**、也**不可能**声称 `2026-09-24` 当天系统已经拥有这些映射。
`2026-09-24` 只能作为"如果当时就有今天这套工程条件，历史截面长什么样"的参照。

---

## 5. T+1 语义（保持冻结，未改动）

```
T    finalized close（收盘后数据已 finalize）
  -> signal

T+1  actual open
  -> economic execution

T+1  收盘之后
  -> CNEquity 日线最终证据可获得

DELAYED_T1_OPEN_ACCOUNTING
NOT_REALTIME_EXECUTION_EVIDENCE
```

- **禁止**用 T+1 close / T+2 open / previous close / synthetic open 替代 T+1 actual open。
- 记账模式保持 `DELAYED_EOD_ACTUAL_PROCESSED_AT`：
  `fill.executed_at` 与 `epoch.started_at` 记录**真实处理时刻**，
  而 `market_execution_at` 单独披露为 T+1 09:30。
- 任何 epoch NAV 都不得早于 `epoch.started_at`。

---

## 6. 未来 Shadow 起点的合法规则

```
EARLIEST_LEGAL_SHADOW_START_RULE
```

未来某一交易日 `T` 可以成为**首个正式 Shadow signal day**，当且仅当：

1. Production Candidate 已经创建、冻结并通过独立重读校验；
2. 行业→ETF 映射已验证（`available_at <= T 收盘后的处理时刻`）；
3. 参与组合的每只 ETF 的行情与 20 日流动性准入在该时点成立；
4. `T` 的收盘数据在该时点已 finalize；
5. `T` 所需要的一切输入，在该时点都**已经实际可获得**（不是"事后才知道"）。

本轮**只定义规则**，不启动。`SHADOW_EPOCH_CREATED = FALSE`。

---

## 7. 禁止清单

- 禁止把 `HISTORICAL_ENGINEERING_REFERENCE_DATE` 当作真实运行日。
- 禁止把今天验证的映射倒填成 `2026-09-24` 已知。
- 禁止用 `cutoff`、`observation date`、`first bar date` 冒充 `list_date`。
- 禁止制造 pre-epoch NAV、正式 signal、order intent、fill、holding、NAV、PnL、performance。
- 禁止把"未来历法交易日"当作"未来价格"。
