"""backtesting runner 与 result 的离线测试。

不加载 Hikyuu、不访问网络：runner 用注入的假 framework 函数。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest

from src.backtesting import (
    RESULT_FILES,
    BacktestMetadata,
    BacktestMetrics,
    BacktestRequest,
    BacktestRequestError,
    BacktestResult,
    StrategySpec,
    UnknownFrameworkError,
    UnknownStrategyError,
    discover_strategies,
    now_run_id,
    register_framework,
    run_backtest,
)
from src.backtesting.testing.smoke_strategy import (
    EXECUTION_SMOKE_NAME,
    EXECUTION_SMOKE_RUN_TYPE,
)

# --- BacktestRequest 校验 -------------------------------------------------


def test_request_requires_dates():
    with pytest.raises(BacktestRequestError, match="start_date"):
        BacktestRequest(strategy="s", framework="f", start_date=None, end_date="2024-01-01")


def test_request_rejects_reversed_range():
    with pytest.raises(BacktestRequestError, match="早于"):
        BacktestRequest(strategy="s", framework="f", start_date="2024-06-01", end_date="2024-01-01")


def test_request_rejects_bad_date_format():
    with pytest.raises(BacktestRequestError, match="格式非法"):
        BacktestRequest(strategy="s", framework="f", start_date="not-a-date", end_date="2024-01-01")


def test_request_rejects_non_positive_cash():
    with pytest.raises(BacktestRequestError, match="initial_cash"):
        BacktestRequest(
            strategy="s",
            framework="f",
            start_date="2024-01-01",
            end_date="2024-02-01",
            initial_cash=0,
        )


def test_request_accepts_multiple_date_formats():
    for s, e in (("2024-01-01", "2024-02-01"), ("20240101", "20240201")):
        r = BacktestRequest(strategy="s", framework="f", start_date=s, end_date=e)
        assert r.start.year == 2024 and r.end.month == 2


def test_request_rejects_empty_strategy():
    with pytest.raises(BacktestRequestError, match="strategy"):
        BacktestRequest(strategy="", framework="f", start_date="2024-01-01", end_date="2024-02-01")


# --- run_backtest 错误边界 ------------------------------------------------


def _spec() -> dict[str, StrategySpec]:
    return {
        "demo": StrategySpec(
            name="demo", package="strategies.demo", path=Path("/nonexistent"), version="1.0"
        )
    }


def test_run_backtest_rejects_unknown_framework():
    req = BacktestRequest(
        strategy="demo", framework="nope", start_date="2024-01-01", end_date="2024-02-01"
    )
    with pytest.raises(UnknownFrameworkError, match="nope"):
        run_backtest(req, specs=_spec(), frameworks={"hikyuu": lambda r, s: None})


def test_run_backtest_rejects_unknown_strategy():
    req = BacktestRequest(
        strategy="ghost", framework="hikyuu", start_date="2024-01-01", end_date="2024-02-01"
    )
    with pytest.raises(UnknownStrategyError, match="ghost"):
        run_backtest(req, specs=_spec(), frameworks={"hikyuu": lambda r, s: None})


def test_run_backtest_dispatches_to_framework():
    captured = {}

    def fake_fw(req, spec):
        captured["req"] = req
        captured["spec"] = spec
        return "RESULT"

    req = BacktestRequest(
        strategy="demo", framework="hikyuu", start_date="2024-01-01", end_date="2024-02-01"
    )
    out = run_backtest(req, specs=_spec(), frameworks={"hikyuu": fake_fw})
    assert out == "RESULT"
    assert captured["spec"].name == "demo"


def test_register_and_available_frameworks():
    register_framework("dummy-fw", lambda r, s: None)
    from src.backtesting import available_frameworks

    assert "dummy-fw" in available_frameworks()


# --- 策略发现 -------------------------------------------------------------


def test_discover_strategies_finds_sw_sector_rotation():
    from scripts.quant import _load_strategy_entry

    specs = discover_strategies(entry_loader=_load_strategy_entry)
    assert "sw_sector_rotation" in specs
    sp = specs["sw_sector_rotation"]
    assert sp.package == "strategies.sw_sector_rotation"
    assert sp.entry is not None, "策略包应暴露 *Core 入口类"
    assert sp.config_file == "sw_sector_rotation.yaml"


def test_discover_strategies_ignores_non_packages(tmp_path):
    (tmp_path / "not_a_strategy").mkdir()
    (tmp_path / "not_a_strategy" / "README.md").write_text("x", encoding="utf-8")
    assert discover_strategies(tmp_path) == {}


def test_discover_strategies_missing_dir_returns_empty(tmp_path):
    assert discover_strategies(tmp_path / "nope") == {}


def test_strategy_spec_load_config_raises_on_missing_file(tmp_path):
    sp = StrategySpec(name="x", package="x", path=tmp_path, config_file="missing.yaml")
    with pytest.raises(BacktestRequestError, match="配置文件不存在"):
        sp.load_config()


def test_strategy_spec_load_config_reads_yaml(tmp_path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "c.yaml").write_text("alpha: 0.01\n", encoding="utf-8")
    sp = StrategySpec(name="x", package="x", path=tmp_path, config_file="c.yaml")
    assert sp.load_config()["alpha"] == 0.01


# --- BacktestResult 序列化 ------------------------------------------------


def _result() -> BacktestResult:
    meta = BacktestMetadata(
        strategy="demo",
        strategy_version="1.0",
        framework="hikyuu",
        framework_version="2.8.2",
        git_commit="abc1234",
        run_id="run-1",
        start_date="2024-01-01",
        end_date="2024-12-31",
        data_source="hikyuu:pytdx-hdf5",
        data_snapshot=None,
        initial_cash=100000.0,
        commission=None,
        slippage=None,
        status="LEVEL_A_SMOKE",
    )
    metrics = BacktestMetrics(
        initial_cash=100000.0,
        final_value=101000.0,
        total_return=0.01,
        annual_return=None,
        max_drawdown=-0.02,
        volatility=None,
        sharpe=None,
        trade_count=3,
        commission=None,
        slippage=None,
        execution_time=1.5,
    )
    return BacktestResult(
        metadata=meta,
        metrics=metrics,
        trades=pd.DataFrame(
            [
                {
                    "datetime": "2024-02-01",
                    "symbol": "X",
                    "business": "BUY",
                    "price": 10.0,
                    "number": 100.0,
                    "amount": 1000.0,
                    "cash": 0.0,
                    "cost": None,
                }
            ]
        ),
        positions=pd.DataFrame(columns=["datetime", "symbol", "number", "price"]),
        equity_curve=pd.DataFrame(
            [{"date": "2024-01-01", "equity": 100000.0}, {"date": "2024-12-31", "equity": 101000.0}]
        ),
        yearly_returns=pd.DataFrame(columns=["year", "return"]),
    )


def test_unsupported_fields_are_none_not_zero():
    """不支持的指标必须是 None，绝不用 0 冒充。"""
    m = BacktestMetrics()
    d = m.to_dict()
    assert d["sharpe"] is None
    assert d["slippage"] is None
    assert d["annual_return"] is None
    assert set(m.unsupported_fields) >= {"sharpe", "slippage", "annual_return", "volatility"}


def test_unsupported_serializes_to_json_null(tmp_path):
    res = _result()
    out = res.write(str(tmp_path))
    with open(os.path.join(out, "metrics.json"), encoding="utf-8") as f:
        data = json.load(f)
    assert data["sharpe"] is None
    assert data["slippage"] is None
    assert data["annual_return"] is None
    assert data["final_value"] == 101000.0


def test_write_creates_all_standard_files(tmp_path):
    res = _result()
    out = res.write(str(tmp_path))
    for name in RESULT_FILES:
        assert os.path.exists(os.path.join(out, name)), f"缺少输出文件 {name}"


def test_write_uses_strategy_and_run_id_path(tmp_path):
    res = _result()
    out = res.write(str(tmp_path))
    assert out.endswith(os.path.join("demo", "run-1"))


def test_report_marks_unsupported_explicitly():
    md = _result().render_report()
    assert "*unsupported*" in md
    assert "未用 0 冒充" in md


def test_report_states_limitations():
    res = _result()
    res.metadata.limitations = ("未建模涨跌停",)
    md = res.render_report()
    assert "未建模涨跌停" in md


def test_metadata_serializes_none_snapshot(tmp_path):
    res = _result()
    out = res.write(str(tmp_path))
    with open(os.path.join(out, "metadata.json"), encoding="utf-8") as f:
        d = json.load(f)
    assert d["data_snapshot"] is None
    assert d["limit_up_down_modeled"] is False


def test_now_run_id_format():
    rid = now_run_id("pre-")
    assert rid.startswith("pre-")
    assert len(rid) > 8


# --- execution_smoke 语义（本轮新增） ------------------------------------
#
# 背景：LEVEL A 跑的是「真实 Hikyuu 数据 + 真实 System + 真实 TradeManager
# + 极简 execution smoke 规则」，**不是 sw_sector_rotation**。它产生的收益/
# 回撤/Sharpe 不得被读成策略绩效。以下测试锁死这个语义，防止将来被改回。


def _smoke_result() -> BacktestResult:
    """一个 run_type=execution_smoke 的结果（strategy 刻意不叫 sw_sector_rotation）。"""
    res = _result()
    res.metadata.strategy = EXECUTION_SMOKE_NAME
    res.metadata.run_type = EXECUTION_SMOKE_RUN_TYPE
    return res


def test_default_run_type_is_strategy_backtest():
    """默认必须是 strategy_backtest（宁可被当成正式回测，也不默认伪装 smoke）。"""
    assert (
        BacktestMetadata(
            strategy="s",
            strategy_version="v",
            framework="f",
            framework_version="1",
            git_commit="c",
            run_id="r",
            start_date="2024-01-01",
            end_date="2024-01-02",
            data_source="d",
            data_snapshot=None,
            initial_cash=1.0,
            commission=None,
            slippage=None,
            status="ok",
        ).run_type
        == "strategy_backtest"
    )


def test_execution_smoke_does_not_use_strategy_name_dir(tmp_path):
    """smoke 运行不得写入 reports/backtests/<策略名>/ —— 那会被误读为策略绩效。"""
    res = _smoke_result()
    out = res.write(str(tmp_path))
    assert out.endswith(os.path.join("hikyuu_execution_smoke", "run-1"))
    assert "sw_sector_rotation" not in out


def test_execution_smoke_dir_differs_from_strategy_name():
    """即便 strategy 字段被误设为策略名，execution_smoke 仍不得占用该目录。"""
    m = _smoke_result().metadata
    m.strategy = "sw_sector_rotation"  # 人为误设
    assert m.output_dir_name == "hikyuu_execution_smoke"


def test_execution_smoke_report_has_explicit_non_strategy_banner():
    """report.md 必须显式声明这不是 sw_sector_rotation 策略回测。"""
    md = _smoke_result().render_report()
    assert "THIS IS NOT A SW_SECTOR_ROTATION STRATEGY BACKTEST" in md
    assert "execution_smoke" in md
    assert "不得用于评价" in md


def test_strategy_backtest_report_has_no_smoke_banner():
    """正式策略回测不应出现 smoke 警告（否则警告会失去意义）。"""
    assert "THIS IS NOT A SW_SECTOR_ROTATION" not in _result().render_report()


def test_metadata_json_records_run_type(tmp_path):
    out = _smoke_result().write(str(tmp_path))
    with open(os.path.join(out, "metadata.json"), encoding="utf-8") as f:
        d = json.load(f)
    assert d["run_type"] == "execution_smoke"
    assert d["strategy"] != "sw_sector_rotation"


def test_result_files_constant_matches_task_spec():
    assert set(RESULT_FILES) == {
        "metadata.json",
        "metrics.json",
        "trades.csv",
        "positions.csv",
        "equity_curve.csv",
        "yearly_returns.csv",
        "report.md",
    }
