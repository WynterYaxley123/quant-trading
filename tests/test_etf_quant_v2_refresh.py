"""Synthetic verified ETF supplement and closed factual boundary tests."""

import json
from datetime import date

import polars as pl
import pytest

from strategies.etf_quant_v2 import refresh as module


def test_normalized_export_supplement_preserves_existing_keys_and_stock_queries(
    tmp_path, monkeypatch
):
    day = date(2026, 9, 30)
    directory = tmp_path / str(day)
    directory.mkdir()
    path = directory / "510001.SH.parquet"
    fresh = pl.DataFrame(
        {
            "symbol": ["510001.SH"] * 2,
            "trade_date": [date(2026, 9, 29), day],
            "close": [999.0, 11.0],
        }
    )
    fresh.write_parquet(path)
    receipt = {"receipts": [{"symbol": "510001.SH", "bars_sha256": module.checksum(path)}]}
    monkeypatch.setattr(module, "refresh", lambda *args: receipt)
    old = pl.DataFrame(
        {"symbol": ["510001.SH"], "trade_date": [date(2026, 9, 29)], "close": [10.0]}
    )
    calls = []

    def loader(dataset, **kwargs):
        calls.append((dataset, kwargs))
        return old

    load = module.with_current_etf_bars(loader, ["510001.SH"], day, tmp_path, tmp_path / "source")
    result = load(
        "daily_bars", symbols=["510001.SH"], start="2026-09-29", end=str(day), adjust=None
    )
    assert result["close"].to_list() == [10.0, 11.0]
    assert load(
        "daily_bars", symbols=["600000.SH"], start="2026-09-29", end=str(day), adjust="hfq"
    ).equals(old)
    assert len(calls) == 2 and old["close"].to_list() == [10.0]
    path.write_bytes(b"SYNTHETIC tamper")
    with pytest.raises(ValueError, match="ETF_EXPORT_RECEIPT_HASH"):
        module.with_current_etf_bars(loader, ["510001.SH"], day, tmp_path, tmp_path / "source")


def test_factual_snapshot_rejects_unregistered_file_set_before_reading_content(tmp_path):
    doc = {
        "source_commit": module.PIN,
        "source_identity": "CNEQUITY_LOCAL_LAKE_V1",
        "files": {"unregistered.json": "a" * 64},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="CLOSED_FACTUAL_EXPORT"):
        module.verified_snapshot(tmp_path)
