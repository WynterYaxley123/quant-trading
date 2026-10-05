"""Active Markdown link coverage, independent of repository totals and aliases."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.engineering.references import audit


@pytest.fixture
def documentation(tmp_path):
    (tmp_path / "config/engineering").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/valid.md").write_text("valid")
    mapping = {"documents": [{"path": "docs/current.md", "class": "ACTIVE_USER_DOC"}]}
    (tmp_path / "config/engineering/documentation-map.json").write_text(json.dumps(mapping))
    return tmp_path


@pytest.mark.parametrize(
    "text,passes",
    [
        ("[inline](valid.md)", True),
        ("[inline](missing.md)", False),
        ("[reference][id]\n\n[id]: valid.md", True),
        ("[reference][id]\n\n[id]: missing.md", False),
        ("[reference][missing]", False),
        ("[missing][]", False),
        ("[id][]\n\n[id]: valid.md", True),
        ("[id]\n\n[id]: valid.md", True),
        ("[id]\n\n[id]: missing.md", False),
        ('[reference][id]\n\n[id]: valid.md "optional title"', True),
        ('[reference][id]\n\n[id]: <valid.md> "optional title"', True),
        ("[reference][id]\n\n[id]: <missing.md>", False),
        ("[reference][ A  B ]\n\n[a b]: valid.md", True),
        ("[id]\n\n[id]: valid.md\n[ID]: missing.md", True),
        ("[id]\n\n[id]: missing.md\n[ID]: valid.md", False),
        ("[unused]: missing.md", False),
        ("[remote](https://example.invalid/unfetched)\n\n[id]: http://example.invalid", True),
        ("`[undefined][id]`\n\n```md\n[undefined][id]\n```", True),
        ("\\[literal] [ordinary bracket text]", True),
        ("[inline](../../outside.md)", False),
        ("[ref][id]\n\n[id]: ../../outside.md", False),
        ("[ref][id]\n\n[id]: %2e%2e/%2e%2e/outside.md", False),
        ("![image][id]\n\n[id]: missing.md", False),
    ],
)
def test_active_inline_reference_and_containment_contracts(documentation, text, passes):
    (documentation / "docs/current.md").write_text(text)
    result = audit(documentation)
    assert (result["status"] == "PASS") is passes
    assert bool(result["broken_active_links"]) is not passes


def test_archival_path_mapping_never_rescues_a_wrong_active_reference(documentation):
    (documentation / "docs/archive.md").write_text("archived")
    mapping_path = documentation / "config/engineering/documentation-map.json"
    mapping = json.loads(mapping_path.read_text())
    mapping["documents"].append(
        {"path": "docs/archive.md", "original_path": "docs/old.md", "class": "HISTORICAL_AUDIT"}
    )
    mapping_path.write_text(json.dumps(mapping))
    (documentation / "docs/current.md").write_text("[ref][id]\n\n[id]: old.md")
    result = audit(documentation)
    assert result["broken_active_links"] == [
        {"document": "docs/current.md", "target": "docs/old.md"}
    ]
    assert result["historical_alias_references"] == 1
    (documentation / "docs/current.md").write_text("[ref][id]\n\n[id]: archive.md")
    assert audit(documentation)["status"] == "PASS"


def test_historical_docs_skip_link_checks_but_keep_byte_preservation(documentation):
    source = documentation / "docs/current.md"
    source.write_text("[reference][missing]")
    mapping_path = documentation / "config/engineering/documentation-map.json"
    mapping = {
        "documents": [
            {
                "path": "docs/current.md",
                "class": "HISTORICAL_AUDIT",
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        ]
    }
    mapping_path.write_text(json.dumps(mapping))
    assert audit(documentation)["status"] == "PASS"
    source.write_text("changed historical bytes")
    assert audit(documentation)["changed_archived_bytes"] == ["docs/current.md"]


def test_symlink_target_outside_repository_is_rejected(documentation):
    outside = documentation.parent / "outside.md"
    outside.write_text("synthetic")
    (documentation / "docs/escape.md").symlink_to(outside)
    (documentation / "docs/current.md").write_text("[ref][id]\n\n[id]: escape.md")
    assert audit(documentation)["status"] == "FAIL"


def test_active_status_and_named_obsolete_paths_stay_consistent():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/README.md").read_text()
    assert "策略开发尚未开始" not in source
    assert "首个正式 Shadow epoch 尚未创建" in source
    mapping = json.loads((root / "config/engineering/documentation-map.json").read_text())
    for item in mapping["documents"]:
        if item["class"].startswith("ACTIVE_") and not item.get("removed_from_tree"):
            text = (root / item["path"]).read_text()
            for obsolete in (
                "chatgpt_workflow.md",
                "integration_v1_handoff.md",
                "integration-audit.md",
            ):
                assert obsolete not in text, item["path"]
    assert "frozen models" not in (root / "services/etf-quant-runner/README.md").read_text()


def test_plain_repository_paths_are_checked_without_alias_rescue(documentation):
    current = documentation / "docs/current.md"
    current.write_text("See `docs/valid.md` and docs/missing.md.\n")
    result = audit(documentation)
    assert result["active_plain_paths_checked"] == 2
    assert result["broken_active_links"] == [
        {"document": "docs/current.md", "target": "docs/missing.md"}
    ]


def test_unclassified_tracked_markdown_cannot_hide_from_link_metric(documentation):
    (documentation / "docs/current.md").write_text("current")
    result = audit(documentation, names=["docs/current.md", "docs/unreviewed.md"])
    assert result["status"] == "FAIL"
    assert result["unclassified_markdown"] == ["docs/unreviewed.md"]
