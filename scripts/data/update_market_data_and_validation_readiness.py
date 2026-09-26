"""Read-only readiness CLI; append update fails closed until a safe adapter exists.

Use only the existing Docker environment. No network/scheduler/apply path.
Optional audit exports are exclusive-create inside the ignored manifest tree.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from research.f1_validation_readiness_v1 import ROOT, blocked_cycle, inspect_parent
from src.data.providers.shenwan_append_only import canonical_bytes


def export_audit(root: Path, destination: Path, artifacts: dict[str, dict]) -> None:
    destination = destination.resolve()
    allowed = (root / "data/manifests/f1_validation_readiness_v1").resolve()
    if destination == allowed or not destination.is_relative_to(allowed):
        raise ValueError("AUDIT_EXPORT_PATH_BLOCKER")
    if any(Path(name).name != name or not name.endswith(".json") for name in artifacts):
        raise ValueError("AUDIT_EXPORT_FILENAME_BLOCKER")
    # Never overwrite an existing run or publish any canonical dataset.
    destination.mkdir(parents=True, exist_ok=False)
    for name, value in artifacts.items():
        with (destination / name).open("xb") as stream:
            stream.write(canonical_bytes(value))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--readiness-only", action="store_true")
    modes.add_argument("--update-append-only", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    pre, readiness = inspect_parent()
    manifest = blocked_cycle(pre, readiness)
    if args.update_append_only:
        post, post_readiness = inspect_parent()
        if canonical_bytes(pre) != canonical_bytes(post) or canonical_bytes(readiness) != canonical_bytes(post_readiness):
            raise ValueError("PARENT_CHANGED_DURING_BLOCKED_CYCLE_BLOCKER")
        manifest["postAuditStatus"] = "PASS_UNCHANGED_PARENT_NO_CANONICAL_WRITES"
    if args.output_dir is not None:
        export_audit(ROOT, args.output_dir, {"pre_update_manifest.json": pre,
            "update_manifest.json": manifest, "readiness.json": readiness})
    sys.stdout.buffer.write(canonical_bytes(manifest if args.update_append_only else readiness))
    # 2 means a deliberate fail-closed data-update blocker, not an executed fetch.
    return 2 if args.update_append_only else 0


if __name__ == "__main__":
    raise SystemExit(main())
