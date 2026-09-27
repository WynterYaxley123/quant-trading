# ETF-Quant V1 — Legacy Offline Test Fixture & Gate Audit V1

- 任务性质：FORENSIC INVENTORY / TEST-GATE AUDIT（只调查，不修复、不伪造、不降门槛）
- ETF-Quant integration commit（被测）：`594d04c76f31c25d0f147fc175f564b487830cd5`
- integration branch：`integration/etf-quant-v1`（worktree `D:\quant-worktrees\etf-quant-integration`，全程只读，未动）
- 主 worktree：`D:\quant-trading`（HEAD `bd13d278b25eace66a7eae287307413f930effd9`，全程只读，未动）
- 对照基线 commit：`457b432056ebc894992de330a3b480c062e90bcc`（integration base）
- MiMo 执行分支：`agent/mimo-offline-fixture-gate-audit-v1`
- MiMo worktree：`D:\quant-worktrees\mimo-offline-fixture-audit`（= 594d04c 的独立检出）
- 机器可读矩阵：`docs/etf_quant/offline_test_fixture_gate_matrix_v1.json`
- 本文所有数字均来自本任务独立复现运行，不引用任何先前摘要作为依据

---

## 1. FINAL STATUS

**MIMO_OFFLINE_FIXTURE_AUDIT_COMPLETE** —— 且带正式结论：

> **NO_NEW_OFFLINE_SUITE_FAILURES**（new failures introduced by ETF-Quant = **0**）

| 项 | 值 |
|----|-----|
| baseline tested | `457b432056ebc894992de330a3b480c062e90bcc`（detached 临时 worktree） |
| integration tested | `594d04c76f31c25d0f147fc175f564b487830cd5`（MiMo worktree） |
| exact test command | `python -B -m pytest -q -p no:cacheprovider --tb=no`（取证跑加 `--tb=long -rfE`） |
| working directory | 容器内 `/tmp/run`（worktree 只读挂载后的副本，data-free） |
| environment | `quant-research:py3.12`（image id `578582381893`，与交接文档 sha256 前缀一致），Python 3.12.11，未安装任何依赖 |
| **integration** | passed **575** / failed **8** / errors **44** / skipped **2** / deselected **17**（24.85s，646 collected） |
| **baseline** | passed **445** / failed **8** / errors **44** / skipped **2** / deselected **17**（14.67s，同 646 collected） |
| **new ETF-Quant failures count** | **0**（52 个非通过 node id 与 baseline 逐一相同，`diff` 为空集） |
| TEST_RESULT_REPRODUCTION_MISMATCH | 无 —— 8 failed / 44 errors 已精确复现 |

已知 Codex 摘要（356 passed 组合跑、575/8/44/2/17 全量跑、base 445/8/44/2/17）经本任务独立运行全部核实属实。

## 2. 复现方法（可重复）

两次运行（integration 与 baseline）使用完全相同的方法与环境：

```text
# 在 Windows Git Bash 中（Docker 路径按 AGENTS.md 允许的完整路径形式）：
docker run --rm \
  -v 'D:\quant-worktrees\<worktree>:/src:ro' \
  -e PYTHONDONTWRITEBYTECODE=1 \
  quant-research:py3.12 \
  bash -c "cp -a /src /tmp/run && cd /tmp/run && python -B -m pytest -q -p no:cacheprovider --tb=no"
```

环境要点（如实记录）：

1. **data-free**：worktree 是 git 检出（`data/` 从不入库），容器内 `/tmp/run` 下无任何 data/ 产物。
   8F/44E 在这种"干净检出"环境下产生。
2. **`/tmp/run` 副本执行**（与先前交接文档同法）：源码先 `cp -a` 到容器内再执行，
   测试写入全部落在容器 `/tmp`，`--rm` 后销毁；宿主 worktree 零写入（本任务因此保持 clean）。
3. **无缓存、无字节码**：`PYTHONDONTWRITEBYTECODE=1` + `python -B` + `-p no:cacheprovider`。
4. **git 不可解析**：worktree 的 `.git` 是指向 `D:/quant-trading/.git/worktrees/...` 的指针文件，
   容器内该 Windows 路径不存在，故 subprocess 调 `git` 会失败。
   该条件对 base 与 integration **完全相同**（公平对照），且与先前 copied-source 运行条件一致。
   实测该条件不产生任何额外失败（全部 52 项 traceback 均为数据文件缺失，无 git 报错项）。
5. 框架正常退出输出 `Quit Hikyuu system!`；2 warnings（legacy 已知）。

测试计数勾稽：646 collected = 629 selected（默认 `-m "not integration"`）+ 17 deselected；
629 = 575 + 8 + 44 + 2。base：497 selected = 445 + 8 + 44 + 2，同 17 deselected。

## 3. Baseline 对照与 ETF-Quant 归因

方法 B（独立临时 worktree）：`git worktree add --detach D:\quant-worktrees\mimo-offline-base-457b 457b432...`，
同一命令运行，得 **445 passed / 8 failed / 44 errors / 2 skipped / 17 deselected**。

**归因证据（三重）**：

1. **Node 集合逐一相同**：两次运行的 `FAILED|ERROR` node id 列表（52 行）`diff` 结果为空 →
   `new failures introduced by ETF-Quant = 0`。
2. **集成零触碰 legacy 测试与研究代码**：`git diff --name-status 457b432 594d04c -- tests/ research/ scripts/ src/ strategies/sw_sector_rotation/`
   只有新增（`tests/etf_quant/**`、`strategies/etf_quant/**`），**无任何 M/D**。
   `pytest.ini`（`addopts = -m "not integration"`）逐字节未变；`.gitignore` 仅新增防御性忽略模式（runtime/external/lake/db 等）。
3. **缺失产物从未入库**：两件根因产物在整个 git history 中从未 tracked（见第 8 节），
   任何 commit 下都不存在——与 ETF-Quant 时间线无关。

**结论：8 failed / 44 errors 全部为 baseline-existing 的冻结外部数据依赖问题（PRE_EXISTING），
ETF-Quant 集成新增 130 个 ETF 测试全数通过，未引入任何新失败。**

## 4. 8 failed 根因摘要

8 个 FAILED 均为**调用阶段 FileNotFoundError**（测试体/被测函数在读取冻结数据时抛出，非断言失败、非代码缺陷）：

| # | node id | 首见 traceback | 根因 |
|---|---------|----------------|------|
| 1 | `test_historical_proxy_evidence_audit.py::test_manifest_hash_failure_stops_before_admission` | tests/…:152 `verify_inputs(ROOT)` | `data/raw/etf_evidence/index_evidence_manifest.json` 缺失（monkeypatch 哈希前先读 manifest） |
| 2 | `test_historical_proxy_evidence_audit.py::test_audit_never_calls_network` | tests/…:160 `audit(ROOT)` | 同上（且后续断言需 239 交易日证据包） |
| 3 | `test_sector_development_baseline.py::test_gate_rejects_hash_and_snapshot_mismatch` | tests/…:182 直读 | `data/processed/shenwan/sector_admission.json` 缺失 |
| 4 | `test_sector_development_baseline.py::test_no_network_or_etf_path_in_gate` | tests/…:221 → research/sector_development_baseline.py:224 | 同上（gate 函数先读 admission） |
| 5 | `test_sector_index_baseline_preparation.py::test_real_preparation_never_reads_etf_data` | tests/…:200/:204 直读 | 同上 |
| 6 | `test_sector_research_split.py::test_no_etf_dependency_network_or_docker_process` | tests/…:235/:250 | 同上 |
| 7 | `test_sector_universe_feasibility.py::test_audit_cannot_fit_model_or_compute_performance` | tests/…:173/:191 | 同上 |
| 8 | `test_sector_universe_feasibility.py::test_no_etf_network_or_docker_process_dependency` | tests/…:201 | 同上 |

注意：6/8 是**守卫类测试**（断言"无网络/无 ETF 依赖/不能算绩效"等安全性质）。
它们并非守卫断言失败，而是在到达断言之前先读取冻结数据失败。这决定了修复路径：
补外部产物即可让守卫恢复生效，**不需要也不能改测试**。

## 5. 44 errors 根因摘要

44 个 ERROR 全部是 **fixture setup 阶段 FileNotFoundError**（module 级 fixture 在收集冻结数据时失败，
导致该文件中依赖 fixture 的测试全部 error）。43 + 9 = 52 与总异常计数逐一勾稽（43 次 admission、9 次 manifest）：

| 测试文件 | ERROR 数 | fixture → 首见 traceback | 根因缺失文件 |
|----------|---------|--------------------------|--------------|
| test_historical_proxy_evidence_audit.py | 7 | `actual_audit`(module) :54 → scripts/data/audit_historical_proxy_evidence.py:208 → :77 | `data/raw/etf_evidence/index_evidence_manifest.json` |
| test_sector_development_protocol.py | 18 | module fixture :18 → research/sector_development_protocol.py:267 | `data/processed/shenwan/sector_admission.json` |
| test_sector_universe_feasibility.py | 9 | module fixture :23 → research/sector_universe_feasibility.py:195 | 同上 |
| test_sector_research_split.py | 6 | module fixture :24 → research/sector_research_split.py:216 | 同上 |
| test_sector_index_baseline_preparation.py | 4 | module fixture :22 → research/sector_index_baseline.py:254 | 同上 |

## 6. FAILURE / ERROR → ROOT REQUIREMENT MATRIX（52 行完整表）

字段说明（简写）：
**首见 TB** = 第一个相关 traceback（文件:行）；**baseline** = 457b432 对照状态；**ETF?** = 是否 594d04c 引入；
**tracked/ign** = git 跟踪状态；**sealed** = 是否 sealed artifact；**remed** = 合法修复路径（P 级）；
**gate** = PRV（private integration sync gate：不阻断）/ PUB（public release main gate：阻断）。

| ID | test node id | status | category | baseline | ETF? | missing requirement | expected path/env | producer | tracked/ign | sealed | 首见 TB | remed | gate |
|----|--------------|--------|----------|----------|------|---------------------|-------------------|----------|-------------|--------|---------|-------|------|
| M01 | test_historical_proxy_evidence_audit.py::test_manifest_hash_failure_stops_before_admission | FAILED | A1 | PRE_EXISTING | NO | 证据完整性 manifest + 证据文件包 | data/raw/etf_evidence/index_evidence_manifest.json | 无 tracked producer（人工收集登记） | ignored(/data/), 从未 tracked | NO | tests/…:152 | P3 原样供给冻结证据包 | PRV不阻断/PUB阻断 |
| M02 | test_historical_proxy_evidence_audit.py::test_audit_never_calls_network | FAILED | A1 | PRE_EXISTING | NO | 同上 + 239 交易日覆盖表 | 同上 + data/processed/shenwan_etf_mapping/etf_daily_coverage.csv 等 | 同上 | ignored(/data/), 从未 tracked | NO | tests/…:160 | P3 同上 | PRV不阻断/PUB阻断 |
| M03 | test_historical_proxy_evidence_audit.py::test_publication_inventory_provenance_and_classification | ERROR | A1 | PRE_EXISTING | NO | 同 M01 | data/raw/etf_evidence/index_evidence_manifest.json | 无 tracked producer | ignored(/data/), 从未 tracked | NO | tests/…:54→scripts/…:77 | P3 同上 | PRV不阻断/PUB阻断 |
| M04 | test_historical_proxy_evidence_audit.py::test_1436_is_not_trading_coverage | ERROR | A1 | PRE_EXISTING | NO | 同 M01 | 同上 | 同上 | 同上 | NO | 同 M03 | P3 同上 | PRV不阻断/PUB阻断 |
| M05 | test_historical_proxy_evidence_audit.py::test_point_snapshots_do_not_validate_whole_interval | ERROR | A1 | PRE_EXISTING | NO | 同 M01 | 同上 | 同上 | 同上 | NO | 同 M03 | P3 同上 | PRV不阻断/PUB阻断 |
| M06 | test_historical_proxy_evidence_audit.py::test_relationship_known_at_time_is_not_continuity | ERROR | A1 | PRE_EXISTING | NO | 同 M01 | 同上 | 同上 | 同上 | NO | 同 M03 | P3 同上 | PRV不阻断/PUB阻断 |
| M07 | test_historical_proxy_evidence_audit.py::test_512880_and_159852_purity_do_not_bypass_temporal_gate | ERROR | A1 | PRE_EXISTING | NO | 同 M01 | 同上 | 同上 | 同上 | NO | 同 M03 | P3 同上 | PRV不阻断/PUB阻断 |
| M08 | test_historical_proxy_evidence_audit.py::test_announcement_precedes_close_effectiveness_but_not_full_composition | ERROR | A1 | PRE_EXISTING | NO | 同 M01 | 同上 | 同上 | 同上 | NO | 同 M03 | P3 同上 | PRV不阻断/PUB阻断 |
| M09 | test_historical_proxy_evidence_audit.py::test_no_fixed_proxy_interval_or_formal_execution | ERROR | A1 | PRE_EXISTING | NO | 同 M01 | 同上 | 同上 | 同上 | NO | 同 M03 | P3 同上 | PRV不阻断/PUB阻断 |
| M10 | test_sector_development_baseline.py::test_gate_rejects_hash_and_snapshot_mismatch | FAILED | A2 | PRE_EXISTING | NO | 冻结 sector admission（epoch 数据） | data/processed/shenwan/sector_admission.json | scripts/data/admit_shenwan_sector.py（需冻结 raw） | ignored(/data/), 从未 tracked | NO | tests/…:182 | P3 原样供给（重生成不安全） | PRV不阻断/PUB阻断 |
| M11 | test_sector_development_baseline.py::test_no_network_or_etf_path_in_gate | FAILED | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | tests/…:221→research/…:224 | P3 同上 | PRV不阻断/PUB阻断 |
| M12 | test_sector_development_protocol.py::test_formal_universe_is_fixed_124 | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | tests/…:18→research/…:267 | P3 同上 | PRV不阻断/PUB阻断 |
| M13 | test_sector_development_protocol.py::test_u1_remains_diagnostic | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M12 | P3 同上 | PRV不阻断/PUB阻断 |
| M14 | test_sector_development_protocol.py::test_u2_remains_diagnostic | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M12 | P3 同上 | PRV不阻断/PUB阻断 |
| M15 | test_sector_development_protocol.py::test_policy_c_total_and_deficit | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M12 | P3 同上 | PRV不阻断/PUB阻断 |
| M16 | test_sector_development_protocol.py::test_frozen_ordinal_intervals[development-1-100-100] | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M12 | P3 同上 | PRV不阻断/PUB阻断 |
| M17 | test_sector_development_protocol.py::test_frozen_ordinal_intervals[purge_1-101-220-120] | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M12 | P3 同上 | PRV不阻断/PUB阻断 |
| M18 | test_sector_development_protocol.py::test_frozen_ordinal_intervals[validation-221-280-60] | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M12 | P3 同上 | PRV不阻断/PUB阻断 |
| M19 | test_sector_development_protocol.py::test_frozen_ordinal_intervals[purge_2-281-400-120] | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M12 | P3 同上 | PRV不阻断/PUB阻断 |
| M20 | test_sector_development_protocol.py::test_frozen_ordinal_intervals[final_oos-401-460-60] | ERROR | A2 | PRE_EXISTING | NO | 同 M10（仅协议区间定义，非 OOS 绩效） | 同上 | 同上 | 同上 | NO | 同 M12 | P3 同上 | PRV不阻断/PUB阻断 |
| M21 | test_sector_development_protocol.py::test_current_239_phase_counts_and_seals | ERROR | A2 | PRE_EXISTING | NO | 同 M10（仅 phase 计数/封存状态） | 同上 | 同上 | 同上 | NO | 同 M12 | P3 同上 | PRV不阻断/PUB阻断 |
| M22 | test_sector_development_protocol.py::test_current_exact_dates_are_from_verified_calendar | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M12 | P3 同上 | PRV不阻断/PUB阻断 |
| M23 | test_sector_development_protocol.py::test_split_hash_is_deterministic_and_no_ephemera | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M12 | P3 同上 | PRV不阻断/PUB阻断 |
| M24 | test_sector_development_protocol.py::test_prediction_hash_is_deterministic | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M12 | P3 同上 | PRV不阻断/PUB阻断 |
| M25 | test_sector_development_protocol.py::test_frozen_metric_contract_is_full_and_prediction_only | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M12 | P3 同上 | PRV不阻断/PUB阻断 |
| M26 | test_sector_development_protocol.py::test_synthetic_portfolio_remains_disabled | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M12 | P3 同上 | PRV不阻断/PUB阻断 |
| M27 | test_sector_development_protocol.py::test_no_performance_outputs_or_results | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M12 | P3 同上 | PRV不阻断/PUB阻断 |
| M28 | test_sector_development_protocol.py::test_no_etf_execution_or_network_dependency | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M12 | P3 同上 | PRV不阻断/PUB阻断 |
| M29 | test_sector_development_protocol.py::test_policy_json_can_round_trip_without_generated_ids | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M12 | P3 同上 | PRV不阻断/PUB阻断 |
| M30 | test_sector_index_baseline_preparation.py::test_real_signal_range_is_independent_of_etf_mapping_and_delay | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | tests/…:22→research/…:254 | P3 同上 | PRV不阻断/PUB阻断 |
| M31 | test_sector_index_baseline_preparation.py::test_factor_warmup_training_purge_and_last_label_endpoint | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M30 | P3 同上 | PRV不阻断/PUB阻断 |
| M32 | test_sector_index_baseline_preparation.py::test_actual_801193_gap_and_source_invalid_bars_remain_visible | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M30 | P3 同上 | PRV不阻断/PUB阻断 |
| M33 | test_sector_index_baseline_preparation.py::test_frozen_model_assumptions_and_no_network | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M30 | P3 同上 | PRV不阻断/PUB阻断 |
| M34 | test_sector_index_baseline_preparation.py::test_real_preparation_never_reads_etf_data | FAILED | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | tests/…:200/:204 | P3 同上 | PRV不阻断/PUB阻断 |
| M35 | test_sector_research_split.py::test_combined_baseline_uses_max_horizon | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | tests/…:24→research/…:216 | P3 同上 | PRV不阻断/PUB阻断 |
| M36 | test_sector_research_split.py::test_actual_239_sessions_make_strict_three_way_impossible | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M35 | P3 同上 | PRV不阻断/PUB阻断 |
| M37 | test_sector_research_split.py::test_two_phase_budget_does_not_authorize_dropping_validation | ERROR | A2 | PRE_EXISTING | NO | 同 M10（split 预算协议，非 Validation 绩效） | 同上 | 同上 | 同上 | NO | 同 M35 | P3 同上 | PRV不阻断/PUB阻断 |
| M38 | test_sector_research_split.py::test_oos_remains_unopened_and_unlocked | ERROR | A2 | PRE_EXISTING | NO | 同 M10（断言 OOS 保持封存，不读 OOS） | 同上 | 同上 | 同上 | NO | 同 M35 | P3 同上 | PRV不阻断/PUB阻断 |
| M39 | test_sector_research_split.py::test_missing_rebalance_or_holding_blocks_config_hash | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M35 | P3 同上 | PRV不阻断/PUB阻断 |
| M40 | test_sector_research_split.py::test_actual_training_cutoffs_all_verified | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M35 | P3 同上 | PRV不阻断/PUB阻断 |
| M41 | test_sector_research_split.py::test_no_etf_dependency_network_or_docker_process | FAILED | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | tests/…:235/:250 | P3 同上 | PRV不阻断/PUB阻断 |
| M42 | test_sector_universe_feasibility.py::test_u0_reproduces_formal_239_sessions | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | tests/…:23→research/…:195 | P3 同上 | PRV不阻断/PUB阻断 |
| M43 | test_sector_universe_feasibility.py::test_801193_missing_diagnostics_are_deterministic | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M42 | P3 同上 | PRV不阻断/PUB阻断 |
| M44 | test_sector_universe_feasibility.py::test_other_sectors_have_separate_continuity_bottleneck | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M42 | P3 同上 | PRV不阻断/PUB阻断 |
| M45 | test_sector_universe_feasibility.py::test_u1_is_counterfactual_and_formal_catalog_stays_124 | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M42 | P3 同上 | PRV不阻断/PUB阻断 |
| M46 | test_sector_universe_feasibility.py::test_u1_factor_training_and_label_ranges_are_separate | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M42 | P3 同上 | PRV不阻断/PUB阻断 |
| M47 | test_sector_universe_feasibility.py::test_u2_is_diagnostic_only_with_asof_sector_counts | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M42 | P3 同上 | PRV不阻断/PUB阻断 |
| M48 | test_sector_universe_feasibility.py::test_u1_and_u2_are_mathematically_nonempty_but_no_candidate_policy_fits | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M42 | P3 同上 | PRV不阻断/PUB阻断 |
| M49 | test_sector_universe_feasibility.py::test_u0_additional_raw_sessions_use_verified_120_session_tail | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M42 | P3 同上 | PRV不阻断/PUB阻断 |
| M50 | test_sector_universe_feasibility.py::test_synthetic_semantics_and_oos_remain_unfrozen | ERROR | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | 同 M42 | P3 同上 | PRV不阻断/PUB阻断 |
| M51 | test_sector_universe_feasibility.py::test_audit_cannot_fit_model_or_compute_performance | FAILED | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | tests/…:173/:191 | P3 同上 | PRV不阻断/PUB阻断 |
| M52 | test_sector_universe_feasibility.py::test_no_etf_network_or_docker_process_dependency | FAILED | A2 | PRE_EXISTING | NO | 同 M10 | 同上 | 同上 | 同上 | NO | tests/…:201 | P3 同上 | PRV不阻断/PUB阻断 |

（node id 简写：表中省略 `tests/` 前缀；完整 node id 见 JSON 矩阵 `offline_test_fixture_gate_matrix_v1.json`。）

## 7. 测试分类计数（A–H）

| 类别 | 数量 | 说明 |
|------|-----:|------|
| **A. MISSING_EXTERNAL_DEVELOPMENT_ARTIFACT** | **52** | A1 人工证据包（proxy evidence bundle）9 项；A2 冻结 canonical 准入产物（sector admission epoch 数据）43 项 |
| B. MISSING_LOCAL_TEST_FIXTURE | 0 | 无合成测试 fixture 缺失（缺失物是真实研究数据，不是测试夹具） |
| C. MISSING_RUNTIME_INITIALIZATION | 0 | （该类对应的行情/bundle 未初始化走的是 skip，见第 10 节，不在 52 内） |
| D. SEALED_ARTIFACT_DEPENDENCY | 0 | 52 项无一读取 Validation/Final OOS 绩效；见下方防火墙说明 |
| E. ENVIRONMENT_CONFIGURATION | 0 | 52 项均非 env/配置问题 |
| F. ACTUAL_CODE_FAILURE | 0 | 无代码回归；全部为调用/setup 期 FileNotFoundError |
| G. BASELINE_TEST_DESIGN_ISSUE | 0 | 归类不放此（见下"设计观察"） |
| H. UNKNOWN | 0 | 无未归因项 |

**SEALED 防火墙说明（D=0 的依据）**：52 项中的敏感字样的 node id
（`test_frozen_ordinal_intervals[validation-…]`、`[final_oos-…]`、`test_oos_remains_unopened_and_unlocked`、
`test_current_239_phase_counts_and_seals`）均为**协议区间定义/封存状态断言**，其依赖的
`data/processed/shenwan/sector_admission.json` 与 `data/raw/etf_evidence/*` 是
Development 侧准入/证据元数据（由 `admit_shenwan_sector.py` 数据准入脚本与人工证据收集产生），
不是 Validation result / Final OOS artifact。本任务未打开任何 reports/research 产物、
未读取任何 Validation/OOS 绩效内容。**SEALED_ARTIFACT_DEPENDENCY = 0。**

**设计观察（不改归类、不改测试，仅记录）**：
这 52 项测试直接硬依赖冻结数据、无"数据缺失即 skip"护栏（对比 `tests/framework/test_hikyuu_smoke.py`
的 `DATA_NOT_INITIALIZED` skip 模式），因此在 data-free 检出环境必然 FAIL/ERROR。
这正是它们表现为"红色"而非"跳过"的原因，属 gate 设计议题（第 11 节处理），
根因仍是缺失外部产物（A）。

## 8. 缺失 artifact 清单与来源判定（第 9 节任务）

| artifact | 角色 | 来源判定 | 主 worktree 存在? | ignore | 曾 tracked? |
|----------|------|----------|------------------|--------|-------------|
| `data/raw/etf_evidence/index_evidence_manifest.json` | 证据完整性 manifest（filename→dir/file/bytes/sha256/source_url/retrieved_at） | **C 本应 external + D 本应 gitignored + E 只存在于本地 worktree** | YES（33,535 bytes，Sep 23） | `/data/`（.gitignore:7） | 从未 |
| `data/raw/etf_evidence/{etf_announcements,index_constituents,index_methodology,sw_l2_constituents}/*` | 人工收集的公开证据文件（47 文件在盘） | C+D+E | YES（3+23+14+7 文件） | `/data/` | 从未 |
| `data/processed/shenwan_etf_mapping/four_proxy_historical_evidence.csv` 等 5 个 CSV（temporal_coverage / historical_sources / historical_evidence_calendar / etf_daily_coverage） | 12 行证据/区间/来源表 + 239 交易日覆盖 | B 本应 generated（由证据审计/映射准入管线生成）+D+E | YES | `/data/` | 从未 |
| `data/processed/shenwan/sector_admission.json` | 冻结准入摘要（研究区间 239 交易日、宇宙 124、覆盖率审计、raw/代码指纹、verified calendar 精确日期） | **B 本应 generated + D + E** | YES（16,195 bytes，Sep 23） | `/data/` | 从未 |
| `data/raw/shenwan/**`（StockClassifyUse_stock.xls、manifest.json、sector_catalog/、sector_history/、sector_history_append/） | sector_admission 的上游冻结 raw | C+D+E | YES | `/data/` | 从未 |
| `docs/data/shenwan_historical_proxy_publications.csv` | 12 行公开出版记录 | A 本应 tracked | YES（tracked ✓） | n/a | tracked |

F（从未存在）：不适用——所有缺失文件都存在于开发者机器（主 worktree `D:\quant-trading\data\`），
只是从不入库，干净检出中必然缺失。G（sealed artifact）：不适用（见第 7 节）。

## 9. Fixture producer inventory（第 17 节任务）

**Artifact: `data/processed/shenwan/sector_admission.json`**
- Producer: `scripts/data/admit_shenwan_sector.py`
  （docstring 载明命令：`docker compose exec quant-research python scripts/data/admit_shenwan_sector.py`）
- Inputs: `data/raw/shenwan/`（官方 raw：StockClassifyUse_stock.xls + manifest.json + sector_catalog + sector_history/*.json + sector_history_manifest.json）+ `src/data/providers/shenwan_*.py`（代码指纹入档）
- Outputs: `data/processed/shenwan/`（canonical sector_catalog/ohlcva/classification + 质量报告 + sector_admission.json）
- Mutates canonical data? **YES**（它就是 canonical 准入产物的写入者）
- Touches sealed data? **NO**
- Safe to regenerate? **NO**：① 需要精确冻结 raw 快照（数据是 append-only 演进的，用当前 raw 重跑会得到不同 epoch 值，而测试断言冻结值 239/124/精确日期）；② 重跑会写 canonical 目录（本轮明令禁止的 mutation）。→ 只能**原样供给**，不能重生成。

**Artifact: `data/raw/etf_evidence/index_evidence_manifest.json`**
- Producer: **无 tracked producer**（全库检索无生成脚本）——为人工收集公开证据文件后的登记 manifest
  （被 `scripts/data/audit_historical_proxy_evidence.py` 严格消费：逐文件校验 bytes/sha256/source_url/retrieved_at）
- Inputs: 人工下载的公开证据文件（ETF 公告、指数成分、指数编制方法、申万 L2 成分）
- Mutates canonical data? **NO**（raw 侧完整性登记）
- Touches sealed data? **NO**
- Safe to regenerate? **N/A —— 必须原样恢复**（manifest 的哈希即证据文件的钉子；重造等于伪造证据链）

**Fixture ownership**：两者均为 RESEARCH 侧数据资产（数据管线/证据收集负责人 = 研究数据持有人），
非测试夹具、非框架资产。**fixture source**：前者源自申万官方 raw 下载，后者源自人工收集的公开文档。

## 10. skipped / deselected 核对（第 19–21 节任务）

**Python 2 skipped —— EXPECTED_ENVIRONMENTAL_SKIP（属实）**：
- `tests/framework/test_hikyuu_smoke.py::test_data_availability_is_reported` →
  `pytest.skip("DATA_NOT_INITIALIZED: Hikyuu 行情数据库尚未建立（data/ 为空）")`
  （docstring 明示："这不是框架故障，因此以 skip 标记，不判失败"）
- `tests/framework/test_rqalpha_smoke.py::test_bundle_availability_is_reported` →
  `pytest.skip("RQALPHA_DATA_NOT_INITIALIZED: RQAlpha bundle 尚未下载（~/.rqalpha/bundle 不存在）")`
- 结论：**属于 EXPECTED_ENVIRONMENTAL_SKIP**。不为消 skip 而初始化行情数据（本轮亦禁止）。

**Dashboard 3 skipped —— 与 Codex 所述一致（属实）**：
`dashboard/tests/real-artifacts-integration.test.ts` 采用
`describe.skipIf(!baseUrl || !reportRoot)`，其中 `baseUrl = process.env.RESEARCH_DASHBOARD_REAL_API_BASE_URL`、
`reportRoot = process.env.RESEARCH_REPORT_ROOT`。3 个用例需要**存活的 Research API 服务 + 外部正式
Development 报告根**，离线环境二者均未提供。skip 是测试既有条件分支，不是为掩盖失败新增。保持不动。

**Research API 7 skipped —— 与 Codex 所述一致（属实）**：
`services/research-api/tests/integration.test.ts` 采用 `describe.skipIf(!reportRoot)`，
7 个用例需要外部正式 Iteration-1 Development 产物根（`RESEARCH_REPORT_ROOT`）。同上，保持不动。

**17 deselected —— 来自既有 marker/config，非 ETF-Quant 引入**：
- 来源：`pytest.ini` 的 `addopts = -m "not integration"`（该文件与 base 逐字节未变）。
- marker：`integration`（网络类再叠加 `network`）。
- 清单：`tests/framework/test_akshare_smoke.py` 3 项（integration+network）、
  `tests/integration/test_hikyuu_real_data.py` 10 项（integration）、
  `tests/integration/test_shenwan_etf_local.py` 3 项（integration）、
  `tests/integration/test_shenwan_network.py` 1 项（integration+network）。
- base 457b432 同样 17 deselected → **非 ETF-Quant 新引入过滤**。

## 11. Release gate 分析与两层 gate 建议（第 16 节任务，仅建议不改配置）

按测试性质分层：

| 层 | 内容 | 数量 |
|----|------|-----:|
| A. 每次 integration push 前必须通过 | 当前 data-free 环境下绿色的全部（575 passed；含 ETF 130 + legacy 445）+ 2 环境 skip（按设计） | 575+2 |
| B. 需外部 Development 产物才能运行 | 第 6 节 52 项 + Research API integration 7 skipped + Dashboard real-artifact 3 skipped | 52+10 |
| C. 需 optional runtime 初始化 | 2 个框架 skip（Hikyuu 行情库 / RQAlpha bundle） | 2 |
| D. 不应阻断 private integration backup push | B 层全部（62 项）——它们在干净检出里**根本无法运行**，在 base 上同样红，阻断它们=永远无法同步 | 62 |
| E. 应阻断 public release / main merge | B 层 52 项（全量 offline suite 必须绝对绿色）+ 安全/许可证门（见安全基线文档） | 52+ |

**PRIVATE_INTEGRATION_SYNC_GATE（建议）**：
以"回归差分"为门，而非"绝对绿色"——
1. 全量 offline suite 运行后，**非通过集合必须与已知 52 node 集合完全相同**（不增不减；
   若某 node 消失或新增，都要重新评估）；
2. 全部当前绿色测试保持绿色（passed 数不得下降：575 ≥ 575，ETF 130 全过）；
3. 2 环境 skip / 17 deselected 保持不变；
4. Dashboard/Research API 的 artifact 门控 skip 保持原状，其 unit/typecheck/build 保持通过。
满足即可做 private integration 备份同步（仍不 push，push 需用户指令）。

**PUBLIC_RELEASE_MAIN_GATE（建议）**：
1. **绝对绿色**：offline suite 627 selected 全过（=575+52 恢复后），0 failed 0 errors，
   且必须在**供给了授权冻结数据**的环境复验（不是靠 skip/xfail 掩盖）；
2. Research API integration 7 + Dashboard real-artifact 3 在供给正式 Development 报告根后转绿；
3. 公开 GitHub 安全基线的全部 release gates（secret 扫描、许可证、研究 IP 评审等）；
4. 52 项测试的分类如有变更（例如用户明确指示改分类），必须留下显式决策记录，禁止默认降门槛。

## 12. Remediation plan（第 23 节任务，按优先级）

- **P0 — 真正代码回归：0 项。** 无任何 ACTUAL_CODE_FAILURE；无新回归（NO_NEW_OFFLINE_SUITE_FAILURES）。
- **P1 — 本应存在的 tracked 测试夹具：0 项。** 检索确认没有"小的合成夹具本应入库却缺失"的情形；
  缺失的都是真实冻结研究数据，按数据政策**不得**入库（`/data/` 是刻意忽略）。
- **P2 — 可安全重新生成的 Development 夹具：0 项（1 项有 producer 但不安全）。**
  `sector_admission.json` 有官方 producer（admit_shenwan_sector.py），但重生成会①动 canonical、
  ②产生非冻结 epoch 值 → **不安全**，本轮未运行、也不建议在无授权下运行。
- **P3 — external / runtime-dependent（主修复路径）：**
  1. **原样供给冻结外部数据包**（从授权数据持有人处恢复，非重生成、非伪造）：
     `data/raw/etf_evidence/`（manifest + 4 个证据目录）、
     `data/processed/shenwan_etf_mapping/` 的 5 个 CSV、
     `data/processed/shenwan/sector_admission.json`；
     若未来授权重生成 admission，须同时提供精确冻结的 `data/raw/shenwan/` 快照并显式批准 canonical 写入。
  2. 运行环境须把这些路径置于测试运行根下（本审计的 `/tmp/run` 形态即可）。
  3. 供给后按第 11 节命令复跑，预期 627 passed / 0 failed / 0 errors
     （诚实保留：恢复首个缺失文件后，更深层依赖若再缺，会继续如实报错——本审计不得伪造到无法验证）。
  4. optional runtime 类（Hikyuu 数据库、RQAlpha bundle）按需另行初始化，不为消 skip 而做。
- **P4 — sealed / 故意不可用：0 项。** 无 SEALED_ARTIFACT_DEPENDENCY；无测试依赖 Validation/OOS 绩效产物。

## 13. Codex remediation prerequisites（复绿前置条件清单）

1. 明确授权：由用户/数据持有人提供**精确冻结**的外部数据包（第 12 节 P3 清单），
   并确认其为当时测试通过所用的同一 epoch 快照（不是当前新数据）。
2. 摆放位置：测试运行根下的 `data/...` 相对路径（与测试读取路径一致）。
3. 禁止项重申：不得生成/复制/改名/造哈希/造快照；不得加 skip/xfail；不得改断言或 fixture 期望路径。
4. 复跑命令：`python -B -m pytest -q -p no:cacheprovider --tb=no`（容器内、data 副本环境）。
5. 通过标准：627 selected 全绿 + 2 环境 skip + 17 deselected 不变；
   之后才谈 Research API / Dashboard 的外部报告根供给与转绿。
6. 若不供给数据而要改 52 项测试分类（例如永久跳过）——那是测试语义变更，
   需用户显式指示并记录决策，不在本审计授权内。

## 14. 强制声明

- **MAIN WORKTREE WAS NOT MODIFIED** ✅（`D:\quant-trading` HEAD 仍 `bd13d27…`，clean）
- **ETF-QUANT INTEGRATION WORKTREE WAS NOT MODIFIED** ✅（`D:\quant-worktrees\etf-quant-integration` HEAD 仍 `594d04c…`，clean）
- **NO TEST WAS WEAKENED** ✅
- **NO TEST WAS SKIPPED BY THIS TASK** ✅（2 skipped / Dashboard 3 / API 7 均为既有条件分支，未新增）
- **NO FIXTURE WAS FABRICATED** ✅
- **NO RESEARCH ARTIFACT WAS REGENERATED** ✅（admit_shenwan_sector.py 等 producer 未运行）
- **VALIDATION PERFORMANCE WAS NOT READ** ✅
- **FINAL OOS WAS NOT READ** ✅
- **NO CANONICAL MARKET DATA WAS MODIFIED** ✅
- **NO DOCKER OR DEPENDENCY CHANGE WAS MADE** ✅（仅用现有镜像 `578582381893` 跑测试容器，未改 image/compose/mount/依赖）
- **NO GITHUB PUSH WAS PERFORMED** ✅

附注：baseline 对照用的临时 worktree `D:\quant-worktrees\mimo-offline-base-457b`（detached 457b432）
为本任务按任务书第 7 节 B 方案新建的独立路径，只读使用，未做任何提交；
测试日志存放于 Git 树外 `D:\QuantForge\temp\mimo-offline-audit\`（不入库）。

## 15. NEXT SAFE ACTION

等待用户决策其一：
1. **供给冻结外部数据包**（P3 清单）后授权复跑全量 offline suite，验证 627 全绿 →
   然后再谈 private integration 同步指令；
2. 或就 52 项测试的 gate 分类给出显式方向（维持 A 类外部依赖 / 其它），
   由后续任务按指示处理，本审计不代为变更。
在此之前：不 push、不改测试、不重生成任何研究产物。
