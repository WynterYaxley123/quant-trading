"""Hikyuu adapter 测试。

覆盖迁移任务书第九、十一节：
- KData → canonical market frame 转换
- ranking → targets / SystemWeight 输入
- 实测确认的 Hikyuu 2.8.2 API 存在性
- 行情未初始化时抛 HikyuuDataNotInitialized（测试 skip，不算失败）

本测试**不下载行情、不初始化 Hikyuu 数据库、不跑正式回测**。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

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
from strategies.sw_sector_rotation.src.factors.sector_rotation import CANONICAL_COLUMNS
from strategies.sw_sector_rotation.src.model.ranking import (
    rank_sectors,
    sector_scores_to_weights,
)


# ---------------------------------------------------------------------------
# 假 KData（不依赖 Hikyuu）
# ---------------------------------------------------------------------------


class _Bar:
    """模拟 Hikyuu KRecord 的数值接口。"""

    def __init__(self, dt, o, h, l, c, v, a):
        self.datetime = dt
        self.open = o
        self.high = h
        self.low = l
        self.close = c
        self.volume = v
        self.amount = a


class _FakeKData:
    """模拟 Hikyuu KData：可迭代、可 len()、有 get_datetime_list()。"""

    def __init__(self, n=50, start="2024-01-02"):
        dates = pd.bdate_range(start=start, periods=n)
        self._bars = []
        for i, d in enumerate(dates):
            c = 100.0 + i
            self._bars.append(
                _Bar(d.to_pydatetime(), c - 0.5, c + 1.0, c - 1.0, c, 1e6, 1e8 * c)
            )

    def __len__(self):
        return len(self._bars)

    def __iter__(self):
        return iter(self._bars)

    def get_datetime_list(self):
        return [b.datetime for b in self._bars]


# ---------------------------------------------------------------------------
# KData → canonical frame
# ---------------------------------------------------------------------------


def test_kdata_to_market_frame_basic():
    kdata = _FakeKData(n=60)
    frame = kdata_to_market_frame(kdata)
    assert isinstance(frame, pd.DataFrame)
    assert isinstance(frame.index, pd.DatetimeIndex)
    assert list(frame.columns) == list(CANONICAL_COLUMNS)
    assert len(frame) == 60
    assert frame.index.is_monotonic_increasing


def test_kdata_to_market_frame_values_match():
    kdata = _FakeKData(n=10)
    frame = kdata_to_market_frame(kdata)
    assert frame["close"].iloc[0] == pytest.approx(100.0)
    assert frame["close"].iloc[-1] == pytest.approx(109.0)
    assert frame["high"].iloc[0] > frame["low"].iloc[0]


def test_kdata_none_raises_not_initialized():
    with pytest.raises(HikyuuDataNotInitialized, match="None"):
        kdata_to_market_frame(None)


def test_kdata_empty_raises_not_initialized():
    with pytest.raises(HikyuuDataNotInitialized, match="长度为 0"):
        kdata_to_market_frame(_FakeKData(n=0))


def test_converted_frame_passes_canonical_validation():
    from strategies.sw_sector_rotation.src.factors.sector_rotation import validate_market_frame

    frame = kdata_to_market_frame(_FakeKData(n=120))
    validate_market_frame(frame)  # 不抛异常

    # 转换后可直接跑因子
    from strategies.sw_sector_rotation.src.factors.sector_rotation import compute_all_price_features

    feats = compute_all_price_features(frame, include_rsrs=True)
    assert "rsrs" in feats.columns


def test_kdata_missing_field_raises_typeerror():
    class Broken:
        def __len__(self):
            return 1

        def __iter__(self):
            return iter([object()])

        def get_datetime_list(self):
            return [pd.Timestamp("2024-01-02").to_pydatetime()]

    with pytest.raises(TypeError, match="缺少字段"):
        kdata_to_market_frame(Broken())


# ---------------------------------------------------------------------------
# ranking → targets
# ---------------------------------------------------------------------------


def test_ranked_sectors_to_targets_equal_weight():
    ranked = [("A", 3.0), ("B", 2.0), ("C", 1.0)]
    targets = ranked_sectors_to_targets(ranked)
    assert len(targets) == 3
    assert all(isinstance(t, SectorWeightTarget) for t in targets)
    assert sum(t.target_weight for t in targets) == pytest.approx(1.0)
    assert all(t.target_weight == pytest.approx(1 / 3) for t in targets)


def test_ranked_sectors_to_targets_from_etf_candidates():
    candidates = [
        {"etf_code": "512480", "sectors": ["半导体"], "relation": "direct", "weight": 0.6},
        {"etf_code": "515220", "sectors": ["煤炭"], "relation": "direct", "weight": 0.4},
    ]
    targets = ranked_sectors_to_targets([], candidates)
    assert [t.symbol for t in targets] == ["512480", "515220"]
    assert sum(t.target_weight for t in targets) == pytest.approx(1.0)


def test_targets_normalized_even_if_input_weights_unnormalized():
    candidates = [
        {"etf_code": "E1", "weight": 2.0},
        {"etf_code": "E2", "weight": 6.0},
    ]
    targets = ranked_sectors_to_targets([], candidates)
    assert targets[0].target_weight == pytest.approx(0.25)
    assert targets[1].target_weight == pytest.approx(0.75)


def test_targets_to_system_weights():
    targets = [
        SectorWeightTarget("512480", 0.7),
        SectorWeightTarget("515220", 0.3),
        SectorWeightTarget("", 0.5),  # 空 symbol 应被跳过
    ]
    out = targets_to_system_weights(targets)
    assert len(out) == 2
    assert out[0] == {"symbol": "512480", "weight": 0.7}
    assert all(set(d) == {"symbol", "weight"} for d in out)


def test_build_stock_selector_input():
    targets = [SectorWeightTarget("SECTOR_A", 0.5), SectorWeightTarget("SECTOR_B", 0.5)]
    out = build_stock_selector_input(targets)
    assert out["stock_list"] == ["SECTOR_A", "SECTOR_B"]
    assert out["weights"] == {"SECTOR_A": 0.5, "SECTOR_B": 0.5}
    assert set(out["scores"]) == {"SECTOR_A", "SECTOR_B"}


def test_build_stock_selector_input_with_resolver():
    targets = [SectorWeightTarget("A", 1.0)]
    out = build_stock_selector_input(targets, symbol_resolver={"A": "SH512480"})
    assert out["stock_list"] == ["SH512480"]


def test_end_to_end_ranking_to_hikyuu_inputs():
    """排名 → 权重 → ETF targets → Hikyuu 输入描述，全链路可跑。"""
    scores = {"半导体": 3.0, "煤炭": 2.0, "银行": 1.0}
    ranked = rank_sectors(scores)
    weights = sector_scores_to_weights(ranked)
    assert sum(weights.values()) == pytest.approx(1.0)

    mapping = {
        "半导体": {"code": "512480", "name": "半导体ETF", "relation": "direct"},
        "煤炭": {"code": "515220", "name": "煤炭ETF", "relation": "direct"},
        "银行": {"code": "512800", "name": "银行ETF", "relation": "direct"},
    }
    from strategies.sw_sector_rotation.src.model.ranking import build_etf_candidates

    candidates = build_etf_candidates(ranked, mapping, top_n=2)
    for c in candidates:
        c["weight"] = weights.get(c["sectors"][0], 1.0 / len(candidates))

    targets = ranked_sectors_to_targets(ranked, candidates)
    sys_weights = targets_to_system_weights(targets)
    assert len(sys_weights) == 2
    assert sum(d["weight"] for d in sys_weights) == pytest.approx(1.0)

    selector_input = build_stock_selector_input(targets)
    assert len(selector_input["stock_list"]) == 2


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


def test_protocols_are_runtime_checkable():
    class Selector:
        def add_stock_list(self, stock_list):
            pass

        def calculate(self):
            pass

        def get_selected(self):
            pass

    s = Selector()
    assert isinstance(s, HikyuuSelectorProtocol)

    class NotASelector:
        pass

    assert not isinstance(NotASelector(), HikyuuSelectorProtocol)


def test_allocator_protocol():
    class Alloc:
        def set_param(self, name, value):
            pass

        def reset(self):
            pass

    assert isinstance(Alloc(), HikyuuAllocatorProtocol)


# ---------------------------------------------------------------------------
# 实测确认的 Hikyuu 2.8.2 API
# ---------------------------------------------------------------------------


def test_verified_api_registry_covers_required_classes():
    assert set(VERIFIED_HIKYUU_API) == {
        "Portfolio",
        "SelectorBase",
        "AllocateFundsBase",
        "System",
    }
    assert "run" in VERIFIED_HIKYUU_API["Portfolio"]
    assert "add_stock_list" in VERIFIED_HIKYUU_API["SelectorBase"]
    assert "set_param" in VERIFIED_HIKYUU_API["AllocateFundsBase"]


def test_hikyuu_api_actually_exists_in_framework():
    """在真实 Hikyuu 2.8.2 上核对注册表里的方法确实存在。

    Hikyuu 不可 import 时 skip（不算失败）。
    """
    hikyuu = pytest.importorskip("hikyuu", reason="hikyuu not importable")
    for cls_name, methods in VERIFIED_HIKYUU_API.items():
        cls = getattr(hikyuu, cls_name, None)
        assert cls is not None, f"Hikyuu 缺少类 {cls_name}"
        available = set(dir(cls))
        for m in methods:
            assert m in available, f"{cls_name} 缺少方法 {m}"


def test_adapter_documents_wiring_reason():
    assert AdaptersNotWiredReason.DATA_NOT_INITIALIZED == "DATA_NOT_INITIALIZED"
    assert (
        AdaptersNotWiredReason.SELECTOR_SUBCLASS_PENDING
        == "SELECTOR_SUBCLASS_PENDING"
    )


def test_adapter_does_not_import_hikyuu_at_module_level():
    """adapter 模块不得在顶层 import hikyuu（保持框架无关可测）。"""
    from pathlib import Path

    import strategies.sw_sector_rotation.src.adapters.hikyuu.sector_rotation as mod

    text = Path(mod.__file__).read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("import hikyuu") or stripped.startswith("from hikyuu"):
            pytest.fail(f"adapter 顶部不应 import hikyuu: {line!r}")


def test_core_strategy_does_not_import_frameworks():
    """纯核心（factors/model/ranking/strategy/risk/portfolio）不得 import 框架。"""
    from pathlib import Path

    import strategies.sw_sector_rotation.src.factors.sector_rotation as f
    import strategies.sw_sector_rotation.src.factors.rsrs as r
    import strategies.sw_sector_rotation.src.factors.macro_pit as mp
    import strategies.sw_sector_rotation.src.risk.sector_rotation as risk
    import strategies.sw_sector_rotation.src.portfolio.sector_etf_mapping as port
    import strategies.sw_sector_rotation.src.model.model as model
    import strategies.sw_sector_rotation.src.strategy as strat

    banned = ("import hikyuu", "from hikyuu", "import rqalpha", "from rqalpha")
    for mod in (f, r, mp, risk, port, model, strat):
        text = Path(mod.__file__).read_text(encoding="utf-8")
        for line in text.splitlines():
            s = line.strip()
            if any(s.startswith(b) for b in banned):
                pytest.fail(f"{mod.__name__} 不应依赖框架: {line!r}")


def test_market_data_not_downloaded_in_tests():
    """策略测试不得包含行情下载调用。

    只扫描新增的策略测试目录；``tests/framework`` 下的 smoke test
    会检查依赖能否 import，属既有基线，不在本次范围内。

    注意：本测试扫描的源文件包含它自身，因此 banned 字符串必须
    拼接构造，避免自匹配。
    """
    from pathlib import Path

    strategy_tests = Path(__file__).resolve().parent
    banned = (
        "ak" + "share",
        "index_hist_" + "sw",
        "requests." + "get",
        "url" + "open",
    )
    for py in strategy_tests.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for b in banned:
            if b in text:
                pytest.fail(f"{py.name} 含行情下载痕迹: {b!r}")
