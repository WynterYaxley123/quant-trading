# SW Sector Rotation Core

**状态：CORE AUDITED / RESEARCH DECISIONS REQUIRED / NOT YET BACKTESTED**

申万二级行业横截面轮动策略。核心命题是**预测行业的相对排名**，
而不是预测绝对涨跌。

当前实现实际预测 **absolute close-to-close forward return 后排序**，
并非 rank/relative-return target。完整事实、修复和未决事项见
[核心审计报告](docs/core_hardening_report.md)。

来源：Legacy china-market-data v5
（release commit `1923f9d0fb00eeece9538ae1d0af9db57bbb02d5`）

---

## 重要声明

> 本策略**尚未接入真实行情数据，也从未跑过回测**。
>
> 所有超参（`alpha=0.01`、`train_months=6`、`top_n=5`、三周期权重）
> 均为 **LEGACY INITIAL DEFAULT**，是从旧系统搬来的初始值，
> **不是最优参数**，也未经新系统验证。
>
> 旧系统的一切历史收益数字**不得**引用为本策略业绩。
>
> 本策略定位为**实验/学习性质**。

---

## 使用方式

```python
from strategies.sw_sector_rotation import SWSectorRotationCore

core = SWSectorRotationCore()
# panel: {行业名: canonical OHLCVA DataFrame}
panel = core.build_panel(market_frames)
result = core.run(market_frames, calendar, predict_date, etf_mapping=mapping)
```

输入统一为 **canonical market frame**：
含 `open/high/low/close/volume/amount` 列、index 为升序 `DatetimeIndex`。

---

## 结构

```
sw_sector_rotation/
├─ src/
│  ├─ factors/            因子：MA/MAPP、波动率、反转、回撤、RSI、RSRS、Macro PIT
│  ├─ model/              NumPyRidge + 三周期横截面模型、排名
│  ├─ risk/               五指标风险状态
│  ├─ portfolio/          行业 → ETF 映射
│  ├─ common/             时点完整性护栏（防未来数据泄露）
│  ├─ adapters/hikyuu/    Hikyuu 适配器
│  └─ strategy.py         总入口编排器
├─ config/                策略配置
├─ tests/                 策略测试（188 个）
└─ docs/
   ├─ spec.md             Strategy Specification（完整规格）
   ├─ migration_report.md 迁移报告
   ├─ core_hardening_report.md 核心审计与正式回测前置决策
   └─ legacy/             旧 ETF 映射参考（只读）
```

---

## 数据流

```
market_frame (OHLCVA)
  → src/factors/               算因子
  → src/common/temporal_integrity  切训练/推理（防泄露）
  → src/model/model.py         训练 + 打分
  → src/model/ranking.py       排名 + 权重
  → src/portfolio/             映射到 ETF
  → src/adapters/hikyuu/       候选描述与桥接接口（尚非完整策略执行器）
```

风险状态（`src/risk/`）是**旁路**：只输出 `RiskState`，
**不修改排名**。如何据此调整总仓位留待后续设计
（接口 `apply_risk_budget` 当前为 NOT_IMPLEMENTED）。

---

## 关键设计

1. **纯核心 + adapter 分离**
   核心（factors/model/risk/portfolio/common）不 import 任何框架；
   只有 `adapters/` 与 Hikyuu 桥接。将来可复用于 RQAlpha。

2. **无 scikit-learn**
   当前环境无 sklearn，用 `NumPyRidge` 兼容实现
   （intercept 不做 L2 惩罚，数值与闭式解一致）。

3. **禁用因子**
   - 基本面（`profit_growth`/`roe`/`pb_inv`）：无可信 PIT 财报快照
   - 动量（`m5`/`m20`/`m60`/`accel`）、量比（`vr5`/`vr20`）：旧实验已消融
   - 资金流：仅 inference 期 post-hoc 修正，默认关闭

4. **时点完整性**
   core.run 先截断未来价格，标签和 purge 使用同一交易日历。
   t close 后决策不得同日成交；调仓频率和持有期仍未定义。
   任一 horizon 不可用时不生成融合排名，返回 NOT_READY。

---

## 测试

```bash
docker compose exec quant-research python -m pytest strategies/sw_sector_rotation/tests
```

188 个测试（原有 121 + hardening 新增 67）。测试使用 synthetic fixtures，**不下载真实行情**。

---

## 运行环境

所有量化命令必须走 Docker：

```bash
docker compose exec quant-research python ...
```

环境：Python 3.12.11 / Hikyuu 2.8.2 / RQAlpha 6.4.0 / AKShare 1.18.88

---

## 尚未完成

- 完整申万二级行业 PIT 数据尚未接入策略；框架已有 ETF 数据及 LEVEL A smoke，不是策略结果
- 未回测（收益率、回撤、夏普全部未知）
- 参数未调优
- Hikyuu Portfolio 端到端接线未验证
- ETF 映射需重新核实（ETF 会清盘改名）
- 调仓/持有、成交价格、总风险敞口及研究假设决策，详见核心审计报告
