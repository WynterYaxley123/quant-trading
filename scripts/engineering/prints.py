"""Reviewed stdout call identities; file placement never grants an exemption."""

from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter
from pathlib import Path

CATEGORIES = (
    "CLI_OUTPUT",
    "MACHINE_READABLE_OUTPUT",
    "REPORT_OUTPUT",
    "EXAMPLE_OUTPUT",
    "TEST_OUTPUT",
    "DEBUG_STATUS",
    "ACCIDENTAL_PRINT",
    "UNCLASSIFIED_PRINT",
)


def callsites(name: str, tree: ast.AST) -> list[dict[str, str | int]]:
    """Fingerprint AST plus lexical context and occurrence; ignore line/format changes."""
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    occurrences: Counter[tuple[str, str]] = Counter()
    result: list[dict[str, str | int]] = []
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]
    for node in sorted(calls, key=lambda n: (n.lineno, n.col_offset)):
        context = []
        parent: ast.AST = node
        while parent in parents:
            parent = parents[parent]
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                context.append(parent.name)
        scope = ".".join(reversed(context)) or "<module>"
        fingerprint = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
        occurrence = occurrences[scope, fingerprint]
        occurrences[scope, fingerprint] += 1
        result.append(
            {
                "path": name,
                "context": scope,
                "ast_sha256": fingerprint,
                "occurrence": occurrence,
                "line": node.lineno,
            }
        )
    return result


def identity(call: dict[str, str | int]) -> str:
    return json.dumps([call[k] for k in ("path", "context", "ast_sha256", "occurrence")])


def classify(
    name: str, tree: ast.AST, policy: list[dict[str, str | int]]
) -> list[dict[str, str | int]]:
    """Missing or malformed review metadata fails closed."""
    reviewed = {identity(item): item for item in policy}
    result = []
    for call in callsites(name, tree):
        item = reviewed.get(identity(call), {})
        category, reason = item.get("category"), item.get("reason")
        valid = category in CATEGORIES[:-1] and isinstance(reason, str) and bool(reason.strip())
        result.append(
            {
                **call,
                "category": str(category) if valid else "UNCLASSIFIED_PRINT",
                "reason": str(reason) if valid else "No matching semantic review",
            }
        )
    return result


def load_policy(root: Path) -> list[dict[str, str | int]]:
    path = root / "config/engineering/print-policy.json"
    return json.loads(path.read_text())["calls"] if path.is_file() else []
