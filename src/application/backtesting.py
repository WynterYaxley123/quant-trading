"""框架级回测编排层。

职责（严格限定）
----------------
- strategy discovery（发现可用策略与 framework 适配器）
- config loading（加载策略配置 YAML）
- framework selection（选择执行框架，当前仅 hikyuu）
- start/end validation（区间校验）
- 调用对应 framework runner
- 返回统一的 :class:`~src.backtesting.result.BacktestResult`
- 统一错误边界

**不包含**：Hikyuu 交易逻辑、策略因子、行业模型、RSRS、Ridge、
risk 逻辑。这些分别属于 hikyuu_runner / 策略包。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "BacktestRequest",
    "BacktestRequestError",
    "UnknownFrameworkError",
    "UnknownStrategyError",
    "StrategySpec",
    "discover_strategies",
    "register_framework",
    "available_frameworks",
    "run_backtest",
]

#: 项目根目录（src/application/backtesting.py → 上溯 3 层）
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_STRATEGIES_DIR = _PROJECT_ROOT / "strategies"

#: 已注册的执行框架：name → 可调用对象
#: 可调用对象签名 ``(request, spec) -> BacktestResult``
_FRAMEWORKS: dict[str, Callable[[Any, "StrategySpec"], Any]] = {}


# --- 异常 -----------------------------------------------------------------


class BacktestRequestError(ValueError):
    """请求参数非法（区间颠倒、缺少必填项等）。"""


class UnknownFrameworkError(ValueError):
    """请求了未注册的执行框架。"""

    def __init__(self, framework: str, available: list[str]) -> None:
        self.framework = framework
        self.available = available
        super().__init__(f"未知执行框架 {framework!r}，当前可用: {available}")


class UnknownStrategyError(ValueError):
    """请求了不存在的策略。"""

    def __init__(self, strategy: str, available: list[str]) -> None:
        self.strategy = strategy
        self.available = available
        super().__init__(f"未知策略 {strategy!r}，当前可用: {available}")


# --- 策略发现 -------------------------------------------------------------


@dataclass(frozen=True)
class StrategySpec:
    """一个策略的发现结果。

    ``requirements`` 由策略包自行声明（如 ``{"sector_data": True}``），
    runner 据此判断能否执行，**不猜测**策略需要什么数据。
    """

    name: str
    package: str
    path: Path
    #: 策略入口对象（通常是 Core 类），供 framework adapter 使用
    entry: Any = None
    #: 策略配置文件名（位于 ``<strategy>/config/``）
    config_file: str | None = None
    #: 版本标识
    version: str = "unknown"
    #: 数据需求声明
    requirements: Mapping[str, Any] = field(default_factory=dict)

    def load_config(self) -> dict:
        """加载策略配置 YAML，返回 dict（无配置时返回空 dict）。"""
        if not self.config_file:
            return {}
        path = self.path / "config" / self.config_file
        if not path.exists():
            raise BacktestRequestError(f"策略配置文件不存在: {path}")
        import yaml

        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}


def _read_version(strategy_dir: Path) -> str:
    """依次读取 ``VERSION``、``version.txt``；均不存在时返回 unknown。"""
    for cand in ("VERSION", "version.txt"):
        p = strategy_dir / cand
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return "unknown"


def discover_strategies(
    root: Path | None = None, *, entry_loader: Callable[[str], Any] | None = None
) -> dict[str, StrategySpec]:
    """扫描 ``strategies/`` 下的自包含策略包。

    一个目录被视为策略包的条件：含 ``__init__.py`` 且含 ``src/`` 子目录。
    不符合的目录（如只有 README）被跳过，**不报错**。
    默认只读取元数据，不导入策略；入口加载由调用方显式注入。
    """
    base = root or _STRATEGIES_DIR
    found: dict[str, StrategySpec] = {}
    if not base.is_dir():
        return found
    for d in sorted(base.iterdir()):
        if not d.is_dir() or d.name.startswith((".", "_")):
            continue
        if not (d / "__init__.py").exists() or not (d / "src").is_dir():
            continue
        pkg = f"strategies.{d.name}"
        entry = None
        if entry_loader is not None:
            try:
                entry = entry_loader(pkg)
            except Exception:  # noqa: BLE001 - 发现阶段不因单个策略失败而中断
                entry = None

        cfg_dir = d / "config"
        cfg_file = None
        if cfg_dir.is_dir():
            ys = sorted(cfg_dir.glob("*.yaml")) + sorted(cfg_dir.glob("*.yml"))
            # 排序后的 YAML 在 YML 前；优先排除 example，否则保留全部候选
            ys = [p for p in ys if "example" not in p.name] or ys
            if ys:
                cfg_file = ys[0].name

        req: dict[str, Any] = {}
        req_file = d / "data_requirements.yaml"
        if req_file.exists():
            import yaml

            req = yaml.safe_load(req_file.read_text(encoding="utf-8")) or {}

        found[d.name] = StrategySpec(
            name=d.name,
            package=pkg,
            path=d,
            entry=entry,
            config_file=cfg_file,
            version=_read_version(d),
            requirements=req,
        )
    return found


# --- 框架注册 -------------------------------------------------------------


def register_framework(name: str, fn: Callable[[Any, StrategySpec], Any]) -> None:
    """注册一个执行框架。``fn(request, spec) -> BacktestResult``。"""
    _FRAMEWORKS[name] = fn


def available_frameworks() -> list[str]:
    return sorted(_FRAMEWORKS)


# --- 请求 -----------------------------------------------------------------


def _coerce_date(v: Any, field_name: str) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return datetime.strptime(v.replace("-", "")[:8], "%Y%m%d").date()
        except ValueError as e:
            raise BacktestRequestError(
                f"{field_name} 日期格式非法: {v!r}（应为 YYYY-MM-DD 或 YYYYMMDD）"
            ) from e
    raise BacktestRequestError(f"{field_name} 类型不支持: {type(v).__name__}")


@dataclass
class BacktestRequest:
    """一次回测请求。"""

    strategy: str
    framework: str = "hikyuu"
    start_date: Any = None
    end_date: Any = None
    config: Mapping[str, Any] | None = None
    initial_cash: float = 100_000.0
    #: 输出根目录；None 表示不落盘
    output_root: str | None = None
    #: 额外框架参数（透传给具体 framework runner）
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.strategy:
            raise BacktestRequestError("strategy 不能为空")
        if not self.framework:
            raise BacktestRequestError("framework 不能为空")
        if self.start_date is None or self.end_date is None:
            raise BacktestRequestError("start_date 与 end_date 均为必填")
        self._start = _coerce_date(self.start_date, "start_date")
        self._end = _coerce_date(self.end_date, "end_date")
        if self._end < self._start:
            raise BacktestRequestError(f"end_date ({self._end}) 早于 start_date ({self._start})")
        if not (isinstance(self.initial_cash, (int, float)) and self.initial_cash > 0):
            raise BacktestRequestError(f"initial_cash 必须为正数，收到 {self.initial_cash!r}")

    @property
    def start(self) -> date:
        return self._start

    @property
    def end(self) -> date:
        return self._end


# --- 执行 -----------------------------------------------------------------


def run_backtest(
    request: BacktestRequest,
    *,
    specs: Mapping[str, StrategySpec] | None = None,
    frameworks: Mapping[str, Callable] | None = None,
) -> Any:
    """执行一次回测，返回 :class:`BacktestResult`。

    错误边界：
    - 未知框架 → :class:`UnknownFrameworkError`
    - 未知策略 → :class:`UnknownStrategyError`
    - 参数非法 → :class:`BacktestRequestError`

    :param specs: 覆盖策略发现结果（测试注入用）。
    :param frameworks: 覆盖框架注册表（测试注入用）。
    """
    fw_map = dict(frameworks) if frameworks is not None else dict(_FRAMEWORKS)
    if request.framework not in fw_map:
        raise UnknownFrameworkError(request.framework, sorted(fw_map))

    spec_map = dict(specs) if specs is not None else discover_strategies()
    if request.strategy not in spec_map:
        raise UnknownStrategyError(request.strategy, sorted(spec_map))

    spec = spec_map[request.strategy]
    fn = fw_map[request.framework]
    return fn(request, spec)
