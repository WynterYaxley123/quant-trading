"""排名 / 权重 / ETF 映射测试。

覆盖迁移任务书第六、七节：
- ranking → ETF candidates（纯函数）
- 权重归一化
- **不迁移** 错误的 Top5→Top3 "降敞口"逻辑
- apply_risk_budget 为 NOT_IMPLEMENTED
"""

from __future__ import annotations

import pytest

from src.portfolio.sector_etf_mapping import (
    NOT_IMPLEMENTED,
    RELATION_DIRECT,
    RELATION_PROXY,
    RiskBudgetNotImplemented,
    apply_risk_budget,
    match_etfs_for_sectors,
    normalize_scores_to_weights,
    passthrough_sector_weights,
)
from src.strategies.hikyuu.sw_sector_rotation.ranking import (
    build_etf_candidates,
    rank_sectors,
    sector_scores_to_weights,
    select_top,
)


# ---------------------------------------------------------------------------
# 排名
# ---------------------------------------------------------------------------


def test_rank_sectors_descending():
    scores = {"A": 1.0, "B": 3.0, "C": 2.0}
    ranked = rank_sectors(scores)
    assert [s for s, _ in ranked] == ["B", "C", "A"]


def test_rank_sectors_tie_breaks_stably():
    scores = {"Z": 1.0, "A": 1.0, "M": 1.0}
    ranked = rank_sectors(scores)
    assert [s for s, _ in ranked] == ["A", "M", "Z"]


def test_select_top():
    ranked = [("A", 3.0), ("B", 2.0), ("C", 1.0)]
    assert select_top(ranked, 2) == [("A", 3.0), ("B", 2.0)]
    assert select_top(ranked, 0) == []
    assert select_top(ranked, 10) == ranked


# ---------------------------------------------------------------------------
# 权重
# ---------------------------------------------------------------------------


def test_sector_scores_to_weights_sum_to_one():
    ranked = [("A", 3.0), ("B", 1.0), ("C", -1.0)]
    w = sector_scores_to_weights(ranked)
    assert sum(w.values()) == pytest.approx(1.0)
    assert all(v >= 0 for v in w.values()), "long_only 下不得有负权重"
    assert w["A"] > w["B"] > w["C"]


def test_sector_scores_to_weights_equal_when_identical():
    ranked = [("A", 1.0), ("B", 1.0)]
    w = sector_scores_to_weights(ranked)
    assert w["A"] == pytest.approx(0.5)
    assert w["B"] == pytest.approx(0.5)


def test_sector_scores_to_weights_empty():
    assert sector_scores_to_weights([]) == {}


def test_normalize_scores_to_weights_handles_negatives():
    w = normalize_scores_to_weights({"A": -5.0, "B": 5.0})
    assert sum(w.values()) == pytest.approx(1.0)
    assert all(v >= 0 for v in w.values())


# ---------------------------------------------------------------------------
# ETF 映射
# ---------------------------------------------------------------------------


_MAPPING = {
    "半导体": {"code": "512480", "name": "半导体ETF", "relation": RELATION_DIRECT},
    "消费电子": {"code": "159997", "name": "电子ETF", "relation": "composite"},
    "元件": {"code": "159997", "name": "电子ETF", "relation": "composite"},
    "煤炭": {"code": "515220", "name": "煤炭ETF", "relation": RELATION_DIRECT},
    "未知行业": None,
}


def test_match_etfs_deduplicates():
    """一个 ETF 覆盖多个行业时只出现一次。"""
    ranked = [("消费电子", 2.0), ("元件", 1.5), ("半导体", 1.0)]
    out = match_etfs_for_sectors(ranked, _MAPPING)
    codes = [r["etf_code"] for r in out]
    assert len(codes) == len(set(codes)), "ETF 必须去重"
    electronic = next(r for r in out if r["etf_code"] == "159997")
    assert set(electronic["sectors"]) == {"消费电子", "元件"}
    assert electronic["score"] == pytest.approx(2.0), "取覆盖行业的最高分"


def test_match_etfs_sorted_by_score():
    ranked = [("半导体", 1.0), ("煤炭", 5.0)]
    out = match_etfs_for_sectors(ranked, _MAPPING)
    assert [r["etf_code"] for r in out] == ["515220", "512480"]


def test_match_etfs_skips_unmapped():
    ranked = [("未知行业", 9.0), ("半导体", 1.0)]
    out = match_etfs_for_sectors(ranked, _MAPPING)
    assert [r["etf_code"] for r in out] == ["512480"]


def test_direct_relation_preferred_on_merge():
    """同一 ETF 同时来自 direct 与 composite 时保留 direct。"""
    mapping = {
        "X": {"code": "E1", "name": "e", "relation": RELATION_PROXY},
        "Y": {"code": "E1", "name": "e", "relation": RELATION_DIRECT},
    }
    out = match_etfs_for_sectors([("X", 1.0), ("Y", 1.0)], mapping)
    assert out[0]["relation"] == RELATION_DIRECT


def test_build_etf_candidates_respects_top_n():
    mapping = {
        f"S{i}": {"code": f"E{i}", "name": f"etf{i}", "relation": RELATION_DIRECT}
        for i in range(10)
    }
    ranked = [(f"S{i}", float(10 - i)) for i in range(10)]
    out = build_etf_candidates(ranked, mapping, top_n=3)
    assert len(out) == 3


def test_passthrough_sector_weights_explicit():
    entry = {"sector_weights": {"A": 0.6, "B": 0.4}}
    w = passthrough_sector_weights(entry, ["A", "B"])
    assert w == pytest.approx({"A": 0.6, "B": 0.4})


def test_passthrough_sector_weights_equal_default():
    w = passthrough_sector_weights({}, ["A", "B", "C"])
    assert all(v == pytest.approx(1 / 3) for v in w.values())


# ---------------------------------------------------------------------------
# 未迁移的错误逻辑 / 未实现接口
# ---------------------------------------------------------------------------


def test_apply_risk_budget_not_implemented():
    """风险敞口调整必须为 NOT_IMPLEMENTED。"""
    assert NOT_IMPLEMENTED == "NOT_IMPLEMENTED"
    with pytest.raises(RiskBudgetNotImplemented):
        apply_risk_budget(red_lights=3)


def test_top5_to_top3_logic_not_migrated():
    """legacy 的 Top5→Top3 '降敞口' 逻辑不得迁移。

    该逻辑并未降低总敞口，只是提高集中度。这里用**行为测试**验证：
    选 Top N 后权重仍归一化到 1.0（总敞口不变），且不存在
    「红灯时自动把 top_n 改小」的代码路径。
    """
    from pathlib import Path

    import src.strategies.hikyuu.sw_sector_rotation.ranking as rk

    # ranking 模块不得 import 风险模块（风险必须与 ranking 解耦）
    text = Path(rk.__file__).read_text(encoding="utf-8")
    assert "import" not in text or "src.risk" not in text.replace("``src.risk", ""), (
        "ranking 不得 import 风险模块"
    )
    assert "RiskState" not in text, "ranking 不得依赖 RiskState"

    # 行为验证：无论选几个，权重总和恒为 1.0（不擅自降低总敞口）
    ranked = [("A", 5.0), ("B", 4.0), ("C", 3.0), ("D", 2.0), ("E", 1.0)]
    for n in (3, 5):
        w = sector_scores_to_weights(select_top(ranked, n))
        assert sum(w.values()) == pytest.approx(1.0)


def test_weights_sum_to_one_after_top_selection():
    """选 Top N 后权重仍归一化到 1.0（总敞口不变，不擅自降仓）。"""
    ranked = [("A", 5.0), ("B", 4.0), ("C", 3.0), ("D", 2.0), ("E", 1.0)]
    top = select_top(ranked, 3)
    w = sector_scores_to_weights(top)
    assert sum(w.values()) == pytest.approx(1.0)
    assert len(w) == 3
