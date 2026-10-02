"""Measure repository engineering health without importing application code.

Inputs are tracked source paths, never market data or sealed performance. Function
coverage counts complete signatures (excluding self/cls), including private helpers.
Print/path/document classifications are explicit heuristics for subsequent review.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from pathlib import Path

MACHINE_PATH = re.compile(r"[CD]:[/\\]|QuantForge|/home/|/Users/|\.codex[/\\]worktrees")
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".ps1",
    ".css",
    ".html",
    ".sh",
}


def document_class(name: str) -> str:
    """Classify documents without relocating path-bound historical evidence."""
    if any(
        word in name.lower()
        for word in ("audit", "handoff", "acceptance", "closure", "takeover", "report", "archive")
    ):
        return "HISTORICAL_AUDIT_OR_HANDOFF"
    if "architecture" in name:
        return "ARCHITECTURE"
    if name.startswith("docs/research/") or "contract" in name or "spec" in name:
        return "RESEARCH_CONTRACT"
    if "environment" in name or "runner" in name or "console" in name:
        return "OPERATIONS"
    if "contribut" in name.lower() or "engineering" in name or "developer" in name:
        return "ACTIVE_DEVELOPER_DOC"
    return "ACTIVE_USER_DOC"


def measure(root: Path, names: list[str]) -> dict[str, object]:
    """Return counts and locations; never publish source or credential values."""
    functions = annotated = function_docs = modules = module_docs = classes = class_docs = 0
    python_files: list[dict[str, str | int]] = []
    bom: list[str] = []
    crlf: list[str] = []
    prints: list[dict[str, object]] = []
    paths: list[dict[str, object]] = []
    documents: dict[str, str] = {}
    for name in sorted(names):
        path = root / name
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            bom.append(name)
        if b"\r\n" in raw:
            crlf.append(name)
        content = raw.decode("utf-8-sig")
        for line, value in enumerate(content.splitlines(), 1):
            if MACHINE_PATH.search(value):
                category = (
                    "TEST_FIXTURE"
                    if "/tests/" in name or name.startswith("tests/")
                    else "HISTORICAL_OR_DOC_EXAMPLE"
                    if path.suffix == ".md"
                    else "OPERATIONAL_SOURCE_OR_CONFIG"
                )
                paths.append({"path": name, "line": line, "category": category})
        if path.suffix == ".md":
            documents[name] = document_class(name)
        if path.suffix != ".py":
            continue
        tree = ast.parse(content, filename=name)
        modules += 1
        module_docs += bool(ast.get_docstring(tree))
        python_files.append({"path": name, "lines": len(content.splitlines())})
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions += 1
                args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                args += [a for a in (node.args.vararg, node.args.kwarg) if a is not None]
                annotated += node.returns is not None and all(
                    a.annotation is not None for a in args if a.arg not in {"self", "cls"}
                )
                function_docs += bool(ast.get_docstring(node))
            elif isinstance(node, ast.ClassDef):
                classes += 1
                class_docs += bool(ast.get_docstring(node))
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ):
                category = (
                    "D_TEST_OUTPUT"
                    if name.startswith("tests/") or "/tests/" in name
                    else "A_CLI_OUTPUT"
                    if name.startswith(("scripts/", "research/", "services/", "examples/"))
                    or name.endswith(("cli.py", "feishu.py", "runtime_smoke.py"))
                    else "C_REVIEW_INTERNAL"
                )
                prints.append({"path": name, "line": node.lineno, "category": category})
    return {
        "method": "Tracked UTF-8 source; AST complete signatures exclude self/cls. Categories are reviewed heuristics; LOC includes comments/blanks.",
        "python_files": modules,
        "python_lines": sum(int(f["lines"]) for f in python_files),
        "functions": functions,
        "fully_annotated_functions": annotated,
        "annotation_percent": round(100 * annotated / functions, 2) if functions else None,
        "function_docstrings": function_docs,
        "function_docstring_percent": round(100 * function_docs / functions, 2)
        if functions
        else None,
        "module_docstrings": module_docs,
        "classes": classes,
        "class_docstrings": class_docs,
        "bom_files": bom,
        "crlf_files": crlf,
        "largest_python_files": sorted(python_files, key=lambda f: int(f["lines"]), reverse=True)[
            :15
        ],
        "print_counts": dict(Counter(str(p["category"]) for p in prints)),
        "print_locations": prints,
        "machine_path_counts": dict(Counter(str(p["category"]) for p in paths)),
        "machine_path_locations": paths,
        "markdown_classes": dict(Counter(documents.values())),
        "documents": documents,
    }


def main() -> None:
    """Write a JSON inventory from an explicitly supplied Git path manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    names = args.manifest.read_text(encoding="utf-8-sig").splitlines()
    args.output.write_text(json.dumps(measure(root, names), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
