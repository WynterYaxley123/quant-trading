"""Synthetic V2 numerical, chronology, namespace and compatibility regressions."""

import json
from dataclasses import asdict, replace
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.etf_quant_v2.coverage import external_directory, immutable_bytes, lake_fingerprint
from research.etf_quant_v2.diagnostics import (
    Standardization,
    dependence,
    feature_geometry,
    moving_block_interval,
    ridge_vs_ols,
)
from research.etf_quant_v2.models import Observation, cache_identity, fit, fuse
from research.etf_quant_v2.protocol import (
    V1_SEALED_FROM,
    MembershipEvidence,
    candidates,
    canonical_hash,
    chronological_split,
    search_specification,
    training_indices,
)
from scripts.engineering.naming import violations
from strategies.etf_quant.config import (
    MAPPING_CONTRACT_PENDING,
    PENDING_DEEPSEEK_CONTRACT,
    PENDING_MIMO_AUDIT,
    PUBLIC_INTEGRATION_REVIEW_PENDING,
)
from strategies.etf_quant.models import NumPyRidge
from strategies.etf_quant.models.fusion import cross_sectional_zscore
from strategies.etf_quant.runtime import RuntimeState


def calendar():
    return tuple(pd.bdate_range("2010-01-01", periods=2400).date)


def test_closed_search_grid_and_frozen_factor_vocabulary():
    grid = candidates()
    assert len(grid) == len({c.identifier for c in grid}) == 120
    assert {c.alpha for c in grid} == {0.001, 0.01, 0.1, 1, 10}
    assert {c.training_months for c in grid} == {6, 12, 24}
    assert all(c.factors(10) == ("d10", "p5", "align", "vc", "dd20") for c in grid)
    assert len(next(c for c in grid if c.family == "D").factors(80)) == 19
    registered = json.loads(
        (
            Path(__file__).resolve().parents[1] / "config/research/etf-quant-v2-search.json"
        ).read_text()
    )
    assert canonical_hash(search_specification()) == registered["specification_sha256"]
    assert canonical_hash(registered["specification"]) == registered["specification_sha256"]


def test_split_and_label_gates_fail_before_sealed_access():
    with pytest.raises(ValueError, match="STRICT_PIT"):
        chronological_split(calendar(), strict_pit_admitted=False)
    split = chronological_split(calendar(), strict_pit_admitted=True)
    assert len(split.validation) == len(split.final_oos) == len(split.label_tail) == 120
    for day in (split.validation[0], split.final_oos[0], V1_SEALED_FROM):
        with pytest.raises(ValueError, match="SEALED"):
            split.guard(day)
    with pytest.raises(ValueError, match="SEALED_LABEL"):
        split.guard(split.development[-1], V1_SEALED_FROM)


@pytest.mark.parametrize("months", [6, 12, 24])
def test_calendar_window_is_anchored_to_horizon_cutoff(months):
    days = calendar()
    indices = training_indices(days, days[1200], 120, months)
    expected_start = (pd.Timestamp(days[1080]) - pd.DateOffset(months=months)).date()
    assert all(expected_start <= days[i] <= days[1080] for i in indices)
    assert indices[-1] + 120 == 1200
    with pytest.raises(ValueError, match="FULL_TRAINING_WINDOW"):
        training_indices(days, days[130], 120, months)


def test_standardization_uses_training_parameters_for_shifted_signal():
    train = np.array([[1, 100], [3, 200], [5, 300]], dtype=float)
    transform = Standardization.fit(train)
    np.testing.assert_allclose(transform.apply(train).mean(axis=0), 0, atol=1e-14)
    signal = np.array([[1000, 10000]], dtype=float)
    np.testing.assert_allclose(transform.apply(signal), (signal - train.mean(0)) / train.std(0))
    assert transform == Standardization.fit(train)
    with pytest.raises(ValueError, match="VARIANCE"):
        Standardization.fit([[1, 2], [1, 3]])


def test_ridge_effect_depends_on_geometry_without_market_conclusion():
    rng = np.random.default_rng(42)
    x = rng.normal(size=(200, 3))
    y = x @ np.array([1.0, -0.5, 0.1])
    small, large = ridge_vs_ols(x * 0.001, y), ridge_vs_ols(x * 100, y)
    assert small["shrinkage_norm_ratio"] < 0.1
    assert large["shrinkage_norm_ratio"] > 0.99
    assert feature_geometry(np.ones((30, 3)))["constant_feature_indices"] == [0, 1, 2]


def test_temporal_dependence_keeps_order_and_does_not_claim_one_sample():
    rng = np.random.default_rng(3)
    returns = rng.normal(size=1800)
    target = np.convolve(returns, np.ones(120), mode="valid")
    result = dependence(target, 120)
    assert 1 < result["ess_positive_sequence"] < len(target)
    assert result["adjacent_label_overlap_fraction"] == 119 / 120
    interval = moving_block_interval(target, replications=100)
    assert interval == moving_block_interval(target, replications=100)
    assert interval[0] < interval[1]
    target[1] = np.nan
    with pytest.raises(ValueError, match="GAP_COMPRESSION"):
        dependence(target, 120)


def test_membership_effective_date_alone_cannot_admit_later_information():
    early = datetime(2015, 1, 1, 16, tzinfo=timezone.utc)
    proof = MembershipEvidence(date(2010, 1, 1), date(2020, 1, 1), early, early, "a" * 64, "b" * 64)
    proof.admit(early)
    with pytest.raises(ValueError, match="MEMBERSHIP_UNSUPPORTED"):
        proof.admit(datetime(2014, 1, 1, 16, tzinfo=timezone.utc))


def test_v2_raw_fit_reuses_frozen_solver_and_excludes_future_row():
    days = calendar()
    split = chronological_split(days, strict_pit_admitted=True)
    candidate = next(c for c in candidates() if c.identifier == "C-RAW-m6-a0.01")
    signal = datetime.combine(days[1200], datetime.min.time(), tzinfo=timezone.utc).replace(hour=16)
    indices = training_indices(days, signal.date(), 10, 6)
    proof_at = datetime(2009, 1, 1, tzinfo=timezone.utc)
    proof = MembershipEvidence(days[0], days[-1], proof_at, proof_at, "a" * 64, "b" * 64)
    rows, universes, x, y = [], {}, [], []
    rng = np.random.default_rng(14)
    for i in indices:
        day = days[i]
        universe = ("1001", "1002", "1003")
        universes[day] = universe
        targets = rng.normal(size=3)
        for code, target in zip(universe, targets):
            features = tuple(rng.normal(size=5))
            instant = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
            label_at = datetime.combine(days[i + 10], datetime.min.time(), tzinfo=timezone.utc)
            rows.append(
                Observation(
                    day,
                    code,
                    features,
                    candidate.factors(10),
                    instant,
                    proof,
                    days[i + 10],
                    label_at,
                    float(target),
                )
            )
            x.append(features)
            y.append(target - targets.mean())
    rows.append(replace(rows[0], day=days[1201], raw_forward_return=float("nan")))
    fitted = fit(
        candidate,
        10,
        rows,
        sessions=days,
        signal_at=signal,
        split=split,
        universe_by_date=universes,
    )
    reference = NumPyRidge(alpha=0.01).fit(x, y)
    np.testing.assert_allclose(fitted.coefficients, reference.coef_, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(fitted.predict(x[:3]), reference.predict(x[:3]))
    rows[0] = replace(rows[0], label_available_at=signal.replace(year=2025))
    with pytest.raises(ValueError, match="FUTURE_TRAINING"):
        fit(
            candidate,
            10,
            rows,
            sessions=days,
            signal_at=signal,
            split=split,
            universe_by_date=universes,
        )


@pytest.mark.parametrize("family", ["A", "B", "C", "D"])
def test_registered_fusion_is_deterministic_complete_and_uses_prediction_zscores(family):
    candidate = next(c for c in candidates() if c.family == family)
    universe = ("5", "1", "2", "4", "3")
    scores = {h: {code: float(code) * h for code in universe} for h in candidate.horizons}
    ranked = fuse(candidate, scores, universe=universe)
    assert [code for code, _ in ranked] == ["5", "4", "3", "2", "1"]
    expected = cross_sectional_zscore([1, 2, 3, 4, 5])
    np.testing.assert_allclose([v for _, v in ranked], expected[::-1])
    scores[candidate.horizons[0]].pop("1")
    with pytest.raises(ValueError, match="UNIVERSE_MISMATCH"):
        fuse(candidate, scores, universe=universe)


def test_legacy_serialized_foundation_state_is_identical():
    assert PENDING_DEEPSEEK_CONTRACT == MAPPING_CONTRACT_PENDING == "PENDING_DEEPSEEK_CONTRACT"
    assert PENDING_MIMO_AUDIT == PUBLIC_INTEGRATION_REVIEW_PENDING == "PENDING_MIMO_AUDIT"
    state = asdict(RuntimeState())
    assert state["data_contract"] == "PENDING_DEEPSEEK_CONTRACT"
    assert state["public_integration"] == "PENDING_MIMO_AUDIT"
    assert state["broker_enabled"] is state["real_order_path"] is False


def test_cache_scope_and_external_immutable_publication(tmp_path):
    key = cache_identity("a" * 64, "b" * 64, ("2010", "2015"), {"scaling": "RAW"})
    assert key != cache_identity("a" * 64, "b" * 64, ("2010", "2015"), {"scaling": "STANDARDIZED"})
    target = tmp_path / "snapshot.json"
    immutable_bytes(target, b"synthetic")
    immutable_bytes(target, b"synthetic")
    with pytest.raises(ValueError, match="CONFLICT"):
        immutable_bytes(target, b"changed")
    (tmp_path / ".git").mkdir()
    with pytest.raises(ValueError, match="EXTERNAL"):
        external_directory(tmp_path)


def test_naming_gate_does_not_exempt_new_transcripts_in_historical_directory(tmp_path):
    names = ["docs/archive/codex_new.md", "docs/handoff.md", "AGENTS.md", "docs/glossary.md"]
    assert violations(tmp_path, names, {}) == names[:2]


def test_capability_fingerprint_never_reads_sealed_or_derived_industry_payload(
    tmp_path, monkeypatch
):
    factual = tmp_path / "curated/daily_bars/synthetic.parquet"
    factual.parent.mkdir(parents=True)
    factual.write_bytes(b"SYNTHETIC FACTUAL BYTES")
    sealed = tmp_path / "derived/industry_index/validation-results.parquet"
    sealed.parent.mkdir(parents=True)
    sealed.write_bytes(b"SYNTHETIC SEALED CANARY")
    original = Path.open

    def guarded(path, *args, **kwargs):
        assert path != sealed, "sealed payload was opened"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    _, files = lake_fingerprint(tmp_path)
    assert list(files) == ["curated/daily_bars/synthetic.parquet"]
