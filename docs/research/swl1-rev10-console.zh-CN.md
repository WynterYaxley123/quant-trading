# REV10 中文研究控制台

SWL1 REV10 Short-V1 已实现为固定规则：过去 10 个每日行业收益的负算术均值，
含信号日 T 收盘；在冻结的 30 个行业内中心化，按原始评分降序、代码升序处理并列。
无需训练，保留 PR36 的递归首个有限收益种子排除和 6/11 行 warmup。

已有历史指标和六张图直接来自经哈希核验的
[PR36 研究](swl1-short-horizon-exploration.zh-CN.md)，标记为
`EXPLORATORY_POST_HOC`。数据截至 2026-09-29，排名属于
`HISTORICAL_REPLAY / RESEARCH_REPLAY_ONLY`，不代表今日行情。
H10 是主要评价周期，H5 是次要周期。等权零评分的 RankIC 未定义。
原始 Top5–Bottom5 收益差不代表可执行净利润。

## 打开已交付的本地成果

在包含本次合并代码的安全 checkout 中运行：

```powershell
& .\scripts\Show-SWL1-REV10.ps1
```

默认私有成果目录为 `D:\QuantForge\research\swl1-rev10-delivery`。
控制台路径为 `/industry-forecast/swl1-rev10`；启动器输出经过健康检查的实际 URL。
它使用已构建的现有 Dashboard，在 loopback 启动或复用身份、源码及工件哈希
完全一致的只读服务；未知端口服务保留，冲突时改用空闲端口。
`-NoBrowser` 可执行同样验收而不打开系统浏览器。

离线入口为私有目录下 `review\index.html`，双击即可打开，无需 API 或 CDN。
包含完整历史排名时，所有数值仅存在于本地私有成果包。
`review\delivery-manifest.json` 记录 HTML、六张图、公开研究来源及排名 manifest 哈希。
Web 启动失败时，仅在离线成果包校验通过后提供离线回退。

公开 clone 不包含真实逐行业评分、私有输入或构建输出；缺少私有排名时 API
返回明确 unavailable，历史聚合报告仍可查看。生成私有预览只能在独立 Docker
中对原 PR36 物理截断视图执行，不可改用母面板、更新数据或读取新日期。
交付者先构建 Dashboard 并用 `scripts/engineering/rev10-bundle.mjs` 绑定源码，
再将该构建复制到私有 `web` 目录；日常启动器不会安装依赖或运行量化研究。

## 页面与证据

页面可切换 Top5、Bottom5、全部 30 行业及六张原始图；显示原始/相对评分、
10 日平均收益、名称验证、日期、截面完整性和 source generation。
排名缺失或哈希/结构损坏时拒绝显示排名；API 断开时显示错误和离线入口。
图表及证据通过服务器闭合资源列表读取，接口不接受任意路径、日期或写请求。

[模型规格](../../config/research/swl1-rev10-short-v1.json)、
[预注册草案](swl1-rev10-preregistration-draft.zh-CN.md)、
[工程验收](../engineering/swl1-rev10-acceptance.md)。

模型实现、历史探索和草案准备已完成，正式预注册未激活。
真实来源准入为 `DATA_SOURCE_NOT_READY`，生产签名身份未建立，统计设计待完成，
真实前瞻观测为 0，独立 Validation 未开始。SWL1 Ridge V1/V2 保持失败，
Final OOS 未打开，旧历史访问隔离 `NOT_CERTIFIED`。
未来正式验证复用既有准入、authority、activation、ledger 和精确 H5/H10 成熟门控；
还需来源权利、PIT/质量、正式身份、独立统计设计及单独正式授权。
