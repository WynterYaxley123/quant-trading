"""Metadata by default; explicit replay uses isolated read-only inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .replay import load_spec, replay


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--view", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.view is not None:
        if args.output is None:
            parser.error("--view requires --output")
        result = replay(args.root, args.view, args.output)
    else:
        spec, digest = load_spec(args.root)
        result = {"model_hash": digest, "spec": spec, "numeric_access": False}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
