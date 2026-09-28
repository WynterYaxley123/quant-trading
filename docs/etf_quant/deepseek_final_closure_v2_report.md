# ETF-Quant V1 — DeepSeek 最终收口 v2 报告

```
PRIMARY：                  DEEPSEEK_FINAL_CLOSURE_BLOCKED
ETF_QUANT_READY_FOR_SHADOW：FALSE
SHADOW_START_READINESS：    BLOCKED
SHADOW_EPOCH_CREATED：      FALSE
PRODUCTION_CANDIDATE：      未创建（按 §21/§42，条件未满足时不得创建）
```

本轮唯一主线的终点是 **CP6**。冻结 Top5 中四个行业经多个官方一手来源穷举与可复现的成分集
包含检验，确认不存在任何可准入的 A 股 ETF，因此 `DISTINCT_EXECUTABLE_ETF_BLOCKER` 成立
（§36 第 9 条）。CP7–CP9 按冻结规则**不得继续**：不足 5 只不同 ETF 时不得计算权重、不得
创建 Candidate、不得声称 Shadow readiness。

---

## 1. L2 统一结果

冻结契约：**`ETF_QUANT_INDUSTRY_LEVEL_V1 = "SHENWAN_L2"`（4 位代码）**。模型未改成 L3。

- 新增 `strategies/etf_quant/domain/industry_level.py`：契约常量 + 封存 taxonomy 的严格加载器。
- 新增 `strategies/etf_quant/config/shenwan_industry_taxonomy_v1.json`：
  - 来源为**申万宏源研究官网**的官方《申万行业分类（2021版）》代码表
    `SwClassCode_2021.xls`（511 行 = 31 一级 / 134 二级 / 346 三级），
    记录 URL、检索时间与 SHA-256。
  - 每个二级行业记录官方二级代码、官方二级名称、显式三级子集。
  - 另含 59 个不在 2021 版标准表内、但存在于官方股票归属表的历史三级代码，
    以 `vintage=PRE_2021_OR_UNMAPPED_LEGACY` 单独保留且**不带名称**，用于保持
    `width=4` 解析与冻结工程层完全一致；无名称的代码不能作为生产映射键。
  - 覆盖率：生产快照中 396/396 个存量三级代码全部可解析。
- `mapping/registry.py` 现在**只接受 4 位 L2 键**：`industry_code` 必须是 4 位且存在于
  taxonomy，`industry_name` 必须与官方名称一致，registry 顶层必须声明
  `industry_level = SHENWAN_L2` 与 `taxonomy_identity`。旧的六位 L3 键被直接拒绝。
- `runtime/industry.py::build_industry_series` 不再使用字符串截断：所有存量三级代码
  通过显式关系表解析到二级，未知代码 `INDUSTRY_TAXONOMY_BLOCKER` fail-closed。
- 独立复核：用指数成分股集合包含关系把 335 个申万三级指数归并得到 126 个二级名称，
  与本轮官方表**逐条一致**；医药生物 6 个、银行 4 个、非银金融 3 个共 13 个生产相关
  二级行业与官方 801xxx 指数名称 **13/13 完全一致**。

## 2. 时间语义

新增 `docs/etf_quant/production_time_semantics_v1.md`（中文，冻结）。要点：

- `2026-09-24 = HISTORICAL_ENGINEERING_REFERENCE_DATE`，**不是**真实 Shadow 起点。
- 区分 `signal_date / economic_execution_at / effective_at / observed_at / available_at /
  processed_at / evidence_observed_at`，并强制
  `source_retrieved_at ≤ evidence_observed_at ≤ verified_at ≤ available_at`
  与 `effective_at ≥ date(available_at)`。
- 本轮映射证据真实观测于 2026-09-28，**未倒填**为 2026-09-24 已知。生产路径在
  2026-09-24 截面上因此**零条映射可用**，这正是防倒填属性生效的证据。
- T+1 语义保持：`T finalized close → signal`，`T+1 actual open → economic execution`，
  `DELAYED_T1_OPEN_ACCOUNTING`；禁止用 T+1 close / T+2 open / previous close 替代。

## 3. Top5 行业（从 engineering ranking artifact 读取，未硬编码）

来源：`.../codex-final-completion/reports/etf_quant_engineering_ridge_20260928T123624Z_828fad6e.json`
（SHA-256 `6fbcb13518c2664ec236879473a87a833f9b6e0e263f106919628e2052bc484c`）。

| rank | L2 代码 | 官方二级名称 | fused score |
|---|---|---|---|
| 1 | 3706 | 医疗服务 | 2.3767168362915063 |
| 2 | 3703 | 生物制品 | 1.83545058741489 |
| 3 | 4901 | 证券Ⅱ | 1.2282859716780057 |
| 4 | 4803 | 股份制银行Ⅱ | 1.1068604652745437 |
| 5 | 3701 | 化学制药 | 1.0768533956276514 |

> 说明：`4803` 是**股份制银行Ⅱ**（不是城商行Ⅱ，城商行Ⅱ是 4804）。该结论由官方
> 2014→2021 对照表与官方股票归属表的成员构成双重确认。

## 4. verified ETF candidates

准入规则：ETF 官方基金文件须证明其标的指数；该指数的**官方成分股集合必须是申万二级
行业成员集合的子集**（越界即不构成该行业的映射）。名称匹配从不作为准入依据。

| 行业 | 结论 | 依据 |
|---|---|---|
| 4901 证券Ⅱ | **VERIFIED**：512880.SH、159848.SZ（同一标的指数 中证全指证券公司指数 399975） | 官方基金文件 + 成分集包含检验：49 只成分股**全部**落在 4901 成员集合内，越界 0 只 |
| 3706 医疗服务 | **REJECTED** | 全部候选指数越界：399989 越界 34、H30178 越界 97、931940 越界 123、931592 越界 21 |
| 3703 生物制品 | **REJECTED** | 930726 越界 15、931992 越界 12、930743 越界 24 |
| 3701 化学制药 | **REJECTED** | 931152 中证创新药产业指数越界 27；无任何 ETF 的官方文件声明跟踪“化学制药” |
| 4803 股份制银行Ⅱ | **REJECTED** | 399986 中证银行指数 42 只成分股仅 9 只落在 4803 内，越界 33（国有大行/城商行/农商行） |

穷举性证据（官方目录全量枚举，非关键词猜测）：中证指数有限公司 2997 条指数、国证指数
1479 条、上交所基金参考数据 1240 只、深交所基金列表 1060 只中，**不存在**任何以
医疗服务／生物制品／化学制药／股份制银行（或更窄的银行子行业）为标的的 A 股指数或 ETF。
中证指数公司官网按名称检索“医疗服务”“生物制品”命中数为 **0**。

Registry 同时以 `REJECTED` 行显式保留上述否定结论与理由；空表绝不代表全覆盖。

## 5. CNEquity ETF 行情

- 全部行情来自 **pinned CNEquity**（commit `1650e384a3fd1f67a70144a489acc91432f1df27`，
  version 0.11.0）；未升级、未改 pinned upstream、未关闭 TLS、未用第三方行情 fallback。
- 走**正式生命周期**：`fetch → staging → batch → settle → compact → curated`，
  再由 pinned sidecar 以只读方式发布不可变快照（未直接写 curated）。
- 结果：湖内 ETF 92 个标的、29,162 行、2025-04-10 → 2026-09-24，`amount` 空值 **0** 行。
- 候选池 89 只全部摄取成功（0 缺失）。发布快照
  `7b34b95ad77de8af484201e47e9a14fd69f697c9123d87f44a7b0c6adda61fd7`。

## 6. 20 日流动性

冻结规则：**最近 20 个交易日的 20 日平均成交额**；任何一天 `amount` 缺失即
`LIQUIDITY_ADMISSION_FAIL`；上市不足 20 个交易日即 `LIQUIDITY_HISTORY_INSUFFICIENT`。
不得 drop-null 均值、不得补零、不得用 volume 替代、不得缩短窗口。

- 窗口：**2026-08-28 → 2026-09-24**（20 个交易日），execution session = 2026-09-28。
- 89 只候选：**PASS 89 / FAIL 0 / INSUFFICIENT 0**。
- 该结论由生产准入函数 `assess_liquidity` 本身在不可变快照上运行得出，非独立复算。

## 7. 最终 5 只 ETF

**未达成。** 冻结 Top5 可触达的**不同** ETF 仪器数为 **2**（`512880.SH`、`159848.SZ`），
且两者跟踪同一条标的指数。按 §16：

```
DISTINCT_EXECUTABLE_ETF_BLOCKER
shortfall = NO_ADMISSIBLE_CANDIDATE
distinct_etf_count = 2 < 5
```

未用重复 ETF 伪造 5 个资产；四个无 ETF 行业的 rank 未被静默降级替换成更低排名行业。

## 8. 权重与 35% cap

**未计算。** §17 要求“只有拿到 5 只 ETF 后才算权重”，因此本轮不产出任何目标权重。
权重引擎本身由单元测试独立认证：softmax → 35% 单 ETF 上限 → 仅向未达上限者再分配，
验证 `all finite`、`all > 0`、`sum ≈ 1`（1e-12）、`max ≤ 0.35`、无杠杆、无做空；
不足 5 只时返回 `INSUFFICIENT_EXECUTABLE_ASSETS` 且 100% 未分配。

## 9. Production Candidate

**未创建。** §21 的九项前置条件中，`verified L2 mapping`、`distinct Top5`、`portfolio
feasibility` 未满足，因此按 §42 不创建。本轮只产出：

- `reports/etf_quant/deepseek_final_closure_v2_manifest.json`（纯 metadata，
  显式声明 `production_candidate_created = false`）。

## 10. Shadow readiness

```
ETF_QUANT_READY_FOR_SHADOW = FALSE
SHADOW_START_READINESS     = BLOCKED
SHADOW_EPOCH_CREATED       = FALSE
```

未创建正式 signal / order intent / fill / holding / NAV / PnL / performance。
`EARLIEST_LEGAL_SHADOW_START_RULE` 已在时间语义文档中定义，但本轮不启动。
`T+1 actual open` 语义与 `DELAYED_T1_OPEN_ACCOUNTING` 保持不变。

## 11. 测试

| 套件 | 结果 |
|---|---|
| ETF Python | **266 passed, 1 skipped, 0 failed**（基线 238 passed, 1 skipped） |
| API（node --test） | **57 passed, 0 failed** |
| Frontend（vitest） | **95 passed, 3 skipped, 0 failed** |
| typecheck (tsc) | PASS |
| lint (eslint) | PASS |
| **NEW REGRESSIONS** | **0** |

本轮新增 28 个针对冻结契约的测试，覆盖：L2 契约常量与宽度、taxonomy 封存与证据、
“未知代码绝不截断”、L3 键被拒、名称漂移被拒、宽基指数（510300/沪深300）被拒、
证据观测时间与生效时间不可倒填、`verified` 标志一致性、20 日窗口恰为 20 个交易日、
缺失 amount 不得取均值、零值与亚元成交额视为 feed artefact、上市不足 20 日不得缩短窗口、
冲突回退到下一个已准入候选、重复 ETF 不得伪造 Top5、五位 key 必须是 L2、
软最大 + 35% 上限与再分配、未满 5 只时不得计算权重。

未使用 skip / xfail / 伪造 fixture / 修改 expected 来制造绿色。已知的全仓 52 个 non-pass
（8 failed / 44 errors，与本轮隔离 worktree 缺失仓外历史研究产物有关）不属本轮范围，
本轮未触碰它们，也未改变其状态。

## 12. Git

- base：`integration/etf-quant-v1-final` @ `7e1931627aa3d5061ec78e43c14dec63ed682ee2`
  （worktree 创建后 `git rev-parse HEAD` 已精确校验）。
- 工作分支：`agent/deepseek-etf-quant-final-closure-v2`
- worktree：`D:\quant-worktrees\deepseek-etf-quant-final-closure-v2`
- 未 push、未 rebase 旧 agent 分支、未 force push。main 与 integration 分支未修改，
  其它 worktree 全部只读。

## 13. 剩余 blocker

```
DISTINCT_EXECUTABLE_ETF_BLOCKER   (TRUE HARD BLOCKER §36.9)
```
唯一可继续的路径需要用户决策，二选一：

1. **放宽映射规则**，允许用“代理敞口”（例如 3706 用 H30178 系、3703 用 930726 系）
   代替“指数即行业”。这会修改冻结的准入定义，属 §36 第 1 条，必须由用户明确授权。
2. **保留规则并接受结果**：ETF-Quant V1 在 5 只不同 ETF 的约束下无法对当前冻结 Top5
   形成可执行组合；系统保持 `ETF_QUANT_READY_FOR_SHADOW = FALSE`。

无论选择哪条，本轮交付的 L2 生产契约、官方 taxonomy、时间语义、verified mapping
准入机制、20 日流动性准入、Top5 冲突回退与权重上限引擎都是可用且经过测试的工程条件。
