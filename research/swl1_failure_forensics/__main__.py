"""Default read-only audit; --replay admits only already consumed frozen fits.

Run quantitative code inside the independent developer container. The evidence
root contains only the pinned panel and two read-only consumed lifecycle roots.
No formal evaluators, lifecycle writers, network clients or registries are called.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategies.etf_quant.factors import compute_close_factors

from .boundary import FROZEN, PANEL_SHA, admit, boundary, contained, npy_prefix, sha
from .replay import phase_replay, shared_development
from .report import write


def run(repo: Path, evidence: Path, scratch: Path | None = None) -> dict[str, Any]:
    documents = {name: admit(repo, name, expected) for name, expected in FROZEN.items()}
    protocols = {
        v: documents[f"config/research/swl1-ridge-{v}-protocol.json"] for v in ("v1", "v2")
    }
    candidates = {
        v: documents[f"config/research/swl1-ridge-{v}-candidate.json"] for v in ("v1", "v2")
    }
    implementation = {}
    for protocol in protocols.values():
        for name, expected in protocol["implementation_hashes"].items():
            if sha(contained(repo, name)) != expected:
                raise ValueError("FROZEN_IMPLEMENTATION_HASH_MISMATCH")
            implementation[name] = expected
    panel = contained(evidence, "factual_panel.npz")
    if sha(panel) != PANEL_SHA:
        raise ValueError("FROZEN_PANEL_HASH_MISMATCH")
    feasibility: dict[str, Any] = json.loads(
        contained(repo, "reports/research/swl1_ridge_v1/data_feasibility.json").read_text()
    )
    count = feasibility["trading_sessions"]
    date_array, _ = npy_prefix(panel, "dates.npy", count, count)
    codes_array, _ = npy_prefix(panel, "codes.npy", 30, 30)
    dates, codes = date_array.tolist(), codes_array.tolist()
    if any(p["model_universe"] != codes for p in protocols.values()):
        raise ValueError("FROZEN_UNIVERSE_ALIGNMENT_FAILURE")
    limits = boundary(dates, protocols)
    manifest = {
        "label": "POST_HOC_FAILURE_FORENSICS",
        "frozen_evidence_sha256": FROZEN,
        "frozen_implementation_sha256": implementation,
        "panel_sha256": PANEL_SHA,
        "boundary": limits,
        "unseen_outcomes_read": False,
        "sealed_oos_performance_read": False,
        "formal_validation_reopened": False,
        "new_model_generation": False,
        "source_sha256": {
            p.relative_to(repo).as_posix(): sha(p)
            for p in sorted((repo / "research/swl1_failure_forensics").glob("*.py"))
        },
    }
    if scratch is None:
        return manifest
    scratch = scratch.resolve()
    if scratch.is_relative_to(repo.resolve()) or scratch.is_relative_to(evidence.resolve()):
        raise ValueError("SCRATCH_MUST_BE_INDEPENDENT")
    # Persist admission before the first numeric payload is inflated.
    write(scratch / "evidence-boundary.json", manifest, public=True)
    returns, return_receipt = npy_prefix(
        panel, "returns.npy", limits["permitted_return_rows"], limits["permitted_return_rows"]
    )
    features, feature_receipt = npy_prefix(
        panel, "features.npy", limits["permitted_feature_rows"], limits["permitted_feature_rows"]
    )
    if returns.shape[1:] != (30,) or features.shape[1:] != (30, 19):
        raise ValueError("PANEL_SHAPE_FAILURE")
    closes = np.full_like(returns[: len(features)], np.nan)
    closes[1:] = 100 * np.cumprod(1 + returns[1 : len(features)], axis=0)
    reconstructed = np.stack(
        [
            compute_close_factors(
                pd.Series(closes[:, j], index=pd.DatetimeIndex(dates[: len(features)]))
            ).to_numpy()
            for j in range(30)
        ],
        axis=1,
    )
    factor_error = float(np.nanmax(np.abs(reconstructed - features)))
    if not np.allclose(reconstructed, features, rtol=1e-10, atol=1e-10, equal_nan=True):
        raise ValueError("FROZEN_FACTOR_RECONSTRUCTION_FAILURE")
    summary: dict[str, Any] = {
        "label": "POST_HOC_FAILURE_FORENSICS",
        "not_a_new_validation": True,
        "not_a_new_final_oos": True,
        "not_a_new_model_generation": True,
        "not_preregistered_predictive_evidence": True,
        "read_receipts": [return_receipt, feature_receipt],
        "factor_reconstruction_max_absolute_error": factor_error,
        "input_post_seed_returns_missing": int(np.sum(~np.isfinite(returns[1:]))),
        "phases": {},
        "comparability": {},
    }
    private = {}
    for version in ("v1", "v2"):
        for phase in ("development", "validation"):
            print(f"Frozen forensic replay: {version} {phase}", flush=True)
            expected = (
                candidates[version]["development"]
                if phase == "development"
                else documents[f"reports/research/swl1_ridge_{version}/validation.json"]["metrics"]
            )
            result, trace = phase_replay(
                version,
                phase,
                features,
                returns,
                dates,
                codes,
                protocols[version]["split"]["indices"][phase],
                candidates[version]["spec"],
                expected,
            )
            key = version + "_" + phase
            summary["phases"][key] = result
            private[key] = trace
            write(scratch / (key + "-private-replay.json"), trace)
    summary["comparability"]["shared_development"] = shared_development(
        private["v1_development"], private["v2_development"]
    )
    summary["comparability"]["validation"] = {
        "same_universe": True,
        "same_factual_panel": True,
        "same_target": True,
        "same_signal_dates": False,
        "same_outcomes": False,
        "same_native_block_definition": False,
        "causal_model_effect_identifiable": False,
    }
    summary["factor_drift"] = {
        v: {
            name: (
                validation["pooled_distribution"]["mean"]
                - development["pooled_distribution"]["mean"]
            )
            / development["pooled_distribution"]["std"]
            if development["pooled_distribution"]["std"]
            else None
            for name in summary["phases"][v + "_development"]["factor_names"]
            for development, validation in [
                (
                    summary["phases"][v + "_development"]["factors"][name],
                    summary["phases"][v + "_validation"]["factors"][name],
                )
            ]
        }
        for v in ("v1", "v2")
    }
    summary["replay_parity"] = "PASS"
    summary["frozen_fit_count"] = sum(len(v["fits"]) for v in private.values())
    manifest["read_receipts"] = summary["read_receipts"]
    manifest["private_replay_sha256"] = {
        key: sha(scratch / (key + "-private-replay.json")) for key in private
    }
    manifest["private_lifecycle_sha256"] = {
        f"{v}/{name}": sha(contained(evidence, f"{v}/{name}"))
        for v in ("v1", "v2")
        for name in (
            "candidate.json",
            "development.claim.json",
            "development.result.json",
            "validation.claim.json",
            "validation.result.json",
        )
    }
    write(scratch / "summary.json", summary, public=True)
    write(scratch / "evidence-manifest.json", manifest, public=True)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--scratch", type=Path)
    args = parser.parse_args()
    if args.replay != (args.scratch is not None):
        parser.error("--replay requires independent --scratch; default mode writes nothing")
    manifest = run(args.repo, args.evidence, args.scratch)
    print(json.dumps({"boundary": manifest["boundary"], "numeric_replay": args.replay}, indent=2))


if __name__ == "__main__":
    main()
