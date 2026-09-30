"""Hikyuu 适配器包。

把 Hikyuu 的 KData / Portfolio / Selector / AllocateFunds 与框架无关的
纯策略核心桥接起来。当前阶段只建立接口，不做正式行情回测。
"""

from strategies.sw_sector_rotation.src.adapters.hikyuu.sector_rotation import (
    VERIFIED_HIKYUU_API,
    AdaptersNotWiredReason,
    HikyuuAllocatorProtocol,
    HikyuuDataNotInitialized,
    HikyuuSelectorProtocol,
    SectorWeightTarget,
    build_stock_selector_input,
    kdata_to_market_frame,
    ranked_sectors_to_targets,
    targets_to_system_weights,
)

__all__ = [
    "VERIFIED_HIKYUU_API",
    "HikyuuDataNotInitialized",
    "AdaptersNotWiredReason",
    "SectorWeightTarget",
    "HikyuuSelectorProtocol",
    "HikyuuAllocatorProtocol",
    "kdata_to_market_frame",
    "ranked_sectors_to_targets",
    "targets_to_system_weights",
    "build_stock_selector_input",
]
