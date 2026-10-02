"""读取已核验的申万 canonical 文件，缺日和异常必须显式可见。"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from ..providers.shenwan_official import ShenwanRawDataError, sha256_file
from ..providers.shenwan_sector import CATALOG_COLUMNS, OHLCVA_COLUMNS

DEFAULT_PROCESSED_DIR = Path("data/processed/shenwan")


def _metadata(root: Path) -> dict:
    path = root / "sector_admission.json"
    if not path.is_file():
        raise ShenwanRawDataError(f"未生成申万 admission metadata: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _verified_csv(root: Path, name: str, metadata: dict) -> Path:
    path = root / name
    expected = metadata.get("canonical_hashes", {}).get(name)
    if not expected or not path.is_file() or sha256_file(path) != expected:
        raise ShenwanRawDataError(f"canonical SHA256 不匹配: {name}")
    return path


def load_sector_catalog(processed_dir: Path | str = DEFAULT_PROCESSED_DIR) -> pd.DataFrame:
    root = Path(processed_dir)
    metadata = _metadata(root)
    frame = pd.read_csv(
        _verified_csv(root, "sector_catalog.csv", metadata), dtype={"sector_code": "string"}
    )
    if not set(CATALOG_COLUMNS).issubset(frame.columns) or frame["sector_code"].duplicated().any():
        raise ShenwanRawDataError("canonical sector catalog schema/代码重复")
    if frame["sector_name"].isna().any() or not frame["sector_level"].eq(2).all():
        raise ShenwanRawDataError("canonical sector catalog 名称/级别无效")
    return frame.sort_values("sector_code").reset_index(drop=True)


def _market(root: Path) -> pd.DataFrame:
    meta = _metadata(root)
    frame = pd.read_csv(
        _verified_csv(root, "sector_ohlcva.csv", meta),
        dtype={"sector_code": "string"},
        parse_dates=["date"],
        low_memory=False,
    )
    if not set(OHLCVA_COLUMNS).issubset(frame.columns):
        raise ShenwanRawDataError("canonical sector OHLCVA schema 不完整")
    if frame.duplicated(["sector_code", "date"]).any():
        raise ShenwanRawDataError("canonical sector OHLCVA 日期重复")
    if (
        not frame.sort_values(["sector_code", "date"])[["sector_code", "date"]]
        .reset_index(drop=True)
        .equals(frame[["sector_code", "date"]].reset_index(drop=True))
    ):
        raise ShenwanRawDataError("canonical sector OHLCVA 顺序错误")
    if not frame["source_snapshot"].eq(frame["source_sha256"]).all():
        raise ShenwanRawDataError("canonical sector OHLCVA source snapshot 不一致")
    if (
        frame[["sector_name", "source_provider", "source_url", "source_filename", "source_sha256"]]
        .isna()
        .any()
        .any()
    ):
        raise ShenwanRawDataError("canonical sector OHLCVA 来源字段缺失")
    prices = frame[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    finite = pd.DataFrame(
        np.isfinite(prices.to_numpy()), columns=prices.columns, index=prices.index
    ).all(axis=1)
    valid = finite & prices.gt(0).all(axis=1)
    valid &= prices["high"].ge(prices[["open", "low", "close"]].max(axis=1))
    valid &= prices["low"].le(prices[["open", "high", "close"]].min(axis=1))
    for col in ("volume", "amount"):
        values = pd.to_numeric(frame[col], errors="coerce")
        valid &= frame[col].isna() | (np.isfinite(values) & values.ge(0))
    if not valid.eq(frame["is_valid_ohlc"]).all():
        raise ShenwanRawDataError("canonical OHLC 质量标记与实际数值不一致")
    if meta.get("data_snapshot_id") is None:
        raise ShenwanRawDataError("缺少 data_snapshot_id")
    return frame


def load_sector_ohlcva(
    sector_code: str,
    start: object | None = None,
    end: object | None = None,
    *,
    processed_dir: Path | str = DEFAULT_PROCESSED_DIR,
    allow_invalid_for_audit: bool = False,
) -> pd.DataFrame:
    """返回单行业真实 bar；异常默认抛错，审计时可显式读取原值。"""

    frame = _market(Path(processed_dir))
    out = frame.loc[frame["sector_code"] == str(sector_code)]
    if start is not None:
        out = out.loc[out["date"] >= pd.Timestamp(start)]
    if end is not None:
        out = out.loc[out["date"] <= pd.Timestamp(end)]
    if out.empty:
        raise ShenwanRawDataError(f"无申万行业行情: {sector_code} / {start}..{end}")
    if not allow_invalid_for_audit and not out["is_valid_ohlc"].all():
        examples = (
            out.loc[~out["is_valid_ohlc"], ["date", "quality_violations"]]
            .head(3)
            .to_dict("records")
        )
        raise ShenwanRawDataError(f"行业 {sector_code} 含源头异常 OHLC，禁止进入模型: {examples}")
    return out.reset_index(drop=True)


def load_sector_panel(
    sector_codes: Sequence[str],
    start: object,
    end: object,
    *,
    processed_dir: Path | str = DEFAULT_PROCESSED_DIR,
    allow_invalid_for_audit: bool = False,
) -> pd.DataFrame:
    """长表 panel（date, sector_code），不填补缺失 bar。"""

    if not sector_codes or len(sector_codes) != len(set(sector_codes)):
        raise ValueError("sector_codes 必须非空且唯一")
    if pd.Timestamp(end) < pd.Timestamp(start):
        raise ValueError("end 早于 start")
    market = _market(Path(processed_dir))
    requested = {str(code) for code in sector_codes}
    available = set(market["sector_code"])
    if missing := requested - available:
        raise ShenwanRawDataError(f"请求的行业不存在: {sorted(missing)}")
    out = (
        market.loc[
            market["sector_code"].isin(requested)
            & market["date"].between(pd.Timestamp(start), pd.Timestamp(end))
        ]
        .sort_values(["date", "sector_code"])
        .reset_index(drop=True)
    )
    if not allow_invalid_for_audit and not out["is_valid_ohlc"].all():
        raise ShenwanRawDataError("panel 含源头异常 OHLC，禁止进入模型")
    # 没有 group reindex 或 ffill；缺日表现为该 (date, sector_code) 行不存在。
    return out
