#!/usr/bin/env python
"""量化项目统一 CLI（最小实现）。

当前仅支持 ``backtest``，只接 ``hikyuu`` 框架。
**不追求功能完整**：runner 正确性优先于 CLI 的丰富度。

用法（容器内）::

    python scripts/quant.py backtest --strategy sw_sector_rotation --framework hikyuu \\
        --start 2020-01-01 --end 2024-12-31

    python scripts/quant.py strategies          # 列出发现的策略
    python scripts/quant.py frameworks          # 列出可用执行框架
"""

from __future__ import annotations

import argparse
import os
import sys

# 保证从项目根可 import src.*
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

DEFAULT_OUTPUT_ROOT = os.path.join(_ROOT, "reports", "backtests")


def _cmd_strategies(_args) -> int:
    from src.backtesting import discover_strategies

    specs = discover_strategies()
    if not specs:
        print("未发现任何策略包（strategies/<name>/ 需含 __init__.py 与 src/）")
        return 0
    for name, sp in sorted(specs.items()):
        req = f" requirements={dict(sp.requirements)}" if sp.requirements else ""
        print(f"{name}\n  package: {sp.package}\n  config:  {sp.config_file}\n  version: {sp.version}{req}")
    return 0


def _cmd_frameworks(_args) -> int:
    import src.backtesting  # noqa: F401  触发注册

    from src.backtesting import available_frameworks

    print("\n".join(available_frameworks()) or "(无)")
    return 0


def _cmd_backtest(args) -> int:
    from src.backtesting import (
        BacktestRequest,
        BacktestRequestError,
        UnknownFrameworkError,
        UnknownStrategyError,
        run_backtest,
    )

    try:
        req = BacktestRequest(
            strategy=args.strategy,
            framework=args.framework,
            start_date=args.start,
            end_date=args.end,
            initial_cash=args.initial_cash,
            output_root=args.output_root,
        )
    except BacktestRequestError as e:
        print(f"参数错误: {e}", file=sys.stderr)
        return 2

    try:
        res = run_backtest(req)
    except UnknownFrameworkError as e:
        print(f"框架错误: {e}", file=sys.stderr)
        return 2
    except UnknownStrategyError as e:
        print(f"策略错误: {e}", file=sys.stderr)
        return 2

    out = None
    if args.output_root:
        out = res.write(args.output_root)

    print(f"状态: {res.metadata.status}")
    print(f"框架: {res.metadata.framework} {res.metadata.framework_version}")
    print(f"标的: {', '.join(res.metadata.symbols)}")
    print(f"区间: {res.metadata.start_date} ~ {res.metadata.end_date}")
    print("-" * 40)
    for k, v in res.metrics.to_dict().items():
        print(f"  {k}: {'unsupported' if v is None else v}")
    if out:
        print("-" * 40)
        print(f"输出: {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="quant", description="量化项目 CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("strategies", help="列出发现的策略").set_defaults(func=_cmd_strategies)
    sub.add_parser("frameworks", help="列出可用执行框架").set_defaults(func=_cmd_frameworks)

    b = sub.add_parser("backtest", help="运行回测")
    b.add_argument("--strategy", required=True)
    b.add_argument("--framework", default="hikyuu")
    b.add_argument("--start", required=True, help="YYYY-MM-DD 或 YYYYMMDD")
    b.add_argument("--end", required=True)
    b.add_argument("--initial-cash", type=float, default=100_000.0)
    b.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    b.set_defaults(func=_cmd_backtest)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
