from datetime import date, datetime, time, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from strategies.etf_quant.runtime.exports import PROVENANCE, SCHEMAS, encode_table
from strategies.etf_quant.runtime.storage import GateError

TZ = timezone(timedelta(hours=8))
OBSERVED = datetime(2026, 9, 24, 18, tzinfo=TZ)
D1, D2, D3, D4 = date(2026, 9, 23), date(2026, 9, 24), date(2026, 9, 25), date(2026, 9, 26)
SYMBOLS = [f"60000{i}.SH" for i in range(6)]

STOCK_COLS = ["symbol", "trade_date", "open", "high", "low", "close", "volume", "amount",
              "adj_close", "adj_is_exact", "source", "data_version", "fetched_at"]
CAL_COLS = ["trade_date", "is_trading", "source", "data_version", "fetched_at"]
MEM_COLS = ["symbol", "classification_system", "industry_code", "industry_name", "as_of_date",
            "source", "data_version", "fetched_at"]
INS_COLS = ["symbol", "name", "exchange", "asset_type", "list_date", "delist_date", "prev_symbol",
            "source", "data_version", "fetched_at"]
ETF_COLS = ["symbol", "trade_date", "open", "high", "low", "close", "volume", "amount",
            "source", "data_version", "fetched_at"]
STS_COLS = ["symbol", "trade_date", "is_trading", "status", "source", "data_version", "fetched_at"]
BMK_COLS = ["symbol", "trade_date", "close", "frequency", "source", "data_version", "fetched_at"]


class FakeFrame:
    """Polars-shaped stand-in: column order preserved, bounded slices."""

    def __init__(self, columns, rows):
        self.columns = list(columns)
        self.rows = [{k: row[k] for k in self.columns} for row in rows]

    def to_dicts(self):
        return [dict(row) for row in self.rows]

    def iter_slices(self, n_rows=50_000):
        for i in range(0, len(self.rows), n_rows):
            yield FakeFrame(self.columns, self.rows[i:i + n_rows])


def bar(symbol, day, **over):
    row = {"symbol": symbol, "trade_date": day, "open": 10., "high": 11., "low": 9., "close": 10.,
           "volume": 100., "amount": 1000., "adj_close": 10., "adj_is_exact": True,
           "source": "test", "data_version": "v2", "fetched_at": datetime.combine(day, time(16), TZ)}
    row.update(over)
    return row


def member(symbol, source="sw", system="sw"):
    return {"symbol": symbol, "classification_system": system, "industry_code": "801012",
            "industry_name": "801012", "as_of_date": D1, "source": source, "data_version": "v2",
            "fetched_at": datetime.combine(D1, time(16), TZ)}


def synthetic_lake():
    calendar = [{"trade_date": day, "is_trading": flag, "source": "test", "data_version": "v2",
                 "fetched_at": datetime.combine(D2, time(16), TZ)}
                for day, flag in ((D1, True), (D2, True), (D3, True), (D4, False))]
    stock = [bar(s, D1, adj_is_exact=s != SYMBOLS[-1]) for s in SYMBOLS]
    stock += [bar(s, D2) for s in SYMBOLS]
    instruments = [{"symbol": s, "name": "Synthetic " + s, "exchange": "SH",
                    "asset_type": "etf" if s == "510001.SH" else "stock",
                    "list_date": date(2020, 1, 1), "delist_date": None, "prev_symbol": None,
                    "source": "test", "data_version": "v2",
                    "fetched_at": datetime.combine(D2, time(16), TZ)} for s in SYMBOLS + ["510001.SH"]]
    benchmark = [{"symbol": "000300.SH", "trade_date": day, "close": close, "frequency": frequency,
                  "source": "test", "data_version": "v2", "fetched_at": datetime.combine(day, time(16), TZ)}
                 for day, close, frequency in ((D1, 3000., "1d"), (D2, 3010., "1d"), (D2, 3005., "1w"))]
    status = [{"symbol": "510001.SH", "trade_date": day, "is_trading": True, "status": "NORMAL",
               "source": "test", "data_version": "v2", "fetched_at": datetime.combine(day, time(16), TZ)}
              for day in (D1, D2)]
    return {"calendar": calendar, "stock": stock, "membership": [member(s) for s in SYMBOLS] + [member("600100.SH", source="csi")],
            "instruments": instruments, "etf": [bar("510001.SH", day) for day in (D1, D2)],
            "status": status, "benchmark": benchmark}


def fake_load(lake, calls=None):
    def load(dataset, **kw):
        if calls is not None:
            calls.append((dataset, kw))
        start = date.fromisoformat(kw["start"]) if "start" in kw else None
        end = date.fromisoformat(kw["end"]) if "end" in kw else None

        def dated(rows, field="trade_date"):
            return [r for r in rows if start <= r[field] <= end]

        def scoped(rows):
            return [r for r in rows if r["symbol"] in kw["symbols"]] if "symbols" in kw else rows

        if dataset == "industry_members":
            return FakeFrame(MEM_COLS, dated(lake["membership"], "as_of_date"))
        if dataset == "trading_calendar":
            return FakeFrame(CAL_COLS, dated(lake["calendar"]))
        if dataset == "instruments":
            return FakeFrame(INS_COLS, lake["instruments"])
        if dataset == "trading_status":
            return FakeFrame(STS_COLS, scoped(dated(lake["status"])))
        if dataset == "index_bars":
            return FakeFrame(BMK_COLS, scoped(dated(lake["benchmark"])))
        if dataset == "daily_bars" and kw.get("adjust") == "hfq":
            return FakeFrame(STOCK_COLS, scoped(dated(lake["stock"])))
        if dataset == "daily_bars":
            return FakeFrame(ETF_COLS, scoped(dated(lake["etf"])))
        raise AssertionError("unexpected dataset " + dataset)

    return load


def cfg(tmp_path, name="exports", etfs=()):
    return {"paths": {"lake_root": str(tmp_path / "lake"), "export_root": str(tmp_path / name)},
            "export": {"start": str(D1), "cutoff": str(D2), "calendar_end": str(D4),
                       "etf_symbols": list(etfs), "classification_version": "SWCLASS2021"}}


def load_sidecar_modules():
    root = Path(__file__).resolve().parents[2] / "services/cnequity-sidecar"
    sys.path.insert(0, str(root))
    try:
        spec = importlib.util.spec_from_file_location("sidecar_export_streaming", root / "export_streaming.py")
        streaming = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(streaming)  # imports runner for IDENTITY/DATASETS/lake_fingerprint
        return sys.modules["runner"], streaming
    finally:
        sys.path.pop(0)


def assert_no_publication(tmp_path, name="exports"):
    root = tmp_path / name
    assert not root.exists() or not any(root.iterdir())


def test_streaming_byte_identical_to_batch_export(tmp_path):
    runner_mod, streaming = load_sidecar_modules()
    batch = runner_mod.export_lake(cfg(tmp_path, "exports_batch"), fake_load(synthetic_lake()), observed_at=OBSERVED)
    stream = streaming.export_lake_streaming(cfg(tmp_path), fake_load(synthetic_lake()), observed_at=OBSERVED)
    assert stream["streaming"] is True and stream["peak_chunk_rows"] == 7
    assert stream["snapshot_id"] == batch["snapshot_id"] == stream["run_id"]
    assert stream["manifest_sha256"] == batch["manifest_sha256"]
    dir_batch, dir_stream = tmp_path / "exports_batch" / batch["snapshot_id"], tmp_path / "exports" / stream["snapshot_id"]
    assert sorted(p.name for p in dir_batch.iterdir()) == sorted(p.name for p in dir_stream.iterdir())
    for published in dir_batch.iterdir():
        assert published.read_bytes() == (dir_stream / published.name).read_bytes(), published.name
    from strategies.etf_quant.runtime.exports import ExportProvider
    exported = ExportProvider(dir_stream, expected_identity=runner_mod.IDENTITY, now=OBSERVED)
    assert exported.manifest["snapshot_id"] == stream["snapshot_id"]
    assert set(exported.tables["industry_membership"].symbol) == set(SYMBOLS)
    published_keys = set(zip(exported.tables["stock_bars"].symbol, exported.tables["stock_bars"].trade_date))
    assert len(published_keys) == 11 and (SYMBOLS[-1], D1) not in published_keys
    lake = synthetic_lake()
    expected_stock = [r for r in lake["stock"] if r["adj_is_exact"] is True]
    assert (dir_stream / "stock_bars.csv").read_bytes() == encode_table(expected_stock, STOCK_COLS)
    expected_members = [r for r in lake["membership"] if r["source"] == "sw" and r["classification_system"] == "sw"]
    assert len(expected_members) == 6
    assert (dir_stream / "industry_membership.csv").read_bytes() == encode_table(expected_members, MEM_COLS)
    expected_benchmark = [r for r in lake["benchmark"] if r["frequency"] == "1d"]
    assert (dir_stream / "benchmark_csi300.csv").read_bytes() == encode_table(expected_benchmark, BMK_COLS)
    empty_columns = sorted({**SCHEMAS["etf_bars"], **PROVENANCE})
    assert (dir_stream / "etf_bars.csv").read_bytes() == encode_table([], empty_columns)
    manifest = json.loads((dir_stream / "manifest.json").read_bytes())
    assert manifest["adjustment_exact_rows"] == 11 and manifest["adjustment_rejected_rows"] == 1
    assert manifest["datasets"]["stock_bars"]["row_count"] == 11
    assert manifest["datasets"]["stock_bars"]["query"]["rejected_nonexact_rows"] == 1
    assert manifest["datasets"]["industry_membership"]["row_count"] == 6
    etf_query = manifest["datasets"]["etf_bars"]["query"]
    assert etf_query == {"dataset": "daily_bars", "symbols": [], "adjust": None, "status": "NO_VERIFIED_ETF_SCOPE"}
    assert manifest["datasets"]["etf_bars"]["row_count"] == 0
    assert manifest["datasets"]["trading_status"]["query"]["status"] == "NO_VERIFIED_ETF_SCOPE"


def test_non_empty_etf_scope_streams_and_validates(tmp_path):
    _, streaming = load_sidecar_modules()
    pointer = streaming.export_lake_streaming(cfg(tmp_path, etfs=["510001.SH"]), fake_load(synthetic_lake()),
                                              observed_at=OBSERVED)
    manifest = json.loads((tmp_path / "exports" / pointer["snapshot_id"] / "manifest.json").read_bytes())
    assert manifest["datasets"]["etf_bars"]["row_count"] == 2
    assert manifest["datasets"]["trading_status"]["row_count"] == 2
    assert manifest["datasets"]["etf_bars"]["query"]["symbols"] == ["510001.SH"]
    assert manifest["datasets"]["etf_bars"]["query"]["adjust"] is None


def test_duplicate_symbol_within_one_day_chunk_blocked(tmp_path):
    _, streaming = load_sidecar_modules()
    lake = synthetic_lake()
    lake["stock"].append(bar(SYMBOLS[0], D2))
    with pytest.raises(GateError, match="DUPLICATE"):
        streaming.export_lake_streaming(cfg(tmp_path), fake_load(lake), observed_at=OBSERVED)
    assert_no_publication(tmp_path)


def test_high_below_close_blocked(tmp_path):
    _, streaming = load_sidecar_modules()
    lake = synthetic_lake()
    lake["stock"][0]["high"] = 9.5
    with pytest.raises(GateError, match="PRICE_SCHEMA"):
        streaming.export_lake_streaming(cfg(tmp_path), fake_load(lake), observed_at=OBSERVED)
    assert_no_publication(tmp_path)


def test_fetched_before_session_close_blocked(tmp_path):
    _, streaming = load_sidecar_modules()
    lake = synthetic_lake()
    lake["stock"][0]["fetched_at"] = datetime.combine(D1, time(14), TZ)
    with pytest.raises(GateError, match="PARTIAL_SESSION"):
        streaming.export_lake_streaming(cfg(tmp_path), fake_load(lake), observed_at=OBSERVED)
    assert_no_publication(tmp_path)


def test_fetched_after_created_at_blocked(tmp_path):
    _, streaming = load_sidecar_modules()
    lake = synthetic_lake()
    lake["stock"][0]["fetched_at"] = datetime.combine(D3, time(16), TZ)
    with pytest.raises(GateError, match="CNE_SNAPSHOT_TIME_BLOCKER"):
        streaming.export_lake_streaming(cfg(tmp_path), fake_load(lake), observed_at=OBSERVED)
    assert_no_publication(tmp_path)


def test_membership_unavailable_blocked(tmp_path):
    _, streaming = load_sidecar_modules()
    lake = synthetic_lake()
    for row in lake["membership"]:
        row["source"] = "csi"
    with pytest.raises(GateError, match="SHENWAN_MEMBERSHIP_UNAVAILABLE"):
        streaming.export_lake_streaming(cfg(tmp_path), fake_load(lake), observed_at=OBSERVED)
    assert_no_publication(tmp_path)


def test_calendar_without_cutoff_session_blocked(tmp_path):
    _, streaming = load_sidecar_modules()
    lake = synthetic_lake()
    lake["calendar"] = [r for r in lake["calendar"] if r["trade_date"] != D2]
    with pytest.raises(GateError, match="CNE_CALENDAR_BLOCKER"):
        streaming.export_lake_streaming(cfg(tmp_path), fake_load(lake), observed_at=OBSERVED)
    assert_no_publication(tmp_path)


def test_lake_fingerprint_change_blocked(tmp_path, monkeypatch):
    _, streaming = load_sidecar_modules()
    values = iter(["a" * 64, "b" * 64])
    monkeypatch.setattr(streaming, "lake_fingerprint", lambda lake: next(values))
    with pytest.raises(GateError, match="SOURCE_LAKE_CHANGED_DURING_EXPORT_BLOCKER"):
        streaming.export_lake_streaming(cfg(tmp_path), fake_load(synthetic_lake()), observed_at=OBSERVED)
    assert_no_publication(tmp_path)


def test_immutable_generation_exists_and_no_stage_left(tmp_path):
    _, streaming = load_sidecar_modules()
    streaming.export_lake_streaming(cfg(tmp_path), fake_load(synthetic_lake()), observed_at=OBSERVED)
    with pytest.raises(GateError, match="IMMUTABLE_GENERATION_EXISTS"):
        streaming.export_lake_streaming(cfg(tmp_path), fake_load(synthetic_lake()), observed_at=OBSERVED)
    assert not list((tmp_path / "exports").glob(".stage_*"))


def test_memory_bounded_query_shape(tmp_path):
    _, streaming = load_sidecar_modules()
    calls = []
    streaming.export_lake_streaming(cfg(tmp_path, etfs=["510001.SH"]), fake_load(synthetic_lake(), calls),
                                    observed_at=OBSERVED)
    assert [ds for ds, _ in calls[:2]] == ["industry_members", "trading_calendar"]
    assert all("as_of" not in kw and "universe" not in kw for _, kw in calls)
    stock_calls = [kw for ds, kw in calls if ds == "daily_bars" and kw.get("adjust") == "hfq"]
    assert len(stock_calls) == 2
    assert all(kw["start"] == kw["end"] for kw in stock_calls)
    assert {kw["start"] for kw in stock_calls} == {str(D1), str(D2)}
    assert all(kw["symbols"] == SYMBOLS and kw["strict_adj"] is False for kw in stock_calls)
    others = {}
    for ds, kw in calls:
        if ds == "daily_bars" and kw.get("adjust") == "hfq":
            continue
        key = (ds, "etf" if ds == "daily_bars" else ds)
        others[key] = others.get(key, 0) + 1
    assert others == {("industry_members", "industry_members"): 1, ("trading_calendar", "trading_calendar"): 1,
                      ("instruments", "instruments"): 1, ("daily_bars", "etf"): 1,
                      ("trading_status", "trading_status"): 1, ("index_bars", "index_bars"): 1}
