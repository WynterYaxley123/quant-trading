# Hikyuu 2.8.2 数据能力调查报告

- 调查日期：2026-09-19
- 调查环境：Docker 容器 `quant-research`（Linux x64，Python 3.12.9，Hikyuu 2.8.2 RELEASE）
- 调查方式：**全部结论来自容器内实测**（`dir()` / `__doc__` / 源码 `grep` / 网络连通性测试），
  未依据记忆推断 API。凡未实测的项均标注「未实测」。

---

## 一、结论摘要

Hikyuu 2.8.2 在**无 GUI 的 Linux Docker 环境**中可以完成真实行情数据初始化，
推荐路径为：

```
pytdx 协议（网络）→ hikyuu.data.pytdx_to_h5 导入函数 → HDF5（K线）+ SQLite（基础信息）
```

关键事实：

1. 容器内可连通 pytdx 行情服务器（实测 180.101.48.170:7709、123.125.108.90:7709 可连，
   119.147.212.81:7709 超时），并成功取到真实行情（510300 沪深300ETF、159915 创业板ETF）。
2. `hikyuu.data.pytdx_to_h5` 提供**函数级**导入 API，无需 GUI、无需本地通达信客户端。
3. 依赖 `tables`（PyTables）、`pytdx`、`sqlite3` **均已安装**，无需 pip install。
4. 官方 GUI（HikyuuTDX）不是唯一路径，其底层逻辑即上述 Python 函数，可直接复用。
5. Hikyuu **不直接支持申万行业指数作为交易标的**，也不内置申万行业分类。
   申万行业数据应由项目公共数据层作为 external feature 提供，
   实际交易标的（ETF）进入 Hikyuu。此结构与任务书第七节一致。

---

## 二、StockManager 状态（实测）

```python
import hikyuu
sm = hikyuu.StockManager.instance()
len(sm) → 0                     # 未装载任何证券
sm.get_market_list() → []       # 未装载任何市场
```

- `StockManager.instance()` 可用，单例。
- 当前 `len == 0`、`get_market_list() == []` → **数据未初始化**。
- `sm['tmp0001']` 形式可访问临时证券（market 前缀 `tmp`）。

### StockManager 实测可用方法（节选，完整列表见附录 A）

| 分类 | 方法 |
|---|---|
| 证券增删 | `add_stock`, `remove_stock`, `add_temp_csv_stock`, `remove_temp_csv_stock` |
| 查询 | `get_stock`, `get_stock_list`, `get_market_list`, `get_market_stock`, `get_market_info` |
| 日历 | `get_trading_calendar`, `is_holiday`, `is_trading_hours` |
| 板块 | `add_block`, `get_block`, `get_block_list`, `save_block` |
| 路径 | `datadir()`, `tmpdir()`, `get_plugin_path()` |
| 类型 | `get_stock_type_info`, `get_stock_type_info_list`, `get_category_list` |
| 预载 | `get_preload_parameter`, `data_ready`, `wait_data_ready`, `reload`, `reload_with` |
| 财务 | `get_history_finance_all_fields`, `get_history_finance_field_name` |

---

## 三、数据目录与配置（实测）

| 项 | 实测值 |
|---|---|
| 配置目录 | `~/.hikyuu/`（容器内 `/home/mambauser/.hikyuu`） |
| 已存在文件 | `.hikyuu.lic`, `hikyuu.log`, `hub.db`, `uid`, `hub_cache/` |
| **`hikyuu.ini`** | **不存在**（需生成） |
| hub 路径 | `get_hub_path('default')` → `/home/mambauser/.hikyuu/hub_cache/default` |
| hub 列表 | `get_hub_name_list()` → `['default']` |
| `sm.datadir()` | 返回空字符串（未配置） |
| `sm.tmpdir()` | 返回空字符串（未配置） |
| 默认数据目录（模板） | Linux: `~/stock`；Windows: `C:\stock` |

### 配置文件生成

`hikyuu.data.hku_config_template.generate_default_config()` 会生成：

- `~/.hikyuu/hikyuu.ini` —— 主配置（默认 HDF5 模板）
- `~/.hikyuu/importdata-gui.ini` —— 导入配置
- `~/stock/block/` —— 板块配置文件（从包内 `config/block` 拷贝）

**注意**：该函数若检测到文件已存在则**不覆盖**。

### hikyuu.ini 结构（HDF5 模板，实测源码）

```ini
[hikyuu]
tmpdir   = {dir}/tmp
datadir  = {dir}
reload_time = 00:00
quotation_server = ipc:///tmp/hikyuu_real.ipc
lazy_preload = False

[block]        type = sqlite3 ; db = {dir}/stock.db
[baseinfo]     type = sqlite3 ; db = {dir}/stock.db
[kdata]
type   = hdf5                      ; 可选 tdx
sh_day = {dir}/sh_day.h5
sz_day = {dir}/sz_day.h5
bj_day = {dir}/bj_day.h5
sh_min = {dir}/sh_1min.h5   ... 等
```

支持三种后端模板：`hdf5_template`、`mysql_template`、`clickhouse_template`。

---

## 四、数据存储方式（实测源码 + 依赖检查）

| 后端 | 类型标识 | 依赖库 | 容器内状态 | 适用性 |
|---|---|---|---|---|
| **HDF5** | `hdf5` | `tables` (PyTables) | ✅ 已安装 | **推荐**（本地文件，无需服务） |
| SQLite3 | `sqlite3` | 标准库 | ✅ 内置 | 基础信息 + 板块（必须） |
| MySQL | `mysql` | `pymysql` | ❌ 缺失 | 需装依赖，本轮不用 |
| ClickHouse | `clickhouse` | `clickhouse_driver` | ❌ 缺失 | 需装依赖，本轮不用 |
| TDX 本地 | `tdx` | 无（读本地文件） | ✅ | 需本地通达信数据，本轮不用 |

- **K线数据**与**基础信息**（证券表、市场表）分离存储：
  - K线 → HDF5 文件（`sh_day.h5` / `sz_day.h5` …）
  - 基础信息 → SQLite `stock.db`
- `hikyuu/data/common_h5.py` 提供 HDF5 读写（`H5Record`, `H5Index`, `open_h5file`, `get_h5table`, `update_hdf5_extern_data`）。

---

## 五、数据导入方式（实测）

### 5.1 pytdx 网络导入（推荐，无需本地 TDX）

模块：`hikyuu.data.pytdx_to_h5`，实测函数签名：

| 函数 | 作用 |
|---|---|
| `import_index_name(connect)` | 导入指数代码表 → SQLite |
| `import_stock_name(connect, api, market, quotations)` | 导入股票/基金代码表 → SQLite |
| `import_data(connect, market, ktype, quotations, api, dest_dir, startDate, progress)` | 导入指定市场/类型的 K线 → HDF5 |
| `import_on_stock_data(...)` | 单只证券导入（内部） |
| `import_trans` / `import_time` | 分笔 / 分时（本轮不用） |

- `ktype` 取值实测：`'DAY'`, `'1MIN'`, `'5MIN'`（大写字符串）
- `market` 取值：`'SH'`, `'SZ'`, `'BJ'`
- `quotations` 取值：`['stock', 'fund']`（来自 `hikyuu.data.common.get_stktype_list`）
- 依赖 `pytdx.hq.TdxHq_API`，需 `api.connect(host, port)`。

**重要**：模块内 `if __name__ == '__main__'` 段是开发者硬编码脚本
（`dest_dir = "/Users/fasiondog/stock"`，Mac 路径，含 `unrar` 解压 qianlong 权息），
**不是生产 CLI**。应直接调用上述函数，不要执行该 `__main__`。

### 5.2 本地 TDX 文件导入

`hikyuu.data.tdx_to_h5`，需本地通达信 `vipdoc` 目录。Docker 环境无此数据，本轮不用。

### 5.3 CSV 临时导入

`sm.add_temp_csv_stock(code, day_filename, min_filename, tick, tick_value, precision, ...)`

- 适用于「只有 CSV 格式 K线数据时进行临时测试」。
- 生成的 stock 属于 market `"TMP"`，需以 `sm['tmp0001']` 形式获取。
- CSV 必须含列：`Datetime`(或 Date/日期), `OPEN`, `HIGH`, `LOW`, `CLOSE`, `AMOUNT`, `VOLUME`(或 VOL/COUNT/成交量)
- 必须 utf8 编码。

**实测坑**：
- `min_filename` 传空字符串会在加载时尝试打开并报
  `Can't open this file: , ktype: MIN (KDataTempCsvDriver.cpp:155)`
- `min_filename` 传**日线 csv 本身**会导致**进程段错误（exit 139/SIGSEGV）**。
  → 结论：`min_filename` 必须是一个**格式合法的分钟线 CSV**，不可复用日线文件，不可留空。
  本轮因只需要日线回测，此路径仅作为可选补充，非主路径。

### 5.4 其他后端导入脚本（存在但不使用）

`tdx_to_h5` / `pytdx_to_mysql` / `pytdx_to_clickhouse` / `pytdx_weight_to_*` /
`zh_bond10_to_*` / `weight_to_sqlite` / `em_block_to_sqlite`（东财板块）/
`download_block` / `pytdx_finance_to_*`（财务）。

---

## 六、行情类型（实测）

来自 `hikyuu.data.common.get_stktype_list(quotations)`：

- `quotations=None` → 全部类型
- `['stock']` → 股票类
- `['fund']` → 基金类（含 ETF）
- `['stock', 'fund']` → 两者，是常见组合

K线类型（ktype）：`DAY`、`WEEK`、`MONTH`、`QUARTER`、`HALFYEAR`、`YEAR`、
`1MIN`、`5MIN`、`15MIN`、`30MIN`、`60MIN`、`HOUR2`、`TIMELINE`、`TRANS`。

预载配置项见 `hikyuu.ini` 的 `[preload]` 段（`day`、`week`、`min5` … 各自可开关，且有 `*_max` 上限）。

---

## 七、KData 获取方式（实测）

- 通过 `Stock` 对象获取 K线，`KQuery` 构造查询条件。
  注意：`hikyuu.KQuery` **不存在**于顶层命名空间，需从子模块导入
  （实测 `hikyuu.KQuery` → `AttributeError`）。
- 交易日历查询：`sm.get_trading_calendar(query, market='SH')` → `DatetimeList`。
- 重载：`sm.reload()` / `sm.reload_with(其他配置)`。

现有项目代码（`strategies/sw_sector_rotation/src/adapters/hikyuu/sector_rotation.py`）
已在此前实测中确认过 `KData` 转换逻辑，本轮将在此基础上接真实数据。

---

## 八、交易日历来源（实测）

- API：`sm.get_trading_calendar(query, market)`、`sm.is_holiday(date)`、`sm.is_trading_hours(datetime)`
- `hikyuu.data.common.get_new_holidays()` 用于获取节假日。
- 日历数据来源为 Hikyuu 自身（配置生成时内置于包内配置 / 通过 Market 表 lastDate 维护）。
- **未实测**：完整日历是否需要额外数据文件。若 `get_trading_calendar` 在空 SM 下返回空，
  则说明日历依赖已装载的市场数据；此点将在数据初始化后验证。

---

## 九、官方 CLI / import 工具（实测）

- Hikyuu 包内**未发现**独立的行情导入 CLI 命令（`grep` 表明 `tdx_to_h5` 有 `__main__` 但为硬编码开发脚本）。
- `hikyuu/hub.py` 提供**仓库（hub）系统**：
  `add_local_hub`, `add_remote_hub`, `update_hub`, `build_hub`, `remove_hub`,
  `get_part`, `get_part_list`, `search_part`, `get_hub_name_list`, `get_part_name_list`。
- 已安装 `default` hub 含 **61 个 part**，其中包括对回测极有价值的现成组件（见第十一节）。
- `hikyuu.gui` 存在（HikyuuTDX GUI），但其底层逻辑即 `hikyuu.data.*` 中的 Python 函数，
  **可在无 GUI 环境直接复用**。

---

## 十、Docker Linux 环境下推荐的数据初始化方式

```text
1. hku_config_template.generate_default_config()   # 生成 ~/.hikyuu/hikyuu.ini（HDF5 模板）
2. sqlite3.connect(datadir/stock.db) + create_database(connect)   # 建基础信息表
3. pytdx.hq.TdxHq_API().connect(host, port)         # 连通行情服务器
4. pytdx_to_h5.import_stock_name(connect, api, 'SH'/'SZ', ['stock','fund'])
5. pytdx_to_h5.import_data(connect, market, 'DAY', ['stock','fund'], api, dest_dir)
6. sm = hikyuu.StockManager.instance(); sm.reload()  # 装载
7. 验证：len(sm) > 0，get_market_list() 非空，KData 可读，交易日历可用
```

分阶段：先用少量标的验证链路（LEVEL A），再考虑完整数据（LEVEL B 依赖申万行业数据）。

---

## 十一、附：default hub 现成组件（实测 `get_part_name_list('default')`）

对回测有直接价值的部分：

| part | 说明 |
|---|---|
| `default.other.stks-etf` | 获取所有 ETF（依赖 StockManager，当前返回空 list） |
| `default.other.stks-沪深300` | 沪深300 成分股 |
| `default.pf.base_最低单因子轮动` | 组合选择器：**最低单因子轮动**（模板） |
| `default.pf.银行股低市净率轮动` | 轮动组合示例 |
| `default.sys.调仓日买入` | 调仓日买入系统 |
| `default.se.最低单因子` / `default.se.signal` / `default.se.fixed` | 选择器 |
| `default.af.equal_weight` / `default.af.fixed_weight` | 资金分配 |
| `default.mm.*` | 资金管理（fixed_count/percent/capital/risk/unit 等） |
| `default.pg.*` | 盈利目标（fixed_percent/fixed_hold_days/nogoal） |
| `default.st.saftyloss` / `default.st.fixed_percent` | 止损 |
| `default.sys.*` | 现成系统（双均线金叉、布林线、趋势等） |

**注意**：这些 part 提供的是**策略模板组件**，与 sw_sector_rotation 的算法无关。
本轮只使用其**运行框架能力**（Portfolio / System / 资金管理 / 成本），
**不引入其因子或选股逻辑**，以免污染策略核心。

---

## 十二、回测执行 API（第二阶段实测补充）

### 12.1 最小执行链路（实测可用）

```python
import hikyuu
hikyuu.load_hikyuu()
sm = hikyuu.StockManager.instance()
stk = sm['sh510300']                      # 必须带市场前缀

tm = hikyuu.crtTM(init_cash=100000)       # 交易账户
sg = hikyuu.SG_Cross(hikyuu.MA(hikyuu.CLOSE(), 5),
                     hikyuu.MA(hikyuu.CLOSE(), 20))
mm = hikyuu.MM_FixedCount(1000)
st = hikyuu.ST_FixedPercent(0.05)
sys = hikyuu.SYS_Simple(tm=tm, sg=sg, mm=mm, st=st)
sys.run(stk, hikyuu.Query(hikyuu.Datetime(20200101), hikyuu.Datetime(20241231)))
```

### 12.2 TradeManager 实测要点

| 方法/属性 | 实测签名与说明 |
|---|---|
| `get_trade_list()` | 返回 `TradeRecord` 列表；**首条是 `BUSINESS.INIT`**（建账，number=0） |
| `TradeRecord` 字段 | `datetime` / `stock` / `business` / **`real_price`（成交价，不是 `price`）** / `plan_price` / `number` / `cash` / `cost.total` / `part` / `stoploss` |
| `get_funds_curve(dates)` | **只接受 `DatetimeList`**，不接受 `Query`；返回 `list[float]` |
| `get_funds(datetime)` | 返回 `FundsRecord(现金, 市值, ...)` |
| `get_funds_list(dates)` | 返回 `list[FundsRecord]` |
| `get_history_position_list()` | 历史持仓 |
| `get_max_pull_back()` | **无参数**；实测未平仓状态下返回 0.0（不可靠） |
| `get_performance(datetime, ktype)` | 返回 `Performance`（`to_dict()` 53 个中文键）；实测部分日期参数下全 0 |

### 12.3 三个必须避免的坑（实测）

1. **`Query(20200101, 20241231)`（int 形式）会导致 `get_funds_curve` 返回空**。
   必须用显式 `hikyuu.Datetime(...)` 构造 Query。
2. **`sym in sm` 恒返回 `False`**（`StockManager.__contains__` 实现问题）。
   必须直接索引 `sm[sym]` 再检查 `.valid`。
3. **`get_max_pull_back()` 与 `get_performance()` 不可靠**。
   最大回撤/年化/Sharpe 建议从 `get_funds_curve` 自行计算，
   公式透明、可追溯。

### 12.4 现成组件（`default` hub）

`SYS_Simple` / `SYS_WalkForward` / `SG_*` / `MM_*` / `ST_*` / `PG_*` /
`SP_*` / `CN_*` 均为顶层可用函数。
`get_part('default.pf.base_最低单因子轮动')` 等组合模板可复用，
但**自带选股逻辑**，接入本项目策略时需注意避免污染策略核心。

---

## 十三、未实测 / 待验证项

1. `get_trading_calendar` 在空 SM 下的行为（预期依赖已装载数据）。
2. 完整市场数据导入的耗时与体积（本轮只做最小集）。
3. `import_data` 在容器内对 `SH`/`SZ` 全市场的实际稳定性（网络中断恢复行为）。
4. ETF 的 `quotations` 分类是否确为 `'fund'`（需在导入后用 `sm` 验证类型字段）。
5. 复权（weight）数据导入路径 `weight_to_sqlite` 是否可用的完整验证。
