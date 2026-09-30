"""项目级 pytest 配置。

为 ``tests/`` 下的框架级测试提供：

1. 把**项目根**加入 ``sys.path``，使 ``import src.*`` /
   ``import strategies.*`` 在容器内（``/workspace``）与 WSL 下都能工作。
2. 注册 ``integration`` marker。

**离线约束**：本目录下的测试默认不得联网、不得重新导入行情、
不得修改 ``data/hikyuu`` 下的 HDF5 / stock.db。
需要真实行情的测试必须标记 ``@pytest.mark.integration``。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 本文件位于 <root>/tests/conftest.py → parents[1] = 项目根
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: 需要真实行情数据或 Hikyuu 数据目录的测试（默认不跑）",
    )
