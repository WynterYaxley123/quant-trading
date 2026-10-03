# Unified Research Console acceptance — 2026-10-02

这是本次 PR 内冻结的本地验收快照。最终 branch / merge / main tree SHA 与 GitHub live verification 写入仓外 `unified-console-acceptance-20261002/FINAL_REPORT.md` 和 `delivery.json`，避免提交哈希自引用。旧工程报告保留原始日期和结论。

## A. FINAL VERDICT

本地工程验收 PASS。正常 PowerShell 控制台真实启动 ETF Quant API、既有 Research API 和 Dashboard；两套只读接口均真实连接。无获准 Research 产物时显示 connected / NOT_CONFIGURED，而不是 API DISCONNECTED。ETF-Quant V1 量化源码和冻结输入未修改。工程可用于既有 forward Shadow 观察；不表示投资收益或实盘能力。

## B. GIT / SOURCE STATE

| 项目 | 验收基线 |
| --- | --- |
| repository | WynterYaxley123/quant-trading |
| fetched main | `9fb4190e783ea36ca276d0b1b2ed893b16949998` |
| previous accepted integration | `2744410a91b3829464f6189e1282a23290f5cdd8` |
| integration branch | `integration/unified-research-console-readme-final` |
| candidate checkout | `D:/quant-worktrees/unified-research-console-readme-final` |
| formal runtime branch | `integration/etf-quant-v1-shadow-autonomous-final` |

开发前已检查 worktrees、branches、status、remote、graph、正常 fetch 与 GitHub repo / merged PR。main 与此前接受的 integration tree 相同。所有开发改动位于新的专用 worktree，没有 reset / rebase / force push / 清理其他工作区。

## C. UNIFIED CONSOLE ARCHITECTURE

`Start-EtfQuantConsole.ps1` → 127.0.0.1:3312 ETF API + 127.0.0.1:8787 Research API + 127.0.0.1:5173 Dashboard。每个进程具有独立 cwd、日志和身份记录。浏览器直接访问本地 API，无 Vite proxy；production bundle 的两个 API URL 在构建时确定。

量化执行环境仍是冻结 Docker 镜像，控制台没有 runner、训练、刷新或调度调用。Dashboard 的 READY 表示当前文档实际已服务并渲染；两个 API 的 READY 来自真实响应和 schema，而不是固定成功旗标。

## D. RESEARCH API INTEGRATION

复用 `services/research-api/src/index.ts` 的 Hono / TypeScript 服务，通过既有 Node / tsx 运行。参数、既有环境变量、默认 checkout `reports/research` 依次决定 Research root。缺失可选目录返回空 catalog；仅 ENOENT 可作空状态，损坏 metadata、schema、hash、权限与 realpath 逃逸仍报错。

连接检查不读取研究文件。Research 页面先读取 health / capabilities / status / runs；空 catalog 阻止 run / performance loader。ETF 页面只做 artifact-free Research health 检查。验证集 / Final OOS 仍封存，execution / trading / mutation flags 保持 false。未知路径独立显示恢复入口，不被空产物状态遮盖。

## E. ETF QUANT API

从实际 `ENDPOINTS` 注册表发现并验证全部 16 个 GET 路由：

| 类别 | 路由 |
| --- | --- |
| runtime | status, strategy, models |
| rankings | rankings/10d, /40d, /120d, /fusion |
| account observation | portfolio/summary, /holdings, /nav, trades |
| evidence | mappings, benchmark/csi300, health |
| current readiness | readiness, current |

全部 HTTP 200、合法 JSON、独立 frontend Zod schema PASS。拒绝 POST / PUT / PATCH / DELETE（405）、未知路由（404）、force / bypass / traversal（400）、bad Origin / wrong Host（403）。HEAD / OPTIONS 和批准本地 Origin 成功。响应检查无 secret / stack / NaN / raw state；既有 `one_shot_command` 是有意公开的本地操作说明，不是私有状态泄露。

## F. RESEARCH API LIVE ACCEPTANCE

实际 `ROUTE_PATHS` 注册表的 11 个 GET 路由全部获准 Development HTTP + frontend schema PASS：health、capabilities、research/status、runs、run、candidates、metrics、daily-metrics、predictions、diagnostics、integrity。

默认 8787 的 health / capabilities / status / runs 皆 200；runs 为空，artifactState / phase 为 NOT_CONFIGURED，mutation / execution / tradable false，Validation / Final OOS SEALED。批准的已有 Iteration-1 Development 数据在隔离测试端口 8788 及统一栈 8787 验证；既有两次 Development run 均可正常列出。

全部 ETF / Research live negative 检查共 36 项；写方法 405，非法或不存在 ID / route 404，unsupported / duplicate / force / bypass query 400，sealed path / query 和 raw traversal 403。Research bad Origin 不返回 Access-Control-Allow-Origin，浏览器不可跨域读取。29 个明确 Development 文件的 SHA256 前后相同。没有读取封存性能。

## G. DASHBOARD / BROWSER ACCEPTANCE

使用真实 Codex in-app browser，等待页面模块和 API 数据完成：

| 范围 | 结果 |
| --- | --- |
| ETF 9 routes：overview, readiness, portfolio, rankings, factors, mappings, trades, benchmarks, health | PASS |
| Research 6 routes：/, candidates, development, sectors, diagnostics, integrity，批准 Development | PASS |
| Research 6 routes，默认无产物 | PASS / connected empty / SEALED |
| production build，全部 15 routes | PASS |
| 导航菜单 → Development、D2 / H40 筛选、带查询 URL 刷新 | PASS |
| 未知路径恢复入口 | PASS |

三个服务状态在各页面可见，健康情况下没有 API DISCONNECTED。空状态没有伪造指标；零 Epoch 的持仓 / 流水 / NAV 没有历史填充。Console errors=0，warnings=0，unexpected browser network failures=0（本次浏览器观察范围：真实响应、页面加载和 dev logs；不是外部网络流量取证）。没有 CORS 失败。

截图、AX 检查与 console logs 留在仓外，未提交 UI 临时文件、研究数值或运行 payload。

## H. README QUALITY REVIEW

README 已按正式主页组织：Overview、capabilities、architecture Mermaid、冻结策略、Research、Shadow、safety、components、quick start、workflow、testing、structure、data/runtime、security、limitations、docs、license/data rights。

明确区分 Research 的 U0_FIXED_124 与 ETF 的 107 admitted industries、非严格历史 classification PIT、Shadow 与正式控制台、唯读 UI 与独立 one-shot。移除 PR / 修改时间线口吻、临时 PID、永久数据截止日、固定测试计数和虚假 badge。

结构参考了 [Qlib](https://github.com/microsoft/qlib)、[LEAN](https://github.com/QuantConnect/Lean)、[NautilusTrader](https://github.com/nautechsystems/nautilus_trader) 的项目概览、架构、运行与文档组织；没有复制其文案、品牌或图。未知路径使用 Router 的标准 splat，依据 [TanStack routing concepts](https://tanstack.com/router/latest/docs/routing/routing-concepts)。

## I. FRONTEND TEST / TYPECHECK / LINT / BUILD

| 检查 | 实际结果 |
| --- | --- |
| complete Vitest，含真实 Development HTTP integration | 122 passed / 0 skipped / 0 failed |
| test process | exit 0；55.15 s wall time；Vitest 54.10 s |
| TypeScript | PASS / exit 0 |
| ESLint | PASS / exit 0 |
| production build | PASS / exit 0 |

没有升级依赖、忽略类型错误或新增 lint suppression。jsdom 测试日志包含既有 Window.scrollTo 未实现提示；真实浏览器错误 / 警告为零。新行为覆盖健康、断连、degraded、empty、retry、ETF/Research 数据边界和未知路由。第一次名称断言仍使用旧标题；已更新并完整重验。

## J. FULL ETF TEST RESULTS

本次重新执行完整套件，未复用旧 610/1 证书：

`python -B -m pytest -q -p no:cacheprovider tests/etf_quant tests/test_etf_evidence_diagnostics.py tests/test_etf_proxy_mapping_policy.py`

| 项目 | 实际结果 |
| --- | --- |
| passed / skipped / failed | 612 / 1 / 0 |
| exit | 0 |
| pytest duration | 606.16 s |
| total Docker command wall time | 610.15 s |
| image | `sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5` |
| fixture | `ETF_QUANT_EXTERNAL_RUNTIME_ROOT=/external-runtime` |
| isolation | network none；源码和既有 runtime 挂载 readonly；无 bytecode / pytest cache 写入 |

唯一 skip 是 Docker 内未安装宿主 sidecar 的 `cnequity` 模块，对应 pinned upstream TLS import 检查。没有为消除 skip 安装或改变冻结环境；现有 sidecar 源码 TLS 禁用扫描测试仍通过。

Python source integrity：197 个 Python 文件内存 compile、47 JSON、8 YAML、1 TOML parse，10 个关键策略模块 import PASS。全部使用冻结 Docker、network none、readonly 源码，无数据抓取和 Shadow 写入。

## K. RESEARCH API TEST RESULTS

22 unit + 7 明确批准 Development integration = 29 passed / 0 skipped / 0 failed，exit 0；Vitest 7.75 s。TypeScript 和 build PASS / exit 0。新增 absence / corrupt / loopback / force-bypass 拒绝覆盖；既有 sealed、containment、哈希与逐值对账继续通过。API / native security Node 测试：77 passed / 0 skipped / 0 failed，3.074 s。

## L. SECURITY / SECRET / DATA AUDIT

运行既有 `services/etf-quant-runner/security-audit.mjs`。完整 tracked / 新文件 / reachable Git history 扫描 PASS，无 secret candidates、forbidden raw/runtime paths、sealed performance 路径、500 KB 以上误入大文件、embedded remote credentials、环境 / research firewall 改动。扫描器是仓库内只读模式/路径审计，不宣称第三方认证。

临时脚本、浏览器截图、测试日志、receipt 和实际产物都留在新仓外审计目录。未提交 .env、data、runtime DB、bars、account payload、node_modules、.venv、dist 或 cache。发布前再次运行本工具，并将最终计数和输出哈希记录在外部交付证书。

## M. BROKER / REAL-ORDER NEGATIVE PROOF

仓库源码搜索 QMT / MiniQMT / xtquant / easytrader / PTrade / submit_order / place_order / cancel_order / real account / live cash / live positions：生产可达 SDK 或提交函数匹配为 0。

`domain` / `runtime` 强制 simulation_only、broker_enabled=false、real_order_path=false；API 和前端 schema 保留 false literal；两个 API 无执行/账户写路由。Simulation lot accounting 是内部记账。结论：REAL_ORDER_PATH_PROVEN_ABSENT=TRUE，BROKER_ENABLED=FALSE。

## N. SHADOW / PIT INTEGRITY

正式 Shadow namespace 全部 6 个文件在所有控制台 / HTTP / 浏览器 / holiday command 验收前后大小和 SHA256 一致。latest 正式成功指针仍不存在：Epoch / Signal / Intent / Fill = 0 / 0 / 0 / 0，没有 NAV 历史生成。

| 上海日历验收快照 | 实际值 |
| --- | --- |
| current date | 2026-10-02，非交易日 |
| latest eligible finalized | 2026-09-30 |
| next eligible | 2026-10-08 |
| model H10 / H40 / H120 | PASS |
| runtime | ARMED_FOR_NEXT_ELIGIBLE_T |
| one-shot engineering smoke | EXACTLY_ONCE_HOLIDAY_NO_REFRESH |
| one-shot result | READY_NO_SIGNAL；refresh_attempted=false |

先检查官方 calendar、export manifest hash、eligible target、finalized cutoff、无 formal latest、正式分支 clean committed，再按 README 的原官方命令执行恰好一次。没有 force time / cutoff 或重试循环，只有外部 control observation receipt 正常更新，未刷新行情或进入量化 cycle。

Candidate / PIT / Strict registry 文件与基线相同；CNEquity source checkout clean，HEAD 仍 `1650e384a3fd1f67a70144a489acc91432f1df27`。没有创建 historical epoch / signal / intent / fill 或 retroactive intent。

## O. PROCESS / PORT / RESTART BEHAVIOR

真实默认端口清空（仅停止已验证 task-owned 进程）→ 单一默认命令启动三个 READY → 第二次命令三个 REUSED。PID/start time/command/executable/listener/配置 fingerprint 验证，127.0.0.1 是实际 listener 地址。

隔离 launcher tests：3 passed / 0 skipped / 0 failed，28.200 s。覆盖异 cwd、调用方环境恢复、重复启动 PID 保持、受控 unrelated listener 被拒绝且保持运行、损坏 Research metadata 导致 readiness 失败并只回滚本次新建服务。夹具清理也重新校验 PID/start time/command/executable。有限超时、回退日志和明确报错均验证。没有管理员、系统网络变更或任意进程终止。

正式运行 checkout 只在 PR 已合并且接受的 tree 通过比对后，使用既有分支 fast-forward 部署。该分支 guard 不改名，不创建 tag / release，其他 worktrees 不修改。

## P. DOCUMENTATION CONSISTENCY

稳定文档统一解释 3312 / 8787 / 5173、两个只读 API、Research optional root / empty、loopback、Vite URL、预览、Shadow 边界。更新 Dashboard 9 路由索引；基础环境架构 / 工作流增加日期与当前产品索引，历史正文和报告保留。

README 所有相对链接、内部 heading anchors、组件路径核验；主启动命令（clean/reuse）、官方 holiday one-shot、列出的测试命令均实际运行。Docker 测试使用完整已有 CLI 路径，兼容当前旧 PATH 快照。没有文档中的独立 Research 手工启动变成正常必需步骤。

## Q. LICENSE / DATA-RIGHTS STATUS

repo 没有统一 owner LICENSE grant，未新增虚构许可证或 license badge。第三方 notices 保留。OWNER_LICENSE_DECISION=REVIEW_REQUIRED，SOURCE_DATA_REDISTRIBUTION_CLEARANCE=REVIEW_REQUIRED。这是既有法律/数据权利边界，不阻断已授权的内部工程整合；不作法律授权推断。

## R. MODIFICATIONS MADE

- robust 三服务 PowerShell launcher 与真实进程验收测试；
- 既有 Research API optional catalog、NOT_CONFIGURED DTO、loopback enforcement、严格 query；
- 全局真实服务状态、Research empty / disconnected / degraded / retry、ETF artifact 隔离；
- 统一品牌、preview loopback、标准 unknown-route recovery 与 regression tests；
- 正式项目 README、稳定文档与本次验收记录。

没有 quantitative strategy、production ETF API 实现、runner、sidecar、Candidate、PIT/Strict、数据管线、F1、封存规则或依赖 pin 改动。

## S. FINAL GIT STATUS

本地验收源与最终提交内容须 `git diff --check` PASS；按 console / Dashboard / docs / acceptance 的职责形成逻辑提交。发布前 tracked 工作区 clean。生成物与外部运行数据继续 ignored / 仓外。最终 branch SHA 和 merged main tree 在最终外部证书中记录。

## T. GITHUB PR / MERGE

采用普通 dedicated-branch push → standard PR into main → 审阅实际 changed files / live head / repository policy → expected-head merge → 再 fetch。没有 force push、bypass 或未经授权的 Release。

本文件是合并前的不可自引用验收证据，不在未完成时宣称 MERGED。最终 PR number、merge SHA、main tree=accepted PR tree、正式 runtime fast-forward clean 和 GitHub live state，以同次交付的外部 FINAL_REPORT / delivery.json 为准。

## U. FINAL STATUS FLAGS

以下是已实际完成的本地验收；GitHub 三项由交付后实时核验填写，不从静态文档推断。

~~~text
UNIFIED_CONSOLE=PASS
DASHBOARD_STARTUP=PASS
ETF_QUANT_API_STARTUP=PASS
ETF_QUANT_API_LIVE_ACCEPTANCE=PASS
RESEARCH_API_STARTUP=PASS
RESEARCH_API_LIVE_ACCEPTANCE=PASS
RESEARCH_API_CONNECTED_IN_NORMAL_CONSOLE=TRUE
RESEARCH_API_LOOPBACK_ONLY=TRUE
ETF_API_LOOPBACK_ONLY=TRUE
DASHBOARD_LOOPBACK_ONLY=TRUE
NORMAL_RESEARCH_PAGE_API_DISCONNECTED=FALSE
RESEARCH_EMPTY_STATE=PASS
RESEARCH_SEALED_DATA_FIREWALL=PASS
RESEARCH_API_READ_ONLY=TRUE
DASHBOARD_BROWSER_ALL_ROUTES=PASS
BROWSER_CONSOLE_ERRORS=0
BROWSER_CONSOLE_WARNINGS=0
UNEXPECTED_BROWSER_NETWORK_FAILURES=0
README_REWRITTEN=PASS
README_PROJECT_INTRODUCTION=PASS
README_ARCHITECTURE=PASS
README_QUICK_START=PASS
README_LINKS=PASS
README_COMMANDS_TESTED=PASS
README_CHANGELOG_STYLE_REMOVED=TRUE
FRONTEND_TESTS=PASS
FRONTEND_TYPECHECK=PASS
FRONTEND_LINT=PASS
FRONTEND_BUILD=PASS
RESEARCH_API_TESTS=PASS
ETF_FULL_TEST_SUITE=PASS
SECRET_AUDIT=PASS
RAW_RUNTIME_DATA_GIT_AUDIT=PASS
REAL_ORDER_PATH=FALSE
REAL_ORDER_PATH_PROVEN_ABSENT=TRUE
BROKER_ENABLED=FALSE
FROZEN_STRATEGY_CHANGED=FALSE
CN_EQUITY_PIN_CHANGED=FALSE
SEALED_VALIDATION_READ=FALSE
FINAL_OOS_READ=FALSE
HISTORICAL_SHADOW_BACKFILL=FALSE
RETROACTIVE_INTENT=FALSE
CONSOLE_START_CREATED_EPOCH=FALSE
CONSOLE_START_CREATED_SIGNAL=FALSE
CONSOLE_START_CREATED_INTENT=FALSE
CONSOLE_START_CREATED_FILL=FALSE
PRODUCTION_USABLE=TRUE
V1_STRATEGY_SEMANTICS_UNCHANGED=TRUE
OWNER_LICENSE_DECISION=REVIEW_REQUIRED
SOURCE_DATA_REDISTRIBUTION_CLEARANCE=REVIEW_REQUIRED
REMAINING_ENGINEERING_BLOCKERS=NONE
~~~
