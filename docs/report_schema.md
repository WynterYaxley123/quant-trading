# 报告目录结构规范

> 本文件定义研究结果的统一输出标准。
> **当前只建立 schema 与模板，不生成任何策略结果。**

---

## 1. 顶层结构

```
reports/
├─ strategies/      策略规格与说明汇总
├─ backtests/       回测结果
├─ factors/         因子研究结果
├─ comparisons/     双框架交叉验证比较
└─ daily/           日常研究记录
```

---

## 2. 标准回测目录

```
reports/backtests/<strategy>/<run_id>/
├─ metadata.json          运行元信息
├─ metrics.json           核心指标
├─ trades.csv             成交明细
├─ positions.csv          持仓记录
├─ equity_curve.csv       净值曲线
├─ yearly_returns.csv     分年度收益
├─ report.md              分析报告
├─ equity_curve.png       净值图
└─ drawdown.png           回撤图
```

`<strategy>`：策略名称（下划线小写）
`<run_id>`：运行标识，建议 `YYYYMMDD_HHMMSS_<framework>`
例如 `20260919_153000_hikyuu`

---

## 3. metadata.json schema

```json
{
  "strategy": "",
  "version": "",
  "framework": "",
  "run_id": "",
  "started_at": "",
  "finished_at": "",
  "specification": "docs/specs/<strategy>.md",
  "git_commit": "",
  "data_range": {"start": "", "end": ""},
  "universe": "",
  "benchmark": "",
  "status": ""
}
```

| 字段 | 说明 |
|------|------|
| `framework` | `hikyuu` 或 `rqalpha` |
| `specification` | 对应 Strategy Specification 路径 |
| `git_commit` | 运行时代码版本 |
| `status` | `success` / `failed` / `partial` |

---

## 4. metrics.json schema

```json
{
  "annual_return": null,
  "total_return": null,
  "max_drawdown": null,
  "sharpe": null,
  "sortino": null,
  "calmar": null,
  "volatility": null,
  "win_rate": null,
  "turnover": null,
  "trade_count": null
}
```

---

## 5. trades.csv 列定义

| 列 | 说明 |
|----|------|
| `datetime` | 成交时间 |
| `symbol` | 标的代码 |
| `side` | buy / sell |
| `price` | 成交价 |
| `volume` | 成交量 |
| `amount` | 成交额 |
| `commission` | 手续费 |
| `pnl` | 平仓盈亏 |

---

## 6. positions.csv 列定义

| 列 | 说明 |
|----|------|
| `datetime` | 时间 |
| `symbol` | 标的代码 |
| `volume` | 持仓量 |
| `avg_cost` | 持仓成本 |
| `market_value` | 市值 |
| `weight` | 仓位权重 |

---

## 7. equity_curve.csv 列定义

| 列 | 说明 |
|----|------|
| `datetime` | 时间 |
| `equity` | 账户净值 |
| `benchmark` | 基准净值 |
| `drawdown` | 当期回撤 |

---

## 8. yearly_returns.csv 列定义

| 列 | 说明 |
|----|------|
| `year` | 年份 |
| `strategy_return` | 策略收益 |
| `benchmark_return` | 基准收益 |
| `excess_return` | 超额收益 |

---

## 9. comparisons/ 结构

双框架交叉验证比较：

```
reports/comparisons/<strategy>/
├─ comparison.md         差异分析
└─ comparison.json       指标对照
```

`comparison.json` schema：

```json
{
  "strategy": "",
  "version": "",
  "hikyuu_run": "",
  "rqalpha_run": "",
  "metrics": {
    "annual_return": {"hikyuu": null, "rqalpha": null, "diff": null},
    "max_drawdown": {"hikyuu": null, "rqalpha": null, "diff": null},
    "sharpe": {"hikyuu": null, "rqalpha": null, "diff": null}
  },
  "validation": "",
  "notes": []
}
```

`validation` 取值：`PASS` / `FAIL` / `REVIEW`

---

## 10. 内容规则

1. **禁止**手工编造指标数据
2. 所有 `null` 表示尚未产生结果，不得用 0 或估计值替代
3. 每次运行生成独立 `<run_id>` 目录，**不覆盖**历史运行
4. 报告必须记录 `git_commit`，保证可复现
5. 大文件（原始行情、模型权重）不入库

---

## 11. 模板文件

Schema 模板位于 `scripts/automation/report_schema/`，仅作结构参考，
**不含任何策略数据**。
