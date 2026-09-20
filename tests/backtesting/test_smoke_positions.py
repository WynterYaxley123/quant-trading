"""报告字段回归：仅测试对象，不生成任何真实执行验收结果。"""
from types import SimpleNamespace

import pytest

from src.backtesting.hikyuu_runner import positions_from_tm


def test_positions_use_dated_engine_snapshots_not_closed_record_defaults():
    days = [SimpleNamespace(year=2024, month=1, day=d) for d in (2, 3)]
    stock = SimpleNamespace(market="SH", code="510300")
    class TM:
        def get_position(self, d, s):
            assert s is stock
            return SimpleNamespace(number=1000 if d.day == 2 else 0)
        def get_funds(self, d):
            return SimpleNamespace(cash=96000 if d.day == 2 else 100100,
                                   market_value=4000 if d.day == 2 else 0)
    out = positions_from_tm(TM(), days, stock)
    assert out["datetime"].tolist() == ["2024-01-02", "2024-01-03"]
    assert out["number"].tolist() == [1000, 0]
    assert out["cash"].tolist() == [96000, 100100]
    assert out["symbol"].tolist() == ["sh510300", "sh510300"]
    assert "price" not in out  # 不存在的平均成本字段不得补零


def test_position_api_failure_is_not_silently_empty():
    class TM:
        def get_position(self, d, s):
            raise RuntimeError("API failure")
    with pytest.raises(RuntimeError, match="API failure"):
        positions_from_tm(TM(), [object()], object())
