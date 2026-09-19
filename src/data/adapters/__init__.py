"""数据层适配器 —— 把 canonical frame 转成下游组件需要的格式。

职责：格式转换，不含业务逻辑。
"""

from __future__ import annotations

from .to_market_frame import canonical_to_market_frame

__all__ = ["canonical_to_market_frame"]
