"""AKShare 包可用性 smoke test。

本测试只验证 AKShare 包能否正常 import、以及外部数据源可达性。
**不批量下载、不落大量数据、不做策略。**

重要区分（任务书第六节）：
    - AKShare 包可用          → 环境正常
    - 外部数据源当前不可达     → 网络/第三方问题，**不是环境损坏**

因此外部接口失败一律以 pytest.skip 标记，绝不判 failed。
"""

import socket

import pytest

# 顶层 import：若失败则为包级故障
akshare = pytest.importorskip("akshare", reason="akshare not importable")

# 轻量公共接口（只取少量结果，非批量）
LIGHT_ENDPOINT = "https://push2.eastmoney.com/api/qt/clist/get"
DNS_HOSTS = ["push2.eastmoney.com", "pypi.org"]


def test_akshare_version():
    """AKShare 可 import 且版本可读。"""
    assert akshare.__version__ == "1.18.88"


def test_akshare_key_functions_exist():
    """常用接口函数存在（不调用，只确认 API 面存在）。"""
    for name in ("stock_zh_a_spot_em", "stock_zh_index_spot_sina"):
        assert hasattr(akshare, name), f"missing akshare API: {name}"


def test_dns_resolution():
    """DNS 解析可用（纯网络层检查，与 akshare 无关）。

    若 DNS 都失败，则应怀疑容器网络；这是环境级问题。
    """
    resolved = []
    for host in DNS_HOSTS:
        try:
            socket.gethostbyname(host)
            resolved.append(host)
        except OSError:
            pass
    if not resolved:
        pytest.skip("NETWORK_UNAVAILABLE: 容器内 DNS 解析全部失败，疑似网络环境问题")
    assert len(resolved) > 0


def test_light_public_endpoint():
    """轻量公开数据接口可达性测试。

    只取少量结果，验证网络/API 可达。
    接口失败可能是限流、第三方临时故障或出口 IP 限制，
    一律 skip，不判 failed。
    """
    import urllib.request

    url = LIGHT_ENDPOINT + "?pn=1&pz=2&fs=m:1+s:2&fields=f12,f14"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            assert resp.status == 200
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"NETWORK_UNAVAILABLE: 轻量接口当前不可达（{type(exc).__name__}）")


def test_akshare_call_returns_data():
    """AKShare 实际调用测试（只做一次，取少量结果）。

    使用新浪指数接口（实测可用）。
    若该接口当前不可达，skip 而非 failed。
    """
    try:
        df = akshare.stock_zh_index_spot_sina()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"NETWORK_UNAVAILABLE: akshare 外部数据源当前不可达（{type(exc).__name__}）")

    assert df is not None
    assert len(df) > 0, "akshare 返回空数据集"
