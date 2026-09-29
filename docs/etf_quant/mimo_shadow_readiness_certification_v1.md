# ETF-Quant V1 — Shadow Readiness 认证书（MiMo）

```
PRIMARY：MIMO_FINAL_PIT_READINESS_CERTIFICATION_COMPLETE

PRODUCTION_PIT_EVIDENCE_REGISTRY：PASS
SWS_MEMBERSHIP_EVIDENCE：PASS_WITH_KNOWN_LIMITATION
PRODUCTION_STRICT_EVIDENCE：PASS
PIT_ADAPTER_COMPATIBILITY：PASS
NO_BACKFILL_AUDIT：PASS
FAIL_CLOSED_CASH：PASS
TECHNICAL_SHADOW_READINESS：PASS
ETF_QUANT_PROXY_READY_FOR_SHADOW：TRUE
SHADOW_EPOCH_CREATED：FALSE
```

分支：`agent/mimo-final-pit-readiness-certification-v1`
认证基线：`78562bd575d78db875296e34871a52ec977f1483`
认证时间：2026-09-30（证据冻结时刻 2026-09-29T23:05:26+09:00 起 forward-only）
执行政策：**B40_WITH_CASH**（用户已批准；A40 / B40_RENORMALIZED 不在讨论范围）

---

## 一、认证对象与范围

本认证基于：

1. DeepSeek 生产 PIT 证据体系（`PRODUCTION_PIT_EVIDENCE_REGISTRY_V1::2026-09-29`，
   8133 条适配器证据簿记录，427+ pinned 来源，全量 FORWARD_ONLY）；
2. Codex B40_WITH_CASH runtime 接线（daily_cycle / Cash 再平衡 / T+1 延迟记账 /
   Shadow dry-run，已认证）；
3. 本轮 MiMo 的独立复核、真实 package 冒烟与最小机械修正（strict 成分集包含派生）。

认证对象是"**是否可以安全进入 READY_FOR_FUTURE_SHADOW**"，不是启动 Shadow。

## 二、认证结论的依据（对照就绪门槛）

| 门槛 | 状态 | 依据 |
|------|------|------|
| PIT Adapter | PASS | 12/12 真实 package 测试 + 本轮 A/B/C 冒烟，适配器零修改 |
| Production evidence schema | PASS | 49 单元契约测试；五类证据（A–E）时间链三定律 |
| 官方来源 provenance | PASS | SSE 500 行逐字段一致、CSI 权重逐值一致、SWS 134/134 哈希链（3 源抽查） |
| forward-only 语义 | PASS | `publication <= observed <= available`；`available_at = max(输入)` |
| no-backfill | PASS | `prefix(2026-09-24) == {}`；`available_at-1s` 边界拒绝；双向 wall-clock 护栏 |
| SWS membership 语义 | PASS（附 limitation） | 5220 券 0 冲突、1104/1104 交叉一致、缺口 fail closed |
| Strict/Proxy/Cash 行为 | PASS | 4901→STRICT（成分集包含+verified registry 双证）；4803/3701→PROXY；3706/3703→Cash |
| 缺证据 fail closed | PASS | 12 benchmark fail closed；186 count_mismatch 拒绝；不回退研究证据 |
| Cash runtime | PASS | Codex 合成状态机认证；现金保留、无 order、不再分配 |
| T+1 | PASS | Codex 合成状态机认证；真实 raw open、延迟记账、拒绝 T+2 补执行 |
| candidate integrity | PASS | manifest 哈希互锁逐一复核；source_integrity 全通过 |
| tests | PASS | 基线 512 passed / 1 skipped 达标 + 新增 22 用例 |
| security | PASS | secret/credential/token/.env/tracked raw rows/runtime DB = 0 |

**Coverage 低（22.5%/20.1%）不构成阻断**：B40_WITH_CASH 已定义缺证据→Cash 的
确定性行为，且未设最低覆盖阈值；该缺口如实记为
`PRODUCTION_EVIDENCE_COVERAGE_LOW`（product availability limitation），
未来信号中表现为较高 Cash 比例，增量补抓权重可改善。

## 三、SWS membership 结论

`component_stocks` 官方二级行业指数成分集合**足够**作为 production
Security→Shenwan L2 membership 证据（`PRODUCTION_MEMBERSHIP_EVIDENCE_SUFFICIENT`）：

- 语义上，申万二级行业指数成分集合即该行业成员集合（行业指数按分类取成分）；
  5220 券在 134 个官方二级行业指数成分间构成 0 冲突的互斥分割，支持一一语义；
- 与研究 sidecar 交叉 1104/1104 一致（sidecar 仅 CROSS_CHECK_ONLY，未提升）；
- 不在任何官方成分内的证券（920982、689009）fail closed，缺口方向只会"少分类→Cash"；
- 来源为申万官方 API、可重取、逐字节哈希、逐券官方生效日、forward-only、append-only。

保留 known limitation：

```
SOURCE_FORM_LIMITATION = OFFICIAL_L2_INDEX_CONSTITUENTS_NOT_MASTER_CLASSIFICATION_TABLE
```

这是 provenance 形态限制，不是技术不安全。

## 四、Strict 结论

**4901 = STRICT_PIT_AVAILABLE。** "Production Strict mappings = 0" 是生产证据层
`decide_b40_mapping` 硬编码 `PROXY_EXPOSURE` 类型的口径问题，不是 4901 被降级：

- 运行时 STRICT 通道是独立的 `VERIFIED_MAPPING_REGISTRY_V1`，4901 已有 2 条 VERIFIED
  （512880.SH / 159848.SZ → 399975，官方基金文件，哈希核对通过）；
- `select_pit_mappings` 对存在 strict 行的行业不进入 proxy 候选；`select_mappings_partial`
  中 strict 独占候选池——**Proxy 覆盖 Strict 不可能发生**；
- 生产证据独立重证成分集包含：399975/931412/931402/950105 四个 benchmark 对 4901
  成分集包含成立（越界 0、缺分类 0、unmapped 0、权重集完整）。严格性由逐券包含证明，
  不由"暴露恰好 100%"证明；
- 本轮小修（strict.py 派生 + summary + 22 测试）不改变 Strict 定义、不改 verified
  registry 语义、不改 daily_cycle；`available_at <= decision_at` 的 PIT 约束同样适用
  （2026-09-24 全不可见，无倒填）。

## 五、就绪状态

```
candidate_status           = READY_FOR_FUTURE_SHADOW
policy_approved            = TRUE
execution_policy           = B40_WITH_CASH
technical_shadow_readiness = PASS
ready_for_shadow           = TRUE
production_pit_evidence_ready = TRUE
production_ready_from      = READY_FOR_NEXT_ELIGIBLE_FUTURE_SIGNAL_CYCLE
shadow_epoch_created       = FALSE
```

`production_ready_from` 语义：全部证据 forward-only（最早可用 2026-09-29T23:05:26+09:00），
**2026-09-24 不是也不可能是生产起点**；真实 Shadow 起点只能是未来合法信号日，
本认证不猜测具体交易日期，写 `READY_FOR_NEXT_ELIGIBLE_FUTURE_SIGNAL_CYCLE`。

**READY 不是启动。** 即便 `ETF_QUANT_PROXY_READY_FOR_SHADOW = TRUE`：
`SHADOW_EPOCH_CREATED = FALSE`；未生成 formal signal / intent / order / fill /
holding / NAV / PnL。启动 Shadow 需用户另行授权，且必须在合法未来交易日以真实
上市与 20 日流动性重新核对后进行。

## 六、强制声明

MAIN 未修改；旧 integration 分支未修改；旧 DeepSeek / Codex / Kimi worktree 未修改；
F1 未修改；Validation performance 未读取；Final OOS 未读取；19 因子未修改；
Ridge 未修改；H10/H40/H120 未修改；Fusion 未修改；Source-C 未修改；
industry ranking 未修改；Strict 规则未降低；B40 未修改；40% 未降低；
target-largest 未降低；Cash policy 未修改；daily_cycle 业务语义未修改；
rebalance 业务语义未修改；T+1 业务语义未修改；35% cap 未修改；
20 日流动性未修改；purity 未参与 alpha；research sidecar 未冒充 production evidence；
missing evidence fail closed；missing classification fail closed；
incomplete benchmark fail closed；future evidence rejected；
effective_date 未冒充 available_at；没有历史证据倒填；Strict > Proxy > Cash；
Cash 未伪装成 ETF；Cash 未重新分配；Cash 未产生 order；未创建 Shadow epoch；
未创建 formal signal/order/fill/holding/NAV/PnL；未 push；未提交大型 raw 数据；
未暴露 secret。`SOURCE_LICENSING_UNRESOLVED` 保持。
