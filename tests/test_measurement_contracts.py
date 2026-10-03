"""Adversarial metric-definition tests independent of repository totals."""

import ast
import json
from pathlib import Path

from scripts.engineering.inventory import MACHINE_PATH, measure
from scripts.engineering.prints import callsites, classify
from scripts.engineering.references import audit
from strategies.etf_quant.config.runtime_paths import evidence_root, runtime_root
from strategies.etf_quant.evidence._validation import parse_weight_pct as evidence_weight
from strategies.etf_quant.mapping.proxy import parse_weight_pct as proxy_weight


def test_stdout_review_follows_semantics_and_fails_after_directory_move_or_duplicate():
    tree = ast.parse('def main():\n    print("done")\n')
    call = callsites("library.py", tree)[0]
    policy = [{**call, "category": "CLI_OUTPUT", "reason": "CLI completion message"}]
    assert classify("library.py", tree, policy)[0]["category"] == "CLI_OUTPUT"
    assert classify("scripts/library.py", tree, policy)[0]["category"] == "UNCLASSIFIED_PRINT"
    changed = ast.parse('def main():\n    print("debug")\n')
    assert classify("library.py", changed, policy)[0]["category"] == "UNCLASSIFIED_PRINT"
    duplicated = ast.parse('def main():\n    print("done")\n    print("done")\n')
    assert classify("library.py", duplicated, policy)[1]["category"] == "UNCLASSIFIED_PRINT"
    assert (
        classify("library.py", tree, [{**call, "category": "CLI_OUTPUT", "reason": ""}])[0][
            "category"
        ]
        == "UNCLASSIFIED_PRINT"
    )


def test_archival_alias_never_hides_active_literal_404(tmp_path):
    (tmp_path / "config/engineering").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/current.md").write_text(
        "[old](old.md) [root](/README.md) [reference][missing]\n[missing]: missing.md\n"
    )
    (tmp_path / "docs/archive.md").write_text("archive")
    (tmp_path / "README.md").write_text("readme")
    mapping = {
        "documents": [
            {"path": "docs/current.md", "class": "ACTIVE_USER_DOC"},
            {
                "path": "docs/archive.md",
                "original_path": "docs/old.md",
                "class": "HISTORICAL_AUDIT",
            },
        ]
    }
    (tmp_path / "config/engineering/documentation-map.json").write_text(json.dumps(mapping))
    result = audit(tmp_path)
    assert result["broken_active_links"] == [
        {"document": "docs/current.md", "target": "docs/old.md"},
        {"document": "docs/current.md", "target": "docs/missing.md"},
    ]
    assert result["historical_alias_references"] == 1


def test_no_tls_verification_bypass_in_active_build_files():
    root = Path(__file__).resolve().parents[1]
    for name in (
        "docker/Dockerfile",
        ".devcontainer/Dockerfile",
        "docker-compose.yml",
        "requirements-dev.lock.txt",
    ):
        text = (root / name).read_text().lower()
        assert "trusted-host" not in text and "pip_trusted_host" not in text
        assert "verify=false" not in text and "cert_reqs=cert_none" not in text


def test_provider_and_application_import_boundaries():
    root = Path(__file__).resolve().parents[1]
    for path in (root / "strategies/sw_sector_rotation/src").rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("src.data.providers")
    for path in (root / "src").rglob("*.py"):
        if path.is_relative_to(root / "src/application"):
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("strategies.")
        # Only application orchestration performs concrete strategy discovery.
        assert 'f"strategies.' not in path.read_text()


def test_weight_parser_domain_difference_is_explicit():
    class NumericText:
        def __str__(self):
            return "2.5%"

    assert proxy_weight(NumericText()) == 2.5
    assert evidence_weight(NumericText()) is None
    for value in (None, True, "- -", float("nan"), float("inf")):
        assert proxy_weight(value) is None
        assert evidence_weight(value) is None


def test_private_path_pattern_does_not_confuse_http_urls_with_windows_drives():
    assert MACHINE_PATH.search("https://example.invalid/api") is None
    assert MACHINE_PATH.search("http://localhost:8787") is None
    assert MACHINE_PATH.search("Z:/private/runtime") is not None
    assert MACHINE_PATH.search(r"D:\private\runtime") is not None


def test_inventory_definitions_count_complete_signatures_and_all_path_scopes(tmp_path):
    for name, text in {
        "library.py": 'def complete(x: int, *, y: int = 1) -> int:\n    """Sum."""\n    return x+y\ndef incomplete(x: int, y) -> int:\n    return x+y\n# Z:/source\n',
        "README.md": "Z:/docs\n",
        "Dockerfile": "# Z:/config\n",
        "tests/fixture.py": "# Z:/fixture\n",
        "scripts/engineering/inventory.py": 'import re\nMACHINE_PATH = re.compile("QuantForge")\nROOT = "Z:/hidden"\nMACHINE_PATH = re.compile("QuantForge"); OTHER = "Z:/same-line"\n',
        "pyproject.toml": "[tool.ruff]\n",
        "config/engineering/mypy-baseline.json": "{}",
        "reports/etf_quant/autonomous_code_integrity_v1.json": '{"files":{}}',
    }.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    result = measure(
        tmp_path,
        [
            "library.py",
            "README.md",
            "Dockerfile",
            "tests/fixture.py",
            "scripts/engineering/inventory.py",
        ],
    )
    assert result["functions"] == 2
    assert result["fully_annotated_functions"] == 1
    assert result["function_docstrings"] == 1
    assert result["machine_path_counts"] == {
        "ACTIVE_SOURCE": 3,
        "ACTIVE_DOC": 1,
        "ACTIVE_CONFIG": 1,
        "TEST_FIXTURE": 1,
        "PATTERN_DEFINITION": 1,
    }


def test_external_runtime_overrides_are_shared_and_require_no_private_drive(monkeypatch, tmp_path):
    monkeypatch.setenv("ETF_QUANT_EXTERNAL_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.delenv("ETF_QUANT_PIT_ROOT", raising=False)
    assert runtime_root() == tmp_path
    assert evidence_root("PIT") == tmp_path / "production-pit-evidence-v1"
    monkeypatch.setenv("ETF_QUANT_PIT_ROOT", str(tmp_path / "explicit"))
    assert evidence_root("PIT") == tmp_path / "explicit"
