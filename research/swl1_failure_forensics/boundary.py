"""Admit exact frozen evidence and decode only authorized NPY row prefixes."""

from __future__ import annotations

import ast
import hashlib
import io
import json
import math
import struct
import zipfile
import zlib
from pathlib import Path
from typing import Any

import numpy as np

FROZEN = {
    "reports/research/swl1_ridge_v1/data_feasibility.json": "39aff56e15b730bc834cb7407a086546a75f7d4f292ee0cadc38294e1987fad3",
    "reports/research/swl1_ridge_v1/factor_audit.json": "c3998b221e4b210271dee6e6e4b6ae118cc4a34717900820425c2d1ef8f9f041",
    "config/research/swl1-ridge-v1-protocol.json": "3d148ba7adc4846cd3fa951a46dc224f34a5070a8dd5cfa50523bca4a0c5222e",
    "config/research/swl1-ridge-v2-protocol.json": "df832a94eba54d703110defe2e7f0169e9de93a316a7def795a38fe9e50e428a",
    "config/research/swl1-ridge-v1-candidate.json": "c5917b83d5c81627cfa88ae19d1691fd7356b7c91134be1472c1047e2a31ab6c",
    "config/research/swl1-ridge-v2-candidate.json": "c94d511d925e47947b12d12a1b8c0380417da525282651a790ca55f84c81efad",
    "reports/research/swl1_ridge_v1/development.json": "a031bec412de2c86008eeb2b9272f8409fd17ce79b8ef511a893d497003dfeda",
    "reports/research/swl1_ridge_v1/validation.json": "4f39211fb8fcdd3e350355414b753065940b8bdb42bb2ee57a432b89241c205c",
    "reports/research/swl1_ridge_v1/status.json": "9d2a6b9d418e88008a0125d4004fd9283735ce5fd1b854f7a9de607f73eb6569",
    "reports/research/swl1_ridge_v2/development.json": "8715911746935fcf27200a76d17f402cd95f61f3eaa36312f947c07081be13f2",
    "reports/research/swl1_ridge_v2/validation.json": "e1fea05ccef53c1767f3e8e6b845c9e52e23112543856bbe85095501706dbc97",
    "reports/research/swl1_ridge_v2/status.json": "5453501bbe21068042f9691f3cf900513e6d529a28dd8de3f73b624cc7b6eb85",
}
PANEL_SHA = "20c038f87daa93cccf1515f41bda7de5b30fa70a4d1443ae6c34b770e19a5776"


def contained(root: Path, relative: str) -> Path:
    """Reject traversal and every symlink component, even links back into root."""
    name = Path(relative)
    if name.is_absolute() or not name.parts or ".." in name.parts or "\\" in relative:
        raise ValueError("EVIDENCE_PATH_BLOCKED")
    resolved_root = root.resolve(strict=True)
    current = resolved_root
    for part in name.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("EVIDENCE_SYMLINK_BLOCKED")
    resolved = current.resolve(strict=True)
    if not resolved.is_relative_to(resolved_root) or not resolved.is_file():
        raise ValueError("EVIDENCE_PATH_BLOCKED")
    return resolved


def sha(path: Path) -> str:
    """Integrity hashing is opaque byte verification, not outcome decoding."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def admit(root: Path, name: str, expected: str) -> dict[str, Any]:
    path = contained(root, name)
    if sha(path) != expected:
        raise ValueError("FROZEN_EVIDENCE_HASH_MISMATCH")
    value: dict[str, Any] = json.loads(path.read_text())
    return value


def historical_panel_access(root: Path, implementation: dict[str, str]) -> dict[str, Any]:
    """Inspect pinned source only; date arithmetic cannot certify historical access.

    This recognizes the exact frozen executors, not arbitrary control flow. It
    never imports or executes them, opens their panel, or infers human inspection.
    """
    sources = {}
    for version in ("v1", "v2"):
        name = f"research/swl1_ridge_{version}/execute.py"
        if name not in implementation:
            continue
        path = contained(root, name)
        if sha(path) != implementation[name]:
            raise ValueError("FROZEN_IMPLEMENTATION_HASH_MISMATCH")
        nodes = list(ast.walk(ast.parse(path.read_text())))
        loads = sorted(
            n.lineno
            for n in nodes
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "np"
            and n.func.attr == "load"
        )
        members = {
            member: sorted(
                n.lineno
                for n in nodes
                if isinstance(n, ast.Subscript)
                and isinstance(n.value, ast.Name)
                and n.value.id == "data"
                and isinstance(n.slice, ast.Constant)
                and n.slice.value == member
            )
            for member in ("returns", "features")
        }
        sources[name] = {
            "sha256": implementation[name],
            "np_load_lines": loads,
            "numeric_member_lines": members,
            "full_numeric_members_materialized": bool(loads and all(members.values())),
        }
    return {
        "method": "PINNED_SOURCE_INSPECTION_NOT_RUNTIME_OR_HUMAN_ACCESS_TRACE",
        "sources": sources,
        "historical_unseen_access_certified": False,
        "declared_target_maturity_is_not_access_isolation_proof": True,
    }


class LimitedInflater:
    """DEFLATE decoder with no decompressed read-ahead past each requested byte.

    ZipExtFile buffers decompressed future rows; this reader deliberately does not.
    Compressed input bytes may be prefetched, but remain opaque like SHA input.
    """

    def __init__(self, compressed: bytes, method: int) -> None:
        if method not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise ValueError("UNSUPPORTED_ZIP_CODEC")
        self.raw = io.BytesIO(compressed)
        self.decoder = zlib.decompressobj(-15) if method == zipfile.ZIP_DEFLATED else None
        self.pending = b""
        self.decoded_bytes = 0

    def read(self, size: int) -> bytes:
        if size < 0:
            raise ValueError("UNBOUNDED_EVIDENCE_READ_BLOCKED")
        if self.decoder is None:
            result = self.raw.read(size)
        else:
            parts: list[bytes] = []
            remaining = size
            while remaining:
                data = self.pending or self.raw.read(4096)
                if not data:
                    raise ValueError("TRUNCATED_NPY")
                decoded = self.decoder.decompress(data, max_length=remaining)
                self.pending = self.decoder.unconsumed_tail
                parts.append(decoded)
                remaining -= len(decoded)
            result = b"".join(parts)
        self.decoded_bytes += len(result)
        if len(result) != size:
            raise ValueError("TRUNCATED_NPY")
        return result


def npy_prefix(
    path: Path, member: str, rows: int, allowed_rows: int
) -> tuple[np.ndarray, dict[str, Any]]:
    """No unseen outcome is interpreted as a number; dates/codes are metadata.

    Fortran storage interleaves each admitted column prefix with an opaque tail.
    Skip these bytes without dtype conversion, like an integrity byte stream;
    record the discard count separately from numeric payload decoding.
    """
    if member not in ("returns.npy", "features.npy", "dates.npy", "codes.npy"):
        raise ValueError("NPZ_MEMBER_NOT_WHITELISTED")
    if not 0 < rows <= allowed_rows:
        raise ValueError("UNSEEN_OUTCOME_READ_BLOCKED")
    with zipfile.ZipFile(path) as archive:
        if archive.namelist().count(member) != 1:
            raise ValueError("AMBIGUOUS_NPZ_MEMBER")
        info = archive.getinfo(member)
    with path.open("rb", buffering=0) as handle:
        handle.seek(info.header_offset)
        local = handle.read(30)
        if len(local) != 30 or local[:4] != b"PK\x03\x04" or info.flag_bits & 1:
            raise ValueError("UNSUPPORTED_ZIP_HEADER")
        name_len, extra_len = struct.unpack("<HH", local[26:30])
        handle.seek(name_len + extra_len, 1)
        compressed = handle.read(info.compress_size)
    reader = LimitedInflater(compressed, info.compress_type)
    version = np.lib.format.read_magic(reader)
    if version == (1, 0):
        shape, fortran, dtype = np.lib.format.read_array_header_1_0(reader)
    elif version == (2, 0):
        shape, fortran, dtype = np.lib.format.read_array_header_2_0(reader)
    else:
        raise ValueError("UNSUPPORTED_NPY_VERSION")
    if dtype.hasobject or dtype.fields or not shape or rows > shape[0]:
        raise ValueError("UNSAFE_NPY_LAYOUT")
    header_bytes = reader.decoded_bytes
    required = rows * math.prod(shape[1:]) * dtype.itemsize
    discarded = 0
    if fortran and len(shape) > 1:
        columns = math.prod(shape[1:])
        admitted = []
        for column in range(columns):
            admitted.append(np.frombuffer(reader.read(rows * dtype.itemsize), dtype=dtype))
            if column + 1 < columns:
                skip = (shape[0] - rows) * dtype.itemsize
                while skip:
                    count = min(skip, 4096)
                    reader.read(count)  # Opaque layout bytes; never converted to outcomes.
                    discarded += count
                    skip -= count
        array = np.concatenate(admitted).reshape((rows, *shape[1:]), order="F")
    else:
        array = np.frombuffer(reader.read(required), dtype=dtype).reshape((rows, *shape[1:]))
    return array, {
        "member": member,
        "shape_metadata": list(shape),
        "rows_decoded": rows,
        "payload_bytes_decoded": reader.decoded_bytes - header_bytes - discarded,
        "payload_bytes_permitted": required,
        "decompressed_read_ahead": 0,
        "opaque_layout_bytes_discarded_without_numeric_conversion": discarded,
        "storage_order": "FORTRAN" if fortran else "C",
        "tail_rows_not_decoded": shape[0] - rows,
    }


def boundary(dates: list[str], protocols: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if dates != sorted(set(dates)):
        raise ValueError("EXCHANGE_SPINE_REQUIRED")
    generations: dict[str, Any] = {}
    for version, protocol in protocols.items():
        phases = {}
        for phase in ("development", "validation"):
            indices = protocol["split"]["indices"][phase]
            if not indices or indices != sorted(set(indices)) or indices[0] < 0:
                raise ValueError("INVALID_CONSUMED_PHASE")
            end = max(indices) + 120
            if end >= len(dates):
                raise ValueError("UNAVAILABLE_MATURE_EVIDENCE")
            phases[phase] = {
                "first_signal": dates[min(indices)],
                "last_signal": dates[max(indices)],
                "signals": len(indices),
                "last_signal_index": max(indices),
                "outcome_cutoffs": {str(h): dates[max(indices) + h] for h in (10, 40, 120)},
                "last_outcome_index": end,
            }
        end = max(p["last_outcome_index"] for p in phases.values())
        generations[version] = {
            "phases": phases,
            "last_outcome_index": end,
            "last_outcome": dates[end],
        }
    union = max(v["last_outcome_index"] for v in generations.values())
    signal = max(p["last_signal_index"] for v in generations.values() for p in v["phases"].values())
    return {
        "generations": generations,
        "union_last_outcome": dates[union],
        "union_last_outcome_index": union,
        "permitted_return_rows": union + 1,
        "permitted_feature_rows": signal + 1,
        "spine_first": dates[0],
        "spine_last_metadata_only": dates[-1],
        "outcomes_beyond_declared_consumption": {
            "first": dates[union + 1] if union + 1 < len(dates) else None,
            "last": dates[-1] if union + 1 < len(dates) else None,
            "sessions": len(dates) - union - 1,
            "outcomes_read_by_this_forensic_task": False,
            "historical_unseen_status": "NOT_CERTIFIED_BY_DATE_ARITHMETIC",
            "independently_unseen_sessions_certified": 0,
        },
        "prospective_only": "Dates beyond the admitted spine; no additional source consulted.",
        "data_unavailable": "Contemporaneous historical membership and independent official index proof.",
        "unseen_outcomes_read": False,
    }
