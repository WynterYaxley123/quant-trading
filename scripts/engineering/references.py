"""Verify active Markdown links and byte-preserved historical path mappings."""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def audit(root: Path = ROOT) -> dict[str, object]:
    """Check local references without requesting remote pages or private files."""
    mapping = json.loads((root / "config/engineering/documentation-map.json").read_text())
    documents = mapping["documents"]
    moved = {item["original_path"]: item["path"] for item in documents if "original_path" in item}
    broken: list[dict[str, str]] = []
    changed: list[str] = []
    checked = 0
    historical_alias_references = 0
    for item in documents:
        source = root / item["path"]
        if item.get("removed_from_tree"):
            continue
        if item.get("sha256") and hashlib.sha256(source.read_bytes()).hexdigest() != item["sha256"]:
            changed.append(item["path"])
        if not item["class"].startswith("ACTIVE_"):
            continue
        text = re.sub(
            r"```.*?```|~~~.*?~~~", "", source.read_text(encoding="utf-8-sig"), flags=re.S
        )
        for match in LINK.finditer(text):
            value = match.group(1).strip().strip("<>").split(' "', 1)[0]
            parts = urlsplit(value)
            if parts.scheme or parts.netloc or not parts.path:
                continue
            checked += 1
            target = posixpath.normpath(
                unquote(parts.path).lstrip("/")
                if parts.path.startswith("/")
                else posixpath.join(posixpath.dirname(item["path"]), unquote(parts.path))
            )
            historical_alias_references += int(target in moved)
            if target.startswith("../") or not (root / target).exists():
                broken.append({"document": item["path"], "target": target})
    return {
        "status": "PASS" if not broken and not changed else "FAIL",
        "active_local_links_checked": checked,
        "broken_active_links": broken,
        "changed_archived_bytes": changed,
        "historical_path_aliases": len(moved),
        "historical_alias_references": historical_alias_references,
    }


def main() -> None:
    """Emit counts and paths; no archived payloads or local machine paths."""
    result = audit()
    print(json.dumps(result, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
