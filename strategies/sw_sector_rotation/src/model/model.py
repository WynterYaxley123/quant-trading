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
- 中心化后用增广最小二乘求解；不构造正规方程，不做特征标准化
- 提供 ``fit`` / ``predict`` / ``coef_`` / ``intercept_``，API 与 sklearn 对齐

保留上述有限接口与目标函数，不宣称兼容 sklearn 全部行为。

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
堆叠；标签为该周期未来绝对 close-to-close 收益，再按预测值排序。

初始超参为 **LEGACY INITIAL DEFAULT**，不得标记为最终最优：
``ridge_alpha = 0.01``、``train_months = 6``、``top_n = 5``。
三周期融合参考权重 ``short 0.25 / medium 0.50 / long 0.25`` 同样是初始默认。

本模块是纯函数 + 纯 numpy/pandas，无 I/O。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import warnings

import numpy as np
import pandas as pd

from ..common.temporal_integrity import validate_train_features

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

    ``intercept`` 不做 L2 惩罚。中心化后求解
    ``[X_c; sqrt(alpha) I] w ≈ [y_c; 0]``，与原 Ridge 目标相同。
    使用 lstsq 避免正规方程放大条件数；alpha=0 时取最小范数解。

    参数
    ----
    alpha:
        L2 正则化强度，默认 0.01。
    fit_intercept:
        是否拟合截距，默认 True。
    """

    def __init__(self, alpha: float = DEFAULT_ALPHA, fit_intercept: bool = True):
        if not np.isfinite(alpha) or alpha < 0:
            raise ValueError(f"alpha 必须 >= 0, 收到 {alpha}")
        self.alpha = float(alpha)
        self.fit_intercept = bool(fit_intercept)
        self.coef_: np.ndarray | None = None
        self.intercept_: float = 0.0
        self.n_features_in_: int | None = None

    def fit(self, X, y) -> "NumPyRidge":
        # 失败的重新训练不可留下上一窗口的模型。
        self.coef_, self.intercept_, self.n_features_in_ = None, 0.0, None
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        if X.ndim != 2:
            raise ValueError(f"X 必须是二维数组, 收到 shape={X.shape}")
        if y.ndim != 1 or not X.shape[0] or not X.shape[1]:
            raise ValueError("X 必须非空，y 必须为一维")
        if not np.isfinite(X).all() or not np.isfinite(y).all():
            raise ValueError("Ridge 输入含 NaN/Inf")
        if X.shape[0] != y.shape[0]:
            raise ValueError(
                f"X 与 y 样本数不一致: {X.shape[0]} vs {y.shape[0]}"
            )
        n_features = X.shape[1]
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                X_mean = X.mean(axis=0) if self.fit_intercept else np.zeros(n_features)
                y_mean = y.mean() if self.fit_intercept else 0.0
                Xc, yc = X - X_mean, y - y_mean
                # 同一 Ridge 目标的增广最小二乘；避免 X.T @ X 平方条件数。
                # 无 feature scaling，截距仅中心化且不受 L2 惩罚。
                A, b = Xc, yc
                if self.alpha > 0:
                    A = np.vstack((Xc, np.sqrt(self.alpha) * np.eye(n_features)))
                    b = np.concatenate((yc, np.zeros(n_features)))
                coef, _, rank, _ = np.linalg.lstsq(A, b, rcond=None)
                if self.alpha > 0 and rank < n_features:
                    raise ValueError("Ridge 数值秩不足；特征尺度超出可靠求解范围")
                intercept = float(y_mean - X_mean @ coef)
                fitted = X @ coef + intercept
                if not np.isfinite(coef).all() or not np.isfinite(intercept) or not np.isfinite(fitted).all():
                    raise ValueError("Ridge 求解产生非有限结果")
        except (FloatingPointError, np.linalg.LinAlgError) as exc:
            raise ValueError("Ridge 数值求解失败") from exc
        self.coef_ = coef
        self.intercept_ = intercept
        self.n_features_in_ = n_features
        return self

    def predict(self, X) -> np.ndarray:
        if self.coef_ is None:
            raise RuntimeError("NumPyRidge 尚未 fit")
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        if X.ndim != 2 or not np.isfinite(X).all():
            raise ValueError("Ridge predict 需要有限二维数据")
        if X.shape[1] != self.n_features_in_:
            raise ValueError(
                f"特征数不匹配: 模型期望 {self.n_features_in_}, 收到 {X.shape[1]}"
            )
        with np.errstate(over="raise", invalid="raise"):
            result = X @ self.coef_ + self.intercept_
        if not np.isfinite(result).all():
            raise ValueError("Ridge predict 产生非有限结果")
        return result

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
    coverage: dict = field(default_factory=dict)
    excluded_sectors: dict = field(default_factory=dict)


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
        min_train_dates: int = MIN_TRAIN_DATES,
    ):
        self.alpha = float(alpha)
        self.train_months = int(train_months)
        self.top_n = int(top_n)
        self.forward_windows = dict(forward_windows or FORWARD_WINDOWS)
        self.fusion_weights = dict(fusion_weights or FUSION_WEIGHTS)
        self.models: dict[str, NumPyRidge] = {}
        self.min_train_dates = int(min_train_dates)
        if self.min_train_dates < 1:
            raise ValueError("min_train_dates 必须为正整数")
        if set(self.fusion_weights) != set(self.forward_windows):
            raise ValueError("fusion_weights 必须与 horizon 名称完全一致")
        weights = np.asarray(list(self.fusion_weights.values()), dtype=float)
        if not np.isfinite(weights).all() or (weights <= 0).any():
            raise ValueError("fusion_weights 必须为有限正数")
        self.feature_schemas: dict[str, tuple[str, ...]] = {}
        self.training_coverage: dict[str, dict] = {}

    @staticmethod
    def _validate_schema(feature_names, panel):
        if not feature_names or len(set(feature_names)) != len(feature_names):
            raise ValueError("feature schema 必须非空且无重复")
        validate_train_features(feature_names)
        if any(n.startswith("fwd") or n in {"sector", "sector_code", "symbol", "date"} for n in feature_names):
            raise ValueError("feature schema 不得包含 label 或行业标识")
        for name, frame in panel.items():
            if (not isinstance(frame.index, pd.DatetimeIndex) or frame.index.has_duplicates
                    or frame.index.hasnans or not frame.index.is_monotonic_increasing or frame.columns.has_duplicates):
                raise ValueError(f"{name}: panel index/columns 不合法")
            missing = set(feature_names) - set(frame.columns)
            if missing:
                raise ValueError(f"{name}: 缺少 feature columns {sorted(missing)}")

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
        （由 :mod:`strategies.sw_sector_rotation.src.common.temporal_integrity` 计算）。
        有效训练日期 < :data:`MIN_TRAIN_DATES` 时返回 ``None``（不训练）。
        """
        if period not in self.forward_windows:
            raise KeyError(f"未知周期: {period}")
        self.models.pop(period, None)
        self.feature_schemas.pop(period, None)
        self.training_coverage.pop(period, None)
        self._validate_schema(feature_names, panel)
        train_dates = sorted(set(pd.Timestamp(d) for d in train_dates))
        if len(train_dates) < self.min_train_dates:
            return None

        label_col = label_col or f"fwd{self.forward_windows[period]}"
        dates = set(pd.Timestamp(d) for d in train_dates)

        xs, ys = [], []
        counts_by_date, counts_by_sector, dropped = {}, {}, {}
        for name, frame in sorted(panel.items()):
            if label_col not in frame.columns:
                raise ValueError(f"{name}: 缺少 label column {label_col}")
            sel = frame.loc[frame.index.isin(dates)]
            if np.isinf(sel[list(feature_names) + [label_col]].to_numpy(dtype=float)).any():
                raise ValueError(f"{name}: training data 含 Inf")
            before = len(sel)
            sel = sel.dropna(subset=list(feature_names) + [label_col])
            dropped[name] = before - len(sel)
            counts_by_sector[name] = len(sel)
            for d in sel.index:
                counts_by_date[str(d.date())] = counts_by_date.get(str(d.date()), 0) + 1
            if sel.empty:
                continue
            xs.append(sel[list(feature_names)].to_numpy(dtype=float))
            ys.append(sel[label_col].to_numpy(dtype=float))

        coverage = {
            "samples_by_date": counts_by_date, "samples_by_sector": counts_by_sector,
            "dropped_nan_rows": dropped, "n_train_dates": len(counts_by_date),
            "n_train_samples": sum(counts_by_sector.values()),
            "weighting": "one_weight_per_date_sector_sample",
        }
        self.training_coverage[period] = coverage
        if any(n != len(panel) for n in counts_by_date.values()):
            warnings.warn("sector coverage 不一致；保留逐样本权重，详见 training_coverage", RuntimeWarning, stacklevel=2)
        if not xs or len(counts_by_date) < self.min_train_dates:
            return None
        X = np.vstack(xs)
        y = np.concatenate(ys)
        model = NumPyRidge(alpha=self.alpha).fit(X, y)
        self.models[period] = model
        self.feature_schemas[period] = tuple(feature_names)
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

        只使用 predict_date 当日特征；无当日数据/预热不足的行业明确记录。
        标签不参与推理。列名和顺序必须与训练契约完全相同。
        """
        if period not in self.models:
            raise RuntimeError(f"周期 {period} 尚未训练")
        model = self.models[period]
        if tuple(feature_names) != self.feature_schemas[period]:
            raise ValueError("feature schema/order 与训练不一致")
        self._validate_schema(feature_names, panel)
        predict_date = pd.Timestamp(predict_date)

        scores: dict[str, float] = {}
        excluded = {
            name: "missing_sector"
            for name in self.training_coverage[period]["samples_by_sector"]
            if name not in panel
        }
        for name, frame in sorted(panel.items()):
            if predict_date not in frame.index:
                excluded[name] = "missing_signal_date"
                continue
            row = frame.loc[predict_date]
            values = row[list(feature_names)]
            if np.isinf(values.to_numpy(dtype=float)).any():
                raise ValueError(f"{name}: prediction features 含 Inf")
            if values.isna().any():
                excluded[name] = "incomplete_features"
                continue
            scores[name] = float(model.predict(values.to_numpy(dtype=float).reshape(1, -1))[0])

        if excluded:
            warnings.warn(f"推理排除行业: {excluded}", RuntimeWarning, stacklevel=2)
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        coef = model.coef_ if model.coef_ is not None else np.array([])
        return RankingResult(
            period=period,
            forward_days=self.forward_windows[period],
            predict_date=predict_date,
            train_start=None,
            train_end=None,
            n_train_dates=self.training_coverage[period]["n_train_dates"],
            n_train_samples=self.training_coverage[period]["n_train_samples"],
            scores=scores,
            rankings=[
                {"rank": i + 1, "sector": s, "score": round(v, 6)}
                for i, (s, v) in enumerate(ranked)
            ],
            model=model,
            feature_names=list(feature_names),
            non_zero_coefs=int((np.abs(coef) > 1e-6).sum()) if coef.size else 0,
            coverage=self.training_coverage[period],
            excluded_sectors=excluded,
        )

    # -- 融合 ---------------------------------------------------------------

    def fuse_periods(self, results: dict[str, RankingResult]) -> list[tuple[str, float]]:
        """按 :attr:`fusion_weights` 融合多周期分数。

        先对每个周期的分数做横截面 z-score（避免不同周期量纲不同），
        再按权重加权平均。返回按融合分数降序的 ``[(sector, score), ...]``。
        只使用各周期都存在的行业。
        """
        missing = [p for p in self.forward_windows if p not in results or results[p] is None or not results[p].scores]
        if missing:
            warnings.warn(f"horizon unavailable: {missing}; 不生成融合排名", RuntimeWarning, stacklevel=2)
            return []
        available = {p: results[p] for p in self.forward_windows}
        if len({r.predict_date for r in available.values()}) != 1:
            raise ValueError("horizon prediction dates 不一致")
        for period, r in available.items():
            if r.period != period or r.forward_days != self.forward_windows[period]:
                raise ValueError("horizon result 身份不一致")
            if not np.isfinite(list(r.scores.values())).all():
                raise ValueError("horizon score 含 NaN/Inf")

        common = None
        for r in available.values():
            keys = set(r.scores)
            common = keys if common is None else (common & keys)
        if not common:
            warnings.warn("horizon 无共同可用行业", RuntimeWarning, stacklevel=2)
            return []
        common = sorted(common)
        if any(set(r.scores) != set(common) for r in available.values()):
            warnings.warn("horizon sector coverage 不一致，融合仅取交集", RuntimeWarning, stacklevel=2)

        fused: dict[str, float] = {s: 0.0 for s in common}
        total_w = 0.0
        for period, r in available.items():
            w = float(self.fusion_weights.get(period, 0.0))
            if w <= 0:
                continue
            vals = np.array([r.scores[s] for s in common], dtype=float)
            # z-score 对正比例缩放不变，先缩放可避免有限极值溢出。
            magnitude = max(float(np.max(np.abs(vals))), 1.0)
            vals = vals / magnitude
            std = vals.std()
            if std > 1e-12 / magnitude:
                z = (vals - vals.mean()) / std
            else:
                z = np.zeros_like(vals)
            for s, zi in zip(common, z):
                fused[s] += w * float(zi)
            total_w += w
        if total_w <= 0:
            return []
        fused = {s: v / total_w for s, v in fused.items()}
        return sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))

    def top_n_sectors(self, ranked: list[tuple[str, float]]) -> list[tuple[str, float]]:
        """取前 N 个行业。"""
        return ranked[: self.top_n]
