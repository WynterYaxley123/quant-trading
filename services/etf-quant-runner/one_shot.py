"""Stdlib-only one-shot transport: refresh -> gates -> Docker formal cycle.

Run with the existing isolated sidecar interpreter. No scheduler/time override.
"""
import argparse
import csv
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

import run as transport

REPO = Path(__file__).resolve().parents[2]
SHANGHAI = timezone(timedelta(hours=8))
CANDIDATE = REPO / "reports/etf_quant/etf_quant_v1_proxy_final_candidate_manifest.json"
PIT_REGISTRY = REPO / "reports/etf_quant/production_pit_evidence_registry_v1.json"


def checksum(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def certified_inputs(config):
    pins = {
        CANDIDATE: "e743bedb846a286c83870202c4514c80504c74409779b24f2968740914c2eb89",
        PIT_REGISTRY: "81cf6d44831736c81966d3f5275bb0fd0c7d56c4652320821e4fc34143f172dc",
        REPO / "strategies/etf_quant/config/verified_mappings_v1.json":
            "37a9b81cbc07c3255d18b514eef733d4497f98cca19ba855f8626031a66afb37",
        transport.external_file(config["pit_evidence"]):
            "ac730d6475528d494515eec841b7c49f8be55d667449fc8208f534058a907b79",
    }
    if any(checksum(p) != h for p, h in pins.items()):
        raise transport.GateError("FORMAL_CERTIFIED_INPUT_HASH_BLOCKER")
    extension = json.loads((REPO/"reports/etf_quant/autonomous_code_integrity_v1.json").read_bytes())
    if extension.get("candidate_sha256") != pins[CANDIDATE]:
        raise transport.GateError("FORMAL_IMPLEMENTATION_HASH_BLOCKER")
    for name, expected in extension["files"].items():
        leaf = transport.storage.contained(REPO, name)
        if checksum(leaf) != expected:
            raise transport.GateError("FORMAL_IMPLEMENTATION_HASH_BLOCKER")
    return pins


def run_once(config, *, now=None):
    # A separate metadata-only control root serializes refresh and initialization.
    control = transport.external_directory(config["control_root"])
    with transport.transport_lock(control):
        result = _run_once(config, control, now=now)
        # A real refresh can cross the closing boundary. Recheck once, never
        # sleep/schedule/replay and never allow a test clock to become live.
        if (now is None and result["status"] == "WAITING_FOR_MARKET_CLOSE"
                and datetime.now(timezone.utc).astimezone(SHANGHAI).time() >= time(15,5)):
            result = _run_once(config, control)
        result["shadow_runtime_armed"] = not result["status"].startswith("BLOCKED")
        result["shadow_start_gate"] = ("STARTED" if result["status"] in ("STARTED", "ALREADY_PROCESSED")
            else "ARMED_FOR_NEXT_ELIGIBLE_T" if result["shadow_runtime_armed"] else "BLOCKED_HARD")
        transport.storage.atomic_bytes(control / "latest_observation.json", transport.storage.json_bytes(result))
        return result


def _run_once(config, control, *, now=None):
    now = datetime.now(timezone.utc) if now is None else now
    commit = transport.committed_code()
    if transport.call(["git", "branch", "--show-current"], cwd=REPO).stdout.strip() != "integration/etf-quant-v1-shadow-autonomous-final":
        raise transport.GateError("FORMAL_INTEGRATION_BRANCH_REQUIRED")
    pins = certified_inputs(config)
    snapshot = transport.external_directory(config["snapshot"])
    export_pointer = control / "latest_export.json"
    if export_pointer.exists():
        pointer = json.loads(export_pointer.read_bytes())
        exports = transport.external_directory(config["export_root"])
        snapshot = transport.storage.contained(exports, pointer["snapshot_id"])
        if checksum(snapshot/"manifest.json") != pointer["manifest_sha256"]:
            raise transport.GateError("EXPORT_HASH_BLOCKER")
    meta = transport.verify_snapshot_files(snapshot)
    runtime = Path(config["runtime_root"])
    if not runtime.is_absolute() or any((p/".git").exists() for p in (runtime, *runtime.parents)):
        raise transport.GateError("EXPLICIT_EXTERNAL_PATH_REQUIRED")
    # Audit existing data before deciding to refresh. A committed same-T signal
    # is idempotent even if a provider would later return different bytes.
    if (runtime / "latest.json").exists():
        pointer = json.loads((runtime / "latest.json").read_bytes())
        manifest, bodies = transport.storage.read_generation(runtime/"runs", pointer)
        state = json.loads(bodies["state.json"])
        if not state.get("shadow_epoch"):
            raise transport.GateError("FORMAL_LEGACY_NAMESPACE_MIX_BLOCKER")
        if state["shadow_epoch"].get("candidate_hash") != pins[CANDIDATE]:
            raise transport.GateError("FORMAL_EPOCH_PROVENANCE_DRIFT_BLOCKER")
        if state["formal_signal"]["signal_date"] == now.astimezone(SHANGHAI).date().isoformat():
            return {"status": "ALREADY_PROCESSED", "shadow_epoch_created": True, "run_id": manifest["run_id"]}
    with (snapshot/"trading_calendar.csv").open(encoding="utf-8", newline="") as handle:
        calendar = {date.fromisoformat(r["trade_date"]): r["is_trading"] == "true" for r in csv.DictReader(handle)}
    local = now.astimezone(SHANGHAI)
    eligible_days = [d for d, trading in calendar.items() if trading and
                     (d < local.date() or d == local.date() and local.time() >= time(15,5))]
    if local.date() not in calendar:
        return {"status": "BLOCKED_DATA_INTEGRITY", "reason_code": "OFFICIAL_CALENDAR_REQUIRED",
                "classification": "LOCAL_ENGINEERING_FAILURE"}
    target = max(eligible_days) if eligible_days else None
    refresh = {"refresh_attempted": False}
    if target and meta["data_cutoff"] < str(target):
        sidecar = transport.external_directory(config["sidecar_root"])
        interpreter = sidecar / "venv/Scripts/python.exe"
        if not interpreter.exists(): interpreter = sidecar / "venv/bin/python"
        result = transport.call([interpreter, "-B", REPO/"services/cnequity-sidecar/forward.py",
            "--root", sidecar, "--source-config", transport.external_file(config["source_config"]),
            "--export-config", transport.external_file(config["export_config"]),
            "--target", target, "--after", meta["data_cutoff"]], timeout=3600)
        refresh = transport.result_json(result)
        receipt_id = now.strftime("%Y%m%dT%H%M%S") + "_" + transport.uuid4().hex[:12]
        transport.storage.publish_generation(control/"refreshes", receipt_id,
            {"refresh.json": transport.storage.json_bytes(refresh)}, {"created_at": now.isoformat()})
        finalized = refresh.get("latest_finalized") or (refresh if refresh.get("status") == "REFRESH_EXPORTED" else None)
        if finalized:
            exports = transport.external_directory(config["export_root"])
            admitted = transport.storage.contained(exports, finalized["snapshot_id"])
            if checksum(admitted / "manifest.json") != finalized["manifest_sha256"]:
                raise transport.GateError("EXPORT_HASH_BLOCKER")
            admitted_meta = transport.verify_snapshot_files(admitted)
            if not meta["data_cutoff"] <= admitted_meta["data_cutoff"] <= str(target):
                raise transport.GateError("FINALIZATION_MONOTONICITY_BLOCKER")
            snapshot, meta = admitted, admitted_meta
            transport.storage.atomic_bytes(export_pointer, transport.storage.json_bytes({
                "snapshot_id": snapshot.name, "manifest_sha256": checksum(snapshot/"manifest.json")}))
        if result.returncode or refresh.get("status") != "REFRESH_EXPORTED":
            status = refresh.get("status", "BLOCKED_CODE_INTEGRITY")
            if status == "WAITING_FOR_DATA": status = "WAITING_FOR_PROVIDER_DATA"
            return {"status": status, "reason_code": refresh.get("reason_code", "SOURCE_SESSION_INCOMPLETE"),
                    "data_cutoff": meta["data_cutoff"], "refresh": refresh}
    if not calendar[local.date()]:
        return {"status": "READY_NO_SIGNAL", "data_cutoff": meta["data_cutoff"], "refresh": refresh}
    if local.time() < time(15,5):
        return {"status": "WAITING_FOR_MARKET_CLOSE", "data_cutoff": meta["data_cutoff"], "refresh": refresh}
    if meta["data_cutoff"] != str(local.date()):
        return {"status": "WAITING_FOR_FINALIZED_DATA", "data_cutoff": meta["data_cutoff"], "refresh": refresh}
    profile = transport.external_file(config["profile"])
    profile_doc = json.loads(profile.read_bytes())
    if profile_doc.get("mode") != "SIMULATION_ONLY" or profile_doc.get("provider_identity") != transport.POLICY:
        raise transport.GateError("FROZEN_SOURCE_POLICY_REQUIRED")
    runtime = transport.external_directory(runtime)
    evidence_root = transport.external_directory(config["evidence_root"])
    source_root = transport.external_directory(config["pit_source_root"])
    docker = config["docker_executable"]
    snapshot_target = "/snapshot/" + snapshot.name
    mounts = [(REPO,"/workspace",True), (snapshot,snapshot_target,True), (runtime,"/shadow",False),
              (evidence_root,"/strict-evidence",True), (source_root,"/pit-sources",True),
              (profile,"/profile.json",True), (Path(config["pit_evidence"]),"/pit-book.json",True)]
    argv = [docker,"run","--rm"]
    for src, dest, readonly in mounts:
        argv += ["--mount", f"type=bind,source={src},target={dest}" + (",readonly" if readonly else "")]
    argv += ["-e","PYTHONDONTWRITEBYTECODE=1","-w","/workspace","quant-research:py3.12",
        "python","-B","-m","strategies.etf_quant.runtime.cli","one-shot",
        "--snapshot",snapshot_target,"--runtime","/shadow","--profile","/profile.json",
        "--registry","/workspace/strategies/etf_quant/config/verified_mappings_v1.json",
        "--evidence-root","/strict-evidence","--commit",commit,"--execution-policy","B40_WITH_CASH",
        "--pit-evidence","/pit-book.json","--pit-source-root","/pit-sources",
        "--candidate","/workspace/reports/etf_quant/etf_quant_v1_proxy_final_candidate_manifest.json",
        "--pit-registry","/workspace/reports/etf_quant/production_pit_evidence_registry_v1.json"]
    with transport.transport_lock(runtime):
        result = transport.call(argv, timeout=3600)
    response = transport.result_json(result)
    if result.returncode and response.get("status") not in ("BLOCKED", "BLOCKED_INTEGRITY"):
        raise transport.GateError("EXISTING_DOCKER_TRANSPORT_BLOCKER")
    if response.get("status") == "BLOCKED":
        response["status"] = "BLOCKED_INTEGRITY"
    return {**response, "refresh": refresh}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_once(json.loads(transport.external_file(args.config).read_bytes()))
    except transport.GateError as error:
        result = {"status": "BLOCKED_CODE_INTEGRITY" if error.code in
                  ("FORMAL_CERTIFIED_INPUT_HASH_BLOCKER", "FORMAL_IMPLEMENTATION_HASH_BLOCKER",
                   "CLEAN_COMMITTED_INTEGRATION_REQUIRED", "FORMAL_INTEGRATION_BRANCH_REQUIRED")
                  else "BLOCKED_DATA_INTEGRITY", "reason_code": error.code,
                  "classification": "LOCAL_ENGINEERING_FAILURE"}
    except Exception as error:
        result = {"status": "BLOCKED_CODE_INTEGRITY", "reason_code": "FORMAL_TRANSPORT_INPUT_BLOCKER",
                  "exception_class": type(error).__name__}
    print(transport.storage.json_bytes(result).decode())
    return 2 if result["status"].startswith("BLOCKED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
