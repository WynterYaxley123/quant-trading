"""时点完整性（Temporal Integrity）工具。

本模块是整套 sector rotation 核心的**防未来数据泄露护栏**。
所有训练 / 推理 / 回测代码都必须通过这里的时间语义函数来切分数据，
不得自行用 iloc 或手工日期算术绕过。

迁移来源
--------
Legacy china-market-data v5 (release commit 1923f9d0fb00eeece9538ae1d0af9db57bbb02d5)，
其中 ``backtest_production.py::temporal_boundaries`` 是最早的正确实现。
本模块把它提炼为可复用、可测试的纯函数集合，并补充 pytest 护栏。

核心不变量
----------
1. 预测日 t、预测周期 fwd 交易日：最后一条可进入训练的数据，其 forward
   label 必须在 t 时刻**已经完全实现**。
2. 特征只能使用 <= as_of 的价格。
3. 当前推理行不得进入训练标签。
4. 历史模式禁止使用实时资金流。
5. 未披露财务数据不得进入历史训练。
6. 宏观数据在发布时间之前不可见。

本模块**不做任何 I/O**，只做时间/切分计算，便于单元测试。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = [
    "TemporalBoundaries",
    "as_of_truncate",
    "trading_calendar",
    "position_of",
    "temporal_boundaries",
    "make_forward_label",
    "training_window",
    "inference_rows",
    "non_overlapping_periods",
    "assert_no_lookahead",
    "ALLOWED_TRAIN_GROUPS",
    "FORBIDDEN_TRAIN_FEATURES",
    "validate_train_features",
    "signal_timing",
    "validate_execution_date",
]

# ---------------------------------------------------------------------------
# 常量：训练特征白名单
# ---------------------------------------------------------------------------

#: 允许进入训练的因子组（与 legacy v5 TRAIN_GROUPS 一致）。
ALLOWED_TRAIN_GROUPS = ("ma", "vol", "rev", "dd", "macro")

#: 明确**禁止**进入训练的特征。
#:
#: - ``flow_net`` / ``flow_pct``：实时资金流，历史回测中不可得，只能做
#:   inference 阶段的 post-hoc 修正。
#: - ``profit_growth`` / ``roe`` / ``pb_inv``：legacy 没有可靠的逐公司
#:   point-in-time 财报快照，加入训练即构成前视偏差。
#: - 动量族 ``m5`` / ``m20`` / ``m60`` / ``accel`` 与量比 ``vr5`` /
#:   ``vr20``：legacy 实验已消融，不作为正式训练特征迁移。
FORBIDDEN_TRAIN_FEATURES = frozenset(
    {
        "flow_net",
        "flow_pct",
        "profit_growth",
        "roe",
        "pb_inv",
        "m5",
        "m20",
        "m60",
        "accel",
        "vr5",
        "vr20",
    }
)


def validate_train_features(features: Iterable[str]) -> None:
    """校验一组特征名不含被禁特征；违规时抛 ``ValueError``。

    这是 HARD GUARDRAIL：未来 ChatGPT 修改策略时若不小心把资金流或基本面
    放回训练集，测试会立刻失败。
    """
    bad = sorted(set(features) & FORBIDDEN_TRAIN_FEATURES)
    if bad:
        raise ValueError(
            f"禁止进入训练的特征: {bad}. "
            "fundamentals 无可信 PIT 快照；flow 只能做 inference post-hoc 修正。"
        )


# ---------------------------------------------------------------------------
# 基础时间工具
# ---------------------------------------------------------------------------


def trading_calendar(dates: Iterable) -> pd.DatetimeIndex:
    """把任意日期序列整理成去重、升序的 ``DatetimeIndex``。"""
    cal = pd.DatetimeIndex(list(dates))
    if cal.hasnans or cal.tz is not None or not cal.equals(cal.normalize()):
        raise ValueError("交易日历必须为无 NaT、无时区的日频日期")
    return cal.unique().sort_values()


def validate_execution_date(signal_date, execution_date) -> None:
    """收盘后决策不得在同日或更早成交；可交易性由执行层另行验证。"""
    signal, execution = pd.Timestamp(signal_date), pd.Timestamp(execution_date)
    if pd.isna(signal) or pd.isna(execution) or execution.normalize() <= signal.normalize():
        raise ValueError("execution_date 必须晚于 signal_date；信号在收盘后产生")


def signal_timing(calendar: Sequence, signal_date, forward_days: int) -> dict:
    """标签观察期与交易持有期分开；next session 仅是执行下界，不保证成交。"""
    if (
        isinstance(forward_days, bool)
        or not isinstance(forward_days, (int, np.integer))
        or forward_days <= 0
    ):
        raise ValueError("forward_days 必须为正整数")
    cal = trading_calendar(calendar)
    signal = pd.Timestamp(signal_date)
    pos = position_of(cal, signal)
    if pos is None:
        raise ValueError("signal_date 不在交易日历中")
    return {
        "signal_date": signal,
        "decision_time": "after_close",
        "earliest_execution_date": cal[pos + 1] if pos + 1 < len(cal) else None,
        "execution_date": None,  # 实际成交日只能由执行引擎提供
        "label_start": signal,
        "label_end": cal[pos + forward_days] if pos + forward_days < len(cal) else None,
        "prediction_horizon": int(forward_days),
        "rebalance_cadence": None,
        "holding_period": None,
        "holding_end": None,
    }


def position_of(calendar: pd.DatetimeIndex, date) -> int | None:
    """返回 ``date`` 在交易日历中的位置；不存在返回 ``None``。"""
    try:
        return int(calendar.get_loc(pd.Timestamp(date)))
    except KeyError:
        return None


def as_of_truncate(frame: pd.DataFrame, as_of) -> pd.DataFrame:
    """截断到 ``as_of``（含当日）之前的行。

    预测在 t 日收盘后做出，因此 t 日收盘价可用，``as_of`` 本身保留。
    """
    if frame.empty:
        return frame
    ts = pd.Timestamp(as_of)
    return frame.loc[frame.index <= ts]


# ---------------------------------------------------------------------------
# purge 核心
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TemporalBoundaries:
    """一次 walk-forward 预测的合法时间边界。

    Attributes
    ----------
    pred_date:
        做出预测的日期（收盘后）。
    label_cutoff:
        最后一条允许进入训练的日期。其 forward label 在 ``pred_date``
        时已完全实现，即 ``label_cutoff + fwd`` 交易日 <= ``pred_date``。
    realized_end:
        本次预测的标签实现日 = ``calendar[pred_pos + fwd]``；未知则 None。
        最后训练标签的实现日为 pred_date，与本字段不同。
    train_start:
        滚动训练窗口起点 = ``label_cutoff - train_months``。
    forward_days:
        预测周期（交易日）。
    """

    pred_date: pd.Timestamp
    label_cutoff: pd.Timestamp
    realized_end: pd.Timestamp | None
    train_start: pd.Timestamp
    forward_days: int

    def as_dict(self) -> dict:
        return {
            "pred_date": str(self.pred_date.date()),
            "label_cutoff": str(self.label_cutoff.date()),
            "realized_end": str(self.realized_end.date())
            if self.realized_end is not None
            else None,
            "train_start": str(self.train_start.date()),
            "forward_days": self.forward_days,
        }


def temporal_boundaries(
    calendar: Sequence,
    pred_date,
    forward_days: int,
    train_months: int = 6,
) -> TemporalBoundaries | None:
    """计算 purged rolling window。

    参数
    ----
    calendar:
        交易日历（去重排序；调用方必须提供真实交易日，不能传普通自然日）。
    pred_date:
        预测日。
    forward_days:
        预测周期，单位交易日。
    train_months:
        滚动训练窗口长度（月）。

    返回
    ----
    ``TemporalBoundaries``，若 ``pred_date`` 不在日历中、或日历长度不足以
    在历史侧留出 ``forward_days``，则返回 ``None``。推理不要求未来日历。

    关键：``label_cutoff = calendar[pred_pos - forward_days]``。
    这保证 ``label_cutoff`` 的 fwd 日收益在 ``pred_date`` 当天已经实现完毕，
    即训练集里**不存在**任何依赖未来价格的标签。这正是 purge 的含义。
    """
    for name, value in (("forward_days", forward_days), ("train_months", train_months)):
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value <= 0:
            raise ValueError(f"{name} 必须为正整数")
    cal = trading_calendar(calendar)
    pred_ts = pd.Timestamp(pred_date)
    pred_pos = position_of(cal, pred_ts)
    if pred_pos is None:
        return None
    if pred_pos < forward_days:
        return None

    label_cutoff = cal[pred_pos - forward_days]
    realized_end = cal[pred_pos + forward_days] if pred_pos + forward_days < len(cal) else None
    train_start = label_cutoff - pd.DateOffset(months=train_months)
    return TemporalBoundaries(
        pred_date=pred_ts,
        label_cutoff=label_cutoff,
        realized_end=realized_end,
        train_start=train_start,
        forward_days=int(forward_days),
    )


# ---------------------------------------------------------------------------
# 标签 / 训练 / 推理切分
# ---------------------------------------------------------------------------


def make_forward_label(
    close: pd.Series, forward_days: int, *, calendar: Sequence | None = None
) -> pd.Series:
    """构造未来 ``forward_days`` 日收益标签。

    ``label[t] = close[calendar[pos(t)+fwd]] / close[t] - 1``。
    缺失终点保留 NaN，不填价格。省略 calendar 仅适用于完整日历序列；
    核心编排器始终传入公共交易日历，不能用行业自身缺日的行数代替。
    """
    if (
        isinstance(forward_days, bool)
        or not isinstance(forward_days, (int, np.integer))
        or forward_days <= 0
    ):
        raise ValueError("forward_days 必须为正整数")
    if (
        not isinstance(close.index, pd.DatetimeIndex)
        or close.index.has_duplicates
        or close.index.hasnans
    ):
        raise ValueError("label index 必须为唯一、无 NaT 的 DatetimeIndex")
    close = close.sort_index()
    values = close.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("label close 必须为有限正价格")
    cal = trading_calendar(close.index if calendar is None else calendar)
    if not close.index.isin(cal).all():
        raise ValueError("close 日期不在公共交易日历中")
    aligned = close.reindex(cal)  # 缺失日期保留 NaN，绝不移动终点或填价格
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        labels = aligned.shift(-forward_days) / aligned - 1.0
    return labels.reindex(close.index)


def training_window(
    labelled_dates: Sequence,
    boundaries: TemporalBoundaries,
    min_observations: int = 30,
) -> list[pd.Timestamp]:
    """返回可进入训练、且 forward label 已完全实现的日期列表。

    只有落在 ``[train_start, label_cutoff]`` 内、且明确存在于
    ``labelled_dates``（即已有已实现标签）中的日期才被保留。
    """
    ld = sorted(pd.Timestamp(d) for d in labelled_dates)
    window = [d for d in ld if boundaries.train_start <= d <= boundaries.label_cutoff]
    if len(window) < min_observations:
        return []
    return window


def inference_rows(
    frame: pd.DataFrame,
    pred_date,
    *,
    require_label: bool = False,
    label_column: str | None = None,
) -> pd.DataFrame:
    """取出可用于推理的行。

    ``require_label=False``（推理）：允许最新一行没有标签，只要特征齐全。
    ``require_label=True``（训练）：要求 forward label 完整存在。

    本函数只负责按日期和标签有无做筛选，特征完整性由调用方或
    :func:`assert_no_lookahead` 之外的逻辑校验。
    """
    if frame.empty:
        return frame
    ts = pd.Timestamp(pred_date)
    sel = frame.loc[frame.index <= ts]
    if require_label and label_column is not None:
        sel = sel.loc[sel[label_column].notna()]
    return sel


def non_overlapping_periods(
    dates: Sequence,
    forward_days: int,
) -> list[pd.Timestamp]:
    """从日期序列中挑出样本周期互不重叠的观测点。

    评估 Sharpe / 最大回撤等正式绩效指标时，若使用重叠的 forward window，
    会把同一段未来收益重复计入，人为抬高统计显著性。本函数按
    ``forward_days`` 步长抽样，保证相邻两个评估点的持有期不重叠。

    用途：仅限**正式绩效统计**。特征构造、训练取样仍可使用全部日期。
    """
    d = sorted(pd.Timestamp(x) for x in dates)
    if forward_days <= 0 or not d:
        return []
    out = []
    last_pos = None
    for ts in d:
        pos = d.index(ts)
        if last_pos is None or pos - last_pos >= forward_days:
            out.append(ts)
            last_pos = pos
    return out


# ---------------------------------------------------------------------------
# 护栏
# ---------------------------------------------------------------------------


def assert_no_lookahead(
    frame: pd.DataFrame,
    as_of,
    price_columns: Sequence[str] = ("open", "high", "low", "close", "volume", "amount"),
) -> None:
    """断言 ``frame`` 中不存在晚于 ``as_of`` 的价格数据。

    这是结构性护栏，用于测试与 adapter 入口自检：
    ``as_of`` 之后的价格必须不可见。
    """
    if frame.empty:
        return
    ts = pd.Timestamp(as_of)
    future = frame.loc[frame.index > ts]
    if not future.empty:
        raise ValueError(
            f"检测到未来数据泄露: {len(future)} 行晚于 as_of={ts.date()}, "
            f"首个违规日期={future.index[0].date()}"
        )
    hit = [c for c in price_columns if c in frame.columns]
    if not hit:
        raise ValueError(
            f"frame 缺少价格列; 期望其中之一: {list(price_columns)}, 实际列: {list(frame.columns)}"
        )
