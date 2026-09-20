# SW Sector Rotation Baseline v1 — 数据准入检查与研究阻塞报告

状态：**SW SECTOR ROTATION LEVEL B BLOCKED - DATA NOT READY**。
日期：2026-09-20；研究分支：`experiment/sw-sector-level-b-research`。
起点：`b865231`，已包含前两轮规格草稿和 LEVEL A 验收改动。

这不是完整研究报告或策略结果。用户要求“正式数据不足则停止”，本次在数据准入阶段停止。
未运行行业模型、Baseline、参数实验或 Final OOS；不选择“完成”“候选已锁定”或“OOS污染”状态冒充进度。

## 1. 数据范围及行业/映射覆盖

本地 `data/` 仅有 Hikyuu 数据目录等，不含已初始化的申万二级研究数据。
直接只读 HDF5 表首尾日期得到：

| ETF | 本地首日 | 本地末日 | 行数 |
|---|---|---|---:|
| sh510300 | 2012-05-28 | 2026-09-18 | 3481 |
| sh510500 | 2013-03-15 | 2026-09-18 | 3285 |
| sh512400 | 2017-09-01 | 2026-09-18 | 2197 |
| sh512660 | 2016-08-08 | 2026-09-18 | 2458 |
| sh588000 | 2020-11-16 | 2026-09-18 | 1420 |
| sz159745 | 2021-06-18 | 2026-09-18 | 1277 |
| sz159915 | 2011-12-09 | 2026-09-18 | 3589 |
| sz159934 | 2013-12-16 | 2026-09-18 | 3105 |

这只是既有 ETF 的实际文件覆盖，不证明历史可成交性、权息完整或行业映射覆盖。
合格申万二级行业数 **0（尚未准入，不代表市场没有行业）**；合格行业数据起止 **null**。
classification_version、data_snapshot、validated primary ETF mapping version 均 **null**。
映射覆盖率 **未定义**：历史有效行业池分母尚未建立，不能写为 0% 或把 legacy 表算作已验证覆盖。

## 2. 来源调查与阻塞证据

检查的是当前 Docker 内 AKShare **1.18.88** 实际源码，未更新依赖。

| 来源/接口 | 实际发现 | 本次检查 |
|---|---|---|
| `stock_industry_clf_hist_sw` | 官方 StockClassifyUse_stock.xls；源码返回 symbol/start_date/industry_code/update_time | 正常 TLS 校验报 SSLError：unable to get local issuer certificate；系统 CA 重试同样失败 |
| `index_hist_sw` | 官方 trend endpoint，字段为代码/日期/OHLC/成交量/成交额；无历史分类版本/发布时间字段 | 801193 仅作接口数据样本探测，TLS 失败，未取得可准入样本，不计算收益 |
| `index_component_sw` | 最新权重、计入日期；不能单独还原完整历史成分与退出记录 | 读源码确认字段限制，没有把当前列表回填历史 |
| 官方分类网页、current endpoint | 分类下载页/当前指数目录 | 容器 TLS 失败；网页读取工具亦超时 |
| 官方无 www 主机 | 有限替代连接检查 | DNS 解析失败 |
| 乐咕当前行业页 | sw_index_second_info 的当前目录来源，无历史生效/退出/可得版本链 | 带普通浏览器 UA 的首次请求 HTTP 200，另一次普通请求 HTTP 403；停止重试，不绕过限制 |

官方链接：[申万分类下载页](https://www.swsresearch.com/institute_sw/allIndex/downloadCenter/industryType)、
[历史分类文件](https://www.swsresearch.com/swindex/pdf/SwClass2021/StockClassifyUse_stock.xls)。
接口字段可对照 [AKShare 指数文档](https://akshare.akfamily.xyz/data/index/index.html)；
线上文档版本比本机新，本次行为结论以本机源码和实际请求为准，不把文档示例数据当作本地已下载数据。

没有关闭 TLS 校验、没有绕过站点限制、没有安装/升级依赖或重建容器。
**不声称数据源永远不可用，也不声称历史分类文件缺少全部必要信息：本次尚未成功获取并验收它。**
当前目录可访问不等于历史 PIT 合格；下载时间/文件指纹也不等于每个历史时点已知。
即使连接修复，仍需验证分类版本生效/公布、指数历史是否回算、单位与修订、ETF primary 关系及可成交性。

## 3. 已批准的 Baseline 与分区

计划配置：[sw_sector_rotation_level_b_research.yaml](../config/sw_sector_rotation_level_b_research.yaml)；
批准补充：[strategy_spec_v1.md 第 20 节](strategy_spec_v1.md#20-level-b-research-authorization-and-data-gate)。

模型保留 19 raw price features、Ridge alpha=0.01、无 scaler、absolute target、
10/40/120、0.25/0.50/0.25、Top5、6 个月、30 个有效训练日、逐 observation 同权。
RSRS 不入模，Macro/Flow/Fundamental 不启用。
交易批准为下一 session open、每 10 session 差额再平衡、validated primary ETF 去重等权、
RiskState record-only、当日撤余单、期末不强平。
成本版本 research-cost-v1：0.00025/最低5 CNY/印花税0/滑点0.001，仅研究假设。

Development/Validation/Final OOS 起止均 **null**，约 60/20/20 仅记录为分配原则；
尚无合格联合覆盖，不能承诺每段都包含完整牛熊震荡。
dates_locked=false、OOS_LOCKED=false、候选名单为空。
不借现有 ETF 时间范围替代行业数据范围，也不为满足格式任填日期。

## 4. Baseline、实验与候选

Baseline Development/Validation：**NOT_RUN**。
全部参数实验：**NOT_STARTED**，未执行 scaler/target/weighting/alpha/window/fusion/TopN/cadence 搜索。
模型研究候选只在计划配置中留痕，未宣称任何方案优于 Baseline。
最终参数：**未选择**，原 Baseline 参数没有被优化替换；无 Candidate A/B。
Final OOS：**NOT_EVALUATED**，未查看策略指标/曲线，未用于反复调参。
既有 LEVEL A 使用过 ETF 行情不等于 LEVEL B OOS 已评价，但后续报告应披露此事实，不能声称无人见过原始市场历史。

## 5. 指标、成本与稳定性

Total Return、CAGR、Max Drawdown、Sharpe、Sortino、Alpha、Beta、胜率、盈亏比、
Profit Factor、Trade Count、Turnover、Commission、Slippage、平均持有时间、Exposure：
**全部 null / NOT_RUN**。不能复制 LEVEL A 的数值，也不能以 0 代替未运行。
策略/基准/超额净值、月度/年度收益、回撤曲线均未生成。
Development→Validation 稳定性、成本影响和是否过拟合：**无法判断**；数据检查失败不是参数实验失败。

基准候选：沪深300价格指数或中证500价格指数，理由是衡量宽基股票市场暴露；
不按收益选择，也不自动把 sh510300 的 ETF 价格等同于指数。
建议先明确沪深300价格指数作为市场 Beta 比较候选，再按交易范围/数据口径验证选择；
当前 selected=null，未计算 Alpha/Beta。指数/ETF、价格/全收益口径不可混用。

## 6. 后续恢复条件与 OOS 护栏

优先取得可信、允许使用的历史快照或修复官方来源的可信证书链；需有：
sector_code/name、classification_version、effective_from/to、available_at/source、
行业 OHLCVA/单位/价格定义/修订说明、历史 primary ETF 映射及其有效/可得日期、
ETF 交易/权息/限制数据和公共日历。若某来源不直接给这些字段，应提供等效可审计证据，不能伪填。
不要求用户提供金融账户、Cookie 或 Token；如需付费/登录/新依赖，须另获授权。

连接问题与数据证据是两个独立门槛，修复连接不自动解锁研究。
数据通过后才建立具体分区并 commit，完成 LEVEL B 专用执行/报告与隔离测试。
随后先跑 Baseline Development+Validation，再单变量逐阶段研究；所有失败/非最优实验都留痕。
评分阈值、交易数/年贡献/回撤恶化判据须事先明确，不看结果后移动拒绝门槛。
最多 Baseline+两候选冻结并 commit、核验 OOS_LOCKED 后一次性评价 OOS；失败不回调参数。

本次未创建 experiments 汇总或 strategy_backtest 输出，避免空产物看起来像已执行实验。
未写入 `reports/backtests/sw_sector_rotation/`。

## 7. 验收与 Git

归档前 Docker 离线 pytest：**305 passed / 2 skipped / 13 deselected / 2 warnings**。
其中 10 个 integration 默认排除，3 个联网用例预先排除，不删除或跳过失败测试。
两个原有 skip 为旧 Hikyuu block 检查及未初始化 RQAlpha bundle，不是数据门槛通过的证据。
本轮研究分支仅记录规格、计划配置与数据阻塞报告，不改策略算法或依赖，不 merge/push。
配置为**未接线的声明式计划**，不是声称已实现程序化 OOS 隔离。
