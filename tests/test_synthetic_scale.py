"""Equivalence/scale smoke checks use temporary synthetic files only."""

import pytest


def test_provider_metadata_matches_per_symbol_reference(tmp_path):
    pytest.importorskip("polars", reason="independent developer optional scale dependency")
    from scripts.engineering.benchmark import provider_scale

    assert provider_scale(tmp_path, symbols=3, sessions=4)["bars"] == 12


def test_lazy_catalogue_matches_eager_union_and_repair(tmp_path):
    pytest.importorskip("polars", reason="independent developer optional scale dependency")
    from scripts.engineering.benchmark import catalogue_scale

    assert catalogue_scale(tmp_path, rows=10)["eligible"] == 2
