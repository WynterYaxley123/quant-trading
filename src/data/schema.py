"""Canonical market data schema —— 项目级统一行情表结构。

所有 provider / loader 的输出必须归一化到本模块定义的列集合，
策略与回测只依赖这一套，避免每个策略各搞一套列名。

设计要求（来自任务书第五节）：不过度设计，只统一真正必要的字段。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

import pandas as pd

# --- 列定义 ---------------------------------------------------------------

#: 必需列。缺失任一列即视为数据不合格。
REQUIRED_COLUMNS: tuple[str, ...] = (
    "date",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
)

#: 可选列。允许缺失，但若存在则会参与校验。
OPTIONAL_COLUMNS: tuple[str, ...] = (
    "name",
    "amount",
    "adjust_factor",
    "market",
    "asset_type",
    "suspended",
)

#: 全部规范列（必需 + 可选），固定顺序。
CANONICAL_COLUMNS: tuple[str, ...] = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

#: OHLCV 数值列（用于类型强制与有限性检查）。
_PRICE_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close")
_VOLUME_COLUMNS: tuple[str, ...] = ("volume", "amount")


class DataIntegrityError(ValueError):
    """行情数据违反 canonical schema 或完整性约束时抛出。

    本异常**绝不**在数据层内部被静默吞掉：调用方必须显式处理，
    以免把「数据缺失」误当成「数据正常」。
    """


# --- 归一化 ---------------------------------------------------------------


def normalize_frame(
    frame: pd.DataFrame,
    *,
    symbol: str | None = None,
    name: str | None = None,
    market: str | None = None,
    asset_type: str | None = None,
) -> pd.DataFrame:
    """把任意来源的行情 DataFrame 归一化为 canonical frame。

    处理内容：

    1. 列名统一为小写（``Date``/``OPEN``/``Close`` → ``date``/``open``/``close``）。
    2. 兼容常见别名：``vol``/``count`` → ``volume``，``turnover`` → ``amount``。
    3. ``date`` 统一为 ``pandas.Timestamp``（去掉时间部分，日线语义）。
    4. 若未提供 ``symbol`` 列且传入 ``symbol`` 参数，则补齐常量列。
    5. 按 ``date`` 升序排序并去重（重复日期**保留最后一条**并记录，
       由调用方决定是否需要 :func:`validate_frame` 报错）。

    不在此处填充缺失值 —— 缺失处理属策略决策，见
    ``docs/data/market_data_policy.md``。
    """
    if not isinstance(frame, pd.DataFrame):
        raise DataIntegrityError(f"normalize_frame 需要 DataFrame，收到 {type(frame).__name__}")

    df = frame.copy()

    # 1. 列名小写
    df.columns = [str(c).strip().lower() for c in df.columns]

    # 2. 别名映射
    aliases = {
        "vol": "volume",
        "count": "volume",
        "成交量": "volume",
        "turnover": "amount",
        "成交额": "amount",
        "成交金额": "amount",
        "日期": "date",
        "开盘价": "open",
        "最高价": "high",
        "最低价": "low",
        "收盘价": "close",
    }
    df = df.rename(columns={k: v for k, v in aliases.items() if k in df.columns})

    # 3. date 规范化
    if "date" not in df.columns:
        raise DataIntegrityError("行情数据缺少 date 列（可用别名：Date/日期）")
    df.loc[:, "date"] = pd.to_datetime(df["date"]).dt.normalize()

    # 4. 补齐常量列
    if symbol is not None:
        df["symbol"] = symbol
    if name is not None:
        df["name"] = name
    if market is not None:
        df["market"] = market
    if asset_type is not None:
        df["asset_type"] = asset_type

    # 5. 排序 + 去重（保留最后一条，即最新到达的记录）
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")

    # 6. 列顺序：canonical 顺序在前，额外列保留其后
    ordered = [c for c in CANONICAL_COLUMNS if c in df.columns]
    extra = [c for c in df.columns if c not in CANONICAL_COLUMNS]
    df = df[ordered + extra].reset_index(drop=True)
    return df


# --- 校验 -----------------------------------------------------------------


def validate_frame(
    frame: pd.DataFrame,
    *,
    require_optional: Sequence[str] | None = None,
    check_monotonic: bool = True,
    check_ohlc_bounds: bool = True,
    check_finite: bool = True,
) -> None:
    """校验 canonical frame 的完整性，违反时抛 :class:`DataIntegrityError`。

    检查项（对应任务书第十九节的测试要求）：

    - 必需列齐全（缺失列 → 报错，**不静默补列**）。
    - 日期升序且无重复（``check_monotonic``）。
    - OHLC 内部一致性：``low <= min(open, close) <= max(open, close) <= high``
      （``check_ohlc_bounds``）。停牌日由 ``suspended`` 列标记，不在此处豁免。
    - 数值列全为有限值（无 NaN/inf）（``check_finite``）。

    :param require_optional: 额外要求必须存在的可选列名。
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise DataIntegrityError(f"缺少必需列: {missing}")

    if require_optional:
        missing_opt = [c for c in require_optional if c not in frame.columns]
        if missing_opt:
            raise DataIntegrityError(f"缺少要求的可选列: {missing_opt}")

    if len(frame) == 0:
        return  # 空表通过结构性检查，由调用方判断是否可用

    if check_monotonic:
        if frame["date"].duplicated().any():
            dups = frame.loc[frame["date"].duplicated(), "date"].head(5).tolist()
            raise DataIntegrityError(f"存在重复日期（示例）: {dups}")
        # 显式用 numpy 比较，避免 pandas Index 构造触发 FutureWarning
        vals = frame["date"].to_numpy()
        if len(vals) > 1 and not bool((vals[1:] >= vals[:-1]).all()):
            raise DataIntegrityError("date 列未按升序排列")

    if check_finite:
        for col in _PRICE_COLUMNS + _VOLUME_COLUMNS:
            if col not in frame.columns:
                continue
            series = frame[col]
            if series.isna().any():
                n = int(series.isna().sum())
                raise DataIntegrityError(f"列 {col} 含 {n} 个缺失值（不静默填充）")
            try:
                if not series.map(_is_finite_number).all():
                    raise DataIntegrityError(f"列 {col} 含非有限值（inf/nan）")
            except TypeError:
                # 非数值列（如意外的字符串），直接判不合格
                raise DataIntegrityError(f"列 {col} 含非数值内容")

    if check_ohlc_bounds:
        hi = frame["high"]
        lo = frame["low"]
        op = frame["open"]
        cl = frame["close"]
        bad = (hi < lo) | (op > hi) | (op < lo) | (cl > hi) | (cl < lo)
        if bad.any():
            idx = frame.index[bad][:5].tolist()
            raise DataIntegrityError(f"OHLC 边界不一致（low<=o/c<=high 被违反），行索引示例: {idx}")


def _is_finite_number(v: object) -> bool:
    """判断是否为有限数值（排除 NaN / inf）。"""
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return f == f and f not in (float("inf"), float("-inf"))


def describe_schema() -> dict[str, Iterable[str]]:
    """返回 schema 摘要，供文档生成与测试断言使用。"""
    return {
        "required": REQUIRED_COLUMNS,
        "optional": OPTIONAL_COLUMNS,
        "canonical": CANONICAL_COLUMNS,
    }


def align_columns(
    frames: Mapping[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """把多标的 frame 对齐到交集的日期索引。

    用于横截面策略：只有全部标的都有数据的日期才是可比较的日期。
    返回按日期升序、索引为日期的 dict。
    """
    if not frames:
        return {}
    idx: pd.Index | None = None
    for df in frames.values():
        s = pd.Index(df["date"])
        idx = s if idx is None else idx.intersection(s)
    assert idx is not None
    out: dict[str, pd.DataFrame] = {}
    for k, df in frames.items():
        sub = df.set_index("date").loc[idx].sort_index()
        out[k] = sub
    return out
