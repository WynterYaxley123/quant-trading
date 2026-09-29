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
| worktree | `D:\quant-worktrees\deepseek-production-pit-evidence-v1` |
| final SHA | 见本节末尾（提交后填写） |
| push | **未执行** |

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
| 原始采集（repo 外） | `...\raw\`（含 `raw\sws\l2_members\` 124 个文件、`raw\sws\catalog\`） |
| immutable packages | `...\packages\{weights,exposure,classification}\` |
| 适配器证据簿 | `...\adapter-tests\production_evidence_book_v1.json` |
| 报告 | `...\reports\` |
| registry（repo 内副本） | `reports/etf_quant/production_pit_evidence_registry_v1.json` |

registry 元数据（见 `production_pit_evidence_registry_v1.json`）：

```json
{
  "registry_id": "PRODUCTION_PIT_EVIDENCE_REGISTRY_V1::2026-09-29",
  "schema_version": "1.0.0",
  "created_at": "2026-09-29T22:50:56+09:00",
  "production_available_from": "2026-09-29T22:50:56+09:00",
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
| 成功派生 L2 暴露 | 61 | 12.2% |
| 因分类不完整 fail closed | 51 | 10.2% |
| 因成分计数不符被拒 | 186 | 37.3% |
| 分类覆盖证券 | 5200 | —（124 个二级行业，0 冲突） |
| 适配器证据簿记录 | 1816 | — |
| pinned 来源 | 384（81 verbatim + 303 documented extraction） | — |

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
所有 package 的 `production_available_at = 2026-09-29T22:50:56+09:00`，因此 `2026-09-24` 一条都用不了。

| 行业 | 名称 | 状态 | 最佳 benchmark | 目标暴露 | 目标最大 | 可用 ETF |
|------|------|------|----------------|----------|----------|----------|
| 3706 | 医疗服务 | B40 拒绝（证据存在） | 000814 | 28.04% | 否 | 1 |
| 3703 | 生物制品 | B40 拒绝（证据存在） | 930743 | 33.06% | 是 | 4 |
| 4901 | 证券Ⅱ | **PRODUCTION_PIT_PROXY_AVAILABLE** | 399975 | 100.00% | 是 | 17 |
| 4803 | 股份制银行Ⅱ | **PRODUCTION_PIT_PROXY_AVAILABLE** | H30022 | 41.48% | 是 | 1 |
| 3701 | 化学制药 | **PRODUCTION_PIT_PROXY_AVAILABLE** | 932217 | 58.14% | 是 | 1 |

即：**3 个可 Proxy，2 个因 B40 阈值/最大性不足而 fail closed 到 Cash**。
本轮**没有**用旧研究 evidence 去补齐这两个槽位。

`strict_pit_records = 170` 指的是适配器证据簿中行业码落在 Top5 内的记录条数，
**不等于** STRICT 映射准入数（STRICT 需要独立 VERIFIED registry 条目）。

---

## 8. 已知缺口（如实交接，不要粉饰）

1. **分类来源是官方行业指数成分表，不是官方全股票分类表。**
   `StockClassifyUse_stock.xls` 是 XLS，适配器无法消费；本轮改用申万官方 JSON
   二级行业指数成分（`component_stocks`）。差别已写入 registry `known_limitations`。

2. **6 只证券无官方二级行业归属**（`CLASSIFICATION_INCOMPLETE` 导致 51 个 benchmark fail closed）：

   | 证券 | 研究 sidecar 归类 | 官方行业指数 |
   |------|------------------|--------------|
   | 600938 | 7501 油气开采Ⅱ | 官方无此指数 |
   | 300896 / 920982 / 688363 | 7703 医疗美容 | 官方无此指数 |
   | 601888 | 4507 旅游零售Ⅱ | 官方无此指数 |
   | 689009 | 2804 摩托车及其他 | 有指数（801881，16 成员）但该证券不在其中 |

   另有 10 个封印二级行业官方不发布对应行业指数：
   `1103, 1109, 3307, 4507, 4606, 4607, 4806, 7208, 7501, 7703`。

   这 6 只在研究 sidecar 里都有归类 —— 这是**真实的官方 vs 研究分歧**，
   已按 `CROSS_CHECK_ONLY` 报告，**研究 sidecar 未被提升为生产证据，也未被用来补洞**。

3. **中证不提供"全量成分+逐股权重"的官方 JSON**（已穷举官网 200+ 接口路径）。
   全量只有 XLS。本轮走通官方 JSON 反向查询并重建，用"权重和 ∈ [99.0, 100.5] 且计数相符"
   作为独立算术交叉证明；186 个 benchmark 因计数不符被拒，**没有一个是因和不在带内被拒**。

4. **覆盖率只有 22.5%（权重）/ 12.2%（暴露）**，见第 2 节表格。
   最高优先级的后续工作是把 186 个 `count_mismatch` 的 benchmark 补齐成分（继续增量抓取即可）。

5. **交易所目录不提供上市状态字段**（已对原始字节做 token 扫描，0 命中）。
   `listing_status` 仅表示"出现在交易所自己维护的在市基金目录中"。

6. **所有官方来源都不提供发布时间**，因此 `source_publication_at = null`，
   adapter book 中取本系统首次观察时刻作为诚实下界。历史 PIT **不可证明** → 全量 FORWARD_ONLY。

7. **来源可复现性已区分两类并全部标注**：384 个 pinned 来源中，
   81 个是 `VERBATIM_PROVIDER_BYTES`（官方字节原样保存，可重取复现 SHA-256），
   303 个是 `DOCUMENTED_EXTRACTION`（本系统聚合文档，**100% 携带上游 `derived_from` 文件与哈希**）。
   申万 124 个原始响应实测重新抓取 SHA-256 完全一致，且原始字节中无注入字段。

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

## 11. 本轮技术环境说明（供复核者避免误判）

* 宿主 Python 使用 DSH 捆绑运行时：
  `C:\Users\Lenovo\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`。
* **必须设置 `PYTHONUTF8=1`**：该解释器默认 locale 编码为 cp1252，
  而 `tests/etf_quant/test_config_domain.py::test_core_import_firewall_and_no_provider_urls`
  使用 `Path.read_text()` 无显式编码读取含中文注释的源文件。
  经实测（临时移出本轮新增模块后仍失败），该失败**与本轮改动无关**，
  是解释器 locale 差异，不是仓库缺陷。设置 `PYTHONUTF8=1` 后该测试通过。
* 受影响的 ETF 测试：`tests/etf_quant` 全部通过（见第 12 节实测数字）。
* 未运行封存研究测试，未触碰 Validation / OOS 数据。
* Docker：本轮未使用（未重装、未修改）。
