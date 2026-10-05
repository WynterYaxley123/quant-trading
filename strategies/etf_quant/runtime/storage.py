"""Small immutable-publication primitives shared by export and Shadow storage."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


class GateError(ValueError):
    def __init__(self, code, details=None):
        super().__init__(code)
        self.code = code
        self.details = {} if details is None else details


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def closed_id(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}", value):
        raise GateError("RUNTIME_INTEGRITY_BLOCKER")
    return value


def contained(root: Path, name: str, *, exists=True) -> Path:
    root = root.resolve(strict=True)
    try:
        target = (root / name).resolve(strict=exists)
    except OSError as error:
        raise GateError("RUNTIME_INTEGRITY_BLOCKER") from error
    if target == root or not target.is_relative_to(root):
        raise GateError("RUNTIME_INTEGRITY_BLOCKER")
    return target


def external_root(path: Path) -> Path:
    path = path.resolve()
    if any((parent / ".git").exists() for parent in (path, *path.parents)):
        raise GateError("REPO_EXTERNAL_RUNTIME_REQUIRED")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve(strict=True)


def atomic_bytes(path: Path, payload: bytes, *, replace=os.replace, sleep=time.sleep, audit=None):
    temp = path.with_name("." + path.name + "." + uuid4().hex + ".tmp")
    try:
        with temp.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(1, 5):
            try:
                replace(temp, path)
                return
            except PermissionError as error:
                # Retry only OS sharing/access errors, never parsing/hash gates.
                if error.errno not in (1, 13, None) or attempt == 4:
                    raise GateError("RUNTIME_PUBLICATION_BLOCKER", {"attempts": attempt}) from error
                if audit is not None:
                    audit(
                        {
                            "event": "ATOMIC_REPLACE_RETRY",
                            "attempt": attempt,
                            "exception": type(error).__name__,
                            "errno": error.errno,
                        }
                    )
                sleep(0.05 * 2 ** (attempt - 1))
    finally:
        if temp.exists():
            temp.unlink()


def publish_generation(root: Path, run_id: str, files: dict[str, bytes], metadata: dict) -> dict:
    """Directory becomes discoverable only after every file and manifest closes."""
    root = external_root(root)
    closed_id(run_id)
    destination = root / run_id
    if destination.exists():
        raise GateError("IMMUTABLE_GENERATION_EXISTS")
    stage = root / (".stage_" + uuid4().hex)
    stage.mkdir()
    hashes = {}
    for name, payload in files.items():
        if not re.fullmatch(r"[a-z0-9_]+\.(json|csv)", name):
            raise GateError("RUNTIME_INTEGRITY_BLOCKER")
        atomic_bytes(stage / name, payload)
        hashes[name] = digest(payload)
    manifest = {**metadata, "schema_version": "1.0.0", "run_id": run_id, "files": hashes}
    manifest_bytes = json_bytes(manifest)
    atomic_bytes(stage / "manifest.json", manifest_bytes)
    os.rename(stage, destination)
    return {"run_id": run_id, "manifest_sha256": digest(manifest_bytes)}


def read_generation(root: Path, pointer: dict) -> tuple[dict, dict[str, bytes]]:
    run_id = closed_id(pointer.get("run_id"))
    run_root = contained(root, run_id)
    raw = contained(run_root, "manifest.json").read_bytes()
    if digest(raw) != pointer.get("manifest_sha256"):
        raise GateError("RUNTIME_INTEGRITY_BLOCKER")
    manifest = json.loads(raw)
    if manifest.get("run_id") != run_id or manifest.get("schema_version") != "1.0.0":
        raise GateError("RUNTIME_INTEGRITY_BLOCKER")
    payloads = {}
    for name, expected in manifest["files"].items():
        if not re.fullmatch(r"[a-z0-9_]+\.(json|csv)", name):
            raise GateError("RUNTIME_INTEGRITY_BLOCKER")
        body = contained(run_root, name).read_bytes()
        if digest(body) != expected:
            raise GateError("RUNTIME_INTEGRITY_BLOCKER")
        payloads[name] = body
    return manifest, payloads


@contextmanager
def process_lock(path: Path) -> Iterator[None]:
    """An OS mutex releases on process death; its persistent file is not ownership."""
    if path.resolve().parent != path.parent.resolve():
        raise GateError("RUNTIME_INTEGRITY_BLOCKER")
    with path.open("a+b") as guard:
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
            raise GateError("CONCURRENT_OR_INTERRUPTED_RUN_BLOCKER") from error
        try:
            yield
        finally:
            guard.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(guard.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(guard, fcntl.LOCK_UN)


def _pointer_bytes(root: Path) -> bytes | None:
    leaf = root / "latest.json"
    if not leaf.exists():
        return None
    leaf = contained(root, "latest.json")
    with leaf.open("rb") as handle:
        raw = handle.read(4097)
    if len(raw) > 4096:
        raise GateError("RUNTIME_PUBLICATION_JOURNAL_BLOCKER")
    return raw


def recover_publication(root: Path) -> None:
    """Finish a byte-verified prior commit under the account lock, without refitting."""
    journal = root / ".publication.json"
    if not journal.exists():
        return
    with contained(root, journal.name).open("rb") as handle:
        raw = handle.read(4097)
    try:
        record = json.loads(raw)
        if len(raw) > 4096 or set(record) != {"pointer", "previous_pointer_sha256"}:
            raise ValueError()
        pointer = record["pointer"]
        if set(pointer) != {"run_id", "manifest_sha256"}:
            raise ValueError()
        run_id = closed_id(pointer["run_id"])
        if not re.fullmatch(r"[a-f0-9]{64}", pointer["manifest_sha256"]):
            raise ValueError()
        previous = record["previous_pointer_sha256"]
        if previous is not None and not re.fullmatch(r"[a-f0-9]{64}", previous):
            raise ValueError()
        current = _pointer_bytes(root)
        current_hash = digest(current) if current is not None else None
        if current_hash != previous and current != json_bytes(pointer):
            raise ValueError()
        runs = contained(root, "runs", exists=False)
        destination = runs / run_id
        if destination.exists():
            read_generation(runs, pointer)
            atomic_bytes(root / "latest.json", json_bytes(pointer))
        elif current_hash != previous:
            raise ValueError()
        # An unpublished stage is not formal evidence. A completed generation is
        # promoted with its original decision time, never reconstructed/backdated.
        journal.unlink()
    except (ValueError, TypeError, KeyError) as error:
        raise GateError("RUNTIME_PUBLICATION_JOURNAL_BLOCKER") from error


def publish_account_generation(
    root: Path,
    run_id: str,
    files: dict[str, bytes],
    metadata: dict,
    *,
    publisher: Callable = publish_generation,
) -> dict:
    """Journal before immutable publication; caller must hold the account mutex."""
    if (root / ".publication.json").exists():
        raise GateError("RUNTIME_PUBLICATION_JOURNAL_BLOCKER")
    closed_id(run_id)
    manifest = {
        **metadata,
        "schema_version": "1.0.0",
        "run_id": run_id,
        "files": {name: digest(body) for name, body in files.items()},
    }
    pointer = {"run_id": run_id, "manifest_sha256": digest(json_bytes(manifest))}
    previous = _pointer_bytes(root)
    atomic_bytes(
        root / ".publication.json",
        json_bytes(
            {"pointer": pointer, "previous_pointer_sha256": digest(previous) if previous else None}
        ),
    )
    published = publisher(contained(root, "runs", exists=False), run_id, files, metadata)
    if published != pointer:
        raise GateError("RUNTIME_PUBLICATION_JOURNAL_BLOCKER")
    atomic_bytes(root / "latest.json", json_bytes(pointer))
    (root / ".publication.json").unlink()
    return pointer


@contextmanager
def account_lock(root: Path) -> Iterator[None]:
    """Recover under a same-OS mutex; operational account owners run in Docker."""
    with process_lock(root / ".cycle.guard"):
        if (root / ".cycle.lock").exists():
            raise GateError("CONCURRENT_OR_INTERRUPTED_RUN_BLOCKER")
        recover_publication(root)
        yield
