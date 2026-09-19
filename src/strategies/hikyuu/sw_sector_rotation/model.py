"""横截面 Ridge 行业排名模型。

迁移来源
--------
Legacy china-market-data v5 ``scripts/quant/predict.py::run_prediction``
的三周期独立训练结构，与 ``cost_config.py`` 的初始超参。

Ridge 依赖说明（重要）
-----------------------
当前 Docker 稳定环境中**不存在** ``scikit-learn``
（已验证：``import sklearn`` → ModuleNotFoundError）。
按迁移约束，**禁止 pip install**，因此本模块提供 :class:`NumPyRidge`，
作为对 ``sklearn.linear_model.Ridge`` 的兼容实现：

- 目标函数 ``||X w + b - y||^2 + alpha * ||w||^2``
- **intercept（截距）不做 L2 惩罚**（与 sklearn 默认一致）
- 通过 ``X`` 增广一列常数实现，但用 mask 将该列排除出惩罚项
- 提供 ``fit`` / ``predict`` / ``coef_`` / ``intercept_``，API 与 sklearn 对齐

未来若环境中出现 sklearn，可无缝替换（二者数值一致，见单元测试）。

三周期结构
----------
=========  ==================
周期        预测交易日数
=========  ==================
short      10
medium     40
long       120
=========  ==================

每个周期**独立训练一个 Ridge**。训练样本为「全部行业 × 滚动窗口内日期」
堆叠；标签为该周期未来相对收益。

初始超参为 **LEGACY INITIAL DEFAULT**，不得标记为最终最优：
``ridge_alpha = 0.01``、``train_months = 6``、``top_n = 5``。
三周期融合参考权重 ``short 0.25 / medium 0.50 / long 0.25`` 同样是初始默认。

本模块是纯函数 + 纯 numpy/pandas，无 I/O。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

__all__ = [
    "FORWARD_WINDOWS",
    "FUSION_WEIGHTS",
    "DEFAULT_ALPHA",
    "DEFAULT_TRAIN_MONTHS",
    "DEFAULT_TOP_N",
    "MIN_TRAIN_DATES",
    "NumPyRidge",
    "CrossSectionalRidgeModel",
    "RankingResult",
]

#: 三周期 → 预测交易日数。
FORWARD_WINDOWS = {"short": 10, "medium": 40, "long": 120}

#: 三周期融合参考权重（LEGACY INITIAL DEFAULT，非最终最优）。
FUSION_WEIGHTS = {"short": 0.25, "medium": 0.50, "long": 0.25}

#: 初始超参（LEGACY INITIAL DEFAULT）。
DEFAULT_ALPHA = 0.01
DEFAULT_TRAIN_MONTHS = 6
DEFAULT_TOP_N = 5

#: 至少多少个有效训练日期才允许训练（legacy 门槛）。
MIN_TRAIN_DATES = 30


class NumPyRidge:
    """对 ``sklearn.linear_model.Ridge`` 的 NumPy 兼容实现。

    ``intercept`` 不做 L2 惩罚。求解闭式解：
    ``w = (X_c^T X_c + alpha * I_pen)^-1 X_c^T y_c``，
    其中 ``X_c = X - mean(X)``、``y_c = y - mean(y)``，
    ``I_pen`` 为单位阵（不含截距，因截距已通过中心化消去）。

    参数
    ----
    alpha:
        L2 正则化强度，默认 0.01。
    fit_intercept:
        是否拟合截距，默认 True。
    """

    def __init__(self, alpha: float = DEFAULT_ALPHA, fit_intercept: bool = True):
        if alpha < 0:
            raise ValueError(f"alpha 必须 >= 0, 收到 {alpha}")
        self.alpha = float(alpha)
        self.fit_intercept = bool(fit_intercept)
        self.coef_: np.ndarray | None = None
        self.intercept_: float = 0.0
        self.n_features_in_: int | None = None

    def fit(self, X, y) -> "NumPyRidge":
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float).ravel()
        if X.ndim != 2:
            raise ValueError(f"X 必须是二维数组, 收到 shape={X.shape}")
        if X.shape[0] != y.shape[0]:
            raise ValueError(
                f"X 与 y 样本数不一致: {X.shape[0]} vs {y.shape[0]}"
            )
        n_samples, n_features = X.shape
        self.n_features_in_ = n_features

        if self.fit_intercept:
            X_mean = X.mean(axis=0)
            y_mean = y.mean()
            Xc = X - X_mean
            yc = y - y_mean
        else:
            X_mean = np.zeros(n_features)
            y_mean = 0.0
            Xc = X
            yc = y

        if self.alpha > 0:
            gram = Xc.T @ Xc + self.alpha * np.eye(n_features)
        else:
            gram = Xc.T @ Xc
        rhs = Xc.T @ yc
        try:
            coef = np.linalg.solve(gram, rhs)
        except np.linalg.LinAlgError:
            # 退化时退到最小二乘伪逆，保证 predict 仍可用
            coef = np.linalg.pinv(gram) @ rhs

        self.coef_ = coef
        self.intercept_ = float(y_mean - X_mean @ coef) if self.fit_intercept else 0.0
        return self

    def predict(self, X) -> np.ndarray:
        if self.coef_ is None:
            raise RuntimeError("NumPyRidge 尚未 fit")
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        if X.shape[1] != self.n_features_in_:
            raise ValueError(
                f"特征数不匹配: 模型期望 {self.n_features_in_}, 收到 {X.shape[1]}"
            )
        return X @ self.coef_ + self.intercept_

    def get_params(self) -> dict:
        return {"alpha": self.alpha, "fit_intercept": self.fit_intercept}


@dataclass
class RankingResult:
    """单个周期的排名结果。"""

    period: str
    forward_days: int
    predict_date: pd.Timestamp
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    n_train_dates: int
    n_train_samples: int
    scores: dict = field(default_factory=dict)
    rankings: list = field(default_factory=list)
    model: NumPyRidge | None = None
    feature_names: list = field(default_factory=list)
    non_zero_coefs: int = 0


class CrossSectionalRidgeModel:
    """横截面 Ridge 行业排名模型（三周期）。

    用法
    ----
    1. 用 :meth:`fit_period` 对每个周期训练一个 Ridge；
    2. 用 :meth:`predict_period` 得到该周期全部行业的分数与排名；
    3. 用 :meth:`fuse_periods`（可选）融合三周期。

    训练数据组织
    ------------
    ``panel`` 为 ``{sector: DataFrame}``，每个 DataFrame 含特征列、
    目标列 ``fwd{window}``，index 为日期。模型把所有行业、所有落在
    ``train_dates`` 的 (日期, 行业) 样本**堆叠**成一个矩阵。
    """

    def __init__(
        self,
        alpha: float = DEFAULT_ALPHA,
        train_months: int = DEFAULT_TRAIN_MONTHS,
        top_n: int = DEFAULT_TOP_N,
        forward_windows: dict | None = None,
        fusion_weights: dict | None = None,
    ):
        self.alpha = float(alpha)
        self.train_months = int(train_months)
        self.top_n = int(top_n)
        self.forward_windows = dict(forward_windows or FORWARD_WINDOWS)
        self.fusion_weights = dict(fusion_weights or FUSION_WEIGHTS)
        self.models: dict[str, NumPyRidge] = {}

    # -- 训练 ---------------------------------------------------------------

    def fit_period(
        self,
        period: str,
        panel: dict[str, pd.DataFrame],
        feature_names: list[str],
        train_dates: list[pd.Timestamp],
        label_col: str | None = None,
    ) -> NumPyRidge | None:
        """训练一个周期的 Ridge。

        ``train_dates`` 必须已经是**forward label 完全实现**的日期
        （由 :mod:`src.common.temporal_integrity` 计算）。
        有效训练日期 < :data:`MIN_TRAIN_DATES` 时返回 ``None``（不训练）。
        """
        if period not in self.forward_windows:
            raise KeyError(f"未知周期: {period}")
        if len(train_dates) < MIN_TRAIN_DATES:
            return None

        label_col = label_col or f"fwd{self.forward_windows[period]}"
        dates = set(pd.Timestamp(d) for d in train_dates)

        xs, ys = [], []
        for frame in panel.values():
            if label_col not in frame.columns:
                continue
            sel = frame.loc[frame.index.isin(dates)]
            sel = sel.dropna(subset=list(feature_names) + [label_col])
            if sel.empty:
                continue
            xs.append(sel[list(feature_names)].to_numpy(dtype=float))
            ys.append(sel[label_col].to_numpy(dtype=float))

        if not xs:
            return None
        X = np.vstack(xs)
        y = np.concatenate(ys)
        if len(y) < MIN_TRAIN_DATES:
            return None

        model = NumPyRidge(alpha=self.alpha).fit(X, y)
        self.models[period] = model
        return model

    # -- 推理 ---------------------------------------------------------------

    def predict_period(
        self,
        period: str,
        panel: dict[str, pd.DataFrame],
        feature_names: list[str],
        predict_date: pd.Timestamp,
    ) -> RankingResult:
        """对 ``predict_date`` 当日的全部行业打分并排名。

        只使用 ``<= predict_date`` 的最新一行；允许该行标签为空
        （推理不需要已实现标签）。特征不全的行业被跳过。
        """
        if period not in self.models:
            raise RuntimeError(f"周期 {period} 尚未训练")
        model = self.models[period]
        predict_date = pd.Timestamp(predict_date)

        scores: dict[str, float] = {}
        for name, frame in panel.items():
            rows = frame.loc[frame.index <= predict_date]
            if rows.empty:
                continue
            row = rows.iloc[-1]
            values = row[list(feature_names)]
            if values.isna().any():
                continue
            scores[name] = float(model.predict(values.to_numpy(dtype=float).reshape(1, -1))[0])

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        coef = model.coef_ if model.coef_ is not None else np.array([])
        return RankingResult(
            period=period,
            forward_days=self.forward_windows[period],
            predict_date=predict_date,
            train_start=None,
            train_end=None,
            n_train_dates=0,
            n_train_samples=0,
            scores=scores,
            rankings=[
                {"rank": i + 1, "sector": s, "score": round(v, 6)}
                for i, (s, v) in enumerate(ranked)
            ],
            model=model,
            feature_names=list(feature_names),
            non_zero_coefs=int((np.abs(coef) > 1e-6).sum()) if coef.size else 0,
        )

    # -- 融合 ---------------------------------------------------------------

    def fuse_periods(self, results: dict[str, RankingResult]) -> list[tuple[str, float]]:
        """按 :attr:`fusion_weights` 融合多周期分数。

        先对每个周期的分数做横截面 z-score（避免不同周期量纲不同），
        再按权重加权平均。返回按融合分数降序的 ``[(sector, score), ...]``。
        只使用各周期都存在的行业。
        """
        available = {p: r for p, r in results.items() if r is not None and r.scores}
        if not available:
            return []

        common = None
        for r in available.values():
            keys = set(r.scores)
            common = keys if common is None else (common & keys)
        if not common:
            return []

        fused: dict[str, float] = {s: 0.0 for s in common}
        total_w = 0.0
        for period, r in available.items():
            w = float(self.fusion_weights.get(period, 0.0))
            if w <= 0:
                continue
            vals = np.array([r.scores[s] for s in common], dtype=float)
            std = vals.std()
            if std > 1e-12:
                z = (vals - vals.mean()) / std
            else:
                z = np.zeros_like(vals)
            for s, zi in zip(common, z):
                fused[s] += w * float(zi)
            total_w += w
        if total_w <= 0:
            return []
        fused = {s: v / total_w for s, v in fused.items()}
        return sorted(fused.items(), key=lambda kv: kv[1], reverse=True)

    def top_n_sectors(self, ranked: list[tuple[str, float]]) -> list[tuple[str, float]]:
        """取前 N 个行业。"""
        return ranked[: self.top_n]
