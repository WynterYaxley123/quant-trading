"""Record a compact source transition without copying the historical hash inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from strategies.etf_quant.runtime.implementation import certificate_hash

ROOT = Path(__file__).resolve().parents[2]


def build(root: Path, parent_path: str, output_path: str, base_sha: str) -> dict[str, Any]:
    parent_bytes = (root / parent_path).read_bytes()
    parent = json.loads(parent_bytes)["implementation_integrity"]
    if parent["identifier"] != "CURRENT_IMPLEMENTATION_INTEGRITY":
        raise ValueError("FULL_VERIFIED_PARENT_REQUIRED")
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", "-z", base_sha, "--"], cwd=root
    )
    added = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=root
    )
    names = set((changed + added).decode().strip("\0").split("\0")) - {""}
    names.add(parent_path)  # The verifier's closed copy fixture includes its parent.
    files, changes = {}, []
    for name in sorted(set(names) | set(parent["files"])):
        if name == output_path:
            continue
        target = (root / name).resolve(strict=True)
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            raise ValueError("SOURCE_CONTAINMENT_REQUIRED")
        after = hashlib.sha256(target.read_bytes()).hexdigest()
        before = parent["files"].get(name)
        if before == after:
            continue
        if before and (
            name.startswith(("reports/", "config/research/", "docs/archive/"))
            or name.startswith("strategies/")
            and "/config/" in name
        ):
            raise ValueError("IMMUTABLE_ARTIFACT_CHANGED:" + name)
        files[name] = after
        changes.append(
            {
                "path": name,
                "before_sha256": before,
                "after_sha256": after,
                "reason": "V7 verified research labeling, runtime recovery and engineering correction",
            }
        )
    integrity = {
        "identifier": "CURRENT_IMPLEMENTATION_DELTA",
        "canonicalization": "JSON_SORTED_KEYS_COMPACT_UTF8_V1",
        "parent_manifest_path": parent_path,
        "parent_manifest_sha256": hashlib.sha256(parent_bytes).hexdigest(),
        "parent_sha": base_sha,
        "transition_reason": "V7 remediation; historical evidence stays byte-pinned by the parent chain",
        "files": files,
        "changes": changes,
        "regression_evidence": "docs/engineering/v7-remediation.md",
    }
    integrity["certificate_sha256"] = certificate_hash(integrity)
    return {"schema_version": 1, "implementation_integrity": integrity}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-sha", required=True)
    args = parser.parse_args()
    output = ROOT / args.output
    if not output.resolve().is_relative_to(ROOT):
        raise ValueError("REPOSITORY_OUTPUT_REQUIRED")
    output.write_text(
        json.dumps(build(ROOT, args.parent, args.output, args.base_sha), indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
