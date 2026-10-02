"""RQAlpha 框架可用性 smoke test。

本测试只验证 RQAlpha 框架能否正常 import、配置解析、核心子系统可用。
**不下载 bundle、不跑完整回测、不做策略开发。**

当前项目尚未下载 RQAlpha bundle（~/.rqalpha/bundle 不存在），
因此依赖行情数据的断言会以 pytest.skip 标记为 RQALPHA_DATA_NOT_INITIALIZED，
而不是判定失败。
"""

import os

import pytest

pytestmark = pytest.mark.external_runtime

# 顶层 import：若失败则为框架级故障
rqalpha = pytest.importorskip("rqalpha", reason="rqalpha not importable")


def test_rqalpha_version():
    """RQAlpha 可 import 且版本可读。"""
    assert rqalpha.__version__ == "6.4.0"


def test_rqalpha_top_level_api_exists():
    """顶层运行入口存在（run / run_file / run_func）。"""
    for name in ("run", "run_file", "run_func"):
        assert hasattr(rqalpha, name), f"missing top-level API: {name}"
        assert callable(getattr(rqalpha, name))


def test_core_modules_importable():
    """核心子系统模块可 import。"""
    import rqalpha.const  # noqa: F401
    import rqalpha.core.events  # noqa: F401
    import rqalpha.interface  # noqa: F401
    import rqalpha.mod.rqalpha_mod_sys_accounts  # noqa: F401


def test_abstract_interfaces_exist():
    """框架抽象接口齐全（broker / datasource / position / mod 等）。"""
    import rqalpha.interface as iface

    for name in (
        "AbstractBroker",
        "AbstractDataSource",
        "AbstractEventSource",
        "AbstractMod",
        "AbstractPosition",
        "AbstractPriceBoard",
        "AbstractStrategyLoader",
        "AbstractTransactionCostDecider",
    ):
        assert hasattr(iface, name), f"missing interface: {name}"


def test_config_parser_available():
    """配置解析模块可用。"""
    from rqalpha.utils.config import parse_config  # noqa: F401

    assert callable(parse_config)


def test_strategy_loader_available():
    """策略加载器可用（框架的运行入口依赖它）。"""
    from rqalpha.core.strategy_loader import FileStrategyLoader  # noqa: F401

    assert FileStrategyLoader is not None


def test_event_bus_and_events():
    """事件总线与事件枚举可构造，确认事件驱动内核已加载。"""
    from rqalpha.core.events import EVENT, EventBus

    bus = EventBus()
    assert bus is not None
    assert len(list(EVENT)) > 0


def test_const_account_types():
    """常量模块可用，交易账户类型枚举可读。"""
    from rqalpha.const import DEFAULT_ACCOUNT_TYPE

    accounts = list(DEFAULT_ACCOUNT_TYPE)
    assert len(accounts) > 0
    assert any("STOCK" in str(a) for a in accounts)


def test_bundle_availability_is_reported():
    """报告 RQAlpha bundle 数据是否已下载。

    当前基线预期：~/.rqalpha/bundle 不存在。
    这不是框架故障，因此以 skip 标记，不判失败。
    """
    bundle_dir = os.path.expanduser("~/.rqalpha/bundle")
    if not os.path.isdir(bundle_dir):
        pytest.skip(
            "RQALPHA_DATA_NOT_INITIALIZED: RQAlpha bundle 尚未下载（~/.rqalpha/bundle 不存在）"
        )
    assert os.path.isdir(bundle_dir)
