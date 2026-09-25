"""申万官方文件 fallback 的纯离线安全测试。"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from src.data.providers.shenwan_official import (
    PROVIDER,
    STOCK_CLASSIFICATION_FILENAME,
    STOCK_CLASSIFICATION_URL,
    RawFileRecord,
    ShenwanAdmissionError,
    ShenwanRawDataError,
    assert_level_b_admissible,
    discover_raw_files,
    initialize_manifest,
    load_manifest,
    parse_stock_classification,
    register_raw_file,
    sha256_file,
    verify_manifest,
    write_manifest,
)


def _record(path, *, version=None):
    return RawFileRecord(
        provider=PROVIDER,
        source_url=STOCK_CLASSIFICATION_URL,
        retrieved_at="2026-09-20T10:00:00+08:00",
        original_filename=path.name,
        sha256=sha256_file(path),
        classification_version=version,
        notes="browser download from official public URL",
    )


def test_initialize_and_load_empty_manifest(tmp_path):
    path = initialize_manifest(tmp_path)
    assert path.name == "manifest.json"
    assert load_manifest(tmp_path) == ()
    assert json.loads(path.read_text(encoding="utf-8"))["files"] == []


def test_discovery_excludes_manifest_and_is_stable(tmp_path):
    initialize_manifest(tmp_path)
    (tmp_path / "z.xls").write_bytes(b"z")
    (tmp_path / "a.xlsx").write_bytes(b"a")
    assert [path.name for path in discover_raw_files(tmp_path)] == ["a.xlsx", "z.xls"]


def test_register_records_sha256_without_modifying_raw_file(tmp_path):
    raw = tmp_path / STOCK_CLASSIFICATION_FILENAME
    raw.write_bytes(b"official bytes")
    before = raw.read_bytes()
    record = register_raw_file(
        raw.name,
        source_url=STOCK_CLASSIFICATION_URL,
        retrieved_at=None,
        classification_version=None,
        notes="retrieval time and version are unknown",
        raw_dir=tmp_path,
    )
    assert raw.read_bytes() == before
    assert record.sha256 == sha256_file(raw)
    assert record.retrieved_at is None
    assert record.classification_version is None
    assert verify_manifest(tmp_path) == (record,)


def test_verify_rejects_hash_mismatch(tmp_path):
    raw = tmp_path / STOCK_CLASSIFICATION_FILENAME
    raw.write_bytes(b"first")
    write_manifest((_record(raw),), tmp_path)
    raw.write_bytes(b"changed")
    with pytest.raises(ShenwanRawDataError, match="SHA256 不一致"):
        verify_manifest(tmp_path)


def test_verify_rejects_unregistered_raw_file(tmp_path):
    initialize_manifest(tmp_path)
    (tmp_path / "unregistered.xls").write_bytes(b"content")
    with pytest.raises(ShenwanRawDataError, match="未登记"):
        verify_manifest(tmp_path)


@pytest.mark.parametrize(
    "payload, message",
    [
        ("not-json", "无法解析"),
        ('{"schema_version": 1}', "顶层字段"),
        ('{"schema_version": 2, "files": []}', "schema_version"),
    ],
)
def test_malformed_manifest_is_rejected(tmp_path, payload, message):
    (tmp_path / "manifest.json").write_text(payload, encoding="utf-8")
    with pytest.raises(ShenwanRawDataError, match=message):
        load_manifest(tmp_path)


def test_manifest_rejects_non_official_or_non_https_source(tmp_path):
    raw = tmp_path / STOCK_CLASSIFICATION_FILENAME
    raw.write_bytes(b"content")
    record = _record(raw)
    bad = RawFileRecord(**{**record.__dict__, "source_url": "http://example.com/file.xls"})
    with pytest.raises(ShenwanRawDataError, match="官方 HTTPS"):
        write_manifest((bad,), tmp_path)


def test_parse_preserves_unknown_pit_fields_and_blocks_admission(tmp_path, monkeypatch):
    raw = tmp_path / STOCK_CLASSIFICATION_FILENAME
    raw.write_bytes(b"xls placeholder")
    write_manifest((_record(raw, version=None),), tmp_path)
    source = pd.DataFrame(
        {
            "股票代码": ["000001"],
            "计入日期": ["2021-12-13"],
            "行业代码": ["801780"],
            "更新日期": ["2022-01-01"],
        }
    )
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: source)

    frame = parse_stock_classification(tmp_path)
    assert frame.loc[0, "effective_from"] == pd.Timestamp("2021-12-13")
    assert pd.isna(frame.loc[0, "effective_to"])
    assert pd.isna(frame.loc[0, "available_at"])
    assert pd.isna(frame.loc[0, "classification_version"])
    assert frame.loc[0, "source_retrieved_at"] == pd.Timestamp(
        "2026-09-20T10:00:00+08:00"
    )
    assert frame.loc[0, "source_url"] == STOCK_CLASSIFICATION_URL
    assert frame.loc[0, "source_updated_at"] == pd.Timestamp("2022-01-01")
    with pytest.raises(ShenwanAdmissionError, match="available_at"):
        assert_level_b_admissible(frame)


def test_unknown_retrieval_time_also_blocks_admission(tmp_path, monkeypatch):
    raw = tmp_path / STOCK_CLASSIFICATION_FILENAME
    raw.write_bytes(b"xls placeholder")
    record = RawFileRecord(
        **{**_record(raw, version="SW2021").__dict__, "retrieved_at": None}
    )
    write_manifest((record,), tmp_path)
    source = pd.DataFrame(
        {
            "股票代码": ["000001"],
            "计入日期": ["2021-12-13"],
            "行业代码": ["801780"],
            "更新日期": ["2022-01-01"],
        }
    )
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: source)
    frame = parse_stock_classification(tmp_path)
    with pytest.raises(ShenwanAdmissionError, match="source_retrieved_at"):
        assert_level_b_admissible(frame)


def test_parse_rejects_malformed_excel_columns(tmp_path, monkeypatch):
    raw = tmp_path / STOCK_CLASSIFICATION_FILENAME
    raw.write_bytes(b"xls placeholder")
    write_manifest((_record(raw),), tmp_path)
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: pd.DataFrame({"股票代码": ["1"]}))
    with pytest.raises(ShenwanRawDataError, match="缺少字段"):
        parse_stock_classification(tmp_path)


def test_parse_rejects_excel_reader_failure(tmp_path, monkeypatch):
    raw = tmp_path / STOCK_CLASSIFICATION_FILENAME
    raw.write_bytes(b"not really xls")
    write_manifest((_record(raw),), tmp_path)

    def explode(*args, **kwargs):
        raise ValueError("bad workbook")

    monkeypatch.setattr(pd, "read_excel", explode)
    with pytest.raises(ShenwanRawDataError, match="无法读取"):
        parse_stock_classification(tmp_path)
