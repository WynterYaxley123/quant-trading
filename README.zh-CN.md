# quant-trading

[English](README.md) | [简体中文](README.zh-CN.md)

SWL1 数据与证据基础设施已完成合成验收；正式来源准入仍阻断，V1/V2 保持失败，
未来协议尚未创建，正式前瞻观察为 0。参见[数据可行性](docs/research/swl1-data-first-feasibility.zh-CN.md)
和[独立 Docker 演示与操作边界](docs/engineering/prospective-evidence-operations.md)。
全新公开 clone 使用固定开发镜像运行 `python -m examples.prospective_evidence_demo`，
不需要私有数据。新隔离不会追认旧数值访问合格。

当前项目研究**申万一级与二级行业预测**，二级策略家族正式命名为 **SWL2-Ridge-V1** 与
**SWL2-Ridge-V2**。两者角色均为 `INDUSTRY_FORECAST_RESEARCH`，ETF 产品化已
`RETIRED`。独立的 **SWL1-Ridge-V1** 已完成 20 个 Development specs 和一次 Validation，
结果为 `FAILED_VALIDATION`；Final OOS 从未打开，forward eligible=false，ETF 产品化 `NOT_STARTED`。
单独公开预注册的 **SWL1-Ridge-V2** 已完成冻结的 16 个规格及唯一一次 Validation，
同样为 `FAILED_VALIDATION`，永久关闭。Final OOS 从未打开，前瞻资格为 false。

## 当前状态

| 家族 | 行业层级 | 冻结宇宙 | 模型 | 研究状态 | Validation | Final OOS | 前瞻资格 | ETF 产品化 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SWL2-Ridge-V1 | 2 | 107 | Ridge | FROZEN_BASELINE | SEALED | SEALED | 既有冻结前瞻路径 | RETIRED |
| SWL2-Ridge-V2 | 2 | 124 | Ridge | PROVISIONAL_HISTORICAL_RESEARCH_CANDIDATE | 原始 FAIL | CONSUMED | 既有冻结前瞻路径 | RETIRED |
| SWL1-Ridge-V1 | 1 | 30（当前 taxonomy 31） | alpha 100 / 12个月 / 标准化19因子 | FAILED_VALIDATION | FAIL | NOT_OPENED | false | NOT_STARTED |
| SWL1-Ridge-V2 | 1 | 相同30 | penalty 10 × 训练行数 / 24个月 / 标准化19因子 | FAILED_VALIDATION | FAIL | PROSPECTIVE_ONLY / NOT_OPENED | false | NOT_STARTED |

[V2 正式预注册](docs/research/swl1-ridge-v2-protocol.md)在真实指标计算前单独合并。
16 个 Development 规格中 3 个准入，确定性选择 B-m24-l10；[一次 Validation](docs/research/swl1-ridge-v2-results.md)
综合 RankIC −0.030123、H120 −0.161329、加权正 IC 比例 41.87%、正时间块仅 1/4。
保持相同的重建一级行业等权目标，不重试、不修订，也不进入 OOS。

SWL1 失败归因：**COMPLETED**（[中文报告](docs/research/swl1-v1-v2-failure-forensics.zh-CN.md)）。
V1/V2 仍为 **FAILED_VALIDATION**。冻结诊断重放与原始指标一致，唯一因果根因尚不可识别。
下一代：**NOT_STARTED**；[设计审查](docs/research/swl1-next-generation-design-review.md)
建议 DATA_FIRST，没有生成新协议、候选或模型。

SWL1 是独立家族，不是 SWL2 V3。[协议](docs/research/swl1-ridge-v1-protocol.md)在任何真实
模型表现计算前提交并冻结，两个 purge 各 120 个真实交易 session。[一次 Validation](docs/research/swl1-ridge-v1-results.md)
综合 RankIC −0.076308、加权正 IC 比例 42.26%、加权原始收益 spread −1.5404%，仅 2/4 时间块为正。
V1 不重试、不调整 candidate，不打开 Final OOS。[通用目录](config/research/industry-forecast-families.json)
让 API/UI 如实展示历史失败记录，禁止该家族读取或发布前瞻 runtime。

[家族注册表](config/research/swl2-ridge-families.json)统一名字、历史身份、模型哈希和宇宙。
V1 的冻结准入宇宙实际是 **107** 个行业；V2 的冻结 warmup 元数据是 **124** 个行业。
两者保存各自真实完整预测。把 V1 扩到 124 会改变训练截面、标签中心化和排名，故不扩容。
本次工程交付没有创建任何真实前瞻预测或成熟评价；缺失指标为 null，UI 如实显示空状态。

V1 是冻结基线，Validation / Final OOS 继续 SEALED。V2 是
`PROVISIONAL_HISTORICAL_RESEARCH_CANDIDATE`：原 Validation 失败，受 Validation
启发的修订已消费一次原 Final OOS。历史方向性标签 `STRONG_POSITIVE`，独立统计置信度
`LIMITED`、成员资格置信度 `RECONSTRUCTED`、历史 ETF 执行验证 `NOT_ESTABLISHED`。
已消费 OOS 不会因改名或延长区间重新成为 unseen；历史分类及字节保持原样。

## 冻结科学合同

| 项目 | SWL2-Ridge-V1 | SWL2-Ridge-V2 |
| --- | --- | --- |
| 行业数量 | 107 | 124 |
| Ridge alpha / 窗口 | 0.01 / 6 个月 | 30.0 / 12 个月 |
| 输入 | 原始 X | S2A-RAW-m12-a30 原始 X |
| 因子 | H10 冻结 5 因子，H40/H120 冻结 19 因子 | 相同冻结因子集 |
| horizon | 10 / 40 / 120 真实交易 session | 10 / 40 / 120 真实交易 session |
| 融合 | 总体 z-score；0.25 / 0.50 / 0.25 | 总体 z-score；0.25 / 0.50 / 0.25 |

科学目标仍为同日截面超额行业收益：行业精确 H-session 累积收益减去该模型冻结宇宙均值。
滚动系数拟合只用成熟标签。SWL2 没有调参、重新 Validation、打开 sealed OOS 或重跑
市场数据回测。research budget 指实验数量及阶段门控；货币预算不属于当前行业研究。

## 前瞻发布与成熟评价

runner 从 main 实际合并历史解析 transition commit，然后单独冻结 runtime 的源码、
模型哈希和启用时间。首个合法预测日是同时严格晚于 merge 和 freeze 日期的正式交易日；
只接受该日上海时间 15:05 后实际观察到的 finalized 事实。漏过的日期不可回填。
preflight / dry-run 不写入、不冻结；本交付不启动 live scheduler。

每条不可变预测保存全部行业名称、代码、H10/H40/H120 raw prediction、总体 z-score、
各期限 rank、fused score/rank、cutoff、源码 commit、模型哈希与 provenance。
原子 generation、OS mutex、哈希链及 journal 恢复保证重试幂等；重复发布跳过模型 refit。
每个 horizon 等精确交易日到期且全路径事实 finalized 后才追加评价，提前只显示 PENDING。
不使用临时收盘、填补缺口、未来值或伪造历史 epoch。

描述性评价包括 Spearman RankIC、期限 Top5/Bottom5 平均收益及 spread、真实 Top5
重叠率、排名绝对误差、20 个成熟日期的 rolling mean 与最差 spread 区间。空指标 null；
重叠 horizons 不作显著性或统计胜负声明。融合 Top5 outcome 单列为研究诊断。

两家公平比较采用 `COMMON_FORWARD_WINDOW` 的共同真实日期和共同成熟期限。
额外 `COMMON_INDUSTRY_CROSS_SECTION_DIAGNOSTIC` 在共有行业及一致实际收益上
重算描述性指标，主指标仍分别使用各自冻结宇宙；历史 sealed/consumed OOS 不进入比较。

## 实际行业序列与图表

当前已有准入 Source-C 调整后成分股收益、带日期成员资格和冻结覆盖规则重建行业收益，
明确标为 `RECONSTRUCTED_SWL2_EQUAL_WEIGHT`。分类来源官方并不意味着价格序列是
官方行业指数行情。目前准入适配器没有已建立授权的官方 SWL2 index bars；重建序列
可复现并有 provenance，本地准入不授予上游数据再分发权。

Dashboard 默认展示 Industry Forecast：完整排名、Top5、信号历史、到期状态、预测与
实际排名及共同窗口比较。成熟行业路径起点 1.0，明确标为 `VISUAL_TREND_DIAGNOSTIC` /
`NORMALIZED_RESEARCH_INDEX` / `NON_TRADABLE_RESEARCH_DIAGNOSTIC`，配同日行业
宇宙等权基线。各信号结果独立，不把重叠预测拼成可交易 NAV。无成熟样本时如实为空。

## 历史 ETF 产品化退役

可靠可执行 ETF 覆盖不足以代表二级行业粒度，覆盖结果保留为
`HISTORICAL_PRODUCTIZATION_RESULT`。ETF 的存在、纯度、流动性与现金比例不再影响
行业预测能力评价。active path 没有映射、账户、targets、intents、fills、NAV、初始资金、
仓位上限、手数、佣金或滑点。旧写命令 fail closed；只允许显式隔离临时目录的合成回归。

历史 `ETF_QUANT_V1` / `ETF_QUANT_V2` 配置、mapping、release、Shadow、报告、ledger、
证书和结果保持原身份与哈希。旧 API / 页面是带退役标记的只读审计视图。
不启用券商、真实订单、杠杆或做空。本任务不迁移或改写 live QuantForge。

## 架构与目录

固定外部 PIT 事实 → 冻结 Ridge → 完整预测 ledger → 精确成熟行业结果 → 只读 API / UI。
核心代码在 `strategies/swl2_ridge/`，runner / API 分别在
`services/industry-forecast-runner/` 与 `services/industry-forecast-api/`。
注册表位于 `config/research/`，历史文档原字节归档在 `docs/archive/productization/`。

## 无数据快速开始

仅使用独立开发 Docker 镜像，不修改部署镜像、不在宿主 Python 安装量化依赖。

```sh
git clone https://github.com/WynterYaxley123/quant-trading.git
cd quant-trading
docker build -f .devcontainer/Dockerfile -t quant-trading-dev:local .
docker run --rm -v "${PWD}:/workspace" quant-trading-dev:local python -m examples.industry_forecast_demo
docker run --rm -v "${PWD}:/workspace" quant-trading-dev:local python -m pytest -q -m "not external_runtime"
```

容器内运行 `pnpm --dir dashboard install --frozen-lockfile` 后执行 test/typecheck/lint/build。
`node services/industry-forecast-api/server.mjs` 在没有 runtime 配置时显示真实空状态。
runner 必须使用 clean merged source 与显式外部只读事实。scheduler template 保持 disabled。

## 文档、贡献与后续研究

阅读[行业预测合同](docs/industry-forecast.md)、[文档索引](docs/index.md)、
[开发](docs/development.md)、[测试](docs/testing.md)、[数据/PIT](docs/data-and-pit.md)、
[部署](docs/deployment.md)、[中文运维](docs/operations.zh-CN.md)、
[复现](docs/reproducibility.md)、[研究状态](docs/research-status.md)、
[贡献指南](CONTRIBUTING.md)与[历史策略合同](docs/strategy.md)。
SWL1-Ridge-V1 已因 Validation 失败关闭，未挪用 SWL2 的已消费证据。不含结果的
[SWL1-Ridge-V2 草案](docs/research/swl1-ridge-v2-draft.md)尚未预注册、也未运行。源码 [MIT](LICENSE)，
[第三方声明](THIRD_PARTY_NOTICES.md)和[数据权限](docs/data/market_data_policy.md)独立适用。

## 宇宙与目标的独立口径

冻结 taxonomy artifact 的当前 SWCLASS2021 二级行业为 **134** 个，另保留
**63** 个旧版解析身份。V1/V2 模型宇宙保持 **107/124**，对应 **27/10** 个
当前 taxonomy-only 身份。API 动态校验冻结引用，分别展示分类数量、模型数量
和真实发布行数；未发布时行数为 0。历史 ETF mapping coverage 属于历史产品化结果。

科学目标为行业从信号日到准确第 h 个后续交易 session 的复合收益，减去该家族
完整冻结宇宙在同一 (t,h) 的收益均值。V1/V2 共同窗口只校验共有行业原始收益
兼容性；不同宇宙中心化后的 scientific target 可以不同。

历史 ETF 产品化退役原因是相对于二级行业研究宇宙，可靠可执行产品覆盖存在结构性
不足。历史 mapping、账户、Shadow、合同与证书完整保留。

SWL1 真实来源资格审查见[中文报告](docs/research/swl1-real-data-source-qualification.zh-CN.md)和[材料取得计划](docs/research/swl1-source-acquisition-plan.md)。已审计 12 类来源、核验 15 份公开材料；真实准入仍为 0，下一代研究暂缓。
