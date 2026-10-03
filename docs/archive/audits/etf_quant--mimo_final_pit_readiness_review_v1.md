# ETF-Quant V1 — 最终生产 PIT 证据审查报告（MiMo）

分支：`agent/mimo-final-pit-readiness-certification-v1`
基线（DeepSeek 最终证据提交）：`78562bd575d78db875296e34871a52ec977f1483`
审查日期：2026-09-29/30
审查性质：**审查 + 认证 + 必要小型修正**。未重新抓取全市场数据，未重新做研究，未重新开发 runtime。

---

## 摘要

| 判定项 | 结论 |
|--------|------|
| PRODUCTION_PIT_EVIDENCE_REGISTRY | **PASS** |
| SWS_MEMBERSHIP_EVIDENCE | **PASS_WITH_KNOWN_LIMITATION** |
| PRODUCTION_STRICT_EVIDENCE | **PASS** |
| PIT_ADAPTER_COMPATIBILITY | **PASS** |
| NO_BACKFILL_AUDIT | **PASS** |
| FAIL_CLOSED_CASH | **PASS** |
| TECHNICAL_SHADOW_READINESS | **PASS** |
| ETF_QUANT_PROXY_READY_FOR_SHADOW | **TRUE** |
| SHADOW_EPOCH_CREATED | **FALSE**（本轮绝不创建） |

---

## 一、SWS membership：`component_stocks` 语义审查

**结论：PRODUCTION_MEMBERSHIP_EVIDENCE_SUFFICIENT，附 SOURCE_FORM_LIMITATION。**

**语义依据（不是"官方所以 PASS"）：**

1. **一一语义成立**。申万官方二级行业指数（801xxx）的成分集合就是该二级行业的
   成员集合：行业指数按行业分类取成分，指数成分表与分类表是同一事实的两种发布形式。
   本轮的机械性质支持这一点：134 个官方二级行业指数成分集合重新推导出 **5220 只证券、
   0 冲突**（每只证券至多落在一个官方二级行业指数成分内）——如果指数成分只是行业成员的
   真子集或跨行业采样，这种互斥分割不会成立。
2. **独立交叉验证一致**。官方分类与研究 sidecar 共有 1104 只证券，**1104/1104 完全一致、
   0 不匹配**（`research_cross_check_only`）。sidecar 全程 `CROSS_CHECK_ONLY`，
   未被提升为生产证据（已由 `test_production_pit_no_backfill_audit.py` 独立断言）。
3. **缺口方向是安全的**。不在任何官方二级行业指数成分内的证券（`920982`、`689009`）
   一律 `UNCLASSIFIED_FOR_V1`，导致相关 benchmark fail closed（12 个），**不用 sidecar 补洞**。
   语义缺口若存在，只能造成"少分类→Cash"，不可能造成"错分类→错执行"。
4. **来源与可复现性**。申万官方 `swsresearch.com`（在适配器官方主机白名单内）；
   134 个原始响应按 `VERBATIM_PROVIDER_BYTES` 原样保存，**134/134 与检索账本 SHA-256 一致**
   （本轮独立复核）；原始字节中无 `source_url`/`swindexcode` 等注入字段（token 扫描 0 命中）。
   逐券生效日全部来自官方 `beginningdate`（5220/5220，521 个不同取值）。
5. **目录口径已修正且正确**。124→134 的修复已落入最终 artifact：未过滤 `index_name/`
   目录（1014 条）名称精确匹配，134 个二级行业全部唯一解析；补回的 10 个（含 801011 林业Ⅱ、
   801961 油气开采Ⅱ、801983 医疗美容等）在 `raw_members/` 中全部存在且非空（其中
   801217/801768/801786 官方声明成分数为 0，账本 `complete=true`，如实保留为空行业）。
   **最终 snapshot 含 5220 只证券、131 个有成员的 L2 码、0 冲突，非旧 124 缓存。**

**必须保留的 known limitation：**

```
SOURCE_FORM_LIMITATION = OFFICIAL_L2_INDEX_CONSTITUENTS_NOT_MASTER_CLASSIFICATION_TABLE
```

证据形态是"官方二级行业指数成分集合"，不是官方全股票分类主表
（`StockClassifyUse_stock.xls` 为 OLE2 XLS，适配器无法消费）。这是 provenance 层面的
形态限制，由上述互斥分割 + 交叉一致 + fail-closed 方向共同约束，**不构成技术不安全**。

**Live refetch 抽查说明**：本轮抽查申万成员接口时站点返回 HTTP 508（暂时不可用），
记 `LIVE_REFETCH_NOT_AVAILABLE`；按规则不因此否定证据，改以本地 hash chain 复核
（134/134 通过）+ DeepSeek 采集期实测重取 SHA-256 一致的记录。

---

## 二、Strict：为什么 Production Strict mappings = 0，4901 到底是什么

**结论：PRODUCTION_STRICT_EVIDENCE = PASS。"Strict=0" 是生产证据层的类型命名口径，
不是 4901 被降级为 Proxy。4901 = STRICT（成分集包含已由生产证据机械证明 + 运行时
verified registry 双通道确认）。**

**根因（真实原因，非猜测）：**

1. DeepSeek 生产证据 registry 中所有 B40 mapping 记录的 `mapping_type` 由
   `decide_b40_mapping`（`strategies/etf_quant/evidence/schema.py`）**硬编码为
   `PROXY_EXPOSURE`**。该层的职责是"exposure 派生的 B40 候选"，它只描述
   benchmark→L2 暴露，不承载 ETF 身份文件证据，因此从不产生 `STRICT_MAPPING` 类型记录。
   这是任务选项 **D（故意设计）+ A（builder 不生成 strict 类型）** 的组合，不是 B/C。
2. 运行时的 STRICT 通道是**另一个独立 registry**：`verified_mappings_v1.json`
   （`VERIFIED_MAPPING_REGISTRY_V1`），其中 4901 已有 **2 条 VERIFIED**
   （512880.SH、159848.SZ，均跟踪 399975，官方基金文件 + 成分集包含检验，
   文件 SHA-256 与证据根逐一核对通过）。`select_pit_mappings` 对每个行业先查该
   registry 的 strict 行，**有 strict 行时 proxy 路径根本不进入候选池**
   （`mapping/pit.py`：`if not strict_rows:` 才读 book）；
   `select_mappings_partial` 中 strict 候选一旦存在即独占 `eligible_pool`。
3. **因此系统不会把 4901 降成 Proxy。** 本轮真实 package 冒烟测试（模拟未来
   cutoff 2026-11-02，真实 book + 真实 verified registry + 合成行情微结构）实测：
   **4901 → `STRICT_MAPPING`**（159848.SZ，target exposure 100.0%，largest=True）；
   同轮 4803→PROXY（159887.SZ/H30022/41.48%）、3701→PROXY（562050.SH/932217/58.14%）、
   3706 与 3703→Cash（`TARGET_EXPOSURE_BELOW_THRESHOLD`，正常 B40 拒绝而非 ERROR）。

**4901 的 Strict 条件逐项核对（生产证据侧）：**

| 条件 | 399975→4901 | 931412→4901 | 931402→4901 | 950105→4901 |
|------|-------------|-------------|-------------|-------------|
| 成分全部有官方分类 | 49/49 | 30/30 | 46/46 | 33/33 |
| 成分全部属目标 L2（越界 0） | ✅ | ✅ | ✅ | ✅ |
| `unmapped_weight = 0` | 0.0 | 0.0 | 0.0 | 0.0 |
| 权重集完整（重算判据） | COMPLETE | COMPLETE | COMPLETE | COMPLETE |
| 暴露 / 最大性 | 100.00% / True | 100.00% / True | 99.97% / True | 99.99% / True |
| PIT 可用时刻 | 2026-09-29T23:05:26+09:00 | 同左 | 同左 | 同左 |

注意暴露 99.97–100.04 的浮动是官方权重求和舍入，**严格性由成分集包含证明，不由
"恰好 100%" 证明**——这正是"100% exposure 不自动等于 Strict"的边界：本轮派生
逐券核对成员关系，一个越界证券即拒绝（有测试固化），而不是看汇总数。

**Small fix（本轮实施，最小、机械、低风险）：**

- 新增 `strategies/etf_quant/evidence/strict.py`：成分集包含的机械证明
  （`prove_constituent_containment`）与 strict 映射证据派生
  （`derive_strict_mapping_evidence`，产出 schema 自身的 `B40MappingEvidence`，
  `mapping_type="STRICT_MAPPING"`，条件不满足即 `REJECTED` 带首因）。
- 新增 `scripts/etf_quant/build_production_strict_pit_evidence_summary.py` 与产物
  `reports/etf_quant/production_strict_pit_evidence_summary_v1.json`（仅 mapping
  metadata、package IDs、hashes、availability times，无成分行）。
- 新增 `tests/etf_quant/test_production_strict_pit_evidence.py`（22 用例）：
  全包含→STRICT PASS；一个越界证券→Strict reject；缺分类→reject；
  future evidence→reject；未映射权重>0→reject；权重集不完整→reject；
  空成分集→reject；可用时刻取输入最大值；wall-clock 双向护栏（早于真实抓取拒绝、
  晚于墙上时钟拒绝）；真实包复核（399975/931412 包含通过、000300 必须拒绝、
  summary 与包重算一致）。
- **未改变 Strict 定义、未改 verified registry 语义、未改 daily_cycle/映射域**；
  运行时 STRICT 通道原样。4901 的 Strict 身份证据（基金文件）仍来自 verified registry，
  生产证据提供的是独立重证的成分集包含，两者一致。

**Strict 与 Proxy 的时间语义（PIT）**：verified registry 的 4901 条目
`available_at=2026-09-28T23:30:00+08:00`、`effective_from=2026-09-28`，
生产证据 `production_available_at=2026-09-29T23:05:26+09:00`。二者均 forward-only：
**在 2026-09-24 全部不可见**（实测 `prefix(2026-09-24) == {}`，strict 行 `active()` 同样为假），
没有因"数学上是严格子集"而倒填。

---

## 三、Coverage：22.5% / 20.1% 是什么

**结论：NORMAL FAIL-CLOSED COVERAGE LIMITATION，不是 TECHNICAL SAFETY BLOCKER。**

用户批准的 B40_WITH_CASH 政策已定义缺证据行为：

| 缺口 | 系统行为 | 实测 |
|------|----------|------|
| benchmark 缺失 | reject → 该槽 Cash | ✅ |
| 权重不完整（count_mismatch） | reject（186 个）→ 不准入 | ✅ |
| 分类缺失 | reject（12 个 benchmark fail closed） | ✅ |
| 分类冲突 | reject | ✅ |
| 未来证据 | reject（`available_at - 1s` 边界实测） | ✅ |
| 无合格映射 | → Cash | ✅ |

Cash 是状态字段，不是证券、不产生 order、不重新分配、原权重保留（35% cap 内），
Cash 合约与 T+1 已由 Codex dry-run 认证。**B40_WITH_CASH 从未规定最低 coverage 阈值，
本轮不擅自发明 `coverage > X%` 才可 Shadow 的隐含门槛。**

必须如实报告的 product availability limitation：

- 当前覆盖：498 个被引用 benchmark 中 112 个有完整官方权重（22.5%）、
  100 个成功派生暴露（20.1%）；瓶颈在权重抓取（186 个 count_mismatch），
  增量补抓可改善，无需方法学变更。
- 未来信号中该缺口会表现为**较高的 Cash 比例**——这是可投资范围限制，不是运行时 bug。
- `H30463` 保持 `UNRESOLVED_FAIL_CLOSED`，本轮未重研。

---

## 四、PIT：2026-09-24 为什么必须为空

1. **时间链三定律**（schema 层强制）：`publication <= observed <= available`；
   `effective_date <= available.date()`；`production_available_at = max(所有输入)`。
   `effective_date` 从未冒充 `available_at`（独立审计断言 + 测试）。
2. **双向护栏**（构建脚本 `assert_observed_after_every_retrieval`）：
   `--observed-at` 早于任何真实抓取 → `REFUSING TO BACKDATE`；
   晚于墙上时钟+2min → `REFUSING A FUTURE OBSERVATION`。本轮新增测试运行并验证了
   两个方向均拒绝、窗口内接受（ERROR-2 的21小时超前缺陷的修复仍然在位）。
3. **实测边界**：
   - `prefix(2026-09-24T18:00+08:00) == {}`；模拟 cutoff 同日五槽全 Cash、`selected == []`。
   - 最早可用时刻 `2026-09-29T23:05:26+09:00`：
     `prefix(该时刻 - 1s) == {}`，`prefix(该时刻)` 全量非空——**available_at-1s 必须拒绝**。
   - verified registry 的 strict 行同样在 2026-09-24 不可见。
4. `source_publication_at = null` 保留：所有官方来源均无发布时间字段，
   适配器侧以本系统首次观察时刻为诚实下界，**未伪造 publication time**。

---

## 五、真实 package smoke test

模拟 `SIMULATED_FUTURE_DECISION_CUTOFF = 2026-11-02`（>= registry 冻结时刻），
真实 book（8133 记录）+ 真实 verified registry + 合成行情微结构（适配性测试不用实时行情）：

| 槽位 | mapping_type | instrument | benchmark | 目标暴露 | 最大 | evidence id | available_at | 原因 | Cash 保留 |
|------|--------------|------------|-----------|----------|------|-------------|--------------|------|-----------|
| 3706 医疗服务 | CASH_UNEXECUTABLE_SIGNAL | — | — | — | — | — | — | `TARGET_EXPOSURE_BELOW_THRESHOLD`（37.16%<40%） | 原权重全额保留 |
| 3703 生物制品 | CASH_UNEXECUTABLE_SIGNAL | — | — | — | — | — | — | `TARGET_EXPOSURE_BELOW_THRESHOLD`（33.06%<40%） | 原权重全额保留 |
| 4901 证券Ⅱ | **STRICT_MAPPING** | 159848.SZ | 399975 | 100.0% | True | d68b7eca… | 2026-09-28T23:30+08:00 | B40_ADMITTED | 0 |
| 4803 股份制银行Ⅱ | PROXY_EXPOSURE | 159887.SZ | H30022 | 41.48% | True | 18df79d4… | 2026-09-29T23:05:26+09:00 | B40_ADMITTED | 0 |
| 3701 化学制药 | PROXY_EXPOSURE | 562050.SH | 932217 | 58.14% | True | da743bed… | 2026-09-29T23:05:26+09:00 | B40_ADMITTED | 0 |

> 该结果是 **PRODUCTION_EVIDENCE_SMOKE_TEST**，不是正式未来信号。
> 决定准入的一切（权重向量、申万二级归属、可用时刻、pinned 源哈希）为真实生产证据；
> 行情微结构为合成（适配性测试不依赖实时行情快照）。真实未来 T 的上市与 20 日流动性
> 必须届时用真实数据重新核对。4901 的 strict 候选有两个（512880.SH / 159848.SZ），
> 当日按流动性择一；2026-09-24 参考组合里的 512880.SH 不是未来承诺。

---

## 六、Candidate / Readiness

- `candidate_status = READY_FOR_FUTURE_SHADOW`
- `policy_approved = TRUE`，`execution_policy = B40_WITH_CASH`
- `technical_shadow_readiness = PASS`，`ready_for_shadow = TRUE`
- `shadow_epoch_created = FALSE`，`formal_business_records_created = 0`
- `production_pit_evidence_ready = TRUE`
- `production_pit_evidence_available_from = 2026-09-29T23:05:26+09:00`（registry 冻结时刻）
- **`production_ready_from = READY_FOR_NEXT_ELIGIBLE_FUTURE_SIGNAL_CYCLE`**
  —— 证据全部 forward-only，2026-09-24 不可用；真实 Shadow 起点只能是未来合法信号日，
  具体交易日不猜测。
- manifest hash 与 readiness JSON 互锁一致（candidate manifest SHA-256 =
  `e743bedb846a286c83870202c4514c80504c74409779b24f2968740914c2eb89`，readiness 中 pin 一致）。
- integrity status：source_integrity 各文件哈希逐一复核通过（pit.py / shadow.py /
  liquidity.py / 各 policy 与 manifest），`strict_mapping_registry_sha256` 与
  `verified_mappings_v1.json` 实际哈希一致。
- **READY 不是启动**：未创建 Shadow epoch、未生成 formal signal/intent/order/fill/
  holding/NAV/PnL；启动 Shadow 需用户另行授权。

---

## 七、Tests

| 套件 | 结果 |
|------|------|
| `tests/etf_quant` + 顶层 ETF 两文件（DeepSeek 基线 512 passed / 1 skipped） | **达标**（此前实测 502 + 10 = 512 passed / 1 skipped） |
| 新增 `test_production_strict_pit_evidence.py` | 22 passed |
| 更新后的 `test_proxy_final_candidate_manifest.py` | 2 passed |
| 受影响全套件复跑（含新增与更新） | 见最终 Git 报告 |
| 未跑全仓 Python（含封存研究与仓外历史 artifact） | 有意不跑，不以读取封存数据求"绿色" |

新增测试无删减、无放宽；manifest 测试的更新是状态推进的配套断言（SHA-256 互锁与
安全断言 `shadow_epoch_created=false`、security_assertions 全 false 均保留）。

---

## 八、Git

见最终 Git 报告（branch / base SHA / final SHA / merge-base / commits /
git status clean / push=FALSE）。本轮提交仅含：小型代码补充（strict.py + summary
builder）、测试、metadata、readiness manifest、docs、hash 引用。未提交任何官方原始
大文件、成分大表、行情行、runtime DB、PDF/XLS。

---

## 九、强制声明

MAIN 未修改；旧 integration（`integration/etf-quant-v1-proxy-runtime-final`、
`integration/etf-quant-v1-proxy-final`、`integration/etf-quant-v1-final`）未修改；
旧 DeepSeek / Codex / Kimi worktree 未修改；F1 未修改；Validation performance 未读取；
Final OOS 未读取；19 因子未修改；Ridge 未修改；H10/H40/H120 未修改；Fusion 未修改；
Source-C 未修改；industry ranking 未修改；Strict 规则未降低；B40 未修改；
40% 未降低；target-largest 未降低；Cash policy 未修改；daily_cycle 业务语义未修改；
rebalance 业务语义未修改；T+1 业务语义未修改；35% cap 未修改；20 日流动性未修改；
purity 未参与 alpha；research sidecar 未冒充 production evidence；
missing evidence fail closed；missing classification fail closed；
incomplete benchmark fail closed；future evidence rejected；
`effective_date` 未冒充 `available_at`；没有历史证据倒填；Strict > Proxy > Cash；
Cash 未伪装成 ETF；Cash 未重新分配；Cash 未产生 order；未创建 Shadow epoch；
未创建 formal signal/order/fill/holding/NAV/PnL；未 push；未提交大型 raw 数据；
未暴露 secret。`SOURCE_LICENSING_UNRESOLVED` 保持（未做法律结论）。
