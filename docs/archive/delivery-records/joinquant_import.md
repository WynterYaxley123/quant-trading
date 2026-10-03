# 聚宽（JoinQuant）策略导入流程

> 状态：**规划文档。当前不登录、不配置、不执行。**
> 最后更新：2026-09-19

---

## 1. JoinQuant 当前角色

| 角色 | 状态 |
|------|------|
| 策略学习来源 | 未来 |
| 模拟盘平台 | 未来 |

**当前不要登录或配置。**

---

## 2. 标准流程

```
JoinQuant Strategy
        ↓
保存原始策略
        ↓
ChatGPT 阅读
        ↓
分析逻辑
        ↓
检查未来函数 / 偏差
        ↓
建立 Strategy Specification
        ↓
ChatGPT 改写为 Hikyuu
        ↓
Hikyuu 回测
        ↓
ChatGPT 分析
        ↓
ChatGPT 编写 RQAlpha 验证版
        ↓
RQAlpha 交叉验证
        ↓
生成报告
        ↓
飞书推送
        ↓
Git commit
        ↓
GitHub push（未来）
```

---

## 3. 原始代码保存规则

**必须保留原始版本，ChatGPT 不直接覆盖。**

| 项 | 规则 |
|----|------|
| 存放位置 | 策略包内 `strategies/<strategy_name>/src/original/` |
| 文件命名 | 保留聚宽原策略名，建议加日期前缀：`YYYYMMDD_<name>.py` |
| 修改 | **禁止**修改原始文件内容 |
| 元信息 | 建议同目录加 `YYYYMMDD_<name>.meta.md`，记录来源链接、抓取日期、作者 |

原始文件仅作**参考与溯源**，不在其上直接开发。

---

## 4. 迁移时必须检查的项目

### 未来函数检查

| 检查项 | 说明 |
|--------|------|
| `shift(-n)` | 是否使用未来数据 |
| 当日收盘价决策当日交易 | 是否用收盘价做当日信号 |
| 财务数据发布时点 | 是否使用未公布的财务数据 |
| 指数成分股变更 | 是否使用事后成分股名单 |
| 停牌股处理 | 停牌期间是否被错误交易 |
| 涨跌停处理 | 涨跌停时是否假设能成交 |
| 复权方式 | 前复权 / 后复权是否一致 |

### 平台差异

| 差异项 | 说明 |
|--------|------|
| 数据获取 API | 聚宽 `get_price` vs Hikyuu KQuery vs RQAlpha data bundle |
| 下单接口 | 聚宽 `order_target` vs 各框架交易 API |
| 撮合规则 | 成交价、成交量的假设差异 |
| 手续费模型 | 默认费率与计算方式 |
| 交易日历 | 节假日与停牌处理差异 |
| 复权方式 | 默认前复权 / 后复权的差异 |

---

## 5. 迁移后的要求

迁移完成后**必须重新回测验证**：

- 不得直接沿用聚宽上的原回测结论
- 必须在 Hikyuu 内重新回测
- 必须在 RQAlpha 内独立复现
- 两侧结果若存在显著差异，需分析原因并记入
  Strategy Specification 的 `Known Limitations`

---

## 6. 目录约定

每个策略是**自包含策略包**，位于顶层 `strategies/`：

```
strategies/
└─ <strategy_name>/
   ├─ src/
   │  ├─ original/       ← 原始聚宽代码（只读，不改）
   │  └─ ...             ← 迁移实现（Hikyuu / RQAlpha 共用核心）
   ├─ config/
   ├─ tests/
   └─ docs/
```

框架基础设施在顶层 `src/`，与策略包分离。参见 `strategies/README.md`。

---

## 7. 当前禁止事项

- 登录 JoinQuant
- 配置 JoinQuant 账号
- 运行 JoinQuant 模拟盘
- 下载任何行情数据
- 实际执行迁移

本文件当前**只定义流程**。
