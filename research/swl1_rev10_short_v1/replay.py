"""Owner-authorized private replay from the existing physically bounded PR36 view."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research.swl1_failure_forensics.boundary import contained, sha
from research.swl1_short_horizon_exploration.boundary import load_view
from research.swl1_short_horizon_exploration.verify import verify_reports

from .model import CODES, score, summarize_ranking

SPEC = "config/research/swl1-rev10-short-v1.json"


def load_spec(root: Path) -> tuple[dict[str, Any], str]:
    leaf = contained(root, SPEC)
    spec = json.loads(leaf.read_text(encoding="utf-8"))
    universe = contained(root, spec["universe_file"])
    if (
        spec["lookback"] != 10
        or spec["primary_horizon"] != 10
        or spec["secondary_horizon"] != 5
        or spec["training_required"] is not False
        or spec["model_type"] != "FIXED_RULE"
        or spec["formal_preregistration_active"] is not False
        or spec["production_source_admitted"] is not False
        or sha(universe) != spec["universe_sha256"]
        or tuple(json.loads(universe.read_text())["industries"]) != CODES
    ):
        raise ValueError("FIXED_RESEARCH_SPEC_REQUIRED")
    return spec, sha(leaf)


def write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def replay(root: Path, view: Path, output: Path) -> dict[str, Any]:
    spec, model_hash = load_spec(root)
    verify_reports(root)
    # Pins come from the immutable public PR36 boundary, not a mutable private receipt.
    boundary = json.loads(
        contained(
            root, "reports/research/swl1_short_horizon_exploration/data-boundary.json"
        ).read_text()
    )
    for name, expected in spec["view_sha256"].items():
        if boundary["view_sha256"][name] != expected or sha(contained(view, name)) != expected:
            raise ValueError("PR36_PRIVATE_VIEW_HASH_MISMATCH")
    if output.resolve() != output or any(
        (output, *output.parents)[i].is_symlink() for i in range(len(output.parents) + 1)
    ):
        raise ValueError("PRIVATE_OUTPUT_PATH_REQUIRED")
    if any((parent / ".git").exists() for parent in (output, *output.parents)):
        raise ValueError("PRIVATE_OUTPUT_OUTSIDE_GIT_REQUIRED")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("FRESH_PRIVATE_PREVIEW_REQUIRED")
    returns, dates, codes, _, receipt = load_view(root, view)
    asof = dates[-1]
    result = score(returns, tuple(dates), tuple(codes), asof=asof, cutoff=spec["historical_cutoff"])
    universe = json.loads(contained(root, spec["universe_file"]).read_text())
    names = {item["code"]: item["name"] for item in universe["metadata"] if item.get("name")}
    generation = "PR36_BOUNDED_VIEW_" + spec["view_sha256"]["returns.npy"]
    ranking = summarize_ranking(result, names=names, asof=asof, source_generation=generation)
    observation = {
        "model_name": spec["model_name"],
        "model_hash": model_hash,
        "status": "HISTORICAL_REPLAY",
        "namespace": "RESEARCH_REPLAY_ONLY",
        "asof": asof,
        "cutoff": spec["historical_cutoff"],
        "count": 30,
        "window_sessions": dates[-10:],
        "source_commit": spec["source_commit"],
        "source_generation": generation,
        "input_sha256": spec["view_sha256"],
        "names_reference_sha256": spec["universe_sha256"],
        "future_numeric_rows_read": 0,
        "formal_forecast": False,
        "pit": boundary["pit"],
        "original_historical_access_isolation": "NOT_CERTIFIED",
        "worker_isolation": receipt["research_worker_isolation"],
    }
    write(output / "observation.json", observation)
    write(
        output / "scores.json",
        {"rows": sorted(ranking["rows"], key=lambda row: row["industry_code"])},
    )
    write(output / "ranking.json", ranking)
    manifest = {
        "schema_version": 1,
        "namespace": "RESEARCH_REPLAY_ONLY",
        "model_hash": model_hash,
        "asof": asof,
        "source_commit": spec["source_commit"],
        "count": 30,
        "files": {
            name: sha(output / name) for name in ("observation.json", "scores.json", "ranking.json")
        },
        "implementation_sha256": {
            name: sha(contained(root, f"research/swl1_rev10_short_v1/{name}"))
            for name in ("model.py", "replay.py")
        },
    }
    write(output / "manifest.json", manifest)
    integrity = {
        "manifest_sha256": sha(output / "manifest.json"),
        "files": manifest["files"],
        "namespace": "RESEARCH_REPLAY_ONLY",
    }
    write(output / "integrity.json", integrity)
    return {"status": "HISTORICAL_REPLAY_CREATED", "asof": asof, "count": 30, **integrity}
