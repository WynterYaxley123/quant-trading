"""Development requires a protocol already published on a fetched remote ref.

Local commit times are self-asserted. A remote-tracking ref containing the exact
protocol bytes, without any result file at that commit, shows the protocol was
pushed before the run; GitHub's merge record is the external witness.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

PROTOCOL = "config/research/swl1-ridge-v2-protocol.json"
RESULTS = (
    "reports/research/swl1_ridge_v2/development.json",
    "reports/research/swl1_ridge_v2/validation.json",
    "reports/research/swl1_ridge_v2/status.json",
    "config/research/swl1-ridge-v2-candidate.json",
)


def git(repository: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=repository, capture_output=True, check=False)


def public_anchor(repository: Path, remote_ref: str) -> dict[str, Any]:
    if not remote_ref.startswith("refs/remotes/"):
        raise ValueError("REMOTE_TRACKING_REF_REQUIRED")
    if git(repository, "rev-parse", "--verify", "--quiet", remote_ref + "^{commit}").returncode:
        raise ValueError("REMOTE_REF_NOT_FETCHED")
    added = git(repository, "log", "--format=%H", "--diff-filter=A", remote_ref, "--", PROTOCOL)
    commits = added.stdout.decode().split()
    if added.returncode or not commits:
        raise ValueError("PROTOCOL_NOT_PUBLISHED")
    commit = commits[-1]
    published = git(repository, "show", f"{remote_ref}:{PROTOCOL}")
    if published.returncode or published.stdout != (repository / PROTOCOL).read_bytes():
        raise ValueError("PROTOCOL_CHANGED_AFTER_PUBLICATION")
    for name in RESULTS:
        if not git(repository, "cat-file", "-e", f"{commit}:{name}").returncode:
            raise ValueError("RESULTS_PUBLISHED_WITH_PROTOCOL")
    when = git(repository, "show", "-s", "--format=%cI", commit).stdout.decode().strip()
    return {"remote_ref": remote_ref, "protocol_commit": commit, "protocol_committed_at": when}
