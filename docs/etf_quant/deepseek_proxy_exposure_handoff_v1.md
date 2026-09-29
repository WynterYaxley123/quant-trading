# DEEPSEEK PROXY EXPOSURE —— CODEX 交接单（V1）

生成时间：2026-09-29T16:27:55+09:00

## 1. Git

| 项 | 值 |
|---|---|
| branch | `agent/deepseek-etf-quant-proxy-exposure-v1` |
| base SHA | `681b2ccb52fdb5d28a8607d3255e81975b628d02` |
| final SHA | `0c953e3ca970ff6d7c6ce2a2076c3668aeb35de7` |
| worktree | `D:\quant-worktrees\deepseek-etf-quant-proxy-exposure` |
| push | **未推送**（本地） |

## 2. 本轮新增/改动文件

- `strategies/etf_quant/mapping/proxy.py` —— PROXY_EXPOSURE 契约核心（纯函数）
- `tests/etf_quant/test_proxy_exposure.py` —— 46 条契约测试
- `reports/etf_quant/proxy_l2_coverage_sensitivity_v1.json`
- `reports/etf_quant/proxy_current_top5_feasibility_v1.json`
- `reports/etf_quant/proxy_execution_candidate_v1.json`（若已建立）
- `reports/etf_quant/deepseek_proxy_exposure_manifest_v1.json`
- `docs/etf_quant/proxy_exposure_feasibility_v1.md`、本文件

**未改动**：19 因子、H10/H40/H120、Ridge alpha、6 日历月窗口、min_valid_days、label 成熟、
z-score、fusion `0.25/0.50/0.25`、行业排序、Top5 信号、严格映射 registry、流动性规则。

## 3. 关键输入与其位置

| 输入 | 位置 | 说明 |
|---|---|---|
| 中证官方权重 | `runtime\...\official-sources\csi_reverse_weights_v1.json` | 逐证券反查，LEVEL 1 |
| 国证官方权重 | `runtime\...\subagents\subagent-b-cni-weights\cni_official_weights_v1.json` | 官方工作簿，LEVEL 1 |
| 股票→申万二级 | `runtime\...\subagents\subagent-c-sw-membership\stock_to_l2_v1.json` | as-of `2026-09-24` |
| ETF 流动性 | `runtime\...\subagents\subagent-f-liquidity\etf_liquidity_20d_v2.json` | 冻结 20 日，CNEquity pinned |
| 冻结契约审计 | `runtime\...\subagents\subagent-g-contract-audit\frozen_contract_audit_v1.json` | 15 契约 / 224 行级引用 |

## 4. 测试

```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; $env:PYTHONDONTWRITEBYTECODE='1'
& 'C:\Users\Lenovo\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe' `
  -m pytest -p no:cacheprovider -q tests/etf_quant
```

`PYTHONUTF8=1` **必需**（默认 cp1252 会在读取中文源码时抛 `UnicodeDecodeError`）。
Docker 当前 DOWN，上表命令为实测可用的等价路径。

## 5. 结论摘要

- STRICT：**4 / 134 = 2.99%**，`NOT_EXECUTABLE_UNDER_CURRENT_ETF_SUPPLY`
- PROXY 可行性：**MODERATE**
- 推荐规则：{"name": "A40", "threshold": 40.0, "require_largest": false, "min_dominance_margin": null, "selection_basis": "highest target-exposure threshold that still yields 5/5 distinct; then prefer requiring target-is-largest; then the larger dominance margin. NOTE: no rule that requires target-is-largest reaches 5/5, so this selection necessarily fell through to the threshold-only shape.", "distinct_etfs": 5, "fidelity_class": "TECHNICALLY_FEASIBLE_BUT_LOW_FIDELITY"}
- 是否建立 candidate：**是**
- SHADOW_EPOCH_CREATED：**FALSE**

## 6. 建议整合顺序

1. 先看 `strategies/etf_quant/mapping/proxy.py` 与 46 条测试 —— 契约即文档。
2. 再核对 `proxy_l2_coverage_sensitivity_v1.json` 的 24 行敏感度表，确认推荐规则可复现。
3. 再看 `proxy_current_top5_feasibility_v1.json` 确认 Top5 逐行业映射。
4. 若建立 candidate，最后看 `proxy_execution_candidate_v1.json` 与组合约束。
5. `deepseek_proxy_exposure_manifest_v1.json` 内含全部输入哈希，可直接校验。

## 7. 已知限制（与可行性文档第 7 节一致）

- Proxy purity 是执行质量指标，不是收益指标；未混入 alpha。
- 证据观察时间不回填至 2026-09-24。
- 权重集不完整的基准一律 fail-closed，因此覆盖率为下界。
- 股票→申万二级归属为单一 sidecar 来源，`SOURCE_LICENSING_UNRESOLVED`；
  `HISTORICAL_MEMBERSHIP_PIT_UNPROVEN`。
- 冻结湖对 ETF 日线覆盖有限，无数据即不可准入。
- 严格版本与"不可执行"结论原样保留，proxy 只是独立 execution variant。
