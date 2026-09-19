"""SW Sector Rotation Core 的策略源码。

结构：

- ``factors/``    因子（MA/MAPP、波动率、反转、回撤、RSI、RSRS、Macro PIT）
- ``model/``      三周期横截面 Ridge 模型与排名
- ``risk/``       五指标风险状态
- ``portfolio/``  行业 → ETF 映射
- ``common/``     时点完整性护栏
- ``adapters/``   Hikyuu 适配器
- ``strategy.py`` 总入口编排器

纯核心（factors / model / risk / portfolio / common）不依赖任何框架；
``adapters/`` 负责与 Hikyuu 桥接。
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
