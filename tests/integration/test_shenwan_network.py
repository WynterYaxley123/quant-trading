"""申万官方 HTTPS 的显式 opt-in 网络测试。"""

from __future__ import annotations

import os

import pytest
import requests

from src.data.providers.shenwan_official import STOCK_CLASSIFICATION_URL


pytestmark = [pytest.mark.integration, pytest.mark.network]


def test_shenwan_official_classification_download_uses_strict_tls():
    if os.environ.get("RUN_SHENWAN_NETWORK_TESTS") != "1":
        pytest.skip("set RUN_SHENWAN_NETWORK_TESTS=1 for strict Shenwan HTTPS probe")
    # 不传 verify=False，也不捕获 SSLError 为成功；服务端链恢复后才应通过。
    response = requests.get(STOCK_CLASSIFICATION_URL, timeout=30)
    response.raise_for_status()
    assert response.content
