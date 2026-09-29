# DeepSeek → Codex 最终交接：PRODUCTION PIT EVIDENCE V1

本轮性质：**证据工程**。本轮**未修改**任何策略、因子、模型、执行政策或 runtime 业务语义。
Codex 下一步只做 **REVIEW + FINAL READINESS CERTIFICATION**，
不需要重新抓全市场、重新做分类研究或重新做 Proxy 研究。

---

## 1. Git

| 项 | 值 |
|----|-----|
| branch | `agent/deepseek-production-pit-evidence-v1` |
| base SHA | `42eb601bfc80991847e301f14387cdff77323b96` |
| final SHA | `45241b12e27dce33c6fd8b3d4b4f2b6c2e030324` |
| commit range | `42eb601..45241b1`（4 个提交） |
| worktree | `D:\quant-worktrees\deepseek-production-pit-evidence-v1` |
| merge-base | `42eb601bfc80991847e301f14387cdff77323b96` |
| working tree | clean（`git status --short` 为空） |
| push | **未执行** |
| registry path | `reports/etf_quant/production_pit_evidence_registry_v1.json` |
| registry sha256 | `81cf6d44831736c81966d3f5275bb0fd0c7d56c4652320821e4fc34143f172dc` |

`main` / 旧 integration / 旧 DeepSeek / 旧 Codex worktree **全部只读未改动**。
未执行 reset / clean / stash / rebase / force checkout / push。

### 提交内容（仅允许的类别）

```
strategies/etf_quant/evidence/schema.py          证据 schema 与时间语义
strategies/etf_quant/evidence/sources.py         pinned 原始字节的不可变存储
strategies/etf_quant/evidence/builder.py         不可变 package 构建器
strategies/etf_quant/evidence/__init__.py
scripts/etf_quant/build_production_pit_evidence.py
scripts/etf_quant/build_production_pit_top5_status.py
scripts/etf_quant/build_production_pit_manifest.py
tests/etf_quant/test_production_pit_evidence.py          49 单元测试
tests/etf_quant/test_production_pit_adapter.py           12 真实 package 适配器测试
tests/etf_quant/test_production_pit_no_backfill_audit.py 21 独立 no-backfill 审计
reports/etf_quant/production_pit_evidence_registry_v1.json        （小 metadata）
reports/etf_quant/production_pit_current_top5_status_v1.json      （小 metadata）
reports/etf_quant/deepseek_production_pit_evidence_manifest_v1.json（小 metadata）
docs/etf_quant/production_pit_evidence_registry_v1.md
docs/etf_quant/deepseek_production_pit_evidence_handoff_v1.md
```

**未提交**：任何官方原始字节、任何成分大表、任何股票分类大表、任何 PDF/XLS、
任何 runtime DB、任何原始行情行。全部留在 repo 外的 runtime 路径。

---

## 2. 关键路径与哈希

| 项 | 路径 / 值 |
|----|----------|
| runtime 根 | `D:\QuantForge\runtime\etf-quant-v1\production-pit-evidence-v1\` |
| pinned 官方原始源（repo 外） | `...\adapter-sources\` |
| 原始采集（repo 外） | `...\raw\`（`raw\sws\raw_members\` **134** 个逐券成员响应、`raw\sws\raw_catalog\` 未过滤行业目录、`raw\sws\catalog\` 过滤目录） |
| immutable packages | `...\packages\{weights,exposure,classification}\` |
| 适配器证据簿 | `...\adapter-tests\production_evidence_book_v1.json` |
| 报告 | `...\reports\` |
| registry（repo 内副本） | `reports/etf_quant/production_pit_evidence_registry_v1.json` |

registry 元数据（见 `production_pit_evidence_registry_v1.json`）：

```json
{
  "registry_id": "PRODUCTION_PIT_EVIDENCE_REGISTRY_V1::2026-09-29",
  "schema_version": "1.0.0",
  "created_at": "2026-09-29T23:05:26+09:00",
  "production_available_from": "2026-09-29T23:05:26+09:00",
  "availability_semantics": "FORWARD_ONLY",
  "classification_snapshot_id": "SWS_L2_CURRENT_SNAPSHOT_20260929",
  "cneqity_pin": "1650e384a3fd1f67a70144a489acc91432f1df27"
}
```

本轮关键计数（**覆盖率显式记录，不修饰**）：

| 指标 | 数值 | 占比（对 498 个被 ETF 引用的 benchmark） |
|------|------|------------------------------------------|
| 被 ETF 引用的 benchmark | 498 | 100% |
| 有完整官方权重向量 | 112 | 22.5% |
| 成功派生 L2 暴露 | 100 | 20.1% |
| 因分类不完整 fail closed | 12 | 2.4% |
| 因成分计数不符被拒 | 186 | 37.3% |
| 分类覆盖证券 | 5220 | —（**134 个二级行业全部覆盖**，0 冲突） |
| 适配器证据簿记录 | 8133 | — |
| pinned 来源 | 427（81 verbatim + 346 documented extraction） | — |

---

## 3. 证据 schema（三类基础 + 两类派生）

| 类型 | identity | 关键字段 |
|------|----------|----------|
| A ETF→benchmark | `ETF_TRACKING_RELATION_EVIDENCE_V1` | exchange / etf_code / etf_name / benchmark_code / benchmark_name / index_provider / listing_status / listing_date / source_type / official_source_url / source_publication_at / evidence_observed_at / evidence_available_at / raw_source_hash / valid_from / valid_to / notes |
| B benchmark→weights | `BENCHMARK_CONSTITUENT_WEIGHT_EVIDENCE_V1` | benchmark_code / provider / weight_source_type / constituent_effective_date / declared_constituent_count / rows(security_code,weight_pct) / weight_quality / weight_sum / evidence_observed_at / evidence_available_at / sources[] |
| C security→Shenwan L2 | `SHENWAN_L2_CLASSIFICATION_EVIDENCE_V1` | snapshot_id / validity_semantics / rows(security_code, l1_code, l1_name, l2_code, l2_name, classification_effective_from, evidence_available_at, classification_quality) / superseded_by / coverage_gap |
| D benchmark→L2 exposure（派生） | `BENCHMARK_L2_EXPOSURE_PIT_PACKAGE_V1` | benchmark_code / l2_weights / unmapped_weight / weight_sum / input_package_hashes / derivation_code_hash / production_available_at |
| E B40 mapping（派生） | `B40_MAPPING_EVIDENCE_V1` | target_l2_code / etf_code / benchmark_code / target_l2_exposure / target_is_largest / dominance_margin / mapping_type / admission_status / rejection_reason / production_available_at |

每个 package 都带 `package_hash = sha256(canonical_json(document 去除 package_hash 自身))`。

来源层另有 `kind` 区分（见 `raw_source_manifest_v1.json`）：

* `VERBATIM_PROVIDER_BYTES` —— 官方响应原样保存，重取可复现 SHA-256；
* `DOCUMENTED_EXTRACTION` —— 本系统聚合文档，必须携带 `derived_from`（上游文件名 + SHA-256）。

---

## 4. 构建命令（可确定性重跑）

```powershell
# 采集（联网，单独步骤；不在构建里做）
python -u D:\QuantForge\runtime\etf-quant-v1\production-pit-evidence-v1\build\harvest_sws.py
python -u D:\QuantForge\runtime\etf-quant-v1\production-pit-evidence-v1\build\harvest_csi_incremental.py

# 构建（不联网）
python scripts/etf_quant/build_production_pit_evidence.py --observed-at "<带时区 ISO8601>"
python scripts/etf_quant/build_production_pit_top5_status.py
python scripts/etf_quant/build_production_pit_manifest.py
```

相同输入 + 相同时刻 ⇒ 字节级可复现。不同时刻 ⇒ 新的 forward-only 生效点（append-only，新 package ID）。

---

## 5. 适配器 smoke test 结果

**适配器源码零修改**（见 `git diff --stat <base> -- strategies/etf_quant/mapping ...` 为空）。

`tests/etf_quant/test_production_pit_adapter.py` — **12/12 PASS**：

| 场景 | 结果 |
|------|------|
| 真实 book 经未修改 loader | PASS（1172 条记录全部通过 SOURCE / HASH / SCHEMA / TIME / CLASSIFICATION 门） |
| 每条记录 `COMPLETE_WEIGHT_SET` 且 `unmapped_weight == 0` | PASS |
| **`2026-09-24` 前缀为空（关键 no-backfill）** | PASS |
| 模拟未来 cutoff `2026-11-02` 跑 STRICT > PROXY > CASH | PASS |
| 同一 book 在 `2026-09-24` 全槽位 Cash | PASS |
| 篡改 pinned 源 | `PIT_OFFICIAL_SOURCE_HASH_BLOCKER` |
| 缺 `available_at` | `PIT_EVIDENCE_SCHEMA_BLOCKER` |
| 可用时刻倒填到观察之前 | `PIT_EVIDENCE_TIME_BLOCKER` |
| 伪造官方域名 | `PIT_OFFICIAL_SOURCE_IDENTITY_BLOCKER` |
| STRICT 路径仍拒绝 PIT book | `STRICT_PATH_PIT_EVIDENCE_FORBIDDEN` |

> 测试诚实性：ETF 行情 / 上市 / 交易状态为**合成**（兼容性测试不应依赖实时行情快照）；
> 决定准入的一切（权重向量、申万二级归属、可用时刻、pinned 源哈希）为**真实生产证据**。

**适配器的一条既有约束（非本轮修改，仅记录）**：
两个 pinned 来源**必须都是 JSON** 且文件名**不得含路径分隔符**。
构建器据此在写入时把审计路径扁平化（`weights/000300_x.json` → `weights__000300_x.json`），
审计身份保留在 `source_manifest` 的 `relative_path` 字段。

---

## 6. No-backfill 测试与 `2026-09-24`

`tests/etf_quant/test_production_pit_no_backfill_audit.py` — **21/21 PASS**。

该模块**刻意不 import 证据层**，只用标准库从原始 JSON 重新推导，构建器或 schema 的缺陷无法在审计中隐藏。
结论：

* book 中最早 `available_at = 2026-09-30T18:45:00+08:00`；
* `prefix(2026-09-24T18:00:00+08:00) == {}`；
* `prefix(2026-09-30T18:44:59+08:00) == {}`，`prefix(2026-09-30T18:45:00+08:00)` 才返回全部；
* 不存在任何把 `effective_date`（`2026-08-31`）当作 `available_at` 的字段。

---

## 7. 当前 Top5 生产证据状态

**这是"未来可用证据状态"，不是 `2026-09-24` 的运行结果。**
所有 package 的 `production_available_at = 2026-09-29T23:05:26+09:00`，因此 `2026-09-24` 一条都用不了。

| 行业 | 名称 | 状态 | 最佳 benchmark | 目标暴露 | 目标最大 | 可用 ETF |
|------|------|------|----------------|----------|----------|----------|
| 3706 | 医疗服务 | B40 拒绝（证据存在） | 000913 | **37.16%** | **是** | 1 |
| 3703 | 生物制品 | B40 拒绝（证据存在） | 930743 | 33.06% | 是 | 4 |
| 4901 | 证券Ⅱ | **PRODUCTION_PIT_PROXY_AVAILABLE** | 399975 | 100.00% | 是 | 17 |
| 4803 | 股份制银行Ⅱ | **PRODUCTION_PIT_PROXY_AVAILABLE** | H30022 | 41.48% | 是 | 1 |
| 3701 | 化学制药 | **PRODUCTION_PIT_PROXY_AVAILABLE** | 932217 | 58.14% | 是 | 1 |

即：**3 个可 Proxy，2 个因 B40 阈值/最大性不足而 fail closed 到 Cash**。
本轮**没有**用旧研究 evidence 去补齐这两个槽位。

`strict_pit_records = 617` 指的是适配器证据簿中行业码落在 Top5 内的记录条数，
**不等于** STRICT 映射准入数（STRICT 需要独立 VERIFIED registry 条目）。

---

## 8. 已知缺口（如实交接，不要粉饰）

1. **分类来源是官方行业指数成分表，不是官方全股票分类表。**
   `StockClassifyUse_stock.xls` 是 XLS，适配器无法消费；本轮改用申万官方 JSON
   二级行业指数成分（`component_stocks`）。差别已写入 registry `known_limitations`。

2. **分类缺口已基本关闭（前一轮报告有误，已自行纠正）。**
   早期版本用 `indextype=二级行业` 查询取行业目录，只拿到 **124** 个条目，
   我据此错误地认为 10 个封印二级行业没有官方指数。改用**未过滤**的
   `index_name/` 目录（1,014 条）后，**134 个封印二级行业全部可解析**，每个恰好唯一匹配。
   补齐后：分类证券 5200 → **5220**，派生暴露 61 → **100**，fail closed 51 → **12**。

   仍有 2 只证券（`920982`、`689009`）不在任何官方二级行业指数成分中，
   导致 **12** 个 benchmark fail closed。这是**真实的官方来源缺口**，
   两套独立采集都未在任何官方二级行业指数里找到它们。
   研究 sidecar 对它们有归类，但**未被提升为生产证据**。

3. **中证不提供"全量成分+逐股权重"的官方 JSON**（已穷举官网 200+ 接口路径）。
   全量只有 XLS。本轮走通官方 JSON 反向查询并重建，用"权重和 ∈ [99.0, 100.5] 且计数相符"
   作为独立算术交叉证明；186 个 benchmark 因计数不符被拒，**没有一个是因和不在带内被拒**。

4. **覆盖率 22.5%（权重）/ 20.1%（暴露）**，见第 2 节表格。
   **瓶颈已从分类转移到权重**：186 个 benchmark 的成分向量不完整（`count_mismatch`），
   继续增量抓取即可改善，不需要方法学变更。

5. **交易所目录不提供上市状态字段**（已对原始字节做 token 扫描，0 命中）。
   `listing_status` 仅表示"出现在交易所自己维护的在市基金目录中"。

6. **所有官方来源都不提供发布时间**，因此 `source_publication_at = null`，
   adapter book 中取本系统首次观察时刻作为诚实下界。历史 PIT **不可证明** → 全量 FORWARD_ONLY。

7. **来源可复现性已区分两类并全部标注**：427 个 pinned 来源中，
   81 个是 `VERBATIM_PROVIDER_BYTES`（官方字节原样保存，可重取复现 SHA-256），
   346 个是 `DOCUMENTED_EXTRACTION`（本系统聚合文档，**100% 携带上游 `derived_from` 文件与哈希**）。
   申万 134 个原始响应实测重新抓取 SHA-256 完全一致，且原始字节中无注入字段。

8. `SOURCE_LICENSING_UNRESOLVED`（保持，未做法律判断）。

9. 深交所目录分页请求有限流，重放采集必须限速退避。

---

## 9. 本轮未做（符合任务边界）

* 未创建 Shadow epoch（`SHADOW_EPOCH_CREATED = FALSE`）。
* 未创建任何 formal signal / intent / order / fill / holding / NAV / PnL。
* 未修改任何冻结常量：B40 = 40.0、target-largest = True、35% cap、20 日流动性、
  STRICT > PROXY > CASH 优先级、T+1 合约、`daily_cycle` / rebalance 业务语义。
* 未修改 19 因子 / Ridge / H10·H40·H120 / Fusion / Source-C / 行业 ranking / Top5。
* 未读取 Validation performance / Final OOS。
* 未构建历史回放数据库（FUTURE_WORK）。

---

## 10. 给 Codex 的建议认证步骤

1. 复核 `strategies/etf_quant/evidence/` 的时间语义三定律：
   `publication <= observed <= available`、`effective_date <= available.date()`、
   `production_available_at = max(所有输入)`。断言方式是"看代码 + 跑
   `tests/etf_quant/test_production_pit_no_backfill_audit.py`"。
2. 复核 registry 小文件与 runtime 报告一致（counts / hashes / availability）。
3. 跑 `tests/etf_quant/test_production_pit_adapter.py`，确认真实 package 被**现有**适配器准入。
4. 抽查 2–3 个 pinned 源，从官方 URL 重新抓取并核对 SHA-256 与 manifest。
5. 确认 `git diff --stat <base> -- strategies/etf_quant/{mapping,portfolio,runtime,models,factors}` 为空。
6. 依 `Evidence Readiness` 定义（见 registry 文档第 1 节）决定
   `ETF_QUANT_PROXY_READY_FOR_SHADOW`。**本轮不自行把它改成 TRUE。**

---

## 11b. 与独立 155 次官方扫描的一致性核对

另一个独立子智能体对官方 API 做了 **155 次**逐行业扫描（31 一级 + 124 二级），
报告 L1 覆盖 5,220 只、L2 覆盖 5,200 只，并列出**恰好 20 只**"有 L1 无 L2"的证券。

把本轮补收的 10 个二级行业加回去后核对：

| 核对项 | 结果 |
|--------|------|
| 本轮 L2 并集证券数 | **5,220** |
| 独立 L1 扫描并集证券数 | **5,220** —— **完全相等** |
| 独立报告的 20 只"有 L1 无 L2" | **20/20 全部由这 10 个行业补回**，无遗漏、无多余 |
| 同一证券落入多个 L2 | **0** |
| 每个行业 `count == len(results)` | **134/134 通过** |

**剩余 12 个 benchmark 的 fail closed 责任证券只有 2 只**：

| 证券 | 名称 | 阻塞数 | 官方申万归属 |
|------|------|--------|--------------|
| `689009` | 九号公司 | 6 | **无**（134 个 L2 与 31 个 L1 响应中都不出现） |
| `920982` | 锦波生物 | 7 | **无**（同上） |

两只都是真实上市公司，且 **CSI CICS 与研究 sidecar 都在给它们归类**——
只有申万官方行业指数不收它们。这是数据源覆盖差异，不是检索缺陷。
已在审计模块中用测试锁死：官方若补收，测试立即失败并提示重跑构建。

---

## 12. 本轮技术环境说明（供复核者避免误判）

* 宿主 Python 使用 DSH 捆绑运行时：
  `C:\Users\Lenovo\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`。
* **必须设置 `PYTHONUTF8=1`**：该解释器默认 locale 编码为 cp1252，
  而 `tests/etf_quant/test_config_domain.py::test_core_import_firewall_and_no_provider_urls`
  使用 `Path.read_text()` 无显式编码读取含中文注释的源文件。
  经实测（临时移出本轮新增模块后仍失败），该失败**与本轮改动无关**，
  是解释器 locale 差异，不是仓库缺陷。设置 `PYTHONUTF8=1` 后该测试通过。
* 本轮实测测试结果（提交后、clean tree 上）：
  `tests/etf_quant` + 两个顶层 ETF 测试文件 = **见本轮最终实测**（下方第 14 节）。
* 未运行封存研究测试，未触碰 Validation / OOS 数据。
* Docker：本轮未使用（未重装、未修改）。

---

## 13. 独立对抗审计的结论与处置

本轮在执行中另起了一个**独立对抗审计子智能体**（不与被审计方共享任何测试），
它的结论是"证据树数字层面异常干净，但来源链断裂 + 不稳定，当时不能作为生产 PIT 证据使用"。
其发现已逐条处置：

| # | 审计发现 | 本轮处置 |
|---|---------|---------|
| 1 | 320 个 pinned 文件中 240 个是本地合成文档却挂官方 URL，哈希不可复现 | 引入 `kind`：81 个 `VERBATIM_PROVIDER_BYTES` + 303 个 `DOCUMENTED_EXTRACTION`，后者 **100%** 带 `derived_from`（上游文件 + SHA-256） |
| 2 | 申万 pinned 文件被注入了 `source_url`/`swindexcode` 两个字段 | 重新采集 **134** 个响应，**原样保存**，实测重取 SHA-256 完全一致，无注入字段 |
| 3 | 记录里的 CSI `weight_source_url` 实测返回 `code=500` | 端点与调用方式写入 manifest note 与 registry 文档；CSI 原始响应另行登记 |
| 4 | 硬编码 `--valid-from 2026-09-30` 埋着倒填机制 | 默认改为观察时刻的本地日期，并加"早于观察日即拒绝构建"护栏 |
| 5 | `constituent_effective_date` 硬编码 `2026-08-31`，无官方出处 | 删除该字面量；改为锚定官方 `beginningdate`，无官方日期时用观察日**并显式标注** |
| 6 | 分类包丢掉官方 `beginningdate`，全部写成构建常量 | 改为逐券使用官方 `beginningdate`，**5220/5220 全部来自官方**，共 521 个不同取值 |
| 7 | `csi_reverse` 输入目录在构建后仍在增长，构建不可复现 | 已停止采集，缓存冻结（4202 文件），本次最终构建基于冻结快照 |
| 11 | 分类目录取自 `indextype=二级行业` 过滤查询，漏掉 10 个官方二级行业 | 改用**未过滤**的 `index_name/` 目录（1,014 条）按官方名称精确匹配，**134 个二级行业全部覆盖**；分类证券 5200→**5220**，派生暴露 61→**100**，fail closed 51→**12** |
| 8 | 覆盖率只有 10% 却未显式报告 | registry 与 build report 显式记录 `scope = 498`，并给出 112 / 61 的占比 |
| 9 | 全部证据共享一个时间常量，只靠一个常量兜住 | 加双向护栏（不得早于真实抓取、不得晚于墙上时钟）+ 逐来源检索账本；`last_real_retrieval` 由账本推导 |
| 10 | 审计期间发现上一版 `observed_at` 比机器时钟超前 21h | 已加入"拒绝未来观察时刻"护栏（该缺陷真实发生过并被修复） |

审计同时确认成立、本轮未改动的部分：无历史倒填（C1）、`effective_date` 未冒充 `available_at`（C2）、
权重真实完整（C4）、无重归一化（C5）、适配器未修改（C10）、包哈希可复现（C11）、Top5 报告与底层包一致。

**审计的总体判断仍应传给 Codex**：本轮证据体系在**结构与时间语义**上已经可审计、可复现、
fail-closed 明确，但在**覆盖率**（22.5% 权重 / 20.1% 暴露）与**分类来源层级**（指数成分而非官方分类表）上仍是有限的。
`ETF_QUANT_PROXY_READY_FOR_SHADOW` 的最终判定交给 Codex，本轮不自行置 TRUE。
