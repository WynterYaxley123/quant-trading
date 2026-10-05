# scripts/automation

报告 schema 模板目录。

## 当前内容

```
report_schema/
├─ metadata.json     回测元信息模板
├─ metrics.json      核心指标模板
└─ comparison.json   双框架交叉验证模板
```

当前**仅有 schema 模板**，不含任何策略数据或运行脚本。

## 用途

定义 `reports/backtests/<strategy>/<run_id>/` 下的标准文件结构。
详见 `docs/report_schema.md`。

## 规则

1. 模板中所有值制空或为 `null`，**禁止填入虚构数据**
2. 修改遵循仓库工程规则；没有常驻代理所有权
3. ETF-Quant 正式运行使用现有 `services/etf-quant-runner/one_shot.py`，调度与重试见 [运行说明](../../docs/operations.md)
4. **不得**在此目录实现策略或因子逻辑

## 未来规划

- 回测运行编排
- 报告自动生成
- 飞书通知触发
- 定时任务调度
