"""End-to-end reusable model example, using no runtime data or execution path."""

from __future__ import annotations

import pytest

from examples.minimal_demo.__main__ import run_demo


def test_minimal_demo_is_deterministic_and_respects_frozen_sizing() -> None:
    result = run_demo()
    assert result == run_demo()
    assert result["label"] == "SYNTHETIC DEMO ONLY"
    assert result["external_data_required"] is False
    assert result["broker_enabled"] is result["real_order_path"] is False
    assert result["horizons"] == [10, 40, 120]
    assert result["allocation_status"] == "READY"
    weights = result["weights"]
    assert isinstance(weights, dict)
    assert len(weights) == 5
    assert sum(weights.values()) == pytest.approx(1)
    assert max(weights.values()) <= 0.35 + 1e-12
