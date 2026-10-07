"""Freeze factual admission and one result-free protocol before any real metric."""

from __future__ import annotations

import json
from dataclasses import asdict
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np

from strategies.etf_quant.factors import FACTOR_REGISTRY

from .audit import finalize_feasibility, write
from .protocol import ALPHAS, body, digest, immutable


def preregister(root: Path, repository: Path, source_commit: str) -> dict[str, Any]:
    data = np.load(root / "factual_panel.npz", allow_pickle=False)
    dates, codes = data["dates"].tolist(), data["codes"].tolist()
    report = finalize_feasibility(
        json.loads((root / "data_feasibility.json").read_text()),
        data["features"],
        data["returns"],
        dates,
    )
    write(root / "data_feasibility.json", report)
    # Exchange identities and aggregates are public-safe; stock rows/prices are private.
    public_report = {
        **report,
        "training_windows": {
            k: {
                **v,
                "split": None
                if v["split"] is None
                else {"ranges": v["split"]["ranges"], "purge_sessions": 120},
            }
            for k, v in report["training_windows"].items()
        },
    }
    public = repository / "reports/research/swl1_ridge_v1"
    immutable(public / "data_feasibility.json", public_report)
    taxonomy = json.loads((root / "taxonomy.json").read_text())
    immutable(repository / "config/research/swl1-ridge-v1-taxonomy.json", taxonomy)
    names = {r["industry_code"]: r["industry_name"] for r in taxonomy["industries"]}
    universe = {
        "industry_level": 1,
        "industries": codes,
        "admission_rule": report["coverage_admission_rule"],
        "metadata": [
            {
                "code": c,
                "name": names[c],
                "valid_industry_days": report["industry_valid_day_counts"][c],
                "admission_reason": "CONTINUOUS_EXACT_RETURN_HISTORY",
            }
            for c in codes
        ],
        "excluded": report.get("excluded_industries", []),
        "performance_used": False,
    }
    universe_hash = immutable(repository / "config/research/swl1-ridge-v1-universe.json", universe)
    factors = [
        {
            **asdict(spec),
            "level_1_applicable": True,
            "data_dependency": "CLOSE_ONLY_RECONSTRUCTED_INDUSTRY_LEVEL",
            "nan_policy": "PRESERVE_GAPS_AND_ROLLING_WARMUP",
            "leakage_policy": "BACKWARD_LOOKBACK_ONLY",
            "units": "0_TO_100" if name == "rsi" else "DIMENSIONLESS_WITH_HETEROGENEOUS_SCALE",
        }
        for name, spec in FACTOR_REGISTRY.items()
    ]
    immutable(
        public / "factor_audit.json",
        {
            "factors": factors,
            "excluded": [],
            "scaling": "STANDARDIZED",
            "reason": "RSI scale differs from fractional returns and bounded position factors; training-only population scaling.",
            "performance_used": False,
        },
    )
    splits = [v["split"] for v in report["training_windows"].values() if v["split"]]
    split = (
        splits[-1] if splits else None
    )  # Common 24m-eligible Development for like-for-like selection.
    specifications = (
        [
            {"alpha": alpha, "months": months, "policy": policy}
            for alpha, months, policy in product(ALPHAS, (12, 24), ("A", "B"))
        ]
        if split
        else []
    )
    protocol = {
        "protocol_version": "SWL1_RIDGE_V1_PREREGISTRATION_1",
        "family_id": "swl1_ridge_v1",
        "source_commit": source_commit,
        "research_feasible": report["research_feasible"],
        "data_panel_sha256": digest((root / "factual_panel.npz").read_bytes()),
        "data_contract_hash": digest(body(public_report)),
        "taxonomy_hash": digest(body(taxonomy)),
        "model_universe": codes,
        "model_universe_hash": universe_hash,
        "model_universe_rule": universe["admission_rule"],
        "primary_series": "RECONSTRUCTED_SWL1_EQUAL_WEIGHT",
        "membership_confidence": "RECONSTRUCTED",
        "target": "R_i(t,h) - mean_{j in complete frozen U} R_j(t,h)",
        "horizons": [10, 40, 120],
        "fusion": [0.25, 0.5, 0.25],
        "scaling": "STANDARDIZED",
        "scaling_rule": "Fit population mean/std only on mature training rows; constant scale = 1.",
        "feature_policies": {
            "A": "H10 existing compact five; H40/H120 existing nineteen",
            "B": "Existing nineteen for every horizon",
        },
        "specifications": specifications,
        "search_budget_max": 20,
        "split": split,
        "split_policy": "252 eligible phase signals first, then 126; >=126 Development signals; exact 120 exchange-session purge; common full-window eligibility.",
        "minimum_training_dates": 30,
        "minimum_valid_phase_fraction": 0.9,
        "minimum_industries": 10,
        "development_admission": "All horizons sufficient; every mean RankIC >= -0.02; no provenance/universe/leakage failure.",
        "selection": "Composite mean RankIC descending; 1e-12 primary ties; minimum horizon mean descending; 12m before 24m; alpha descending; policy lexical.",
        "validation_gate": {
            "composite_mean": ">0",
            "median_weighted_daily_horizon_ic": ">0",
            "weighted_positive_fraction": ">=0.55",
            "weighted_raw_top5_bottom5_spread": ">0",
            "positive_horizons": ">=2",
            "minimum_horizon_mean": ">=-0.03",
            "positive_chronological_equal_count_blocks": ">=3/4",
            "integrity": "REQUIRED",
        },
        "final_oos_classification": {
            "STRONG_POSITIVE": "Composite>0; all horizon means>0; weighted positive fraction>=0.60; weighted spread>0; 4/4 positive blocks",
            "POSITIVE": "Composite>0; >=2 positive horizons; fraction>=0.55; spread>0; >=3 positive blocks",
            "NEGATIVE": "Composite<0 and >=3 negative diagnostics among majority horizon means, fraction<0.5, spread<0, <=1 positive blocks",
            "MIXED": "Otherwise, including insufficient valid samples",
        },
        "independent_statistical_confidence": "LIMITED",
        "iid_inference": False,
        "forward_eligibility": "Only Validation PASS plus POSITIVE/STRONG_POSITIVE Final OOS; no publication in this task.",
        "failure_rules": "No same-generation revision/retry; Validation FAIL forbids Final OOS; exclusive phase claims remain consumed after crashes.",
        "implementation_hashes": {
            p.relative_to(repository).as_posix(): digest(p.read_bytes())
            for p in sorted((repository / "research/swl1_ridge_v1").glob("*.py"))
        },
    }
    checksum = immutable(repository / "config/research/swl1-ridge-v1-protocol.json", protocol)
    immutable(
        public / "preregistration.json",
        {
            "protocol_hash": checksum,
            "source_commit": source_commit,
            "performance_computed_before_freeze": False,
            "spec_count": len(specifications),
        },
    )
    return {
        "protocol_hash": checksum,
        "split": None if split is None else split["ranges"],
        "model_universe_size": len(codes),
        "search_specs": len(specifications),
    }


if __name__ == "__main__":
    import sys

    print(json.dumps(preregister(Path("/research"), Path("/workspace"), sys.argv[1]), indent=2))
