"""Official-only append cycle. Readiness is date/quality-only; Validation never opens.

Docker: python scripts/data/update_shenwan_official.py {probe,stage,audit,apply,readiness,cycle}
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.providers import shenwan_official_update as update  # noqa: E402


def git_state(require_clean: bool) -> tuple[str, str]:
    # Windows bind mount ownership differs from mambauser. Trust only this user-
    # authorized repository for this invocation, never change global Git config.
    git = ["git", "-c", "safe.directory=" + str(ROOT)]
    head = subprocess.check_output([*git, "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    status = subprocess.check_output([*git, "status", "--porcelain"], cwd=ROOT, text=True)
    if require_clean and status:
        raise ValueError("SHENWAN_UPDATER_DIRTY_WORKTREE_BLOCKER")
    return head, status


def execute(mode: str, run_id: str, dry_run: bool) -> dict:
    head, _ = git_state(mode in {"cycle", "stage", "apply"})
    pre, before = update.current_readiness(ROOT)
    parent = update.read_parent(ROOT)
    result = {"schemaVersion": 1, "runId": run_id, "mode": mode, "dryRun": dry_run,
              "implementationCommit": head, "parentSnapshotId": parent["snapshotId"],
              "oldCutoff": parent["cutoff"], "oldRowCount": parent["rowCount"],
              "baselineReadiness": before["ready"], "updateAttempted": False, "updateApplied": False,
              "fetchStatus": "NOT_RUN", "overlapStatus": "NOT_RUN", "snapshotStatus": "NOT_RUN",
              "knownAnomalies": pre["knownAnomalies"]}
    if mode == "readiness":
        return before  # No network or file writes, not even a status artifact.
    health = None
    try:
        if mode in {"probe", "stage", "cycle"}:
            client = update.OfficialClient()
            client.retry_audit_path = ROOT / "data/manifests/shenwan_official_runs" / run_id / "network_retry_audit.jsonl"
            result["networkRetryAuditPath"] = str(client.retry_audit_path.relative_to(ROOT))
            result["networkRetryPolicy"] = {"maxAttempts": len(update.NETWORK_FETCH_BACKOFF) + 1,
                "backoffSeconds": list(update.NETWORK_FETCH_BACKOFF), "timeout": list(update.OFFICIAL_REQUEST_TIMEOUT)}
            result["networkRetryEvents"] = getattr(client, "network_retry_events", [])
            health = update.probe(client, parent)
            result["sourceHealth"] = health
            if health["status"] != "PASS":
                result.update(status="OFFICIAL_ENDPOINT_BLOCKED", blocker=health["errors"])
            elif mode == "probe":
                result["status"] = "SOURCE_HEALTH_PASS"
            else:
                # Writer emits counts only; no Windows-side staging reader.
                folder = update.stage(ROOT, parent, client, health, run_id,
                    progress=lambda event: print(json.dumps(event), file=sys.stderr, flush=True))
                result.update(stagingPath=str(folder.relative_to(ROOT)), fetchStatus="PASS", sectorsFetched=len(parent["names"]))
                if mode == "stage":
                    result["status"] = "STAGED"
                else:
                    audit_result = update.apply_stage(ROOT, folder, head, dry_run=True)
                    result.update(audit_result)
                    result["overlapStatus"] = "PASS" if audit_result["audit"]["totalRevisions"] == 0 else "FAIL"
                    if not dry_run and audit_result["status"] == "DRY_RUN_PASS":
                        result["updateAttempted"] = True
                        result.update(update.apply_stage(ROOT, folder, head))
                        result["snapshotStatus"] = "PUBLISHED_VERIFIED"
        elif mode in {"audit", "apply"}:
            folder = ROOT / "data/staging/shenwan_official" / run_id
            result["stagingPath"] = str(folder.relative_to(ROOT))
            if mode == "audit":
                audit, _ = update.audit_stage(ROOT, parent, folder)
                result.update(status=audit["status"], audit=audit)
            else:
                result["updateAttempted"] = not dry_run
                result.update(update.apply_stage(ROOT, folder, head, dry_run=dry_run))
        else:
            raise ValueError("CLI_MODE_BLOCKER")
    except Exception as error:
        result.update(status="STAGING_IO_BLOCKER" if isinstance(error, update.StagingIOBlocker) else
                      "NETWORK_FETCH_BLOCKER" if isinstance(error, update.NetworkFetchBlocker) else
                      "OFFICIAL_ENDPOINT_BLOCKED" if mode in {"probe", "stage", "cycle"}
                      and not result["updateAttempted"] and result["fetchStatus"] == "NOT_RUN" else "BLOCKED",
                      blocker=type(error).__name__ + ": " + str(error))
        folder = ROOT / "data/staging/shenwan_official" / run_id
        failure = folder / "failure.json"
        metadata = failure if failure.exists() else folder / "stage.json"
        if metadata.exists():
            info = update.read_json(metadata)
            result.update(stagingPath=str(folder.relative_to(ROOT)), sectorsFetched=len(info["files"]), fetchStatus="FAIL")
        # If failure happened after pointer commit, do not misrepresent it as a
        # rejected/no-write update. Re-audit accepted state and preserve evidence.
        current = update.read_parent(ROOT)
        result["currentSnapshotAfterFailure"] = current["snapshotId"]
        result["publicationOccurred"] = current["snapshotId"] != parent["snapshotId"]
    _, after = update.current_readiness(ROOT)
    result.update(readiness=after, readinessBefore=before["ready"], readinessAfter=after["ready"],
                  readinessDelta=after["ready"] - before["ready"], currentSnapshotId=after["snapshotId"],
                  currentCutoff=after["cutoff"], historicalPrefixUnchanged=True,
                  validationOpened=False, validationPerformanceRead=False,
                  validationResultsGenerated=False, finalOosRead=False)
    run_path = ROOT / "data/manifests/shenwan_official_runs" / run_id / "result.json"
    update.durable_bytes(run_path, update.encoded(result))
    result["resultPath"] = str(run_path.relative_to(ROOT))
    if health is None and mode in {"probe", "stage", "cycle"}:
        health = {"provider": update.PROVIDER, "sourceHost": update.HOST,
                  "catalogEndpoint": update.source_url("current"), "trendEndpoint": update.source_url("trend"),
                  "tlsMode": None, "tlsChainComplete": None, "intermediatePinned": None,
                  "intermediateSha256": None, "sourceReachable": False, "schemaCompatible": None,
                  "latestFinalizedSourceDate": None, "status": "BLOCKED", "errors": [result.get("blocker")]}
    if health is not None:
        previous_path = ROOT / "data/manifests/shenwan_official_source_status.json"
        previous = update.read_json(previous_path) if previous_path.exists() else {}
        status = {**health, "lastCheckedAt": update.now(), "lastSuccessfulUpdateAt": update.now()
                  if result["updateApplied"] else previous.get("lastSuccessfulUpdateAt"),
                  "currentSnapshotId": after["snapshotId"], "currentCutoff": after["cutoff"],
                  "readinessReady": after["ready"], "readinessTotal": 60,
                  "frozenSectorCoverage": result.get("sectorsFetched"), "lastRunId": run_id,
                  "lastRunResult": result["status"], "validationOpened": False}
        update.atomic_json(previous_path, status)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["probe", "stage", "audit", "apply", "readiness", "cycle"])
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run_id = args.run_id or "sw_" + update.now()[:19].replace("-", "").replace(":", "").replace("T", "_") + "_" + uuid4().hex[:8]
    if args.mode in {"audit", "apply"} and args.run_id is None:
        parser.error("audit/apply require --run-id from an existing STAGED run")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", run_id):
        parser.error("invalid run id")
    result = execute(args.mode, run_id, args.dry_run)
    if args.mode == "readiness":
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    compact = {key: value for key, value in result.items() if key not in {"audit", "readiness", "sourceHealth"}}
    if "audit" in result:
        compact["auditSummary"] = {key: value for key, value in result["audit"].items() if key not in {"perSector", "sourceHealth"}}
    if "sourceHealth" in result:
        compact["sourceHealthSummary"] = {key: value for key, value in result["sourceHealth"].items() if key not in {"requests", "catalogRequests"}}
    print(json.dumps(compact, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["status"] in {"SOURCE_HEALTH_PASS", "STAGED", "PASS", "DRY_RUN_PASS", "UPDATE_APPLIED", "NO_NEW_CANONICAL_DATA"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
