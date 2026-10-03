"""V4 dependency direction and immutable contract regressions, using synthetic inputs."""

from __future__ import annotations

import ast
import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from benchmarks import fixtures, reference
from quant_primitives.ohlc import valid_daily_open
from src.application.backtesting import discover_strategies
from strategies.etf_quant.mapping.proxy import ProxyPurity
from strategies.etf_quant.runtime.prefix import source_prefix

ROOT = Path(__file__).resolve().parents[1]


def test_forbidden_production_import_graph_has_no_static_or_dynamic_edges():
    violations = []
    for base, forbidden in [
        (ROOT / "strategies", "src"),
        (ROOT / "src/application", "strategies"),
        (ROOT / "src/backtesting", "strategies"),
        (ROOT / "quant_primitives", "src"),
        (ROOT / "quant_primitives", "strategies"),
    ]:
        for path in base.rglob("*.py"):
            if "tests" in path.relative_to(base).parts:
                continue
            for node in ast.walk(ast.parse(path.read_text())):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [item.name for item in node.names]
                elif isinstance(node, ast.ImportFrom) and not node.level:
                    modules = [node.module or ""]
                elif isinstance(node, ast.Call) and (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "__import__"
                    or isinstance(node.func, ast.Attribute)
                    and node.func.attr == "import_module"
                ):
                    modules = [
                        value.value
                        for arg in node.args
                        for value in ast.walk(arg)
                        if isinstance(value, ast.Constant) and isinstance(value.value, str)
                    ]
                if any(name == forbidden or name.startswith(forbidden + ".") for name in modules):
                    violations.append((str(path.relative_to(ROOT)), node.lineno))
    assert violations == []


def test_fresh_imports_and_metadata_discovery_do_not_attempt_strategy_loading():
    # A fresh interpreter detects attempted imports even if discovery suppresses the exception.
    code = """
import importlib
import sys
attempts = []
original = importlib.import_module
def guarded(name, *args, **kwargs):
    if name == 'strategies' or name.startswith('strategies.'):
        attempts.append(name)
        raise AssertionError(name)
    return original(name, *args, **kwargs)
importlib.import_module = guarded
from src.backtesting import discover_strategies
found = discover_strategies()
assert found and all(spec.entry is None for spec in found.values())
assert attempts == []
assert not any(name == 'strategies' or name.startswith('strategies.') for name in sys.modules)
"""
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True, capture_output=True)


def test_strategy_import_is_independent_of_top_level_src():
    code = """
import sys
from strategies.sw_sector_rotation.src.portfolio.sector_etf_mapping import daily_mapping_availability
assert not any(name == 'src' or name.startswith('src.') for name in sys.modules)
"""
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True, capture_output=True)


def test_discovery_injection_and_documented_version_config_order(tmp_path):
    package = tmp_path / "synthetic"
    (package / "src").mkdir(parents=True)
    (package / "config").mkdir()
    (package / "__init__.py").write_text("")
    (package / "VERSION").write_text("1.0")
    (package / "version.txt").write_text("2.0")
    for name in ("synthetic.yaml", "a.yaml", "0.yml", "0_example.yaml"):
        (package / "config" / name).write_text("{}")
    calls = []

    class SyntheticCore:
        pass

    def loader(name):
        calls.append(name)
        return SyntheticCore

    spec = discover_strategies(tmp_path, entry_loader=loader)["synthetic"]
    assert spec.entry is SyntheticCore and calls == ["strategies.synthetic"]
    assert spec.version == "1.0" and spec.config_file == "a.yaml"
    assert discover_strategies(tmp_path)["synthetic"].entry is None
    (package / "VERSION").unlink()
    assert discover_strategies(tmp_path)["synthetic"].version == "2.0"


def test_cli_injection_dispatches_to_existing_framework_without_market_execution(monkeypatch):
    from scripts import quant

    observed = {}

    def fake_discover(*, entry_loader):
        observed["loader"] = entry_loader
        return {"synthetic": object()}

    def fake_run(request, *, specs):
        observed["specs"] = specs
        return SimpleNamespace(
            metadata=SimpleNamespace(
                status="synthetic",
                framework="fake",
                framework_version="1",
                symbols=(),
                start_date="2020-01-01",
                end_date="2020-01-02",
            ),
            metrics=SimpleNamespace(to_dict=lambda: {}),
        )

    import src.backtesting as backtesting

    monkeypatch.setattr(backtesting, "discover_strategies", fake_discover)
    monkeypatch.setattr(backtesting, "run_backtest", fake_run)
    args = SimpleNamespace(
        strategy="synthetic",
        framework="fake",
        start="2020-01-01",
        end="2020-01-02",
        initial_cash=1,
        output_root=None,
    )
    assert quant._cmd_backtest(args) == 0
    assert observed["loader"] is quant._load_strategy_entry
    assert "synthetic" in observed["specs"]


def test_ohlc_has_one_shared_implementation_and_preserves_series_mapping_admission():
    from src.data.ohlc import valid_daily_open as infrastructure

    assert infrastructure is valid_daily_open
    good = dict(open=10, high=12, low=9, close=11)
    assert valid_daily_open(good) and valid_daily_open(pd.Series(good))
    for field in good:
        assert not valid_daily_open({**good, field: float("nan")})
        assert not valid_daily_open({**good, field: 0})
    assert not valid_daily_open(None)
    assert not valid_daily_open({**good, "high": 8})


def test_proxy_legacy_serialization_and_non_target_dominance_are_unchanged():
    purity = ProxyPurity(
        "target", 30, "largest-other", 50, False, 2, "benchmark", "PASS", "OFFICIAL"
    )
    assert purity.dominance_margin == -20
    assert not hasattr(purity, "largest_non_target_l2_code")
    assert not hasattr(purity, "largest_non_target_l2_exposure")
    assert purity.as_dict()["second_largest_l2_exposure"] == 50


def test_prefix_duplicate_unknown_future_and_missing_dates_preserve_byte_identity():
    p = fixtures.industry(12, 2)
    stocks = p.tables["stock_bars"]
    p.tables["stock_bars"] = pd.concat([stocks, stocks.iloc[[0]]], ignore_index=True)
    p.tables["instruments"].loc[0, "list_date"] = None
    p.cutoff = p.sessions[-2]
    p.tables["no_date"] = pd.DataFrame({"ignored": [1]})
    assert source_prefix(p) == reference.source_prefix(p)
    first = source_prefix(p)
    first["stock_bars"].clear()
    assert source_prefix(p) == reference.source_prefix(p)
    assert not hasattr(importlib.import_module("strategies.etf_quant.runtime.prefix"), "_INDEX")


def test_v3_parent_manifest_remains_byte_pinned_in_v4_certificate():
    from hashlib import sha256

    from strategies.etf_quant.runtime.implementation import (
        ACTIVE_MANIFEST,
        PARENT_MANIFEST,
        ImplementationIntegrityError,
        verify_implementation,
    )

    report = json.loads((ROOT / ACTIVE_MANIFEST).read_text())["implementation_integrity"]
    assert (
        report["parent_manifest_sha256"]
        == sha256((ROOT / PARENT_MANIFEST).read_bytes()).hexdigest()
    )
    assert PARENT_MANIFEST in verify_implementation(ROOT)
    # The existing source-tamper/forged-hash regression covers every active certificate.
    assert issubclass(ImplementationIntegrityError, ValueError)
