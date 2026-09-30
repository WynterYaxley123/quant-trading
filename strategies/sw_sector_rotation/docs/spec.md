# SW Sector Rotation Core —— 策略规格

| 项 | 值 |
|----|-----|
| **Name** | SW Sector Rotation Core |
| **Source** | Legacy china-market-data v5 |
| **Release commit** | `1923f9d0fb00eeece9538ae1d0af9db57bbb02d5` |
| **Status** | **CORE AUDITED / RESEARCH DECISIONS REQUIRED / NOT YET BACKTESTED** |
| **Universe** | 申万二级行业（Shenwan Level-2 sectors） |
| **Model** | Cross-sectional Ridge ranking |
| **Horizons** | 10 / 40 / 120 trading days |

> **重要**：本文档中所有参数均为 **LEGACY INITIAL DEFAULT**，不是最终最优值。
> 任何 legacy 历史收益数字都**不得**引用为当前系统业绩。
> 全部标记 **LEGACY REFERENCE ONLY**。

---

## 1. 目标命题

预测**行业的相对排名**，而不是预测绝对涨跌。

这是研究目标，不等于当前回归 target：代码实际预测 absolute forward return 后排序。
本轮未更换 target；市场 Beta 风险与后续决策见 [核心审计报告](core_hardening_report.md)。

```
行业数据 (OHLCVA)
  ↓ 因子
  ↓ 横截面模型
行业 ranking
  ↓ ETF mapping
组合
```

这是一个**横截面排名**策略：模型只需要把相对更强的行业排到前面，
不需要预测大盘方向。绝对涨跌由风险状态与仓位管理处理（见第 6 节）。

---

## 2. 数据接口

核心算法接受统一 **canonical market frame**：

| 列 | 含义 |
|----|------|
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价 |
| `volume` | 成交量 |
| `amount` | 成交额 |

- index 必须为升序 `DatetimeIndex`。
- 校验函数：`strategies.sw_sector_rotation.src.factors.sector_rotation.validate_market_frame()`
- **本阶段不迁移任何数据下载代码**，只建立输入接口。
  数据层未来由 quant-trading 提供（Hikyuu / AKShare）。

Hikyuu 侧的转换见 `strategies.sw_sector_rotation.src.adapters.hikyuu.sector_rotation.kdata_to_market_frame()`。

---

## 3. Active Factors（全部来自 legacy 源码确认）

### 3.1 MA deviation（价格相对均线位置）

```
d5 / d10 / d20 / d60 / d120 = (close - MA_n) / MA_n
```

实现：`strategies.sw_sector_rotation.src.factors.sector_rotation.compute_ma_features()`

### 3.2 Range position（MAPP 稳位置）

```
p5 / p10 / p20 / p60 / p120 = (close - min_n) / (max_n - min_n)   # clip 到 [0,1]
```

### 3.3 Trend alignment

```
align = ( MA5 > MA10 ) * 3 + ( MA10 > MA20 ) * 2 + ( MA20 > MA60 ) * 1
align = align / 6      # 归一化到 [0,1]
```

### 3.4 Volatility

```
v5  = 日收益 5 日滚动标准差
v20 = 日收益 20 日滚动标准差
vc  = v5 / (v20 + eps)
```

### 3.5 Reversal

```
rev5  = - 过去 5 日平均收益
rev10 = - 过去 10 日平均收益
rsi   = RSI(14)
```

### 3.6 RSRS

```
对每个 t，取 [t-n+1, t] 的 high/low 做 OLS: low = alpha + beta * high
z_t  = ( beta_t - mean(beta[t-m:t]) ) / std(beta[t-m:t])     # 窗口严格不含 t
RSRS = z_t * beta_t * R2_t
```

默认 `n = 18`、`m = 600`。实现：`strategies.sw_sector_rotation.src.factors.rsrs.compute_rsrs()`

RSRS 当前计算为诊断列，但不在默认 19 列 `TRAIN_FEATURES_PRICE` 中，本轮未加入训练。

**关键**：z-score 窗口为 `[t-m, t)`，**严格不含当前值**，有单元测试守护
（`test_rsrs_zscore_window_excludes_current_value`）。

### 3.7 Drawdown

```
dd20 = close / max(close, 20) - 1
dd60 = close / max(close, 60) - 1
```

### 3.8 Optional（默认关闭）

| 因子 | 状态 | 说明 |
|------|------|------|
| Macro PIT | **disabled by default** | 时点对齐算法已迁移，`macro_enabled=false`，本次不下载宏观数据 |
| Fund flow post-hoc | **disabled by default** | `apply_flow_adjustment(score, flow_net)`，修正限制 ±0.02，**不得进入历史训练** |

---

## 4. Disabled / 不迁移的因子

| 类别 | 因子 | 原因 |
|------|------|------|
| **纯动量** | `m5` / `m20` / `m60` / `accel` | legacy 实验已消融 |
| **量比** | `vr5` / `vr20` / 旧 volume ratio | legacy 实验已消融 |
| **基本面** | `profit_growth` / `roe` / `pb_inv` | legacy 没有可靠的逐公司 point-in-time 财报快照 |

### 基本面重新启用原则

> **基本面数据只有在未来建立严格 PIT 数据集后，才允许重新加入训练。**

代码层面强制：`SWSectorRotationConfig(include_fundamentals=True)` 会抛
`ValueError`；`validate_train_features()` 会拒绝含被禁特征的训练集。

---

## 5. Model

### 5.1 结构

三个周期**各独立训练一个 Ridge**：

| 周期 | 预测交易日数 |
|------|--------------|
| short | 10 |
| medium | 40 |
| long | 120 |

训练样本组织：**全部行业 × 滚动训练窗口内的日期** 堆叠成一个矩阵。
标签：`close[calendar[pos(t)+h]] / close[t] - 1`，未来对应周期的行业绝对收益。
缺失端点保留 NaN。每个有效 date × sector 样本同权，覆盖率可查；不进行全截面去均值。

### 5.2 初始超参（LEGACY INITIAL DEFAULT）

```
ridge_alpha   = 0.01
train_months  = 6
top_n         = 5
fusion_weights: short 0.25 / medium 0.50 / long 0.25
min_train_dates = 30        # 至少 30 个有效训练日期才允许训练
```

> 这些只能作为 **LEGACY INITIAL DEFAULT**，**不得标记为最终最优**。

### 5.3 Ridge 实现（依赖说明）

**当前 Docker 稳定环境中不存在 scikit-learn**（已实测：
`import sklearn` → `ModuleNotFoundError`）。

按迁移约束**禁止 pip install**，因此实现 `NumPyRidge`
（`strategies/sw_sector_rotation/src/model/model.py`）作为对
`sklearn.linear_model.Ridge` 的**兼容实现**：

- 目标函数 `||Xw + b - y||^2 + alpha||w||^2`
- **intercept 不做 L2 惩罚**（与 sklearn 默认一致，有专门测试）
- 提供 `fit` / `predict` / `coef_` / `intercept_`，API 与 sklearn 对齐
- 中心化 + 增广最小二乘，保持同一目标、避免正规方程放大条件数
- 未做 feature scaling；非有限值/形状错误/不可靠数值秩明确失败

仅保证上述有限接口，不宣称完整 sklearn 行为兼容。
三周期缺任一周期则不融合；默认权重读自 YAML，不静默重新分配可用周期权重。

---

## 6. Risk（五指标风险状态）

生产版 `risk_filter_v2`，实现于 `strategies.sw_sector_rotation.src.risk.sector_rotation`。
**不迁移** `self_improver/modules/risk_filter.py`（实验版阈值与生产版不一致）。

| # | 指标 | 红灯条件 |
|---|------|----------|
| 1 | Market Breadth | 行业 close > MA20 的比例 < 0.4 |
| 2 | New High / New Low | 20 日新高/新低比 < 1.0（0.5% 容差） |
| 3 | Cross-Sectional Volatility | 行业 5 日平均收益的横截面标准差 > 历史均值 + 1.5σ |
| 4 | Volume Concentration | Top5 行业成交额占比 > 0.35 |
| 5 | Average Correlation | 过去 20 日行业收益相关性均值 < 0.2 |

置信度映射：`0-1 红灯 → 1.00`，`2 → 0.85`，`3-5 → 0.70`。

### 6.1 对角线排除（HARD GUARDRAIL）

相关性均值**必须排除相关矩阵对角线**。
旧说明书曾怀疑 legacy 代码未排除，但源码核查确认 legacy 的
`np.triu(..., k=1)` + `[~mask]` 语义**是正确的**（下三角、不含对角线）。
迁移版本用更直白的写法并加显式单元测试。

### 6.2 RiskState 与 ranking 解耦（重要设计决定）

**旧系统的错误做法**：把所有行业分数统一乘以 `confidence`。
这**不改变横截面排序**，对 ranking 毫无作用。

**迁移版本**：Risk Filter 只输出 `RiskState`：

```python
RiskState(
    red_lights=3,
    confidence=0.70,
    details={"market_breadth": "red", ...},
    metrics={...},
)
```

**不得直接修改 ranking。** 未来如何根据 RiskState 调整总仓位（降仓 /
提现金 / 减少 Top N / 切宽基 / 停止开仓）留给 ChatGPT 后续研究，
接口为 `strategies.sw_sector_rotation.src.portfolio.sector_etf_mapping.apply_risk_budget()`，
当前状态 **NOT_IMPLEMENTED**。

### 6.3 不迁移：Top5 → Top3

legacy `strategy.py` 在红灯 ≥ 3 时把 Top5 缩到 Top3，再归一化到 100%。
这**并没有降低总市场敞口**，只是增加集中度（2 只变 3 只，权重和为 1）。
因此**不予迁移**。有测试守护。

---

## 7. 时点完整性（Temporal Integrity）

实现：`strategies.sw_sector_rotation.src.common.temporal_integrity`。这是本次迁移**最重要的部分之一**。

### 7.1 核心规则

```
预测日期 t，预测周期 fwd 交易日
→ 最后允许进入训练的数据，其 forward label 必须在 t 时已完全实现
```

具体实现：

```
label_cutoff = calendar[pred_pos - fwd]      # 训练标签边界
train_start  = label_cutoff - train_months
realized_end = calendar[pred_pos + fwd]      # 本次预测的目标实现日；未知则 None
```

标签终点不等于持仓退出日。signal_date=t、decision_time=after_close，
execution_date 必须晚于 t；下一交易日只是执行日期下界，不保证成交。
实际 execution_date、rebalance_cadence、holding_period、holding_end 均未定义/实现，
保留 null，正式回测前必须决策。`validate_execution_date` 是待执行引擎接入的校验接口。

### 7.2 禁止事项（全部有测试守护）

- 禁止未来价格进入特征
- 禁止当前推理行进入训练标签
- 禁止实时资金流出现在历史回测
- 禁止未披露财务数据进入历史训练
- 禁止宏观数据在发布时间之前被使用

### 7.3 护栏函数

| 函数 | 用途 |
|------|------|
| `as_of_truncate` | 截断到 as_of（含当日） |
| `temporal_boundaries` | 计算 purged rolling window |
| `make_forward_label` | 构造未来收益标签 |
| `training_window` | 筛出标签已实现的训练日期 |
| `inference_rows` | 推理允许最新无标签行 |
| `non_overlapping_periods` | 正式绩效统计用不重叠采样 |
| `assert_no_lookahead` | 断言无未来数据泄露 |
| `validate_train_features` | 拒绝含被禁特征的训练集 |

---

## 8. Walk-Forward 与回测边界

- 迁移了 legacy `temporal_boundaries()` 与 strict walk-forward **思想**。
- **不迁移** legacy 完整 backtest engine。
- 正式回测由 **Hikyuu** 承担；RQAlpha 作为独立验证。
- 核心策略模块**不自己实现交易引擎**。

Hikyuu 必须负责：交易日 / 订单 / 持仓 / 资金 / 成本 / 净值。

---

## 9. 交易成本（初始默认）

配置文件：`strategies/sw_sector_rotation/config/sw_sector_rotation.yaml`

| 项 | 值 |
|----|-----|
| ETF commission | 0.00025 |
| 最低佣金 | 5 |
| ETF stamp duty | 0 |
| slippage | 0.001 |

> **不得**把 legacy 的 `round_trip_cost = 4 * ...` 当作所有回测的固定公式。
> 未来真实成本由 Hikyuu transaction cost model 与 RQAlpha validation
> 分别实现。

---

## 10. 代码结构

```
src/
├─ factors/
│  ├─ sector_rotation.py      # MA/MAPP、波动率、反转、回撤、RSI（纯函数）
│  ├─ rsrs.py                 # RSRS
│  └─ macro_pit.py            # 宏观 PIT 时点对齐（默认关闭）
├─ model/
│  ├─ model.py                # NumPyRidge + 三周期横截面模型
│  ├─ ranking.py              # 排名 / 权重（纯函数，不碰风险）
├─ strategy.py                # 编排器（框架无关）
├─ risk/sector_rotation.py    # 五指标风险状态
├─ portfolio/sector_etf_mapping.py   # ETF 映射 + apply_risk_budget 接口
├─ common/temporal_integrity.py      # 时点完整性护栏
└─ adapters/hikyuu/sector_rotation.py  # Hikyuu 适配器
```

测试：`strategies/sw_sector_rotation/tests/`
（test_factors / test_rsrs / test_ridge / test_risk /
test_temporal_integrity / test_ranking / test_hikyuu_adapter）

配置：`strategies/sw_sector_rotation/config/sw_sector_rotation.yaml`
Legacy 映射参考：`strategies/sw_sector_rotation/docs/legacy/sector_etf_mapping_reference.md`

---

## 11. Known Limitations

1. **完整行业数据未就绪**：已有 ETF 数据与框架 LEVEL A smoke，
   但未接入完整申万二级行业 PIT 数据，策略 Portfolio 端到端仍未验证。
2. **未回测**：本策略**尚未产生任何绩效数据**。所有历史收益数字均属
   legacy 系统，不可沿用。
3. **ETF 映射未验证**：`strategies/sw_sector_rotation/config/sw_sector_rotation_mapping.example.yaml`
   为 LEGACY REFERENCE ONLY，ETF 代码/规模/关系均需重新核实。
4. **宏观因子默认关闭**：PIT 算法已迁移但未接入数据源。
5. **资金流默认关闭**：仅提供 post-hoc 接口。
6. **无 sklearn**：使用 NumPyRidge 兼容实现（数值等价，但无 sklearn 的
   稀疏/正则化变体）。
7. **风险敞口调整未实现**：`apply_risk_budget` 为 NOT_IMPLEMENTED。

---

## 12. 验收状态

当前核心审计验收详见 [core_hardening_report.md](core_hardening_report.md)。
以下是旧迁移阶段的历史记录，不能代表当前数据状态或测试数量。

```
LEGACY CORE MIGRATION COMPLETE - DATA NOT INITIALIZED
```

- pytest：**154 passed, 3 skipped, 0 failed**
  （迁移前基线 33 passed / 3 skipped，新增 121 个测试）
- 3 个 skip 与基线一致（Hikyuu DATA_NOT_INITIALIZED /
  RQAlpha bundle 未初始化 / AKShare 网络不可达）
- Docker 稳定环境**完全未变化**：无 pip install / uninstall /
  升级 / 降级 / 重建镜像
