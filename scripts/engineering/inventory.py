"""Measure repository engineering health without importing application code.

Inputs are tracked source paths, never market data or sealed performance. Function
coverage counts complete signatures (excluding self/cls), including private helpers.
Stdout identities require explicit semantic reviews; paths cover source/config/docs.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import tomllib
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.engineering.prints import CATEGORIES, classify, load_policy  # noqa: E402
from scripts.engineering.typecheck import diagnostics  # noqa: E402 -- Standalone engineering CLI.

MACHINE_PATH = re.compile(
    r"(?<![A-Za-z0-9])[A-Z]:[/\\]|/mnt/[a-z]/|QuantForge|/home/|/Users/|\.codex[/\\]worktrees", re.I
)
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
        return "HISTORICAL_HANDOFF" if "handoff" in name.lower() else "HISTORICAL_AUDIT"
    if "architecture" in name:
        return "ACTIVE_ARCHITECTURE_DOC"
    if name.startswith("docs/research/") or "contract" in name or "spec" in name:
        return "ACTIVE_RESEARCH_PROTOCOL"
    if "environment" in name or "runner" in name or "console" in name:
        return "ACTIVE_OPERATIONS_DOC"
    if "contribut" in name.lower() or "engineering" in name or "developer" in name:
        return "ACTIVE_DEVELOPER_DOC"
    return "ACTIVE_USER_DOC"


def measure(root: Path, names: list[str]) -> dict[str, object]:
    """Return counts and locations; never publish source or credential values."""
    functions = annotated = function_docs = modules = module_docs = classes = class_docs = 0
    python_files: list[dict[str, str | int]] = []
    bom: list[str] = []
    crlf: list[str] = []
    prints: list[dict[str, str | int]] = []
    paths: list[dict[str, object]] = []
    documents: dict[str, str] = {}
    print_policy = load_policy(root)
    map_path = root / "config/engineering/documentation-map.json"
    mapped = json.loads(map_path.read_text()) if map_path.exists() else {"documents": []}
    document_classes = {item["path"]: item["class"] for item in mapped["documents"]}
    for name in sorted(names):
        path = root / name
        if not path.is_file() or (
            path.suffix not in TEXT_SUFFIXES
            and not name.endswith(("Dockerfile", ".example", ".gitignore", ".gitattributes"))
        ):
            continue
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            bom.append(name)
        if b"\r\n" in raw:
            crlf.append(name)
        content = raw.decode("utf-8-sig")
        pattern_spans: dict[int, tuple[int, int]] = {}
        if name == "scripts/engineering/inventory.py":
            for definition in ast.walk(ast.parse(content)):
                if (
                    isinstance(definition, ast.Assign)
                    and any(
                        isinstance(target, ast.Name) and target.id == "MACHINE_PATH"
                        for target in definition.targets
                    )
                    and isinstance(definition.value, ast.Call)
                    and isinstance(definition.value.func, ast.Attribute)
                    and isinstance(definition.value.func.value, ast.Name)
                    and definition.value.func.value.id == "re"
                    and definition.value.func.attr == "compile"
                    and definition.value.args
                    and isinstance(definition.value.args[0], ast.Constant)
                    and isinstance(definition.value.args[0].value, str)
                ):
                    literal = definition.value.args[0]
                    for row in range(literal.lineno, (literal.end_lineno or literal.lineno) + 1):
                        pattern_spans[row] = (
                            literal.col_offset if row == literal.lineno else 0,
                            (literal.end_col_offset or 0)
                            if row == literal.end_lineno
                            else len(content.splitlines()[row - 1]),
                        )
        for line, value in enumerate(content.splitlines(), 1):
            matches = list(MACHINE_PATH.finditer(value))
            if matches:
                span = pattern_spans.get(line)
                only_pattern = span is not None and all(
                    span[0] <= match.start() and match.end() <= span[1] for match in matches
                )
                historical = document_classes.get(name, "").startswith(
                    "HISTORICAL_"
                ) or name.startswith("docs/archive/")
                category = (
                    "TEST_FIXTURE"
                    if "/tests/" in name or name.startswith("tests/")
                    else "HISTORICAL"
                    if historical or name.startswith("reports/etf_quant/")
                    else "ACTIVE_DOC"
                    if path.suffix == ".md"
                    else "PATTERN_DEFINITION"
                    if only_pattern
                    else "ACTIVE_SOURCE"
                    if path.suffix in {".py", ".ts", ".tsx", ".js", ".mjs", ".ps1", ".sh"}
                    else "ACTIVE_CONFIG"
                )
                paths.append({"path": name, "line": line, "category": category})
        if path.suffix == ".md":
            documents[name] = document_classes.get(name, document_class(name))
        if path.suffix != ".py":
            continue
        tree = ast.parse(content, filename=name)
        prints.extend(classify(name, tree, print_policy))
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
    config = tomllib.loads((root / "pyproject.toml").read_text())
    baseline = json.loads((root / "config/engineering/mypy-baseline.json").read_text())
    historical = json.loads(
        (root / "reports/etf_quant/autonomous_code_integrity_v1.json").read_text()
    )
    active_private_paths = [
        p for p in paths if documents.get(str(p["path"]), "").startswith("ACTIVE_")
    ]
    return {
        "method": "Tracked UTF-8 source; AST complete signatures exclude self/cls. Stdout requires per-call semantic review. LOC includes comments/blanks. Literal documentation links, no alias exemptions. Machine paths cover all source/config/docs separately.",
        "python_files": modules,
        "python_lines": sum(int(f["lines"]) for f in python_files),
        "active_python_bom_files": [name for name in bom if name.endswith(".py")],
        "active_python_crlf_files": [name for name in crlf if name.endswith(".py")],
        "active_python_modules_over_500_lines": [
            f
            for f in python_files
            if int(f["lines"]) > 500
            and "/tests/" not in str(f["path"])
            and not str(f["path"]).startswith("tests/")
        ],
        "ruff_format_exclusions": config["tool"]["ruff"].get("format", {}).get("exclude", []),
        "historically_certified_source_files": len(historical["files"]),
        "mypy_baseline_diagnostic_count": sum(baseline.values()),
        "mypy_baseline_files_containing_diagnostics": len({json.loads(key)[0] for key in baseline}),
        "tracked_markdown_files": len(documents),
        "docs_etf_quant_markdown_files": sum(
            name.startswith("docs/etf_quant/") for name in documents
        ),
        "historical_markdown_files": sum(
            value.startswith("HISTORICAL_") for value in documents.values()
        ),
        "active_document_private_path_references": active_private_paths,
        "active_source_private_path_references": [
            p for p in paths if p["category"] == "ACTIVE_SOURCE"
        ],
        "active_config_private_path_references": [
            p for p in paths if p["category"] == "ACTIVE_CONFIG"
        ],
        "historical_private_path_references": [p for p in paths if p["category"] == "HISTORICAL"],
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
        "print_counts": {
            category: sum(p["category"] == category for p in prints) for category in CATEGORIES
        },
        "print_locations": prints,
        "machine_path_counts": dict(Counter(str(p["category"]) for p in paths)),
        "machine_path_locations": paths,
        "markdown_classes": dict(Counter(documents.values())),
        "documents": documents,
    }


def mypy_inventory(output: str) -> dict[str, object]:
    """Count raw diagnostics separately from files, with explicit active scope."""
    raw = diagnostics(output)
    by_file: Counter[str] = Counter()
    by_area: Counter[str] = Counter()
    active = (
        "src/",
        "strategies/etf_quant/",
        "services/etf-quant-runner/",
        "services/cnequity-sidecar/",
    )
    for key, count in raw.items():
        name = str(json.loads(key)[0])
        by_file[name] += count
        by_area[name.split("/")[0]] += count
    return {
        "raw_diagnostic_count": sum(raw.values()),
        "files_containing_diagnostics": len(by_file),
        "diagnostics_by_file": dict(sorted(by_file.items())),
        "diagnostics_by_top_level_area": dict(sorted(by_area.items())),
        "active_runtime_diagnostic_count": sum(
            n for name, n in by_file.items() if name.startswith(active)
        ),
        "active_runtime_scope": list(active),
    }


def main() -> None:
    """Write a JSON inventory from an explicitly supplied Git path manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mypy-output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    names = args.manifest.read_text(encoding="utf-8-sig").splitlines()
    result = measure(root, names)
    if args.mypy_output is not None:
        result["mypy"] = mypy_inventory(args.mypy_output.read_text(encoding="utf-8"))
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    counts = result["print_counts"]
    assert isinstance(counts, dict)
    if any(counts[k] for k in ("DEBUG_STATUS", "ACCIDENTAL_PRINT", "UNCLASSIFIED_PRINT")):
        raise SystemExit("Stdout semantic review gate failed; see inventory print_locations")


if __name__ == "__main__":
    main()
