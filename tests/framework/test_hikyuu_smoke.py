"""Hikyuu 框架可用性 smoke test。

本测试只验证框架本身能否正常 import 与构造核心对象。
**不下载行情、不跑回测、不做策略开发。**

当前项目尚未初始化 Hikyuu 行情数据库（data/ 为空），
因此涉及数据访问的断言会以 pytest.skip 标记为 DATA_NOT_INITIALIZED，
而不是判定失败。
"""

import pytest

# 顶层 import：若失败则为框架级故障
hikyuu = pytest.importorskip("hikyuu", reason="hikyuu not importable")


def test_hikyuu_version():
    """Hikyuu 可 import 且版本可读。"""
    assert hikyuu.__version__ == "2.8.2"


def test_hikyuu_core_classes_exist():
    """核心类在顶层命名空间中可访问。"""
    for name in (
        "StockManager",
        "Stock",
        "Query",
        "Indicator",
        "TradeManager",
        "System",
        "KData",
        "Block",
        "Datetime",
    ):
        assert hasattr(hikyuu, name), f"missing core class: {name}"


def test_stock_manager_singleton():
    """StockManager 单例可正常构造与访问。"""
    sm = hikyuu.StockManager.instance()
    assert sm is not None
    # 重复获取应为同一实例
    assert hikyuu.StockManager.instance() is sm


def test_stock_manager_basic_api():
    """StockManager 基础查询 API 可调用（无数据时返回空集合，不抛异常）。"""
    sm = hikyuu.StockManager.instance()
    block_list = sm.get_block_list()
    assert isinstance(block_list, (list, tuple))


def test_indicator_module_accessible():
    """Indicator 基础模块可调用 —— 用无数据依赖的指标构造验证。

    实测该版本 API：
      - Indicator()            无参构造，OK
      - MA(n) / CLOSE()        返回 Indicator 实例，OK
      - Indicator(1.0)         不支持（只接受空参或 IndicatorImp）
    """
    empty = hikyuu.Indicator()
    assert empty is not None

    ma = hikyuu.MA(10)
    assert ma is not None

    close = hikyuu.CLOSE()
    assert close is not None


def test_indicator_to_stoploss_chain():
    """指标 → 止损策略链路可构造。

    ST_Indicator 实测为工厂函数：
        ST_Indicator(ind: Indicator) -> StoplossBase
    用无数据依赖的 MA(10) 作输入，验证指标子系统与止损子系统均已加载。
    """
    assert hasattr(hikyuu, "ST_Indicator")
    ma10 = hikyuu.MA(10)
    st = hikyuu.ST_Indicator(ma10)
    assert st is not None


def test_query_object_constructible():
    """Query 对象可构造（数据访问的入口对象）。"""
    q = hikyuu.Query(-1)
    assert q is not None


def test_data_availability_is_reported():
    """报告行情数据是否已初始化。

    当前基线预期：data/ 为空，Hikyuu 尚未加载行情。
    这不是框架故障，因此以 skip 标记，不判失败。
    """
    sm = hikyuu.StockManager.instance()
    block_list = sm.get_block_list()
    if len(block_list) == 0:
        pytest.skip("DATA_NOT_INITIALIZED: Hikyuu 行情数据库尚未建立（data/ 为空）")
    assert len(block_list) > 0
