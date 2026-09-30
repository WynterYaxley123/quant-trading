from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timezone
from decimal import Decimal
import importlib
import ast
from pathlib import Path

import pytest

from strategies.etf_quant import StrategyConfig, StrategyRunMetadata
from strategies.etf_quant.config import FACTORS_19, H10_FACTORS, FUSION_WEIGHTS
from strategies.etf_quant.domain import (BenchmarkId, ETFMapping, Horizon, HorizonModelSpec,
    MappingAdmission, Product, RunMode, TransactionCost)
from strategies.etf_quant.mapping import validate_candidate
from strategies.etf_quant.runtime import RuntimeState
from strategies.etf_quant.schemas import to_json, to_primitive

NOW = datetime(2026, 1, 2, 17, tzinfo=timezone.utc)


def test_frozen_config():
    config = StrategyConfig()
    assert config.product is Product.ETF_QUANT and config.mode is RunMode.SIMULATION_ONLY
    assert config.initial_cash == Decimal('10000') and config.currency == 'CNY'
    assert config.fusion_weights == FUSION_WEIGHTS == ((10, .25), (40, .5), (120, .25))
    assert config.top_k == 5 and config.max_target_weight == .35
    assert tuple(s.horizon for s in config.horizons) == tuple(Horizon)
    assert config.horizons[0].factor_names == H10_FACTORS == ('d10', 'p5', 'align', 'vc', 'dd20')
    assert config.horizons[1].factor_names == config.horizons[2].factor_names == FACTORS_19
    assert len(FACTORS_19) == 19 and len(set(FACTORS_19)) == 19
    assert all(s.alpha == .01 and s.training_window_months == 6 and s.minimum_valid_training_days == 30
               for s in config.horizons)
    assert config.costs == TransactionCost(Decimal(3), Decimal(5), Decimal(0), Decimal(0))
    with pytest.raises(FrozenInstanceError): config.top_k = 3


@pytest.mark.parametrize('changes', [
    {'mode': 'LIVE'}, {'product': 'SHENWAN_F1'}, {'top_k': 4}, {'max_target_weight': .5},
    {'initial_cash': '5000'}, {'currency': 'USD'}, {'model_name': 'Other'},
    {'fusion_weights': ((10, .5), (40, .25), (120, .25))}, {'horizons': ()},
])
def test_config_rejects_baseline_or_identity_drift(changes):
    with pytest.raises(ValueError): replace(StrategyConfig(), **changes)


@pytest.mark.parametrize('changes', [
    {'alpha': 1.0}, {'alpha': float('nan')}, {'alpha': True},
    {'training_window_months': 5}, {'minimum_valid_training_days': 29},
    {'factor_names': FACTORS_19}, {'factor_names': tuple(reversed(H10_FACTORS))},
    {'target_identity': 'ABSOLUTE_RETURN'},
])
def test_horizon_spec_drift_rejected(changes):
    with pytest.raises(ValueError): replace(StrategyConfig().horizons[0], **changes)


@pytest.mark.parametrize('changes', [{'commission_bps': '-1'}, {'slippage_bps': '10000'},
                                    {'minimum_commission': float('nan')}, {'stamp_duty_bps': True}])
def test_cost_config_invalid(changes):
    with pytest.raises(ValueError): TransactionCost(**changes)


def test_metadata_json_does_not_invent_provenance():
    record = StrategyRunMetadata('SYNTHETIC_ONLY', NOW)
    body = to_primitive(record)
    assert body['product'] == 'ETF_QUANT' and body['mode'] == 'SIMULATION_ONLY'
    assert body['implementation_commit'] is body['data_snapshot'] is body['provider_identity'] is None
    assert 'null' in to_json(record)
    assert not body['broker_enabled'] and not body['real_order_path']
    with pytest.raises(ValueError): replace(record, broker_enabled=True)
    with pytest.raises(ValueError): replace(record, real_order_path=True)
    with pytest.raises(ValueError): replace(record, created_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError): replace(record, implementation_commit='unknown')
    with pytest.raises(ValueError): replace(record, provider_identity='')
    with pytest.raises(ValueError): to_json({'value': float('nan')})


def test_mapping_unknowns_and_contract_stay_deferred():
    row = ETFMapping('SYN_INDUSTRY_A')
    result = validate_candidate(row)
    assert result.status is MappingAdmission.INCOMPLETE
    assert 'UNKNOWN:effective_from' in result.reasons and 'UNKNOWN:available_at' in result.reasons
    assert row.etf_code is row.effective_from is row.verified_at is None
    assert 'PENDING_DEEPSEEK_CONTRACT' in result.reasons
    with pytest.raises(ValueError): replace(row, admission_status=MappingAdmission.ADMITTED)
    with pytest.raises(ValueError): replace(row, effective_to=date(2020, 1, 1))
    with pytest.raises(ValueError): replace(row, mapping_confidence=1.1)
    with pytest.raises(ValueError): replace(row, etf_code='')
    complete = replace(row, industry_name='Synthetic only', etf_code='SYN_ETF_A', etf_name='Synthetic only',
        mapping_method='SYNTHETIC_TEST', tracking_index_code='SYN_INDEX', tracking_index_name='Synthetic',
        effective_from=date(2020, 1, 1), verified_at=NOW, available_at=NOW, mapping_confidence=1.0)
    assert validate_candidate(complete).status is MappingAdmission.PENDING_CONTRACT


def test_ports_and_benchmarks_have_no_implementations():
    runtime = importlib.import_module('strategies.etf_quant.runtime')
    assert {b.value for b in BenchmarkId} == {'CSI_300', 'NASDAQ_COMPOSITE', 'SP_500'}
    for name in ('IndustryDataProvider', 'ETFUniverseProvider', 'TradingCalendarProvider',
                 'BenchmarkDataProvider', 'IndustryETFMapper'):
        port = getattr(runtime, name)
        assert port._is_protocol
        with pytest.raises(TypeError): port()
    state = RuntimeState()
    assert state.phase == 'FOUNDATION_ONLY' and not state.broker_enabled and not state.real_order_path
    with pytest.raises(ValueError): replace(state, phase='RUNNING')
    with pytest.raises(ValueError): replace(state, data_contract='READY')
    with pytest.raises(ValueError): replace(state, broker_enabled=True)


def test_core_import_firewall_and_no_provider_urls():
    root = Path(__file__).resolve().parents[2] / 'strategies/etf_quant'
    forbidden = {'research', 'src', 'requests', 'http', 'urllib', 'socket', 'subprocess',
                 'hikyuu', 'rqalpha', 'sklearn', 'akshare', 'cnequity'}
    for path in root.rglob('*.py'):
        text = path.read_text()
        assert 'https://' not in text and 'http://' not in text and 'cnequity' not in text.lower()
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import):
                assert all(a.name.split('.')[0] not in forbidden for a in node.names)
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                assert (node.module or '').split('.')[0] not in forbidden
