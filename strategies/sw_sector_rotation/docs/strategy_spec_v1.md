# SW Sector Rotation — Strategy Specification v1

状态：**STRATEGY SPEC V1 DRAFT - USER DECISIONS REQUIRED**

更新：用户已批准本文件第 20 节所列 LEVEL B 研究规则；**当前阻塞为 DATA NOT READY**。
第 20 节及 `config/sw_sector_rotation_level_b_research.yaml` 是新增批准记录的权威补充。
第 1–19 节保留原草稿作为决策来历，其中“未批准”描述若与第 20 节冲突，以第 20 节为准。
批准研究方案不代表数据合格、实现完成或 OOS 已锁定。

文档版本：`v1-draft.1`；日期：2026-09-20。

事实基线：`experiment/sw-sector-core-hardening`，commit `3af2398b408bce9827b61df6b92269da99bc8348`。

本文锁定现有模型研究假设，**未批准任何待决交易规则，不是 LEVEL B 启动授权**。
仅新增规格文档，不改代码/配置/测试，不初始化数据，不执行任何回测或参数实验。
Hikyuu 为主研究/执行框架，RQAlpha 为独立验证框架，未来双方必须实现同一批准版本。

术语：**LOCKED**＝本次任务明确保留；**IMPLEMENTED**＝当前代码事实；
**PROPOSED**＝建议但未批准；**REQUIRED DECISION (Dxx)**＝需用户选择；
**REQUIRED DATA VALIDATION (Vxx)**＝必须提供证据，不能用批准代替数据真实性。
correctness、research choice、execution assumption 分别记作 C、R、E；详见第 18 节。

事实来源（相对本文件位置）：

- [核心审计](core_hardening_report.md)、[编排器](../src/strategy.py)、[模型](../src/model/model.py)、[时点护栏](../src/common/temporal_integrity.py)。
- [因子](../src/factors/sector_rotation.py)、[排名与行业权重](../src/model/ranking.py)、[映射](../src/portfolio/sector_etf_mapping.py)、[适配描述](../src/adapters/hikyuu/sector_rotation.py)、[风险](../src/risk/sector_rotation.py)。
- [参数](../config/sw_sector_rotation.yaml)、[legacy 映射示例](../config/sw_sector_rotation_mapping.example.yaml)、[合成回归测试](../tests/test_core_hardening.py)、[RSRS 测试](../tests/test_rsrs.py)。
- [公共数据层](../../../src/data/)、[回测框架](../../../src/backtesting/)、[行情政策](../../../docs/data/market_data_policy.md)、[执行链路记录](../../../docs/data/hikyuu_backtest_pipeline.md)、[报告规范](../../../docs/report_schema.md)。

## 1. Strategy objective

研究目标：利用申万二级行业价格信息预测行业相对强弱次序，经历史有效的 ETF 映射形成组合。
当前实现是预测**绝对未来收益后排序**，不是直接优化排名；不声称消除了市场 Beta。
模型输出是信号，不是订单、成交保证或已验证的策略收益。

旧描述与真实行为的差异，以右列为准：

| 旧描述/容易误读之处 | 当前事实 |
|---|---|
| 行业相对收益 target | absolute close-to-close return，无横截面去均值 |
| RSRS 属于因子，因此参与回归 | 默认计算，但不在 19 列训练 schema 中 |
| 三个周期可直接当持有期限 | 仅 prediction horizons，调仓/持有未接线 |
| 行业权重直接成为 ETF 权重 | core ETF 候选不含权重；adapter 默认去重 ETF 等权，两者没有自动传递关系 |
| YAML 全部生效 | 默认加载模型参数/可选开关；因子常量、风险阈值等不能仅凭 YAML 认定已接线 |
| 当前 backtest CLI 已验证本策略 | 当前 Hikyuu runner 仍是 execution_smoke，不调用本策略完成 LEVEL B |
| 数据层 is_pit=True/旧空数据库说明 | 标志不是历史版本证明；已有 ETF smoke 数据不等于行业 PIT 数据就绪 |

## 2. Data contract

**LOCKED/C：**行业用于信号，ETF 用于交易；两类数据不得互相冒充。
每日观察使用统一交易日历 C；核心日索引为无时区、归一化、唯一且升序的 DatetimeIndex，
其外部交易时点按 Asia/Shanghai 解释，并记录真实数据可见时间。

策略输入 `{sector_key: frame}` 必须具备 open/high/low/close/volume/amount，
OHLC 为有限正数，volume/amount 有限非负；禁止伪造缺失价格或成交额。
公共 canonical schema 的 amount 是可选列，但本策略要求存在，接线时不能遗漏。
行业 key 的稳定标识及显示名需保存：当前同分按 key 排序，重命名会影响平局，不能暗换编码。

每份输入清单必须含：source、source_version、snapshot_id/hash、抓取时间、可见时间、
行业 classification_version、历史生效区间、行业/ETF 代码与单位、复权/分红口径、
calendar_version、区间和缺失/修订记录。原始数据不提交 Git，但必须可按快照重放。
`available_at <= decision_time`，不只是行情日期 <= t；按当时有效的行业分类和映射取数。
不得把今天存续行业/ETF 名单向历史回填，不能事后剔除已消失标的来美化结果。

**REQUIRED DATA VALIDATION：**

| ID | 必须验证的证据 |
|---|---|
| V01 | 申万二级历史分类/价格序列的来源、版本、生效/可得时间及修订记录；不是当前分类重构过去 |
| V02 | 公共交易日历覆盖、节假日、各 frame 缺口及原始重复记录；不能默认最长 ETF K 线就是完整市场日历 |
| V03 | 历史 ETF 映射和存续/交易状态、暴露关系、上市起点/退市及分红拆分信息，见第 13 节 |
| V04 | 信号价格与成交价格分别采用的口径、权息事件可得时点、现金分红/份额调整账务、量额单位 |
| V05 | 停牌/限价/交易单位/结算可卖性/流动性数据的历史规则及时间戳；不能凭日线价格不动推断 |
| V06 | 文件内容指纹、软件/配置版本、双框架一致性及数据集覆盖清单；快照可重放不等于其天然 PIT |

当前缺口：provider 声明 is_pit=True 但不提供复权因子；loader 取最长标的日历；
normalize_frame 会先保留重复日期最后一条。正式接线必须在这些处理之前留存/检查原始记录，
不能靠规范化后的表反向宣称原始数据无重复或无修订。此轮仅记录，不修改公共层。

## 3. Feature set

**LOCKED：**固定顺序为：

```text
d5,d10,d20,d60,d120,p5,p10,p20,p60,p120,align,
v5,v20,vc,rev5,rev10,dd20,dd60,rsi
```

令 c 为行业 close，r 为 `pct_change(fill_method=None)`，epsilon=1e-10。

| 特征 | 当前公式 |
|---|---|
| dN，N=5/10/20/60/120 | (c - rolling_mean_N(c)) / rolling_mean_N(c) |
| pN，同上 | clip((c - rolling_min_N(c)) / (rolling_max_N(c)-rolling_min_N(c)+epsilon), 0, 1)；使用 close 区间，不是 high/low 区间 |
| align | (3×I(MA5>MA10)+2×I(MA10>MA20)+I(MA20>MA60))/6 |
| v5/v20；vc | r 的 rolling std，ddof=1；v5/(v20+epsilon) |
| rev5/rev10 | -rolling_mean_N(r) |
| dd20/dd60 | c/rolling_max_N(c)-1 |
| rsi | 100-100/(1+mean_14(max(r,0))/(mean_14(max(-r,0))+epsilon))；简单均值，非 Wilder 平滑 |

rolling 不居中，只用过去及当日行；当前按已观察行数滚动，不自动补齐缺失 session（D14）。
窗口不足产生的 NaN 按模型规则处理，不是把缺 OHLC 填成可用行情。
RSRS n=18/m=600 是诊断列，历史 beta 标准化窗口 `[t-m,t)` 排除当前值；不入模。
Macro/Flow 均 disabled；fundamental、momentum、volume ratio 均 excluded。
行业编码、日期、标签不得作为数值特征；推理 feature names/order 必须与训练完全一致。

## 4. Target definition

**LOCKED：**对 h∈{10,40,120}，样本日期 s 的标签：

```text
y_h(s) = close[C[pos(s)+h]] / close[s] - 1
```

这是输入行业 close 序列的 absolute forward return，不做市场基准扣除、横截面去均值或排名转换。
缺起点/终点的样本不可训练；终点缺失保持 NaN，不移动到下一条有行情记录。
日期偏移使用同一公共交易日历而非行业自身行数。
标签从 s close 开始，并不意味着能在观察到 s close 后仍以它成交。
标签不能替代 ETF 实际成交到退出期间的账户盈亏；价格序列口径必须经 V01/V04 验证。

## 5. Model

**LOCKED：**三个独立 NumPyRidge，alpha=0.01，无 feature scaling，截距不受罚。
目标为 `sum((Xw+b-y)^2)+alpha*sum(w^2)`，不是按样本数归一化后的另一种 alpha 定义。
中心化仅用于截距；增广 lstsq 保持同一目标，不引入 sklearn 或新模型。

每次调用 core.run 都重新拟合各 horizon，不跨失败窗口复用旧模型。
信号日 t 的 `cutoff_h=C[pos(t)-h]`，训练日期在
`[cutoff_h-DateOffset(months=6), cutoff_h]`，两端包含；**不是从 t 往前六个月**。
先取输入各行业非空标签日期交集，再逐行业剔除训练特征/标签 NaN 行；
把有效 date×sector 样本堆叠成该 horizon 的一个模型，每个样本权重相同。
至少 30 个实际有效不同训练日期；不是 30 行样本，也不要求每行业各 30 日。
保留 coverage、样本数、丢弃行数，不改成 date-balanced weighting。

Inf/不合法 schema/不可靠数值秩/溢出明确报错；常数列可求解。
推理只取 t 行，缺行或特征 NaN 的行业被记录并排除，不回退陈旧行。
预测不读取标签；数值安全边界和缺数据状态不等于正式交易回退策略（D07）。

## 6. Multi-horizon fusion

**LOCKED：**short=10、medium=40、long=120；独立标签、训练、推理。
配置融合权重为 0.25/0.50/0.25。
三者日期和 horizon 身份必须一致；取共同可用行业集合，覆盖不一致产生提示。
先在该交集上按各周期分数计算横截面 z-score（总体 std，ddof=0），再加权求和。
常数/接近常数截面（当前 std 阈值 1e-12）为零 z-score；NaN/Inf 分数则报错，不能当零。
内部先等比例缩放以避免溢出，这不是训练 feature scaling。
按融合分数降序、同行业 key 升序打破平局，取至多 Top5，不事后补足行业数量。

任一 horizon 不可用，或三者无共同可用行业，均不生成融合排名；core 返回 NOT_READY。
不静默重分配缺失周期的权重。少于 5 个有效行业的代码仍可输出更短排名，
正式运行是否允许由 D07 决定；NOT_READY **不是清仓指令**。

## 7. Signal timing

**LOCKED/C：**signal_date=t，decision_time=t 的 after_close；特征只能读取此时已可见数据。
每日数据若收盘后尚未发布，不能仅因标注为 t 日就视为已知。
core.run 在构造特征和标签前截断 >t 的行情；日历未来日期不是未来价格。

| 字段 | 精确定义/当前状态 |
|---|---|
| signal_date | t，模型信息截点日期 |
| decision_time | after_close；正式运行还需记录实际数据可见/决策时间 |
| earliest_execution_date | C 中严格晚于 t 的下一 session；日历不足时 null，不猜自然日 |
| execution_date | 实际成交时间所属日期；当前 null；部分成交按每笔分别记录 |
| label_start | 对 t 的预测标签从 t close 开始 |
| label_end | C[pos(t)+h]；未知未来日历时 null |
| prediction_horizon | 10/40/120 session，仅标签和模型预测跨度 |
| rebalance_cadence | 组合重新设定目标的计划频率，D02 未批准 |
| holding_period | 实际建仓至退出持续时长，由 D03 和成交决定，当前 null |
| holding_end | 实际退出/平仓时点；未退出为 null，不取 label_end 代替 |

## 8. Execution timing

**LOCKED/C：**使用 t close 后绝不能假设 t close 成交，实际 execution_date>signal_date。
`validate_execution_date` 已存在但尚未接入完整订单引擎。
**PROPOSED：**t after_close 冻结信号/目标 → 下一 session 尝试执行；
若 ETF 停牌、受限制或数据不可验证，不把该 session 强行写成实际成交日。

D01 候选：A 下一 session open 作为计划价并应用获批成本/可成交性模型；
B 下一 session 的明确时段 VWAP。建议 A，日频数据对接更简单，**不保证以 open 成交**。
B 需分钟/成交数据，事后 VWAP 只能用于执行模拟，不可回流为 t 日信号，
且不能用 amount/volume 在单位未经核实的情况下冒充 VWAP。
两者都不是当前已批准规则，也不能默认使用引擎自带收盘成交设置。

## 9. Rebalance policy

**REQUIRED DECISION D02：**horizon ≠ cadence。如下建议未按历史收益筛选：

| 方案 | 优点 | 缺点 | 与 10/40/120 关系 | 换手影响（结构推断，非结果） | 实现复杂度 |
|---|---|---|---|---|---|
| A 每 5 个交易日 | 更频繁吸收新信息 | 交易机会/成本暴露更多 | 最短预测跨度内可更新两次，其余周期高度重叠 | 通常更频繁触发权重调整，不保证实际换手更高 | 低；固定日历锚点+步长 |
| B 每 10 个交易日（建议） | 便于解释和复现，更新次数适中 | 可能延迟响应短期变化 | 等于最短 horizon 只是调度巧合，仍不强制持有 10 日；40/120 模型保留 | 比 A 少调仓机会，不据此声称收益或成本最优 | 低；固定锚点+步长 |
| C 每月最后一个交易日 after_close | 按月报表清楚 | session 间隔不固定，对短周期信号反应更慢 | 不等于任一预测 horizon | 通常调仓机会更少，但单次变化可能更大 | 中；月末日历及下一 session 边界 |

建议调仓信号日同时重新训练三模型；非调仓日不产生新交易目标。
若要每日诊断计算但仅定期交易，应将诊断与可执行信号分开记录，不偷偷改变调仓频率。
A/B 需在首次运行前指定 calendar_anchor 与首个 signal_date，不能根据表现或缺数据重新移锚。
不足训练数据时的计划日处理由 D07 决定；也不能把“跳过一次”自动改成另一套频率。

## 10. Holding/exit policy

**REQUIRED DECISION D03：**

- A 每次调仓按新目标组合重新计算差额订单（建议）。跌出目标则计划退出，保留标的也按新权重调整。
  优点是可复现、与目标权重一致；缺点是权重漂移会产生交易。
  “重构”不等于先全部卖出再全部买回；只交易目标与实际仓位差额。
- B 只在跌出 TopN 后计划退出，留在目标中的 ETF 保留实际份额，新进入者只使用可用现金。
  优点是可能减少对存量持仓的调整；缺点是权重路径依赖，仍须批准新入场分配、现金不足和共享 ETF 归属规则。

持有期由连续入选/退出和真实成交决定，可跨多次调仓；不得按 10/40/120 自动强平。
共享 ETF 只要仍属于当前有效目标，不因其原来关联的单个行业退出而重复卖出。
无法卖出时仍保留真实持仓，不在 positions 中伪造消失；撤单/重试见 D11。
未批准额外止盈、止损、持有期上限或缓冲带；不借用 smoke 的均线/止损规则。
回测末日持仓处理另见 D16，不能默认为以最后 close 无成本清仓。

## 11. Portfolio construction

流程：行业 score/rank → Top5 行业 → 历史有效 ETF mapping → ETF sleeve target weights
→ 总投资预算/现金 → 有约束的差额订单 → 实际持仓。后三步未完成 LEVEL B 接线。

**IMPLEMENTED，不能混用的三种权重：**

1. `sector_weights`：对 Top 行业按 `(score-min_score+1e-9)/sum(...)` 归一化，全相等时等权。
2. ETF candidates：去重后的代码、分数、关联行业和 relation，**不带 weight**。
3. `ranked_sectors_to_targets`：候选全带 weight 时规范化；全不带则 ETF 等权；部分带权拒绝。
   显式空候选仍为空，None 的旧行业描述路径不能当作 ETF 交易路径。

**D04**：A 去重 ETF 等权（建议，沿用当前 adapter 默认，最少附加假设）；
B 行业现有权重按明确映射矩阵聚合到 ETF；C 按去重 ETF max score 平移归一化。
B/C 是新增组合构建选择，不是现有 core 已完成的传递关系，需要另行实现/测试。
共享 ETF 会使实际 ETF 数少于 5；不通过第 6 名行业悄悄补足 5 只 ETF。

**D06**：资金预算另行批准。A 使用扣除已知费用和交易约束后的可部署资金；
B 预留固定现金缓冲后使用剩余预算（需明确参数）。建议 A 作为简单研究预算，不声称降低风险。
初始现金、单标的上限是否存在、取整方法、费用预留、现金利息口径必须填入运行配置。
单标的上限候选为不另加 sleeve 上限或显式固定上限（需数值及超额资金留现金规则）；
建议首基线不另加上限以免叠加组合实验，但应披露共享 ETF 导致的集中度，不称为风险控制。
两案都建议不杠杆、不卖空，仅研究设计建议；最终须批准。record-only 风险不自动决定预算。
行业/ETF sleeve 权重和为 1，不代表账户实际满仓，更不是已决定 risk budget。

## 12. Risk policy

**LOCKED：**RiskState 与 score/rank 解耦；`apply_risk_budget=NOT_IMPLEMENTED`。
禁止 score×confidence，也禁止 Top5→Top3 后重新满仓却称为降敞口。
保留原五指标/阈值/置信度映射，不调参数。

| 指标 | 当前判定（严格不等式） |
|---|---|
| 市场广度 | close>MA20 的有效行业比例 <0.4 为红 |
| 新高/新低 | 近 20 行 close 最大/最小，last>=max×0.995 计新高，否则 last<=min×1.005 计新低；新高数/max(新低数,1)<1.0 为红 |
| 截面波动 | 行业最近 5 个有效日收益均值的总体 std > 历史均值+1.5×历史总体 std 为红 |
| 成交集中度 | 正成交额 Top5 合计/max(全部正成交额合计,1.0)>0.35 为红 |
| 相关性 | 最近 20 个有效收益的行业相关系数非对角均值 <0.2 为红；忽略 NaN，全部无效时 legacy helper 返回 0 |

当前最少行业数 10、最少历史行数 25；风险价格窗口先截取距共同最后日期 120 个自然日内的行。
数据过短、最后日期不一致或不是 as_of 时返回 INSUFFICIENT_DATA。
默认 cross-vol 历史缺省均值=0.01、std=0.005；red_lights 为 0–1/2/3–5 时
confidence 分别为 1.00/0.85/0.70，**这些数值不是仓位比例**。

**D05**：

- A record-only（建议）：按信号时点记录状态、指标、覆盖率和错误，不据此改持仓。
  好处是隔离排名模型基线与风险择时；局限是没有风险状态触发的降仓保护。
- B 控制总敞口/现金：拟议接口 `budget(RiskState, as_of, approved_policy) -> exposure, cash, reason`。
  仅可提出“红灯增加不增加敞口”等候选约束；各档位、恢复/滞后规则、数据不足处置待批准，
  本文不填写任何敞口百分比，也不把现有 confidence 直接当 exposure。

未来评估必须显式传 as_of=t；历史 cross-vol 目前是无日期列表，需额外保证只含 t 前可见观测。
历史波动率缺省兜底仍是 legacy 行为，不是数据已充分的证明。
INSUFFICIENT_DATA 的中性字段不是安全开仓信号：A 下记录不可用，不自动变更仓位；
B 下必须有批准的异常策略。模型/映射自身不可用仍须按 D07 处理。

## 13. ETF mapping policy

当前状态：**legacy reference / requires_validation**；旧 21 ETF 不是 production truth。
本轮不联网核实、不批准任何具体产品。V03 必须逐历史日期验证：
ETF 存在及代码连续性、当日能否正常交易、行业暴露关系、历史起点/终点、
多行业同 ETF、行业无 ETF、一行业多 ETF、重复映射及变更的可得/生效时间。
ETF 当前存在不代表在回测起点可用；不得用后发行的产品填补历史。

当前规则：一行业一条映射；共享 ETF 保留最高行业 score，合并行业列表，direct 优先；
relation 标签不证明暴露准确。缺映射告警并跳过，不回填低排名行业；一对多记录拒绝；
候选重复或无效权重拒绝。穿透 sector_weights helper 不是核心已实现的 ETF 预算分配。

**D08**：A 保留已验证的一行业一 ETF，共享 ETF 按现有规则去重；未解决一对多阻止运行（建议，最贴近代码）；
B 经审核固定一对多分配矩阵，共享 ETF 聚合金额（额外组合假设，须单独实现）。
两案均须维护映射版本；重复键冲突不能靠 YAML 覆盖顺序决定。
选中行业无映射按 D07，而非默认资金转投其余 ETF。

## 14. Cost/execution assumptions

以下全部只是 **legacy initial assumptions**，不是已批准的生产规则：

| 项目 | 旧值 | 正式运行前必须批准/明确 |
|---|---|---|
| ETF commission | 0.00025 | 计费基数、买卖两侧、是否含其他费用、舍入 |
| minimum commission | 5 CNY | 按订单/成交笔/每日聚合计最低费，不能省略或双计 |
| stamp duty | 0 | 适用标的和历史区间的依据；本轮不作法律/税费有效性确认 |
| slippage | 0.001 | 是否是相对计划价的比例、买卖不利方向、是否包含价差，不能与成交模型重复计费 |

**D09**：A 用户明确批准上述数字作为研究简化场景，并补齐计费定义；
B 使用有版本和适用区间依据的费用/滑点规则（建议 B，可审计；若选 A 不称 production）。
当前 smoke 的 TC_Zero/未独立建模滑点不能继承为本策略成本。

**D10**：A 日频保守可成交性模型（建议，匹配当前基础）；B 分钟/成交级模型。
A 仍必须有历史停牌/限制价格/规则；日 OHLC 触及某价不能证明在计划时点能成交。
无法确认开盘可成交时保守拒绝，不用当日 close 判开盘订单是否可成交；
事后全天成交量只能用于明确标注的执行近似，不得提前决定 t 日信号或订单规模。
B 更细但要求新增数据，仍不保证有真实排队信息。
流动性筛选/参与率上限/订单最小单位/结算可卖性需明确值及来源，缺证据不得默认无限成交。
流动性约束候选为基于截至信号日历史成交量的订单上限，或有充分执行数据的时段参与率上限；
日频方案建议前者，回看窗口与上限数值仍待批准，不按策略收益选择。

**D11**：A 当日未成交余额撤销，下次批准调仓重新计算差额（建议，状态简单）；
B 有限 session 重试（必须批准有效期，遇到新目标先撤销旧单）。
两案都记录拒绝/部分成交原因；失败卖单不能假装释放现金支持买单。
建议执行先处理可卖出差额，再按实际可用资金和批准买入分配规则处理买单；
交易单位向下取整，现金不足候选规则为按买入预算同比缩减或按目标排序依次执行，待 D11 批准。
无行情不得交易；持有标的缺失行情时的估值与交易必须分离（D16）。

## 15. Temporal integrity rules

以下为 C，不是可选择放松的研究选项：

1. 所有特征/训练标签/映射/分类只用 decision_time 前可得信息；t close 后不在 t 成交。
2. 对每个训练日期 s，C[pos(s)+h]≤t 且对应价格已可见；不得绕过 purge。
3. 不 forward/backward fill 缺失 OHLC，不移动 label endpoint，不把未实现收益填零。
4. 不用未来行业分类、未来修订宏观快照或全样本 scaler；本 baseline 根本不启用后三类特征/变换。
5. 输入价格缺失与因子预热 NaN 分开处理；行业 coverage、失败 horizon、缺映射均记录。
6. 收益必须由真实模拟成交、现金、费用和持仓估值产生，不用重叠标签直接拼账户净值。
7. 两框架用同一有效日历和端点约定；查询接口闭开区间差异需验证并写入 Known Limitations。

**D12**：行业数据获取候选 A 权威来源的历史分类/价格版本；B 能提供相同定义与 PIT 证据的独立供应快照。
建议 A；B 必须核对定义与修订，不用当前行业名单回填历史。具体 source/version 尚未选择。
**D13**：A 经验证的原始行业价格指数 close + ETF 原始成交价/独立权息账务（建议，模型 close 定义透明）；
B 同一定义、按 as-of 可得事件构造的价格序列 + ETF 原始成交与权息账务，需验证与 A 的差异。
不得默认替换为 total-return index 或改 target；若 B 改变研究含义则移出 baseline。
任何复权口径都要验证数值过程，不能只凭“后复权”名称证明 PIT；禁用依未来事件重写历史的信号价格。
**D14**：A 保留当前 observation-row rolling 并逐窗报告缺口；B 要求相关输入窗口日历连续，否则阻止该次正式运行。
建议 B 做数据准入门槛，避免把“120 行”误称为“120 个连续交易日”；不得靠填行实现。
它是新增运行门槛，未改变现有因子算法，尚未实施/批准；对可运行区间的影响必须报告。
只检查截至信号日已知的历史窗口，不能用未来是否连续/存续筛选今天的行业池。

与旧 docs/data 的差异必须显式解决：最长标的日历未经验证不等于完整日历；
去交集不能压缩 horizon；close 等于某限制价不构成通用的开盘可成交性规则；
数据政策中“缺失成交量可填零”的一般许可不等于本策略采用，baseline 不制造未知量额。
上述更严格的正式运行要求不表示本轮已修补数据层或改写已生效通用政策。

## 16. Backtest reproducibility requirements

只有批准规格、通过 V01–V06、完成策略执行接线及对应测试的运行，才可命名为
**SW Sector Rotation Strategy Backtest**。本草稿不能满足该命名条件。

未来目录：`reports/backtests/sw_sector_rotation/<run_id>/`；每次独立，禁止覆盖旧产物。
metadata 必须显式写入 `run_type=strategy_backtest`、`strategy=sw_sector_rotation`。
不能依赖 BacktestMetadata 的默认 run_type 来证明执行了策略。

| 必需记录 | 要求 |
|---|---|
| git commit、代码/环境版本 | 可解析完整 commit；运行工作区 clean；镜像标识及依赖版本，禁止 unknown 冒充可追溯 |
| strategy_spec_version/path/hash | 获批版本、文件指纹、决策批准记录；不能只写旧策略包 version |
| config_snapshot/hash | 模型、因子常量、风险、映射、预算、执行和成本的实际生效值，不只复制未接线 YAML |
| data_snapshot/version | 内容指纹、source、coverage、修订/可得时间、calendar、adjustment、mapping 版本 |
| classification_version | 行业历史生效/可得区间及代码转换表 |
| date_range | 请求及实际区间、预热/训练区间、评价区间、端点约定、OOS 划分 |
| cost_model / rebalance_rule / execution_rule | 全部获批规则与参数，另含 holding/risk/budget/unfilled/valuation 规则 |
| framework / limitations | Hikyuu 或 RQAlpha 版本；不一致项逐项列出，不静默更改两侧参数 |

标准产物保留 metadata.json、metrics.json、trades.csv、positions.csv、equity_curve.csv、
yearly_returns.csv、report.md；图表按项目规范输出。
另保存信号/各 horizon 样本覆盖/目标权重/订单-成交-拒绝日志，以及 spec/config/data manifest 快照或引用。
需能追踪每笔成交来源 signal_date、decision_time、计划/实际执行时点、持有结束及费用。
未知指标为 null 并说明，不用零/估值冒充；账户估值与标签收益分开。
Sharpe 年化/无风险利率、净值频率和换手计算口径须固定，不能两引擎各用默认值。

当前 BacktestMetadata 没有上述完整 spec/config/classification/rule 字段；data_snapshot 可空，
runner 仍输出 execution_smoke，年度聚合等也有限制。需后续独立实现，**本文没有升级 schema**。
已有 LEVEL A 文件必须继续标记 execution_smoke，不能改名迁入正式策略目录。

**D15**：A 在数据合格范围内事前固定一个 walk-forward 评价区间；B 固定开发/保留 OOS 两段（建议 B，防止后续实验反复利用同一评价集）。
两案都逐信号日 purge，不提前拟合未来数据；不依收益选择日期。实际起止、首信号/日历锚点、
初始现金和 benchmark 必须在运行前批准。benchmark 候选为固定宽基或历史有效行业等权诊断，
建议固定宽基作账户比较；具体代码/价格口径须验证，不自动启用现有 ETF。

**D16**：末日 A 不强平、按可验证市值计价并披露未平仓（建议，避免人为末日交易）；
B 明确安排末日后可执行的清算 session 并计成本/扩展实际区间。
持仓缺行情估值候选：可验证的独立估值源，或单独标记的 last-known mark；后者仅估值、绝不生成行情行或成交。
建议优先可验证估值源；两者均无可靠依据时净值不可声明完整。
现金利息可选研究简化的零计息或有版本的利率曲线；建议首基线零计息并明确披露，待批准。

## 17. Baseline v1 locked assumptions

| 项目 | LOCKED 值 |
|---|---|
| Feature schema | 第 3 节固定顺序 19 个 price features，raw scale |
| Exclusions | RSRS 不入模；momentum/volume ratio/fundamental 不入模；Macro/Flow disabled |
| Model / alpha | NumPyRidge / 0.01；不做 feature scaling |
| Target | absolute close-to-close forward return |
| Horizons / training | 10/40/120 trading sessions，各自独立训练；每次 core.run 重训 |
| Fusion / selection | 0.25/0.50/0.25，三周期交集 z-score，Top5 上限 |
| Train window / minimum | 从各自 label cutoff 回溯 6 个日历月；≥30 个有效不同训练日 |
| Sample weighting | 每个有效 sector observation 同权，不按日期平衡 |
| Risk separation | 不改 score/rank，原阈值不变，risk budget 未实现 |

锁定不代表策略最优或已可交易。Dxx 的建议值均未写进 YAML、代码或运行计划。

## 18. Research decisions still required

所有行当前均 **PENDING USER APPROVAL**。建议仅基于实现清晰度、审计性和变量隔离，非收益判断。
数据真伪/PIT/禁止同日成交等 correctness 底线没有“放松版”选项。

| ID / 类别 | 2–3 个候选方案 | 建议与理由；仍须补齐 |
|---|---|---|
| D01 E 成交价格 | 下一 session open；明确时段 VWAP | open 计划价，日频更易核验；成本/可成交模型仍不可缺 |
| D02 R/E 调仓 | 每 5 session；每 10 session；月末 | 10 session，调度简单；批准锚点/首个信号，不等同持有 10 日 |
| D03 R 持仓退出 | 每次目标差额再平衡；仅跌出 TopN 退出 | 目标差额再平衡，目标与持仓关系更明确 |
| D04 R ETF 权重 | 去重 ETF 等权；行业权重聚合；ETF max score 归一化 | 等权，保留 adapter 默认，避免暗加映射分配假设 |
| D05 R 风险政策 | record-only；控制总敞口/现金 | record-only，隔离首条模型基线；B 的比例/恢复规则不得留空 |
| D06 E/R 资金预算 | 费用后可部署预算；固定现金缓冲预算 | 前者，少一个任意参数；初始现金/上限/取整和现金利息需批准 |
| D07 C/E 信号或映射不足 | 终止并标记未完成；跳过本次调仓保留真实持仓/现金 | 首基线终止，避免隐含选择偏差；包括 NOT_READY、Top 不足 5、选中映射缺失；并非追溯性清仓 |
| D08 R 映射分配 | 现有单映射+共享去重；审核的一对多矩阵 | 前者，最少代码差异；无一对多分配授权，V03 仍必需 |
| D09 E 成本 | 明确批准 legacy 研究假设；核验后有版本的成本模型 | 后者，可追溯；若前者也须批准双侧、最低费、滑点等全部定义 |
| D10 E 可成交模型 | 日频保守；分钟/成交级 | 日频保守，匹配当前基础；历史限制及流动性参数证据不可省略 |
| D11 E 未成交/资金不足 | 当日撤余单；有限 session 重试。买入不足按预算同比缩减或按排名依次分配 | 当日撤单+同比缩减建议，减少队列状态和任意优先级；卖出失败不释放现金 |
| D12 C 数据取得 | 权威历史版本；同定义且有 PIT 证据的独立供应快照 | 权威版本优先；实际 source/version、历史池和 V01–V06 都需落地 |
| D13 C/R 价格口径 | 原始行业价格指数+ETF 权息账务；同定义的 as-of 调整序列+ETF 权息账务 | 前者，避免暗改 close 含义；需证明分红/拆分处理与数值不泄漏 |
| D14 C 缺日准入 | 保留 observation-row 窗口并报告缺口；要求相关窗口连续否则中止 | 后者，避免行数与 session 数混用；准入门槛未实现，不能静默缩窄样本 |
| D15 R 评价设计 | 固定单区间 walk-forward；开发/OOS 事前分段。benchmark 为固定宽基或历史行业等权 | 分段+固定宽基建议；日期、锚点、基准和指标公式运行前签字，不根据收益选择 |
| D16 E 结束/估值 | 末日不强平；后续 session 清算。缺价用独立估值或标记 last-known mark | 不强平+优先独立估值；现金零计息简化或版本利率曲线，建议前者并披露 |

批准记录至少包含 decision_id、selected_option、完整规则/参数、approved_by、approved_at、spec_version。
本轮没有写入批准记录；不能把建议自动视为用户同意。

**LEVEL B readiness gate：**

- [ ] D01–D16 的关键规则、参数与异常处置获批并形成无歧义规格。
- [ ] V01–V06 数据证据齐全，验证历史有效映射、价格与交易约束。
- [ ] 策略专属多 ETF 执行适配、时间校验、预算/成本/订单状态和报告字段实现并通过测试。
- [ ] Hikyuu 与 RQAlpha 的共同输入/规格/一致性测试就绪；差异记入 Known Limitations。
- [ ] 冻结 spec/config/data/代码版本与评价计划，并获得运行授权。

**当前答案：不足以开始 LEVEL B。** 用户选择只是必要条件，不替代数据验证和执行层实现。
仅当上述门槛满足才可改为 `STRATEGY SPEC V1 READY FOR LEVEL B`；本轮仍不运行回测。

文档阶段验收：Docker 默认 pytest 为 306 passed / 2 skipped / 10 deselected / 2 warnings，
与前轮总用例数相同（本次原 AKShare 网络测试通过）；未增删测试，integration 仍排除。
这是代码基线检查，不是策略验证。原审计里的 305 passed / 3 skipped 为当时网络状态。

## 19. Future experiment matrix

以下只定义，不执行；Baseline v1 的锁定项不因此开放修改。
批准的交易/成本/映射/评价区间和数据快照在对照中固定，单次仅改变一个核心研究变量。

| 实验 | Baseline v1 | 单变量对照 | 额外正确性要求 |
|---|---|---|---|
| A | raw features | training-window standardized features | 各 horizon 仅用其训练窗口拟合 mean/std，推理复用；常数列确定处理；禁止全样本 scaler |
| B1 | absolute forward return | cross-sectional demeaned return | 历史有效横截面、标签已实现，不能顺便改权重/特征 |
| B2 | absolute forward return | 明确基准的 relative return | 与 B1 分开运行；基准价格定义及时间一致，不在结果后选择基准 |
| C | per-observation weighting | date-balanced weighting | 标签/特征/模型参数不变，明确定义每天和每行业样本权重 |

rank/percentile target、RSRS 入模、alpha/horizon/fusion 权重、新因子均为其他独立研究，
不得与 A/B/C 同时变更。未来实验保存独立 experiment_id、parent_baseline、唯一变量差异和完整元数据，
不得覆盖 Baseline v1 结果，也不能将多个变化后的表现称为某一变量的因果效果。

## 20. LEVEL B research authorization and data gate

本次任务批准：t after_close → 下一 session open；每 10 个交易日目标差额再平衡；
Top5 行业 → validated primary ETF → ETF 去重等权；RiskState record-only；
未成交订单当日取消；期末 mark-to-market、不强平。
保留全部第 17 节模型基线。成本 0.00025 佣金、最低 5 CNY、印花税 0、滑点 0.001，
记录为 `research-cost-v1`，不是生产费率声明。最低佣金聚合、资金取整、可成交性等细节仍须明确。

旧决策编号的更新：D01=open、D02=10 sessions、D03=目标差额、D04=去重 ETF 等权、
D05=record-only、D08=validated primary（未验证的 legacy proxy 不自动获得批准）、
D09=上述研究成本数字、D11=当日撤余单、D16=期末不强平，D15=按时间 Development/Validation/Final OOS。
该批准记录只约束未来 LEVEL B；没有改动现有 core 的模型/参数或 LEVEL A 执行模型。

研究计划配置：[sw_sector_rotation_level_b_research.yaml](../config/sw_sector_rotation_level_b_research.yaml)。
**它是声明式计划，当前 core/runner 不读取它，不能作为已实现的执行/OOS 隔离系统。**
数据检查报告：[baseline_v1_research_report.md](baseline_v1_research_report.md)。

当前合格行业数据范围、历史分类/映射版本均未知，因此三段 start/end、rebalance_anchor、
partition lock commit 均为 null，dates_locked=false，OOS_LOCKED=false。
不以现有 ETF 数据范围冒充完整行业可研究范围；不机械用 60/20/20 填日期。
正式数据仍不足，按用户要求停止于数据阶段，未运行 Baseline 或参数研究。

后续分区必须遵循：

1. 先按历史有效行业和 ETF 的实际可用覆盖确定研究范围，预留 120 日 label purge、
   各 horizon cutoff 前 6 个月训练窗及 120 行特征预热；不能把预热不足当作有效评价区间。
2. 时间顺序 Development → Validation → Final OOS；60/20/20 仅为参考。
   牛/熊/震荡覆盖不是凭比例能保证的。需事先定义客观行情状态口径和最短区间要求，
   若实际跨度不足以让三段均有充分状态覆盖，暂停并报告，不能反复看 OOS 后挑边界。
3. 边界、评价/基准/成本定义及研究选择门槛在研究前写入配置并 commit。
   在此之前只做覆盖/质量核查，不计算或展示 Final OOS 策略绩效。
4. 每个 prediction date 仍调用原滚动训练：从该 horizon 的 label_cutoff 回溯 6 个月，
   不是整段 Development 拟合一次。用于 Development/Validation 研究的标签终点不得越入 OOS。
5. 先保留 Baseline 的 Development/Validation 结果，再按单变量分阶段研究；
   保留失败与非最优实验，不使用 OOS 指标或曲线选参数。
6. 最多 Baseline + 两个候选，冻结参数、候选名单及其锁定 commit 后设 OOS_LOCKED=true。
   此字段不能仅靠手动布尔值替代实际 commit/快照/候选一致性校验。
7. 冻结规则下 OOS walk-forward 可以使用当时已经实现的历史标签更新模型系数，
   但不能据 OOS 表现更改超参数、模型定义、映射、成本、频率或候选名单。
8. Final OOS 只做一次最终评价；结果差则报告失败，不回调参数后重新使用同一 OOS。
   跨分区持仓延续/独立账户、估值与全区间拼接口径需预先定义，不能简单相乘独立区间收益冒充连续账户。
