# 运维手册

[English](operations.md) | [简体中文](operations.zh-CN.md)

## 架构与所有权

Git 是 `SOURCE_OF_TRUTH_REPOSITORY`，保存源码、测试、模板、依赖 pin、部署逻辑和公共知识。
`LOCAL_DEPLOYMENT_ROOT` 保存本机事实数据、账户、控制状态、私有证据、日志和真实配置。
维护者参考根目录 `D:\QuantForge` 只是实现细节，公共用户可以自行选择外部路径。
建立环境和目录布局见[部署指南](deployment.md)。

Operational checkout 是 canonical Git 源码的部署副本，不是第二个源码权威。
保持该 checkout 干净并明确所有权。外部 provider 固定、只读挂载，数据和账户/control 根独立。
不能因为源码部署在本地根中，就把整个部署根提交到 Git。

## Canonical runner 与每日生命周期

唯一正式入口是 `services/etf-quant-runner/one_shot.py`。
兼容单个外部 `--config`；双版本调用重复传入一次 V1 和一次 V2 配置。
调用前验证版本不同、解析后账户/control 路径互不覆盖；按顺序分别执行，一个版本被阻断仍保留另一版本结果。
任一完整性阻断的 aggregate 返回码为 2。具体配置和 mount 见[runner 文档](../services/etf-quant-runner/README.md)。

宿主机解释器只执行标准库 transport；模型、分配、PIT 准入和记账在 Docker 中执行。
正式调用使用干净已提交且匹配 fetched `origin/main` 的 checkout。不能为了通过 gate 重置他人的工作。
官方交易日最终收盘后，验证事实和发布证据，只创建冻结之后真正当前的信号。
已提交的同日信号在 provider 刷新和模型执行前返回，不重复产生事件。

时序为 T 最终收盘 → 当前合法信号 → 未来真实 T+1 原始开盘 → 延后模拟记账。
延后处理不改变真实证据时点，不能制造历史 signal、intent 或 fill。
休市可以保持准备/等待状态，不创建业务记录。下一个合法日期来自官方日历与 release 可用时间，
不能把仍在等待的当前日期悄悄跳过。

## Scheduler

Windows 调度由 `scripts/Install-ForwardShadowTask.ps1` 管理，任务调用标准库
`services/etf-quant-runner/scheduled_wake.py`。
使用永久、独占、干净的 operational checkout，不能使用 PR 或研究工作区。
将[scheduler 模板](../services/etf-quant-runner/scheduler.config.example.json)复制到 Git 外，
填写显式 Python/Git、checkout、双版本配置和既有外部日志目录。
先执行英文手册中的 [dry-run](operations.md#scheduler)：只验证路径和已合并源码身份，不更新 checkout，不调用 one-shot。
安装与启用是独立的部署操作，工程验证不安装、启用或唤醒正式任务。

任务使用当前用户 interactive token，不存密码、不要求管理员权限。
上海时间 15:05 开始，每 15 分钟重试，持续七小时，转换为宿主机本地时间；登录五分钟后也唤醒。
只允许运行一个实例，补做错过的调度并对失败重试三次。
登录用户需要可用的 Docker Desktop。睡眠、退出登录或服务不可用不能保证信号，错过时点不授权回填。

Wake 只对独占干净 checkout 做 fetch/fast-forward，dirty/divergent 状态会阻断且不丢弃工作。
UTC receipt 包含 commit、决策、事实日期、状态身份和可用业务计数，不含价格、持仓或 child stderr。
Scheduler CLI 的 dry-run 仍会在配置的外部日志根写入诊断 receipt，但不创建 signal、intent、fill 或账户 generation。
WAIT/NOOP 返回 0；Git、provider 子进程、日志和 runner blocker 返回 3 供任务重试。

## 决策与错过 T+1

WAIT 表示事实/日历尚未成熟；SIGNAL 发布当前合法收盘决策；FILL 使用验证后的真实 T+1 开盘进行模拟记账；
NOOP 保持已处理日期。完整性 blocker 不能当作 WAIT 忽略。

`ABANDONED_MISSED_T1` 是终止的错过意图，必须保留原记录和证据。
后续合法 epoch 可以继续，但不能猜开盘价、改意图日期、删除终止记录或重播历史以取得想要的结果。

## 幂等、锁与崩溃恢复

Host transport 锁串行化调用；账户发布和恢复都在 Docker Linux 锁域。
Windows 字节锁不能与挂载目录中的 Linux file lock 协调。账户 mutex 在进程结束时释放。
发布不可变 generation 前写入的 journal，使恢复只完成已验证哈希的原 generation/latest pointer，保留原时间戳。
未完整 stage 不发布；损坏 journal、未知 legacy lock 需要诊断。
信号、intent、fill、NAV 在发布前后崩溃场景下仍保持幂等。

PID 可能重用，不能只据 PID 或锁文件年龄停止进程/删锁。
先核对 executable、启动时间、checkout、账户和所有权，只暂停自己的 writer。
所有权不明时保留现场；通过 canonical journal 恢复，不直接修改 ledger。

## 服务、API 与 Dashboard

`scripts/Start-EtfQuantConsole.ps1` 只启动观测服务，不刷新事实、不初始化 epoch、不调用 runner。
通过 Git 外的 `ETF_QUANT_CONSOLE_CONFIG` 或 `-Config` 提供路径。
联合控制台显式提供 V2 runtime/control 两个根，所有账户/control 根解析后独立。
Research workspace 通过 `RESEARCH_WORKSPACE_CONFIG` 或外部 control 的配置提供。
没有获准 Development artifact 时诚实展示空状态，不能挂载封存证据填充页面。

ETF API 和 Research API 信任边界不同。检查 loopback 服务、账户版本、as-of 日期、完整性和等待状态。
进程可达不等于账户通过准入，健康检查不能调用正式 runner。
较新观测阻断时保留最后一个验证后的账户。
Origins 必须为精确允许来源，不能含通配、凭证、路径、query 或 fragment。
Jupyter token 使用环境或忽略的本地 `.env`；缺少 token 时 fail closed，不能提交到 Git。

## 数据延迟、网络与 provider

Provider 不可用或证据缺失时保留 WAIT/BLOCKED receipt，不猜价格、不手填事实、不用无 PIT 证据的缓存代替。
核对固定 CNEquity pin、source/export 配置、发布证据与来源诊断；不输出受限市场行。
禁止弱化 TLS、静默升级 SDK，事实采集与 network-disabled 数值执行分开。

Windows 绑定错误可能来自 HNS 保留端口而非进程占用。
使用[只读端口诊断](../scripts/operations/host-ports.mjs)同时检查 IPv4/IPv6，
再以[Compose 模板](../config/deployment/compose.host-ports.example.yml)参数化 loopback host publication。
内部端口、镜像和 mount 保持原契约。常规恢复不修改全局 DNS、地区、语言、防火墙，也不安装远程控制软件。

## 完整性、日志与备份

[部署边界检查](../scripts/operations/verify_deployment.py)验证根目录和外部 pin，不读取市场或 ledger payload。
通过边界检查不等于完整数据/readiness 证书，账户仍使用既有 generation/certificate 验证。
私有 receipt、stdout/stderr、provider cache 和证据留在部署根；公开诊断只给身份与计数，不泄露 token、路径或市场值。
按本地策略保留日志，不删除唯一失败/恢复证据。

暂停独占 writer 后备份一致的账户/control generation、配置与源码/镜像/provider pin，或备份验证后的不可变 generation。
备份是私有数据，源码 MIT 不授予数据再分发权。恢复前验证哈希和账户身份，保留失败现场与原时间戳。
恢复是明确的运维动作，不能用工程 fixture 替换真实账户。

## 部署更新、回滚与安全重启

先 review、CI、merge，再考虑部署切换。保存配置与状态备份，核对所有权、dirty 状态、源码 transition 和有效 Compose 配置。
只 fast-forward 干净独占 checkout，不 reset/stash 用户工作。源码更新不授权镜像/provider 升级或模型改变。
新路径在 merged main 验证完成且 live 引用切换前，不删除旧脚本或配置；live operations clone 可以继续保留。

Console 重启先核对 process receipt、executable、启动时间和 checkout，只停止有所有权证据的进程。
用相同外部配置启动观测 launcher，再检查 health，不杀任意端口占用者、不用正式 cycle 验证重启。
Writer 恢复先保留现场，沿 canonical 恢复协议处理。回滚需要 coherent backup 和合法 certificate/generation 链，
不能因回滚源码而授权历史 fill 或 ledger 编辑。卸载只处理确认归本部署所有的任务/服务，保留数据、账户与备份。

## 故障排查与禁止操作

| 症状 | 安全的首项检查 |
| --- | --- |
| 缺目录/provider 不匹配 | 只读边界检查与 exact pin |
| Windows bind 失败 | HNS 保留区间、TCP 端口和有效 loopback override |
| 事实或日历等待 | 发布时点、官方交易日和成熟 gate |
| dirty/divergent checkout | 保留修改，检查 fetch/fast-forward 原因 |
| 陈旧 receipt/疑似锁 | 进程所有权与验证后的 generation/journal |
| Research API 空 | 获准 Development 根与配置，不触碰封存证据 |
| Runtime 完整性失败 | 源码证书、哈希和发布 generation 链 |

禁止 retroactive fill、手工编辑 ledger、绕过完整性 gate、从历史 fixture 替换账户、
通过 production runner 搜索模型、提交 secret/private evidence、启用 real broker 或真实 order。
Readiness 与 API 可达不证明盈利。恢复必须保留 V1/V2 规格、映射政策、consumed OOS 身份与命名空间隔离。
