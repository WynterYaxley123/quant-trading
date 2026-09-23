"""申万行业 canonical、来源、时点和缺日的确定性离线测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.data.loaders import load_sector_catalog, load_sector_ohlcva, load_sector_panel
from src.data.providers.shenwan_official import ShenwanRawDataError, sha256_file
from src.data.providers.shenwan_sector import (
    _violations, audit_coverage, candidate_research_range,
    load_history_manifest, load_raw_catalog, parse_classification_with_intervals,
    parse_sector_ohlcva, snapshot_id,
)
from src.data.providers.shenwan_sector_admission import evaluate_admission


def _response(rows, count, *, next_url=None, previous_url=None):
    return {"code": "200", "message": "ok", "data": {
        "count": count, "next": next_url, "previous": previous_url, "results": rows,
    }}


def _fixture(tmp_path: Path):
    root = tmp_path / "data" / "raw" / "shenwan"
    catalog_dir = root / "sector_catalog"
    history_dir = root / "sector_history"
    catalog_dir.mkdir(parents=True)
    history_dir.mkdir()
    rows = [
        {"swindexcode": "801012", "swindexname": "农产品加工"},
        {"swindexcode": "801014", "swindexname": "饲料"},
    ]
    link = "http://www.swsresearch.com/api/index_publish/current/?indextype=%E4%BA%8C%E7%BA%A7%E8%A1%8C%E4%B8%9A&page=2&page_size=50"
    (catalog_dir / "sws_index_catalog_L2_page1.json").write_text(
        json.dumps(_response(rows[:1], 2, next_url=link)), encoding="utf-8"
    )
    (catalog_dir / "sws_index_catalog_L2_page2.json").write_text(
        json.dumps(_response(rows[1:], 2, previous_url=link)), encoding="utf-8"
    )
    (catalog_dir / "sws_index_catalog_L2.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )
    manifest_files = []
    for code, name in (("801012", "农产品加工"), ("801014", "饲料")):
        bars = []
        for date in ("2024-01-02", "2024-01-03", "2024-01-04"):
            bars.append({
                "swindexcode": code, "bargaindate": date,
                "openindex": 10, "maxindex": 11, "minindex": 9, "closeindex": 10.5,
                "bargainamount": None, "bargainsum": None,
            })
        path = history_dir / f"{code}.json"
        path.write_text(json.dumps({"code": "200", "data": bars}), encoding="utf-8")
        manifest_files.append({
            "sector_code": code, "sector_name": name,
            "source_url": f"https://www.swsresearch.com/institute-sw/api/index_publish/trend/?swindexcode={code}&period=DAY",
            "retrieved_at": "2026-09-20T19:16:00+08:00",
            "sha256": sha256_file(path), "row_count": 3,
            "start_date": "2024-01-02", "end_date": "2024-01-04",
            "raw_path": f"data/raw/shenwan/sector_history/{code}.json",
        })
    manifest = tmp_path / "history_manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "provider": "shenwan_research_official",
        "period": "DAY", "sector_count": 2,
        "retrieved_at": "2026-09-20T19:16:00+08:00", "files": manifest_files,
    }), encoding="utf-8")
    return root, manifest


def test_level2_catalog_provenance_unique_and_name(tmp_path):
    raw, manifest = _fixture(tmp_path)
    catalog, hashes = load_raw_catalog(raw, retrieved_at="2026-09-20T19:16:00+08:00")
    assert catalog.sector_code.tolist() == ["801012", "801014"]
    assert catalog.sector_level.eq(2).all()
    assert catalog.sector_name.notna().all()
    assert len(hashes) == 3
    assert catalog.source_sha256.iloc[0] == sha256_file(raw / catalog.source_filename.iloc[0])
    _, by_code = load_history_manifest(raw, manifest)
    assert set(by_code) == set(catalog.sector_code)


def test_catalog_rejects_missing_level_evidence_or_duplicate(tmp_path):
    raw, _ = _fixture(tmp_path)
    page = raw / "sector_catalog/sws_index_catalog_L2_page1.json"
    payload = json.loads(page.read_text())
    payload["data"]["next"] = "http://example.org/?indextype=一级行业"
    page.write_text(json.dumps(payload))
    with pytest.raises(ShenwanRawDataError, match="indextype"):
        load_raw_catalog(raw, retrieved_at=None)
    payload["data"]["next"] = "http://www.swsresearch.com/api/index_publish/current/?indextype=二级行业"
    payload["data"]["results"][0]["swindexname"] = ""
    page.write_text(json.dumps(payload))
    with pytest.raises(ShenwanRawDataError, match="代码/名称"):
        load_raw_catalog(raw, retrieved_at=None)
    payload["data"]["results"][0]["swindexname"] = "农产品加工"
    payload["data"]["results"][0]["swindexcode"] = "801014"
    page.write_text(json.dumps(payload))
    mirror = raw / "sector_catalog/sws_index_catalog_L2.jsonl"
    lines = mirror.read_text().splitlines()
    lines[0] = json.dumps(payload["data"]["results"][0])
    mirror.write_text("\n".join(lines) + "\n")
    with pytest.raises(ShenwanRawDataError, match="sector_code 重复"):
        load_raw_catalog(raw, retrieved_at=None)


def test_manifest_detects_raw_mutation_and_parser_does_not_modify_raw(tmp_path):
    raw, manifest = _fixture(tmp_path)
    catalog, _ = load_raw_catalog(raw, retrieved_at=None)
    before = {path: sha256_file(path) for path in raw.rglob("*") if path.is_file()}
    _, by_code = load_history_manifest(raw, manifest)
    frame = parse_sector_ohlcva(raw, catalog, by_code)
    assert len(frame) == 6
    assert {path: sha256_file(path) for path in before} == before
    path = raw / "sector_history/801014.json"
    path.write_text(path.read_text() + " ")
    with pytest.raises(ShenwanRawDataError, match="SHA256"):
        load_history_manifest(raw, manifest)


def test_ohlc_invalid_is_flagged_without_rewriting_or_fill(tmp_path):
    raw, manifest = _fixture(tmp_path)
    path = raw / "sector_history/801014.json"
    payload = json.loads(path.read_text())
    payload["data"][2]["closeindex"] = 12  # 原始 close 高于 high
    payload["data"].pop(1)  # 区间内部缺一个 session，不补
    path.write_text(json.dumps(payload))
    meta = json.loads(manifest.read_text())
    meta["files"][1].update(sha256=sha256_file(path), row_count=2)
    manifest.write_text(json.dumps(meta))
    catalog, _ = load_raw_catalog(raw, retrieved_at=None)
    _, by_code = load_history_manifest(raw, manifest)
    frame = parse_sector_ohlcva(raw, catalog, by_code)
    bad = frame.loc[~frame.is_valid_ohlc]
    assert len(bad) == 1 and bad.iloc[0].close == 12
    assert bad.iloc[0].quality_violations == "high_below_open_close_or_low"
    assert frame.sector_code.eq("801014").sum() == 2
    summary, per = audit_coverage(frame, catalog)
    assert summary["invalid_ohlc_count"] == 1
    assert summary["missing_common_sessions_total"] == 1
    assert per.loc[per.sector_code.eq("801014"), "missing_common_sessions"].iloc[0] == 1


def test_duplicate_or_reverse_dates_are_rejected(tmp_path):
    raw, manifest = _fixture(tmp_path)
    path = raw / "sector_history/801012.json"
    payload = json.loads(path.read_text())
    payload["data"][1]["bargaindate"] = "2024-01-02"
    path.write_text(json.dumps(payload))
    meta = json.loads(manifest.read_text())
    meta["files"][0]["sha256"] = sha256_file(path)
    manifest.write_text(json.dumps(meta))
    catalog, _ = load_raw_catalog(raw, retrieved_at=None)
    _, by_code = load_history_manifest(raw, manifest)
    with pytest.raises(ShenwanRawDataError, match="倒序/重复"):
        parse_sector_ohlcva(raw, catalog, by_code)


def test_date_after_recorded_snapshot_is_rejected(tmp_path):
    raw, manifest = _fixture(tmp_path)
    path = raw / "sector_history/801012.json"
    payload = json.loads(path.read_text())
    payload["data"][-1]["bargaindate"] = "2026-09-21"
    path.write_text(json.dumps(payload))
    meta = json.loads(manifest.read_text())
    meta["files"][0].update(sha256=sha256_file(path), end_date="2026-09-21")
    manifest.write_text(json.dumps(meta))
    catalog, _ = load_raw_catalog(raw, retrieved_at=None)
    _, by_code = load_history_manifest(raw, manifest)
    with pytest.raises(ShenwanRawDataError, match="未来交易日期"):
        parse_sector_ohlcva(raw, catalog, by_code)


def test_nullable_volume_amount_and_invalid_bounds():
    row = {"open": 10, "high": 11, "low": 9, "close": 10, "volume": None, "amount": None}
    assert _violations(row) == ""
    row["volume"] = -1
    assert _violations(row) == "invalid_volume"


def test_classification_derived_intervals_remain_separate(monkeypatch):
    from src.data.providers import shenwan_sector as module
    source = pd.DataFrame({
        "symbol": ["000001", "000001", "000002"],
        "sector_code": ["440101", "480101", "440101"],
        "sector_name": [pd.NA] * 3,
        "effective_from": pd.to_datetime(["2001-01-01", "2014-02-21", "2020-01-01"]),
        "effective_to": [pd.NaT] * 3, "available_at": [pd.NaT] * 3,
        "source_updated_at": pd.to_datetime(["2024-01-01"] * 3),
        "classification_version": [pd.NA] * 3,
        "source_provider": ["official"] * 3, "source_url": ["https://www.swsresearch.com/file"] * 3,
        "source_retrieved_at": [pd.NaT] * 3,
        "source_filename": ["StockClassifyUse_stock.xls"] * 3,
        "source_sha256": ["a" * 64] * 3,
    })
    monkeypatch.setattr(module, "parse_stock_classification", lambda _: source)
    frame = parse_classification_with_intervals("unused")
    assert frame.loc[0, "effective_to_derived"] == pd.Timestamp("2014-02-21")
    assert frame.effective_to_official.isna().all()
    assert frame.available_at.isna().all()
    assert frame.classification_version.isna().all()
    assert frame.sector_level.isna().all()  # 两种 sector_code 命名空间不能猜测映射


def test_snapshot_id_stable_under_mapping_order_and_changes_on_hash():
    first = snapshot_id({"a": "1" * 64, "b": "2" * 64})
    assert first == snapshot_id({"b": "2" * 64, "a": "1" * 64})
    assert first != snapshot_id({"a": "3" * 64, "b": "2" * 64})
    assert first != snapshot_id(
        {"a": "1" * 64, "b": "2" * 64}, code_fingerprints={"parser": "4" * 64}
    )


def test_admission_fixed_and_blocked():
    catalog = pd.DataFrame({"sector_code": ["801012"], "sector_name": ["农业"], "sector_level": [2]})
    market = pd.DataFrame({"sector_code": ["801012"], "date": pd.to_datetime(["2024-01-02"]), "is_valid_ohlc": [True]})
    classification = pd.DataFrame({
        "classification_version": [pd.NA], "effective_from": [pd.Timestamp("2021-01-01")],
        "effective_to_official": [pd.NaT], "available_at": [pd.NaT],
    })
    decision = evaluate_admission(catalog, market, classification, provenance_verified=True,
                                  candidate_start="2024-01-02", candidate_end="2024-01-02")
    assert decision.level == "FIXED_CLASSIFICATION_RESEARCH" and not decision.strict_pit
    denied = evaluate_admission(catalog, market, classification, provenance_verified=False,
                                candidate_start="2024-01-02", candidate_end="2024-01-02")
    assert denied.level == "DATA_NOT_ADMISSIBLE"
    classification.loc[0, "classification_version"] = "verified-version"
    classification.loc[0, "effective_to_official"] = pd.Timestamp("2024-12-31")
    classification.loc[0, "available_at"] = pd.Timestamp("2021-01-02")
    strict = evaluate_admission(catalog, market, classification, provenance_verified=True,
                                candidate_start="2024-01-02", candidate_end="2024-01-02",
                                classification_version_proven=True, publication_timing_proven=True,
                                no_future_classification_leakage_proven=True)
    assert strict.level == "STRICT_PIT" and strict.strict_pit


def test_loader_panel_no_fill_and_rejects_invalid(tmp_path):
    root = tmp_path / "processed"
    root.mkdir()
    pd.DataFrame({"sector_code": ["801012", "801014"], "sector_name": ["农业", "饲料"],
                  "sector_level": [2, 2], **{col: [None, None] for col in (
                      "classification_version", "effective_from", "effective_to", "available_at",
                      "source_provider", "source_url", "source_retrieved_at", "source_filename", "source_sha256")}}).to_csv(root / "sector_catalog.csv", index=False)
    base = {
        "sector_name": "农业", "open": 10, "high": 11, "low": 9, "close": 10.5,
        "volume": None, "amount": None, "source_provider": "official", "source_url": "https://www.swsresearch.com/",
        "source_retrieved_at": None, "source_filename": "file", "source_sha256": "a" * 64,
        "source_snapshot": "a" * 64, "source_row": 0, "is_valid_ohlc": True,
        "quality_violations": "",
    }
    pd.DataFrame([
        {**base, "sector_code": "801012", "date": "2024-01-02"},
        {**base, "sector_code": "801012", "date": "2024-01-03"},
        {**base, "sector_code": "801014", "date": "2024-01-03", "sector_name": "饲料"},
    ]).to_csv(root / "sector_ohlcva.csv", index=False)
    (root / "sector_admission.json").write_text(json.dumps({
        "data_snapshot_id": "snapshot", "canonical_hashes": {
            name: sha256_file(root / name)
            for name in ("sector_catalog.csv", "sector_ohlcva.csv")
        },
    }))
    assert len(load_sector_catalog(root)) == 2
    assert len(load_sector_ohlcva("801012", processed_dir=root)) == 2
    panel = load_sector_panel(["801012", "801014"], "2024-01-02", "2024-01-03", processed_dir=root)
    assert len(panel) == 3
    assert panel[["date", "sector_code"]].values.tolist() == [
        [pd.Timestamp("2024-01-02"), "801012"],
        [pd.Timestamp("2024-01-03"), "801012"],
        [pd.Timestamp("2024-01-03"), "801014"],
    ]
    modified = pd.read_csv(root / "sector_ohlcva.csv")
    modified.loc[0, "is_valid_ohlc"] = False
    modified.to_csv(root / "sector_ohlcva.csv", index=False)
    with pytest.raises(ShenwanRawDataError, match="SHA256"):
        load_sector_ohlcva("801012", processed_dir=root)
    meta = json.loads((root / "sector_admission.json").read_text())
    meta["canonical_hashes"]["sector_ohlcva.csv"] = sha256_file(root / "sector_ohlcva.csv")
    (root / "sector_admission.json").write_text(json.dumps(meta))
    with pytest.raises(ShenwanRawDataError, match="质量标记与实际数值不一致"):
        load_sector_ohlcva("801012", processed_dir=root)
    modified.loc[0, "close"] = 12
    modified["quality_violations"] = modified["quality_violations"].astype("string")
    modified.loc[0, "quality_violations"] = "high_below_open_close_or_low"
    modified.to_csv(root / "sector_ohlcva.csv", index=False)
    meta["canonical_hashes"]["sector_ohlcva.csv"] = sha256_file(root / "sector_ohlcva.csv")
    (root / "sector_admission.json").write_text(json.dumps(meta))
    with pytest.raises(ShenwanRawDataError, match="禁止进入模型"):
        load_sector_ohlcva("801012", processed_dir=root)


def test_candidate_range_counts_sessions_and_reserves_forward_labels():
    days = pd.bdate_range("2021-01-01", periods=500)
    market = pd.DataFrame({
        "date": days, "sector_code": ["801012"] * len(days),
        "is_valid_ohlc": [True] * len(days),
    })
    summary = {"common_start_date": str(days[0].date()), "common_end_date": str(days[-1].date())}
    start, end = candidate_research_range(market, summary)
    assert start is not None and end == str(days[-121].date())
    assert pd.Timestamp(start) > days[240]
    market.loc[market.date.eq(days[250]), "is_valid_ohlc"] = False
    later, _ = candidate_research_range(market, summary)
    assert later is None or pd.Timestamp(later) > pd.Timestamp(start)
