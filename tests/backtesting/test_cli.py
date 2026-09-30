"""CLI 离线冒烟测试。

不运行真实回测：只验证参数解析、子命令分发与错误码，
以及 ``backtest`` 在未知策略/框架下的拒绝路径。
"""

from __future__ import annotations

import importlib.util
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_cli():
    path = os.path.join(_ROOT, "scripts", "quant.py")
    spec = importlib.util.spec_from_file_location("quant_cli", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cli():
    return _load_cli()


def test_parser_has_backtest_subcommand(cli):
    ap = cli.build_parser()
    args = ap.parse_args(
        ["backtest", "--strategy", "s", "--start", "2024-01-01", "--end", "2024-02-01"]
    )
    assert args.cmd == "backtest"
    assert args.framework == "hikyuu"  # 默认框架
    assert args.initial_cash == 100_000.0


def test_parser_requires_start_end(cli):
    ap = cli.build_parser()
    with pytest.raises(SystemExit):
        ap.parse_args(["backtest", "--strategy", "s"])


def test_parser_rejects_unknown_subcommand(cli):
    ap = cli.build_parser()
    with pytest.raises(SystemExit):
        ap.parse_args(["nope"])


def test_strategies_command_lists_package(cli, capsys):
    rc = cli.main(["strategies"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "sw_sector_rotation" in out


def test_frameworks_command_lists_hikyuu(cli, capsys):
    rc = cli.main(["frameworks"])
    assert rc == 0
    assert "hikyuu" in capsys.readouterr().out


def test_backtest_rejects_unknown_strategy_with_code_2(cli, capsys):
    rc = cli.main(
        ["backtest", "--strategy", "ghost", "--start", "2024-01-01", "--end", "2024-02-01"]
    )
    assert rc == 2
    assert "策略错误" in capsys.readouterr().err


def test_backtest_rejects_bad_date_with_code_2(cli, capsys):
    rc = cli.main(
        [
            "backtest", "--strategy", "sw_sector_rotation",
            "--start", "not-a-date", "--end", "2024-02-01",
        ]
    )
    assert rc == 2
    assert "参数错误" in capsys.readouterr().err


def test_backtest_rejects_reversed_range(cli, capsys):
    rc = cli.main(
        [
            "backtest", "--strategy", "sw_sector_rotation",
            "--start", "2024-06-01", "--end", "2024-01-01",
        ]
    )
    assert rc == 2
    assert "参数错误" in capsys.readouterr().err
