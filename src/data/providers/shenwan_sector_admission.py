"""申万数据准入判定；使用显式证据，不根据目标等级反推字段。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class AdmissionDecision:
    level: str
    strict_pit: bool
    reasons: tuple[str, ...]


def evaluate_admission(
    catalog: pd.DataFrame,
    market: pd.DataFrame,
    classification: pd.DataFrame,
    *,
    provenance_verified: bool,
    candidate_start: str | None,
    candidate_end: str | None,
    classification_version_proven: bool = False,
    publication_timing_proven: bool = False,
    no_future_classification_leakage_proven: bool = False,
) -> AdmissionDecision:
    reasons = []
    if not provenance_verified:
        reasons.append("raw manifest/SHA256 provenance 未验证")
    if classification.empty:
        reasons.append("分类历史为空")
    if (
        catalog.empty
        or catalog["sector_code"].duplicated().any()
        or catalog["sector_name"].isna().any()
        or not catalog["sector_level"].eq(2).all()
    ):
        reasons.append("官方二级行业 universe 无效")
    if market.empty or set(market["sector_code"]) != set(catalog["sector_code"]):
        reasons.append("二级行业历史行情不完整")
    if market.duplicated(["sector_code", "date"]).any():
        reasons.append("行情存在重复行业日期")
    if candidate_start is None or candidate_end is None:
        reasons.append("无完整有效的候选研究 session 区间")
    elif not market.loc[
        market["date"].between(candidate_start, candidate_end), "is_valid_ohlc"
    ].all():
        reasons.append("候选研究区间含源头 OHLC 异常")
    if reasons:
        return AdmissionDecision("DATA_NOT_ADMISSIBLE", False, tuple(reasons))

    pit_missing = []
    for col in (
        "classification_version",
        "effective_from",
        "effective_to_official",
        "available_at",
    ):
        if col not in classification or classification[col].isna().any():
            pit_missing.append(f"{col} 缺少官方时点证据")
    if not classification_version_proven:
        pit_missing.append("classification version 官方证据未证明")
    if not publication_timing_proven:
        pit_missing.append("publication timing 未证明")
    if not no_future_classification_leakage_proven:
        pit_missing.append("无未来分类泄漏未证明")
    if pit_missing:
        return AdmissionDecision(
            "FIXED_CLASSIFICATION_RESEARCH",
            False,
            tuple(pit_missing) + ("NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST",),
        )
    return AdmissionDecision("STRICT_PIT", True, ())
