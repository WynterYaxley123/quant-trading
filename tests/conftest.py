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


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: 需要真实行情数据或 Hikyuu 数据目录的测试（默认不跑）",
    )


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    """Avoid importing frozen frameworks when the portable tier is selected.

    Marker deselection happens after import; these two directories load optional
    frameworks at collection time. They remain collected in the full suite.
    """
    if "not external_runtime" in config.getoption("markexpr"):  # noqa: SIM102 -- Preserve independently documented frozen validation branches.
        if collection_path in {_ROOT / "tests" / "framework", _ROOT / "tests" / "integration"}:
            return True
    return None


@pytest.fixture(autouse=True)
def isolated_legacy_replay(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Historical writer regressions use only pytest's isolated synthetic namespace."""
    if "external_runtime" not in request.keywords and "integration" not in request.keywords:
        monkeypatch.setenv("SWL2_LEGACY_SYNTHETIC_REPLAY_ROOT", str(tmp_path_factory.getbasetemp()))
