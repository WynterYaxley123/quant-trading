"""Adversarial synthetic evidence safety and deterministic frozen-fit accounting."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.swl1_failure_forensics.boundary import (
    LimitedInflater,
    admit,
    boundary,
    contained,
    historical_panel_access,
    npy_prefix,
    sha,
)
from research.swl1_failure_forensics.diagnostics import (
    assert_parity,
    coefficient_accounting,
    comparison_eligibility,
    conditioning,
    effective_dimension,
    loo_ic,
)
from research.swl1_failure_forensics.replay import phase_replay, shared_development
from research.swl1_failure_forensics.report import public_safe, write
from research.swl1_ridge_v1.evaluation import evaluate as evaluate_v1
from research.swl1_ridge_v1.protocol import Spec as SpecV1
from research.swl1_ridge_v1.protocol import exact_targets
from research.swl1_ridge_v2.evaluation import calendar_blocks, extremes, public_metrics
from research.swl1_ridge_v2.evaluation import evaluate as evaluate_v2
from research.swl1_ridge_v2.protocol import Spec as SpecV2


def test_default_audit_never_reads_numeric_members_or_mutates_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from research.swl1_failure_forensics import __main__ as cli
    from research.swl1_ridge_v1.lifecycle import Lifecycle as LifecycleV1
    from research.swl1_ridge_v2.lifecycle import Lifecycle as LifecycleV2

    repo, evidence = tmp_path / "repo", tmp_path / "evidence"
    repo.mkdir()
    evidence.mkdir()
    dates = pd.bdate_range("2020-01-01", periods=400).strftime("%Y-%m-%d").tolist()
    codes = [str(i).zfill(6) for i in range(30)]
    panel = evidence / "factual_panel.npz"
    # Numeric fields deliberately invalid: a default audit must not touch them.
    np.savez_compressed(
        panel, dates=dates, codes=codes, returns=np.array([object()]), features=np.array([object()])
    )
    frozen = {}
    for version in ("v1", "v2"):
        protocol = {
            "implementation_hashes": {},
            "model_universe": codes,
            "split": {"indices": {"development": [150], "validation": [200]}},
        }
        for kind, value in (("protocol", protocol), ("candidate", {})):
            name = f"config/research/swl1-ridge-{version}-{kind}.json"
            write(repo / name, value)
            frozen[name] = sha(repo / name)
    write(repo / "reports/research/swl1_ridge_v1/data_feasibility.json", {"trading_sessions": 400})
    monkeypatch.setattr(cli, "FROZEN", frozen)
    monkeypatch.setattr(cli, "PANEL_SHA", sha(panel))
    calls = []
    original = cli.npy_prefix

    def observe(path: Path, member: str, rows: int, allowed: int):
        calls.append(member)
        assert member in ("dates.npy", "codes.npy")
        return original(path, member, rows, allowed)

    def forbid(*args, **kwargs):
        raise AssertionError("Official lifecycle mutation is forbidden")

    monkeypatch.setattr(cli, "npy_prefix", observe)
    for lifecycle in (LifecycleV1, LifecycleV2):
        for method in ("claim", "freeze_candidate", "complete"):
            monkeypatch.setattr(lifecycle, method, forbid)
    before = {str(p): sha(p) for p in tmp_path.rglob("*") if p.is_file()}
    result = cli.run(repo, evidence)
    after = {str(p): sha(p) for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after
    assert calls == ["dates.npy", "codes.npy"]
    assert result["boundary"]["union_last_outcome"] == dates[320]


def test_immutable_evidence_and_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    path.write_text('{"closed": true}')
    frozen = sha(path)
    assert admit(tmp_path, path.name, frozen) == {"closed": True}
    path.write_text('{"closed": false}')
    with pytest.raises(ValueError, match="HASH_MISMATCH"):
        admit(tmp_path, path.name, frozen)


def test_unavailable_and_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        contained(tmp_path, "missing.json")
    with pytest.raises(ValueError, match="PATH_BLOCKED"):
        contained(tmp_path, "../private.json")


def test_symlink_rejected_even_internal(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("{}")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="SYMLINK"):
        contained(tmp_path, "link")


def test_exact_h120_boundary_and_future_separation() -> None:
    dates = pd.bdate_range("2020-01-01", periods=400).strftime("%Y-%m-%d").tolist()
    protocols = {
        "v1": {"split": {"indices": {"development": [150], "validation": [200]}}},
        "v2": {"split": {"indices": {"development": [180], "validation": [250]}}},
    }
    result = boundary(dates, protocols)
    assert result["generations"]["v1"]["last_outcome"] == dates[320]
    assert result["union_last_outcome"] == dates[370]
    tail = result["outcomes_beyond_declared_consumption"]
    assert tail["first"] == dates[371]
    assert tail["independently_unseen_sessions_certified"] == 0
    assert tail["historical_unseen_status"] == "NOT_CERTIFIED_BY_DATE_ARITHMETIC"
    assert result["permitted_return_rows"] == 371
    assert result["permitted_feature_rows"] == 251


def test_historical_full_panel_access_is_source_evidence_only(tmp_path: Path) -> None:
    name = "research/swl1_ridge_v1/execute.py"
    source = tmp_path / name
    source.parent.mkdir(parents=True)
    source.write_text(
        'raise AssertionError("must never execute this file")\n'
        'data = np.load("missing-private-panel.npz", allow_pickle=False)\n'
        'features, returns = data["features"], data["returns"]\n'
    )
    result = historical_panel_access(tmp_path, {name: sha(source)})
    assert result["sources"][name]["full_numeric_members_materialized"]
    assert result["sources"][name]["numeric_member_lines"]["returns"] == [3]
    assert not result["historical_unseen_access_certified"]
    source.write_text("changed")
    with pytest.raises(ValueError, match="IMPLEMENTATION_HASH_MISMATCH"):
        historical_panel_access(tmp_path, {name: "0" * 64})


def test_missing_historical_source_never_certifies_independence(tmp_path: Path) -> None:
    result = historical_panel_access(tmp_path, {})
    assert result["sources"] == {}
    assert not result["historical_unseen_access_certified"]


def test_immature_or_unsorted_boundary_rejected() -> None:
    dates = pd.bdate_range("2020-01-01", periods=130).strftime("%Y-%m-%d").tolist()
    p = {"v1": {"split": {"indices": {"development": [1], "validation": [20]}}}}
    with pytest.raises(ValueError, match="UNAVAILABLE_MATURE"):
        boundary(dates, p)
    with pytest.raises(ValueError, match="SPINE"):
        boundary(dates[::-1], p)


def test_adversarial_unseen_tail_never_inflated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "panel.npz"
    values = np.arange(40.0).reshape(10, 4)
    values[-1] = 987654321.0  # Explicit adversarial future return.
    np.savez_compressed(path, returns=values)
    decoded = []
    original = LimitedInflater.read

    def observe(self: LimitedInflater, size: int) -> bytes:
        result = original(self, size)
        decoded.append(self.decoded_bytes)
        return result

    monkeypatch.setattr(LimitedInflater, "read", observe)
    actual, receipt = npy_prefix(path, "returns.npy", 9, 9)
    np.testing.assert_array_equal(actual, values[:9])
    assert receipt["payload_bytes_decoded"] == 9 * 4 * 8
    assert receipt["tail_rows_not_decoded"] == 1
    assert max(decoded) == 128 + 9 * 4 * 8
    with pytest.raises(ValueError, match="UNSEEN_OUTCOME"):
        npy_prefix(path, "returns.npy", 10, 9)


def test_unbounded_reads_blocked() -> None:
    with pytest.raises(ValueError, match="UNBOUNDED"):
        LimitedInflater(b"", 0).read(-1)


def test_fortran_unseen_tail_redacted_before_numeric_conversion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "panel.npz"
    values = np.asfortranarray(np.arange(30.0).reshape(10, 3))
    values[-1] = 987654321.0
    np.savez_compressed(path, returns=values)
    converted = []
    original = np.frombuffer

    def observe(buffer: bytes, **kwargs: object) -> np.ndarray:
        result = original(buffer, **kwargs)
        converted.extend(result.tolist())
        return result

    monkeypatch.setattr(np, "frombuffer", observe)
    actual, receipt = npy_prefix(path, "returns.npy", 9, 9)
    np.testing.assert_array_equal(actual, values[:9])
    assert 987654321.0 not in converted
    assert len(converted) == 27
    assert receipt["payload_bytes_decoded"] == 27 * 8
    assert receipt["opaque_layout_bytes_discarded_without_numeric_conversion"] == 16
    with pytest.raises(ValueError, match="UNSEEN"):
        npy_prefix(path, "returns.npy", 10, 9)


@pytest.mark.parametrize("member", ["closes.npy", "future.npy"])
def test_nonwhitelisted_npz_members(tmp_path: Path, member: str) -> None:
    with pytest.raises(ValueError, match="WHITELIST"):
        npy_prefix(tmp_path / "missing.npz", member, 1, 1)


@pytest.mark.parametrize("values", [np.array([object()], dtype=object)])
def test_unsafe_npy_layout(tmp_path: Path, values: np.ndarray) -> None:
    path = tmp_path / "panel.npz"
    np.savez_compressed(path, returns=values)
    with pytest.raises(ValueError, match="LAYOUT"):
        npy_prefix(path, "returns.npy", 1, 1)


def test_raw_target_alignment_and_centering() -> None:
    returns = np.array([[99, 99], [0.1, 0.2], [0.2, -0.1], [0.3, 0.1]])
    actual = exact_targets(returns, 2)
    np.testing.assert_allclose(actual[0], [1.1 * 1.2 - 1, 1.2 * 0.9 - 1])
    centered = actual[0] - actual[0].mean()
    assert abs(centered.mean()) < 1e-15
    assert np.isnan(actual[-2:]).all()


def test_condition_and_effective_df() -> None:
    z = np.array([[1.0, 0.0], [-1.0, 0.0], [0.0, 1.0], [0.0, -1.0]])
    result = conditioning(z, 2.0)
    assert result["effective_df_slope"] == pytest.approx(1.0)
    assert result["condition_regularized"] == pytest.approx(1.0)
    assert result["alpha_per_row"] == 0.5
    assert result["intercept_df"] == 1


def test_correlated_and_constant_factors() -> None:
    z = np.column_stack([np.arange(10.0), np.arange(10.0), np.zeros(10)])
    result = conditioning(z, 100.0)
    assert result["condition_unregularized"] is None
    assert np.isfinite(result["condition_regularized"])
    assert 0 < result["effective_df_slope"] < 1


def test_standardized_contribution_accounting() -> None:
    z = np.array([[1.0, 2.0, 0.0], [-1.0, -2.0, 0.0]])
    result = coefficient_accounting(z, np.array([0.1, 0.2, 9.0]))
    assert result["accounting_max_error"] < 1e-15
    assert result["prediction_std"] == pytest.approx(0.5)
    assert result["contribution_l1_shares"] == pytest.approx([0.2, 0.8, 0.0])


def test_missing_coefficients() -> None:
    assert (
        coefficient_accounting(np.zeros((2, 2)), None)["status"]
        == "NOT_COMPUTABLE_WITH_ADMITTED_EVIDENCE"
    )


def test_deterministic_ties_and_calendar_blocks() -> None:
    top, bottom = extremes(np.zeros(6), ["f", "e", "d", "c", "b", "a"], 2)
    assert top.tolist() == bottom.tolist() == [5, 4]
    assert calendar_blocks(
        ["2020-01-01", "2020-01-03", "2020-01-09"], "2020-01-01", "2020-01-09"
    ) == [0, 1, 3]


def test_covariance_and_leave_one_out() -> None:
    x = np.arange(10.0)
    assert effective_dimension(np.column_stack([x, x])) == pytest.approx(1.0)
    assert loo_ic(x, x)["maximum_absolute_ic_change"] < 1e-14


def test_period_mismatch_cannot_identify_model_effect() -> None:
    base = {
        key: "same"
        for key in (
            "universe",
            "panel",
            "dates",
            "horizon",
            "target",
            "outcomes",
            "evaluation",
            "role",
        )
    }
    other = {**base, "dates": "different", "outcomes": "different"}
    eligibility = comparison_eligibility(base, other)
    assert not all(eligibility.values())
    assert all(comparison_eligibility(base, base).values())
    # Same model has very different IC in two periods; no shared dates exists.
    left = {"rows": [{"date": "2020-01-01", "rank_ic": 0.9}]}
    right = {"rows": [{"date": "2021-01-01", "rank_ic": -0.9}]}
    assert shared_development(left, right)["status"] == "NOT_COMPUTABLE_WITH_ADMITTED_EVIDENCE"


def test_replay_parity_failure() -> None:
    with pytest.raises(ValueError, match="PARITY_FAILURE"):
        assert_parity({"ic": 0.2}, {"ic": 0.1})
    with pytest.raises(ValueError, match="PARITY_FAILURE"):
        assert_parity({"missing": []}, {"missing": [None]})


@pytest.mark.parametrize(
    "value",
    [
        {"predictions": [1]},
        {"nested": {"membership": []}},
        {"values": list(range(101))},
        {"ic": float("nan")},
    ],
)
def test_private_or_nonfinite_report_blocked(value: object) -> None:
    with pytest.raises(ValueError):
        public_safe(value)


def test_public_safe_deterministic_json(tmp_path: Path) -> None:
    path = tmp_path / "summary.json"
    value = {"count": 30, "mean_ic": None, "label": "POST_HOC_FAILURE_FORENSICS"}
    write(path, value, public=True)
    first = path.read_bytes()
    write(path, dict(reversed(list(value.items()))), public=True)
    assert first == path.read_bytes()
    assert json.loads(first) == value


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_full_synthetic_replay_without_lifecycle_mutation(tmp_path: Path, version: str) -> None:
    rng = np.random.default_rng(9)
    features = rng.normal(size=(440, 30, 19))
    features[:, :, -1] = 1  # Constant factor must be stable.
    returns = rng.normal(0, 0.01, size=(440, 30))
    dates = pd.bdate_range("2020-01-01", periods=440).strftime("%Y-%m-%d").tolist()
    codes = [str(i).zfill(6) for i in range(30)]
    signals = list(range(300, 308))
    selected = (
        {"alpha": 100.0, "months": 12, "policy": "B"}
        if version == "v1"
        else {"penalty": 10.0, "months": 24, "policy": "B"}
    )
    expected = (
        evaluate_v1(features, returns, dates, codes, signals, SpecV1(**selected))
        if version == "v1"
        else public_metrics(
            evaluate_v2(features, returns, dates, codes, signals, SpecV2(**selected), "development")
        )
    )
    sentinel = tmp_path / "candidate.json"
    sentinel.write_text('{"frozen":true}')
    before = sentinel.read_bytes()
    result, trace = phase_replay(
        version,
        "development",
        features,
        returns,
        dates,
        codes,
        signals,
        selected,
        copy.deepcopy(expected),
    )
    assert result["parity"] == "PASS"
    assert result["prediction_max_absolute_reconstruction_error"] < 1e-12
    assert sentinel.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["candidate.json"]
    public_safe(result)
    assert len(trace["fits"]) == 24
