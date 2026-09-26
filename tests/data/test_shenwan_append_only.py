"""Synthetic staged contracts; no source download or canonical-file writes."""

from copy import deepcopy

import pandas as pd
import pytest

from src.data.providers.shenwan_append_only import ENDPOINT, PROVIDER, audit_append_only, audit_source_overlap, canonical_bytes
from src.data.providers.shenwan_sector import OHLCVA_COLUMNS, snapshot_id


@pytest.fixture
def tables():
    codes = ["801012", "801193"]
    raw = {f"sector_history/{code}.json": "a" * 64 for code in codes}
    raw.update({"sector_history_manifest.json": "b" * 64, "StockClassifyUse_stock.xls": "c" * 64})
    updated = {**raw, **{f"sector_history/{code}.json": "d" * 64 for code in codes},
               "sector_history_manifest.json": "e" * 64}
    code_fp = {"parser.py": "f" * 64}
    records = []
    for code in codes:
        records.append({"date": pd.Timestamp("2026-09-18"), "sector_code": code, "sector_name": code,
            "open": 1.0, "high": 2.0, "low": 1.0, "close": 1.5, "volume": 10.0, "amount": float("nan"),
            "source_provider": PROVIDER, "source_url": ENDPOINT.format(sector_code=code),
            "source_retrieved_at": "2026-09-20T19:16:00+08:00", "source_filename": f"sector_history/{code}.json",
            "source_sha256": "a" * 64, "source_snapshot": "a" * 64, "source_row": 0,
            "is_valid_ohlc": True, "quality_violations": ""})
    # Keep a real-shaped historical invalid observation unmodified.
    records[1].update({"high": 1.0, "is_valid_ohlc": False, "quality_violations": "high_below_open_close_or_low"})
    parent = pd.DataFrame(records, columns=OHLCVA_COLUMNS)
    new = deepcopy(records)
    for row in new:
        row.update({"date": pd.Timestamp("2026-09-21"), "source_sha256": "d" * 64,
                    "source_snapshot": "d" * 64, "source_retrieved_at": "2026-09-22T10:00:00+08:00", "source_row": 1})
    staged = pd.concat([parent, pd.DataFrame(new, columns=OHLCVA_COLUMNS)], ignore_index=True)
    params = {"cutoff": "2026-09-18", "sector_codes": codes, "parent_snapshot": snapshot_id(raw, code_fingerprints=code_fp),
              "parent_raw": raw, "staged_raw": updated, "code_fingerprints": code_fp, "as_of": "2026-09-26"}
    return parent, staged, params


def test_valid_append_preserves_parent_and_anomaly(tables):
    parent, staged, params = tables
    original = parent.copy(deep=True)
    result = audit_append_only(parent, staged, **params)
    assert result["appendedRows"] == 2 and result["historicalRevisions"] == 0
    assert result["snapshotId"] == snapshot_id(params["staged_raw"], code_fingerprints=params["code_fingerprints"])
    assert result["parentSnapshotId"] != result["snapshotId"]
    assert result["parentInvalidOhlcCount"] == 1
    assert result["historicalPrefixHashBefore"] == result["historicalPrefixHashAfter"]
    assert parent.equals(original) and result["dataApplied"] is False
    assert result["rawBytesVerifiedByThisFunction"] is False


@pytest.mark.parametrize("column,value", [
    ("open", 1.1), ("high", 4.0), ("low", 0.5), ("close", 1.6),
    ("volume", 12.0), ("amount", 0.0), ("sector_name", "revised"),
    ("source_sha256", "f" * 64), ("source_retrieved_at", "2026-09-26T00:00:00+08:00"),
    ("quality_violations", "repaired")])
def test_reject_any_historical_revision_and_nan_repair(tables, column, value):
    parent, staged, params = tables
    staged.loc[0, column] = value
    with pytest.raises(ValueError, match="HISTORICAL_DATA_REVISION_BLOCKER"):
        audit_append_only(parent, staged, **params)


def test_reject_invalid_ohlc_repair(tables):
    parent, staged, params = tables
    staged.loc[1, ["high", "is_valid_ohlc", "quality_violations"]] = [2.0, True, ""]
    with pytest.raises(ValueError, match="HISTORICAL_DATA_REVISION"):
        audit_append_only(parent, staged, **params)


def test_reject_historical_deletion(tables):
    parent, staged, params = tables
    with pytest.raises(ValueError, match="HISTORICAL_ROW_DELETION"):
        audit_append_only(parent, staged.drop(index=0), **params)


def test_reject_duplicate_key(tables):
    parent, staged, params = tables
    with pytest.raises(ValueError, match="DUPLICATE"):
        audit_append_only(parent, pd.concat([staged, staged.iloc[[0]]]), **params)


def test_reject_universe_expansion(tables):
    parent, staged, params = tables
    staged.loc[2, "sector_code"] = "999999"
    with pytest.raises(ValueError, match="U0_IDENTITY"):
        audit_append_only(parent, staged, **params)


@pytest.mark.parametrize("change", ["column", "dtype", "source", "url", "catalog", "raw_set", "snapshot", "future", "order", "quality", "retrieved", "raw_sha"])
def test_fail_closed_variants(tables, change):
    parent, staged, params = tables
    if change == "column":
        staged["extra"] = 1
    elif change == "dtype":
        staged["volume"] = staged["volume"].astype(str)
    elif change == "source":
        staged.loc[2, "source_provider"] = "alternate"
    elif change == "url":
        staged.loc[2, "source_url"] += "&adjust=1"
    elif change == "catalog":
        params["staged_raw"]["StockClassifyUse_stock.xls"] = "0" * 64
    elif change == "raw_set":
        params["staged_raw"]["new.json"] = "0" * 64
    elif change == "snapshot":
        params["parent_snapshot"] = "0" * 64
    elif change == "future":
        staged.loc[2, "date"] = pd.Timestamp("2026-09-28")
    elif change == "order":
        staged = staged.iloc[[2, 0, 1, 3]].reset_index(drop=True)
    elif change == "quality":
        staged.loc[3, "is_valid_ohlc"] = True
    elif change == "retrieved":
        staged.loc[2, "source_retrieved_at"] = None
    elif change == "raw_sha":
        params["staged_raw"]["sector_history/801012.json"] = "unknown"
    with pytest.raises(ValueError):
        audit_append_only(parent, staged, **params)


def test_no_fill_for_missing_new_sector_bar(tables):
    parent, staged, params = tables
    staged = staged.drop(index=3)
    result = audit_append_only(parent, staged, **params)
    assert result["appendedRowsBySector"] == {"801012": 1, "801193": 0}
    assert result["appendedRows"] == 1 and len(staged) == 3


def test_noop_keeps_snapshot_and_is_deterministic(tables):
    parent, _, params = tables
    params["staged_raw"] = params["parent_raw"].copy()
    first = audit_append_only(parent, parent.copy(), **params)
    second = audit_append_only(parent, parent.copy(), **params)
    assert first["snapshotId"] == first["parentSnapshotId"] and first["appendedRows"] == 0
    assert canonical_bytes(first) == canonical_bytes(second)


def test_source_dictionary_order_does_not_change_result(tables):
    parent, staged, params = tables
    first = audit_append_only(parent, staged, **params)
    params["staged_raw"] = dict(reversed(list(params["staged_raw"].items())))
    assert canonical_bytes(first) == canonical_bytes(audit_append_only(parent, staged, **params))


def test_raw_overlap_permits_new_retrieval_metadata_but_not_rewrites(tables):
    parent, staged, params = tables
    staged["source_retrieved_at"] = "2026-09-22T10:00:00+08:00"
    staged["source_sha256"] = "d" * 64
    result = audit_source_overlap(parent, staged, cutoff=params["cutoff"], sector_codes=params["sector_codes"])
    assert result["overlapRowsChecked"] == 2 and result["historicalRevisions"] == 0


@pytest.mark.parametrize("change", ["price", "nan_repair", "quality_repair", "drop", "backfill", "duplicate", "schema"])
def test_source_overlap_rejects_revision_before_candidate_extraction(tables, change):
    parent, staged, params = tables
    if change == "price":
        staged.loc[0, "close"] = 1.6
    elif change == "nan_repair":
        staged.loc[0, "amount"] = 0.0
    elif change == "quality_repair":
        staged.loc[1, "is_valid_ohlc"] = True
    elif change == "drop":
        staged = staged.drop(index=0)
    elif change == "backfill":
        staged.loc[2, "date"] = pd.Timestamp("2026-09-17")
    elif change == "duplicate":
        staged = pd.concat([staged, staged.iloc[[0]]])
    else:
        staged["extra"] = 0
    with pytest.raises(ValueError):
        audit_source_overlap(parent, staged, cutoff=params["cutoff"], sector_codes=params["sector_codes"])
