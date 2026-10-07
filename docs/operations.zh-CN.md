# 行业预测运维

当前 SWL2 ETF 产品化 RETIRED，旧 task/runner 及配置仅供历史审计。
本交付不升级 live deployment，不启用 scheduler，不创建业务 event，不改写 QuantForge。

默认 Dashboard 读取 Industry Forecast API。无 runtime 时显示真实空状态和 null 指标；
API 不创建目录、不训练、不冻结、不发布。旧 ETF 页面标明历史产品化与退役。
旧 ETF 写命令 fail closed，合成历史回归仅允许明确隔离的 OS 临时目录。

后续实际启用必须单独授权：使用 clean merged checkout、独立 Docker 镜像、固定外部
CNEquity 与只读事实；私有配置位于 Git 外，writable runtime 为独立 industry-forecast
命名空间。先按[英文运维](operations.md)运行只读 preflight / dry-run。
首个真实 invocation 仅冻结源码、模型和时间，同日不能发布。首个合法信号日严格晚于
merge 与 freeze，且当日事实实际 finalized。漏日不回填。scheduler template 继续 disabled。

重试同一日跳过 Ridge refit，已有预测原字节不改。崩溃仅恢复哈希验证过的 journal；
模型/源码绑定或历史事实变化则阻断。H10/H40/H120 按正式交易 session 到期；全部点
finalized 才评价，不填缺口、不读未来或临时行情，不重新生成旧预测。

参阅[行业合同](industry-forecast.md)、[部署](deployment.md)、[测试](testing.md)、
[工程证据](engineering/swl2-industry-forecast-transition.md)。旧账户和数据保持原位置及哈希，
不迁移。Jupyter 继续要求非空认证与 loopback。没有真实订单或券商路径。

## 行业预测收口运行合同

preflight/dry-run 全程只读，不冻结 namespace。重复调用 NOOP，不重新拟合。成熟评价要求精确 exchange sessions 与完整 finalized 事实；数据/日历缺失保持阻断或 pending。Runner mutex 下按 journal 恢复原始字节，哈希、source、model 不匹配阻断并要求独立审核的 source transition。备份必须包含完整 objects、generations、pointer 与 journal，先在隔离外部目录恢复并校验，再进入另行授权的运行阶段。历史只读检查保留，ETF 状态写入入口已退役。
