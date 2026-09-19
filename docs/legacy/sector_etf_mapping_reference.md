# Legacy 行业 → ETF 映射参考

> **LEGACY REFERENCE ONLY — REQUIRES REVALIDATION**
>
> 本文件是 Legacy china-market-data v5 的 ETF 映射快照，**不是**当前生产配置。
> 其中的 ETF 代码、规模、关系标注均为**历史产品信息**，未经重新验证：
> - ETF 可能已清盘、改名、变更跟踪指数
> - 申万行业分类本身也会调整
> - 规模与流动性需重新核实
>
> **不得**直接用于实盘或作为正式组合配置。
> **不联网更新**本文件。重新验证后另建生产配置。

来源: `scripts/quant/predict.py::load_etf_mapping` (legacy v5)

## relation 语义

| relation | 含义 |
|----------|------|
| direct | 该 ETF 直接跟踪对应行业指数 |
| composite | 该 ETF 覆盖多个行业，目标行业是成分之一 |
| proxy | 无直接对应，用相近 ETF 代理 |

## 映射快照

| 申万二级行业 | ETF 代码 | ETF 名称 | relation |
|--------------|----------|----------|----------|
| 半导体 | 512480 | 国联安中证全指半导体ETF | direct |
| 航天装备Ⅱ | 512660 | 国泰中证军工ETF | composite |
| 军工电子Ⅱ | 512660 | 国泰中证军工ETF | composite |
| 航空装备Ⅱ | 512660 | 国泰中证军工ETF | composite |
| 通信设备 | 515050 | 华夏中证5G通信ETF | direct |
| 消费电子 | 159997 | 天弘中证电子ETF | composite |
| 光学光电子 | 159997 | 天弘中证电子ETF | composite |
| 计算机设备 | 159852 | 嘉实中证软件服务ETF | composite |
| 软件开发 | 159852 | 嘉实中证软件服务ETF | direct |
| IT服务Ⅱ | 159852 | 嘉实中证软件服务ETF | composite |
| 元件 | 159997 | 天弘中证电子ETF | composite |
| 电池 | 159840 | 工银瑞信中证电池ETF | direct |
| 光伏设备 | 515790 | 华泰柏瑞中证光伏ETF | direct |
| 风电设备 | 516160 | 南方中证新能源ETF | composite |
| 能源金属 | 516160 | 南方中证新能源ETF | composite |
| 工业金属 | 512400 | 南方中证申万有色金属ETF | direct |
| 贵金属 | 512400 | 南方中证申万有色金属ETF | composite |
| 小金属 | 512400 | 南方中证申万有色金属ETF | composite |
| 煤炭开采 | 515220 | 国泰中证煤炭ETF | direct |
| 电力 | 159611 | 广发中证全指电力公用ETF | direct |
| 证券Ⅱ | 512880 | 国泰中证全指证券公司ETF | direct |
| 保险Ⅱ | 515770 | 方正富邦中证保险ETF | direct |
| 银行 | 512800 | 华宝中证银行ETF | direct |
| 白酒Ⅱ | 512690 | 鹏华中证酒ETF | direct |
| 饮料乳品 | 515170 | 华夏中证食品饮料ETF | composite |
| 食品加工 | 515170 | 华夏中证食品饮料ETF | composite |
| 医疗器械 | 159883 | 永赢中证医疗器械ETF | direct |
| 医疗服务 | 516820 | 平安中证医药及医疗器械ETF | composite |
| 化学制药 | 159859 | 天弘国证生物医药ETF | composite |
| 中药Ⅱ | 560080 | 汇添富中证中药ETF | direct |
| 生物制品 | 159859 | 天弘国证生物医药ETF | composite |
| 乘用车 | 515030 | 华夏中证新能源汽车ETF | direct |
| 汽车零部件 | 515030 | 华夏中证新能源汽车ETF | composite |
| 房地产开发 | 512200 | 南方中证房地产ETF | direct |
| 装修建材 | 159745 | 易方达中证建筑材料ETF | direct |
| 工程机械 | 516960 | 国泰中证细分机械设备ETF | composite |
| 通用设备 | 516960 | 国泰中证细分机械设备ETF | composite |
| 自动化设备 | 516960 | 国泰中证细分机械设备ETF | composite |
| 电网设备 | 159616 | 建信中证智能电网ETF | direct |
| 航运港口 | 516910 | 富国中证现代物流ETF | composite |
| 航空机场 | 159852 | 嘉实中证软件服务ETF | 无直接 |
| 影视院线 | 159855 | 银华中证影视ETF | direct |
| 游戏Ⅱ | 159869 | 华夏中证动漫游戏ETF | direct |
| 养殖业 | 159865 | 银华中证畜牧养殖ETF | direct |
| 饲料 | 159865 | 银华中证畜牧养殖ETF | composite |
| 种植业 | 159865 | 银华中证畜牧养殖ETF | composite |
| 环境治理 | 159807 | 易方达中证环保ETF | direct |
| 环保设备Ⅱ | 159807 | 易方达中证环保ETF | composite |

## 已知问题（legacy 遗留，勿带入生产）

1. **航空机场 → 159852（软件服务ETF）** 标注为 `无直接`，这是一个明显的
   proxy 失效案例，说明当时的映射表有未清理的错误项。
2. 大量行业共用同一 ETF（如 512400 覆盖 3 个有色子行业），组合层面
   必须去重，否则会重复计权。
3. 映射表只有 48 条，申万二级行业约 131 个，覆盖率不足 40%。

## 迁移实现

算法（匹配、去重、穿透权重）已迁移至
`src/portfolio/sector_etf_mapping.py`：

- `match_etfs_for_sectors()` —— 排名行业 → ETF 候选（含去重）
- `passthrough_sector_weights()` —— 一个 ETF 穿透多行业的权重分配
- `normalize_scores_to_weights()` —— 分数归一化

示例配置见 `configs/strategies/sw_sector_rotation_mapping.example.yaml`。
