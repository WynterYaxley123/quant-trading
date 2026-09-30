import json
from pathlib import Path

from strategies.etf_quant.runtime.view import public_strategy


def test_api_no_runtime_frozen_strategy_matches_core_exactly():
    root = Path(__file__).resolve().parents[2]
    actual = json.loads((root / "services/etf-quant-api/strategy.json").read_bytes())
    assert actual == public_strategy()
