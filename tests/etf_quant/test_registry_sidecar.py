from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from strategies.etf_quant.domain import IndustryRanking
from strategies.etf_quant.mapping.registry import load_registry, select_mappings
from strategies.etf_quant.runtime.storage import GateError, digest, json_bytes

TZ = timezone(timedelta(hours=8))
SIGNAL = datetime(2026, 9, 24, 18, tzinfo=TZ)


def registry_doc(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir(exist_ok=True)
    body = b"SYNTHETIC TEST ONLY - not a real fund document"
    (evidence / "synthetic.txt").write_bytes(body)
    entries = []
    for i in range(6):
        entries.append({"industry_code": f"80101{min(i, 4)}", "industry_name": "SYNTHETIC",
            "etf_code": f"51000{i}.SH", "etf_name": "SYNTHETIC", "mapping_method": "OFFICIAL_FUND_DOCUMENT",
            "tracking_index_code": f"SYN_{i}", "tracking_index_name": "SYNTHETIC",
            "classification": "A_SHARE_INDUSTRY_OR_THEME_ETF", "verification_status": "VERIFIED",
            "verified_at": "2026-08-01T18:00:00+08:00", "effective_from": "2026-08-02", "effective_to": None,
            "notes": "SYNTHETIC TEST ONLY", "available_at": "2026-08-01T18:00:00+08:00",
            "source_provider": "SYNTHETIC", "source_url": "https://example.invalid/synthetic",
            "source_file": "synthetic.txt", "source_sha256": digest(body), "source_retrieved_at": "2026-08-01T17:00:00+08:00"})
    return {"schema_version": "1.0.0", "registry_identity": "VERIFIED_MAPPING_REGISTRY_V1", "scope": "CURRENT_FORWARD_ONLY", "entries": entries}, evidence


def provider():
    days = tuple(d.date() for d in pd.bdate_range(end="2026-09-25", periods=22))
    bars, instruments, status = [], [], []
    for i in range(6):
        symbol = f"51000{i}.SH"
        instruments.append({"symbol": symbol, "asset_type": "etf", "list_date": date(2020, 1, 1),
            "delist_date": None, "prev_symbol": None})
        for day in days:
            bars.append({"symbol": symbol, "trade_date": day, "open": 1., "high": 1.1, "low": .9,
                "close": 1., "volume": 1000., "amount": 1000. * (i + 1), "source": "tdx_protocol"})
            status.append({"symbol": symbol, "trade_date": day, "is_trading": True, "status": "normal", "source": "eastmoney"})
    return SimpleNamespace(sessions=days, cutoff=SIGNAL.date(), tables={"etf_bars": pd.DataFrame(bars),
        "instruments": pd.DataFrame(instruments), "trading_status": pd.DataFrame(status)})


def select(tmp_path, doc=None, p=None):
    original, evidence = registry_doc(tmp_path)
    path = tmp_path / "registry.json"
    path.write_bytes(json_bytes(original if doc is None else doc))
    registry = load_registry(path, evidence_root=evidence)
    return select_mappings(registry, tuple(IndustryRanking(i + 1, f"80101{i}", 5 - i) for i in range(5)),
                           provider() if p is None else p, signal_at=SIGNAL)


def test_registry_empty_is_blocked_not_guessed(tmp_path):
    doc, _ = registry_doc(tmp_path)
    doc["entries"] = []
    result = select(tmp_path, doc)
    assert result["status"] == "MAPPING_ADMISSION_BLOCKED" and result["selected"] == []


def test_registry_liquidity_max_and_twenty_sessions(tmp_path):
    result = select(tmp_path)
    assert result["status"] == "READY" and len(result["selected"]) == 5
    assert result["selected"][-1]["etf_code"] == "510005.SH"
    assert all(r["liquidity_sessions"] == 20 for r in result["diagnostics"])


@pytest.mark.parametrize("change,code", [
    (lambda d: d["entries"][0].update(source_sha256="b" * 64), "HASH"),
    (lambda d: d["entries"][0].update(effective_from="2020-01-01"), "TEMPORAL"),
    (lambda d: d["entries"][0].update(available_at=None), "TIME"),
    (lambda d: d["entries"][0].update(mapping_method="NAME_FUZZY"), "EVIDENCE"),
    (lambda d: d["entries"][0].update(classification="BROAD_MARKET"), "EVIDENCE"),
    (lambda d: d["entries"].append(deepcopy(d["entries"][0])), "DUPLICATE"),
])
def test_registry_rejects_unproven_fields(tmp_path, change, code):
    doc, _ = registry_doc(tmp_path)
    change(doc)
    with pytest.raises(GateError, match=code):
        select(tmp_path, doc)


@pytest.mark.parametrize("value", [0., None])
def test_liquidity_amount_not_substituted_or_partial(tmp_path, value):
    p = provider()
    p.tables["etf_bars"].loc[0, "amount"] = value
    # first row is outside the 20-session window, so invalidate a window row.
    p.tables["etf_bars"].loc[1, "amount"] = value
    result = select(tmp_path, p=p)
    assert result["status"] == "MAPPING_ADMISSION_BLOCKED"
    assert result["selected"] == []


def test_collision_uses_next_verified_admitted_candidate(tmp_path):
    doc, _ = registry_doc(tmp_path)
    row = deepcopy(doc["entries"][0])
    row["industry_code"] = "801014"
    doc["entries"].append(row)
    p = provider()
    p.tables["etf_bars"].loc[p.tables["etf_bars"].symbol == "510000.SH", "amount"] = 100000.
    out = select(tmp_path, doc, p)
    assert out["status"] == "READY" and out["selected"][-1]["etf_code"] == "510005.SH"


def test_exchange_halt_beats_bar_and_eastmoney_default(tmp_path):
    p = provider()
    s = p.tables["trading_status"]
    s.loc[(s.symbol == "510000.SH") & (s.trade_date == SIGNAL.date()), ["source", "status", "is_trading"]] = ["exchange", "suspended", False]
    assert select(tmp_path, p=p)["status"] == "MAPPING_ADMISSION_BLOCKED"


def load_sidecar():
    root = Path(__file__).resolve().parents[2] / "services/cnequity-sidecar"
    sys.path.insert(0, str(root))
    try:
        spec = importlib.util.spec_from_file_location("sidecar_runner", root / "runner.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def test_sidecar_query_scope_exact_adjustment_and_no_asof(tmp_path):
    module = load_sidecar()
    from test_exports_industry import export_tables
    tables = export_tables()
    # Fake lake query transport only; no mock market rows published as real data.
    tables["industry_membership"][0]["symbol"] = "600001.SH"
    calls = []
    reverse = {"industry_members": "industry_membership", "trading_calendar": "trading_calendar",
               "instruments": "instruments", "trading_status": "trading_status", "index_bars": "benchmark_csi300"}
    class Frame:
        def __init__(self, rows): self.rows = rows
        def to_dicts(self): return deepcopy(self.rows)
    def load(dataset, **kw):
        calls.append((dataset, kw))
        target = "stock_bars" if kw.get("adjust") == "hfq" else "etf_bars" if dataset == "daily_bars" else reverse[dataset]
        return Frame(tables[target])
    cfg = {"paths": {"lake_root": str(tmp_path / "lake"), "export_root": str(tmp_path / "exports")},
        "export": {"start": "2020-01-01", "cutoff": "2026-09-24", "calendar_end": "2026-09-25",
            "etf_symbols": ["510001.SH"], "classification_version": "SWCLASS2021"}}
    pointer = module.export_lake(cfg, load, observed_at=SIGNAL)
    assert pointer["snapshot_id"]
    assert all("as_of" not in args and "universe" not in args for _, args in calls)
    stock = next(args for ds, args in calls if ds == "daily_bars" and args.get("adjust"))
    assert stock["strict_adj"] is False and stock["symbols"] == ["600001.SH"]
    assert not any(ds == "industry_index" for ds, _ in calls)


def test_sidecar_cdr_nonexact_row_rejected_without_thinning_membership(tmp_path):
    module = load_sidecar()
    from test_exports_industry import export_tables
    tables = export_tables()
    tables["industry_membership"][0]["symbol"] = "600001.SH"
    cdr_member = deepcopy(tables["industry_membership"][0])
    cdr_member["symbol"] = "689009.SH"
    tables["industry_membership"].append(cdr_member)
    cdr_bar = deepcopy(tables["stock_bars"][0])
    cdr_bar["symbol"] = "689009.SH"
    cdr_bar["adj_is_exact"] = False
    tables["stock_bars"].append(cdr_bar)

    class Frame:
        def __init__(self, rows): self.rows = rows
        def to_dicts(self): return deepcopy(self.rows)

    reverse = {"industry_members": "industry_membership", "trading_calendar": "trading_calendar",
               "instruments": "instruments", "trading_status": "trading_status",
               "index_bars": "benchmark_csi300"}
    def load(dataset, **kw):
        target = "stock_bars" if kw.get("adjust") == "hfq" else "etf_bars" if dataset == "daily_bars" else reverse[dataset]
        return Frame(tables[target])

    cfg = {"paths": {"lake_root": str(tmp_path / "lake"), "export_root": str(tmp_path / "exports")},
           "export": {"start": "2020-01-01", "cutoff": "2026-09-24", "calendar_end": "2026-09-25",
                      "etf_symbols": ["510001.SH"], "classification_version": "SWCLASS2021"}}
    pointer = module.export_lake(cfg, load, observed_at=SIGNAL)
    from strategies.etf_quant.runtime.exports import ExportProvider
    exported = ExportProvider(tmp_path / "exports" / pointer["snapshot_id"],
                              expected_identity=module.IDENTITY, now=SIGNAL)
    assert set(exported.tables["industry_membership"].symbol) == {"600001.SH", "689009.SH"}
    assert set(exported.tables["stock_bars"].symbol) == {"600001.SH"}
    assert exported.manifest["adjustment_exact_rows"] == 1
    assert exported.manifest["adjustment_rejected_rows"] == 1
    assert exported.manifest["datasets"]["stock_bars"]["query"]["rejected_nonexact_rows"] == 1
