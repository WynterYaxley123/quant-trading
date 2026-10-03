"""One diagnostic-motivated Stage 2, preregistered before focused results."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np

from .coverage import digest, immutable_bytes, json_bytes
from .experiment import bootstrap, run_grid, select, validation_open
from .protocol import Candidate, canonical_hash
from .recovery import write_json


def focused_specifications() -> tuple[Candidate, ...]:
    return tuple(
        Candidate(name, horizons, fusion, alpha, months, scaling)
        for (name, horizons, fusion), alpha, months, scaling in product(
            (("S2A", (10, 40, 120), (0.25, 0.5, 0.25)), ("S2C", (10, 40), (1 / 3, 2 / 3))),
            (3.0, 10.0, 30.0),
            (9, 12, 18),
            ("RAW", "TRAIN_ONLY_STANDARDIZED"),
        )
    )


def freeze_focused(
    parent: dict[str, Any], output: Path, stage1: list[dict[str, Any]]
) -> dict[str, Any]:
    if any(r["passes"] for r in stage1):
        raise ValueError("FOCUSED_EXTENSION_NOT_NEEDED")
    policy = json.loads(json.dumps(parent))
    policy.pop("protocol_sha256")
    policy["contract"] = "ETF_QUANT_V2_SINGLE_FOCUSED_EXTENSION"
    policy["parent_protocol_sha256"] = parent["protocol_sha256"]
    policy["stage1"] = [asdict(c) | {"identifier": c.identifier} for c in focused_specifications()]
    policy["selection"]["fold_partition"] = "TARGET_OBSERVABILITY_CALENDAR_BLOCKS"
    policy["reason_before_results"] = (
        "Stage1 has positive high-confidence mean IC/spread but an under-observed calendar fold "
        "fails the unchanged 30-observation floor. Define four contiguous calendar blocks with equal "
        "observable target counts, using availability only, preserving gaps in block bootstrap. "
        "Raw alpha=10 and 12m are the coherent leading region; test 3/10/30 and 9/12/18m. "
        "Retain H120 versus no-long-horizon contrast because incremental evidence is positive yet ESS is low."
    )
    policy["stage1_results_sha256"] = canonical_hash(stage1)
    policy["extension_cycle"] = 1
    policy["protocol_sha256"] = canonical_hash(policy)
    immutable_bytes(output / "protocol.json", json_bytes(policy))
    return policy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metadata = json.loads((args.panel / "panel.json").read_text())
    parent = json.loads((args.output / "protocol.json").read_text())
    stage1 = json.loads((args.output / "grid-development.json").read_text())
    directory = args.output / "stage2"
    directory.mkdir(exist_ok=True)
    policy = freeze_focused(parent, directory, stage1)
    panel = np.load(args.panel / "panel.npz")
    results, retained = run_grid(metadata, panel, policy, directory, focused_specifications())
    winner = select(results)
    if winner is None:
        write_json(
            directory / "status.json",
            {"status": "NO_PASSING_FOCUSED_CANDIDATE", "extension_cycles": 1},
        )
        print("NO_PASSING_FOCUSED_CANDIDATE", flush=True)
        return
    winner["block_uncertainty"] = bootstrap(
        retained[winner["id"] + "/" + winner["mode"]]["result"]["ic_series"]
    )
    frozen = {
        "contract": "ETF_QUANT_V2_DEVELOPMENT_CANDIDATE",
        "selected": winner,
        "protocol_sha256": policy["protocol_sha256"],
        "parent_protocol_sha256": parent["protocol_sha256"],
        "data_sha256": metadata["data_sha256"],
        "stage2_used": True,
        "source_files": {p.name: digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        "mapping_policy": "FROZEN_V1_FORWARD_EVIDENCE_ONLY_WITH_CASH_FALLBACK",
        "final_oos_opened": False,
        "shadow_started": False,
    }
    immutable_bytes(args.output / "development-candidate.json", json_bytes(frozen))
    validation_open(args.output, frozen)
    selected = winner["candidate"]
    spec = Candidate(
        **(
            selected
            | {"horizons": tuple(selected["horizons"]), "fusion": tuple(selected["fusion"])}
        )
    )
    validation_file = args.output / "validation.json"
    if not validation_file.exists():
        validation, _ = run_grid(metadata, panel, policy, directory, (spec,), "VALIDATION")
        chosen = next(r for r in validation if r["mode"] == winner["mode"])
        metrics = chosen["metrics"]
        accepted = (
            metrics["signals"] >= 40
            and metrics.get("mean_rank_ic", -1) > 0
            and metrics.get("mean_spread", -1) > 0
        )
        write_json(
            validation_file,
            {
                "status": "ACCEPTED" if accepted else "FAILED",
                "candidate_sha256": canonical_hash(frozen),
                "results": validation,
                "accepted": accepted,
                "open_count": 1,
                "final_oos_opened": False,
                "development_to_validation_rank_ic": metrics.get("mean_rank_ic", 0)
                - winner["metrics"]["mean_rank_ic"],
            },
        )
    print(
        json.dumps(
            {
                "winner": winner["id"],
                "mode": winner["mode"],
                "validation": json.loads(validation_file.read_text())["status"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
