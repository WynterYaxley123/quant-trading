# tests/test_environment.py
"""
环境测试 —— 只验证依赖模块能否正常加载。

严禁在本文件中：
  - 获取真实行情做策略
  - 创建交易信号
  - 执行回测
  - 创建模拟交易
"""

import sys

import pytest


def test_python_version():
    """确认 Python 版本为 3.12.x

    为何是 3.12：hikyuu 2.7+ 要求 numpy>=2.0，而 rqalpha 6.4.0 在
    python<=3.11 下要求 numpy<2.0。升到 3.12 后 rqalpha 的约束变为
    numpy>=2.0，两库兼容。详见 docs/dependency_conflicts.md
    """
    assert sys.version_info[:2] == (3, 12), f"expected 3.12, got {sys.version}"


def test_import_numpy():
    import numpy

    assert numpy.__version__


def test_import_pandas():
    import pandas

    assert pandas.__version__


def test_import_matplotlib():
    import matplotlib

    assert matplotlib.__version__


def test_import_scipy():
    import scipy

    assert scipy.__version__


@pytest.mark.external_runtime
def test_import_akshare():
    import akshare

    assert akshare.__version__


@pytest.mark.external_runtime
def test_import_hikyuu():
    import hikyuu

    assert hikyuu.__version__ if hasattr(hikyuu, "__version__") else True


@pytest.mark.external_runtime
def test_import_rqalpha():
    import rqalpha

    assert rqalpha.__version__


def test_import_pytest():
    assert pytest.__version__


def test_pytest_available():
    """pytest 可在容器内运行"""
    assert True


@pytest.mark.parametrize(
    "modname",
    ["yaml", "requests", "dotenv", pytest.param("jupyter", marks=pytest.mark.external_runtime)],
)
def test_import_support_modules(modname):
    """辅助依赖可导入（jupyter 为命令，用 importlib 探测）"""
    if modname == "jupyter":
        import importlib.util

        spec = importlib.util.find_spec("jupyter_client")
        assert spec is not None, "jupyter_client 未安装"
    else:
        __import__(modname)
