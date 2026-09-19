"""SW Sector Rotation Core —— 自包含策略包。

包含：

- ``src/factors/``    因子（MA/MAPP、波动率、反转、回撤、RSI、RSRS、Macro PIT）
- ``src/model/``      三周期横截面 Ridge 模型与排名
- ``src/risk/``       五指标风险状态
- ``src/portfolio/``  行业 → ETF 映射
- ``src/common/``     时点完整性护栏
- ``src/adapters/``   Hikyuu 适配器
- ``src/strategy.py`` 总入口编排器
- ``config/``         策略配置
- ``tests/``          策略测试
- ``docs/``           规格书与迁移报告

状态：MIGRATED / NOT YET BACKTESTED（尚未接数据、未回测）
"""

from strategies.sw_sector_rotation.src.strategy import (
    FLOW_ADJUST_LIMIT,
    SWSectorRotationConfig,
    SWSectorRotationCore,
    apply_flow_adjustment,
)

__all__ = [
    "SWSectorRotationCore",
    "SWSectorRotationConfig",
    "apply_flow_adjustment",
    "FLOW_ADJUST_LIMIT",
]
