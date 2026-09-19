"""SW Sector Rotation Core —— Hikyuu 侧策略包。

纯核心 + adapter 分离：
- 本包内的 ``model`` / ``ranking`` / ``strategy`` 是**框架无关**的纯核心；
- ``src.adapters.hikyuu.sector_rotation`` 负责 Hikyuu ↔ canonical frame 的转换。

状态：MIGRATED / NOT YET BACKTESTED。
"""

from src.strategies.hikyuu.sw_sector_rotation.model import (
    CrossSectionalRidgeModel,
    NumPyRidge,
    RankingResult,
)
from src.strategies.hikyuu.sw_sector_rotation.ranking import (
    build_etf_candidates,
    rank_sectors,
    sector_scores_to_weights,
    select_top,
)
from src.strategies.hikyuu.sw_sector_rotation.strategy import (
    FLOW_ADJUST_LIMIT,
    SWSectorRotationConfig,
    SWSectorRotationCore,
    apply_flow_adjustment,
)

__all__ = [
    "CrossSectionalRidgeModel",
    "NumPyRidge",
    "RankingResult",
    "rank_sectors",
    "select_top",
    "sector_scores_to_weights",
    "build_etf_candidates",
    "SWSectorRotationCore",
    "SWSectorRotationConfig",
    "apply_flow_adjustment",
    "FLOW_ADJUST_LIMIT",
]
