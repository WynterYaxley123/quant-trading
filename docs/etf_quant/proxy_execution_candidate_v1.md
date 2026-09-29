# ETF-Quant V1 —— PROPOSED PROXY EXECUTION CANDIDATE（V1）

- 生成时间：2026-09-29T16:16:29+09:00
- candidate_id：`ETF_QUANT_V1_PROXY_EXECUTION_CANDIDATE`
- status：**`PROPOSED_PROXY_EXECUTION_CANDIDATE`**（**不是**正式策略升级）
- base_strategy：`ETF_QUANT_V1`
- execution_mapping_variant：`PROXY_EXPOSURE_V1`
- research_model_changed：**FALSE**　strict_mapping_changed：**FALSE**
- strict_v1_status：`NOT_EXECUTABLE_UNDER_CURRENT_ETF_SUPPLY`（原样保留）

## 1. 时间语义

| 字段 | 值 |
|---|---|
| historical_reference_cutoff | `2026-09-24` |
| proxy_evidence_observed_at | `2026-09-29T16:13:56+0900` |
| candidate_created_at | `2026-09-29T16:16:29+09:00` |
| production_ready_from | `2026-09-29T16:13:56+0900`（不早于全部 proxy 证据可得时刻） |

## 2. 推荐规则

```json
{
  "name": "A40",
  "threshold": 40.0,
  "require_largest": false,
  "min_dominance_margin": null,
  "selection_basis": "highest target-exposure threshold that still yields 5/5 distinct; then prefer requiring target-is-largest; then the larger dominance margin. NOTE: no rule that requires target-is-largest reaches 5/5, so this selection necessarily fell through to the threshold-only shape.",
  "distinct_etfs": 5,
  "fidelity_class": "TECHNICALLY_FEASIBLE_BUT_LOW_FIDELITY"
}
```

## 3. Top5 执行映射

| L2 | 名称 | ETF | 名称 | 基准 | 映射类型 | final_score | raw softmax | cap 后权重 | 目标暴露 | dominance | 20 日均额（元） |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3706 | 医疗服务 | 159828.SZ | 医疗ETF国泰 | 399989 | PROXY_EXPOSURE | 2.376717 | 40.7733% | 35.0000% | 44.83% | -4.60% | 44,494,397 |
| 3703 | 生物制品 | 159643.SZ | 疫苗ETF国泰 | 980015 | PROXY_EXPOSURE | 1.835451 | 23.7305% | 24.5360% | 46.40% | 23.06% | 7,483,184 |
| 4901 | 证券Ⅱ | 159008.SZ | 证券ETF景顺 | 399975 | PROXY_EXPOSURE | 1.228286 | 12.9306% | 14.5080% | 100.00% | 100.00% | 6,482,513 |
| 4803 | 股份制银行Ⅱ | 159887.SZ | 银行ETF富国 | H30022 | PROXY_EXPOSURE | 1.106860 | 11.4521% | 13.1352% | 41.48% | 12.07% | 86,955,232 |
| 3701 | 化学制药 | 159835.SZ | 创新药ETF建信 | 931152 | PROXY_EXPOSURE | 1.076853 | 11.1135% | 12.8208% | 45.98% | 17.99% | 14,520,833 |

## 4. 组合约束校验

```json
{
  "distinct_etfs": 5,
  "all_weights_positive": true,
  "all_weights_finite": true,
  "sum_to_one": 1.0,
  "max_weight": 0.35,
  "cap": 0.35,
  "cap_respected": true,
  "leverage": false,
  "short_positions": false
}
```

## 5. 执行质量指标（非收益）

```json
{
  "weighted_average_target_l2_purity": 52.926698,
  "minimum_target_l2_purity": 41.48,
  "weighted_proxy_leakage": 47.073302,
  "max_weight": 0.35,
  "weight_sum": 1.0,
  "name_count": 5
}
```

## 6. 完整性哈希

```json
{
  "exposure_matrix_sha256": "40b25e60f7b024fa8ed6f4aeb379b0d8335e0d0ea36d23f7d44a620bfe0bdccd",
  "benchmark_l2_purity_sha256": "978c3488a782e5217a9502d08e1f4e4226888690e389480bda3f3396390e665c",
  "csi_weights_sha256": "4b22e83312189368689312c4b9c7eea24883e1e0954e7c04ebd32dcbcdfe7b50",
  "cni_weights_sha256": "4955b7549e3c495b091849e79140528cbed8c8cc41f4de121468db773eb68f2c",
  "stock_to_l2_sha256": "483758af388e57806c6c741d0613c1b832d9730b458bc5b5a453149b546f0c02",
  "liquidity_sha256": "e7b851d06bbe5e6983688d59bf0ad3072a1ad59ea4401e000b8804ac18db5eec"
}
```

## 7. 用途与边界

本 candidate 只能证明：**若用户批准 Proxy Execution Variant，技术上可以进入未来 Shadow**。
它**不能**证明 2026-09-24 当时已经可以运行 proxy，因为权重证据的观察时间晚于参考日。

未创建 Shadow epoch；未产生正式 signal / intent / fill / holding / NAV / PnL。
T+1 契约（`DELAYED_T1_OPEN_ACCOUNTING`，T 日收盘定稿 → T+1 实际开盘经济执行）保持不变。
