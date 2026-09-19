# strategies/ — 策略包集合

本目录存放**自包含的策略包**。每个子目录是一个完整策略，
含自己的代码、配置、测试与文档。

框架级基础设施在顶层 `src/`，两者分离。

## 策略包列表

| 策略 | 状态 | 说明 |
|------|------|------|
| `sw_sector_rotation/` | MIGRATED / **NOT YET BACKTESTED** | SW 行业轮动核心（Legacy 迁移） |

## 调用方式

```python
from strategies.sw_sector_rotation import SWSectorRotationCore
```

## 策略包标准结构

```
strategies/<strategy_name>/
├─ __init__.py          暴露策略入口
├─ README.md            本策略说明 + 状态
├─ config/              策略配置
├─ docs/                规格书、迁移/设计文档
├─ src/                 策略代码（自包含，不依赖顶层 src/）
└─ tests/               策略测试（自包含）
```

## 设计原则

1. **自包含**：策略包不 import 顶层 `src/` 的框架代码；
   顶层 `src/` 也不 import 任何策略包。
2. **互不影响**：一个策略的改动不影响另一个。
3. **不提前抽象**：复用需求出现之前，不做共享层。
   若将来多个策略确实需要同一份逻辑，再提升为框架级共享组件。
4. **测试随包**：策略测试跟策略走，框架 smoke test 留在顶层 `tests/`。

## 新策略开发要求

新策略必须经过：

单元测试 → 历史回测 → 样本外验证 → 仿真 → 用户确认

详见根目录 `AGENTS.md`。

## 预留（尚未接入）

- 聚宽（JoinQuant）策略学习与移植
- 掘金量化 MyQuant：导入插槽见 `src/strategies/myquant/`
