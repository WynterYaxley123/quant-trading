"""横截面 Ridge 模型与排名。

纯核心，框架无关：

- :mod:`...src.model.model` —— NumPyRidge + 三周期横截面模型
- :mod:`...src.model.ranking` —— 排名 / 权重（纯函数，不触碰风险）

总入口编排器在 :mod:`...src.strategy`。

状态：MIGRATED / NOT YET BACKTESTED。
"""

from strategies.sw_sector_rotation.src.model.model import (
    CrossSectionalRidgeModel,
    NumPyRidge,
    RankingResult,
)
from strategies.sw_sector_rotation.src.model.ranking import (
    build_etf_candidates,
    rank_sectors,
    sector_scores_to_weights,
    select_top,
)

__all__ = [
    "CrossSectionalRidgeModel",
    "NumPyRidge",
    "RankingResult",
    "rank_sectors",
    "select_top",
    "sector_scores_to_weights",
    "build_etf_candidates",
]
