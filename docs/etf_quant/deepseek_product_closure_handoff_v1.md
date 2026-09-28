# DeepSeek 产品收口交接说明 v1

**本轮 branch：** `agent/deepseek-etf-quant-product-closure-v1`
**本轮 worktree：** `D:\quant-worktrees\deepseek-etf-quant-product-closure`
**base SHA：** `7e1931627aa3d5061ec78e43c14dec63ed682ee2`
**base 验证：** `git rev-parse HEAD` 精确等于上述 SHA（已确认）

> 说明：本轮未修改 `integration/etf-quant-v1-final`，未修改 main，未 push。以下为中文正文。

---

## 一、本轮实际完成的验证（可复现）

### 1. 工作树基线验证 — PASS
新 worktree 已从 `7e1931627aa3d5061ec78e43c14dec63ed682ee2` 正确创建，`git status` 为 clean。

### 2. L2 / L3 语义冲突 — 已定位根因
集成分支既有产物 `docs/etf_quant/verified_industry_etf_mapping_final_v1.md` 明确记录了冲突：

```
生产 mapping registry 使用 六位 L3 代码
2026-09-24 工程排序 使用 四位 L2 代码
工程 Top5 L2 = 3706, 3703, 4901, 4803, 3701
```

**没有任何基于前缀的自动提升（no prefix-based promotion）** —— 这一点是正确的，
但后果是：**L2 排序结果无法与 L3 mapping registry 对接**，因此 mapping 准入无法进行。
这正是任务 §5.A 所描述的"L2/L3 未统一"，且它是**当前链条的第一块多米诺骨牌**。

**结论：** `ETF_QUANT_INDUSTRY_LEVEL_V1 = SHENWAN_L2` 这一冻结契约在**模型侧已正确**，
但在 **mapping registry 侧尚未对齐**。统一方向必须是 **registry 对齐到 L2**，
绝不能把模型改成 L3（§10 禁止）。

### 3. ETF 行情能力 — 已实测确认真实存在（推翻"源缺失"假设）
使用 pinned CNEquity（commit `1650e384…`，未修改）TDX 协议直取：

```
fetch_daily_bars(['510300.SH'], 2025-04-10, 2026-09-24) -> 358 rows
columns: symbol, trade_date, open, high, low, close, volume, amount
range: 2025-04-10 -> 2026-09-24
is_tdx_servable: 510300.SH=True  512880.SH=True  159915.SZ=True
```

**因此 `ETF_MARKET_DATA_PASS` 的真实阻塞点不是数据源，而是"选择域为空"。**
既有审计 `etf_liquidity_admission_final_v1.md` 记载 manifest 状态为
`NO_VERIFIED_ETF_SCOPE`，`etf_bars.row_count=0` —— 这与本次实测完全一致：
**没有 verified mapping → 没有 ETF 范围 → 导出 0 行**。这是一个**证据缺失**，
不是行情缺失，也不是流动性为零。

### 4. 官方元数据抓取能力 — 可用
已成功抓取基金公司/销售机构官方页面并读取结构化字段，例如 `510300`：

| 字段 | 值 |
|---|---|
| 基金名称 | 沪深300ETF华泰柏瑞 |
| 类型 | 指数型-股票 |
| **跟踪标的** | **沪深300指数** |
| 管理人 | 华泰柏瑞基金 |
| 成立日 | 2012-05-04 |

**这条证据本身就是"禁止名称模糊匹配"的最佳反例**：`510300` 名称含"沪深300"，
类型是"指数型"，但跟踪标的是**宽基指数**，**不是任何申万 L2 行业指数**。
若按名称准入，会把一只宽基 ETF 错误映射到某个行业。

---

## 二、最小不可约 blocker 集合

### BLOCKER 1 — L2/L3 mapping registry 未对齐（可解，Codex 优先）

| 项 | 内容 |
|---|---|
| 根因 | mapping registry 建在六位 L3 代码上，而冻结模型的行业粒度是四位 L2；无任何 L3→L2 已验证的 taxonomy 关系，也未做前缀提升（正确做法） |
| 代码位置 | `docs/etf_quant/verified_industry_etf_mapping_final_v1.md`、`industry_etf_mapping_contract_v1.md`；mapping 契约与 registry 结构 |
| 数据证据 | 工程 Top5 L2 = `3706, 3703, 4901, 4803, 3701`（四位）；registry 寻址六位 L3 |
| 运行时证据 | `etf_bars.row_count=0`，manifest `NO_VERIFIED_ETF_SCOPE` |
| 涉及行业 | 工程 Top5 全部 5 个 L2 行业均无可执行 ETF |
| 涉及 ETF | 0 个已准入 |
| 涉及日期 | 2026-09-24 参考日 |
| 为什么不能绕过 | 前缀猜测会伪造 taxonomy 关系；把模型改成 L3 违反冻结契约 |
| 是否 Codex 可解 | **可以**。需要建立经官方证据支持的 L2 registry，而非复用 L3 |
| 是否需要用户决定 | **否**（工程判断） |

### BLOCKER 2 — 无 verified L2→ETF mapping（可解，依赖 BLOCKER 1）

| 项 | 内容 |
|---|---|
| 根因 | 未完成任何一条具官方证据的 L2 行业→ETF 映射；既有 Shenwan 证据包 0/124 主映射通过，6 个仅为部分证据候选 |
| 代码位置 | 需新建 `strategies/etf_quant/mapping/**` registry |
| 数据证据 | 已准入 mapping = 0；工程 Top5 有 verified ETF = 0/5 |
| 涉及 ETF | 0 |
| 为什么不能绕过 | §20/§21 明令禁止名称模糊匹配，必须官方一手资料 |
| 是否 Codex 可解 | **可以**，且本轮已证明官方元数据抓取**可用** |
| 是否需要用户决定 | **否** |

**重要发现（降低难度）**：本轮已实测确认官方页面可抓取并解析出 `跟踪标的` 字段。
因此这条 blocker 是**可执行的工作量问题，不是能力问题**。

### BLOCKER 3 — ETF 行情与 20 日流动性未执行（可解，依赖 BLOCKER 2）

| 项 | 内容 |
|---|---|
| 根因 | 选择域为空，未发起任何 ETF 行情导出 |
| 数据证据 | `etf_bars.row_count=0`、`trading_status.row_count=0` |
| 运行时证据 | 本轮已证明 `fetch_daily_bars` 对 ETF 返回 358 行含 `amount` |
| 为什么不能绕过 | 不得跳过 mapping 直接抓"猜测的 5 只 ETF"（§28/§29 要求先确认正式流程与范围） |
| 是否 Codex 可解 | **可以** |
| 是否需要用户决定 | **否** |

### BLOCKER 4 — 尚未建立正式 Production Candidate（依赖 1–3）
`production_candidate_snapshot_final_v2.md` 状态为 blocked。Candidate 必须在
mapping + ETF 数据 + liquidity + distinct Top5 全部成立后才能创建（§44）。

### BLOCKER 5 — 时间语义 / PIT 尚未形成正式契约文档（可解，独立）
需要新建 `docs/etf_quant/production_time_semantics_v1.md`，明确区分
`event/effective` · `observed_at` · `available_at` · `processed_at` · `signal_date`。
关键约束（§14）：历史申万成分**可以重建**，但"历史上有效（historically effective）"
不等于"当时可观测（historically observable）"，除非有证据。
因此 `2026-09-24` 只能定性为 `HISTORICAL_ENGINEERING_REFERENCE_DATE`，
**不得**称为 Shadow epoch 起点。

### BLOCKER 6 — `920201.BJ` 的 `list_date` 为 `LIST_DATE_UNVERIFIED`（已隔离，非阻塞）
`list_date = 2026-09-24` 恰好等于 candidate cutoff，且该标的 TDX 返回 0 行历史。
不影响 Source-C（Source-C 不读 `list_date`）。建议保留 flag 并写入 known limitations。

---

## 三、未执行的阶段（诚实声明）

以下阶段**本轮未执行**，不声称任何 PASS：

| 阶段 | 状态 |
|---|---|
| §6–9 L2/L3 全链路审计与代码对齐 | 仅定位根因，**未做代码修改** |
| §16 时间语义文档 | **未创建** |
| §19–26 verified L2→ETF mapping registry | **未创建** |
| §28–32 ETF 行情导出 | **未执行** |
| §33–38 20 日流动性 / distinct Top5 | **未执行** |
| §39–43 softmax + 35% cap 可行性 | **未执行** |
| §44–48 Production Candidate | **未创建** |
| §49–54 Shadow 起点规则 / T+1 契约审计 | **未执行** |
| §63–65 测试 | **未运行**（本轮无代码变更） |

**原因：** 本轮会话上下文预算在中途耗尽。我选择如实记录并把可执行的下一步整理清楚，
而不是伪造未运行阶段的结果。

---

## 四、建议 Codex 的整合顺序（§77）

1. **先做 BLOCKER 1**：确认 `ETF_QUANT_INDUSTRY_LEVEL_V1 = SHENWAN_L2`，
   并把 mapping registry 的寻址基准从六位 L3 改为四位 L2。
   **不要**把模型改成 L3。
2. **再做 BLOCKER 2**：用官方一手资料（基金公司官网 / 交易所 ETF 页面 / 招募说明书 /
   跟踪指数说明）建立 L2→ETF registry。本轮已证明官方页面可抓取且可解析出 `跟踪标的`。
   记录 `evidence_source`、`evidence_type`、`evidence_observed_at`、`verified`。
   注意：**宽基 ETF 必须排除**（`510300` 即为例证）。
3. **然后 BLOCKER 3**：按 registry 范围，经**官方** `staging → batch → settle → compact → curated`
   导出 ETF 行情（**不得**直接写 curated）。20 日完整 + `amount` 全有效才准入。
4. **再做 BLOCKER 5**：时间语义契约文档，冻结 `2026-09-24 = HISTORICAL_ENGINEERING_REFERENCE_DATE`。
5. **最后**：distinct Top5 → softmax + 35% cap → Production Candidate → Shadow readiness 审计。
6. 创建 Candidate 时必须在 manifest 写明 `candidate_created_at > historical_cutoff`（§45）。

**高冲突风险文件：** `services/cnequity-sidecar/bootstrap.py`、
`strategies/etf_quant/data/*`、mapping 相关新目录。

---

## 五、可复现命令（§103）

```powershell
$W = "D:\quant-worktrees\deepseek-etf-quant-product-closure"
# ETF-Quant 定向测试
docker run --rm -v "${W}:/ws" -w /ws --entrypoint python quant-research:py3.12 `
  -m pytest tests/etf_quant/ -q --no-header -p no:cacheprovider

$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
# 验证 ETF 行情能力（应返回 358 行，含 amount）
& "$EXT\venv\Scripts\python.exe" -c @"
import os,sys,datetime as dt
for k in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy'): os.environ.pop(k,None)
sys.path.insert(0, r'$EXT\source\src')
from cnequity.config import load_config
from cnequity.adapters.tdx_protocol.client import fetch_daily_bars
cfg = load_config(r'$EXT\cnequity.production.toml')
f = fetch_daily_bars(['510300.SH'], dt.date(2025,4,10), dt.date(2026,9,24), config=cfg)
print(f.height, f.columns)
"@
```

**不需要**重新下载全市场数据；lake 位于
`D:\QuantForge\external\cnequity-etf-quant-v1\lake-minimal`，为 repo 外运行时路径。

---

## 六、安全与许可

| 项 | 结果 |
|---|---|
| secret 提交 | **0** |
| `.env` 提交 | **0** |
| 运行时 DB 提交 | **0** |
| 真实行情行提交 | **0** |
| 凭据值打印 | **0** |
| `SOURCE_LICENSING_UNRESOLVED` | **未变**，未作法律结论 |

---

## 七、当前状态汇总

```
DEEPSEEK_PRODUCT_CLOSURE_COMPLETE      = FALSE（本轮未完成全阶段）
CODEX_HANDOFF_READY                    = TRUE（交接物已就绪）
L2_PRODUCTION_SEMANTICS_PASS           = BLOCKED（根因已定位，未改代码）
TIME_SEMANTICS_PASS                    = BLOCKED（文档未创建）
VERIFIED_L2_ETF_MAPPING_PASS           = BLOCKED（registry 未建立）
ETF_MARKET_DATA_PASS                   = BLOCKED（选择域为空；源能力已实测存在）
ETF_20D_LIQUIDITY_PASS                 = NOT_REACHED（原因：无候选）
DISTINCT_EXECUTABLE_TOP5_PASS          = NOT_REACHED
PORTFOLIO_FEASIBILITY_PASS             = NOT_REACHED
PRODUCTION_CANDIDATE_PASS              = NOT_REACHED
SHADOW_START_READINESS                 = BLOCKED
原因：L2 mapping registry 未建立，导致 ETF 选择域为空，20 日流动性与 distinct Top5 均无法计算。
ETF_QUANT_READY_FOR_SHADOW             = FALSE
SHADOW_EPOCH_CREATED                   = FALSE
```
