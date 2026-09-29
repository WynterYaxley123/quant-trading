# PRODUCTION PIT EVIDENCE REGISTRY V1

ETF-Quant V1 · 生产级 point-in-time 证据登记册 · 中文正文

分支：`agent/deepseek-production-pit-evidence-v1`
基线：`42eb601bfc80991847e301f14387cdff77323b96`
本轮性质：**证据工程**。未修改任何策略、因子、模型、执行政策或 runtime 业务语义。

---

## 1. 一句话结论

现有 Codex PIT Evidence Adapter（`strategies/etf_quant/mapping/pit.py`）**未做任何修改**，
已经可以读取、校验并准入本轮构建的正式生产证据包；本轮证据全部是
**FORWARD_ONLY**，在历史决策日 `2026-09-24` 上可见证据数为 **0**。

---

## 2. 四个时间字段的确切含义

本轮严格区分四个时间，绝不合并成一个 `date`：

| 字段 | 含义 | 由谁决定 |
|------|------|----------|
| `effective_date` / `constituent_effective_date` / `weight_effective_date` | **数据描述的日期**：这份权重向量 / 分类关系所说的那个时点 | 官方数据本身 |
| `source_publication_at` | **官方发布时间**：发布方自己声明的公开时刻 | 只有发布方声明时才填；否则 `null` |
| `evidence_observed_at` | **本系统实际观察到该字节流的时刻** | 本系统真实抓取时钟 |
| `evidence_available_at` | **本系统正式可用的最早时刻**，恒 `>= evidence_observed_at` | 本系统 |

派生证据再多一个：

| 字段 | 含义 |
|------|------|
| `production_available_at` | `max(benchmark_evidence_available_at, classification_evidence_available_at, derived_at)`，**取最大，绝不取最早** |

### 本轮的现实约束（必须如实记录）

**本轮所有官方来源都不提供发布时间字段。** 中证 API 只暴露 `updateDate` / `tradeDate` /
`publishDate`（指数发布日）/ `basicDate`（基日）；深交所只暴露 `metadata.subname`（统计日）；
上交所的 `queryDate` 实测为空字符串；申万 API 只暴露每行的 `beginningdate`（成分生效时刻）
与指数基日。**没有任何一个是"这份文件何时公开"的声明。**

因此本轮一律：

```
source_publication_at = null            (构建层记录为 null)
adapter book 中 = evidence_observed_at  (适配器要求一条有序时间链，用本系统首次观察作为诚实下界)
```

这不是猜测，是**故意把下界设在最保守处**：不声称 9 月 1 日起系统就能用。

---

## 3. 一个真实 package 的例子

`packages/exposure/<benchmark>_l2_exposure_v1.json`（实际构建产物结构）：

```json
{
  "schema_version": "1.0.0",
  "identity": "BENCHMARK_L2_EXPOSURE_PIT_PACKAGE_V1",
  "exposure": {
    "benchmark_code": "930743",
    "benchmark_effective_date": "2026-08-25",
    "benchmark_evidence_available_at": "2026-09-29T23:05:26+09:00",
    "classification_snapshot_id": "SWS_L2_CURRENT_SNAPSHOT_20260929",
    "classification_evidence_available_at": "2026-09-29T23:05:26+09:00",
    "derived_at": "2026-09-29T23:05:26+09:00",
    "production_available_at": "2026-09-29T23:05:26+09:00",
    "availability_semantics": "FORWARD_ONLY",
    "unmapped_weight": 0.0,
    "weight_sum": 100.0,
    "input_package_hashes": ["...", "..."],
    "derivation_code_hash": "..."
  },
  "package_hash": "..."
}
```

读法：

* **数据描述**权重向量自身的生效日（锚定在该 benchmark 成分中**最晚**的一个官方
  `beginningdate`，并封顶在有效窗口起点）；
* **本系统在** `2026-09-29T23:05:26+09:00` **才第一次真正拿到并校验**这些字节；
* 因此 `production_available_at` 等于该时刻；
* 在 `2026-09-24` 做决策时，这份证据**不存在**，adapter 必须看不到它 —— 见第 8 节。

---

## 4. 三类基础证据 + 两类派生证据

### A. ETF → TRACKING BENCHMARK（`ETF_TRACKING_RELATION_EVIDENCE_V1`）

| 项 | 值 |
|----|-----|
| 官方来源 | 上交所 `query.sse.com.cn/commonSoaQuery.do?sqlId=FUND_LIST`（916 行）<br>深交所 `www.szse.cn/api/report/ShowReport/data?CATALOGID=1945`（748 行） |
| 关系数 | **1653**（上交所 908 + 深交所 745），覆盖 **498** 个 benchmark |
| 关键字段 | `fundCode`/`secNameFull`/`INDEX_CODE`/`INDEX_NAME`/`listingDate`（上交所）<br>`sys_key`/`kzjcurl`/`nhzs`（深交所，HTML 需剥离） |
| `listing_date` | 上交所 `listingDate` 形如 `"20050223"`，916/916 有值；深交所目录**不提供**上市日期 |
| `listing_status` | **两个交易所都不提供状态字段**。已对原始字节做 token 扫描（`status`/`状态`/`停牌`/`终止`/`delist` 等）全部 0 命中。本轮 `listing_status` 只能记为 `LISTED` 并注明其含义是"出现在交易所自己的在市基金目录中" |
| 公开时间 | **无**。`source_publication_at = null` |
| 来源类别 | **VERBATIM_PROVIDER_BYTES**（80 个交易所目录分页，可重取复现） |

### B. BENCHMARK → CONSTITUENTS + WEIGHTS（`BENCHMARK_CONSTITUENT_WEIGHT_EVIDENCE_V1`）

| 项 | 值 |
|----|-----|
| 官方端点 | `POST https://www.csindex.com.cn/csindex-home/indexInfo/index-sample-information`，body `{searchInput:<6位证券代码>, pageNum, pageSize, sortField, sortOrder}` |
| 语义 | 证券 → 该证券所在的每个中证指数，以及它在该指数中的**官方权重** `weightPct` |
| 完整权重向量 | **112** 个 benchmark（ETF 覆盖范围内，占 498 的 **22.5%**） |
| 完整性判定 | `constituent_count == declared_constituent_count` **且** `weight_sum ∈ [99.0, 100.5]`。两个条件都由算术重新计算，不由构建器断言 |
| 拒收 | 186 个 benchmark 因计数不符被拒（成分未全部覆盖），**没有任何一个是因"和不在带内"被拒**，即权重本身从未被重新归一化 |
| 权重来源类型 | `OFFICIAL_WEIGHT`（白名单第一档） |
| 归一化 | **从未发生**。独立审计曾逐证券逐值重建向量，83/83 与原始完全一致，`记录和/原始和` 唯一取值 = 1.0 |

> **重要事实**：中证官方 JSON **不存在**"全量成分 + 逐股权重"的单一接口（已穷举官网 200+ 接口路径）。
> 全量权重文件只有 XLS（`oss-ch.csindex.com.cn/.../closeweight/*.xls`），**按本轮约束不可作为 pinned JSON 来源**。
> 本轮走通官方 JSON 的反向查询路径：对足够多的证券逐个查询后，把返回行重新聚合回 benchmark 的完整权重向量，
> 并用"权重和落在 99.0–100.5"这一独立算术事实交叉证明重建是完整的。
>
> **来源类别**：单个 benchmark 的权重向量是 **DOCUMENTED_EXTRACTION**（本系统聚合文档），
> 每个包都在 manifest 的 `derived_from` 中列出它所用的官方原始响应文件与 SHA-256，
> 因此可以逐个重取核对。它**不是** provider 直接提供的字节，这一点被显式标注，不再混同。

### C. SECURITY → SHENWAN L2（`SHENWAN_L2_CLASSIFICATION_EVIDENCE_V1`）

| 项 | 值 |
|----|-----|
| 官方来源 | 申万宏源研究官方 JSON API<br>目录：`.../index_name/`（**1,014** 个指数名，**未过滤**）<br>成员：`.../index_publish/details/component_stocks/?swindexcode=<code>&page_size=1000`（**134** 个文件） |
| 覆盖证券 | **5220** 只，覆盖 **134** 个二级行业（封印分类法命名的二级行业**全部 134 个**） |
| **分类冲突** | **0**（同一证券同时出现在两个官方二级行业指数中的情况为零） |
| 未分类 | **0**（`unmapped_catalog_indices = 0`） |
| 生效语义 | `validity_semantics = FORWARD_ONLY_UNTIL_SUPERSEDED` |
| `classification_effective_from` | 官方每行自带的 `beginningdate`（纳入生效日） |
| 生效日实测 | **5220/5220 全部来自官方**（`defaulted 0`），共 **521** 个不同官方取值 |
| 来源类别 | **VERBATIM_PROVIDER_BYTES** —— 134 个响应按原样保存，已实测重新抓取得到**完全相同**的 SHA-256 |

> **⚠️ 一个必须记录的方法学修正（本轮自行发现并纠正）**
>
> 早期版本用 `indextype=二级行业` 查询获取行业目录，该查询只返回 **124** 个条目。
> 我据此一度得出"10 个封印二级行业官方不发布对应指数"的结论。
> **该结论是错的** —— `indextype` 只是发布方自己的标签，并不穷尽。
>
> 改用**未过滤**的 `index_name/` 目录（1,014 条）按官方名称精确匹配后：
> **134 个封印二级行业全部可解析，且每个恰好唯一匹配**。
> 缺失的 10 个是 `801011 林业Ⅱ / 801019 农业综合Ⅱ / 801117 其他家电Ⅱ / 801207 旅游零售Ⅱ /
> 801216 体育Ⅱ / 801217 本地生活服务Ⅱ / 801768 社交Ⅱ / 801786 其他银行Ⅱ / 801961 油气开采Ⅱ /
> 801983 医疗美容`。
>
> 补齐后：分类证券 5200 → **5220**，派生暴露 61 → **100**，fail closed 51 → **12**，
> 3706 医疗服务的最佳候选暴露 28.04% → **37.16%**，且由"非最大"变为"最大"。

> **诚实标注**：证券→行业归属来自"官方二级行业指数成分表"（index membership），
> **不是**来自官方全股票分类表（`StockClassifyUse_stock.xls`，OLE2 XLS，适配器无法消费）。
> 差别写入 registry 的 `known_limitations`。

行业指数代码到封印分类码的映射**只通过官方名称精确相等**建立：
`801012 农产品加工 → 1105`。名称不匹配或匹配到多个分类码的一律丢弃，绝不猜测，绝不用数字前缀推导。

### D. BENCHMARK → L2 EXPOSURE（`BENCHMARK_L2_EXPOSURE_PIT_PACKAGE_V1`）

只有 B 与 C 双双生产准入后才派生：**100** 个 benchmark 成功派生（占 498 的 **20.1%**），
**12** 个因分类仍有缺口而 fail closed。

### E. B40 MAPPING（`B40_MAPPING_EVIDENCE_V1`）

B40 规则**未被修改**：`target_l2_exposure >= 40.0` **且** `target_is_largest == True`。

---

## 5. 覆盖率的显式报告（不修饰）

| 指标 | 数值 | 占被 ETF 引用的 498 个 benchmark |
|------|------|----------------------------------|
| 被 ETF 引用的 benchmark | 498 | 100% |
| 有完整官方权重向量 | **112** | **22.5%** |
| 成功派生 L2 暴露 | **100** | **20.1%** |
| 因分类不完整 fail closed | 12 | 2.4% |
| 因成分计数不符被拒 | 186 | 37.3% |

`fail_closed_to_cash: 0` 只是当前 5 个 Top5 行业的计数，**不代表全局**。
registry 与 build report 都显式记录 `scope = 498`，避免被误读成全量覆盖。

**当前瓶颈已从分类转移到权重**：186 个 benchmark 的成分向量不完整（`count_mismatch`），
这是继续增量抓取即可改善的部分，不需要方法学变更。

---

## 6. 来源可复现性（独立审计后的修正）

独立对抗审计指出：早期版本的 320 个 pinned 文件中，240 个是本地合成文档却挂着官方 URL，
其哈希"自洽但不可复现"。已修正：

| 项 | 值 |
|----|-----|
| pinned 来源总数 | **427** |
| `VERBATIM_PROVIDER_BYTES`（可重取复现） | **81** |
| `DOCUMENTED_EXTRACTION`（本系统聚合文档） | **346** |
| 携带上游 lineage 的聚合文档 | **346 / 346**（100%） |
| 申万原始成员响应 | **134** 个，实测重新抓取 SHA-256 **完全一致**，原始字节中**无注入字段** |
| 申万行业目录（未过滤） | **1** 个，`raw_catalog/sws_index_name_all.json` |
| 检索账本 | `reports/sws_raw_retrieval_ledger.jsonl`，**134** 条，含 URL / HTTP 状态 / 时间 / SHA-256 / 计数一致性 |

`raw_source_manifest_v1.json` 中每个来源都带 `kind` 与 `derived_from`，
并在 `reproducibility_note` 中写明两类来源的可验证方式不同。

---

## 7. 生产分类覆盖缺口（如实报告）

**分类缺口已从 6 只证券缩小到 0。** 前一轮报告的"6 只无官方归属证券"中，
5 只是**我的检索缺陷造成的假缺口**，补齐 10 个被 `indextype` 过滤掉的二级行业后已经解决：

| 证券 | 研究 sidecar 归类 | 实际官方归属 | 状态 |
|------|------------------|--------------|------|
| 600938 | 7501 油气开采Ⅱ | 801961 油气开采Ⅱ | ✅ 已归类 |
| 300896 | 7703 医疗美容 | 801983 医疗美容 | ✅ 已归类 |
| 601888 | 4507 旅游零售Ⅱ | 801207 旅游零售Ⅱ | ✅ 已归类 |
| 920982 | 7703 医疗美容 | （不在本次官方快照内） | ⚠️ 仍无官方归属 |
| 688363 | 7703 医疗美容 | 801983 医疗美容 | ✅ 已归类 |
| 689009 | 2804 摩托车及其他 | 不在任何官方行业指数成分内 | ⚠️ 仍无官方归属 |

**剩余 12 个 benchmark 仍 fail closed**，责任证券**只有 2 只**：

| 证券 | 名称 | 阻塞 benchmark 数 | 官方 L2 归属 | 官方 L1 归属 |
|------|------|-------------------|--------------|--------------|
| `689009` | 九号公司 | 6（000069 / 000905 / 000906 / 000982 / 931265 / H30015） | **无** | **无** |
| `920982` | 锦波生物 | 7（000991 / 399989 / 931140 / 931265 / 931484 / H30178 / H30217） | **无** | **无** |

**这两只是真实存在的上市公司**，但**不在**申万官方分类快照里（134 个 L2 响应与 31 个 L1 响应中都不出现）。
已用独立来源交叉核对（`CROSS_CHECK_ONLY`，非生产证据）：

| 证券 | CSI CICS 归类 | 研究 sidecar 归类 |
|------|--------------|------------------|
| `689009` | 可选消费 / 乘用车及零部件 | 2804 摩托车及其他 |
| `920982` | 医药卫生 / 医疗 | 7703 医疗美容 |

即：**三方来源都在给它们归类，只有申万官方行业指数不收它们**。这是数据源覆盖差异，
不是检索缺陷 —— 已用 `test_only_two_securities_lack_an_official_industry_and_they_are_genuinely_absent`
锁死：若将来官方补收，该测试会立即失败并提示重跑构建。

**不补洞**：fail closed 到 Cash 是正确行为。

### 与独立采集的一致性核对

另一个独立子智能体对官方 API 做了 **155 次**逐行业扫描（31 一级 + 124 二级），报告：
L1 覆盖 5,220 只、L2 覆盖 5,200 只，并列出**恰好 20 只**"有 L1 无 L2"的证券。
把本轮补收的 10 个行业加回去后核对：

| 核对项 | 结果 |
|--------|------|
| 本轮 L2 并集证券数 | **5,220** |
| 独立 L1 扫描并集证券数 | **5,220** —— **完全相等** |
| 独立报告"有 L1 无 L2"的 20 只 | **20/20 全部由这 10 个行业补回**，无遗漏、无多余 |
| 同一证券落入多个 L2 | **0** |
| 每个行业 `count == len(results)` | **134/134 通过** |

这证明补收是**恰好正确**的，不是"多抓一点看起来更好"。

---

## 8. 无历史倒填（No-Backfill）

三重保证：

1. **时间链**：`source_publication_at <= evidence_observed_at <= evidence_available_at` 在每一层强制校验。
   把 `available_at` 设到 `observed_at` 之前 → `EVIDENCE_TIME_BLOCKER / AVAILABLE_BEFORE_OBSERVED`。
2. **描述日不得晚于可用日**：`effective_date > available_at.date()` → `EFFECTIVE_DATE_AFTER_AVAILABILITY`。
3. **适配器前缀**：`PITEvidenceBook.prefix(decision_at)` 只返回 `available_at <= decision_at` 的记录。
   本轮 book 中最早 `available_at = 2026-09-29T23:05:26+09:00`，因此
   `prefix(2026-09-24T18:00:00+08:00) == {}`，且在 `available_at - 1s` 上同样为空。

### 构建器两侧的硬护栏

独立审计指出"整份 registry 只靠一个时间常量兜住"，因此本轮加了两个**拒绝构建**的护栏：

| 护栏 | 行为 |
|------|------|
| `--observed-at` 早于任何真实抓取时刻 | **拒绝构建**：`REFUSING TO BACKDATE` |
| `--observed-at` 晚于真实墙上时钟 | **拒绝构建**：`REFUSING A FUTURE OBSERVATION`（上一版真实发生过这个缺陷） |
| `--valid-from` 早于观察日 | **拒绝构建**：`REFUSING TO BACKDATE THE VALIDITY WINDOW` |

`last_real_retrieval` 由采集账本与原始缓存推导，**不由人手输入**。

独立审计模块 `tests/etf_quant/test_production_pit_no_backfill_audit.py`
**刻意不 import 证据层**，只用标准库从原始 JSON 重新推导全部事实。

---

## 9. 现有适配器兼容性

**适配器源码零修改。** 真实 package 直接喂给：

```python
from strategies.etf_quant.mapping.pit import load_pit_evidence, select_pit_mappings
book = load_pit_evidence(book_path, source_root=source_root)
result = select_pit_mappings(registry, rankings, provider, book, signal_at=...)
```

`tests/etf_quant/test_production_pit_adapter.py` **12/12 通过**，覆盖：

| 测试 | 结论 |
|------|------|
| 真实 book 通过未修改的 loader | PASS（**8133** 条记录） |
| 每条记录都是 `COMPLETE_WEIGHT_SET` 且 `unmapped_weight == 0` | PASS |
| `2026-09-24` 前缀为空 | PASS —— **关键 no-backfill 测试** |
| 模拟未来 cutoff 跑 STRICT > PROXY > CASH | PASS |
| 同一 book 在 `2026-09-24` 全槽位 Cash | PASS |
| 篡改 pinned 源 → `PIT_OFFICIAL_SOURCE_HASH_BLOCKER` | PASS |
| 缺 `available_at` → `PIT_EVIDENCE_SCHEMA_BLOCKER` | PASS |
| 把可用时刻倒填到观察之前 → `PIT_EVIDENCE_TIME_BLOCKER` | PASS |
| 伪造官方域名 → `PIT_OFFICIAL_SOURCE_IDENTITY_BLOCKER` | PASS |
| STRICT 路径仍然拒绝 PIT book | PASS |

> **测试诚实性声明**：这些测试中，ETF 行情/上市/交易状态是**合成**的（兼容性测试不应依赖实时行情快照）；
> 但决定准入的一切 —— 权重向量、申万二级归属、可用时刻、pinned 源哈希 —— 都是**真实生产证据**。
> 这一区分写进了测试模块的 docstring，不模糊。

适配器的两条既有约束值得记录（均未修改适配器，只在构建侧遵守）：

1. 两个 pinned 来源**必须都是 JSON**；PDF/XLS/HTML 无法被消费。
2. pinned 文件名**不得含路径分隔符**。构建器据此在写入时把审计路径扁平化
   （`weights/000300_x.json` → `weights__000300_x.json`），审计身份保留在 `relative_path`。

---

## 10. 未来证据更新（append-only）

* 每个 package 的哈希覆盖除 `package_hash` 自身之外的全部字段。
* 同一相对路径重复写入不同字节 → `EVIDENCE_SOURCE_IMMUTABILITY_BLOCKER`
  （本轮真实触发过一次，阻止了权重文档与适配器记录之间的生效日分歧被发布）。
* 新快照 = **新 package**，绝不原地修改旧 package。
* 重跑：`python scripts/etf_quant/build_production_pit_evidence.py --observed-at <ISO8601>`。
  相同输入 + 相同时刻 ⇒ 字节级可复现；不同时刻 ⇒ 新的 forward-only 生效点。

建议刷新频率（本轮不建 scheduler）：

| 来源 | 更新频率 | 建议 |
|------|---------|------|
| 中证成分权重（反向查询） | 每日 | 每日增量抓取新增证券 |
| 申万二级行业成分 | 不定期（调整公告） | 每月 + 调整公告后 |
| 交易所 ETF 目录 | 每日 | 每日 |
| 上市日期 | 变动极少 | 每周 |

---

## 11. 不改动清单（强制声明）

未修改：19 因子 / Ridge / H10·H40·H120 / Fusion / Source-C / 行业 ranking / Top5 /
Strict mapping 规则 / B40 阈值 / target-largest / Cash policy / 35% cap / 20 日流动性 /
T+1 合约 / `daily_cycle` 业务语义 / rebalance 合约 / Shadow runtime 语义。

`SHADOW_EPOCH_CREATED = FALSE`。未创建任何 formal signal / intent / order / fill / holding /
NAV / PnL。`main`、旧 integration、旧 DeepSeek、旧 Codex worktree 全部只读未动。未 push。
未读取 Validation performance / Final OOS。Git 中无 `.env`、无 secret、无原始行情行、无大型官方原始文件。
