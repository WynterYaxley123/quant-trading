"""申万官方二级行业目录与指数日线的可核验本地转换。

只读取 raw。原始响应里的异常行情保留并标记，不修价、不补日。
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

from ..calendar import TradingCalendar
from .shenwan_official import (
    DEFAULT_RAW_DIR,
    PROVIDER,
    ShenwanRawDataError,
    parse_stock_classification,
    sha256_file,
)

PARSER_VERSION = "shenwan-sector-parser-v1"
SCHEMA_VERSION = "shenwan-sector-schema-v1"
TRANSFORM_VERSION = "shenwan-sector-transform-v1"
CATALOG_COLUMNS = (
    "sector_code",
    "sector_name",
    "sector_level",
    "classification_version",
    "effective_from",
    "effective_to",
    "available_at",
    "source_provider",
    "source_url",
    "source_retrieved_at",
    "source_filename",
    "source_sha256",
)
OHLCVA_COLUMNS = (
    "date",
    "sector_code",
    "sector_name",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "source_provider",
    "source_url",
    "source_retrieved_at",
    "source_filename",
    "source_sha256",
    "source_snapshot",
    "source_row",
    "is_valid_ohlc",
    "quality_violations",
)
CLASSIFICATION_COLUMNS = (
    "symbol",
    "sector_code",
    "sector_name",
    "sector_level",
    "effective_from",
    "effective_to_official",
    "effective_to_derived",
    "available_at",
    "source_updated_at",
    "classification_version",
    "source_provider",
    "source_url",
    "source_retrieved_at",
    "source_filename",
    "source_sha256",
)


def _json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ShenwanRawDataError(f"JSON 无法读取: {path}: {exc}") from exc
    if not isinstance(payload, dict) or str(payload.get("code")) != "200":
        raise ShenwanRawDataError(f"官方响应状态异常: {path}")
    return payload


def _official_url(url: str, *, endpoint: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.swsresearch.com"
        or endpoint not in parsed.path
    ):
        raise ShenwanRawDataError(f"非申万官方 HTTPS 来源: {url}")


def load_raw_catalog(
    raw_dir: Path | str = DEFAULT_RAW_DIR,
    *,
    retrieved_at: str | None,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """依据官方响应的 indextype 翻页链确认二级行业集合。"""

    root = Path(raw_dir) / "sector_catalog"
    pages = sorted(
        root.glob("sws_index_catalog_L2_page*.json"), key=lambda p: int(p.stem.split("page")[-1])
    )
    if not pages or [int(p.stem.split("page")[-1]) for p in pages] != list(
        range(1, len(pages) + 1)
    ):
        raise ShenwanRawDataError("二级目录分页缺失或不连续")
    records: list[dict] = []
    fingerprints: dict[str, str] = {}
    expected_count = None
    for page_no, path in enumerate(pages, 1):
        data = _json(path).get("data")
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise ShenwanRawDataError(f"二级目录响应结构异常: {path}")
        expected_count = data.get("count") if expected_count is None else expected_count
        if data.get("count") != expected_count:
            raise ShenwanRawDataError("二级目录分页总数不一致")
        # 原始页 1/2 的 next、页 2/3 的 previous 留下官方请求参数证据。
        link = data.get("next") or data.get("previous")
        parsed_link = urlparse(link or "")
        if (
            parsed_link.hostname != "www.swsresearch.com"
            or not parsed_link.path.endswith("/index_publish/current/")
            or parse_qs(parsed_link.query).get("indextype") != ["二级行业"]
        ):
            raise ShenwanRawDataError(f"缺少官方二级行业 indextype 翻页证据: {path}")
        if page_no < len(pages) and data.get("next") is None:
            raise ShenwanRawDataError(f"目录提前终止: {path}")
        fingerprint = sha256_file(path)
        fingerprints[f"sector_catalog/{path.name}"] = fingerprint
        source_url = (
            "https://www.swsresearch.com/institute-sw/api/index_publish/current/"
            f"?page={page_no}&page_size=50&indextype=二级行业"
        )
        for item in data["results"]:
            code = str(item.get("swindexcode", ""))
            name = item.get("swindexname")
            if not (code.isdigit() and len(code) == 6 and isinstance(name, str) and name.strip()):
                raise ShenwanRawDataError(f"二级目录代码/名称缺失: {path}: {item}")
            records.append(
                {
                    "sector_code": code,
                    "sector_name": name.strip(),
                    "sector_level": 2,
                    "classification_version": None,
                    "effective_from": pd.NaT,
                    "effective_to": pd.NaT,
                    "available_at": pd.NaT,
                    "source_provider": PROVIDER,
                    "source_url": source_url,
                    "source_retrieved_at": retrieved_at,
                    "source_filename": f"sector_catalog/{path.name}",
                    "source_sha256": fingerprint,
                }
            )
    if len(records) != expected_count:
        raise ShenwanRawDataError(f"目录行数 {len(records)} != 官方 count {expected_count}")
    frame = (
        pd.DataFrame(records, columns=CATALOG_COLUMNS)
        .sort_values("sector_code")
        .reset_index(drop=True)
    )
    if frame["sector_code"].duplicated().any():
        raise ShenwanRawDataError("二级目录 sector_code 重复")
    # JSONL 是既有整理副本，必须与官方分页一致才参与快照。
    jsonl = root / "sws_index_catalog_L2.jsonl"
    try:
        mirror = [
            json.loads(line)
            for line in jsonl.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ShenwanRawDataError(f"目录 JSONL 不可读取: {exc}") from exc
    if [(str(x["swindexcode"]), x["swindexname"]) for x in mirror] != [
        (str(x["swindexcode"]), x["swindexname"])
        for page in pages
        for x in _json(page)["data"]["results"]
    ]:
        raise ShenwanRawDataError("目录 JSONL 与官方分页内容不一致")
    fingerprints["sector_catalog/sws_index_catalog_L2.jsonl"] = sha256_file(jsonl)
    return frame, fingerprints


def load_history_manifest(
    raw_dir: Path | str, manifest_path: Path | str
) -> tuple[dict, dict[str, dict]]:
    try:
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ShenwanRawDataError(f"行情 manifest 无法读取: {exc}") from exc
    if (
        payload.get("schema_version") != 1
        or payload.get("provider") != PROVIDER
        or payload.get("period") != "DAY"
    ):
        raise ShenwanRawDataError("行情 manifest 版本/来源/周期不匹配")
    try:
        retrieved = pd.Timestamp(payload["retrieved_at"])
        if retrieved.tzinfo is None:
            raise ValueError("timezone missing")
    except (KeyError, TypeError, ValueError) as exc:
        raise ShenwanRawDataError("行情 manifest retrieved_at 缺失或无时区") from exc
    files = payload.get("files")
    if not isinstance(files, list) or len(files) != payload.get("sector_count"):
        raise ShenwanRawDataError("行情 manifest 文件数不一致")
    by_code = {}
    root = Path(raw_dir).resolve()
    for item in files:
        code = str(item.get("sector_code", ""))
        if code in by_code or not (code.isdigit() and len(code) == 6):
            raise ShenwanRawDataError(f"行情 manifest 重复/非法代码: {code}")
        path = root / "sector_history" / f"{code}.json"
        if (
            item.get("raw_path") != f"data/raw/shenwan/sector_history/{code}.json"
            or not path.is_file()
        ):
            raise ShenwanRawDataError(f"行情 raw_path 不匹配或文件缺失: {code}")
        _official_url(item.get("source_url", ""), endpoint="/index_publish/trend/")
        if parse_qs(urlparse(item["source_url"]).query).get("swindexcode") != [code]:
            raise ShenwanRawDataError(f"行情 URL 代码不匹配: {code}")
        if item.get("retrieved_at") != payload["retrieved_at"]:
            raise ShenwanRawDataError(f"行情 retrieved_at 与 manifest 不一致: {code}")
        if sha256_file(path) != item.get("sha256"):
            raise ShenwanRawDataError(f"行情 SHA256 不匹配: {code}")
        by_code[code] = item
    actual = {p.stem for p in (root / "sector_history").glob("*.json")}
    if actual != set(by_code):
        raise ShenwanRawDataError("行情文件集合与 manifest 不一致")
    return payload, by_code


def _violations(row: dict) -> str:
    bad = []
    try:
        prices = [float(row[k]) for k in ("open", "high", "low", "close")]
        if not all(math.isfinite(v) and v > 0 for v in prices):
            bad.append("non_positive_or_nonfinite_price")
        o, h, l, c = prices  # noqa: E741 -- Established OHLC low-price name in frozen numerical helper.
        if h < max(o, c, l):
            bad.append("high_below_open_close_or_low")
        if l > min(o, c, h):
            bad.append("low_above_open_close_or_high")
    except (TypeError, ValueError, KeyError):
        bad.append("invalid_price_type")
    for col in ("volume", "amount"):
        value = row.get(col)
        if value is not None:
            try:
                if not math.isfinite(float(value)) or float(value) < 0:
                    bad.append(f"invalid_{col}")
            except (TypeError, ValueError):
                bad.append(f"invalid_{col}")
    return ";".join(bad)


def parse_sector_ohlcva(
    raw_dir: Path | str, catalog: pd.DataFrame, by_code: dict[str, dict]
) -> pd.DataFrame:
    """按官方清单解析每份 JSON；异常保留并标记 source row。"""

    names = dict(zip(catalog["sector_code"], catalog["sector_name"]))
    if set(names) != set(by_code):
        raise ShenwanRawDataError("二级目录与历史行情代码集合不一致")
    rows = []
    for code in sorted(by_code):
        item = by_code[code]
        path = Path(raw_dir) / "sector_history" / f"{code}.json"
        data = _json(path).get("data")
        if not isinstance(data, list) or not data or len(data) != item.get("row_count"):
            raise ShenwanRawDataError(f"行情行数不匹配: {code}")
        for position, source in enumerate(data):
            if str(source.get("swindexcode")) != code:
                raise ShenwanRawDataError(f"bar 代码与文件不一致: {code}:{position}")
            raw_date = source.get("bargaindate")
            date = pd.to_datetime(raw_date, format="%Y-%m-%d", errors="coerce")
            if pd.isna(date) or date.date() > pd.Timestamp(item["retrieved_at"]).date():
                raise ShenwanRawDataError(f"无效/未来交易日期: {code}:{position}:{raw_date}")
            row = {
                "date": date,
                "sector_code": code,
                "sector_name": names[code],
                "open": source.get("openindex"),
                "high": source.get("maxindex"),
                "low": source.get("minindex"),
                "close": source.get("closeindex"),
                "volume": source.get("bargainamount"),
                "amount": source.get("bargainsum"),
                "source_provider": PROVIDER,
                "source_url": item["source_url"],
                "source_retrieved_at": item.get("retrieved_at"),
                "source_filename": f"sector_history/{code}.json",
                "source_sha256": item["sha256"],
                "source_snapshot": item["sha256"],
                "source_row": position,
            }
            row["quality_violations"] = _violations(row)
            row["is_valid_ohlc"] = not bool(row["quality_violations"])
            rows.append(row)
        dates = [row["date"] for row in rows[-len(data) :]]
        if dates != sorted(dates) or len(dates) != len(set(dates)):
            raise ShenwanRawDataError(f"行情日期倒序/重复: {code}")
        if str(dates[0].date()) != item.get("start_date") or str(dates[-1].date()) != item.get(
            "end_date"
        ):
            raise ShenwanRawDataError(f"行情日期范围与 manifest 不符: {code}")
    frame = pd.DataFrame(rows, columns=OHLCVA_COLUMNS)
    return frame.sort_values(["sector_code", "date"], kind="stable").reset_index(drop=True)


def parse_classification_with_intervals(raw_dir: Path | str) -> pd.DataFrame:
    """仅派生下一次计入日期；官方结束日期和发布时间始终保留空值。"""

    source = parse_stock_classification(raw_dir)
    frame = source.rename(columns={"effective_to": "effective_to_official"}).copy()
    frame["sector_level"] = pd.NA  # 分类代码不是指数目录代码，不能直接映射二级。
    frame["effective_to_derived"] = pd.NaT
    if frame["effective_from"].isna().any():
        raise ShenwanRawDataError("分类计入日期缺失")
    dates = (
        frame[["symbol", "effective_from"]]
        .drop_duplicates()
        .sort_values(["symbol", "effective_from"])
    )
    dates["next"] = dates.groupby("symbol")["effective_from"].shift(-1)
    lookup = dates.set_index(["symbol", "effective_from"])["next"]
    frame["effective_to_derived"] = [
        lookup.get((symbol, when), pd.NaT)
        for symbol, when in zip(frame["symbol"], frame["effective_from"])
    ]
    return (
        frame.loc[:, CLASSIFICATION_COLUMNS]
        .sort_values(["symbol", "effective_from", "sector_code"], kind="stable")
        .reset_index(drop=True)
    )


def snapshot_id(
    raw_fingerprints: dict[str, str],
    *,
    code_fingerprints: dict[str, str] | None = None,
) -> str:
    """稳定指纹：所有相关 raw SHA256 与显式转换版本。"""

    payload = {
        "parser": PARSER_VERSION,
        "schema": SCHEMA_VERSION,
        "transform": TRANSFORM_VERSION,
        "raw_sha256": dict(sorted(raw_fingerprints.items())),
        "code_sha256": dict(sorted((code_fingerprints or {}).items())),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def audit_coverage(frame: pd.DataFrame, catalog: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """以全部行业观测日期的并集作为统一 session 日历，不填补数据。"""

    calendar = TradingCalendar.from_dates(frame["date"].tolist())
    groups = {code: part for code, part in frame.groupby("sector_code", sort=True)}
    starts = {code: part["date"].min().date() for code, part in groups.items()}
    ends = {code: part["date"].max().date() for code, part in groups.items()}
    common_start = max(starts.values())
    common_end = min(ends.values())
    per = []
    for code in sorted(groups):
        part = groups[code]
        actual = {value.date() for value in part["date"]}
        expected = calendar.between(starts[code], ends[code])
        common = calendar.between(common_start, common_end)
        missing = len(set(expected) - actual)
        per.append(
            {
                "sector_code": code,
                "sector_name": part["sector_name"].iloc[0],
                "row_count": len(part),
                "start_date": str(starts[code]),
                "end_date": str(ends[code]),
                "missing_sessions": missing,
                "coverage_ratio": len(actual) / len(expected),
                "missing_common_sessions": len(set(common) - actual),
                "invalid_ohlc_count": int((~part["is_valid_ohlc"]).sum()),
            }
        )
    summary = {
        "sector_count": len(groups),
        "total_rows": len(frame),
        "earliest_date": str(frame["date"].min().date()),
        "latest_date": str(frame["date"].max().date()),
        "common_start_date": str(common_start),
        "common_end_date": str(common_end),
        "duplicate_count": int(frame.duplicated(["sector_code", "date"]).sum()),
        "invalid_ohlc_count": int((~frame["is_valid_ohlc"]).sum()),
        "missing_sessions_total": sum(row["missing_sessions"] for row in per),
        "missing_common_sessions_total": sum(row["missing_common_sessions"] for row in per),
        "calendar_source": "union_of_official_sector_observed_sessions",
        "calendar_session_count": len(calendar),
    }
    return summary, pd.DataFrame(per)


def candidate_research_range(frame: pd.DataFrame, summary: dict) -> tuple[str | None, str | None]:
    """以共同且全行业有效的连续 session 计算保守候选区间。"""

    common_start = pd.Timestamp(summary["common_start_date"])
    common_end = pd.Timestamp(summary["common_end_date"])
    relevant = frame.loc[frame["date"].between(common_start, common_end)]
    codes = frame["sector_code"].nunique()
    counts = relevant.groupby("date").agg(
        rows=("sector_code", "nunique"), valid=("is_valid_ohlc", "sum")
    )
    full = counts.loc[(counts["rows"] == codes) & (counts["valid"] == codes)].index.sort_values()
    # 不跨缺口计数：要求候选窗口内每个官方观测 session 都齐全有效。
    calendar = TradingCalendar.from_dates(relevant["date"].tolist())
    sessions = list(calendar.days)
    if not sessions:
        return None, None
    full_set = {d.date() for d in full}
    first = None
    for i, current in enumerate(sessions):
        if i < 240 or current not in full_set:
            continue
        cutoff = i - 120  # 120-session label/purge 边界
        training_start = pd.Timestamp(sessions[cutoff]) - pd.DateOffset(months=6)
        start_index = next(
            (j for j, d in enumerate(sessions) if pd.Timestamp(d) >= training_start), None
        )
        if start_index is None or start_index < 120:
            continue
        if all(d in full_set for d in sessions[start_index - 120 : i + 1]):
            first = i
            break
    if first is None:
        return None, None
    last = len(sessions) - 121  # 评价时为 120-session forward label 留出终点
    if last < first or not all(d in full_set for d in sessions[first : last + 121]):
        return None, None
    return str(sessions[first]), str(sessions[last])
