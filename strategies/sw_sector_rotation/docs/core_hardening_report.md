# SW Sector Rotation Core — correctness hardening audit

日期：2026-09-20。分支：`experiment/sw-sector-core-hardening`。
审计基线：`aa7f5a6ebbf4ed54fe98b6a6d03de7a7f4dfa270`。

状态：**SW SECTOR ROTATION CORE AUDITED - RESEARCH DECISIONS REQUIRED**。
这是 correctness hardening，不是 performance optimization，也不是策略验证。
未训练正式市场模型，未执行 LEVEL A / LEVEL B 回测，没有新增业绩数据。

## 1. 当前真实流程与目标

行业 OHLCVA → 按 signal_date 截断 → 价格因子与公共交易日历标签 →
各 horizon 独立 purge、训练、推理 → 各 horizon 横截面 z-score →
0.25 / 0.50 / 0.25 融合 → Top5 行业 → legacy ETF 候选描述。
RiskState 是旁路，不进入 score/rank；adapter 尚不是完整策略执行器。

- 训练为 date × sector 堆叠，每个有效样本同权；不是每天独立回归。
  编排器先取各行业非空标签日期交集，再过滤各行业特征预热缺失。
  因而有效行业数不同的日期，其总训练权重仍不同；现在输出逐日/行业覆盖率。
- 实际 target：`close[calendar[pos(t)+h]] / close[t] - 1`，即
  **absolute close-to-close forward return**；不是超额、去均值或 rank target。
  预测绝对收益再排序不等同于直接优化相对排名，仍有市场 Beta 主导风险。
- 默认 Ridge 训练列是 `TRAIN_FEATURES_PRICE` 的 19 列；RSRS 会计算但不在其中。
  不添加 RSRS 或任何其他特征，不恢复已消融的动量/量比/基本面。
- 默认运行模型参数/开关读取包内 YAML；显式 config 仍支持合成测试。
  不声称整份 YAML 已接线：因子窗口和风险默认阈值仍来自原模块常量。

## 2. 时间与交易契约

| 字段 | 当前语义 |
|---|---|
| signal_date / decision_time | t 日收盘数据可见，`after_close` 决策 |
| earliest_execution_date | 所给交易日历中的下一 session；没有未来日历则 null |
| execution_date | null；必须由未来执行引擎记录真实成交，严格晚于信号日 |
| label_start / label_end | t close → 第 h 个后续交易日 close；不是可执行持仓收益 |
| prediction_horizon | 10 / 40 / 120 交易日，各自独立模型 |
| rebalance_cadence / holding_period / holding_end | 全部未决定，保持 null，不由 horizon 推导 |

最后训练样本为 `calendar[pred_pos-h]`，其标签于预测日收盘完全实现。
`TemporalBoundaries.realized_end` 是**本次预测**的标签终点，不是最后训练标签终点；
未知未来日历不阻止最新日推理。缺失价格端点不填充、不把终点移动至下一个有数据日。
core.run 在计算因子和标签前截断未来价格；完整、截断、污染未来数据三种输入排名一致。
底层 fit_period 仍要求调用方提供已经 purge 的 train_dates；不得绕过编排器拼接未经审计的标签。

`validate_execution_date` 拒绝同日及更早成交；它是契约校验函数，**尚未接入真实订单引擎**。
下一 session 仅是日期下界，并不保证开盘价可成交；停牌、涨跌停、流动性等必须由执行层验证。

## 3. 发现清单（按根因分组，不按断言或文件数）

共 **7 项 P0、8 项 P1、3 项 P2**。P0 代码路径已修补；P1 有护栏与未决设计，
因此不宣称正式回测已就绪。可选路径的缺陷不代表默认历史运行曾触发。

| ID | 发现 | 本轮处置 |
|---|---|---|
| P0-01 | 行业缺日时 row-shift 标签与公共日历 purge 不一致，可能用到未实现标签；最新日还依赖未来日历 | 标签统一日历，缺端点 NaN；先 as-of 截断；移除未来日历推理前置条件 |
| P0-02 | Ridge 正规方程放大病态性，非有限值/失败重训可污染结果 | 相同目标的增广 lstsq；检查形状、有限值、数值秩、溢出；失败清旧状态 |
| P0-03 | 特征 schema/order 无契约，推理可取陈旧行业行 | 固定训练列名与顺序，排除 label/标识；只取信号日，记录缺行业/缺特征 |
| P0-04 | 缺 horizon 静默重新分配权重、非有限分数可能被当成零 | 任一周期不可用不融合，NOT_READY；非有限分数报错；行业交集有提示；平局确定排序 |
| P0-05 | 显式空 ETF 集回退行业目标、重复 ETF/无效权重/缺 resolver 可产生错误描述 | 空集仍空；重复及无效值拒绝；显式 resolver 必须完整；缺映射告警 |
| P0-06 | 可选 macro 在乱序查询时 ffill 会把较晚快照填给较早日期，缺失又变零 | 不跨查询行填充，未发布保持 NaN；核心禁止启用未接线 macro |
| P0-07 | 可选 flow 没有 historical 模式限制，且修正字典未同步到实际融合输入 | 显式 inference + enabled 才允许；同步 result 分数；默认仍关闭 |
| P1-01 | signal/成交/标签/调仓持有期混淆，无真实成交模型 | 新增明确时间字段和同日成交拒绝函数；成交价格、调仓和持有规则仍待定 |
| P1-02 | 名义训练日期数掩盖预热后有效日期不足，覆盖率不可见 | 按实际有效日期执行原 30 日门槛；报告样本数/覆盖率，不改变逐样本权重 |
| P1-03 | 默认 core 未读 YAML，配置与运行易漂移 | 默认模型参数和可选开关读取 YAML；不改任何参数，未接线项在本文明确 |
| P1-04 | RiskState 无 as-of，缺失数据的中性兜底易误认为安全 | 新增 as_of、数据有效性检查及 INSUFFICIENT_DATA；敞口规则/历史波动率 PIT 仍待定 |
| P1-05 | 因子输入重复日期/列、NaN/Inf、非正价格及隐式填充缺少保护 | 输入校验、pct_change 禁止隐式填充；缺日滚动窗口口径仍需真实数据契约 |
| P1-06 | mapping 未验证且一对多/共享 ETF 分配语义未定 | requires_validation；一对多显式拒绝，共享 ETF 保留 max score + direct 优先；不联网核实 |
| P1-07 | 数据/执行/报告尚不具备正式策略验证条件 | 记录真实行业 PIT、复权、停牌/涨跌停、快照及提交溯源要求；不扩改基础设施 |
| P1-08 | macro 固定发布日估计不是真实历史发布时间/修订版本 | 保持 disabled，不宣称现有 helper 已保证真实宏观 PIT |
| P2-01 | 原始量纲影响 Ridge 正则强度 | 不加 scaler；是否使用仅训练窗口拟合的 mean/std 需独立研究决定 |
| P2-02 | absolute target 与相对排名目标非完全一致 | 不改 relative/demeaned/rank target，后续按共同 Specification 决策 |
| P2-03 | 不均衡 sector coverage 的日期权重、RSRS 是否入模及模型参数优化 | 仅暴露事实；不改样本权重、特征集合、alpha、周期、融合权重或阈值 |

## 4. 数值、因子、映射与风险的边界

- Ridge **没有 feature scaling**。中心化只是估计不受罚截距，不是单位方差标准化。
  增广最小二乘保持 `||Xw+b-y||²+alpha||w||²`；alpha>0 正则化处理共线/少样本，
  极端尺度导致数值秩不足则失败；alpha=0 取最小范数解。常数列行为有确定测试。
  特征预热 NaN 可丢弃并计数；Inf 不当作缺失；推理 NaN 行排除并记录，不转零分。
- MA/MAPP、波动率、反转、RSI、回撤均用过去及当日窗口，无 centered rolling。
  RSRS OLS 使用当日及历史，z-score 的 beta 窗口严格 `[t-m,t)`；保留原边界测试。
  唯一有意负 shift 是标签生成，不是训练特征。
- 融合先检查三个独立模型的日期/周期身份；只能用三者共同可用行业。
  常数截面分数的 z-score=0 是定义，不是把无效 score 填零。
- mapping 一行业一条记录；多行业同 ETF 保留原 max score、direct 优先、行业列表汇总。
  候选归一化不等于账户总敞口；禁止把剔除行业后重新满仓称作降低风险。
  `etf_candidates=None` 仍保留旧行业描述兼容路径；不可直接当作可交易证券。
  旧 `targets_to_system_weights` 对空 symbol 保留跳过但现在告警；严格 selector 入口拒绝。
- RiskState 不修改 ranking，`apply_risk_budget` 仍 **NOT_IMPLEMENTED**。
  INSUFFICIENT_DATA 中保留 legacy 中性字段只为兼容，不能作为开仓授权。
  历史 cross-vol 输入仍是无日期列表，调用者必须保证仅含可见历史；未来要有带时间戳的契约。
  原动态阈值兜底、相关性缺失处理未重新设计，也不宣称风险模块已可做总敞口决策。

## 5. 故意不做与正式 LEVEL B 前置决策

1. 决定信号后的执行价格/订单时点、rebalance cadence、holding/退出及成本规则；
   不把 close-to-close 标签直接累计为账户收益，不自行指定日/周/月调仓。
2. 决定 RiskState → 总敞口/现金的映射以及数据不足时行为；不能复活 score × confidence。
3. 验证有历史时点的申万二级行业及 ETF 映射、一对多/缺失/重复映射分配规则。
4. 建立真实交易日历、行业覆盖/缺日、复权、停牌/涨跌停、发布时间/修订版的 PIT 契约。
   现有 8 只 ETF 数据与 Hikyuu 执行 smoke 不代表完整申万行业研究数据已就绪。
5. 决定标准化、absolute target 是否保留、日期/行业样本权重；这类研究变更不能混进 bug fix。
6. Hikyuu 与 RQAlpha 使用同一份正式 Specification，落实 adapter 时间校验与订单约束。
   审阅 src/data、src/backtesting 与 docs/data 但未修改；当前 LEVEL A 报告的
   data_snapshot 可为空，git_commit 可 unknown，不够作为正式可复现实验依据。
   旧 Hikyuu smoke 的空数据 skip 文案不能覆盖已有 ETF HDF5/SQLite 验收事实。

研究假设未主动更换：target、19 个训练特征、原始尺度、逐样本权重、10/40/120、
alpha=0.01、0.25/0.50/0.25、Top5、6 月训练窗口、30 日门槛及风险阈值均未调优。
行为确有收紧：缺日标签、陈旧/非有限数据、缺周期、缺映射不再沿用旧的静默结果；
最新日可推理、求解算法和稳定排序也可能使结果与旧实现不同，不能冒充收益提升。

## 6. 验证与变更范围

- 基线：238 passed / 3 skipped / 10 deselected。
- 完成后默认全仓库 pytest：**305 passed / 3 skipped / 10 deselected / 2 warnings**。
- 原策略 121 个测试未删改；新增 **67** 个 deterministic synthetic 用例，策略合计 188。
  覆盖时点、缺日 purge、无未来日历、未来数据扰动、数值异常、schema、覆盖率、
  缺周期、flow 模式、macro 乱序、映射/权重与风险解耦；RSRS 原历史窗口测试继续通过。
- skip：AKShare 网络不可达、旧 Hikyuu block 检查、RQAlpha bundle 未初始化。
  默认 pytest 仍含原有 AKShare 网络 smoke；新增测试不联网。
  integration 默认排除，不冒充已通过；两个 warning 为原测试触发新增的明确异常提示。
- 仅修改本策略包代码、新增测试和说明；YAML 参数、原测试、顶层框架均不变。
  所有 Python/pytest 在现有 Docker 中执行，无安装/升级/降级/镜像重建。
