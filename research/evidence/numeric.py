"""Authority-owned staging and a physically bounded, authenticated worker view.

The authority may decode the mother file AFTER factual authorization. The worker
can decode only newly serialized bounded members. OS containment is a separate
launcher responsibility, not something this Python firewall can create.
"""

from __future__ import annotations

import io
import json
import os
import stat
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
from numpy.typing import NDArray

from strategies.etf_quant.runtime.storage import atomic_bytes, process_lock

from .contracts import (
    Denied,
    Proof,
    SyntheticAuthority,
    canonical,
    hash_id,
    identity,
    instant,
    require,
    sha,
)
from .prospective import Protocol, activation, verify_source
from .source_admission import SourceRegistry

MAX_BYTES = 16 * 1024 * 1024
FILES = {"manifest.json", "features.npy", "returns.npy"}


@dataclass(frozen=True)
class Boundary:
    phase: str
    authorized_from_session: str
    authorized_through_session: str
    feature_cutoff: str
    realized_return_cutoff: str
    allowed_label_maturity: tuple[int, ...]
    expires_at: str

    def validate(self, protocol: Protocol, now: str) -> None:
        require(self.phase in protocol.phases, "PHASE_NOT_REGISTERED")
        require(
            all(
                s in protocol.sessions
                for s in (
                    self.authorized_from_session,
                    self.authorized_through_session,
                    self.feature_cutoff,
                    self.realized_return_cutoff,
                )
            )
            and self.authorized_from_session <= self.realized_return_cutoff <= self.feature_cutoff
            and self.feature_cutoff <= self.authorized_through_session,
            "DATE_BOUNDARY_MISMATCH",
        )
        require(
            self.allowed_label_maturity
            and all(h in protocol.horizons for h in self.allowed_label_maturity),
            "PENDING_MATURITY",
        )
        require(instant(now) < instant(self.expires_at), "STALE_CAPABILITY")


def grant_claims(protocol: Protocol, boundary: Boundary, facts_hash: str) -> dict[str, Any]:
    hash_id(facts_hash)
    return {
        "protocol_hash": protocol.digest,
        "source_digest": protocol.source_digest,
        "boundary": asdict(boundary),
        "finalized_fact_receipts_hash": facts_hash,
    }


def _npy(array: NDArray[Any]) -> bytes:
    out = io.BytesIO()
    np.save(out, np.ascontiguousarray(array, dtype=np.float64), allow_pickle=False)
    raw = out.getvalue()
    require(len(raw) <= MAX_BYTES, "VIEW_SIZE_LIMIT")
    return raw


def materialize(
    mother: Path,
    destination: Path,
    protocol: Protocol,
    boundary: Boundary,
    grant: Proof,
    registry: SourceRegistry,
    authority: SyntheticAuthority,
    *,
    now: str,
    facts_hash: str,
    activation_anchor: Proof,
    calendar: Proof,
) -> dict[str, Any]:
    """Trusted staging only. No numeric open until source, phase and proofs pass."""
    admission = registry.get(protocol.source_digest)
    verify_source(protocol, registry)
    boundary.validate(protocol, now)
    first_session = activation(protocol, activation_anchor, calendar, authority)
    require(boundary.authorized_from_session >= first_session, "BACKDATED_OBSERVATION_DENIED")
    require(
        authority.verify(grant, "phase")
        == json.loads(canonical(grant_claims(protocol, boundary, facts_hash))),
        "DATA_ACCESS_DENIED",
    )
    require(
        destination.is_absolute() and destination.resolve() == destination, "PATH_ESCAPE_DENIED"
    )
    require(
        destination.parent.name == "views" and not destination.exists(), "IMMUTABLE_VIEW_REQUIRED"
    )
    require(
        mother.suffix == ".npz" and mother.is_file() and not mother.is_symlink(),
        "AUTHORITY_TRANSFORM_REQUIRED",
    )
    require(mother.stat().st_size <= MAX_BYTES, "AUTHORITY_SIZE_LIMIT")
    # C/F/compressed ZIP layouts are decoded ONLY here, never in the worker.
    try:
        mother_raw = mother.read_bytes()
        with zipfile.ZipFile(io.BytesIO(mother_raw)) as archive:
            require(
                sum(member.file_size for member in archive.infolist()) <= MAX_BYTES
                and len(archive.infolist()) == 4,
                "AUTHORITY_SIZE_LIMIT",
            )
        with np.load(io.BytesIO(mother_raw), allow_pickle=False) as panel:
            require(
                set(panel.files) == {"sessions", "universe", "features", "returns"},
                "SOURCE_LAYOUT_INVALID",
            )
            dates = tuple(str(s) for s in panel["sessions"])
            universe = tuple(str(s) for s in panel["universe"])
            require(
                dates == protocol.sessions and universe == protocol.model_universe,
                "MODEL_UNIVERSE_DRIFT",
            )
            features, returns = panel["features"], panel["returns"]
            require(
                features.ndim == 3
                and features.shape[:2] == (len(dates), len(universe))
                and returns.shape == (len(dates), len(universe))
                and features.dtype.kind == "f"
                and returns.dtype.kind == "f",
                "SOURCE_LAYOUT_INVALID",
            )
            a = dates.index(boundary.authorized_from_session)
            f = dates.index(boundary.feature_cutoff) + 1
            r = dates.index(boundary.realized_return_cutoff) + 1
            permitted_features = features[a:f].copy()
            permitted_returns = returns[a:r].copy()
            require(
                np.isfinite(permitted_features).all() and np.isfinite(permitted_returns).all(),
                "FACT_NOT_FINALIZED",
            )
            bodies = {
                "features.npy": _npy(permitted_features),
                "returns.npy": _npy(permitted_returns),
            }
    except Denied:
        raise
    except Exception:
        raise Denied("SOURCE_LAYOUT_INVALID") from None
    content = sha(canonical({name: sha(raw) for name, raw in bodies.items()}))
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "scope": "SYNTHETIC_ONLY",
        "view_id": destination.name,
        "family_id": protocol.family_id,
        "research_generation": protocol.research_generation,
        "protocol_hash": protocol.digest,
        "source_hash": admission.source.source_hash,
        "source_digest": protocol.source_digest,
        "mother_snapshot_hash": sha(mother_raw),
        "data_contract_hash": admission.source.data_contract_hash,
        **asdict(boundary),
        "model_universe_hash": protocol.universe_hash,
        "created_at": now,
        "content_hash": content,
        "feature_sessions": list(dates[a:f]),
        "return_sessions": list(dates[a:r]),
        "universe_size": len(universe),
        "feature_count": permitted_features.shape[2],
        "files": {name: {"sha256": sha(raw), "size": len(raw)} for name, raw in bodies.items()},
    }
    manifest["authority_receipt"] = authority.issue("view", manifest).as_dict()
    destination.parent.mkdir(parents=True, exist_ok=True)
    identity(destination.name)
    with process_lock(destination.parent / ".view.guard"):
        require(not destination.exists(), "IMMUTABLE_VIEW_REQUIRED")
        stage = destination.parent / (".stage_" + uuid4().hex)
        stage.mkdir()
        for name, raw in {**bodies, "manifest.json": canonical(manifest)}.items():
            atomic_bytes(stage / name, raw)
            (stage / name).chmod(0o444)
        stage.chmod(0o555)
        os.rename(stage, destination)
    return manifest


def safe_read(root: Path, name: str, limit: int = MAX_BYTES) -> bytes:
    """Closed leaf names; reject links/reparse/hard links, read verified descriptor."""
    require(name in FILES and root.is_absolute(), "PATH_ESCAPE_DENIED")
    require(root.resolve(strict=True) == root and not root.is_symlink(), "PATH_ESCAPE_DENIED")
    for parent in (root, *root.parents):
        metadata = parent.lstat()
        require(not stat.S_ISLNK(metadata.st_mode), "PATH_ESCAPE_DENIED")
        require(not getattr(metadata, "st_file_attributes", 0) & 0x400, "PATH_ESCAPE_DENIED")
    target = root / name
    before = target.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "PATH_ESCAPE_DENIED")
    require(not getattr(before, "st_file_attributes", 0) & 0x400, "PATH_ESCAPE_DENIED")
    fd = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.set_inheritable(fd, False)
        after = os.fstat(fd)
        require((before.st_dev, before.st_ino) == (after.st_dev, after.st_ino), "TOCTOU_DENIED")
        require(after.st_size <= limit and after.st_nlink == 1, "VIEW_SIZE_LIMIT")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            raw = handle.read(limit + 1)
        require(len(raw) == after.st_size and len(raw) <= limit, "VIEW_SIZE_LIMIT")
        return raw
    finally:
        os.close(fd)


def consume(
    root: Path,
    *,
    pinned_manifest_hash: str,
    protocol: Protocol,
    boundary: Boundary,
    source_hash: str,
    data_contract_hash: str,
    now: str,
) -> dict[str, Any]:
    """Pin is supplied by the trusted launcher, never by a worker-controlled config."""
    require(bool(pinned_manifest_hash), "DATA_ACCESS_DENIED")
    hash_id(pinned_manifest_hash)
    boundary.validate(protocol, now)
    require({p.name for p in root.iterdir()} == FILES, "UNEXPECTED_VIEW_MEMBER")
    raw = safe_read(root, "manifest.json", 64 * 1024)
    require(sha(raw) == pinned_manifest_hash, "MANIFEST_HASH_MISMATCH")
    try:
        manifest = json.loads(raw)
        expected_keys = {
            "schema_version",
            "scope",
            "view_id",
            "family_id",
            "research_generation",
            "protocol_hash",
            "source_hash",
            "source_digest",
            "mother_snapshot_hash",
            "data_contract_hash",
            "model_universe_hash",
            "created_at",
            "content_hash",
            "feature_sessions",
            "return_sessions",
            "universe_size",
            "feature_count",
            "files",
            "authority_receipt",
            *asdict(boundary),
        }
        require(
            set(manifest) == expected_keys
            and manifest["schema_version"] == 1
            and manifest["scope"] == "SYNTHETIC_ONLY",
            "MANIFEST_INVALID",
        )
        require(
            manifest["protocol_hash"] == protocol.digest
            and manifest["family_id"] == protocol.family_id
            and manifest["research_generation"] == protocol.research_generation,
            "PROTOCOL_HASH_MISMATCH",
        )
        require(
            manifest["source_hash"] == source_hash
            and manifest["source_digest"] == protocol.source_digest
            and manifest["data_contract_hash"] == data_contract_hash,
            "SOURCE_IDENTITY_MISMATCH",
        )
        require(
            manifest["model_universe_hash"] == protocol.universe_hash
            and manifest["universe_size"] == len(protocol.model_universe),
            "MODEL_UNIVERSE_DRIFT",
        )
        require(
            all(manifest[k] == v for k, v in json.loads(canonical(asdict(boundary))).items()),
            "DATE_BOUNDARY_MISMATCH",
        )
        a = protocol.sessions.index(boundary.authorized_from_session)
        f = protocol.sessions.index(boundary.feature_cutoff) + 1
        r = protocol.sessions.index(boundary.realized_return_cutoff) + 1
        require(
            manifest["feature_sessions"] == list(protocol.sessions[a:f])
            and manifest["return_sessions"] == list(protocol.sessions[a:r]),
            "DATE_BOUNDARY_MISMATCH",
        )
        require(instant(manifest["created_at"]) <= instant(now), "STALE_CAPABILITY")
        require(set(manifest["files"]) == {"features.npy", "returns.npy"}, "MANIFEST_INVALID")
        bodies = {}
        # Authenticate all member bytes before either numeric decode.
        for name, reference in manifest["files"].items():
            require(set(reference) == {"sha256", "size"}, "MANIFEST_INVALID")
            body = safe_read(root, name)
            require(
                len(body) == reference["size"] and sha(body) == reference["sha256"],
                "CONTENT_HASH_MISMATCH",
            )
            bodies[name] = body
        require(
            sha(canonical({n: sha(b) for n, b in bodies.items()})) == manifest["content_hash"],
            "CONTENT_HASH_MISMATCH",
        )
        features = np.load(io.BytesIO(bodies["features.npy"]), allow_pickle=False)
        returns = np.load(io.BytesIO(bodies["returns.npy"]), allow_pickle=False)
        require(
            features.shape == (f - a, len(protocol.model_universe), manifest["feature_count"])
            and returns.shape == (r - a, len(protocol.model_universe)),
            "VIEW_SHAPE_INVALID",
        )
        require(np.isfinite(features).all() and np.isfinite(returns).all(), "FACT_NOT_FINALIZED")
        return {
            "scope": "SYNTHETIC_ONLY",
            "content_hash": manifest["content_hash"],
            "feature_rows": len(features),
            "return_rows": len(returns),
            "derived_hash": sha(_npy(features.mean(axis=0))),
            "manifest_hash": pinned_manifest_hash,
        }
    except Denied:
        raise
    except Exception:
        raise Denied("MANIFEST_INVALID") from None
