"""Synthetic-only gates for the preregistered Factor Alpha Audit V1 protocol."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy import stats as scipy_stats

from research import factor_alpha_audit_v1_protocol as protocol
from research.sector_development_baseline import EXPECTED_FEATURES
from research.sector_development_protocol import canonical_hash
from strategies.sw_sector_rotation.src.common.temporal_integrity import make_forward_label

FROZEN_ORDER = (
    "d5", "d10", "d20", "d60", "d120", "p5", "p10", "p20", "p60", "p120",
    "align", "v5", "v20", "vc", "rev5", "rev10", "dd20", "dd60", "rsi",
)


def test_factor_order_is_frozen_and_identical_to_ridge_input(monkeypatch):
    assert protocol.FACTOR_ORDER == FROZEN_ORDER
    assert tuple(EXPECTED_FEATURES) == FROZEN_ORDER
    assert len(protocol.FACTOR_ORDER) == 19
    payload = protocol.verify_frozen_factor_alpha_audit_v1_protocol()
    assert payload["factors"]["factor_order"] == list(FROZEN_ORDER)
    assert payload["factors"]["identical_to_ridge_input"] is True
    monkeypatch.setattr(protocol, "FACTOR_ORDER", FROZEN_ORDER[:-1])
    with pytest.raises(ValueError, match="FACTOR_ORDER_FROZEN_VIOLATION"):
        protocol.guard_audit_scope("development", [1])
    monkeypatch.setattr(protocol, "FACTOR_ORDER", FROZEN_ORDER)
    with pytest.raises(ValueError, match="FACTOR_AUDIT_BASELINE_IDENTITY_MISMATCH"):
        monkeypatch.setattr(protocol, "FACTOR_ORDER", FROZEN_ORDER[:-1])
        protocol.factor_alpha_audit_v1_payload()


def test_only_development_ordinals_are_evaluable():
    protocol.guard_audit_scope("development", [1, 50, 100])
    with pytest.raises(PermissionError, match="PURGED_ORDINAL_ACCESS_ERROR"):
        protocol.guard_audit_scope("development", [101])
    with pytest.raises(PermissionError, match="SEALED_PHASE_ACCESS_ERROR"):
        protocol.guard_audit_scope("development", [221])
    with pytest.raises(PermissionError, match="SEALED_PHASE_ACCESS_ERROR"):
        protocol.guard_audit_scope("development", [401])
    with pytest.raises(PermissionError, match="SEALED_PHASE_ACCESS_ERROR"):
        protocol.guard_audit_scope("validation", [221])


def test_endpoint_semantics_no_shift_no_fill():
    index = pd.date_range("2025-01-01", periods=20, freq="D")
    close = pd.Series(np.arange(1.0, 21.0), index=index)
    label = make_forward_label(close, 5, calendar=index)
    assert label.loc[index[0]] == pytest.approx(close.loc[index[5]] / close.loc[index[0]] - 1.0)
    assert label.loc[index[14]] == pytest.approx(close.loc[index[19]] / close.loc[index[14]] - 1.0)
    assert bool(np.isnan(label.loc[index[15]]))  # endpoint beyond calendar: missing, not shifted
    # Sector misses a bar inside the common calendar: its endpoint never moves or fills.
    gapped_close = close.drop(index[10])
    gapped = make_forward_label(gapped_close, 5, calendar=index)
    assert bool(np.isnan(gapped.loc[index[5]]))  # endpoint index[10] has no bar
    assert gapped.loc[index[6]] == pytest.approx(close.loc[index[11]] / close.loc[index[6]] - 1.0)
    assert gapped.loc[index[9]] == pytest.approx(close.loc[index[14]] / close.loc[index[9]] - 1.0)
    assert index[10] not in gapped.index  # origin bar missing: no row, never filled


def test_min_valid_sector_pairs_is_thirty_and_skips_below():
    x = np.arange(30, dtype=float)
    y = 2.0 * x
    assert protocol.MIN_VALID_SECTOR_PAIRS == 30
    result = protocol.cross_sectional_ic(x, y)
    assert result["skipped"] is False and result["valid_pairs"] == 30
    short = protocol.cross_sectional_ic(x[:29], y[:29])
    assert short["skipped"] is True and short["ic"] is None and short["rankic"] is None
    assert short["skip_reason"] == "below_min_valid_sector_pairs"


def test_pearson_ic_and_spearman_rankic_match_scipy_with_ties():
    rng = np.random.default_rng(20260925)
    x = rng.normal(size=40)
    y = 0.5 * x + rng.normal(scale=0.3, size=40)
    x = np.round(x, 0)  # force ties so average-rank handling is exercised
    result = protocol.cross_sectional_ic(x, y)
    expected_ic = float(scipy_stats.pearsonr(x, y).statistic)
    expected_rankic = float(scipy_stats.spearmanr(x, y).statistic)
    assert result["ic"] == pytest.approx(expected_ic, abs=1e-12)
    assert result["rankic"] == pytest.approx(expected_rankic, abs=1e-12)
    zero_variance = protocol.cross_sectional_ic(np.ones(40), y)
    assert zero_variance["skipped"] is True
    assert zero_variance["skip_reason"] == "zero_cross_sectional_variance"


def test_missingness_is_excluded_not_imputed():
    x = np.arange(40, dtype=float)
    y = 2.0 * x
    x_missing = x.copy()
    x_missing[3] = np.nan
    y_missing = y.copy()
    y_missing[7] = np.inf
    result = protocol.cross_sectional_ic(x_missing, y_missing)
    reference = protocol.cross_sectional_ic(np.delete(x, [3, 7]), np.delete(y, [3, 7]))
    assert result["valid_pairs"] == 38
    assert result["ic"] == pytest.approx(reference["ic"], abs=1e-15)
    assert result["rankic"] == pytest.approx(reference["rankic"], abs=1e-15)


def test_no_auto_direction_flip_signed_results_preserved():
    x = np.arange(40, dtype=float)
    y = -3.0 * x + 10.0
    result = protocol.cross_sectional_ic(x, y)
    assert result["ic"] < 0 and result["rankic"] < 0
    assert result["rankic"] == pytest.approx(-1.0, abs=1e-12)
    codes = [f"S{i:03d}" for i in range(40)]
    spread = protocol.quantile_spread(
        protocol.assign_quantiles(x, codes),
        {code: float(-i) for i, code in enumerate(codes)},
    )
    assert spread["q5_minus_q1"] < 0  # original direction kept, never negated


def test_quintile_assignment_ties_by_sector_code_and_remainder_to_earliest():
    codes = [f"S{9-i:03d}" for i in range(12)]
    values = [1.0] * 12  # all tied: ordering falls back to sector code ascending
    assignment = protocol.assign_quantiles(values, codes)
    sizes = {q: sorted(c for c, v in assignment.items() if v == q) for q in range(1, 6)}
    assert [len(sizes[q]) for q in range(1, 6)] == [3, 3, 2, 2, 2]
    assert sizes[1] == sorted(codes)[:3]  # lowest codes land in Q1 under full ties
    mixed = protocol.assign_quantiles([3.0, 1.0, 2.0, 5.0, 4.0, 6.0],
                                      ["A", "B", "C", "D", "E", "F"])
    assert mixed == {"B": 1, "C": 1, "A": 2, "E": 3, "D": 4, "F": 5}


def test_quantile_spread_q5_minus_q1_and_monotonicity():
    codes = [f"C{i}" for i in range(10)]
    values = [float(i) for i in range(10)]
    returns = {code: 0.01 * i for i, code in enumerate(codes)}
    spread = protocol.quantile_spread(protocol.assign_quantiles(values, codes), returns)
    assert spread["quantile_means"][1] == pytest.approx(np.mean([0.0, 0.01]))
    assert spread["quantile_means"][5] == pytest.approx(np.mean([0.08, 0.09]))
    assert spread["q5_minus_q1"] == pytest.approx(np.mean([0.08, 0.09]) - np.mean([0.0, 0.01]))
    assert protocol.quantile_monotonicity([1.0, 2.0, 3.0, 4.0, 5.0]) == pytest.approx(1.0)
    assert protocol.quantile_monotonicity([5.0, 4.0, 3.0, 2.0, 1.0]) == pytest.approx(-1.0)
    assert protocol.quantile_monotonicity([2.0, 2.0, 2.0, 2.0, 2.0]) is None
    assert protocol.quantile_monotonicity([1.0, np.nan, 3.0, 4.0, 5.0]) is None


def test_four_fixed_development_blocks_and_same_sign_count():
    assert [protocol.block_for_ordinal(o) for o in (1, 25, 26, 50, 51, 75, 76, 100)] == [
        1, 1, 2, 2, 3, 3, 4, 4]
    assert protocol.block_for_ordinal(101) is None
    assert protocol.block_for_ordinal(0) is None
    assert protocol.STABILITY_BLOCKS == ((1, 1, 25), (2, 26, 50), (3, 51, 75), (4, 76, 100))
    assert protocol.block_summary([0.1, -0.2, 0.3, None], 0.05) == {
        "full_development_sign": "positive", "same_sign_block_count": 2}
    assert protocol.block_summary([-0.1, -0.2, 0.3, 0.0], -0.05) == {
        "full_development_sign": "negative", "same_sign_block_count": 2}
    assert protocol.block_summary([0.1, 0.2], 0.0) == {
        "full_development_sign": None, "same_sign_block_count": None}


def test_daily_factor_correlation_and_redundancy_threshold():
    x = np.arange(40, dtype=float)
    same = protocol.cross_sectional_spearman(x, x)
    inverse = protocol.cross_sectional_spearman(x, -x)
    alternating = protocol.cross_sectional_spearman(x, np.array([3.0, -1.0] * 20))
    assert same["spearman"] == pytest.approx(1.0, abs=1e-12)
    assert inverse["spearman"] == pytest.approx(-1.0, abs=1e-12)
    assert alternating["skipped"] is False
    assert protocol.REDUNDANCY_THRESHOLD == 0.80
    assert protocol.redundancy_flag(0.80) is True
    assert protocol.redundancy_flag(-0.85) is True
    assert protocol.redundancy_flag(0.7999) is False
    assert protocol.redundancy_flag(None) is False
    short = protocol.cross_sectional_spearman(x[:20], x[:20])
    assert short["skipped"] is True and short["spearman"] is None


def test_descriptive_t_stat_is_never_degenerate():
    values = [0.1, 0.2, 0.3, 0.4]
    expected = float(np.mean(values)) / (float(np.std(values, ddof=1)) / np.sqrt(4))
    assert protocol.descriptive_t_stat(values) == pytest.approx(expected, abs=1e-12)
    assert protocol.descriptive_t_stat([0.5, 0.5, 0.5]) is None
    assert protocol.descriptive_t_stat([0.5]) is None


def test_protocol_hash_frozen_and_drift_detected():
    payload = protocol.verify_frozen_factor_alpha_audit_v1_protocol()
    assert protocol.FROZEN_FACTOR_ALPHA_AUDIT_V1_PROTOCOL_HASH == (
        "87e6e9c3ac79f1f41239d8c91080b16fd142343dea470084226e23512286b815")
    assert protocol.factor_alpha_audit_v1_protocol_hash() == (
        protocol.FROZEN_FACTOR_ALPHA_AUDIT_V1_PROTOCOL_HASH)
    assert protocol.factor_alpha_audit_v1_protocol_hash(payload) == (
        protocol.FROZEN_FACTOR_ALPHA_AUDIT_V1_PROTOCOL_HASH)
    tampered = dict(payload)
    tampered["redundancy"] = dict(payload["redundancy"], threshold=0.90)
    assert canonical_hash(tampered) != protocol.FROZEN_FACTOR_ALPHA_AUDIT_V1_PROTOCOL_HASH
    with pytest.raises(ValueError, match="PROTOCOL_HASH_MISMATCH"):
        protocol.verify_frozen_factor_alpha_audit_v1_protocol(supplied_hash="0" * 64)


def test_audit_payload_is_result_free_and_flags_stay_true():
    payload = protocol.factor_alpha_audit_v1_payload()
    assert payload["selection_flags"] == {
        "NO_PARAMETER_SELECTION": True, "NO_FACTOR_SELECTION": True,
        "DIAGNOSTIC_ONLY": True}
    assert payload["research_identity"]["phase"] == "DEVELOPMENT"
    assert payload["research_identity"]["validation_access"] == "SEALED"
    assert payload["research_identity"]["final_oos_access"] == "SEALED"
    assert payload["sample"]["development_eligible_ids"] == "E001-E100"
    for banned in ("delete_factor", "flip_factor_sign", "parameter_search",
                   "open_validation", "open_final_oos", "highest_ic_subset_selection"):
        assert banned in payload["prohibitions"]
    serialized = str(payload)
    for result_word in ("rankic_mean", "q5_minus_q1_mean", "promotion_status"):
        assert result_word not in serialized
