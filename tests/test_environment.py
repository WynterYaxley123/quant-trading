"""基础环境自检测试。

验证 Python 环境、依赖包可用性与项目结构完整性。
"""

import os
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_python_version():
    """Python 版本必须为 3.11+。"""
    assert sys.version_info >= (3, 11), f"Python too old: {sys.version}"


def test_python_is_64bit():
    """必须使用 64 位 Python。"""
    assert sys.maxsize > 2 ** 32, "Python is not 64-bit"


def test_pandas_importable():
    """pandas 可导入并可用。"""
    import pandas as pd

    assert pd is not None
    df = pd.DataFrame({"a": [1, 2, 3]})
    assert len(df) == 3
    assert hasattr(pd, "__version__")


def test_numpy_importable():
    """numpy 可导入并可用。"""
    import numpy as np

    assert np is not None
    arr = np.array([1.0, 2.0, 3.0])
    assert arr.sum() == pytest.approx(6.0)


def test_matplotlib_importable():
    """matplotlib 可导入（不弹窗）。"""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    assert plt is not None


def test_scipy_importable():
    """scipy 可导入。"""
    import scipy

    assert scipy is not None


def test_requests_importable():
    """requests 可导入。"""
    import requests

    assert requests is not None


def test_yaml_importable():
    """pyyaml 可导入。"""
    import yaml

    assert yaml is not None


def test_dotenv_importable():
    """python-dotenv 可导入。"""
    from dotenv import load_dotenv

    assert load_dotenv is not None


PROJECT_STRUCTURE = [
    "strategies",
    "factors",
    "risk",
    "backtests",
    "tests",
    "docs",
    "data",
    "logs",
    "secrets",
]


@pytest.mark.parametrize("dirname", PROJECT_STRUCTURE)
def test_project_structure_dirs(dirname):
    """项目必需目录必须存在。"""
    d = PROJECT_ROOT / dirname
    assert d.is_dir(), f"missing directory: {dirname}"


PROJECT_FILES = [
    "README.md",
    "AGENTS.md",
    "requirements.txt",
    ".gitignore",
    ".env.example",
]


@pytest.mark.parametrize("filename", PROJECT_FILES)
def test_project_structure_files(filename):
    """项目必需文件必须存在。"""
    f = PROJECT_ROOT / filename
    assert f.is_file(), f"missing file: {filename}"


def test_gitignore_covers_sensitive():
    """.gitignore 必须忽略敏感目录与文件。"""
    gi = PROJECT_ROOT / ".gitignore"
    text = gi.read_text(encoding="utf-8")
    required = [".venv/", ".env", "secrets/", "data/", "logs/", "__pycache__/"]
    for item in required:
        assert item in text, f".gitignore missing rule: {item}"


def test_env_example_has_no_secrets():
    """.env.example 中所有凭证项必须为空值。"""
    p = PROJECT_ROOT / ".env.example"
    text = p.read_text(encoding="utf-8")
    sensitive_keys = [
        "BROKER_ACCOUNT",
        "BROKER_PASSWORD",
        "API_TOKEN",
        "MYQUANT_TOKEN",
    ]
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in sensitive_keys:
            assert value.strip() == "", f"{key} must be empty in .env.example"


def test_no_real_env_committed():
    """真实 .env 不应存在于仓库（若存在则为本地文件，Git 必须忽略）。"""
    env = PROJECT_ROOT / ".env"
    if env.exists():
        gi = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert ".env" in gi, ".env exists but is not gitignored"
