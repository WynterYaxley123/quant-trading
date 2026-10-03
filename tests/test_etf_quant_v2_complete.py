"""Meaningful temporal, numerical, evidence-quality and forward isolation checks."""

from dataclasses import replace
from datetime import date, datetime, timezone

import numpy as np
import pytest

from research.etf_quant_v2.experiment import (
    ExperimentSplit,
    SufficientStatistics,
    bootstrap,
    component,
    make_split,
    targets,
    validation_open,
)
from research.etf_quant_v2.membership import EvidenceTier, HistoricalEvidence, overlap
from strategies.etf_quant.models import NumPyRidge
from strategies.etf_quant_v2.runtime import publish_forward_plan


def test_tiers_do_not_forge_historical_availability():
    evidence = HistoricalEvidence(
        "https://official.example/history",
        "a" * 64,
        date(2020, 1, 1),
        datetime(2026, 10, 4, tzinfo=timezone.utc),
        True,
        True,
        0.99,
    )
    assert evidence.tier(date(2022, 1, 1)) == EvidenceTier.B
    assert evidence.tier(date(2020, 1, 1)) == EvidenceTier.C
    assert replace(evidence, historical_spells=False).tier(date(2022, 1, 1)) == EvidenceTier.D
    assert replace(evidence, completeness_ratio=0.9).tier(date(2022, 1, 1)) == EvidenceTier.C
    published = replace(evidence, published_at=evidence.observed_at)
    assert published.tier(date(2026, 10, 5)) == EvidenceTier.A
    assert published.tier(date(2026, 10, 3)) == EvidenceTier.B


def test_overlap_identifies_assignment_errors_and_dependency():
    result = overlap({"x": "1", "y": "2"}, {"x": "2", "z": "3"}, independent=False)
    assert result["membership_jaccard"] == pytest.approx(1 / 3)
    assert result["industry_assignment_error"] == 1
    assert result["disagreement_rate"] == 1
    assert result["status"] == "DEPENDENT_SOURCE_COMPARISON"


@pytest.mark.parametrize("standardized", [False, True])
@pytest.mark.parametrize("alpha", [0.001, 0.01, 1, 10])
def test_sufficient_statistics_matches_existing_ridge(standardized, alpha):
    rng = np.random.default_rng(41)
    x = rng.normal(size=(65, 15, 5)) * np.array([0.01, 0.2, 1, 7, 100])
    y = rng.normal(size=(65, 15))
    coef, intercept, mean, std = SufficientStatistics(x, y).fit(5, 55, alpha, standardized)
    values, target = x[5:56].reshape(-1, 5), y[5:56].ravel()
    reference = NumPyRidge(alpha).fit((values - mean) / std if standardized else values, target)
    actual = values / std @ coef + intercept
    expected = reference.predict((values - mean) / std if standardized else values)
    np.testing.assert_allclose(actual, expected, atol=1e-8, rtol=1e-8)


def test_prefix_fit_cannot_consume_future_mutation():
    rng = np.random.default_rng(12)
    x, y = rng.normal(size=(70, 12, 3)), rng.normal(size=(70, 12))
    before = SufficientStatistics(x, y).fit(0, 40, 0.1, True)
    x[41:], y[41:] = 1e8, -1e8
    after = SufficientStatistics(x, y).fit(0, 40, 0.1, True)
    for a, b in zip(before, after):
        np.testing.assert_allclose(a, b)


def test_phase_labels_and_final_oos_are_denied():
    split = ExperimentSplit(0, 100, 221, 300, 421, 480, 481)
    x, closes = np.ones((650, 12, 19)), np.arange(1, 651, dtype=float)[:, None] * np.ones((1, 12))
    segments = np.zeros_like(closes, dtype=np.int64)
    dev = targets(x, closes, segments, 40, split, "DEVELOPMENT")
    assert np.isnan(dev[101:]).all()
    with pytest.raises(ValueError, match="FINAL_OOS"):
        targets(x, closes, segments, 40, split, "FINAL_OOS")
    with pytest.raises(ValueError, match="PHASE_LABEL"):
        split.permit("DEVELOPMENT", [101])


def test_gapped_industry_targets_are_not_bridged_or_cherry_picked():
    split = ExperimentSplit(0, 100, 221, 300, 421, 480, 481)
    x, closes = np.ones((650, 12, 19)), np.exp(np.arange(650)[:, None] / 1000) * np.ones((1, 12))
    segments = np.zeros_like(closes, dtype=np.int64)
    segments[15:, 0] = 1
    y = targets(x, closes, segments, 10, split, "DEVELOPMENT")
    assert np.isnan(y[10]).all()
    assert np.isfinite(y[20]).all()


def test_validation_is_resumable_but_cannot_switch_candidate(tmp_path):
    validation_open(tmp_path, {"candidate": "first"})
    validation_open(tmp_path, {"candidate": "first"})
    with pytest.raises(ValueError, match="CANNOT_BE_REPLACED"):
        validation_open(tmp_path, {"candidate": "second"})


def test_bootstrap_retains_calendar_missingness():
    values = np.linspace(-1, 1, 480)
    values[180:200] = np.nan
    result = bootstrap(values)
    assert result["calendar_missing_sessions"] == 20
    assert result["replications"] == 1000
    assert result["bootstrap_ess"] <= 460


def test_component_scaling_is_training_only_and_uses_shared_current_universe():
    rng = np.random.default_rng(51)
    x, y = rng.normal(size=(500, 15, 3)), rng.normal(size=(500, 15))
    dates = np.datetime_as_string(
        np.arange(np.datetime64("2020-01-01"), np.datetime64("2020-01-01") + 500), unit="D"
    ).tolist()
    mask = np.ones((500, 15), dtype=bool)
    mask[450, 0] = False
    first = component(x, y, dates, 40, 6, 1, "TRAIN_ONLY_STANDARDIZED", range(450, 451), mask)
    x[451:], y[451:] = 1e6, -1e6
    second = component(x, y, dates, 40, 6, 1, "TRAIN_ONLY_STANDARDIZED", range(450, 451), mask)
    np.testing.assert_allclose(first[0][450], second[0][450])
    assert np.isnan(first[0][450, 0])
    assert np.std(first[0][450, 1:]) == pytest.approx(1)


def test_split_separates_long_labels_without_v1_sealed_development():
    dates = np.datetime_as_string(
        np.arange(np.datetime64("2018-01-01"), np.datetime64("2026-09-25")), unit="D"
    ).tolist()
    split = make_split(dates)
    assert split.development_end + 120 < split.validation_start
    assert split.validation_end + 120 < split.final_oos_start
    assert dates[split.development_end + 120] < "2026-03-03"


def test_no_implicit_shadow_launch_or_v1_namespace(tmp_path):
    plan = {
        "product": "ETF_QUANT_V2",
        "signal_date": "2026-10-09",
        "broker_enabled": False,
        "real_order_path": False,
    }
    frozen = datetime(2026, 10, 4, tzinfo=timezone.utc)
    now = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="AUTHORIZATION"):
        publish_forward_plan(
            tmp_path / "etf-quant-v2", plan, authorization=False, frozen_at=frozen, now=now
        )
    with pytest.raises(ValueError, match="INDEPENDENT"):
        publish_forward_plan(
            tmp_path / "etf-quant-v1" / "etf-quant-v2",
            plan,
            authorization=True,
            frozen_at=frozen,
            now=now,
        )
    assert not list(tmp_path.rglob("plan.json"))
