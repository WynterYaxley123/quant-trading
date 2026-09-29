# DEEPSEEK PROXY POLICY FINALIZATION —— CODEX 交接单（V1）

生成时间：2026-09-29T18:23:57+09:00

## 1. Git

| 项 | 值 |
|---|---|
| branch | `agent/deepseek-etf-quant-proxy-policy-finalization-v1` |
| base SHA | `c309f39ad80f43f6660dfbc30f87706890f6f846` |
| final SHA | `8bf97d5c85b1743f01f535fc7096eb9c19b752b6` |
| worktree | `D:\quant-worktrees\deepseek-etf-quant-proxy-policy-finalization` |
| push | **未推送** |

## 2. 本轮结论

- **3706_DOMINANT_B40_PROXY = NOT_FOUND**（最佳 target-is-largest 候选仅 37.16%，低于 40% 边界）
- **RECOMMENDED_EXECUTION_POLICY = `B40_WITH_CASH`**
- 三方案排序在换用流动性优先选券规则后**不变**
- **TECHNICAL_SHADOW_READINESS = PASS**（工程完整）
- **PROXY_POLICY_APPROVED = FALSE**（等待用户批准执行政策）
- **ETF_QUANT_PROXY_READY_FOR_SHADOW = FALSE**
- **SHADOW_EPOCH_CREATED = FALSE**

## 3. 本轮新增文件

- `strategies/etf_quant/portfolio/policy.py` —— 三种执行政策的核心契约（纯函数）
- `tests/etf_quant/test_proxy_execution_policy.py` —— 政策契约测试
- `reports/etf_quant/proxy_execution_policy_v1.json`
- `reports/etf_quant/proxy_policy_comparison_v1.json`
- `reports/etf_quant/proxy_execution_candidate_v1.json`
- `reports/etf_quant/deepseek_proxy_policy_finalization_manifest_v1.json`
- `docs/etf_quant/proxy_execution_policy_v1.md`、本文件

**未改动**：19 因子、H10/H40/H120、Ridge alpha、6 日历月窗口、min_valid_days、label 成熟、
z-score、fusion `0.25/0.50/0.25`、行业排序、Top5 信号、严格映射 registry、流动性规则。

## 4. 建议 Codex 审查顺序

1. `strategies/etf_quant/portfolio/policy.py` 与 `test_proxy_execution_policy.py` —— **契约即文档**。
   重点看两条红线：`B40_WITH_CASH` 的存活权重必须与参考权重逐位相同；`cash` 禁止重分配。
2. `reports/etf_quant/proxy_policy_comparison_v1.json` —— 三方案逐指标对比与实际 L2 暴露。
3. `reports/etf_quant/proxy_execution_policy_v1.json` —— 执行政策契约。
4. `reports/etf_quant/proxy_execution_candidate_v1.json` —— PROPOSED candidate。
5. `docs/etf_quant/proxy_execution_policy_v1.md` —— 推荐理由与权衡。
6. `reports/etf_quant/deepseek_proxy_policy_finalization_manifest_v1.json` —— 全部输入哈希。

## 5. Integration hotspots

- `strategies/etf_quant/portfolio/` 是本轮新增的目录职责；`policy.py` 不依赖任何 I/O，可被 shadow 层直接调用。
- 现金需要一个**执行层**字段（不是资产字段）。若既有 schema 需要变更，请保持**加性、向后兼容**，
  详见子智能体 E 的 `cash_schema_compatibility_v1.json`。
- `rebalance_trigger` 的语义变化（可执行性切换算 member-set change）会影响既有 shadow 比较逻辑，
  这是最需要回归的一处。

## 6. 已知限制

见 `proxy_execution_policy_v1.md` 第 7 节。要点：现金收益未定义；tier-2 覆盖非穷尽；
权重集不完整者 fail-closed；成员归属单一来源；ETF 行情覆盖受冻结湖限制；政策待用户批准。

## 7. 测试

```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; $env:PYTHONDONTWRITEBYTECODE='1'
& 'C:\Users\Lenovo\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe' `
  -m pytest -p no:cacheprovider -q tests/etf_quant
```

`PYTHONUTF8=1` **必需**。Docker 当前 DOWN，上表为实测可用路径。
