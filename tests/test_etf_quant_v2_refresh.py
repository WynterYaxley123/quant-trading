"""Synthetic verified ETF supplement and closed factual boundary tests."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

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
            "open": [999.0, 11.0],
            "high": [999.0, 11.0],
            "low": [999.0, 11.0],
            "volume": [1000.0, 1000.0],
            "amount": [999000.0, 11000.0],
        }
    )
    fresh.write_parquet(path)
    observed = datetime(2026, 9, 30, 8, 0, tzinfo=timezone.utc)
    receipt = {
        "receipts": [
            {
                "symbol": "510001.SH",
                "bars_sha256": module.checksum(path),
                "source_commit": module.PIN,
                "data_cutoff": str(day),
                "observed_at": observed.isoformat(),
            }
        ]
    }
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
    supplemental = result.row(1, named=True)
    assert supplemental["source"] == "cnequity_public_tdx_protocol"
    assert supplemental["data_version"] == "PUBLIC_TDX_RECEIPT:" + module.checksum(path)
    assert supplemental["fetched_at"] == observed
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[1] / "services/cnequity-sidecar")
    )
    from export_streaming import _check_cells

    from strategies.etf_quant.runtime.exports import PROVENANCE, SCHEMAS

    _check_cells(supplemental, {**SCHEMAS["etf_bars"], **PROVENANCE})
    assert load(
        "daily_bars", symbols=["600000.SH"], start="2026-09-29", end=str(day), adjust="hfq"
    ).equals(old)
    assert len(calls) == 2 and old["close"].to_list() == [10.0]
    for field, invalid in (
        ("source_commit", "0" * 40),
        ("data_cutoff", "2026-09-29"),
        ("observed_at", "2026-09-30T08:00:00"),
        ("observed_at", "2099-01-01T08:00:00+00:00"),
    ):
        original = receipt["receipts"][0][field]
        receipt["receipts"][0][field] = invalid
        with pytest.raises(ValueError, match="ETF_EXPORT_RECEIPT_IDENTITY"):
            module.with_current_etf_bars(loader, ["510001.SH"], day, tmp_path, tmp_path / "source")
        receipt["receipts"][0][field] = original
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
