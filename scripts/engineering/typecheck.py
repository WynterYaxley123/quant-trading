"""Check every configured module and ratchet reviewed legacy Mypy diagnostics.

No errors are suppressed in Mypy. The baseline lists exact path/code/message
counts, independent of line numbers. New diagnostics and stale allowances fail.
New tooling/demo and strict model/sizing boundaries must have zero diagnostics.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "config/engineering/mypy-baseline.json"
ERROR = re.compile(r"^(.+?):\d+(?::\d+)?: error: (.+)  \[([^]]+)\]$")
STRICT_PATHS = (
    "research/etf_quant_v2/",
    "scripts/engineering/",
    "examples/",
    "src/data/schema.py",
    "src/data/calendar.py",
    "src/notifications/",
    "src/",
    "strategies/etf_quant/",
    "services/etf-quant-runner/",
    "services/cnequity-sidecar/",
    "scripts/data/admit_shenwan_etf_mapping.py",
    "scripts/data/mapping_",
    "scripts/etf_quant/build_production_pit_evidence.py",
    "scripts/etf_quant/production_pit_",
)


def diagnostics(output: str) -> Counter[str]:
    """Discard unstable line numbers, preserving exact diagnostic identities."""
    result: Counter[str] = Counter()
    for line in output.splitlines():
        match = ERROR.fullmatch(line)
        if match:
            name, message, code = match.groups()
            result[json.dumps([name.replace("\\", "/"), code, message])] += 1
    return result


def main() -> int:
    """Fail for regressions or stale debt; updates require explicit review."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-baseline", action="store_true", help="maintainer-only reviewed update"
    )
    args = parser.parse_args()
    run = subprocess.run(
        [sys.executable, "-m", "mypy", "--no-error-summary", "--no-pretty", "--no-color-output"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    current = diagnostics(run.stdout)
    if run.returncode not in (0, 1) or (run.returncode == 1 and not current):
        print(run.stdout + run.stderr)
        return 1
    strict = [key for key in current if json.loads(key)[0].startswith(STRICT_PATHS)]
    if strict:
        print("Strict/new-code diagnostics:")
        for key in strict:
            print(key)
        return 1
    baseline = Counter(json.loads(BASELINE.read_text(encoding="utf-8")))
    added, removed = current - baseline, baseline - current
    if args.write_baseline and not added:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps(dict(sorted(current.items())), indent=2) + "\n", encoding="utf-8"
        )
        baseline = current.copy()
        removed = Counter()
    if added or removed:
        print(
            json.dumps(
                {"new_diagnostics": dict(added), "stale_allowances": dict(removed)}, indent=2
            )
        )
        return 1
    print(
        f"Mypy staged gate PASS; {sum(current.values())} reviewed legacy diagnostics; strict/new code: 0."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
