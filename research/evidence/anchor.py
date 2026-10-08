"""Future protocol-only public anchor verification; never creates a protocol/PR."""

from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

from .contracts import instant, require, sha


def github_merge_record(repository: str, number: int) -> dict[str, Any]:
    """Public unauthenticated HTTPS only; no credentials or caller-chosen endpoint."""
    require(
        re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository), "ANCHOR_REPOSITORY_INVALID"
    )
    require(type(number) is int and number > 0, "ANCHOR_PR_INVALID")
    url = f"https://api.github.com/repos/{repository}/pulls/{number}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "quant-trading-evidence-audit",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        require(response.url == url, "ANCHOR_TRANSPORT_INVALID")
        raw = response.read(1024 * 1024 + 1)
    require(len(raw) <= 1024 * 1024, "ANCHOR_SIZE_LIMIT")
    value = json.loads(raw)
    require(isinstance(value, dict), "ANCHOR_RECORD_INVALID")
    return dict(value)


def verify_lineage(
    root: Path,
    repository: str,
    number: int,
    protocol_path: str,
    protocol_bytes: bytes,
    *,
    result_prefix: str,
) -> dict[str, Any]:
    """Real external record is fetched here; hand-authored merged_at is not accepted.

    Main must already be fetched by the operator. A successful metadata audit is
    NOT a production signing identity or an automatic activation authorization.
    """
    require(
        re.fullmatch(r"config/research/[a-z0-9_-]+\.json", protocol_path), "PROTOCOL_PATH_INVALID"
    )
    require(re.fullmatch(r"reports/research/[a-z0-9_-]+/", result_prefix), "RESULT_PREFIX_INVALID")
    record = github_merge_record(repository, number)
    require(record.get("merged") is True and record.get("number") == number, "UNMERGED_PROTOCOL")
    require(
        record.get("base", {}).get("ref") == "main"
        and record.get("base", {}).get("repo", {}).get("full_name") == repository,
        "ANCHOR_REPOSITORY_INVALID",
    )
    merge = record.get("merge_commit_sha", "")
    require(re.fullmatch(r"[a-f0-9]{40}", merge), "ANCHOR_RECORD_INVALID")
    instant(record.get("merged_at", ""))

    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL)

    require(
        git("remote", "get-url", "origin").decode().strip()
        in {f"https://github.com/{repository}.git", f"https://github.com/{repository}"},
        "ANCHOR_REPOSITORY_INVALID",
    )
    require(
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", merge, "origin/main"],
            cwd=root,
            capture_output=True,
        ).returncode
        == 0,
        "ANCHOR_MAIN_ANCESTRY_INVALID",
    )
    require(git("show", f"{merge}:{protocol_path}") == protocol_bytes, "PROTOCOL_HASH_MISMATCH")
    first = (
        git("log", "--reverse", "--format=%H", merge, "--", protocol_path).decode().splitlines()[0]
    )
    require(git("show", f"{first}:{protocol_path}") == protocol_bytes, "PROTOCOL_HASH_MISMATCH")
    require(
        not git("log", "--format=%H", merge, "--", result_prefix).strip(), "RESULTS_BEFORE_ANCHOR"
    )
    changed = git("diff", "--name-only", merge + "^1", merge).decode().splitlines()
    require(
        changed and all(p == protocol_path or p.startswith("docs/") for p in changed),
        "PROTOCOL_ONLY_PR_REQUIRED",
    )
    return {
        "protocol_hash": sha(protocol_bytes),
        "merge_sha": merge,
        "first_protocol_commit": first,
        "merged_at": record["merged_at"],
        "main_ancestry": "VERIFIED",
        "exact_protocol_bytes": "VERIFIED",
        "result_history": "ABSENT",
        "transport": "GITHUB_HTTPS",
        "production_authority": "SIGNATURE_AUTHORITY_NOT_ESTABLISHED",
    }
