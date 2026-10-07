"""Synthetic-only independent generation, maturity and irreversible access contracts."""

import json
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from research.swl1_ridge_v1.audit import taxonomy
from research.swl1_ridge_v1.data_contract import available_at, equal_weight, parent_at
from research.swl1_ridge_v1.evaluation import directional_label, summarize, validation_pass
from research.swl1_ridge_v1.lifecycle import Lifecycle
from research.swl1_ridge_v1.protocol import (
    Spec,
    body,
    digest,
    exact_targets,
    fit_predict,
    immutable,
    split_sessions,
)
from strategies.etf_quant.config import FACTORS_19
from strategies.industry_forecast.registry import families as generic_families
from strategies.industry_forecast.registry import resolve as resolve_family


def test_taxonomy_discovers_count_and_explicit_named_parent_even_out_of_order(
    monkeypatch, tmp_path
):
    table = pd.DataFrame(
        {
            "行业代码": ["100000", "100100", "200000", "100101"],
            "一级行业名称": ["one", "one", "two", "one"],
        }
    )
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: table)
    workbook = tmp_path / "table.xls"
    workbook.write_bytes(b"synthetic")
    result = taxonomy(workbook)
    assert len(result["industries"]) == 2
    assert parent_at(result, "100101", date(2022, 1, 1)) == "100000"
    with pytest.raises(ValueError, match="BACKFILL"):
        parent_at(result, "100101", date(2020, 1, 1))
    with pytest.raises(ValueError, match="UNSUPPORTED"):
        parent_at(result, "100999", date(2022, 1, 1))


def test_exact_returns_complete_centering_and_missingness():
    returns = np.array([[0.0, 0.0], [0.1, -0.1], [0.2, 0.1], [np.nan, 0.1]])
    targets = exact_targets(returns, 2)
    np.testing.assert_allclose(targets[0], [0.32, -0.01])
    assert np.isnan(targets[1:]).all()
    centered = targets[0] - targets[0].mean()
    assert centered.sum() == pytest.approx(0)
    assert equal_weight({str(i): 0.1 for i in range(5)}) == pytest.approx(0.1)
    assert equal_weight({str(i): (None if i < 2 else 0.1) for i in range(6)}) is None


def test_calendar_split_counts_and_purges_are_exchange_sessions():
    days = pd.bdate_range("2020-01-01", periods=1300).strftime("%Y-%m-%d").tolist()
    split = split_sessions(days, list(range(200, 1180)))
    assert split is not None and split["evaluation_signal_count"] == 252
    phases = split["indices"]
    assert phases["development"][-1] + 120 < phases["validation"][0]
    assert phases["validation"][-1] + 120 < phases["final_oos"][0]
    assert len(phases["final_oos"]) == 252
    fallback = split_sessions(days, list(range(600, 1300)))
    assert fallback is not None and fallback["evaluation_signal_count"] == 126
    assert split_sessions(days, list(range(1000, 1300))) is None


@pytest.fixture
def lifecycle(tmp_path):
    protocol = tmp_path / "protocol.json"
    checksum = immutable(
        protocol, {"split": {"ranges": {"final_oos": {"start": "2028-01-01", "end": "2028-07-01"}}}}
    )
    return Lifecycle(tmp_path / "run", protocol, checksum)


def test_preregistration_and_candidate_guards(lifecycle):
    lifecycle.protocol.write_bytes(b"changed")
    with pytest.raises(ValueError, match="PREREGISTRATION"):
        lifecycle.claim("development")


def test_validation_fail_closes_generation_and_oos_stays_unopened(lifecycle):
    with pytest.raises(ValueError, match="FROZEN_CANDIDATE"):
        lifecycle.claim("validation")
    candidate_hash = lifecycle.freeze_candidate({"spec": "A-m12-a10"})
    lineage = lifecycle.claim("validation")
    assert lineage["candidate_hash"] == candidate_hash
    lifecycle.complete("validation", lineage, {"passed": False})
    with pytest.raises(ValueError, match="REJECT_ALREADY_CONSUMED"):
        lifecycle.claim("validation")
    with pytest.raises(ValueError, match="REVISION_FORBIDDEN"):
        lifecycle.freeze_candidate({"spec": "A-m12-a30"})
    with pytest.raises(ValueError, match="VALIDATION_PASS"):
        lifecycle.claim("final_oos")
    assert not (lifecycle.root / "final_oos.claim.json").exists()


def test_final_oos_pass_gate_consumption_and_hash_lineage(lifecycle):
    lifecycle.freeze_candidate({"spec": "B-m12-a100"})
    validation = lifecycle.claim("validation")
    lifecycle.complete("validation", validation, {"passed": True})
    final = lifecycle.claim("final_oos")
    assert json.loads((lifecycle.root / "final_oos.claim.json").read_bytes())["consumed"]
    lifecycle.complete("final_oos", final, {"directional_label": "MIXED"})
    with pytest.raises(ValueError, match="REJECT_ALREADY_CONSUMED"):
        lifecycle.claim("final_oos")
    (lifecycle.root / "candidate.json").write_bytes(
        body({"protocol_hash": lifecycle.expected_hash, "spec": "tampered"})
    )
    with pytest.raises(ValueError, match="PARENT_MISMATCH"):
        lifecycle.claim("final_oos")


def test_candidate_mutation_after_validation_claim_rejected(lifecycle):
    lifecycle.freeze_candidate({"spec": "A-m12-a10"})
    lineage = lifecycle.claim("validation")
    (lifecycle.root / "candidate.json").write_bytes(b"modified")
    with pytest.raises(ValueError, match="CANDIDATE_BYTES"):
        lifecycle.complete("validation", lineage, {"passed": True})


def test_deterministic_ridge_and_horizon_specific_mature_cutoff():
    rng = np.random.default_rng(71)
    features = rng.normal(size=(700, 11, len(FACTORS_19)))
    targets = rng.normal(size=(700, 11))
    days = pd.bdate_range("2020-01-01", periods=700).strftime("%Y-%m-%d").tolist()
    spec = Spec(10.0, 12, "A")
    result, metadata = fit_predict(features, targets, days, 600, 120, spec)
    assert metadata["mature_label_cutoff"] == days[480]
    assert metadata["training_end"] <= days[480]
    assert metadata["feature_names"] == FACTORS_19
    changed = targets.copy()
    changed[481:] = 1000
    np.testing.assert_array_equal(fit_predict(features, changed, days, 600, 120, spec)[0], result)
    assert digest(result.tobytes()) == digest(
        fit_predict(features, targets, days, 600, 120, spec)[0].tobytes()
    )
    with pytest.raises(ValueError, match="BUDGET"):
        Spec(3, 6, "A")


def test_future_source_not_available():
    decision = datetime(2028, 1, 1, tzinfo=timezone.utc)
    available_at(decision, decision)
    with pytest.raises(ValueError, match="NOT_AVAILABLE"):
        available_at(datetime(2028, 1, 2, tzinfo=timezone.utc), decision)


def test_training_scaler_excludes_future_features_and_labels_remove_daily_market_return():
    rng = np.random.default_rng(94)
    features = rng.normal(size=(700, 8, len(FACTORS_19)))
    features[:, :, 0] = 7.0  # Constant training factor must remain finite.
    targets = rng.normal(size=(700, 8))
    days = pd.bdate_range("2020-01-01", periods=700).strftime("%Y-%m-%d").tolist()
    spec = Spec(100, 12, "B")
    expected, _ = fit_predict(features, targets, days, 600, 120, spec)
    poisoned = features.copy()
    poisoned[481:600] = 1e12
    poisoned[601:] = -1e12
    actual, _ = fit_predict(poisoned, targets, days, 600, 120, spec)
    np.testing.assert_array_equal(actual, expected)
    translated = targets + rng.normal(size=(700, 1)) * 5
    actual, _ = fit_predict(features, translated, days, 600, 120, spec)
    np.testing.assert_allclose(actual, expected, atol=1e-13)


def test_incomplete_industry_drops_whole_training_date_without_short_window_fallback():
    features = np.ones((700, 8, len(FACTORS_19)))
    targets = np.ones((700, 8))
    days = pd.bdate_range("2020-01-01", periods=700).strftime("%Y-%m-%d").tolist()
    spec = Spec(1, 24, "B")
    _, before = fit_predict(features, targets, days, 600, 120, spec)
    targets[450, 0] = np.nan
    _, after = fit_predict(features, targets, days, 600, 120, spec)
    assert after["valid_training_dates"] == before["valid_training_dates"] - 1
    assert after["industry_rows"] == before["industry_rows"] - 8
    targets[:452] = np.nan
    with pytest.raises(ValueError, match="INSUFFICIENT_COMPLETE"):
        fit_predict(features, targets, days, 600, 120, spec)


def test_scientific_negative_paths_and_null_metrics():
    empty = summarize([], 126)
    assert empty["composite_rank_ic"] is None
    assert not validation_pass(empty)
    assert directional_label(empty) == "MIXED"

    def rows(ic):
        return [
            {
                "date": str(i),
                "horizons": {
                    str(h): {"rank_ic": ic, "spread": ic, "top5": ic, "bottom5": 0}
                    for h in (10, 40, 120)
                },
            }
            for i in range(126)
        ]

    positive = summarize(rows(0.1), 126)
    assert validation_pass(positive)
    assert directional_label(positive) == "STRONG_POSITIVE"
    negative = summarize(rows(-0.1), 126)
    assert not validation_pass(negative)
    assert directional_label(negative) == "NEGATIVE"


def test_failed_family_keeps_levels_separate_and_blocks_forward():
    registry = generic_families()
    assert [f["model_universe_size"] for f in registry] == [107, 124, 30, 30]
    failed = resolve_family("swl1-ridge-v1")
    assert failed["taxonomy_universe_size"] == 31
    assert failed["industry_level"] == 1
    assert failed["scientific_status"] == "FAILED_VALIDATION"
    with pytest.raises(ValueError, match="FORWARD_INELIGIBLE"):
        resolve_family("swl1-ridge-v1", require_forward=True)
