"""Result-leak gate for a Factor Set V2 *preregistration* invocation.

This command is intentionally separate from the post-preregistration formal
runner: a completed V2 run must not make ordinary protocol tests fail.
"""

from __future__ import annotations

import argparse
from pathlib import Path

RESULT_PREFIXES = ("factor_set_v2", "iteration2", "v2_candidate")


def assert_no_v2_formal_results(reports_root: Path) -> None:
    """Fail closed if a preregistration would follow an existing V2 result."""
    if not reports_root.exists():
        return
    if not reports_root.is_dir():
        raise ValueError("PREREGISTRATION_RESULT_LEAK_BLOCKER: invalid reports root")
    leaked = sorted(
        entry.name for entry in reports_root.iterdir()
        if entry.is_dir() and entry.name.startswith(RESULT_PREFIXES)
    )
    if leaked:
        raise ValueError(f"PREREGISTRATION_RESULT_LEAK_BLOCKER: {leaked}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reports-root", type=Path,
        default=Path("reports/research/shenwan_sector_index"),
    )
    args = parser.parse_args()
    assert_no_v2_formal_results(args.reports_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
