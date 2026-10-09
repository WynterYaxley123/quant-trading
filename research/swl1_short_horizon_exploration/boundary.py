"""A narrow owner-authorized historical view; no prospective admission writes."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from research.swl1_failure_forensics.boundary import FROZEN, contained, npy_prefix, sha
from research.swl1_failure_forensics.report import write
from strategies.etf_quant.config import FACTORS_19

from .design import DESIGN_SHA, LABEL, LOCK_COMMIT, load_design
from .signals import reversal_features


def isolated_inputs(paths: list[Path]) -> dict[str, Any]:
    if not Path("/.dockerenv").is_file() or {p.name for p in Path("/sys/class/net").iterdir()} != {
        "lo"
    }:
        raise ValueError("NETWORK_DISABLED_DOCKER_REQUIRED")
    if not all(os.statvfs(p).f_flag & os.ST_RDONLY for p in paths):
        raise ValueError("READ_ONLY_INPUT_MOUNTS_REQUIRED")
    return {
        "docker": True,
        "network": "NONE",
        "read_only_inputs": True,
        "interfaces": ["lo"],
        "quantitative_execution_on_host": False,
    }


def pinned_bytes(path: Path, expected: str, limit: int = 16 * 1024 * 1024) -> bytes:
    current = path.absolute()
    if any(p.is_symlink() for p in (current, *current.parents)):
        raise ValueError("SOURCE_LINK_BLOCKED")
    with current.open("rb") as handle:
        value = handle.read(limit + 1)
    if len(value) > limit or hashlib.sha256(value).hexdigest() != expected:
        raise ValueError("SOURCE_BYTES_NOT_PINNED")
    return value


def prepare(root: Path, source: Path, owner_task: Path, output: Path) -> dict[str, Any]:
    """Run in a network-disabled container with four exact read-only input files."""
    design = load_design(root)
    pinned_bytes(owner_task, design["owner_task_sha256"])
    isolation = isolated_inputs(
        [
            root,
            owner_task,
            contained(source, "panel.npz"),
            *(contained(source, name) for name in design["reference_sha256"]),
        ]
    )
    for name, expected in {**FROZEN, **design["reused_implementation_sha256"]}.items():
        if sha(contained(root, name)) != expected:
            raise ValueError("FROZEN_REUSE_CHANGED")
    universe = json.loads(
        pinned_bytes(contained(root, design["universe_file"]), design["universe_sha256"])
    )
    panel = contained(source, "panel.npz")
    if sha(panel) != design["panel_sha256"]:
        raise ValueError("PANEL_NOT_PINNED")
    # Metadata is not a numeric outcome. Prefix counts are committed before any
    # return or feature value is decoded; the actual worker receives only this view.
    dates0, _ = npy_prefix(panel, "dates.npy", 1253, 1253)
    codes0, _ = npy_prefix(panel, "codes.npy", 30, 30)
    dates, codes = dates0.astype(str).tolist(), codes0.astype(str).tolist()
    if dates != sorted(set(dates)) or codes != universe["industries"]:
        raise ValueError("SPINE_OR_FIXED_UNIVERSE_MISMATCH")
    end = dates.index(design["consumed_outcome_end"]) + 1
    if end != design["allowed_return_rows"]:
        raise ValueError("CONSUMPTION_BOUNDARY_MISMATCH")
    for h in (5, 10):
        if dates[end - h - 1] != design["last_mature_signal"][str(h)]:
            raise ValueError("EXACT_MATURITY_ENDPOINT_MISMATCH")
    if output.exists() and any(output.iterdir()):
        raise ValueError("FRESH_PRIVATE_VIEW_REQUIRED")
    receipt: dict[str, Any] = {
        "label": LABEL,
        "design_sha256": DESIGN_SHA,
        "internal_design_commit": LOCK_COMMIT,
        "authorization": design["access_scope"],
        "owner_task_sha256": design["owner_task_sha256"],
        "vendor_grant_or_production_admission": False,
        "historical_independent_unseen_access_certified": False,
        "panel_sha256": design["panel_sha256"],
        "source_commit": design["source_commit"],
        "last_outcome": dates[end - 1],
        "return_rows": end,
        "original_feature_rows": design["allowed_original_feature_rows"],
        "later_numeric_rows_decoded": 0,
        "boundary_persisted_before_numeric_decode": True,
        "preparation_isolation": isolation,
    }
    write(output / "predecode-boundary.json", receipt)
    returns, rr = npy_prefix(panel, "returns.npy", end, end)
    features, fr = npy_prefix(panel, "features.npy", 1132, 1132)
    if returns.shape != (1252, 30) or features.shape != (1132, 30, len(FACTORS_19)):
        raise ValueError("FROZEN_SHAPE_MISMATCH")
    if not np.isfinite(returns[1:]).all() or np.any(returns[1:] <= -1):
        raise ValueError("FIXED_UNIVERSE_RETURN_QUALITY_BLOCKED")
    rebuilt = reversal_features(returns[:1132])
    original = features[:, :, [FACTORS_19.index("rev5"), FACTORS_19.index("rev10")]]
    if not np.array_equal(np.isfinite(rebuilt), np.isfinite(original)):
        raise ValueError("REV_FEATURE_MISSINGNESS_PARITY_FAILED")
    difference = np.abs(rebuilt - original)
    max_error = float(np.nanmax(difference))
    if max_error > 1e-12:
        raise ValueError("EXISTING_REV_DEFINITION_PARITY_FAILED")
    reference: dict[str, list[float]] = {}
    reference_counts: dict[str, int] = {}
    protocol = json.loads(
        contained(root, "config/research/swl1-ridge-v2-protocol.json").read_text()
    )
    for name, expected in design["reference_sha256"].items():
        phase = "development" if "development" in name else "validation"
        trace = json.loads(pinned_bytes(contained(source, name), expected))
        wanted = {dates[i] for i in protocol["split"]["indices"][phase]}
        observed: set[str] = set()
        for fit in trace["fits"]:
            if fit["horizon"] != 10:
                continue
            day = fit["signal_date"]
            values = np.asarray(fit["prediction"], dtype=float)
            if (
                day not in wanted
                or day in observed
                or day in reference
                or values.shape != (30,)
                or not np.isfinite(values).all()
            ):
                raise ValueError("CONSUMED_REFERENCE_IDENTITY_MISMATCH")
            observed.add(day)
            reference[day] = values.tolist()
        if observed != wanted:
            raise ValueError("INCOMPLETE_CONSUMED_REFERENCE")
        reference_counts[phase] = len(observed)
    if sha(panel) != design["panel_sha256"]:
        raise ValueError("SOURCE_CHANGED_DURING_VIEW_CREATION")
    np.save(output / "returns.npy", returns, allow_pickle=False)
    write(output / "metadata.json", {"dates": dates[:end], "codes": codes})
    write(output / "reference.json", reference)
    receipt.update(
        {
            "read_receipts": [rr, fr],
            "rev_reconstruction_max_absolute_error": max_error,
            "reference_signal_counts": reference_counts,
            "reference_sha256": design["reference_sha256"],
            "view_sha256": {
                name: sha(output / name)
                for name in ("returns.npy", "metadata.json", "reference.json")
            },
        }
    )
    write(output / "receipt.json", receipt)
    return receipt


def load_view(
    root: Path, source: Path
) -> tuple[Any, list[str], list[str], dict[str, Any], dict[str, Any]]:
    design = load_design(root)
    isolation = isolated_inputs([root, source])
    receipt = json.loads(contained(source, "receipt.json").read_text())
    if (
        receipt["design_sha256"] != DESIGN_SHA
        or receipt["owner_task_sha256"] != design["owner_task_sha256"]
        or receipt["return_rows"] != 1252
        or receipt["last_outcome"] != "2026-09-29"
        or receipt["panel_sha256"] != design["panel_sha256"]
    ):
        raise ValueError("BOUNDED_VIEW_IDENTITY_MISMATCH")
    for name in ("returns.npy", "metadata.json", "reference.json"):
        if sha(contained(source, name)) != receipt["view_sha256"][name]:
            raise ValueError("BOUNDED_VIEW_HASH_MISMATCH")
    metadata = json.loads(contained(source, "metadata.json").read_text())
    numeric = contained(source, "returns.npy")
    with numeric.open("rb") as handle:
        if np.lib.format.read_magic(handle) != (1, 0):
            raise ValueError("BOUNDED_NPY_VERSION_REQUIRED")
        shape, _, dtype = np.lib.format.read_array_header_1_0(handle)
        if (
            shape != (1252, 30)
            or dtype != np.dtype("float64")
            or numeric.stat().st_size != handle.tell() + 1252 * 30 * 8
        ):
            raise ValueError("PHYSICAL_VIEW_BOUNDARY_MISMATCH")
        # No payload has been converted yet. The file holds exactly the prefix.
        handle.seek(0)
        returns = np.load(handle, allow_pickle=False)
    dates, codes = metadata["dates"], metadata["codes"]
    if (
        returns.shape != (1252, 30)
        or len(dates) != 1252
        or dates != sorted(set(dates))
        or codes != json.loads(contained(root, design["universe_file"]).read_text())["industries"]
        or dates[-1] != design["consumed_outcome_end"]
    ):
        raise ValueError("PHYSICAL_VIEW_BOUNDARY_MISMATCH")
    receipt["research_worker_isolation"] = isolation
    return (
        returns,
        dates,
        codes,
        json.loads(contained(source, "reference.json").read_text()),
        receipt,
    )
