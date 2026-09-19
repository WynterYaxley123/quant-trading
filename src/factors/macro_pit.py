"""宏观因子的 Point-In-Time（时点）对齐算法。

迁移来源与修复
--------------
Legacy china-market-data v5 ``scripts/quant/macro_features.py``。

**Legacy 缺陷**：该文件中 ``_parse_month()`` 函数定义缺失，但被调用 6 次。
由于每次调用都包在独立 ``try/except`` 中，``NameError`` 被静默吞掉，
导致 PMI / M1 / M2 / 社融 / CPI / PPI 全部静默失效——只有不依赖该函数的
LPR 与中美利差能成功。本模块**重新实现** ``_parse_month()`` 并加测试。

本模块只迁移**时点对齐算法**，不迁移任何网络下载代码。
默认 ``macro_enabled = False``；本次不下载宏观数据。

发布时间规则（保守，宁可晚不可早）
----------------------------------
============  ==========================
数据          可获取时间
============  ==========================
PMI           当月最后一天
M1 / M2 / 社融  次月 12 日
CPI / PPI     次月 10 日
LPR           当月 20 日
中美 10Y 收益率 不得提前使用未来日期
============  ==========================
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

__all__ = [
    "DEFAULT_MACRO_ENABLED",
    "PUBLISH_RULES",
    "parse_month",
    "publication_date",
    "macro_available_at",
    "build_macro_feature_columns",
    "add_macro_features",
]

#: 宏观因子默认**关闭**。启用前必须接入真实 PIT 宏观数据源。
DEFAULT_MACRO_ENABLED = False

#: 列名 -> 发布规则标识。
PUBLISH_RULES = {
    "pmi_mfg": "pmi",
    "pmi_non_mfg": "pmi",
    "m1_yoy": "next_month_12",
    "m2_yoy": "next_month_12",
    "social_finance": "next_month_12",
    "cpi_yoy": "next_month_10",
    "ppi_yoy": "next_month_10",
    "lpr_1y": "lpr_current_month",
    "lpr_5y": "lpr_current_month",
    # cn_10y / us_10y 为日频，按月末取样，规则见 _daily_month_end_rule
}

#: 规则 -> (月偏移, 日偏移) 形式的落点。
_RULE_OFFSETS = {
    "next_month_12": (1, 11),  # 下月 1 日 + 11 天 = 下月 12 日
    "next_month_10": (1, 9),   # 下月 1 日 + 9 天 = 下月 10 日
}


def parse_month(value) -> pd.Timestamp:
    """把任意月标识解析为该月 1 日的 ``Timestamp``。

    这是 legacy 中**缺失**的函数，本实现重新编写并测试。

    支持输入
    --------
    - ``pd.Timestamp`` / ``datetime`` / ``date``：取其年月的 1 日
    - ``"2026-05"`` / ``"2026/5"`` / ``"202605"``：解析年月
    - ``"2026-05-17"``：取该日所属月

    解析失败抛 ``ValueError``（不静默失败 —— legacy 静默失败的教训）。
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValueError("parse_month 收到空值")

    if isinstance(value, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(year=value.year, month=value.month, day=1)

    s = str(value).strip()
    if not s:
        raise ValueError("parse_month 收到空字符串")

    # 纯数字 6/8 位
    if s.isdigit():
        if len(s) == 6:
            return pd.Timestamp(year=int(s[:4]), month=int(s[4:6]), day=1)
        if len(s) == 8:
            return pd.Timestamp(year=int(s[:4]), month=int(s[4:6]), day=1)
        raise ValueError(f"无法解析月份: {value!r}")

    ts = pd.to_datetime(s, errors="coerce")
    if pd.isna(ts):
        raise ValueError(f"无法解析月份: {value!r}")
    return pd.Timestamp(year=ts.year, month=ts.month, day=1)


def _month_end(month_ts: pd.Timestamp) -> pd.Timestamp:
    """当月最后一天。"""
    return month_ts + pd.DateOffset(months=1) - pd.DateOffset(days=1)


def publication_date(column: str, month_ts) -> pd.Timestamp:
    """返回 ``column`` 对应月份数据的**可获取日期**。

    未知列按日频处理（不早于月末），保证不会提前使用。
    """
    m = parse_month(month_ts)
    rule = PUBLISH_RULES.get(column)
    if rule is None:
        return _month_end(m)
    if rule == "pmi":
        return _month_end(m)
    if rule == "lpr_current_month":
        return pd.Timestamp(year=m.year, month=m.month, day=20)
    off = _RULE_OFFSETS.get(rule)
    if off is None:
        return _month_end(m)
    months, days = off
    return pd.Timestamp(year=m.year, month=m.month, day=1) + pd.DateOffset(
        months=months, days=days
    )


def _as_of_ts(as_of_date) -> pd.Timestamp:
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.date()
    return pd.Timestamp(as_of_date).normalize()


def macro_available_at(as_of_date, macro_raw: pd.DataFrame) -> dict:
    """返回 ``as_of_date`` 当天**真实可知**的宏观数据快照。

    参数
    ----
    as_of_date:
        观察日。
    macro_raw:
        index 为月份（首日）、列为宏观指标名的 DataFrame。

    返回
    ----
    ``dict``，键加 ``macro_`` 前缀。若某指标在 ``as_of`` 时尚不可获取，
    则该键不出现在结果中（而不是填 NaN 或未来值）。
    """
    as_of = _as_of_ts(as_of_date)
    result: dict[str, float] = {}

    if macro_raw is None or macro_raw.empty:
        return result

    for col in macro_raw.columns:
        series = macro_raw[col].dropna().sort_index()
        if series.empty:
            continue
        best = None
        for month_val in reversed(series.index):
            if publication_date(col, month_val) <= as_of:
                best = series[month_val]
                break
        if best is not None and not pd.isna(best):
            result[f"macro_{col}"] = float(best)

    # 衍生特征只在其成分都存在时生成
    if "macro_pmi_mfg" in result and "macro_pmi_non_mfg" in result:
        result["macro_pmi_diff"] = result["macro_pmi_mfg"] - result["macro_pmi_non_mfg"]
    if "macro_m1_yoy" in result and "macro_m2_yoy" in result:
        result["macro_m1_m2_spread"] = result["macro_m1_yoy"] - result["macro_m2_yoy"]
    if "macro_cn_10y" in result and "macro_us_10y" in result:
        result["macro_cn_us_spread"] = result["macro_cn_10y"] - result["macro_us_10y"]
    return result


def build_macro_feature_columns(example_snapshot: dict) -> list[str]:
    """从一份快照中提取特征列名（排序后）。"""
    return sorted(example_snapshot.keys())


def add_macro_features(
    features_df: pd.DataFrame, macro_raw: pd.DataFrame
) -> pd.DataFrame:
    """把时点对齐的宏观特征并入行业特征 DataFrame。

    对 ``features_df`` 的每个唯一日期求一次快照，然后 reindex + ffill。
    绝不使用未来快照填充过去行。
    """
    if macro_raw is None or macro_raw.empty or features_df.empty:
        return features_df.copy()

    dates = pd.Index(
        [ix.date() if hasattr(ix, "date") else ix for ix in features_df.index]
    )
    snapshots = {d: macro_available_at(d, macro_raw) for d in sorted(set(dates))}
    macro_df = pd.DataFrame.from_dict(snapshots, orient="index")
    macro_df.index = pd.to_datetime(macro_df.index)
    macro_df = macro_df.reindex(pd.to_datetime(dates)).ffill().fillna(0.0)
    macro_df.index = features_df.index

    result = features_df.copy()
    for col in macro_df.columns:
        result[col] = macro_df[col].values
    return result
