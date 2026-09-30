from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from strategies.etf_quant.domain.industry_level import default_taxonomy
from strategies.etf_quant.factors import compute_close_factors, compute_price_factors
from strategies.etf_quant.runtime.exports import ExportProvider, SCHEMAS, export_snapshot
from strategies.etf_quant.runtime.industry import build_industry_series
from strategies.etf_quant.runtime.prediction import current_predictions
from strategies.etf_quant.runtime.storage import (GateError, atomic_bytes, contained, digest,
    external_root, json_bytes, publish_generation, read_generation)

TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 9, 24, 18, tzinfo=TZ)
IDENTITY = {"provider": "SYNTHETIC_TEST", "source_commit": "a" * 40, "source_version": "TEST"}


def export_tables():
    provenance = {"source": "test", "data_version": "v2", "fetched_at": NOW}
    bar = {**provenance, "symbol": "600001.SH", "trade_date": NOW.date(),
        "open": 10., "high": 11., "low": 9., "close": 10., "volume": 100., "amount": 1000.}
    return {
        "trading_calendar": [{**provenance, "trade_date": NOW.date(), "is_trading": True},
                             {**provenance, "trade_date": NOW.date() + timedelta(days=1), "is_trading": True}],
        "stock_bars": [{**bar, "adj_close": 10., "adj_is_exact": True}],
        "industry_membership": [{**provenance, "source": "sw", "symbol": "600001.SH", "industry_code": "801012",
            "industry_name": "801012", "classification_system": "sw", "as_of_date": NOW.date()}],
        "etf_bars": [{**bar, "symbol": "510001.SH"}],
        "instruments": [{**provenance, "symbol": "510001.SH", "name": "Synthetic", "exchange": "SH", "asset_type": "etf",
            "list_date": date(2020, 1, 1), "delist_date": None, "prev_symbol": None}],
        "trading_status": [{**provenance, "symbol": "510001.SH", "trade_date": NOW.date(), "is_trading": True, "status": "NORMAL"}],
        "benchmark_csi300": [{**provenance, "symbol": "000300.SH", "trade_date": NOW.date(), "close": 3000., "frequency": "1d"}],
    }


def make_export(tmp_path, tables=None, created=NOW):
    pointer = export_snapshot(tmp_path, export_tables() if tables is None else tables, identity=IDENTITY,
        created_at=created, fetch_started_at=created, fetch_completed_at=created, cutoff=NOW.date(), queries={})
    return tmp_path / pointer["snapshot_id"], pointer


def test_snapshot_roundtrip_provenance_calendar_and_nulls(tmp_path):
    path, pointer = make_export(tmp_path)
    p = ExportProvider(path, expected_identity=IDENTITY, now=NOW)
    assert len(p.sessions) == 2 and p.sessions[-1] > p.cutoff
    assert p.manifest["available_at"] is p.manifest["source_published_at"] is None
    assert p.tables["stock_bars"].adj_is_exact.all()
    assert p.manifest["datasets"]["stock_bars"]["row_count"] == 1
    manifest, files = read_generation(tmp_path, pointer)
    assert len(files) == 7 and manifest["snapshot_id"] == path.name
    with pytest.raises(GateError, match="IMMUTABLE_GENERATION_EXISTS"):
        make_export(tmp_path)


@pytest.mark.parametrize("change,code", [
    (lambda t: t["stock_bars"][0].update(adj_is_exact=False), "ADJUSTMENT_SEMANTICS"),
    (lambda t: t["stock_bars"].append(deepcopy(t["stock_bars"][0])), "DUPLICATE"),
    (lambda t: t["stock_bars"][0].update(data_version="v1"), "VOLUME_UNIT"),
    (lambda t: t["stock_bars"][0].update(high=8.), "PRICE_SCHEMA"),
    (lambda t: t["stock_bars"][0].update(trade_date=date(2026, 9, 25)), "TIME"),
    (lambda t: t["stock_bars"][0].update(fetched_at=NOW.replace(hour=14)), "PARTIAL_SESSION"),
    (lambda t: t["benchmark_csi300"][0].update(symbol="881001"), "BENCHMARK_IDENTITY"),
    (lambda t: t["industry_membership"][0].update(source="other"), "INDUSTRY_CLASSIFICATION"),
])
def test_export_admission_fail_closed(tmp_path, change, code):
    tables = export_tables()
    change(tables)
    with pytest.raises(GateError, match=code):
        path, _ = make_export(tmp_path, tables)
        ExportProvider(path, expected_identity=IDENTITY, now=NOW)
    assert not list(tmp_path.glob("*/manifest.json"))


def test_tamper_identity_and_external_output(tmp_path):
    path, _ = make_export(tmp_path)
    with pytest.raises(GateError, match="SNAPSHOT_BLOCKER"):
        ExportProvider(path, expected_identity={"source_commit": "b" * 40}, now=NOW)
    (path / "stock_bars.csv").write_bytes(b"corruption")
    with pytest.raises(GateError, match="HASH"):
        ExportProvider(path, expected_identity=IDENTITY, now=NOW)
    with pytest.raises(GateError, match="INTEGRITY"):
        contained(path, "../escape")
    (tmp_path / ".git").mkdir()
    with pytest.raises(GateError, match="EXTERNAL"):
        external_root(tmp_path / "output")


def test_atomic_permission_retry_closed_handle_and_no_partial(tmp_path):
    target = tmp_path / "latest.json"
    target.write_bytes(b"old")
    calls, audit = [], []
    def replace(source, destination):
        calls.append(source)
        # An independent reader can open the completely closed writer output.
        assert source.read_bytes() == b"new"
        if len(calls) == 1:
            raise PermissionError(13, "synthetic sharing conflict")
        source.replace(destination)
    atomic_bytes(target, b"new", replace=replace, sleep=lambda _: None, audit=audit.append)
    assert target.read_bytes() == b"new" and len(calls) == 2 and len(audit) == 1
    assert not list(tmp_path.glob("*.tmp"))
    def failure(*args):
        raise PermissionError(13, "synthetic persistent sharing conflict")
    with pytest.raises(GateError, match="PUBLICATION"):
        atomic_bytes(target, b"bad", replace=failure, sleep=lambda _: None)
    assert target.read_bytes() == b"new"


def test_generation_rejects_partial_hash_and_closed_ids(tmp_path):
    for run_id in ("../escape", "x/y", "", "x.json"):
        with pytest.raises(GateError):
            publish_generation(tmp_path, run_id, {"state.json": b"{}"}, {})
    pointer = publish_generation(tmp_path, "TEST", {"state.json": b"{}"}, {})
    (tmp_path / "TEST/state.json").write_bytes(b"tamper")
    with pytest.raises(GateError, match="INTEGRITY"):
        read_generation(tmp_path, pointer)


def industry_provider(n=500):
    days = tuple(d.date() for d in pd.bdate_range("2024-01-01", periods=n))
    # Real Shenwan codes: the sealed taxonomy resolves stored Level-3 codes to the
    # frozen Level-2 production universe, so the fixture must use codes it defines.
    taxonomy = default_taxonomy()
    level2 = list(taxonomy.named_industry_codes)[:5]
    codes = tuple(taxonomy.level3_children[code][0] for code in level2)
    members, bars = [], []
    for c, code in enumerate(codes):
        for s in range(6):
            symbol = f"SYN_{c}_{s}"
            members.append({"symbol": symbol, "industry_code": code, "as_of_date": days[0]})
            for i, day in enumerate(days):
                price = 10 * np.exp((.0003 + .0001 * c) * i + .01 * np.sin(i / (7 + c)))
                bars.append({"symbol": symbol, "trade_date": day, "adj_close": price, "adj_is_exact": True, "volume": 100.})
    instruments = [{"symbol": r["symbol"], "asset_type": "stock", "list_date": date(2020, 1, 1),
                    "delist_date": None, "prev_symbol": None} for r in members]
    return SimpleNamespace(tables={"industry_membership": pd.DataFrame(members), "stock_bars": pd.DataFrame(bars),
                                  "instruments": pd.DataFrame(instruments)},
        sessions=days, cutoff=days[-1], created_at=datetime.combine(days[-1], datetime.min.time(), TZ).replace(hour=17))


def test_source_c_equal_weight_base_coverage_and_exact_return():
    p = industry_provider(3)
    out = build_industry_series(p, classification_version="SW2021")
    assert np.all(out.closes.iloc[0] == 1000)
    records = p.tables["stock_bars"].query("symbol == 'SYN_0_0'").adj_close
    assert out.closes.iloc[1, 0] == pytest.approx(1000 * records.iloc[1] / records.iloc[0])
    assert out.identity == "INTERNAL_SHENWAN_INDUSTRY_SERIES_V1"
    assert out.audit[0]["daily_return"] is None and out.audit[0]["available_at"] is None


def test_source_c_gap_never_bridged_or_rebased():
    p = industry_provider(4)
    b = p.tables["stock_bars"]
    p.tables["stock_bars"] = b.loc[~((b.symbol.isin(["SYN_0_0", "SYN_0_1"])) & (b.trade_date == p.sessions[1]))]
    out = build_industry_series(p, classification_version="SW2021")
    assert np.isnan(out.closes.iloc[1:, 0]).all()
    first_industry = out.universe[0]
    row = next(r for r in out.audit if r["trade_date"] == str(p.sessions[1]) and r["industry_code"] == first_industry)
    assert row["eligible_members"] == 6 and row["valid_constituents"] == 4
    assert row["industry_level"] == "SHENWAN_L2"
    with pytest.raises(GateError, match="CLASSIFICATION_VERSION"):
        build_industry_series(p)


def test_close_only_factor_parity_and_no_fake_fields():
    close = pd.Series(np.arange(1., 160.), index=pd.bdate_range("2024-01-01", periods=159))
    frame = pd.DataFrame({k: close for k in ("open", "high", "low", "close", "volume", "amount")})
    pd.testing.assert_frame_equal(compute_close_factors(close), compute_price_factors(frame))
    with pytest.raises(ValueError, match="OHLCVA"):
        compute_price_factors(close.to_frame("close"))
    close.iloc[125] = np.nan
    assert np.isnan(compute_close_factors(close).iloc[126].v5)


def test_current_models_independent_maturity_and_null_source_timing():
    p = industry_provider()
    out = build_industry_series(p, classification_version="SW2021")
    models, predictions, fused = current_predictions(out, p, signal_at=p.created_at)
    assert len(models) == len(predictions) == 3 and len(fused.rankings) == 5
    for h, model in models.items():
        assert model.training.label_cutoff == p.sessions[-1 - int(h)]
        assert model.training.training_day_count >= 30 and model.spec.alpha == .01
    assert all(row["available_at"] is None for row in out.audit)
    with pytest.raises(GateError, match="AVAILABILITY"):
        current_predictions(out, p, signal_at=p.created_at - timedelta(seconds=1))
