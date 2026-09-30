"""回测结果标准化结构。

设计原则（任务书第十四、十五、十六节）：

1. 结果统一写入 ``reports/backtests/<output_dir_name>/<run_id>/``。
2. 不支持的字段用 :data:`UNSUPPORTED`（序列化为 ``null``），
   **绝不用 0 冒充不存在的数据**。
3. metadata 必须完整到可以追溯任何一次回测。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd

__all__ = [
    "UNSUPPORTED",
    "BacktestMetadata",
    "BacktestMetrics",
    "BacktestResult",
    "RESULT_FILES",
]

#: 表示「该指标当前框架无法提供」。序列化为 JSON ``null``。
UNSUPPORTED: None = None

#: 一次回测输出的标准文件集合。
RESULT_FILES: tuple[str, ...] = (
    "metadata.json",
    "metrics.json",
    "trades.csv",
    "positions.csv",
    "equity_curve.csv",
    "yearly_returns.csv",
    "report.md",
)


@dataclass
class BacktestMetadata:
    """回测元数据 —— 用于追溯（任务书第十五节）。"""

    strategy: str
    strategy_version: str
    framework: str
    framework_version: str
    git_commit: str
    run_id: str
    start_date: str
    end_date: str
    data_source: str
    data_snapshot: str | None
    initial_cash: float
    commission: float | None
    slippage: float | None
    status: str
    # --- 运行类型（本轮新增） ---
    #: 本次运行的性质。取值：
    #:
    #: - ``"strategy_backtest"`` —— 真实策略回测，指标可用于评价策略。
    #: - ``"execution_smoke"`` —— 仅验证执行链路（KData → System → 订单 →
    #:   TradeManager → 净值）。**指标不得用于评价任何策略。**
    #:
    #: 默认值取 ``"strategy_backtest"`` 是刻意选择：若忘记设置，宁可被当成
    #: 正式回测而被人工质疑，也不能默认伪装成 smoke 来逃避 scrutiny。
    run_type: str = "strategy_backtest"
    # --- 扩展（本轮新增，用于如实记录未建模项） ---
    #: 复权口径：``none``（未复权）/ ``backward`` / ``forward``
    adjust_mode: str = "none"
    #: 是否建模涨跌停
    limit_up_down_modeled: bool = False
    #: 是否建模停牌
    suspension_modeled: bool = False
    #: 标的列表
    symbols: tuple[str, ...] = ()
    #: 数据实际区间
    data_coverage: Mapping[str, Any] = field(default_factory=dict)
    #: 未建模 / 未完成事项（如实记录）
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def output_dir_name(self) -> str:
        """结果目录名 —— 决定 ``reports/backtests/<output_dir_name>/<run_id>/``。

        execution_smoke 运行**不允许**占用策略名目录，否则会让人误以为
        该目录下的数字是策略绩效。因此强制映射到 ``hikyuu_execution_smoke``。
        """
        if self.run_type == "execution_smoke":
            return "hikyuu_execution_smoke"
        return self.strategy

    @property
    def is_execution_smoke(self) -> bool:
        """是否为执行冒烟运行（其指标不可用于评价策略）。"""
        return self.run_type == "execution_smoke"


@dataclass
class BacktestMetrics:
    """回测指标（任务书第十六节）。

    字段值为 ``None`` 表示**当前框架无法提供**，不是 0。
    """

    initial_cash: float | None = None
    final_value: float | None = None
    total_return: float | None = None
    annual_return: float | None = None
    max_drawdown: float | None = None
    volatility: float | None = None
    sharpe: float | None = None
    trade_count: int | None = None
    commission: float | None = None
    slippage: float | None = None
    execution_time: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def unsupported_fields(self) -> list[str]:
        """列出当前为 None（框架未提供）的字段。"""
        return [k for k, v in asdict(self).items() if v is None]


@dataclass
class BacktestResult:
    """一次回测的完整结果，可直接落盘为标准文件集。"""

    metadata: BacktestMetadata
    metrics: BacktestMetrics
    trades: pd.DataFrame = field(default_factory=pd.DataFrame)
    positions: pd.DataFrame = field(default_factory=pd.DataFrame)
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)
    yearly_returns: pd.DataFrame = field(default_factory=pd.DataFrame)

    # -- 落盘 ---------------------------------------------------------------

    def write(self, root: str) -> str:
        """写入 ``root/<output_dir_name>/<run_id>/``，返回输出目录。

        ``output_dir_name`` 由 metadata 决定（见
        :attr:`BacktestMetadata.output_dir_name`）：execution_smoke 运行会被
        强制写入 ``hikyuu_execution_smoke/``，不占用策略名目录。

        所有文件都会写出（即便为空表），以保证目录结构可预测。
        """
        out = os.path.join(root, self.metadata.output_dir_name, self.metadata.run_id)
        os.makedirs(out, exist_ok=True)

        with open(os.path.join(out, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(self.metadata.to_dict(), f, ensure_ascii=False, indent=2,
                      default=_json_default)

        m = self.metrics.to_dict()
        with open(os.path.join(out, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2, default=_json_default)

        for name, df in (
            ("trades.csv", self.trades),
            ("positions.csv", self.positions),
            ("equity_curve.csv", self.equity_curve),
            ("yearly_returns.csv", self.yearly_returns),
        ):
            df.to_csv(os.path.join(out, name), index=False, encoding="utf-8")

        with open(os.path.join(out, "report.md"), "w", encoding="utf-8") as f:
            f.write(self.render_report())

        return out

    # -- 报告 ---------------------------------------------------------------

    def render_report(self) -> str:
        md = self.metadata
        mt = self.metrics
        lines: list[str] = []
        lines.append(f"# 回测报告 — {md.strategy}")
        lines.append("")
        if md.is_execution_smoke:
            # 必须在任何人读到数字之前看到这段。
            lines.append("> ## ⚠️ THIS IS NOT A SW_SECTOR_ROTATION STRATEGY BACKTEST.")
            lines.append("> ")
            lines.append("> 本次运行 ``run_type = execution_smoke``：仅验证 Hikyuu 执行链路")
            lines.append("> （KData → System → 订单 → TradeManager → 净值/成交记录）能否在")
            lines.append("> **真实行情**上跑通。")
            lines.append("> ")
            lines.append("> 使用的规则是确定性的极简测试规则（固定均线交叉 + 固定手数 +")
            lines.append("> 固定止损），**未做任何参数优化**。")
            lines.append("> ")
            lines.append("> **下方所有指标（收益/回撤/Sharpe/成交数）均不得用于评价**")
            lines.append("> ``sw_sector_rotation`` **或其他任何策略的质量。**")
            lines.append("> ")
            lines.append("> sw_sector_rotation 的完整回测（LEVEL B）尚未执行 —— 原因：")
            lines.append("> 申万二级行业数据未初始化，无法产生行业 ranking。")
            lines.append("")
        lines.append(f"- run_id: `{md.run_id}`")
        lines.append(f"- 运行类型: **{md.run_type}**")
        lines.append(f"- 框架: {md.framework} {md.framework_version}")
        lines.append(f"- 策略版本: {md.strategy_version}")
        lines.append(f"- git commit: `{md.git_commit}`")
        lines.append(f"- 区间: {md.start_date} ~ {md.end_date}")
        lines.append(f"- 状态: **{md.status}**")
        lines.append(f"- 数据源: {md.data_source}")
        lines.append(f"- 复权口径: {md.adjust_mode}")
        lines.append("")
        lines.append("## 指标")
        lines.append("")
        lines.append("| 指标 | 值 |")
        lines.append("|---|---|")
        for k, v in mt.to_dict().items():
            if v is None:
                lines.append(f"| {k} | *unsupported* |")
            elif isinstance(v, float):
                lines.append(f"| {k} | {v:.6g} |")
            else:
                lines.append(f"| {k} | {v} |")
        lines.append("")
        if mt.unsupported_fields:
            lines.append("> **unsupported 字段说明**：当前框架无法提供以下指标，已置为 `null`，"
                         "**未用 0 冒充**：")
            lines.append("> " + ", ".join(mt.unsupported_fields))
            lines.append("")
        lines.append("## 未建模事项")
        lines.append("")
        lines.append(f"- 涨跌停建模: {'是' if md.limit_up_down_modeled else '**否**'}")
        lines.append(f"- 停牌建模: {'是' if md.suspension_modeled else '**否**'}")
        if md.limitations:
            lines.append("")
            lines.append("已知限制：")
            for x in md.limitations:
                lines.append(f"- {x}")
        lines.append("")
        lines.append("## 输出文件")
        lines.append("")
        for n in RESULT_FILES:
            lines.append(f"- `{n}`")
        lines.append("")
        return "\n".join(lines)


def _json_default(o: Any):
    """JSON 序列化兜底（numpy/pandas 类型）。"""
    import numpy as np

    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        f = float(o)
        return None if (f != f) else f  # NaN -> null
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (datetime,)):
        return o.isoformat()
    if hasattr(o, "item"):
        try:
            return o.item()
        except Exception:  # noqa: BLE001
            pass
    return str(o)


def now_run_id(prefix: str = "") -> str:
    """生成 run_id：``YYYYmmdd-HHMMSS``（UTC）加可选前缀。"""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}{ts}" if prefix else ts
