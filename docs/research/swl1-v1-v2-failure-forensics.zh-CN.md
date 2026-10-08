# SWL1 Ridge V1/V2 失败归因 — POST_HOC_FAILURE_FORENSICS

NOT_A_NEW_VALIDATION · NOT_A_NEW_FINAL_OOS · NOT_A_NEW_MODEL_GENERATION · NOT_PREREGISTERED_PREDICTIVE_EVIDENCE

## 结论与证据强度

V1、V2 均保持 **FAILED_VALIDATION**，Final OOS 未开启、forward=false、ETF 产品化 NOT_STARTED。本次2,427次冻结拟合精确重放、原始指标树和V2拟合元数据哈希全部一致。在允许审计的源代码和行业面板范围内，确认的target/拟合/评估实现缺陷=0、数据完整性缺陷=0；另确认1项历史读取隔离缺口：原执行器在阶段评估前载入完整数值面板。因此历史数值访问隔离、原始股票/成员/复权数据的独立真实性均不能由当前证据证明。

主要描述性失败模式是**样本外时段的周期方向错配**，V2尤其集中在H120；不同周期预测排序高度一致，难以分散错误方向。唯一因果根因仍不可识别，不能声称“正则化过强导致失败”或“修复某个因子就能成功”。建议下一步 **DATA_FIRST**，对行动顺序的置信度中等，对任何下一代预测成功不作承诺。[English report](swl1-v1-v2-failure-forensics.md) 与下方完整数值附录使用相同证据。

## 冻结谱系与本次范围

基线main为`2d1a235af8fb770fcde14fdafd36da86a174875a`。V1选定B/12m/alpha100，V2选定B/24m/penalty10且alpha=10×实际训练行业行数；均为19因子、STANDARDIZED、30行业、H10/H40/H120和0.25/0.50/0.25权重。V1已有20规格，V2已有16规格、3个admitted；本次只重放两个已冻结的选定规格，不搜索其他规格，不触发生命周期，不重写结果。

核验原始protocol/candidate/Development/Validation/status、冻结实现文件和私有数据字节哈希；四阶段原始汇总及V2 fit trace、实际alpha范围一致。完整哈希在附录及[evidence manifest](../../reports/research/swl1_failure_forensics/evidence-manifest.json)。[V1原始结果](swl1-ridge-v1-results.md)、[V2原始结果](swl1-ridge-v2-results.md)保持原状。

## 已消费信息边界

| Phase | Signal range | Last H10 outcome | Last H40 outcome | Last H120 outcome |
| --- | --- | --- | --- | --- |
| v1 development | 2023-08-02 — 2024-03-25 | 2024-04-10 | 2024-05-27 | 2024-09-19 |
| v1 validation | 2024-09-20 — 2025-04-01 | 2025-04-16 | 2025-06-03 | 2025-09-23 |
| v2 development | 2023-08-02 — 2025-03-31 | 2025-04-15 | 2025-05-30 | 2025-09-22 |
| v2 validation | 2025-09-23 — 2026-04-07 | 2026-04-21 | 2026-06-05 | 2026-09-29 |


V1最后目标日2025-09-23，V2和并集最后目标日2026-09-29，分别为完整交易日脊柱索引1006和1251。实际转换为数值的收益仅1,252行；特征只到最后信号索引1131，共1,132行。日期/code/header只作非绩效元数据。边界manifest先于数值解码写入独立scratch。

### 声明消费边界与历史数值访问必须分开

冻结[V1执行器](../../research/swl1_ridge_v1/execute.py)第32–33行、[V2执行器](../../research/swl1_ridge_v2/execute.py)第88–89行在Development claim之前调用`np.load`并读取完整`features`/`returns`成员，实际会物化整张数值面板，包含各自声明目标消费边界后的行。manifest以冻结源码哈希记录该事实；这是源码证据，不是运行时或人员查阅记录。原评估器和拟合函数正确限定目标与成熟标签，已消费汇总全部精确重放；未发现未来尾行进入target、sealed OOS绩效被计算或此缺口导致失败的证据。

原maturity/lineage证明只覆盖声明目标区间，**不能证明历史访问隔离**。算术PASS不能证明V2 Validation数据在先前构造/执行面板时不可接触；2026-09-30虽在声明消费边界外，也不能认证为历史未看。可认证独立未看的历史尾部交易日=0。这是C类有证据的访问控制限制，不能推断人员看过尾行、数值模型有bug或某个因果效应。两个冻结失败、原协议/证明/结果字节保持不变。未来研究必须通过prospective访问隔离保护结果，仅有未开启的生命周期不能阻止数组读取。

本次压缩文件收益采用Fortran列优先存储。读取器逐列仅把允许行前缀转换成浮点数；29个间隔尾段共232字节只作为布局字节跳过，末列尾段不解码。声明消费边界外的2026-09-30收益在本次不进入数组、目标、IC、spread；未来121行特征不转换。完整文件哈希只校验不透明字节，不解释绩效。对C和Fortran格式都用故意注入未来收益的对抗测试验证本次隔离，不能据此推断旧进程的访问行为。

V2 Dev复用V1全部156个Dev信号，并包含125/126个V1 Validation信号；V2 Validation复用125/126个原计划V1 OOS信号日期。V1 OOS流程未打开，但这些由V2消费过的收益已不能再次宣称unseen。相同历史文件不意味着相同证据角色或独立性。

## Target 与实现正确性

标签严格取t+1..t+h共h个交易日复利收益，训练时扣除同一训练日期完整30行业均值。每个h独立以i≤t-h限定成熟标签；窗口为日历12/24个月，至少30个完整训练日期。标准化总体均值和标准差只来自成熟训练行，常量scale设为1，截距为中心化标签均值。

评估用average ties的Spearman；原始收益扣同一行业均值不会改变排名或Top5-Bottom5 spread。历史Top5/Bottom5是**带正负号的原始复利收益**，不是绝对收益或中心化收益。V1 Bottom5取降序排序末尾；V2对低分单独按code升序打破平局。合成测试保留差异，实际冻结重放未受影响。V1块为等样本数，V2块为等日历长度；无原始信号丢弃。因子最大重建误差7.2475e-13、标签中心化仅有浮点误差。原始股票聚合管线未重新执行。

## 数据来源、PIT 与重建风险

主要序列RECONSTRUCTED_SWL1_EQUAL_WEIGHT；历史成员RECONSTRUCTED，TierA=0、B=0、C=6,515,140个上市股票/交易日行；1,406个未知归属行被排除。当前分类31行业，冻结30，510000因递归事实缺口排除。SWCLASS2021显式父子关系只在2021-07-31版本边界后使用，不按code前缀倒推。

来源使用后来观察到的历史成员区间，没有当时发布/可得性证明。源代码检查上市/退市区间、精确相邻交易日、正成交量/复权因子、有限复权收盘比、绝对股票日收益≤0.5；每行业日需至少5成员和80%有效覆盖，内部缺口不重启递归序列。这些是构造规则，不是独立真值核验。复权信息是否当时可得、退市历史是否完整、成员回溯是否偏向幸存者仍不可识别。

宇宙使用全历史连续覆盖选择，存在以未来可用性筛选行业的回溯选择风险；覆盖中位数1.0不能消除风险。有效成员等权聚合也不同于官方指数。偏差方向/大小与独立目标真值为 **NOT_COMPUTABLE_WITH_ADMITTED_EVIDENCE**。本次没有引入官方指数或根据表现选择新target，也未读取SWL2 sealed结果。

## Ridge：稳定求解与强收缩同时成立

审计标准化Gram特征谱、奇异值、条件数、实际alpha/n、斜率df和贡献分解。斜率df=Σs²/(s²+alpha)，不含形式上的未惩罚截距；中心化标签让截距近零，也不能把df当独立样本数。[标准推导](https://www.math.ntnu.no/emner/MA8701/2023v/MA8701V2023/Part2/L7.html)、[NumPy条件数定义](https://numpy.org/doc/2.3/reference/generated/numpy.linalg.cond.html)。

V1 Val alpha/n中位数约0.0144/0.0165/0.0273，V2全为10；V2斜率df约1.29，V1约14.69–16.44。V2正则Gram条件数约2，线性求解残差q95<3e-16，因此H120不能解释为数值不稳定。V2 H120最强5个Gram方向平均贡献80.36%、最弱5个0.88%；V1对应27.12%/17.54%。贡献是当前横截面标准差的L1占比，不是正交方差或因果归因。

V2明显处于强收缩区间。共同156个Dev日期上，各周期排名每天都与V1发生变化，否定“只有幅度缩小”；但12/24月窗口、penalty、候选选择同时变化，无法单独识别alpha或窗口的作用。本次没有重试其他参数。

![Ridge诊断](assets/swl1-failure-forensics/ridge-conditioning.svg)

来源/范围为上表各自已消费Dev/Val冻结拟合；计算逐拟合条件数/斜率df再取中位数；后验描述，不证明最优正则或新模型有效。

## 19因子与系数方向

所有19因子均从过去重建收盘价得到；信号日无缺失，19因子横截面离散度中位数均为正；V1 Dev/V1 Val/V2 Dev分别有7/21/32个因子-日期近常量横截面，来自位置/回撤/align饱和，V2 Val为0。不存在整个阶段恒定的因子；经济适用性未验证。完整定义、lookback、尺度、离散度、时间漂移、相关矩阵、各周期系数正负/大小/持续性及贡献在附录和JSON。

V2 Val d10/rev5相关-0.9240，d20/rev10=-0.9094，d60/d120=0.9023，存在明显冗余。相关系数和模型系数不能当独立因果效应，不据此挑选“最好的因子”。V2相邻拟合系数余弦中位数≥0.99986，方向稳定不等于预测稳定。H120所有d5..d120系数在全部Val日期为负，但d120对实际H120目标的均值RankIC为+0.24055，存在直接描述性方向错配。

![因子相关性](assets/swl1-failure-forensics/factor-correlations.svg)

![系数符号](assets/swl1-failure-forensics/coefficient-signs.svg)

来源/范围为各自已消费Validation；图1为信号×行业池化Pearson相关，图2为逐因子系数为正的日期比例；后验探索、相关因子非独立效应，不公开逐日拟合。

## H10/H40/H120 与融合

V2 H10均值略正，H40近零且块间转变，H120四个块均负；Dev后两个块H120也已负。不能把H120负向仅归给单个Val时期。本数据也**不支持统一的“短周期动量延续、长周期均值回归”故事**：V2 Val d10/H10=-0.07273、rev10/H10=+0.09531，而d120/H120=+0.24055。短期反转与长周期延续仅为已看数据的相关性，不是验证成功。

V2 Val预测周期相关约0.905–0.963，实际目标排名相关约0.316–0.579，预测Top5重叠约81–83%。不同周期模型大多给出同一行业排序，并没有有效分散周期风险；18–20%的系数符号分歧也未形成明显不同排名。V1周期预测则更不一致，部分方向相反。

原始加权IC分解为H10 +0.010162967671、H40 +0.000045906386、H120 -0.040332291611，合计-0.030123417554。只是对冻结0.25/0.50/0.25指标的数学分解，没有删除/反转H120、调权、计算新候选或新可交易表现。

![原始周期结果](assets/swl1-failure-forensics/horizon-outcomes.svg)

![周期一致性](assets/swl1-failure-forensics/horizon-coherence.svg)

来源/范围为各自原始Dev/Val冻结拟合；计算每日横截面RankIC均值、跨周期Spearman及Top5交集/5；后验描述，Validation日期不同且标签重叠，不能判定代际因果优劣。

## 状态变化与训练窗口

计算前限定代理：过去20日等权行业市场趋势/波动、当日横截面离散度/同涨同跌、日收益协方差、相邻预测排名稳定性、19因子分布漂移；只分固定4日历块，不搜索月份/波动阈值/行业子集。V1 d120 Dev→Val池化均值漂移2.7345个DevSD，V2为0.4120；V2日收益协方差有效维度从1.579变为2.595。状态变化存在，因果机制未证明。

V2 H120 Val训练行10,860–11,010，V1为3,480–3,690；长周期成熟约束天然排除最近标签。较长窗口与稳定系数可能保留过时方向，但无法与正则、来源、选择或时期效应分离。未试6/9/18/36个月窗口，也未训练状态模型。

![日历块](assets/swl1-failure-forensics/calendar-blocks.svg)

来源/范围为各阶段原始信号范围内4个等日历长度块；计算块内RankIC均值，日期/样本数见附录；后验探索，V1正式gate仍为等样本数，各块并非独立。

## 30行业与统计解释限制

Top5为宇宙的1/6。日原始收益协方差参与率约1.45–2.59、第一主成分占60–83%，说明共同市场波动较强；不能把它解释成中心化排名只剩1–3个自由度。删除行业敏感性在保持冻结预测/拟合不变的29行业排名上计算，标记EXPLORATORY_LEAVE_ONE_OUT_DIAGNOSTIC。

V2 H120“每天挑最有利的一个行业删除”的均值上界仍为-0.08838，因此任意固定单行业删除也不能使阶段均值转正；不排除相关行业群、来源偏差或其他机制，不形成新宇宙。126日信号不是126个独立样本；该信号跨度最多容纳H10/H40/H120的13/4/2个不重叠目标区间，训练与状态依赖仍存在。没有IID显著性、p值、盈利或独立验证胜利声明。

![横截面限制](assets/swl1-failure-forensics/cross-section.svg)

来源/范围为各自Dev/Val信号日30行业原始日收益；计算trace(C)²/trace(C²)及最大特征值/trace(C)；后验描述，不是独立时间样本量或排名df。

## 同日期比较与归因分类

两代同宇宙、同事实面板、同target定义，但Validation日期、实际收益、块定义不同。共同156个Dev日期上V1/V2的H10 IC=-0.01615/+0.07519，H40=+0.15877/+0.20286，H120=+0.18331/+0.08843；预测排名相关0.6340/0.7340/0.01981。说明规格组合确有差异，不能证明V2全面优于V1或某个penalty最优。V2设计与Dev也已受到V1 Validation结果影响。

归因矩阵区分A确认实现缺陷、B确认数据完整性缺陷、C支持的描述模式、D合理未确认假说、E现有证据反驳、F不可识别。A/B在target/拟合/评估审计范围为0；历史读取隔离缺口1项归C，不能推断人员查阅或数值影响。C还包含强收缩、冗余、稳定但长周期错误方向、状态漂移和依赖；D包括24m过时方向/过度正则机制；成员偏差大小和唯一根因仍F。详见[机器矩阵](../../reports/research/swl1_failure_forensics/attribution-matrix.json)和附录，不能用测试全过证明经济模型正确。

## 下一代建议与真正未看数据

五路线详见[设计审查](swl1-next-generation-design-review.md)和[机器选项](../../reports/research/swl1_failure_forensics/next-generation-options.json)。推荐DATA_FIRST：先获取授权、成员当时可得性和独立来源语义证明，再决定是否值得独立预注册短期反转/轮动假说。H10只是已看结果启发的候选研究方向，不是运行中的新家族。所有下一代protocol/candidate/training/Validation均未开始。

范围级库存：V1声明目标消费到2025-09-23、V2到2026-09-29；边界之外只有2026-09-30一个交易日，本次未数值读取，但原执行器完整物化面板，因此其历史状态为NOT_CERTIFIED_UNSEEN，可认证独立未看的历史日=0。未来仅指超出当前脊柱的prospective日期；缺失资料包括成员 contemporaneous proof 和独立授权官方指数。当前没有在并集之后完整成熟的H10/H40/H120标签，没有合法成熟的新一代独立Validation/Final OOS阶段。旧OOS未开启并不意味着其数据从未被访问或其被其他已消费horizon覆盖的收益仍独立。

将来先按来源质量冻结目标，不根据已看表现挑源；公开独立result-free协议、经济方向、有限因子/窗口/选择规则、成功失败标准和完整union边界，然后才可接触新目标。未来Validation目标起点必须晚于已看收益和经批准的未来观察边界，逐交易日核验成熟与阶段分离；仅126个连续H120信号就至少需要245个未来目标交易日，依赖仍存在，阶段间隔额外增加等待。未来Validation通过后再开启 untouched Final OOS。不能为减少等待降低证据要求。

## 可复现性与工程边界

量化计算只在独立固定依赖Docker中，科学容器断网，面板和已消费生命周期目录只读，未挂载live/runtime/CNEquity。CLI默认只校验元数据/哈希，不写盘或拟合；明确--replay与独立--scratch才重放冻结候选。30项合成测试覆盖hash/path/layout、未来尾行、成熟边界、targets、df/condition、系数贡献、常量/相关因子、缺失系数、ties/calendar blocks、日期混淆、公开redaction与parity失败；正式生命周期从未调用。

公开仅汇总JSON和静态SVG，逐日预测/系数保存在QuantForge独立私有研究目录，未公开股票价格/成员名单。普通fresh clone和CI不需要数据也不重放实际研究。[新的完整性层](../../reports/engineering/swl1-forensics-access-integrity.json)与[工程验收](../engineering/swl1-failure-forensics.md)记录本次变化和回归；旧证书和冻结字节不变。四家族API/status未改变，没有启用scheduler、部署、formal forecast、ETF事件或真实订单。

## Auditable numerical appendix / 可审计数值附录

Every value below is a public aggregate from the 2,427 exact selected frozen fits, at the native consumed signal ranges listed above. No individual industry or per-date coefficient/prediction series is published. **EXPLORATORY_POST_HOC** throughout. Source: [summary](../../reports/research/swl1_failure_forensics/summary.json), [manifest](../../reports/research/swl1_failure_forensics/evidence-manifest.json). Correlation and sensitivity are descriptive, not causal. 此处均为已消费范围的汇总，不构成新的验证。

### Native results / 原始结果

| Phase | Signals | H10 IC | H40 IC | H120 IC | Composite | Weighted spread | Native positive blocks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v1_development | 156 | -0.016146 | 0.158766 | 0.183309 | 0.121174 | 0.026232 | 4/4 |
| v1_validation | 126 | -0.140064 | -0.074015 | -0.017137 | -0.076308 | -0.015404 | 2/4 |
| v2_development | 401 | 0.037213 | 0.111010 | 0.022181 | 0.070354 | 0.009443 | 4/4 |
| v2_validation | 126 | 0.040652 | 0.000092 | -0.161329 | -0.030123 | 0.000668 | 1/4 |


### Training rows and numerical conditioning / 训练与数值条件

| Phase/H | Rows min..max | alpha/n median | Gram cond median | Regularized cond median | Slope df median | Coefficient norm median |
| --- | --- | --- | --- | --- | --- | --- |
| v1_development/10 | 6960..7170 | 0.014245 | 716.32 | 362.486 | 16.461 | 0.009723 |
| v1_development/120 | 3660..3870 | 0.026882 | 759.68 | 258.769 | 14.989 | 0.026270 |
| v1_development/40 | 6060..6270 | 0.016340 | 713.37 | 336.377 | 16.216 | 0.017629 |
| v1_validation/10 | 6780..6990 | 0.014368 | 701.60 | 354.428 | 16.435 | 0.011586 |
| v1_validation/120 | 3480..3690 | 0.027322 | 810.41 | 262.129 | 14.690 | 0.073491 |
| v1_validation/40 | 5880..6090 | 0.016502 | 722.22 | 330.853 | 16.099 | 0.023557 |
| v2_development/10 | 10680..14460 | 10.000000 | 640.23 | 2.011 | 1.275 | 0.000341 |
| v2_development/120 | 7380..11160 | 10.000000 | 689.67 | 2.017 | 1.271 | 0.001669 |
| v2_development/40 | 9780..13560 | 10.000000 | 655.76 | 2.012 | 1.274 | 0.001055 |
| v2_validation/10 | 14160..14310 | 10.000000 | 595.58 | 1.997 | 1.288 | 0.000253 |
| v2_validation/120 | 10860..11010 | 10.000000 | 606.76 | 1.996 | 1.290 | 0.001639 |
| v2_validation/40 | 13260..13410 | 10.000000 | 598.73 | 2.000 | 1.287 | 0.000609 |


The Gram condition is eigen_max/eigen_min; regularized condition=(eigen_max+alpha)/(eigen_min+alpha). Slopes df=sum eigen/(eigen+alpha). Full averaged 19-value spectra, singular-value quantiles, alpha ranges and solve residuals are in JSON. Slope df excludes the formal unpenalized intercept; the centered labels make its fitted value approximately zero. No df is interpreted as independent observations.

### Coefficients and contributions / 系数与贡献

| Phase/H | Median adjacent beta cosine | Median relative beta change | Median Top3 contribution share | Mean weakest5 eigen share | Mean strongest5 eigen share | IC lag1 |
| --- | --- | --- | --- | --- | --- | --- |
| v1_development/10 | 0.998759 | 0.051728 | 0.403203 | 0.237057 | 0.394248 | 0.722272 |
| v1_development/120 | 0.997420 | 0.072669 | 0.424284 | 0.193425 | 0.290279 | 0.750604 |
| v1_development/40 | 0.998460 | 0.057222 | 0.425436 | 0.147301 | 0.435193 | 0.847688 |
| v1_validation/10 | 0.999157 | 0.044577 | 0.483559 | 0.319630 | 0.281997 | 0.591948 |
| v1_validation/120 | 0.998993 | 0.049179 | 0.613675 | 0.175406 | 0.271241 | 0.841347 |
| v1_validation/40 | 0.999103 | 0.044197 | 0.427501 | 0.252252 | 0.173423 | 0.881376 |
| v2_development/10 | 0.999930 | 0.012801 | 0.432237 | 0.014966 | 0.870413 | 0.811221 |
| v2_development/120 | 0.999960 | 0.010740 | 0.484461 | 0.004772 | 0.876506 | 0.911030 |
| v2_development/40 | 0.999968 | 0.008845 | 0.381163 | 0.009244 | 0.904641 | 0.854435 |
| v2_validation/10 | 0.999864 | 0.018261 | 0.381388 | 0.009058 | 0.758823 | 0.749764 |
| v2_validation/120 | 0.999958 | 0.009454 | 0.395696 | 0.008758 | 0.803623 | 0.782260 |
| v2_validation/40 | 0.999919 | 0.013607 | 0.326229 | 0.014119 | 0.804108 | 0.815974 |


Adjacent cosine uses beta_t dot beta_(t-1) divided by their norms. Relative change uses norm(beta_t-beta_(t-1))/norm(beta_(t-1)). Factor contribution share is std_i(z_ij beta_j)/sum_j std_i(z_ij beta_j). Eigen shares use the same L1 dispersion accounting in the ordered training-Gram eigenbasis. These shares do not add to an orthogonal prediction-variance attribution when current exposures are correlated. Eigenbases change across fits. 相关因子贡献不是因果贡献。

### Unified calendar blocks / 统一日历块

| Phase/block | Count | Signals | H10 IC | H40 IC | H120 IC | Composite |
| --- | --- | --- | --- | --- | --- | --- |
| v1_development/1 | 42 | 2023-08-02 — 2023-09-28 | 0.006685 | 0.021876 | 0.131564 | 0.045500 |
| v1_development/2 | 36 | 2023-10-09 — 2023-11-27 | -0.016228 | 0.091806 | 0.072513 | 0.059974 |
| v1_development/3 | 42 | 2023-11-28 — 2024-01-25 | -0.052524 | 0.236813 | 0.260671 | 0.170443 |
| v1_development/4 | 36 | 2024-01-26 — 2024-03-25 | -0.000260 | 0.294376 | 0.264220 | 0.213178 |
| v1_validation/1 | 30 | 2024-09-20 — 2024-11-07 | -0.292354 | -0.141876 | -0.037449 | -0.153389 |
| v1_validation/2 | 34 | 2024-11-08 — 2024-12-25 | -0.101799 | 0.187921 | 0.142524 | 0.104142 |
| v1_validation/3 | 27 | 2024-12-26 — 2025-02-11 | 0.049660 | 0.134594 | -0.041668 | 0.069295 |
| v1_validation/4 | 35 | 2025-02-12 — 2025-04-01 | -0.193059 | -0.431228 | -0.135903 | -0.297855 |
| v2_development/1 | 102 | 2023-08-02 — 2023-12-29 | 0.019573 | 0.180436 | 0.087260 | 0.116926 |
| v2_development/2 | 98 | 2024-01-02 — 2024-05-31 | 0.109650 | 0.148006 | 0.229084 | 0.158687 |
| v2_development/3 | 100 | 2024-06-03 — 2024-10-30 | 0.059938 | 0.043146 | -0.125980 | 0.005062 |
| v2_development/4 | 101 | 2024-10-31 — 2025-03-31 | -0.037756 | 0.072192 | -0.097607 | 0.002256 |
| v2_validation/1 | 29 | 2025-09-23 — 2025-11-10 | 0.093476 | 0.252733 | -0.304453 | 0.073622 |
| v2_validation/2 | 35 | 2025-11-11 — 2025-12-29 | 0.000019 | -0.041182 | -0.092782 | -0.043782 |
| v2_validation/3 | 32 | 2025-12-30 — 2026-02-13 | -0.004004 | -0.121524 | -0.094327 | -0.085345 |
| v2_validation/4 | 30 | 2026-02-24 — 2026-04-07 | 0.084627 | -0.066251 | -0.174416 | -0.055573 |


Four equal calendar-duration blocks over each phase's own registered first/last signal dates. These exploratory V1 blocks differ from its immutable native equal-count gate; V2 blocks match its original gate. Unequal periods remain unequal. They are not four independent experiments.

### Cross-horizon coherence / 周期一致性

| Phase/pair | Prediction rank correlation mean | Realized rank correlation mean | Top5 overlap mean | Beta sign disagreement mean |
| --- | --- | --- | --- | --- |
| v1_development/10_120 | 0.163472 | 0.232583 | 0.235897 | 0.372470 |
| v1_development/10_40 | 0.461199 | 0.380548 | 0.451282 | 0.403509 |
| v1_development/40_120 | 0.181541 | 0.516848 | 0.244872 | 0.348853 |
| v1_validation/10_120 | -0.098353 | 0.328383 | 0.220635 | 0.436090 |
| v1_validation/10_40 | 0.498282 | 0.430563 | 0.496825 | 0.347953 |
| v1_validation/40_120 | 0.110080 | 0.549711 | 0.409524 | 0.282790 |
| v2_development/10_120 | 0.862406 | 0.256099 | 0.695761 | 0.246489 |
| v2_development/10_40 | 0.895071 | 0.423208 | 0.764589 | 0.234808 |
| v2_development/40_120 | 0.930444 | 0.529588 | 0.789526 | 0.122195 |
| v2_validation/10_120 | 0.905348 | 0.316366 | 0.820635 | 0.181287 |
| v2_validation/10_40 | 0.962657 | 0.473814 | 0.834921 | 0.197160 |
| v2_validation/40_120 | 0.908735 | 0.579123 | 0.807937 | 0.193818 |


Prediction and realized correlations are cross-sectional average-tie Spearman per signal, then arithmetic averages. Top5 overlap is intersection size/5 with ascending-code ties. Beta sign disagreement counts sign differences/19. These are not comparisons of new fusion policies.

### Regime proxies / 状态代理

| Phase | Trailing20 market return mean | Trailing20 market vol mean | Daily CS return std mean | Common direction mean | Covariance dimension | First PC share |
| --- | --- | --- | --- | --- | --- | --- |
| v1_development | -0.010760 | 0.012772 | 0.009038 | 0.809402 | 1.654623 | 0.773692 |
| v1_validation | 0.067565 | 0.018594 | 0.010014 | 0.838360 | 1.452497 | 0.826938 |
| v2_development | 0.010022 | 0.015060 | 0.009328 | 0.822776 | 1.578683 | 0.792862 |
| v2_validation | 0.012103 | 0.010179 | 0.009534 | 0.797090 | 2.594744 | 0.602419 |


Market is the equal-weight mean of 30 admitted industry daily returns; trailing20 compounding/volatility only use days up to the signal. Common direction=max(fraction positive,fraction negative). Covariance effective dimension=trace(C)^2/trace(C^2), first PC share=lambda_max/trace(C) on daily raw industry returns in the phase. This raw-return dimension is not centered-target rank degrees of freedom. No exploratory regime split was used for selection.

### Shared Development dates / 共同 Development 日期

| Horizon | V1 shared Dev IC | V2 shared Dev IC | Prediction correlation mean | Changed rank orders |
| --- | --- | --- | --- | --- |
| 10 | -0.016146 | 0.075192 | 0.634035 | 156 |
| 120 | 0.183309 | 0.088426 | 0.019814 | 156 |
| 40 | 0.158766 | 0.202858 | 0.733952 | 156 |


156 shared dates: 2023-08-02–2024-03-25. Same 30 identities, panel, raw targets, horizons and Dev role. Unified IC method; the native Bottom5 tie rule differs (no actual selected prediction ties affected parity). Each selected specification changed ranks on all156 dates. This rejects pure amplitude equivalence; it cannot isolate penalty from12m/24m windows or candidate-selection effects.

### Comparability matrix / 可比性矩阵

| Dimension | Native Validation V1 vs V2 | Shared Development diagnostic |
| --- | --- | --- |
| SAME_UNIVERSE | true,30 | true,30 |
| SAME_FACTUAL_PANEL | true | true |
| SAME_SIGNAL_DATE | false | true,156 dates |
| SAME_HORIZON | true | true,each10/40/120 |
| SAME_TARGET_DEFINITION | true | true |
| SAME_REALIZED_OUTCOME | false | true |
| SAME_EVALUATION_METHOD | RankIC true; native blocks/Bottom5 ties differ | unified RankIC true; native extremes differ |
| SAME_PHASE_ROLE | Validation label true, dates/ownership differ | Dev label true; informed selection remains |

### Frozen factor definitions / 冻结因子定义

| Factor | Definition | Lookback sessions | Scale | Economic hypothesis |
| --- | --- | --- | --- | --- |
| d5 | (close-MA5)/MA5 | 5 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | MA displacement/relative trend |
| d10 | (close-MA10)/MA10 | 10 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | MA displacement/relative trend |
| d20 | (close-MA20)/MA20 | 20 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | MA displacement/relative trend |
| d60 | (close-MA60)/MA60 | 60 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | MA displacement/relative trend |
| d120 | (close-MA120)/MA120 | 120 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | MA displacement/relative trend |
| p5 | clip((close-min5)/(max5-min5+1e-10),0,1) | 5 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | Range position/trend persistence |
| p10 | clip((close-min10)/(max10-min10+1e-10),0,1) | 10 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | Range position/trend persistence |
| p20 | clip((close-min20)/(max20-min20+1e-10),0,1) | 20 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | Range position/trend persistence |
| p60 | clip((close-min60)/(max60-min60+1e-10),0,1) | 60 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | Range position/trend persistence |
| p120 | clip((close-min120)/(max120-min120+1e-10),0,1) | 120 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | Range position/trend persistence |
| align | (3*(MA5>MA10)+2*(MA10>MA20)+(MA20>MA60))/6 | 60 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | Range position/trend persistence |
| v5 | std(pct_change(close),5,ddof=1) | 6 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | Volatility/state change |
| v20 | std(pct_change(close),20,ddof=1) | 21 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | Volatility/state change |
| vc | v5/(v20+1e-10) | 21 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | Volatility/state change |
| rev5 | -mean(pct_change(close),5) | 6 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | Short-term reversal |
| rev10 | -mean(pct_change(close),10) | 11 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | Short-term reversal |
| dd20 | close/rolling_max(close,20)-1 | 20 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | Drawdown/recovery |
| dd60 | close/rolling_max(close,60)-1 | 60 | DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE | Drawdown/recovery |
| rsi | 100-100/(1+mean(gain,14)/(mean(loss,14)+1e-10)) | 15 | 0_TO_100 | Gain/loss oscillator |


All use reconstructed industry close only, backward lookbacks and gap/warmup preservation. RSI is0..100; range/align are bounded; other fractional scales differ. All19 are technically applicable, but economic appropriateness is unvalidated. Signal missingness=0 in every phase and factor; no nearly-constant signal cross section in V2 Val (threshold std<1e-12). Other phases have7/21/32 factor-date occurrences in V1 Dev/V1 Val/V2 Dev, respectively, due to bounded-factor saturation; per-factor counts are in JSON. No factor is constant throughout a phase. Warmup nulls remain outside admitted signals. Complete per-phase dispersion, time distributions,19x19 correlations, per-horizon sign/magnitude/persistence/contribution distributions are in JSON.

### Per-factor audit / 逐因子审计

| Factor | V2 Val CS std median | V1 Dev/Val drift SD | V2 drift SD | V2 Val H10 factor IC | H40 factor IC | H120 factor IC | H120 mean abs beta | H120 beta positive fraction | H120 sign persistence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d5 | 0.009648 | 0.322737 | 0.001884 | -0.041549 | -0.017194 | 0.061578 | 0.000105 | 0.000000 | 1.000000 |
| d10 | 0.014922 | 0.469218 | -0.000098 | -0.072726 | -0.050133 | 0.077610 | 0.000166 | 0.000000 | 1.000000 |
| d20 | 0.020422 | 0.746954 | 0.010808 | -0.053280 | -0.052916 | 0.091400 | 0.000271 | 0.000000 | 1.000000 |
| d60 | 0.038239 | 1.693849 | 0.160784 | -0.070099 | -0.024472 | 0.122980 | 0.000359 | 0.000000 | 1.000000 |
| d120 | 0.055326 | 2.734502 | 0.412045 | -0.000766 | 0.146392 | 0.240546 | 0.000604 | 0.000000 | 1.000000 |
| p5 | 0.307155 | 0.274236 | 0.132371 | -0.036010 | -0.003132 | 0.064295 | 0.000031 | 0.595238 | 0.960000 |
| p10 | 0.271500 | 0.379841 | 0.151435 | -0.052259 | -0.017913 | 0.087378 | 0.000101 | 0.841270 | 0.992000 |
| p20 | 0.239114 | 0.483715 | 0.163907 | -0.024702 | -0.001713 | 0.128544 | 0.000163 | 0.904762 | 0.984000 |
| p60 | 0.224886 | 0.738721 | 0.378708 | -0.054666 | 0.017290 | 0.167911 | 0.000317 | 0.000000 | 1.000000 |
| p120 | 0.176217 | 1.377203 | 0.719389 | 0.031363 | 0.133291 | 0.204772 | 0.000726 | 0.000000 | 1.000000 |
| align | 0.265767 | 0.682709 | 0.260446 | -0.037712 | -0.006917 | 0.089884 | 0.000206 | 0.000000 | 1.000000 |
| v5 | 0.004659 | 0.475682 | -0.256913 | 0.066254 | 0.096019 | 0.052927 | 0.000379 | 1.000000 | 1.000000 |
| v20 | 0.003417 | 0.628819 | -0.459210 | 0.014570 | 0.086449 | 0.052648 | 0.000618 | 1.000000 | 1.000000 |
| vc | 0.248586 | -0.063629 | 0.093205 | 0.062422 | 0.034910 | 0.027544 | 0.000096 | 0.000000 | 1.000000 |
| rev5 | 0.003993 | -0.392708 | 0.006408 | 0.065907 | 0.050324 | -0.059449 | 0.000129 | 1.000000 | 1.000000 |
| rev10 | 0.002791 | -0.589894 | 0.008753 | 0.095305 | 0.060187 | -0.075121 | 0.000215 | 1.000000 | 1.000000 |
| dd20 | 0.021598 | 0.123197 | 0.281991 | -0.026187 | -0.023756 | 0.101054 | 0.000395 | 0.000000 | 1.000000 |
| dd60 | 0.027528 | 0.300241 | 0.630256 | -0.030360 | -0.051861 | 0.114224 | 0.000744 | 0.000000 | 1.000000 |
| rsi | 10.120186 | 0.590507 | 0.150852 | -0.011282 | 0.012769 | 0.103014 | 0.000088 | 0.865079 | 0.984000 |


Drift=(Val pooled mean-Dev pooled mean)/Dev pooled SD, across phase signals x30 industries, not the frozen fit's scaling. Factor IC uses each raw factor as a descriptive cross-sectional ranking against each already consumed target. It is **NOT_PREREGISTERED_PREDICTIVE_EVIDENCE**, not a factor admission/search result. Coefficients are standardized-X coefficients. Persistence compares consecutive signs; zeros are a separate sign. All hypotheses share the membership, period dependence and correlated-factor limitations.

### Industry deletion sensitivity / 行业删除敏感性

| Phase/H | q95 max abs daily deletion IC change | Mean daily minimum deletion IC | Mean daily maximum deletion IC | Non-overlap window count upper bound |
| --- | --- | --- | --- | --- |
| v1_development/10 | 0.123347 | -0.093126 | 0.063487 | 16 |
| v1_development/120 | 0.116812 | 0.107819 | 0.264952 | 2 |
| v1_development/40 | 0.121548 | 0.079014 | 0.239194 | 4 |
| v1_validation/10 | 0.120586 | -0.222042 | -0.070592 | 13 |
| v1_validation/120 | 0.118008 | -0.100195 | 0.072476 | 2 |
| v1_validation/40 | 0.109598 | -0.152870 | -0.003468 | 4 |
| v2_development/10 | 0.126140 | -0.042740 | 0.113675 | 41 |
| v2_development/120 | 0.123804 | -0.058945 | 0.103266 | 4 |
| v2_development/40 | 0.125981 | 0.034993 | 0.194272 | 11 |
| v2_validation/10 | 0.119804 | -0.040801 | 0.115341 | 13 |
| v2_validation/120 | 0.116383 | -0.251986 | -0.088385 | 2 |
| v2_validation/40 | 0.122553 | -0.086164 | 0.070080 | 4 |


**EXPLORATORY_LEAVE_ONE_OUT_DIAGNOSTIC**: delete each industry in turn, rerank the remaining29, hold the frozen fit/predictions fixed. The daily min/max envelope changes which deleted industry attains it; it is not a new universe. Its mean maximum upper-bounds every fixed-industry deletion's phase mean IC. Thus V2 H120 remains negative even under that favorable per-date upper envelope (-0.088385). Non-overlap counts only bound pairwise outcome intervals; they do not prove independence of training, industry or regime information.

### Failure attribution / 失败归因

| Dimension | Classification | Observed / interpretation |
| --- | --- | --- |
| Target correctness | E_CONTRADICTED_BY_AVAILABLE_EVIDENCE | Exact t+1..t+h compounding, per-date 30-industry training centering; all four native aggregate trees and V2 fit-trace hashes match. No confirmed target alignment, scale, maturity or evaluation defect in admitted scope. Tests do not establish source PIT accuracy. |
| PIT/membership | F_NOT_IDENTIFIABLE | Tier A=0, B=0; 6,515,140 Tier-C listed stock/session rows; historical assignment publication proof absent. Direction and magnitude of retrospective membership bias are not identifiable from the industry panel. |
| Data integrity | F_NOT_IDENTIFIABLE | Pinned panel; 0 post-seed missing admitted returns; factor reconstruction max error 7.25e-13. Full raw stock pipeline was not rerun. No confirmed byte/alignment/feature defect; independent data correctness and corporate-action PIT remain unestablished. |
| Feature suitability | C_SUPPORTED_DESCRIPTIVE_PATTERN | All19 factors have positive median signal dispersion; isolated saturated range/drawdown/align cross sections occur in V1/V2 Dev and V1 Val. Three V2 Validation pairs have abs pooled correlation >0.9. Redundancy is observed; blanket claim that all Level-1 factors are constant is contradicted. Economic sufficiency remains unproved. |
| Ridge conditioning | E_CONTRADICTED_BY_AVAILABLE_EVIDENCE | V2 Validation regularized Gram condition medians 1.9968, 2.0003, 1.9965; solve residual q95 <3e-16. Numerical instability does not explain the replayed H120 failure. Strong shrinkage is not a causal test of underfitting. |
| Regularization strength | C_SUPPORTED_DESCRIPTIVE_PATTERN | V1 alpha/n medians 0.0144/0.0165/0.0273; V2 alpha/n=10; slope df about1.29 versus V1 14.69..16.44. V2 heavily suppresses weak eigen-directions; this changes model shape, but window and selection effects confound attribution. |
| Window dependence | D_PLAUSIBLE_UNCONFIRMED_HYPOTHESIS | Selected V1 12m versus V2 24m; per-horizon mature rows differ; V2 coefficients move slowly. A long window may preserve stale direction; window effect is not separately identified. |
| Coefficient stability | C_SUPPORTED_DESCRIPTIVE_PATTERN | V2 Validation successive coefficient cosine medians >=0.99986; H120 d5..d120 mean coefficients negative on every date. Stable fitted direction can be predictively wrong; sign persistence is not economic robustness. |
| H10 behavior | C_SUPPORTED_DESCRIPTIVE_PATTERN | V1 Val IC=-0.1401, V2 Val=0.04065. V2 d10 factor-H10 mean IC=-0.07273; rev10=0.09531. H10-only interest is a seen-data hypothesis; simple short-horizon momentum continuation is not supported in V2 Val. |
| H40 behavior | C_SUPPORTED_DESCRIPTIVE_PATTERN | V2 Val IC=0.0000918; calendar blocks 0.2527,-0.04118,-0.12152,-0.06625. Average is near zero and varies by period; not a proved stable transition mechanism. |
| H120 behavior | C_SUPPORTED_DESCRIPTIVE_PATTERN | V2 Val IC=-0.16133, all4 calendar block means negative. Daily best one-industry deletion upper envelope averages -0.08838. Failure spans all predefined blocks and cannot be removed by any single fixed industry deletion. Not proof across regimes. |
| Long-horizon mean reversion claim | E_CONTRADICTED_BY_AVAILABLE_EVIDENCE | V2 Val d120-H120 mean factor RankIC=+0.24055; fitted standardized d120 coefficient negative throughout. Available long-horizon relation is continuation for this price proxy, opposite the fitted direction; universal H120 mean reversion is unsupported. |
| Fusion coherence | C_SUPPORTED_DESCRIPTIVE_PATTERN | V2 Val prediction pair correlations 0.9627,0.9053,0.9087 versus realized0.4738,0.3164,0.5791. Top5 overlaps81..83%. Horizons mostly share ranks, not diversify. H120 contributes -0.04033 to original weighted IC. No alternative fusion evaluated. |
| Regime dependence | C_SUPPORTED_DESCRIPTIVE_PATTERN | V1 d120 Dev/Val mean drift2.7345 Dev SD; V2 0.4120. Covariance effective dimension changes1.579 to2.595 in V2. Market/factor state changes are observed; causal regime attribution is not identified. |
| Cross-section limitations | C_SUPPORTED_DESCRIPTIVE_PATTERN | 30 industries, Top5=1/6; raw daily covariance participation ratios1.45..2.59; Validation IC lag1 correlations0.59..0.88. Strong common moves and overlapping labels restrict confidence. Covariance dimension is not the sample size of centered rank IC. |
| V1/V2 comparability | F_NOT_IDENTIFIABLE | Validation dates/outcomes differ; V1 equal-count blocks versus V2 equal-calendar.156 shared Dev dates available. Native Validation aggregates cannot identify a model winner; shared Dev changes combine penalty, window and selection. |
| Primary failure mechanism | C_SUPPORTED_DESCRIPTIVE_PATTERN | Out-of-period directional mismatch concentrated at V2 H120, highly coherent horizon ranks, strong shrinkage and limited independent observations. Descriptive failure pattern is supported; a unique causal source/model/window/penalty root cause is NOT_IDENTIFIABLE. |
| Overregularization causes H120 | D_PLAUSIBLE_UNCONFIRMED_HYPOTHESIS | Strong shrinkage is measured, but no fixed-date same-window alpha-only causal experiment was authorized. Plausible underfitting mechanism; cannot state causation or optimum penalty. |
| Historical numerical-access isolation | C_SUPPORTED_DESCRIPTIVE_PATTERN | Original V1/V2 executors materialize full numeric panel members before Development. One historical isolation gap; declared maturity proof is not an access-isolation certificate. No demonstrated tail-target use, numerical defect or human inspection; zero certified independent historical unseen sessions. |


### Immutable lineage / 不可变谱系

| Artifact | SHA256 |
| --- | --- |
| config/research/swl1-ridge-v1-candidate.json | `c5917b83d5c81627cfa88ae19d1691fd7356b7c91134be1472c1047e2a31ab6c` |
| config/research/swl1-ridge-v1-protocol.json | `3d148ba7adc4846cd3fa951a46dc224f34a5070a8dd5cfa50523bca4a0c5222e` |
| config/research/swl1-ridge-v2-candidate.json | `c94d511d925e47947b12d12a1b8c0380417da525282651a790ca55f84c81efad` |
| config/research/swl1-ridge-v2-protocol.json | `df832a94eba54d703110defe2e7f0169e9de93a316a7def795a38fe9e50e428a` |
| reports/research/swl1_ridge_v1/data_feasibility.json | `39aff56e15b730bc834cb7407a086546a75f7d4f292ee0cadc38294e1987fad3` |
| reports/research/swl1_ridge_v1/development.json | `a031bec412de2c86008eeb2b9272f8409fd17ce79b8ef511a893d497003dfeda` |
| reports/research/swl1_ridge_v1/factor_audit.json | `c3998b221e4b210271dee6e6e4b6ae118cc4a34717900820425c2d1ef8f9f041` |
| reports/research/swl1_ridge_v1/status.json | `9d2a6b9d418e88008a0125d4004fd9283735ce5fd1b854f7a9de607f73eb6569` |
| reports/research/swl1_ridge_v1/validation.json | `4f39211fb8fcdd3e350355414b753065940b8bdb42bb2ee57a432b89241c205c` |
| reports/research/swl1_ridge_v2/development.json | `8715911746935fcf27200a76d17f402cd95f61f3eaa36312f947c07081be13f2` |
| reports/research/swl1_ridge_v2/status.json | `5453501bbe21068042f9691f3cf900513e6d529a28dd8de3f73b624cc7b6eb85` |
| reports/research/swl1_ridge_v2/validation.json | `e1fea05ccef53c1767f3e8e6b845c9e52e23112543856bbe85095501706dbc97` |


The manifest also pins every preregistered implementation file, the original private panel hash, private consumed claim/result byte hashes and independent forensic source hashes. Private claims/results were hashed as opaque integrity evidence, not republished. Their historical lifecycle was never called. Data-file byte hashing and Fortran layout-tail skipping are distinguished from numeric outcome decoding:29 intervening future-column tails (232 bytes) were discarded without floating-point conversion, and the last column tail was not decoded. In this task the1 outcome row beyond declared consumption never entered an ndarray, target, IC or spread;121 future feature rows were likewise excluded. This task-local receipt does not certify historical isolation by the original executors.
