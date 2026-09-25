# Hikyuu 回测管线（LEVEL A / LEVEL B）

- 状态：**LEVEL A 跑通** —— 数据层就绪，Hikyuu 执行链路打通
- 申万行业数据：**未初始化**，因此完整 `sw_sector_rotation` 信号链路未执行
- 生效日期：2026-09-19

---

## 0. 先读这段：LEVEL A ≠ 策略回测

**LEVEL A 是执行冒烟测试，不是 `sw_sector_rotation` 策略回测。**

| | LEVEL A（已完成） | LEVEL B（未完成） |
|---|---|---|
| 性质 | Hikyuu 执行链路冒烟 | 完整策略回测 |
| 数据 | 真实 ETF 日线 | 真实 ETF + 申万二级行业 |
| 规则 | 极简确定性测试规则（固定均线交叉 + 固定手数 + 固定止损） | `sw_sector_rotation` 完整信号链路 |
| 信号来源 | 无（直接对价格算均线） | 行业因子 → Ridge → ranking → ETF mapping |
| `metadata.run_type` | `execution_smoke` | `strategy_backtest` |
| `metadata.strategy` | `hikyuu_execution_smoke` | `sw_sector_rotation` |
| 输出目录 | `reports/backtests/hikyuu_execution_smoke/<run_id>/` | `reports/backtests/sw_sector_rotation/<run_id>/` |
| 指标可评价策略？ | **否** | 是 |

LEVEL A 的真实结果（510300，2020-01-01 ~ 2024-12-31，初始 100000）：

- `final_value` 99176、`total_return` -0.82%、`max_drawdown` -1.94%、
  `sharpe` -0.27、`trade_count` 85

> ⚠️ 这组数字**只能证明执行链路能跑通**（有真实成交、真实净值曲线），
> **不能用于评价 `sw_sector_rotation` 或其他任何策略的质量。**
> 该规则未做任何参数优化，且 LEVEL B 尚未运行。

这些语义已被代码锁死（见 `tests/backtesting/test_runner_and_result.py`
的 execution_smoke 测试组）：即便有人把 `strategy` 字段误设成策略名，
execution_smoke 运行也**不会**写入策略名目录。

---

## 1. 分层结构

```
src/data/                      公共数据层（项目级，所有策略共享）
├─ schema.py                   canonical schema + 校验
├─ calendar.py                 TradingCalendar
├─ providers/                  HikyuuProvider + hikyuu_preflight
├─ loaders/                    panel_loader（多 provider fallback）
└─ adapters/                   canonical frame → 策略格式

src/backtesting/               框架级回测层
├─ result.py                   标准化结果（BacktestResult/Metadata/Metrics）
├─ runner.py                   编排：discovery/config/framework 选择/错误边界
├─ hikyuu_runner.py            Hikyuu 执行链路
└─ testing/smoke_strategy.py   LEVEL A 冒烟规则（非正式策略）

strategies/sw_sector_rotation/ 策略包（自包含，本轮未修改）

scripts/
├─ quant.py                    统一 CLI
└─ data/init_hikyuu_data.py    行情初始化（pytdx → HDF5）

reports/backtests/<output_dir_name>/<run_id>/   回测输出
                         ↑ execution_smoke 运行强制用 hikyuu_execution_smoke
```

依赖方向严格单向：

```
scripts → backtesting → data → (hikyuu / pandas)
                ↓
         策略包（仅通过 adapter 被调用）
```

`factors/` / `model/` / `risk/` / `temporal_integrity` **不依赖 Hikyuu**。

---

## 2. 数据流

```
pytdx 行情服务器
    ↓ import_data（scripts/data/init_hikyuu_data.py）
HDF5（K线） + SQLite（stock.db 基础信息）
    ↓ preflight（结构一致性检查，防段错误）
StockManager.reload()
    ↓ HikyuuProvider.fetch_daily
canonical frame（date/symbol/OHLCV/amount）
    ↓ Adapter
策略所需 market frame（DatetimeIndex）
    ↓ SWSectorRotationCore（完整链路需要申万数据）
ranking → ETF 候选 → 目标权重
    ↓ Hikyuu System（LEVEL A 当前用确定性 smoke 规则）
TradeManager（订单 / 持仓 / 资金）
    ↓
BacktestResult（标准化输出）
```

---

## 3. LEVEL A 实际使用的 Hikyuu API

全部**实测确认**（非文档推断）：

| API | 用途 | 说明 |
|---|---|---|
| `hikyuu.load_hikyuu()` | 装载数据 | 读 `~/.hikyuu/hikyuu.ini` |
| `StockManager.instance()` | 取单例 | |
| `sm['sh510300']` | 取证券 | **必须带市场前缀** |
| `stk.get_kdata(Query)` | 取 K线 | |
| `kd.get_datetime_list()` | 交易日序列 | 日历的主来源 |
| `hikyuu.Query(Datetime, Datetime)` | 查询区间 | **必须用显式 Datetime** |
| `hikyuu.crtTM(init_cash=)` | 交易账户 | cost_func 默认 TC_Zero |
| `hikyuu.SG_Cross(fast, slow)` | 信号 | smoke 规则 |
| `hikyuu.MM_FixedCount(n)` | 资金管理 | 固定手数 |
| `hikyuu.ST_FixedPercent(p)` | 止损 | |
| `hikyuu.SYS_Simple(tm,sg,mm,st)` | 系统 | |
| `sys.run(stk, query)` | 执行回测 | |
| `tm.get_trade_list()` | 成交记录 | 字段 `real_price` 非 `price` |
| `tm.get_funds_curve(DatetimeList)` | 资金曲线 | **只接受 DatetimeList** |
| `tm.first_datetime` / `last_datetime` | 区间 | |

### 为什么用 System 而不是 Portfolio

任务书第十节要求以实际行为为准。本轮选择理由：

1. **LEVEL A 的目标是验证执行引擎**，单标的 `System + TradeManager`
   已完整覆盖「KData → 信号 → 订单 → 持仓 → 资金」全链路。
2. `Portfolio` 的价值在**多标的资金分配**，而 `sw_sector_rotation`
   的多 ETF 轮动需要申万行业数据产生 ranking —— 本轮未初始化该数据，
   强行上 Portfolio 只会得到一个假的组合。
3. Hikyuu 的 `default.pf.*` part（如 `base_最低单因子轮动`）是现成的
   组合模板，但它自带选股逻辑，**会污染策略核心**，本轮不引入。

**结论**：`Portfolio` 待申万数据就绪、需要真实多 ETF 轮动时再评估。
届时报告必须说明该决策。

---

## 4. 实测踩坑（已固化进代码）

| # | 现象 | 处理 |
|---|---|---|
| 1 | `import_stock_name(..., ['fund'])` 抛 ValueError | 必须传 `['stock','fund']` |
| 2 | `sm['510300']` 返回空 Stock 且不报错 | 必须补 `sh`/`sz` 前缀 |
| 3 | `stock.db` 与 HDF5 不一致 → `reload()` 段错误 exit 139 | `preflight()` 前置检查 |
| 4 | `stock.endDate=99999999` 写入 `Market.lastDate` → 市场加载失败 | 从 HDF5 实际读最新日期 |
| 5 | `sym in sm` 恒返回 False | 直接索引 + 检查 `.valid` |
| 6 | `TradeRecord.price` 不存在 | 字段是 `real_price` |
| 7 | `tm.get_funds_curve(Query)` 类型错误 | 只接受 `DatetimeList` |
| 8 | `Query(20200101, 20241231)`（int）导致 `get_funds_curve` 返回空 | 必须用显式 `Datetime` |
| 9 | `tm.get_max_pull_back()` 在未平仓时返回 0.0 | 自行从资金曲线算回撤 |
| 10 | `get_performance()` 部分日期参数下全 0 | 不使用，自算指标 |
| 11 | `tm.get_trade_list()` 首条是 `BUSINESS.INIT` | 过滤，不计入成交 |

---

## 5. 回测输出标准

`reports/backtests/<output_dir_name>/<run_id>/`（`output_dir_name` 由
`metadata.run_type` 决定）：

| 文件 | 内容 | 备注 |
|---|---|---|
| `metadata.json` | 策略/运行类型/框架/commit/区间/数据源/成本/未建模项 | 完整可追溯；含 `run_type` 区分 smoke 与正式回测 |
| `metrics.json` | 指标 | 不支持项为 `null` |
| `trades.csv` | 成交记录 | 真实字段 |
| `positions.csv` | 历史持仓 | |
| `equity_curve.csv` | 日频资金曲线 | |
| `yearly_returns.csv` | 分年收益 | LEVEL A 为空表（未实现分年聚合） |
| `report.md` | 人类可读报告 | 显式标注 unsupported 与未建模项 |

### metrics 支持情况（LEVEL A）

| 指标 | 状态 | 来源 |
|---|---|---|
| `initial_cash` | ✅ | 请求参数 |
| `final_value` | ✅ | 资金曲线末值 |
| `total_return` | ✅ | 自算 |
| `annual_return` | ✅（≥60 交易日才计算） | 自算，年化 252 日 |
| `max_drawdown` | ✅ | 自算（min(equity/cummax-1)） |
| `volatility` | ✅（≥60 交易日） | 自算，日收益 std × √252 |
| `sharpe` | ✅（≥60 交易日） | 自算，无风险利率按 0 |
| `trade_count` | ✅ | `get_trade_list()` 过滤 INIT |
| `commission` | ✅（当前为 0） | `cost.total` 求和 |
| `slippage` | ❌ `null` | crtTM 默认 TC_Zero，未单独建模 |
| `execution_time` | ✅ | 墙钟时间 |

**规则**：样本不足 60 个交易日时年化/波动/Sharpe 一律 `null`，
**绝不用 0 冒充**。

---

## 6. 本轮未完成事项（如实记录）

| 项 | 状态 | 原因 |
|---|---|---|
| 申万二级行业数据 | ❌ 未初始化 | 本轮范围外 |
| `sw_sector_rotation` 完整信号链路 | ❌ 未执行 | 依赖申万数据 |
| 复权因子 | ❌ 未导入 | 见 `market_data_policy.md` |
| 涨跌停建模 | ❌ 未做 | 同上 |
| 停牌建模 | ❌ 未做 | 同上 |
| 多标的组合资金分配 | ❌ 未做 | 见第 3 节 |
| 分年收益聚合 | ❌ 未实现 | `yearly_returns.csv` 为空表 |
| RQAlpha 接入 | ❌ 未做 | 本轮明确不做 |
| 数据内容哈希 | ❌ 未做 | 仅记录导入时间 |

---

## 7. 复现步骤

```bash
# 1. 初始化行情（需要网络，幂等，可重复执行）
docker compose exec quant-research python scripts/data/init_hikyuu_data.py --all-etf

# 2. 查看策略与框架
docker compose exec quant-research python scripts/quant.py strategies
docker compose exec quant-research python scripts/quant.py frameworks

# 3. 跑 LEVEL A 执行冒烟（当前 --framework hikyuu 只产生 execution_smoke 结果）
#    注意：这不是 sw_sector_rotation 策略回测，输出到
#    reports/backtests/hikyuu_execution_smoke/<run_id>/，
#    metadata 为 strategy=hikyuu_execution_smoke, run_type=execution_smoke
docker compose exec quant-research python scripts/quant.py backtest \
    --strategy sw_sector_rotation --framework hikyuu \
    --start 2020-01-01 --end 2024-12-31 \
    --initial-cash 100000 --output-root reports/backtests

# LEVEL B（sw_sector_rotation 完整策略回测）当前不可运行 —— 申万行业数据未初始化。

# 4. 测试
docker compose exec quant-research python -m pytest              # 离线
docker compose exec quant-research python -m pytest -m integration  # 需已初始化行情
```
