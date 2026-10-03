"""Host file-transport only. All factors/models/accounting run in existing Docker.

Manual invocation; no scheduler, network fallback, credentials, or order API.
No market data is read by host model code. The shared storage module is stdlib.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "etf_transport_storage", REPO / "strategies/etf_quant/runtime/storage.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("TRANSPORT_STORAGE_MODULE_UNAVAILABLE")
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)  # Only filesystem/hash utilities; no quant imports.
GateError = storage.GateError
POLICY = json.loads(Path(__file__).with_name("source-policy.json").read_bytes())
HASH = re.compile(r"[a-f0-9]{64}")


def external_file(path):
    path = Path(path)
    if not path.is_absolute():
        raise GateError("EXPLICIT_EXTERNAL_PATH_REQUIRED")
    result = path.resolve(strict=True)
    if not result.is_file() or any((p / ".git").exists() for p in result.parents):
        raise GateError("EXPLICIT_EXTERNAL_PATH_REQUIRED")
    return result


def external_directory(path):
    path = Path(path)
    if not path.is_absolute():
        raise GateError("EXPLICIT_EXTERNAL_PATH_REQUIRED")
    return storage.external_root(path)


def call(argv, *, cwd=None, timeout=900):
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    try:
        result = subprocess.run(
            [str(v) for v in argv],
            cwd=cwd,
            env=env,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        # Structured stdout stays STRICT UTF-8. Native upstream diagnostics
        # sometimes mix Windows encodings; preserve those bytes as escapes
        # instead of letting a stderr reader crash and lose the JSON receipt.
        return subprocess.CompletedProcess(
            result.args,
            result.returncode,
            result.stdout.decode("utf-8"),
            result.stderr.decode("utf-8", errors="backslashreplace"),
        )
    except UnicodeDecodeError as error:
        raise GateError("TRANSPORT_CHILD_ENCODING_BLOCKER") from error
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GateError(
            "TRANSPORT_PROCESS_BLOCKER", {"exception_class": type(error).__name__}
        ) from error


def result_json(result):
    try:
        value = json.loads(result.stdout)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, TypeError) as error:
        raise GateError("TRANSPORT_CHILD_RESPONSE_BLOCKER") from error


def committed_code(repo=REPO):
    branch = call(["git", "--no-optional-locks", "branch", "--show-current"], cwd=repo, timeout=30)
    head = call(["git", "--no-optional-locks", "rev-parse", "HEAD"], cwd=repo, timeout=30)
    status = call(["git", "--no-optional-locks", "status", "--porcelain"], cwd=repo, timeout=30)
    if (
        any(r.returncode for r in (branch, head, status))
        or branch.stdout.strip()
        not in ("integration/etf-quant-v1", "integration/etf-quant-v1-shadow-autonomous-final")
        or status.stdout.strip()
        or not re.fullmatch(r"[0-9a-f]{40}", head.stdout.strip())
    ):
        raise GateError("CLEAN_COMMITTED_INTEGRATION_REQUIRED")
    return head.stdout.strip()


@contextmanager
def lock_guard(root):
    """Kernel-released mutex for create/recover/release; no stale guard owner."""
    with (root / ".transport.guard").open("a+b") as guard:
        guard.seek(0)
        if not guard.read(1):
            guard.write(b"0")
            guard.flush()
        guard.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(guard.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise GateError("CONCURRENT_OR_INTERRUPTED_TRANSPORT_BLOCKER") from error
        try:
            yield
        finally:
            guard.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(guard.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(guard, fcntl.LOCK_UN)


def process_owner(pid):
    """Only an OS-proven absent owner permits recovery; denial is unknown."""
    if not isinstance(pid, int) or pid <= 0:
        return "UNKNOWN"
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return "DEAD" if ctypes.get_last_error() == 87 else "UNKNOWN"
        code = wintypes.DWORD()
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        known = kernel.GetExitCodeProcess(handle, ctypes.byref(code))
        status = ("ALIVE" if code.value == 259 else "DEAD") if known else "UNKNOWN"
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle(handle)
        return status
    try:
        os.kill(pid, 0)
        return "ALIVE"
    except ProcessLookupError:
        return "DEAD"
    except PermissionError:
        return "UNKNOWN"


@contextmanager
def transport_lock(root):
    path = root / ".transport.lock"
    payload = storage.json_bytes(
        {
            "pid": os.getpid(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "scope": "ETF_QUANT_TRANSPORT_V1",
            "root_file_id": root.stat().st_ino,
            "nonce": uuid4().hex,
        }
    )
    with lock_guard(root):
        if path.exists():
            try:
                owner = json.loads(path.read_bytes())
                known = (
                    set(owner) == {"pid", "created_at"}
                    or owner.get("scope") == "ETF_QUANT_TRANSPORT_V1"
                    and owner.get("root_file_id") == root.stat().st_ino
                )
                if not known or process_owner(owner.get("pid")) != "DEAD":
                    raise ValueError()
            except (ValueError, TypeError, OSError):
                raise GateError("CONCURRENT_OR_INTERRUPTED_TRANSPORT_BLOCKER")
            storage.atomic_bytes(
                root / "last_lock_recovery.json",
                storage.json_bytes(
                    {
                        "reason_code": "OS_PROVEN_DEAD_OWNER",
                        "prior_pid": owner["pid"],
                        "recovered_at": datetime.now(timezone.utc).isoformat(),
                    }
                ),
            )
            path.unlink()
        handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        with lock_guard(root):
            if path.exists() and path.read_bytes() == payload:
                path.unlink()


def verify_snapshot_files(folder):
    folder = folder.resolve(strict=True)
    manifest = json.loads(storage.contained(folder, "manifest.json").read_bytes())
    if (
        not HASH.fullmatch(folder.name)
        or manifest.get("snapshot_id") != folder.name
        or any(manifest.get(k) != v for k, v in POLICY.items())
        or manifest.get("schema_version") != "1.0.0"
    ):
        raise GateError("SOURCE_POLICY_OR_SNAPSHOT_BLOCKER")
    expected = {
        n + ".csv"
        for n in (
            "trading_calendar",
            "stock_bars",
            "industry_membership",
            "etf_bars",
            "instruments",
            "trading_status",
            "benchmark_csi300",
        )
    }
    if set(manifest.get("files", {})) != expected:
        raise GateError("SOURCE_POLICY_OR_SNAPSHOT_BLOCKER")
    # Hash streaming, not host quant parsing. Docker repeats schema/maturity gates.
    import hashlib

    for name, checksum in manifest["files"].items():
        path = storage.contained(folder, name)
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != checksum:
            raise GateError("EXPORT_HASH_BLOCKER")
    return manifest


def copy_generation(source, destination, pointer, required):
    manifest, files = storage.read_generation(source, pointer)
    if set(files) != set(required):
        raise GateError("RUNTIME_INTEGRITY_BLOCKER")
    for name, payload in files.items():
        # Re-publish into a hidden bridge root before touching public pointers.
        if storage.digest(payload) != manifest["files"][name]:
            raise GateError("RUNTIME_INTEGRITY_BLOCKER")
    meta = {k: v for k, v in manifest.items() if k not in ("run_id", "schema_version", "files")}
    result = storage.publish_generation(destination, pointer["run_id"], files, meta)
    if result != pointer:
        raise GateError("RUNTIME_GENERATION_IDENTITY_BLOCKER")
    return manifest


def publish_copied_runtime(download, runtime):
    """All copied files verified before immutable publication; pointer LAST.

    A complete unreferenced generation may remain after pointer I/O failure.
    It is safe and recoverable; latest successful account is never overwritten.
    """
    plans = []
    for pointer_name, directory, required in (
        ("latest.json", "runs", ("view.json", "state.json", "prefix.json")),
        ("last_attempt.json", "failures", ("failure.json",)),
    ):
        if not (download / pointer_name).exists():
            continue
        pointer = json.loads(storage.contained(download, pointer_name).read_bytes())
        manifest, files = storage.read_generation(download / directory, pointer)
        if set(files) != set(required) or manifest.get("status") != (
            "SUCCESSFUL_OBSERVATION" if directory == "runs" else "FAILED"
        ):
            raise GateError("RUNTIME_INTEGRITY_BLOCKER")
        dest = runtime / directory / pointer["run_id"]
        if dest.exists():
            existing, existing_files = storage.read_generation(runtime / directory, pointer)
            if existing != manifest or existing_files != files:
                raise GateError("IMMUTABLE_GENERATION_COLLISION_BLOCKER")
        plans.append((pointer_name, directory, pointer, required, dest.exists()))
    for _pointer_name, directory, pointer, required, exists in plans:
        if not exists:
            copy_generation(download / directory, runtime / directory, pointer, required)
    for pointer_name, _, pointer, _, _ in plans:
        storage.atomic_bytes(runtime / pointer_name, storage.json_bytes(pointer))
    return len(plans)


def record_failure(
    runtime, blocker, *, exception_class=None, source_commit=None, processed_at=None
):
    if not re.fullmatch(r"[A-Z0-9_]+", blocker):
        raise GateError("INVALID_BLOCKER_CODE")
    now = datetime.now(timezone.utc) if processed_at is None else processed_at
    run_id = now.strftime("%Y%m%dT%H%M%S") + "_" + uuid4().hex[:12]
    failure = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "status": "FAILED",
        "blocker": blocker,
        "processed_at": now.isoformat(),
        "exception_class": exception_class,
        "source_commit": source_commit,
        "validation_opened": False,
        "final_oos_read": False,
    }
    pointer = storage.publish_generation(
        runtime / "failures",
        run_id,
        {"failure.json": storage.json_bytes(failure)},
        {"status": "FAILED", "created_at": now.isoformat()},
    )
    storage.atomic_bytes(runtime / "last_attempt.json", storage.json_bytes(pointer))
    return {"status": "BLOCKED", "blocker": blocker, **pointer}


def import_smoke_failure(report_path, runtime):
    report = json.loads(external_file(report_path).read_bytes())
    if (
        report.get("status") != "NETWORK_METADATA_SMOKE_BLOCKED"
        or report.get("source_commit") != POLICY["source_commit"]
        or report.get("tls_verification") != "STRICT_UPSTREAM_SSL_CONTEXT"
        or report.get("pit_evidence") is not False
        or report.get("market_data_initialization") is not False
        or not re.fullmatch(r"[a-zA-Z0-9_]+", report.get("exception_class", ""))
    ):
        raise GateError("UNVERIFIED_SMOKE_REPORT_BLOCKER")
    observed = datetime.fromisoformat(report["completed_at"])
    if observed.tzinfo is None or observed > datetime.now(timezone.utc):
        raise GateError("UNVERIFIED_SMOKE_REPORT_BLOCKER")
    with transport_lock(runtime):
        return record_failure(
            runtime,
            "CNEQUITY_RUNTIME_SMOKE_BLOCKED",
            exception_class=report["exception_class"],
            source_commit=report["source_commit"],
            processed_at=observed,
        )


def cycle(config_path):
    config = json.loads(external_file(config_path).read_bytes())
    runtime = external_directory(config["runtime_root"])
    commit = committed_code()
    with transport_lock(runtime):
        try:
            return _cycle(config, runtime, commit)
        except Exception as error:
            code = error.code if isinstance(error, GateError) else "HOST_TRANSPORT_BLOCKER"
            record_failure(runtime, code, exception_class=type(error).__name__)
            raise GateError(code) from error


def _cycle(config, runtime, commit):
    sidecar = external_directory(config["sidecar_root"])
    sidecar_config = external_file(config["sidecar_config"])
    exports = external_directory(config["export_root"])
    profile_path = external_file(config["profile"])
    profile = json.loads(profile_path.read_bytes())
    if (
        profile.get("mode") != "SIMULATION_ONLY"
        or profile.get("provider_identity") != POLICY
        or profile.get("classification_version") != POLICY["classification_version"]
    ):
        raise GateError("FROZEN_SOURCE_POLICY_REQUIRED")
    import tomllib

    source_config = tomllib.loads(sidecar_config.read_text(encoding="utf-8"))
    if Path(source_config["paths"]["export_root"]).resolve() != exports:
        raise GateError("EXPORT_ROOT_CONFIG_MISMATCH")
    interpreter = sidecar / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    entry = REPO / "services/cnequity-sidecar/runner.py"
    verified = call([interpreter, "-B", entry, "verify", "--root", sidecar], timeout=60)
    if verified.returncode or result_json(verified).get("status") != "PINNED_SOURCE_PASS":
        raise GateError("SIDECAR_PIN_VERIFICATION_BLOCKER")
    exported = call(
        [interpreter, "-B", entry, "export", "--root", sidecar, "--config", sidecar_config]
    )
    export_result = result_json(exported)
    if exported.returncode or not HASH.fullmatch(export_result.get("snapshot_id", "")):
        raise GateError("SIDECAR_EXPORT_BLOCKER")
    snapshot = storage.contained(exports, export_result["snapshot_id"])
    verify_snapshot_files(snapshot)
    registry = Path(config["registry"]).resolve(strict=True)
    if registry != REPO / "strategies/etf_quant/config/verified_mappings_v1.json":
        registry = external_file(registry)
    registry_doc = json.loads(registry.read_bytes())
    if registry_doc.get("registry_identity") != "VERIFIED_MAPPING_REGISTRY_V1":
        raise GateError("MAPPING_REGISTRY_SCHEMA_BLOCKER")
    bridge = external_directory(runtime / (".bridge_" + uuid4().hex))
    evidence_dest = bridge / "evidence"
    evidence_dest.mkdir()
    for row in registry_doc["entries"]:
        if row.get("verification_status") != "VERIFIED":
            continue
        name = row.get("source_file", "")
        if not re.fullmatch(r"[a-zA-Z0-9_-]+\.(pdf|html|txt)", name):
            raise GateError("MAPPING_EVIDENCE_BLOCKER")
        evidence = external_directory(config["evidence_root"])
        body = storage.contained(evidence, name).read_bytes()
        if storage.digest(body) != row.get("source_sha256"):
            raise GateError("MAPPING_EVIDENCE_HASH_BLOCKER")
        storage.atomic_bytes(evidence_dest / name, body)
    input_runtime = bridge / "input_runtime"
    input_runtime.mkdir()
    if (runtime / "latest.json").exists():
        pointer = json.loads(storage.contained(runtime, "latest.json").read_bytes())
        copy_generation(
            runtime / "runs",
            input_runtime / "runs",
            pointer,
            ("view.json", "state.json", "prefix.json"),
        )
        storage.atomic_bytes(input_runtime / "latest.json", storage.json_bytes(pointer))
    docker = config["docker_executable"]

    def command(args, **kwargs):
        result = call([docker, *args], **kwargs)
        if result.returncode:
            raise GateError("EXISTING_DOCKER_TRANSPORT_BLOCKER")
        return result

    temp = command(
        ["exec", "quant-research", "mktemp", "-d", "/tmp/etf-quant-v1.XXXXXXXX"]
    ).stdout.strip()
    if not re.fullmatch(r"/tmp/etf-quant-v1\.[a-zA-Z0-9]{8}", temp):
        raise GateError("DOCKER_TEMP_PATH_BLOCKER")
    command(["exec", "quant-research", "mkdir", "-p", temp + "/strategies"])
    # Do not copy .git, Research, raw lakes, credentials or node_modules.
    code = bridge / "code"
    shutil.copytree(
        REPO / "strategies/etf_quant",
        code,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )
    command(["cp", code, "quant-research:" + temp + "/strategies/etf_quant"])
    for src, dest in (
        (snapshot, snapshot.name),
        (profile_path, "profile.json"),
        (registry, "registry.json"),
        (evidence_dest, "evidence"),
        (input_runtime, "runtime"),
    ):
        command(["cp", src, "quant-research:" + temp + "/" + dest])
    child = call(
        [
            docker,
            "exec",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-w",
            temp,
            "quant-research",
            "python",
            "-B",
            "-m",
            "strategies.etf_quant.runtime.cli",
            "cycle",
            "--snapshot",
            temp + "/" + snapshot.name,
            "--runtime",
            temp + "/runtime",
            "--profile",
            temp + "/profile.json",
            "--registry",
            temp + "/registry.json",
            "--evidence-root",
            temp + "/evidence",
            "--commit",
            commit,
        ]
    )
    response = result_json(child)
    # Even an unsuccessful child may have a complete failure manifest, never a partial account.
    downloaded = bridge / "downloaded_runtime"
    command(["cp", "quant-research:" + temp + "/runtime", downloaded])
    publish_copied_runtime(downloaded, runtime)
    if child.returncode:
        blocker = response.get("blocker", "DOCKER_CYCLE_BLOCKER")
        raise GateError(blocker if re.fullmatch(r"[A-Z0-9_]+", blocker) else "DOCKER_CYCLE_BLOCKER")
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("cycle", "record-smoke-blocker"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.command == "cycle":
        if args.config is None:
            raise GateError("EXPLICIT_EXTERNAL_CONFIG_REQUIRED")
        result = cycle(args.config)
    else:
        if args.runtime is None or args.report is None:
            raise GateError("VERIFIED_SMOKE_REPORT_REQUIRED")
        result = import_smoke_failure(args.report, external_directory(args.runtime))
    print(storage.json_bytes(result).decode())
    return 2 if result.get("status") == "BLOCKED" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        code = error.code if isinstance(error, GateError) else "HOST_TRANSPORT_BLOCKER"
        print(
            storage.json_bytes(
                {"status": "BLOCKED", "blocker": code, "exception_class": type(error).__name__}
            ).decode()
        )
        raise SystemExit(2)
