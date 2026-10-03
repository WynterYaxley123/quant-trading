"""One Validation-informed Development revision, with no second Validation read."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from .coverage import digest, immutable_bytes, json_bytes
from .experiment import bootstrap, run_grid
from .focused import focused_specifications
from .protocol import canonical_hash
from .recovery import write_json


def robust_selection(results: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [
        r
        for r in results
        if r["passes"]
        and r["mode"] == "HIGH_CONFIDENCE"
        and r["metrics"]["coefficient_norm_cv"] <= 0.2
        and all(f["mean_rank_ic"] > 0 and f["mean_spread"] > 0 for f in r["metrics"]["folds"])
    ]
    if not eligible:
        raise ValueError("NO_ROBUST_DEVELOPMENT_REVISION")
    return sorted(
        eligible,
        key=lambda r: (
            -min(f["mean_rank_ic"] for f in r["metrics"]["folds"]),
            -min(f["mean_spread"] for f in r["metrics"]["folds"]),
            r["metrics"]["coefficient_norm_cv"],
            len(r["candidate"]["horizons"]),
            r["id"],
        ),
    )[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    original = json.loads((args.output / "development-candidate.json").read_text())
    gate = json.loads((args.output / "validation-access.json").read_text())
    # Only failure status is used to authorize this branch; no return series or
    # alternative Validation models are loaded, fitted or compared.
    validation = json.loads((args.output / "validation.json").read_text())
    if validation["accepted"] or gate["candidate_sha256"] != canonical_hash(original):
        raise ValueError("REVISION_NOT_AUTHORIZED_BY_FROZEN_FAILURE")
    directory = args.output / "revision"
    directory.mkdir(exist_ok=True)
    parent = json.loads((args.output / "stage2/protocol.json").read_text())
    policy = json.loads(json.dumps(parent))
    policy.pop("protocol_sha256")
    policy["contract"] = "ETF_QUANT_V2_SINGLE_VALIDATION_INFORMED_REVISION"
    policy["parent_protocol_sha256"] = parent["protocol_sha256"]
    policy["revision_cycles"] = 1
    policy["generation_rule"] = {
        "universe": "UNCHANGED_36_FOCUSED_SPECS_NO_NEW_HYPERPARAMETERS",
        "require": "ORIGINAL_GATES;ALL_FOLDS_POSITIVE_IC_AND_SPREAD;NORM_CV_AT_MOST_0.2",
        "order": "WORST_FOLD_IC;WORST_FOLD_SPREAD;LOWEST_NORM_CV;SIMPLICITY;ID",
        "motivation": "Original Validation has inconsistent chronological direction. Emphasize worst-regime Development robustness; do not select on exact Validation noise.",
        "secondary_validation": None,
        "revision_status": "VALIDATION_INFORMED_NOT_INDEPENDENTLY_VALIDATED",
    }
    policy["protocol_sha256"] = canonical_hash(policy)
    immutable_bytes(directory / "protocol.json", json_bytes(policy))
    metadata = json.loads((args.panel / "panel.json").read_text())
    if digest(args.panel / "panel.npz") != metadata["panel_sha256"]:
        raise ValueError("PANEL_HASH_MISMATCH")
    results, retained = run_grid(
        metadata,
        np.load(args.panel / "panel.npz"),
        policy,
        directory,
        focused_specifications(),
        "DEVELOPMENT",
    )
    winner = robust_selection(results)
    winner["block_uncertainty"] = bootstrap(
        retained[winner["id"] + "/" + winner["mode"]]["result"]["ic_series"]
    )
    frozen = {
        "contract": "ETF_QUANT_V2_VALIDATION_INFORMED_DEVELOPMENT_REVISION",
        "selected": winner,
        "protocol_sha256": policy["protocol_sha256"],
        "data_sha256": metadata["data_sha256"],
        "original_candidate_sha256": canonical_hash(original),
        "validation_access_sha256": digest(args.output / "validation-access.json"),
        "source_files": {p.name: digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        "revision_cycles": 1,
        "validation_accepted": False,
        "independent_validation_of_revision": None,
        "final_oos_opened": False,
        "shadow_started": False,
        "specifications": [asdict(c) for c in focused_specifications()],
    }
    immutable_bytes(directory / "candidate.json", json_bytes(frozen))
    write_json(
        directory / "status.json",
        {
            "status": "VALIDATION_INFORMED_NOT_INDEPENDENTLY_VALIDATED",
            "winner": winner["id"],
            "validation_open_count": gate["open_count"],
        },
    )
    print(
        json.dumps({"winner": winner["id"], "validation": "NOT_REOPENED", "final_oos": "SEALED"}),
        flush=True,
    )


if __name__ == "__main__":
    main()
