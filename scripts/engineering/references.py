"""Verify active Markdown links and byte-preserved historical path mappings."""

from __future__ import annotations

import hashlib
import json
import posixpath
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt
from markdown_it.common.utils import normalizeReference
from markdown_it.rules_inline.state_inline import StateInline

ROOT = Path(__file__).resolve().parents[2]


def unresolved_reference(state: StateInline, silent: bool) -> bool:
    """Flag undefined explicit/collapsed references outside Markdown code.

    Defined shortcuts are parsed normally; unbound bracket text stays plain text.
    Reference definitions, normalized labels and first-definition precedence come
    from the already-pinned CommonMark parser, not a second definition regex.
    """
    if silent or state.src[state.pos] != "[":
        return False
    end = state.md.helpers.parseLinkLabel(state, state.pos, True)
    if end < 0 or end + 1 >= state.posMax or state.src[end + 1] != "[":
        return False
    reference_end = state.md.helpers.parseLinkLabel(state, end + 1)
    if reference_end < 0:
        return False
    label = normalizeReference(state.src[end + 2 : reference_end] or state.src[state.pos + 1 : end])
    if label in state.env.get("references", {}):
        return False
    token = state.push("unresolved_reference", "", 0)
    token.meta["label"] = label
    state.pos = reference_end + 1
    return True


def markdown_links(text: str) -> tuple[list[str], list[str]]:
    """Collect rendered destinations, effective definitions and undefined labels."""
    parser = MarkdownIt("commonmark")
    parser.inline.ruler.before("link", "unresolved_reference", unresolved_reference)
    environment: dict = {}
    tokens = parser.parse(text, environment)
    targets: list[str] = []
    undefined: list[str] = []
    for block in tokens:
        for token in block.children or []:
            if token.type in {"link_open", "image"}:
                target = token.attrGet("href" if token.type == "link_open" else "src")
                if isinstance(target, str):
                    targets.append(target)
            elif token.type == "unresolved_reference":
                undefined.append(token.meta["label"])
    # Also check unused effective definitions; duplicate definitions use the first.
    for reference in environment.get("references", {}).values():
        if reference["href"] not in targets:
            targets.append(reference["href"])
    return targets, undefined


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
        targets, undefined = markdown_links(source.read_text(encoding="utf-8-sig"))
        broken.extend(
            {"document": item["path"], "target": "UNDEFINED_REFERENCE:" + label}
            for label in undefined
        )
        for raw_target in targets:
            parts = urlsplit(raw_target)
            if parts.scheme or parts.netloc or not parts.path:
                continue
            checked += 1
            target = posixpath.normpath(
                unquote(parts.path).lstrip("/")
                if parts.path.startswith("/")
                else posixpath.join(posixpath.dirname(item["path"]), unquote(parts.path))
            )
            historical_alias_references += int(target in moved)
            resolved = (root / target).resolve()
            if not resolved.is_relative_to(root.resolve()) or not resolved.exists():
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
