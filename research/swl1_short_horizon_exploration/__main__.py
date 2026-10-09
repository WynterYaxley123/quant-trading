"""Explicit isolated preparation or computation; default verifies design only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .boundary import prepare
from .design import DESIGN_SHA, LABEL, load_design
from .study import run
from .verify import verify_reports


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--run", action="store_true")
    action.add_argument("--verify-public", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--owner-task", type=Path)
    parser.add_argument("--private", type=Path)
    parser.add_argument("--public", type=Path)
    args = parser.parse_args()
    design = load_design(args.root)
    if args.verify_public:
        print(json.dumps(verify_reports(args.root)))
    elif args.prepare:
        if args.source is None or args.owner_task is None or args.private is None:
            parser.error("prepare requires --source --owner-task --private")
        value = prepare(args.root, args.source, args.owner_task, args.private)
        print(
            json.dumps(
                {
                    "label": LABEL,
                    "prepared_return_rows": value["return_rows"],
                    "last_outcome": value["last_outcome"],
                }
            )
        )
    elif args.run:
        if args.source is None or args.private is None or args.public is None:
            parser.error("run requires --source --private --public")
        value = run(args.root, args.source, args.private, args.public)
        print(
            json.dumps({"label": LABEL, "status": value["status"], "signals": value["accounting"]})
        )
    else:
        print(
            json.dumps(
                {
                    "label": LABEL,
                    "status": "DESIGN_VERIFIED_NO_NUMERIC_ACCESS",
                    "spec_count": len(design["specifications"]),
                    "manifest_sha256": DESIGN_SHA,
                }
            )
        )


if __name__ == "__main__":
    main()
