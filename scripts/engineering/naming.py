"""Keep current artifact names functional; preserve byte-pinned historical exceptions."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL_NAME = re.compile(
    r"(?:^|[/_.-])(?:codex|deepseek|mimo|kimi|claude|chatgpt|hermes|takeover|handoff|agent)(?:[/_.-]|$)",
    re.I,
)


def violations(root: Path, names: list[str], exceptions: dict[str, str]) -> list[str]:
    """Exact retained historical bytes are exempt; new transcripts are rejected."""
    result = []
    for name in names:
        if name == "AGENTS.md" or not MODEL_NAME.search(name):
            continue
        expected = exceptions.get(name)
        target = (root / name).resolve()
        if (
            not expected
            or not target.is_relative_to(root.resolve())
            or not target.is_file()
            or hashlib.sha256(target.read_bytes()).hexdigest() != expected
        ):
            result.append(name)
    return sorted(result)


def main() -> None:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
    )
    names = sorted(set(output.decode().strip("\0").split("\0")))
    exceptions = json.loads((ROOT / "config/engineering/naming-exceptions.json").read_text())
    failures = violations(ROOT, names, exceptions["historical_files"])
    sys.stdout.write(
        json.dumps(
            {
                "status": "FAIL" if failures else "PASS",
                "violations": failures,
                "retained_historical_files": len(exceptions["historical_files"]),
            }
        )
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
