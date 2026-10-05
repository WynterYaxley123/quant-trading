"""Stdlib-only one-shot transport: refresh -> gates -> Docker formal cycle.

Run with the existing isolated sidecar interpreter. No scheduler/time override.
"""

import argparse
import csv
import hashlib
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import run as transport
from docker_mounts import MountInputError, bind_mount, reference_name
from docker_refresh import refresh_command, refresh_v2_bars

REPO = Path(__file__).resolve().parents[2]
SHANGHAI = timezone(timedelta(hours=8))
CANDIDATE = REPO / "reports/etf_quant/etf_quant_v1_proxy_final_candidate_manifest.json"
PIT_REGISTRY = REPO / "reports/etf_quant/production_pit_evidence_registry_v1.json"


def checksum(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def certified_implementation():
    """Verify only standard-library certificate/hash code before any refresh."""
    integrity_spec = transport.importlib.util.spec_from_file_location(
        "etf_implementation", REPO / "strategies/etf_quant/runtime/implementation.py"
    )
    if integrity_spec is None or integrity_spec.loader is None:
        raise transport.GateError("FORMAL_IMPLEMENTATION_HASH_BLOCKER")
    implementation = transport.importlib.util.module_from_spec(integrity_spec)
    integrity_spec.loader.exec_module(implementation)
    try:
        return implementation.verify_implementation(REPO)
    except ValueError as error:
        raise transport.GateError("FORMAL_IMPLEMENTATION_HASH_BLOCKER") from error


def certified_inputs(config):
    pins = {
        CANDIDATE: "e743bedb846a286c83870202c4514c80504c74409779b24f2968740914c2eb89",
        PIT_REGISTRY: "81cf6d44831736c81966d3f5275bb0fd0c7d56c4652320821e4fc34143f172dc",
        REPO
        / "strategies/etf_quant/config/verified_mappings_v1.json": "37a9b81cbc07c3255d18b514eef733d4497f98cca19ba855f8626031a66afb37",
        transport.external_file(
            config["pit_evidence"]
        ): "ac730d6475528d494515eec841b7c49f8be55d667449fc8208f534058a907b79",
    }
    if any(checksum(p) != h for p, h in pins.items()):
        raise transport.GateError("FORMAL_CERTIFIED_INPUT_HASH_BLOCKER")
    extension = json.loads(
        (REPO / "reports/etf_quant/autonomous_code_integrity_v1.json").read_bytes()
    )
    if extension.get("candidate_sha256") != pins[CANDIDATE]:
        raise transport.GateError("FORMAL_IMPLEMENTATION_HASH_BLOCKER")
    for name, expected in certified_implementation().items():
        leaf = transport.storage.contained(REPO, name)
        if checksum(leaf) != expected:
            raise transport.GateError("FORMAL_IMPLEMENTATION_HASH_BLOCKER")
    model = json.loads(
        (REPO / "strategies/etf_quant/config/common_model_universe_v1.json").read_bytes()
    )
    reference = transport.external_directory(config["model_reference_snapshot"])
    try:
        reference_name(reference.name)
    except MountInputError as error:
        raise transport.GateError("FORMAL_MODEL_REFERENCE_BINDING_BLOCKER") from error
    if (
        reference.name != model["reference_snapshot_id"]
        or checksum(reference / "manifest.json") != model["reference_manifest_sha256"]
        or checksum(reference / "industry_membership.csv") != model["reference_membership_sha256"]
    ):
        raise transport.GateError("FORMAL_MODEL_REFERENCE_BINDING_BLOCKER")
    return pins


def run_once(config, *, now=None):
    # A separate metadata-only control root serializes refresh and initialization.
    control = transport.external_directory(config["control_root"])
    with transport.transport_lock(control):
        version = config.get("strategy_version", "ETF_QUANT_V1")
        if version not in ("ETF_QUANT_V1", "ETF_QUANT_V2"):
            raise transport.GateError("UNKNOWN_STRATEGY_VERSION")
        operation = _run_v2 if version == "ETF_QUANT_V2" else _run_once
        result = operation(config, control, now=now)
        # A real refresh can cross the closing boundary. Recheck once, never
        # sleep/schedule/replay and never allow a test clock to become live.
        if (
            now is None
            and result["status"] == "WAITING_FOR_MARKET_CLOSE"
            and datetime.now(timezone.utc).astimezone(SHANGHAI).time() >= time(15, 5)
        ):
            result = operation(config, control)
        result["shadow_runtime_armed"] = not result["status"].startswith("BLOCKED")
        result.setdefault("strategy_version", version)
        result["observed_at"] = datetime.now(timezone.utc).isoformat()
        result["shadow_start_gate"] = (
            "STARTED"
            if result["status"] in ("STARTED", "ALREADY_PROCESSED")
            else "ARMED_FOR_NEXT_ELIGIBLE_T"
            if result["shadow_runtime_armed"]
            else "BLOCKED_HARD"
        )
        transport.storage.atomic_bytes(
            control / "latest_observation.json", transport.storage.json_bytes(result)
        )
        return result


def _run_v2(config, control, *, now=None):
    if now is not None:
        raise transport.GateError("LIVE_V2_CLOCK_OVERRIDE_DENIED")
    commit = transport.committed_code()
    merged = transport.call(
        ["git", "--no-optional-locks", "rev-parse", "origin/main"], cwd=REPO, timeout=30
    )
    if merged.returncode or merged.stdout.strip() != commit:
        raise transport.GateError("V2_MERGED_MAIN_REQUIRED")
    files = certified_implementation()
    release_path = REPO / "strategies/etf_quant_v2/config/release.json"
    if checksum(release_path) != files.get("strategies/etf_quant_v2/config/release.json"):
        raise transport.GateError("FORMAL_IMPLEMENTATION_HASH_BLOCKER")
    release = json.loads(release_path.read_bytes())
    local = datetime.now(timezone.utc).astimezone(SHANGHAI)
    runtime = transport.external_directory(config["runtime_root"])
    if (runtime / "latest.json").exists():
        pointer = json.loads(transport.storage.contained(runtime, "latest.json").read_bytes())
        _, bodies = transport.storage.read_generation(runtime / "runs", pointer)
        if set(bodies) != {"state.json", "view.json"}:
            raise transport.GateError("V2_RUNTIME_INTEGRITY_BLOCKER")
        state = json.loads(bodies["state.json"])
        if (
            state.get("strategy_version") != "ETF_QUANT_V2"
            or state.get("mode") != "SIMULATION_ONLY"
            or state.get("broker_enabled") is not False
            or state.get("real_order_path") is not False
            or state.get("portfolio", {}).get("initial_cash") != "10000"
            or any(
                state.get(k) != release[k]
                for k in ("candidate_sha256", "registry_sha256", "release_sha256")
            )
        ):
            raise transport.GateError("V2_RUNTIME_INTEGRITY_BLOCKER")
        signal_day = state["signals"][-1]["signal_date"]
        if signal_day > str(local.date()):
            raise transport.GateError("FORWARD_MONOTONIC_SIGNAL_REQUIRED")
        if signal_day == str(local.date()):
            return {
                "status": "ALREADY_PROCESSED",
                "strategy_version": "ETF_QUANT_V2",
                "code_commit": commit,
                "run_id": pointer["run_id"],
                "view": json.loads(bodies["view.json"]),
            }
    snapshot = transport.external_directory(config["snapshot"])
    pointer_path = control / "latest_export.json"
    if pointer_path.exists():
        pointer = json.loads(pointer_path.read_bytes())
        snapshot = transport.storage.contained(
            transport.external_directory(config["export_root"]), pointer["snapshot_id"]
        )
        if checksum(snapshot / "manifest.json") != pointer["manifest_sha256"]:
            raise transport.GateError("EXPORT_HASH_BLOCKER")
    meta = transport.verify_snapshot_files(snapshot)
    with (snapshot / "trading_calendar.csv").open(encoding="utf-8", newline="") as handle:
        calendar = {
            date.fromisoformat(r["trade_date"]): r["is_trading"] == "true"
            for r in csv.DictReader(handle)
        }
    if local.date() not in calendar:
        return {
            "status": "BLOCKED_DATA_INTEGRITY",
            "strategy_version": "ETF_QUANT_V2",
            "reason_code": "OFFICIAL_CALENDAR_REQUIRED",
        }
    sessions = [d for d, trading in calendar.items() if trading]
    completed = [
        d for d in sessions if d < local.date() or d == local.date() and local.time() >= time(15, 5)
    ]
    if completed and meta["data_cutoff"] < str(max(completed)):
        refresh_result = transport.call(
            refresh_command(config, max(completed), meta["data_cutoff"]), timeout=3600
        )
        refresh = transport.result_json(refresh_result)
        finalized = refresh.get("latest_finalized") or (
            refresh if refresh.get("status") == "REFRESH_EXPORTED" else None
        )
        if finalized:
            snapshot = transport.storage.contained(
                transport.external_directory(config["export_root"]), finalized["snapshot_id"]
            )
            if checksum(snapshot / "manifest.json") != finalized["manifest_sha256"]:
                raise transport.GateError("EXPORT_HASH_BLOCKER")
            admitted_meta = transport.verify_snapshot_files(snapshot)
            if not meta["data_cutoff"] <= admitted_meta["data_cutoff"] <= str(max(completed)):
                raise transport.GateError("FINALIZATION_MONOTONICITY_BLOCKER")
            meta = admitted_meta
            transport.storage.atomic_bytes(pointer_path, transport.storage.json_bytes(finalized))
        if refresh_result.returncode or refresh.get("status") != "REFRESH_EXPORTED":
            return {
                "status": refresh.get("status", "WAITING_FOR_PROVIDER_DATA"),
                "strategy_version": "ETF_QUANT_V2",
                "reason_code": refresh.get("reason_code", "SOURCE_SESSION_INCOMPLETE"),
                "data_cutoff": meta["data_cutoff"],
            }
    if local.date() in sessions and local.time() >= time(15, 5):
        refresh_v2_bars(config, snapshot)
    image = config.get("developer_image", "quant-trading-forward:local")
    if image.startswith("quant-research"):
        raise transport.GateError("INDEPENDENT_V2_DEVELOPER_IMAGE_REQUIRED")
    config_file = transport.external_file(config["container_config"])
    expected_config = {
        "strategy_version": "ETF_QUANT_V2",
        "snapshot": "/snapshot",
        "warmup_panel": "/warmup",
        "liquidity_root": "/liquidity",
        "exposure_vectors": "/vectors.json",
        "runtime_root": "/shadow-v2",
        "control_root": "/control-v2",
    }
    if json.loads(config_file.read_bytes()) != expected_config:
        raise transport.GateError("V2_CONTAINER_NAMESPACE_BINDING_REQUIRED")
    mounts = [(REPO, "/workspace", True), (config_file, "/config.json", True)]
    for field, target, readonly in (
        ("snapshot", "/snapshot", True),
        ("warmup_panel", "/warmup", True),
        ("liquidity_root", "/liquidity", True),
        ("exposure_vectors", "/vectors.json", True),
        ("runtime_root", "/shadow-v2", False),
        ("v2_control_root", "/control-v2", False),
    ):
        path = (
            snapshot
            if field == "snapshot"
            else transport.external_file(config[field])
            if field == "exposure_vectors"
            else transport.external_directory(config[field])
        )
        mounts.append((path, target, readonly))
    argv = [config.get("docker_executable", "docker"), "run", "--rm", "--network", "none"]
    for source, target, readonly in mounts:
        argv += bind_mount(source, target, readonly=readonly)
    argv += [
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-e",
        "PYTHONPATH=/workspace",
        "-w",
        "/workspace",
        image,
        "python",
        "-B",
        "services/etf-quant-runner/versioned.py",
        "--config",
        "/config.json",
        "--commit",
        commit,
    ]
    result = transport.call(argv, timeout=3600)
    response = transport.result_json(result)
    if result.returncode:
        raise transport.GateError("V2_FORMAL_DOCKER_CYCLE_BLOCKER")
    return response


def _run_once(config, control, *, now=None):
    now = datetime.now(timezone.utc) if now is None else now
    commit = transport.committed_code()
    if not transport.formal_branch_allowed(
        transport.call(["git", "branch", "--show-current"], cwd=REPO).stdout.strip(), commit
    ):
        raise transport.GateError("FORMAL_INTEGRATION_BRANCH_REQUIRED")
    pins = certified_inputs(config)
    snapshot = transport.external_directory(config["snapshot"])
    export_pointer = control / "latest_export.json"
    if export_pointer.exists():
        pointer = json.loads(export_pointer.read_bytes())
        exports = transport.external_directory(config["export_root"])
        snapshot = transport.storage.contained(exports, pointer["snapshot_id"])
        if checksum(snapshot / "manifest.json") != pointer["manifest_sha256"]:
            raise transport.GateError("EXPORT_HASH_BLOCKER")
    meta = transport.verify_snapshot_files(snapshot)
    runtime = Path(config["runtime_root"])
    if not runtime.is_absolute() or any((p / ".git").exists() for p in (runtime, *runtime.parents)):
        raise transport.GateError("EXPLICIT_EXTERNAL_PATH_REQUIRED")
    # Audit existing data before deciding to refresh. A committed same-T signal
    # is idempotent even if a provider would later return different bytes.
    if (runtime / "latest.json").exists():
        pointer = json.loads((runtime / "latest.json").read_bytes())
        manifest, bodies = transport.storage.read_generation(runtime / "runs", pointer)
        state = json.loads(bodies["state.json"])
        if not state.get("shadow_epoch"):
            raise transport.GateError("FORMAL_LEGACY_NAMESPACE_MIX_BLOCKER")
        if state["shadow_epoch"].get("candidate_hash") != pins[CANDIDATE]:
            raise transport.GateError("FORMAL_EPOCH_PROVENANCE_DRIFT_BLOCKER")
        if state["formal_signal"]["signal_date"] == now.astimezone(SHANGHAI).date().isoformat():
            return {
                "status": "ALREADY_PROCESSED",
                "shadow_epoch_created": True,
                "run_id": manifest["run_id"],
            }
    with (snapshot / "trading_calendar.csv").open(encoding="utf-8", newline="") as handle:
        calendar = {
            date.fromisoformat(r["trade_date"]): r["is_trading"] == "true"
            for r in csv.DictReader(handle)
        }
    local = now.astimezone(SHANGHAI)
    eligible_days = [
        d
        for d, trading in calendar.items()
        if trading and (d < local.date() or d == local.date() and local.time() >= time(15, 5))
    ]
    if local.date() not in calendar:
        return {
            "status": "BLOCKED_DATA_INTEGRITY",
            "reason_code": "OFFICIAL_CALENDAR_REQUIRED",
            "classification": "LOCAL_ENGINEERING_FAILURE",
        }
    target = max(eligible_days) if eligible_days else None
    refresh = {"refresh_attempted": False}
    if target and meta["data_cutoff"] < str(target):
        if config.get("docker_source_root"):
            command = refresh_command(config, target, meta["data_cutoff"])
        else:
            sidecar = transport.external_directory(config["sidecar_root"])
            interpreter = sidecar / "venv/Scripts/python.exe"
            if not interpreter.exists():
                interpreter = sidecar / "venv/bin/python"
            command = [
                interpreter,
                "-B",
                REPO / "services/cnequity-sidecar/forward.py",
                "--root",
                sidecar,
                "--source-config",
                transport.external_file(config["source_config"]),
                "--export-config",
                transport.external_file(config["export_config"]),
                "--target",
                target,
                "--after",
                meta["data_cutoff"],
            ]
        result = transport.call(command, timeout=3600)
        refresh = transport.result_json(result)
        receipt_id = now.strftime("%Y%m%dT%H%M%S") + "_" + transport.uuid4().hex[:12]
        transport.storage.publish_generation(
            control / "refreshes",
            receipt_id,
            {"refresh.json": transport.storage.json_bytes(refresh)},
            {"created_at": now.isoformat()},
        )
        finalized = refresh.get("latest_finalized") or (
            refresh if refresh.get("status") == "REFRESH_EXPORTED" else None
        )
        if finalized:
            exports = transport.external_directory(config["export_root"])
            admitted = transport.storage.contained(exports, finalized["snapshot_id"])
            if checksum(admitted / "manifest.json") != finalized["manifest_sha256"]:
                raise transport.GateError("EXPORT_HASH_BLOCKER")
            admitted_meta = transport.verify_snapshot_files(admitted)
            if not meta["data_cutoff"] <= admitted_meta["data_cutoff"] <= str(target):
                raise transport.GateError("FINALIZATION_MONOTONICITY_BLOCKER")
            snapshot, meta = admitted, admitted_meta
            transport.storage.atomic_bytes(
                export_pointer,
                transport.storage.json_bytes(
                    {
                        "snapshot_id": snapshot.name,
                        "manifest_sha256": checksum(snapshot / "manifest.json"),
                    }
                ),
            )
        if result.returncode or refresh.get("status") != "REFRESH_EXPORTED":
            status = refresh.get("status", "BLOCKED_CODE_INTEGRITY")
            if status == "WAITING_FOR_DATA":
                status = "WAITING_FOR_PROVIDER_DATA"
            return {
                "status": status,
                "reason_code": refresh.get("reason_code", "SOURCE_SESSION_INCOMPLETE"),
                "data_cutoff": meta["data_cutoff"],
                "refresh": refresh,
            }
    if not calendar[local.date()]:
        return {"status": "READY_NO_SIGNAL", "data_cutoff": meta["data_cutoff"], "refresh": refresh}
    if local.time() < time(15, 5):
        return {
            "status": "WAITING_FOR_MARKET_CLOSE",
            "data_cutoff": meta["data_cutoff"],
            "refresh": refresh,
        }
    if meta["data_cutoff"] != str(local.date()):
        return {
            "status": "WAITING_FOR_FINALIZED_DATA",
            "data_cutoff": meta["data_cutoff"],
            "refresh": refresh,
        }
    profile = transport.external_file(config["profile"])
    profile_doc = json.loads(profile.read_bytes())
    if (
        profile_doc.get("mode") != "SIMULATION_ONLY"
        or profile_doc.get("provider_identity") != transport.POLICY
    ):
        raise transport.GateError("FROZEN_SOURCE_POLICY_REQUIRED")
    runtime = transport.external_directory(runtime)
    evidence_root = transport.external_directory(config["evidence_root"])
    source_root = transport.external_directory(config["pit_source_root"])
    model_reference = transport.external_directory(config["model_reference_snapshot"])
    docker = config["docker_executable"]
    snapshot_target = "/snapshot/" + snapshot.name
    mounts = [
        (REPO, "/workspace", True),
        (snapshot, snapshot_target, True),
        (runtime, "/shadow", False),
        (evidence_root, "/strict-evidence", True),
        (source_root, "/pit-sources", True),
        (profile, "/profile.json", True),
        (Path(config["pit_evidence"]), "/pit-book.json", True),
        (model_reference, "/model-reference/" + model_reference.name, True),
    ]
    argv = [docker, "run", "--rm", "--network", "none"]
    for src, dest, readonly in mounts:
        try:
            argv += bind_mount(src, dest, readonly=readonly)
        except MountInputError as error:
            raise transport.GateError("DOCKER_MOUNT_INPUT_BLOCKER") from error
    argv += [
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-w",
        "/workspace",
        "quant-research:py3.12",
        "python",
        "-B",
        "-m",
        "strategies.etf_quant.runtime.cli",
        "one-shot",
        "--snapshot",
        snapshot_target,
        "--runtime",
        "/shadow",
        "--profile",
        "/profile.json",
        "--registry",
        "/workspace/strategies/etf_quant/config/verified_mappings_v1.json",
        "--evidence-root",
        "/strict-evidence",
        "--commit",
        commit,
        "--execution-policy",
        "B40_WITH_CASH",
        "--pit-evidence",
        "/pit-book.json",
        "--pit-source-root",
        "/pit-sources",
        "--candidate",
        "/workspace/reports/etf_quant/etf_quant_v1_proxy_final_candidate_manifest.json",
        "--pit-registry",
        "/workspace/reports/etf_quant/production_pit_evidence_registry_v1.json",
    ]
    argv += ["--model-reference-snapshot", "/model-reference/" + model_reference.name]
    with transport.transport_lock(runtime):
        result = transport.call(argv, timeout=3600)
    response = transport.result_json(result)
    if result.returncode and response.get("status") not in ("BLOCKED", "BLOCKED_INTEGRITY"):
        raise transport.GateError("EXISTING_DOCKER_TRANSPORT_BLOCKER")
    if response.get("status") == "BLOCKED":
        response["status"] = "BLOCKED_INTEGRITY"
    return {**response, "refresh": refresh}


def observe_once(config: dict[str, Any]) -> dict[str, Any]:
    """A failed version returns a bounded receipt without stopping its sibling."""
    try:
        result = run_once(config)
    except transport.GateError as error:
        result = {
            "status": "BLOCKED_CODE_INTEGRITY"
            if error.code
            in (
                "FORMAL_CERTIFIED_INPUT_HASH_BLOCKER",
                "FORMAL_IMPLEMENTATION_HASH_BLOCKER",
                "CLEAN_COMMITTED_INTEGRATION_REQUIRED",
                "FORMAL_INTEGRATION_BRANCH_REQUIRED",
                "FORMAL_MODEL_REFERENCE_BINDING_BLOCKER",
            )
            else "BLOCKED_DATA_INTEGRITY",
            "reason_code": error.code,
            "classification": "LOCAL_ENGINEERING_FAILURE",
        }
    except Exception as error:
        result = {
            "status": "BLOCKED_CODE_INTEGRITY",
            "reason_code": "FORMAL_TRANSPORT_INPUT_BLOCKER",
            "exception_class": type(error).__name__,
        }
    result.setdefault("strategy_version", config.get("strategy_version", "ETF_QUANT_V1"))
    return result


def run_versions(configs: list[dict[str, Any]]) -> dict[str, Any]:
    """Sequential calls to the canonical runner, with disjoint account/control roots."""
    versions: set[str] = set()
    owned: list[Path] = []
    for config in configs:
        version = config.get("strategy_version", "ETF_QUANT_V1")
        if version not in ("ETF_QUANT_V1", "ETF_QUANT_V2") or version in versions:
            raise transport.GateError("DISTINCT_STRATEGY_VERSIONS_REQUIRED")
        versions.add(version)
        roots = [Path(config[k]).resolve() for k in ("control_root", "runtime_root")]
        if any(not Path(config[k]).is_absolute() for k in ("control_root", "runtime_root")):
            raise transport.GateError("EXPLICIT_EXTERNAL_PATH_REQUIRED")
        if roots[0].is_relative_to(roots[1]) or roots[1].is_relative_to(roots[0]):
            raise transport.GateError("CONTROL_AND_ACCOUNT_MUST_BE_DISJOINT")
        if version == "ETF_QUANT_V2" and "v2_control_root" in config:
            if not Path(config["v2_control_root"]).is_absolute():
                raise transport.GateError("EXPLICIT_EXTERNAL_PATH_REQUIRED")
            roots.append(Path(config["v2_control_root"]).resolve())
        if any(a.is_relative_to(b) or b.is_relative_to(a) for a in roots for b in owned):
            raise transport.GateError("V1_AND_V2_STATE_MUST_BE_DISJOINT")
        owned.extend(roots)
    results = [observe_once(config) for config in configs]
    return {
        "status": "BLOCKED_VERSION"
        if any(r["status"].startswith("BLOCKED") for r in results)
        else "VERSIONS_OBSERVED",
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True, action="append")
    args = parser.parse_args()
    try:
        configs = [json.loads(transport.external_file(p).read_bytes()) for p in args.config]
        result = observe_once(configs[0]) if len(configs) == 1 else run_versions(configs)
    except Exception as error:
        result = {
            "status": "BLOCKED_CODE_INTEGRITY",
            "reason_code": error.code
            if isinstance(error, transport.GateError)
            else "FORMAL_TRANSPORT_INPUT_BLOCKER",
            "exception_class": type(error).__name__,
        }
    print(transport.storage.json_bytes(result).decode())
    return 2 if result["status"].startswith("BLOCKED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
