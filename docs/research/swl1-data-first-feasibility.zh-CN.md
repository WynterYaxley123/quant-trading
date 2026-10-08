# SWL1 数据优先可行性

当前决定：C / DATA_SOURCE_NOT_READY。基础设施已用合成事实验证，正式研究仍阻断。
V1、V2 保持 FAILED_VALIDATION，Final OOS 未开启。本任务没有创建 V3。

当前一级收益来自申万有效日期成员表、显式 L2→L1 关系、复权个股价格和
等权重建。分类体系来自官方不能证明收益序列就是官方指数。现有 CNEquity
industry_index 同样是派生序列。未建立获授权的官方 SWL1 指数价格来源，
不等于断言世界上不存在该产品。

CNEquity 固定版本 1650e384a3fd1f67a70144a489acc91432f1df27 的 Apache-2.0
是软件许可，不授予数据权利。SWS 分类/成员、TDX 行情、Sina 公司行动、
Baostock 生命周期和交易日历尚缺本次正式准入要求的数据集授权证据。
现有私人历史研究的用户授权不替代来源许可。合成 fixture 的 MIT 使用范围
仅供工程验收。没有下载新行情、访问凭据或重新计算数值质量。

历史成员是事后整理的 effective-dated reconstruction。
生效时间、公布时间、真实观察时间、本地写入时间、修订时间分别记录；
过去有效不能推出当时已知。Tier A=0、Tier B=0、Tier C=重建保持原样。
公司行动准确性、完整退市/停牌覆盖、个股事实完整性均 NOT_ESTABLISHED。
本地修订计数证明有版本记录，不能单独证明 PIT 或复权正确。
未来交易日历覆盖也不能证明未来价格已经 finalized。

新来源必须在不使用 RankIC、收益或策略表现的条件下准入；许可、身份或
PIT 证明不足即拒绝。旧事实不覆盖，修订保留原版本并隔离相关新证据，
新 source generation 必须重新准入。不得回写旧研究等级或失败状态。

旧执行器物化完整面板的缺口仍为 NOT_CERTIFIED，可认证历史未见交易日为 0。
新系统只能约束未来授权计算，不能追认过去，也没有证据证明人员查看或
未来值影响原训练/Validation。详见冻结的
[访问澄清](../engineering/swl1-forensics-access-clarification.md)。

后续执行 C：先取得数据集使用权与再分发范围，取得当时公布/接收证据，
验证公司行动、退市、停牌和完整成员覆盖；再准入日历、建立正式授权身份。
之后另行规划独立协议 PR，核验外部 GitHub merge/main 谱系，从合并后的真实
交易日开始观察。当前不启动训练。若拟采用 Windows 原生 worker，按 D 先完成
原生进程隔离；当前验证通过的是 Linux Docker 合成容器边界。

[英文审计与来源链接](swl1-data-first-feasibility.md) ·
[来源清单](../../reports/research/swl1_data_first/source-inventory.json) ·
[操作边界](../engineering/prospective-evidence-operations.md)
