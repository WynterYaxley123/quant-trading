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


def build(
    root: Path,
    parent_path: str,
    output_path: str,
    base_sha: str,
    label: str,
    evidence: str,
    previous_path: str | None = None,
) -> dict[str, Any]:
    parent_bytes = (root / parent_path).read_bytes()
    parent = json.loads(parent_bytes)["implementation_integrity"]
    if parent["identifier"] != "CURRENT_IMPLEMENTATION_INTEGRITY":
        raise ValueError("FULL_VERIFIED_PARENT_REQUIRED")
    # A superseded delta on the same parent keeps its recorded reasons for unchanged files.
    previous: dict[str, dict[str, Any]] = {}
    if previous_path:
        prior = json.loads((root / previous_path).read_bytes())["implementation_integrity"]
        if prior["parent_manifest_sha256"] != hashlib.sha256(parent_bytes).hexdigest():
            raise ValueError("PREVIOUS_DELTA_PARENT_MISMATCH")
        previous = {change["path"]: change for change in prior["changes"]}
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", "-z", base_sha, "--"], cwd=root
    )
    added = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=root
    )
    names = set((changed + added).decode().strip("\0").split("\0")) - {""}
    names.update(previous)  # A new transition must carry every earlier delta change.
    names.add(parent_path)  # The verifier's closed copy fixture includes its parent.
    if previous_path:
        names.add(previous_path)  # Preserve and verify the superseded certificate's bytes.
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
                "reason": previous[name]["reason"]
                if previous.get(name, {}).get("after_sha256") == after
                else f"{label} verified remediation",
            }
        )
    integrity = {
        "identifier": "CURRENT_IMPLEMENTATION_DELTA",
        "canonicalization": "JSON_SORTED_KEYS_COMPACT_UTF8_V1",
        "parent_manifest_path": parent_path,
        "parent_manifest_sha256": hashlib.sha256(parent_bytes).hexdigest(),
        "parent_sha": base_sha,
        "transition_reason": f"{label} remediation; historical evidence stays byte-pinned by the parent chain",
        "files": files,
        "changes": changes,
        "regression_evidence": evidence,
    }
    integrity["certificate_sha256"] = certificate_hash(integrity)
    return {"schema_version": 1, "implementation_integrity": integrity}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--label", required=True, help="Transition label, for example V8")
    parser.add_argument("--evidence", required=True, help="Repository regression record")
    parser.add_argument("--previous", help="Superseded delta on the same parent")
    args = parser.parse_args()
    output = ROOT / args.output
    if not output.resolve().is_relative_to(ROOT):
        raise ValueError("REPOSITORY_OUTPUT_REQUIRED")
    output.write_text(
        json.dumps(
            build(
                ROOT,
                args.parent,
                args.output,
                args.base_sha,
                args.label,
                args.evidence,
                args.previous,
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
