"""SW Sector Rotation Core —— 策略编排器。

把因子、模型、风险状态串成一条**不依赖任何框架**的流水线：

    行业 OHLCVA panel
      ↓ 因子              strategies.sw_sector_rotation.src.factors.sector_rotation / rsrs / macro_pit
      ↓ 时点切分           strategies.sw_sector_rotation.src.common.temporal_integrity
      ↓ 横截面 Ridge 排名   model.CrossSectionalRidgeModel
      ↓ 排名 + 权重        ranking
      ↓ ETF 候选           strategies.sw_sector_rotation.src.portfolio.sector_etf_mapping
      ↓ 风险状态（旁路）    strategies.sw_sector_rotation.src.risk.sector_rotation

设计要点
--------
1. **纯核心 + adapter 分离**：本模块只接受 canonical market frame，
   不 import hikyuu / rqalpha。框架适配见 ``strategies.sw_sector_rotation.src.adapters.hikyuu``。
2. **风险状态旁路**：:meth:`SWSectorRotationCore.evaluate_risk` 返回
   :class:`RiskState`，**不参与**排名计算，也不缩放分数。
3. **本阶段不做正式回测**：只提供接口。回测由 Hikyuu / RQAlpha 承担。
4. **资金流默认关闭**：仅当 ``flow_posthoc_enabled=True`` 且显式传入
   ``live_flow`` 时才做推理期 post-hoc 修正，且修正幅度受限 ±0.02。

迁移来源：Legacy china-market-data v5 (commit 1923f9d…)，已剥离
self_improver / meta_learner / daemon / 飞书 / cron 等全部基础设施。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from strategies.sw_sector_rotation.src.common.temporal_integrity import (
    TemporalBoundaries,
    as_of_truncate,
    make_forward_label,
    signal_timing,
    temporal_boundaries,
    trading_calendar,
    validate_train_features,
)
from strategies.sw_sector_rotation.src.factors.sector_rotation import (
    TRAIN_FEATURES_PRICE,
    compute_all_price_features,
)
from strategies.sw_sector_rotation.src.model.model import (
    DEFAULT_ALPHA,
    DEFAULT_TOP_N,
    DEFAULT_TRAIN_MONTHS,
    FORWARD_WINDOWS,
    FUSION_WEIGHTS,
    MIN_TRAIN_DATES,
    CrossSectionalRidgeModel,
)
from strategies.sw_sector_rotation.src.model.ranking import (
    build_etf_candidates,
    rank_sectors,
    sector_scores_to_weights,
    select_top,
)
from strategies.sw_sector_rotation.src.risk.sector_rotation import RiskState, compute_risk_state

__all__ = [
    "FLOW_ADJUST_LIMIT",
    "SWSectorRotationConfig",
    "SWSectorRotationCore",
    "apply_flow_adjustment",
]

#: 资金流 post-hoc 修正上限（legacy 为 ±0.02）。
FLOW_ADJUST_LIMIT = 0.02


def apply_flow_adjustment(score: float, flow_net: float) -> float:
    """资金流 post-hoc 修正（纯算法接口）。

    ``score`` 为基础模型分数，``flow_net`` 为资金净流入指标。
    修正量限制在 ``±FLOW_ADJUST_LIMIT``。

    **资金流不得进入历史训练**，只能作为未来实时推理阶段的
    OPTIONAL POST-HOC FEATURE（默认 disabled）。
    """
    if not np.isfinite([score, flow_net]).all():
        raise ValueError("flow adjustment 输入必须有限")
    adj = float(np.clip(float(flow_net) / 10.0, -FLOW_ADJUST_LIMIT, FLOW_ADJUST_LIMIT))
    return float(score) + adj


@dataclass
class SWSectorRotationConfig:
    """策略配置。默认值均为 LEGACY INITIAL DEFAULT，非最终最优。"""

    alpha: float = DEFAULT_ALPHA
    train_months: int = DEFAULT_TRAIN_MONTHS
    top_n: int = DEFAULT_TOP_N
    min_train_dates: int = MIN_TRAIN_DATES
    forward_windows: dict = field(default_factory=lambda: dict(FORWARD_WINDOWS))
    fusion_weights: dict = field(default_factory=lambda: dict(FUSION_WEIGHTS))
    macro_enabled: bool = False
    flow_posthoc_enabled: bool = False
    include_fundamentals: bool = False  # HARD: 必须保持 False

    def __post_init__(self) -> None:
        if self.include_fundamentals:
            raise ValueError(
                "include_fundamentals 必须为 False：无可信 PIT 财报快照，加入训练将构成前视偏差。"
            )
        if self.macro_enabled:
            raise ValueError("macro_enabled 尚无真实 PIT 数据接线，必须保持 False")
        if not np.isfinite(self.alpha) or self.alpha < 0:
            raise ValueError("alpha 必须为有限非负数")
        for name in ("train_months", "top_n", "min_train_dates"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise ValueError(f"{name} 必须为正整数")
        if set(self.forward_windows) != set(FORWARD_WINDOWS):
            raise ValueError("必须声明 short/medium/long 三个 horizon")
        for v in self.forward_windows.values():
            if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
                raise ValueError("prediction horizon 必须为正整数")
        if set(self.fusion_weights) != set(self.forward_windows):
            raise ValueError("fusion_weights 与 horizons 不一致")
        weights = np.asarray(list(self.fusion_weights.values()), dtype=float)
        if (
            not np.isfinite(weights).all()
            or (weights <= 0).any()
            or not np.isclose(weights.sum(), 1.0)
        ):
            raise ValueError("fusion_weights 必须为有限正数且和为 1")

    @classmethod
    def from_yaml(cls, path: str | Path | None = None) -> "SWSectorRotationConfig":
        """包内 YAML 是默认运行配置；显式 config 对象可用于合成测试。"""
        import yaml

        source = (
            Path(path)
            if path is not None
            else Path(__file__).resolve().parents[1] / "config/sw_sector_rotation.yaml"
        )
        data = yaml.safe_load(source.read_text(encoding="utf-8"))
        model = data["model"]
        optional = data["features"]["optional"]
        return cls(
            alpha=model["alpha"],
            train_months=model["train_months"],
            top_n=model["top_n"],
            min_train_dates=model["min_train_dates"],
            forward_windows=dict(model["horizons"]),
            fusion_weights=dict(model["fusion_weights"]),
            macro_enabled=optional["macro_pit"],
            flow_posthoc_enabled=optional["fund_flow_posthoc"],
        )


class SWSectorRotationCore:
    """行业横截面排名策略核心（框架无关）。"""

    def __init__(self, config: SWSectorRotationConfig | None = None):
        self.config = config or SWSectorRotationConfig.from_yaml()
        self.model = CrossSectionalRidgeModel(
            alpha=self.config.alpha,
            train_months=self.config.train_months,
            top_n=self.config.top_n,
            forward_windows=self.config.forward_windows,
            fusion_weights=self.config.fusion_weights,
            min_train_dates=self.config.min_train_dates,
        )
        # 结构性护栏：训练特征不得含被禁特征
        validate_train_features(TRAIN_FEATURES_PRICE)
        self.feature_names: list[str] = list(TRAIN_FEATURES_PRICE)

    # -- 因子 ---------------------------------------------------------------

    def build_panel(
        self,
        market_frames: Mapping[str, pd.DataFrame],
        *,
        include_rsrs: bool = True,
        calendar: Sequence | None = None,
    ) -> dict[str, pd.DataFrame]:
        """把原始 OHLCVA panel 转成带因子与标签的 panel。

        为每个周期生成 ``fwd{w}`` 标签（未来 w 日收益）。标签使用
        :func:`make_forward_label` 按公共交易日历偏移；终点缺失则为 NaN。
        """
        panel: dict[str, pd.DataFrame] = {}
        if calendar is None and market_frames:
            indices = [f.index for f in market_frames.values()]
            if any(not idx.equals(indices[0]) for idx in indices[1:]):
                raise ValueError("行业日期不一致时必须提供公共交易日历")
            calendar = indices[0].tolist()
        for name, frame in market_frames.items():
            feats = compute_all_price_features(frame, include_rsrs=include_rsrs)
            for w in self.config.forward_windows.values():
                feats[f"fwd{w}"] = make_forward_label(frame["close"], w, calendar=calendar)
            panel[name] = feats
        return panel

    # -- 时点 ---------------------------------------------------------------

    def boundaries(
        self, calendar: Sequence, predict_date, period: str
    ) -> TemporalBoundaries | None:
        """计算某周期的 purged 训练/预测边界。"""
        fwd = self.config.forward_windows[period]
        return temporal_boundaries(calendar, predict_date, fwd, self.config.train_months)

    # -- 训练 + 推理 --------------------------------------------------------

    def run_period(
        self,
        period: str,
        panel: Mapping[str, pd.DataFrame],
        calendar: Sequence,
        predict_date,
    ) -> dict | None:
        """运行单周期的训练 + 预测。

        返回 ``{"ranking", "result", "boundaries", "scores"}``，
        训练数据不足时返回 ``None``。
        """
        fwd = self.config.forward_windows[period]
        label_col = f"fwd{fwd}"
        b = self.boundaries(calendar, predict_date, period)
        if b is None:
            self.model.models.pop(period, None)
            self.model.feature_schemas.pop(period, None)
            self.model.training_coverage.pop(period, None)
            return None

        # 训练日期：已实现标签且落在 [train_start, label_cutoff]
        labelled_sets = []
        for frame in panel.values():
            # Restrict chronology before allocating validity sets or selecting columns.
            labels = frame.loc[b.train_start : b.label_cutoff, label_col]
            labelled_sets.append(set(labels.index[labels.notna()]))
        labelled = sorted(set.intersection(*labelled_sets)) if labelled_sets else []
        train_dates = [d for d in labelled if b.train_start <= d <= b.label_cutoff]
        model = self.model.fit_period(period, dict(panel), self.feature_names, train_dates)
        if model is None:
            return None

        result = self.model.predict_period(period, dict(panel), self.feature_names, b.pred_date)
        result.train_start = b.train_start
        result.train_end = b.label_cutoff

        ranking = rank_sectors(result.scores)
        return {
            "period": period,
            "boundaries": b,
            "train_dates": train_dates,
            "scores": dict(result.scores),
            "ranking": ranking,
            "result": result,
        }

    def run(
        self,
        market_frames: Mapping[str, pd.DataFrame],
        calendar: Sequence,
        predict_date,
        *,
        etf_mapping: Mapping[str, Mapping] | None = None,
        live_flow: Mapping[str, float] | None = None,
        mode: str = "historical",
    ) -> dict:
        """完整流水线：因子 → 三周期训练/预测 → 融合 → ETF 候选。

        ``live_flow`` 仅在 ``config.flow_posthoc_enabled=True`` 时生效，
        且只在**推理阶段**对分数做受限修正，绝不写入训练。
        """
        if mode not in {"historical", "inference"}:
            raise ValueError("mode 必须为 historical 或 inference")
        if live_flow is not None and (mode != "inference" or not self.config.flow_posthoc_enabled):
            raise ValueError("live_flow 仅允许在显式启用的 inference 模式使用")
        cal = trading_calendar(calendar)
        timing = {
            p: signal_timing(cal.tolist(), predict_date, w)
            for p, w in self.config.forward_windows.items()
        }
        visible = {
            name: as_of_truncate(frame, predict_date) for name, frame in market_frames.items()
        }
        panel = self.build_panel(visible, calendar=cal[cal <= pd.Timestamp(predict_date)].tolist())
        results = {}
        for period in self.config.forward_windows:
            results[period] = self.run_period(period, panel, calendar, predict_date)

        # 资金流 post-hoc（仅推理期，默认关闭）
        flow_applied = False
        if self.config.flow_posthoc_enabled and live_flow:
            flow_applied = True
            for period, r in results.items():  # noqa: B007 -- Retain established loop identity for provenance review.
                if not r:
                    continue
                r["scores"] = {
                    s: apply_flow_adjustment(v, live_flow.get(s, 0.0))
                    for s, v in r["scores"].items()
                }
                r["ranking"] = rank_sectors(r["scores"])
                r["result"].scores = dict(r["scores"])
                r["result"].rankings = [
                    {"rank": i + 1, "sector": s, "score": round(v, 6)}
                    for i, (s, v) in enumerate(r["ranking"])
                ]

        fused = self.model.fuse_periods({p: r["result"] for p, r in results.items() if r})
        top = select_top(fused, self.config.top_n)
        weights = sector_scores_to_weights(top)

        etf_candidates = []
        if etf_mapping is not None:
            etf_candidates = build_etf_candidates(fused, etf_mapping, self.config.top_n)

        unavailable = [p for p, r in results.items() if not r or not r["scores"]]

        return {
            "predict_date": str(pd.Timestamp(predict_date).date()),
            "periods": results,
            "fused_ranking": fused,
            "top_sectors": top,
            "sector_weights": weights,
            "etf_candidates": etf_candidates,
            "flow_posthoc_applied": flow_applied,
            "macro_enabled": self.config.macro_enabled,
            "timing": timing,
            "status": "RANKING_READY" if fused else "NOT_READY",
            "unavailable_horizons": unavailable,
            "missing_mapping": [s for s, _ in top if etf_mapping is None or not etf_mapping.get(s)],
            "mapping_status": "requires_validation" if etf_mapping is not None else "not_provided",
            "target_definition": "absolute_close_to_close_forward_return",
            "rebalance_cadence": None,
            "holding_period": None,
            "risk_budget_status": "NOT_IMPLEMENTED",
        }

    # -- 风险（旁路，不修改 ranking） ---------------------------------------

    def evaluate_risk(
        self,
        market_frames: Mapping[str, pd.DataFrame],
        *,
        historical_cross_vols: list[float] | None = None,
        as_of=None,
    ) -> RiskState:
        """计算风险状态。**只返回状态，不触碰 ranking/权重。**"""
        return compute_risk_state(
            market_frames, historical_cross_vols=historical_cross_vols, as_of=as_of
        )
