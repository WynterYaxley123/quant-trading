"""申万官方原始文件的本地登记、校验与解析。

本模块刻意不负责下载。在线获取与本地解析解耦，避免调用方在 TLS
失败时关闭证书校验。用户可以通过正常浏览器取得官方公开文件，再把未经
修改的文件放入 ``data/raw/shenwan`` 并登记到 manifest。

这里也不判断数据是否已经满足 LEVEL B。解析结果保留缺失的时点字段，
并提供显式准入检查；绝不从当前分类倒推出历史有效期或发布时间。
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

PROVIDER = "shenwan_research_official"
DEFAULT_RAW_DIR = Path("data/raw/shenwan")
MANIFEST_FILENAME = "manifest.json"
STOCK_CLASSIFICATION_FILENAME = "StockClassifyUse_stock.xls"
STOCK_CLASSIFICATION_URL = (
    "https://www.swsresearch.com/swindex/pdf/SwClass2021/StockClassifyUse_stock.xls"
)

MANIFEST_REQUIRED_FIELDS = frozenset(
    {
        "provider",
        "source_url",
        "retrieved_at",
        "original_filename",
        "sha256",
        "classification_version",
        "notes",
    }
)
CANONICAL_CLASSIFICATION_COLUMNS = (
    "symbol",
    "sector_code",
    "sector_name",
    "effective_from",
    "effective_to",
    "available_at",
    "source_updated_at",
    "classification_version",
    "source_provider",
    "source_url",
    "source_retrieved_at",
    "source_filename",
    "source_sha256",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CLASSIFICATION_REQUIRED_COLUMNS = frozenset({"股票代码", "计入日期", "行业代码", "更新日期"})


class ShenwanRawDataError(ValueError):
    """申万原始文件、manifest 或解析结果不可信。"""


class ShenwanAdmissionError(ShenwanRawDataError):
    """数据尚无足够的 point-in-time 证据，禁止 LEVEL B 准入。"""


@dataclass(frozen=True)
class RawFileRecord:
    """manifest 中一份不可变官方原文件的来源记录。"""

    provider: str
    source_url: str
    retrieved_at: str | None
    original_filename: str
    sha256: str
    classification_version: str | None
    notes: str


def sha256_file(path: str | Path) -> str:
    """流式计算文件 SHA256，不改变文件内容或时间戳。"""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_raw_files(raw_dir: str | Path = DEFAULT_RAW_DIR) -> tuple[Path, ...]:
    """发现 raw 目录直属文件；manifest 本身不属于原始数据。"""

    root = Path(raw_dir)
    if not root.exists():
        return ()
    if not root.is_dir():
        raise ShenwanRawDataError(f"raw 路径不是目录: {root}")
    return tuple(
        sorted(
            (path for path in root.iterdir() if path.is_file() and path.name != MANIFEST_FILENAME),
            key=lambda path: path.name,
        )
    )


def _is_official_url(value: str) -> bool:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        host == "swsresearch.com" or host.endswith(".swsresearch.com")
    )


def _validate_timestamp(value: str | None, *, field: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise ShenwanRawDataError(f"{field} 必须是带时区 ISO-8601 字符串或 null")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ShenwanRawDataError(f"{field} 不是有效 ISO-8601 时间: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ShenwanRawDataError(f"{field} 必须包含时区: {value!r}")


def _record_from_mapping(item: object, *, index: int) -> RawFileRecord:
    if not isinstance(item, dict):
        raise ShenwanRawDataError(f"manifest files[{index}] 必须是对象")
    missing = MANIFEST_REQUIRED_FIELDS.difference(item)
    unknown = set(item).difference(MANIFEST_REQUIRED_FIELDS)
    if missing:
        raise ShenwanRawDataError(f"manifest files[{index}] 缺少字段: {sorted(missing)}")
    if unknown:
        raise ShenwanRawDataError(f"manifest files[{index}] 含未知字段: {sorted(unknown)}")

    record = RawFileRecord(**item)
    if record.provider != PROVIDER:
        raise ShenwanRawDataError(f"manifest files[{index}] provider 必须为 {PROVIDER!r}")
    if not _is_official_url(record.source_url):
        raise ShenwanRawDataError(
            f"manifest files[{index}] source_url 不是申万官方 HTTPS: {record.source_url!r}"
        )
    if Path(record.original_filename).name != record.original_filename:
        raise ShenwanRawDataError(f"manifest files[{index}] original_filename 不得包含路径")
    if not _SHA256_RE.fullmatch(record.sha256):
        raise ShenwanRawDataError(f"manifest files[{index}] sha256 格式无效")
    if record.classification_version is not None and (
        not isinstance(record.classification_version, str)
        or not record.classification_version.strip()
    ):
        raise ShenwanRawDataError(
            f"manifest files[{index}] classification_version 必须是非空字符串或 null"
        )
    if not isinstance(record.notes, str):
        raise ShenwanRawDataError(f"manifest files[{index}] notes 必须是字符串")
    _validate_timestamp(record.retrieved_at, field=f"files[{index}].retrieved_at")
    return record


def load_manifest(raw_dir: str | Path = DEFAULT_RAW_DIR) -> tuple[RawFileRecord, ...]:
    """严格加载 manifest；不存在不等同于空 manifest。"""

    path = Path(raw_dir) / MANIFEST_FILENAME
    if not path.is_file():
        raise ShenwanRawDataError(f"manifest 不存在: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ShenwanRawDataError(f"manifest 无法解析: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ShenwanRawDataError("manifest 顶层必须是对象")
    if set(payload) != {"schema_version", "files"}:
        raise ShenwanRawDataError("manifest 顶层字段必须且只能包含 schema_version 与 files")
    if payload["schema_version"] != 1:
        raise ShenwanRawDataError(
            f"不支持的 manifest schema_version: {payload['schema_version']!r}"
        )
    if not isinstance(payload["files"], list):
        raise ShenwanRawDataError("manifest files 必须是数组")

    records = tuple(
        _record_from_mapping(item, index=index) for index, item in enumerate(payload["files"])
    )
    names = [record.original_filename for record in records]
    if len(names) != len(set(names)):
        raise ShenwanRawDataError("manifest original_filename 不得重复")
    return records


def write_manifest(
    records: Iterable[RawFileRecord],
    raw_dir: str | Path = DEFAULT_RAW_DIR,
) -> Path:
    """原子写入 manifest；不会写入或修改任何原始文件。"""

    root = Path(raw_dir)
    root.mkdir(parents=True, exist_ok=True)
    normalized = tuple(records)
    # 借助与读取相同的验证器，避免写出项目自身无法读取的 manifest。
    for index, record in enumerate(normalized):
        _record_from_mapping(asdict(record), index=index)
    names = [record.original_filename for record in normalized]
    if len(names) != len(set(names)):
        raise ShenwanRawDataError("manifest original_filename 不得重复")

    payload = {
        "schema_version": 1,
        "files": [asdict(record) for record in normalized],
    }
    destination = root / MANIFEST_FILENAME
    temporary = root / f".{MANIFEST_FILENAME}.tmp"
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def initialize_manifest(raw_dir: str | Path = DEFAULT_RAW_DIR) -> Path:
    """创建空 manifest；已存在时绝不覆盖。"""

    path = Path(raw_dir) / MANIFEST_FILENAME
    if path.exists():
        load_manifest(raw_dir)
        return path
    return write_manifest((), raw_dir)


def register_raw_file(
    filename: str,
    *,
    source_url: str,
    retrieved_at: str | None,
    classification_version: str | None,
    notes: str,
    raw_dir: str | Path = DEFAULT_RAW_DIR,
) -> RawFileRecord:
    """登记一份已存在的官方原始文件并固化 SHA256。"""

    if Path(filename).name != filename:
        raise ShenwanRawDataError("filename 必须是 raw 目录中的文件名，不得包含路径")
    root = Path(raw_dir)
    path = root / filename
    if not path.is_file():
        raise ShenwanRawDataError(f"待登记原始文件不存在: {path}")
    record = RawFileRecord(
        provider=PROVIDER,
        source_url=source_url,
        retrieved_at=retrieved_at,
        original_filename=filename,
        sha256=sha256_file(path),
        classification_version=classification_version,
        notes=notes,
    )
    _record_from_mapping(asdict(record), index=0)

    manifest_path = root / MANIFEST_FILENAME
    records = list(load_manifest(root)) if manifest_path.exists() else []
    if any(existing.original_filename == filename for existing in records):
        raise ShenwanRawDataError(f"manifest 已登记 {filename!r}；为保留可追溯性，不自动覆盖")
    records.append(record)
    write_manifest(records, root)
    return record


def verify_manifest(
    raw_dir: str | Path = DEFAULT_RAW_DIR,
    *,
    require_all_discovered: bool = True,
) -> tuple[RawFileRecord, ...]:
    """验证文件存在、哈希一致，且默认拒绝未登记文件。"""

    root = Path(raw_dir)
    records = load_manifest(root)
    registered = {record.original_filename for record in records}
    if require_all_discovered:
        discovered = {path.name for path in discover_raw_files(root)}
        unregistered = discovered.difference(registered)
        if unregistered:
            raise ShenwanRawDataError(f"raw 目录存在未登记文件: {sorted(unregistered)}")
    for record in records:
        path = root / record.original_filename
        if not path.is_file():
            raise ShenwanRawDataError(f"manifest 文件缺失: {path}")
        actual = sha256_file(path)
        if actual != record.sha256:
            raise ShenwanRawDataError(
                f"SHA256 不一致: {record.original_filename}: "
                f"manifest={record.sha256}, actual={actual}"
            )
    return records


def _parse_date_column(series: pd.Series, *, name: str) -> pd.Series:
    text = series.astype("string").str.strip()
    present = text.notna() & text.ne("")
    parsed = pd.to_datetime(series, errors="coerce")
    invalid = present & parsed.isna()
    if invalid.any():
        examples = series.loc[invalid].head(3).tolist()
        raise ShenwanRawDataError(f"{name} 含无法解析的日期: {examples!r}")
    return parsed


def _clean_code_column(series: pd.Series, *, name: str, pad: int | None) -> pd.Series:
    cleaned = series.astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    if cleaned.isna().any() or cleaned.eq("").any():
        raise ShenwanRawDataError(f"{name} 含空值")
    if not cleaned.str.fullmatch(r"\d+").all():
        examples = cleaned.loc[~cleaned.str.fullmatch(r"\d+")].head(3).tolist()
        raise ShenwanRawDataError(f"{name} 含非数字代码: {examples!r}")
    if pad is not None:
        cleaned = cleaned.str.zfill(pad)
    return cleaned


def parse_stock_classification(
    raw_dir: str | Path = DEFAULT_RAW_DIR,
    *,
    filename: str = STOCK_CLASSIFICATION_FILENAME,
) -> pd.DataFrame:
    """把官方分类原文件解析为保守的 canonical membership 表。

    ``更新日期`` 只保留为 ``source_updated_at``，绝不把它冒充为数据对外
    可得时间。``effective_to`` 和 ``available_at`` 没有官方证据时始终为空。
    """

    root = Path(raw_dir)
    records = {record.original_filename: record for record in load_manifest(root)}
    if filename not in records:
        raise ShenwanRawDataError(f"manifest 未登记分类文件: {filename}")
    record = records[filename]
    path = root / filename
    if not path.is_file():
        raise ShenwanRawDataError(f"分类文件不存在: {path}")
    actual_hash = sha256_file(path)
    if actual_hash != record.sha256:
        raise ShenwanRawDataError(
            f"SHA256 不一致: {filename}: manifest={record.sha256}, actual={actual_hash}"
        )
    try:
        raw = pd.read_excel(
            path,
            dtype={"股票代码": "string", "行业代码": "string"},
        )
    except Exception as exc:
        raise ShenwanRawDataError(f"无法读取官方 Excel 文件 {filename}: {exc}") from exc
    if raw.empty:
        raise ShenwanRawDataError(f"官方分类文件为空: {filename}")
    missing = _CLASSIFICATION_REQUIRED_COLUMNS.difference(raw.columns)
    if missing:
        raise ShenwanRawDataError(f"官方分类文件缺少字段: {sorted(missing)}")

    canonical = pd.DataFrame(index=raw.index)
    canonical["symbol"] = _clean_code_column(raw["股票代码"], name="股票代码", pad=6)
    canonical["sector_code"] = _clean_code_column(raw["行业代码"], name="行业代码", pad=None)
    if "行业名称" in raw.columns:
        canonical["sector_name"] = raw["行业名称"].astype("string").str.strip()
    else:
        canonical["sector_name"] = pd.Series(pd.NA, index=raw.index, dtype="string")
    canonical["effective_from"] = _parse_date_column(raw["计入日期"], name="计入日期")
    canonical["effective_to"] = pd.NaT
    canonical["available_at"] = pd.NaT
    canonical["source_updated_at"] = _parse_date_column(raw["更新日期"], name="更新日期")
    canonical["classification_version"] = (
        record.classification_version if record.classification_version is not None else pd.NA
    )
    canonical["source_provider"] = record.provider
    canonical["source_url"] = record.source_url
    canonical["source_retrieved_at"] = (
        pd.Timestamp(record.retrieved_at) if record.retrieved_at is not None else pd.NaT
    )
    canonical["source_filename"] = record.original_filename
    canonical["source_sha256"] = record.sha256
    return canonical.loc[:, list(CANONICAL_CLASSIFICATION_COLUMNS)].reset_index(drop=True)


def level_b_admission_issues(frame: pd.DataFrame) -> tuple[str, ...]:
    """返回阻止正式 LEVEL B 的可审计 PIT 字段问题。"""

    required = set(CANONICAL_CLASSIFICATION_COLUMNS)
    missing = required.difference(frame.columns)
    if missing:
        return (f"canonical columns missing: {sorted(missing)}",)
    if frame.empty:
        return ("classification data is empty",)

    issues: list[str] = []
    for column in (
        "classification_version",
        "effective_from",
        "effective_to",
        "available_at",
        "source_retrieved_at",
    ):
        if frame[column].isna().any():
            issues.append(f"{column} contains UNKNOWN/null")
    return tuple(issues)


def assert_level_b_admissible(frame: pd.DataFrame) -> None:
    """缺少任一 PIT 证据时显式阻止正式 LEVEL B。"""

    issues = level_b_admission_issues(frame)
    if issues:
        raise ShenwanAdmissionError("LEVEL B admission blocked: " + "; ".join(issues))
