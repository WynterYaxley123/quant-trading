# Legacy Core Migration 报告

**任务**：把 Legacy china-market-data v5 的核心量化算法"抽芯迁移"到
`D:\quant-trading`，重构为干净、框架化、可测试的代码，接入 Hikyuu 2.8.2。

**总体状态**：

```
LEGACY CORE MIGRATION COMPLETE - DATA NOT INITIALIZED
```

**授权说明**：本次为用户明确授权的例外，Hermes 可修改核心量化目录，
**仅限本次迁移任务**。旧 skill **未删除、未修改**（只读）。

---

## 1. 从旧 skill 保留了什么

只迁移**核心算法思想 + 经源码确认的实现**，不含任何基础设施。

| 类别 | 内容 | 新位置 |
|------|------|--------|
| 因子 | MA deviation `d5/d10/d20/d60/d120` | `src/factors/sector_rotation.py` |
| 因子 | Range position `p5/p10/p20/p60/p120`（MAPP 稳位置） | 同上 |
| 因子 | Trend alignment `align`（3/2/1 加权归一化） | 同上 |
| 因子 | Volatility `v5/v20/vc` | 同上 |
| 因子 | Reversal `rev5/rev10` + `rsi` | 同上 |
| 因子 | Drawdown `dd20/dd60` | 同上 |
| 因子 | **RSRS**（n=18, m=600, z×beta×R²） | `src/factors/rsrs.py` |
| 因子 | 宏观 PIT 时点对齐（默认关闭） | `src/factors/macro_pit.py` |
| 模型 | 三周期独立 Ridge（10/40/120） | `src/strategies/hikyuu/sw_sector_rotation/model.py` |
| 模型 | LEGACY INITIAL DEFAULT 超参 | 同上 |
| 风险 | risk_filter_v2 五指标 | `src/risk/sector_rotation.py` |
| 风险 | 相关性**排除对角线** | 同上 |
| 组合 | 行业→ETF 匹配 + 穿透权重算法 | `src/portfolio/sector_etf_mapping.py` |
| 时点 | `temporal_boundaries` purge 思想 | `src/common/temporal_integrity.py` |
| 时点 | 13 项防泄露护栏 | `tests/strategies/sw_sector_rotation/` |
| 成本 | ETF 成本初始默认 | `configs/strategies/sw_sector_rotation.yaml` |

---

## 2. 最终丢弃了什么（全部 Legacy Infrastructure）

**未复制任何一项**：

```
Hermes Skill 包装 / SKILL.md 运行逻辑
self_improver/ / meta_learner/ / daemon.py
cron / Feishu Bot / MCP server / Dashboard / architecture.html
旧发布链 / 旧 Profile / 旧日志系统
旧 API health daemon / 旧自动更新器 / 旧新闻系统
旧 portfolio_state / 旧 weekly_runner / 旧 executor / 旧 tracker
旧 predictions.json 历史 / 旧回测结果 / 旧收益数字 / 旧缓存目录
旧实时数据 fallback 链 / 旧图片字体系统
旧 Git/Profile workflow / 旧 rollback / 旧失败记忆
```

**不迁移的因子**（legacy 实验已消融）：
`m5` / `m20` / `m60` / `accel` / `vr5` / `vr20` / 旧 volume ratio

**不迁移的基本面**：`financial_statement.py`、`profit_growth` / `roe` / `pb_inv`
（无可靠 PIT 财报快照）

**不迁移的错误逻辑**：

- Top5 → Top3 "降敞口"（实际只是提高集中度，未降低总敞口）
- 用同一个 `confidence` 缩放所有行业分数（不改变横截面排序，无意义）
- 旧的 21 只 ETF 生产配置（降级为 LEGACY REFERENCE ONLY）

---

## 3. 新项目目录结构

```
src/
├─ factors/
│  ├─ sector_rotation.py        # MA/MAPP、波动率、反转、回撤、RSI
│  ├─ rsrs.py                   # RSRS
│  └─ macro_pit.py              # 宏观 PIT（默认关闭）
├─ strategies/hikyuu/sw_sector_rotation/
│  ├─ model.py                  # NumPyRidge + 三周期横截面模型
│  ├─ ranking.py                # 排名/权重（纯函数）
│  └─ strategy.py               # 编排器
├─ risk/sector_rotation.py      # 五指标风险状态
├─ portfolio/sector_etf_mapping.py
├─ common/temporal_integrity.py # 时点护栏
└─ adapters/hikyuu/sector_rotation.py

configs/strategies/
├─ sw_sector_rotation.yaml
└─ sw_sector_rotation_mapping.example.yaml

tests/strategies/sw_sector_rotation/
├─ test_factors.py
├─ test_rsrs.py
├─ test_ridge.py
├─ test_risk.py
├─ test_temporal_integrity.py
├─ test_ranking.py
└─ test_hikyuu_adapter.py

docs/strategies/sw_sector_rotation_core.md    # Strategy Specification
docs/legacy/sector_etf_mapping_reference.md   # LEGACY REFERENCE ONLY
```

结构基本遵循任务书建议，未破坏现有目录规范（`src/strategies/hikyuu/` 已存在）。

---

## 4. 迁移的因子清单

| 因子 | 公式 | 状态 |
|------|------|------|
| `d5/d10/d20/d60/d120` | (close - MA_n) / MA_n | active |
| `p5/p10/p20/p60/p120` | (close - min_n) / (max_n - min_n), clip [0,1] | active |
| `align` | (MA5>MA10)*3 + (MA10>MA20)*2 + (MA20>MA60)*1, /6 | active |
| `v5` / `v20` | 日收益滚动标准差 | active |
| `vc` | v5 / (v20 + eps) | active |
| `rev5` / `rev10` | -过去平均收益 | active |
| `rsi` | RSI(14) | active |
| `rsrs` | z × beta × R²，n=18 m=600 | active |
| `dd20` / `dd60` | close / 滚动最高 - 1 | active |
| macro PIT | 时点对齐快照 | **disabled by default** |
| flow adjust | `apply_flow_adjustment(score, flow_net)`，±0.02 | **disabled by default** |
| `profit_growth`/`roe`/`pb_inv` | — | **禁用（配置层抛异常）** |
| `m5/m20/m60/accel/vr5/vr20` | — | **不迁移** |

---

## 5. Ridge 模型实现方式

- **sklearn 是否存在**：**不存在**。实测
  `docker compose exec quant-research python -c "import sklearn"` →
  `ModuleNotFoundError`。
- 按约束**未 pip install**，改为实现 `NumPyRidge` 兼容层。
- 目标函数 `||Xw + b - y||² + α||w||²`，**intercept 不做 L2 惩罚**。
- 闭式解：`w = (XcᵀXc + αI)⁻¹Xcᵀyc`，`Xc`/`yc` 已中心化，故 `I` 不含截距。
- 提供 `fit` / `predict` / `coef_` / `intercept_`，与 sklearn API 对齐。
- 单元测试覆盖：与闭式解一致、intercept 不惩罚、α=0 时等于 OLS、
  奇异矩阵退化到伪逆、已知线性关系复原。
- 未来若环境出现 sklearn 可无缝替换。

---

## 6. 风险过滤器实现情况

- 迁移**生产版** risk_filter_v2（五指标齐全）。
- **未迁移** `self_improver/modules/risk_filter.py`（实验版，与生产版阈值不一致）。
- **对角线排除**：legacy 源码核查确认其 `np.triu(..., k=1)` + `[~mask]`
  **本就是正确的**（下三角、不含对角线）。迁移版用更直白写法 +
  显式单元测试守护（含"若误含对角线会得 0.667"的反例测试）。
- **RiskState 与 ranking 解耦**：核心只输出 `RiskState`，
  不提供用 `confidence` 缩放分数的路径（有测试断言）。
- **Top5→Top3 逻辑未迁移**（有行为测试守护）。
- `apply_risk_budget` 状态：**NOT_IMPLEMENTED**（抛专用异常）。

---

## 7. Temporal Integrity 测试结果

13 项护栏全部实现并有对应测试：

| # | 护栏 | 测试 |
|---|------|------|
| 1 | 未来价格不改变过去因子 | `test_future_prices_do_not_affect_past_factors` |
| 2 | 推理允许最新无标签行 | `test_inference_allows_latest_unlabelled_row` |
| 3 | 训练要求完整 forward label | `test_training_requires_realized_label` |
| 4 | forward label 必须 purge | `test_forward_label_purge` |
| 5 | rolling window 限制 train_months | `test_rolling_window_respects_train_months` |
| 6 | as_of 后价格不可见 | `test_as_of_truncation_hides_future` |
| 7 | 历史模式禁止实时资金流 | `test_flow_forbidden_in_training` |
| 8 | fundamentals 不进训练 | `test_fundamentals_not_in_train_features` |
| 9 | 宏观发布前不可见 | `test_macro_not_visible_before_publication` |
| 10 | prediction date 与 realized return 对齐 | `test_prediction_date_aligned_with_realized_return` |
| 11 | 重叠窗口不得用于正式 Sharpe/DD | `test_non_overlapping_periods` |
| 12 | RSRS z-score 窗口不含当前/未来 | `test_rsrs_zscore_window_excludes_current_value` |
| 13 | 风险相关性排除对角线 | `test_correlation_excludes_diagonal` |

**额外修复**：legacy `macro_features.py` 的 `_parse_month()` **定义缺失**，
本迁移**重新实现**并加多输入格式测试
（`test_parse_month_reimplemented`）。

---

## 8. Hikyuu adapter 实际使用的 API

**全部在 Hikyuu 2.8.2 上实测确认**（`dir()` 验证，不猜）：

| 类 | 确认存在的方法 |
|----|----------------|
| `Portfolio` | `run / query / set_param / get_param / se / af / tm / real_sys_list / performance / reset` |
| `SelectorBase` | `add_stock_list / add_sys / calculate / get_selected / set_scores_filter / add_scores_filter / reset / name` |
| `AllocateFundsBase` | `set_param / get_param / reset / query / name` |
| `System` | `run / query / set_param / get_param / get_stock / st / sp / mm / tp / pg / to / ev / clone` |

另确认存在：`SystemWeight` / `TradeCostBase` / `SlippageBase` /
`MoneyManagerBase` / `ProfitGoalBase` / `StoplossBase`。

**adapter 提供**：

- `kdata_to_market_frame()` —— KData → canonical frame（有 fake KData 测试，
  无需真实行情）
- `ranked_sectors_to_targets()` —— ranking → 目标权重
- `targets_to_system_weights()` —— → Hikyuu `SystemWeight` 输入
- `build_stock_selector_input()` —— → `SelectorBase` 输入描述
- `HikyuuSelectorProtocol` / `HikyuuAllocatorProtocol` —— 扩展点

**未造假的 API**：构造自定义 `Selector` / `AllocateFunds` 子类并接入
`Portfolio.run` 的完整链路，因缺行情无法验证，以 **protocol** 形式
记录为扩展点，等待 ChatGPT 在行情初始化后实现。

---

## 9. 因未初始化行情数据尚无法验证

1. Hikyuu `Portfolio.run` 端到端链路（需行情库 + 自定义 Selector 子类）
2. 真实 KData 的 `kdata_to_market_frame` 转换（用 fake KData 测试了逻辑）
3. 任何正式回测结果、净值、Sharpe、最大回撤
4. 宏观因子接入真实数据源的时点表现
5. 资金流 post-hoc 修正的实际效果
6. ETF 映射的实盘可用性（ETF 代码需重新验证）

---

## 10. 是否修改任何依赖

**否。完全没有。**

- 无 `pip install`
- 无 `pip uninstall`
- 无升级 / 降级
- 无镜像重建

环境基线保持不变：
Python 3.12.11 / Hikyuu 2.8.2 / RQAlpha 6.4.0 / AKShare 1.18.88 /
NumPy 2.3.5 / Pandas 2.3.3 / SciPy 1.16.3。
Ridge 用 NumPy 自实现，**未为旧算法引入任何新依赖**。

---

## 11. pytest 最终结果

```
154 passed, 3 skipped, 0 failed
```

- 迁移前基线：33 passed, 3 skipped, 0 failed
- 新增：**121** 个测试（全部通过）
- **无回归**：原有 33 个测试仍全绿
- 3 个 skip 与基线完全一致：
  - Hikyuu `DATA_NOT_INITIALIZED`
  - RQAlpha bundle 未初始化
  - AKShare `NETWORK_UNAVAILABLE`

---

## 12. Git 分支

- 基线：`dev` = `29ed06e`
- 工作分支：**`experiment/migrate-china-market-core`**
- `main`：`a1f7ff9` **未改动**
- **未自动 merge dev**（等待用户确认）

---

## 13. Commits

（见 git log，4 个 commit，对应任务书建议的拆分）

---

## 14. 是否仍需要旧 china-market-data skill

**暂时保留，标记为 DEPRECATED 候选。**

- 本轮**未删除、未修改**旧 skill（只读），便于迁移出错时追溯源源码。
- 旧 skill 的全部价值已提炼进本报告与 `docs/strategies/sw_sector_rotation_core.md`。
- 待用户验收后，可择机删除或用 `DEPRECATED` 标记。
- **不依赖**旧 skill 的任何运行时组件。
