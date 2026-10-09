"""Public artifact consistency; no source, daily returns or private replay access."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from research.swl1_failure_forensics.boundary import FROZEN, contained, sha
from research.swl1_failure_forensics.report import public_safe

from .charts import CHARTS
from .design import DESIGN_SHA, LABEL, LOCK_COMMIT, REPORT_DIR, load_design
from .study import decision

REPORTS = (
    "exploratory-design-manifest.json",
    "data-boundary.json",
    "signal-definitions.json",
    "research-summary.json",
    "model-comparison.json",
    "temporal-robustness.json",
    "industry-sensitivity.json",
    "research-decision.json",
)


def verify_reports(root: Path) -> dict[str, Any]:
    design = load_design(root)
    reports = {}
    for name in REPORTS:
        reports[name] = json.loads(contained(root, f"{REPORT_DIR}/{name}").read_text())
        public_safe(reports[name])
        if reports[name]["label"] != LABEL:
            raise ValueError("EXPLORATORY_LABEL_REQUIRED")
    manifest = reports["exploratory-design-manifest.json"]
    if (
        manifest["manifest"] != design
        or manifest["manifest_sha256"] != DESIGN_SHA
        or manifest["internal_lock_commit"] != LOCK_COMMIT
        or manifest["independent_preregistration"]
    ):
        raise ValueError("INTERNAL_DESIGN_PUBLICATION_MISMATCH")
    boundary = reports["data-boundary.json"]
    if (
        boundary["last_outcome"] != design["consumed_outcome_end"]
        or boundary["unseen_outcomes_read"]
        or boundary["vendor_grant_or_production_admission"]
        or boundary["later_numeric_rows_decoded"] != 0
    ):
        raise ValueError("SCIENTIFIC_ACCESS_SCOPE_MISMATCH")
    for r in boundary["read_receipts"]:
        if (
            r["decompressed_read_ahead"] != 0
            or r["payload_bytes_decoded"] != r["payload_bytes_permitted"]
        ):
            raise ValueError("NUMERIC_PREFIX_RECEIPT_MISMATCH")
    models = reports["research-summary.json"]["models"]
    if set(models) != {"S0", "S1", "S2", "S3", "S4", "S5"}:
        raise ValueError("SIX_FIXED_STRUCTURES_REQUIRED")
    for h in ("5", "10"):
        required = reports["research-summary.json"]["accounting"][h]["required_signals"]
        for spec in ("S0", "S1", "S2", "S3", "S4"):
            m = models[spec][h]
            if (
                m["signal_count"] + m["excluded_signals"] != required
                or len(m["calendar_blocks"]) != 4
                or len(m["leave_one_industry_out"]) != 30
            ):
                raise ValueError("COMPLETE_SIGNAL_AND_ROBUSTNESS_ACCOUNTING_REQUIRED")
        if models["S0"][h]["rank_ic"]["mean"] is not None:
            raise ValueError("CONSTANT_SCORE_RANKIC_UNDEFINED")
        for spec in ("S1", "S2", "S3"):
            delta = reports["model-comparison.json"]["ridge_minus_simple"][h][spec]
            if (
                delta["comparison"] != "EXPLORATORY_INFORMED_COMPARISON"
                or delta["matched_signal_count"] != required
                or not np.isclose(
                    delta["delta_rank_ic"]["mean"],
                    models["S4"][h]["rank_ic"]["mean"] - models[spec][h]["rank_ic"]["mean"],
                    rtol=0,
                    atol=1e-12,
                )
            ):
                raise ValueError("MATCHED_COMPARISON_MISMATCH")
    outcome = reports["research-decision.json"]
    if outcome["decision"] != decision(models) or any(
        outcome[k]
        for k in (
            "independent_validation_created",
            "new_formal_model_created",
            "V3_trained",
            "formal_forecasts_created",
            "real_orders_created",
        )
    ):
        raise ValueError("EXPLORATORY_DECISION_OR_LIFECYCLE_MISMATCH")
    if models["S5"]["5"]["status"] != "NOT_APPLICABLE_NO_FROZEN_H5_REFERENCE":
        raise ValueError("NO_SYNTHETIC_FROZEN_H5_REFERENCE")
    for name, expected in {
        **FROZEN,
        **design["reused_implementation_sha256"],
        design["universe_file"]: design["universe_sha256"],
    }.items():
        if sha(contained(root, name)) != expected:
            raise ValueError("FROZEN_SOURCE_OR_ARTIFACT_CHANGED")
    for name in CHARTS:
        body = contained(root, f"{REPORT_DIR}/{name}").read_text()
        if (
            "EXPLORATORY_POST_HOC" not in body
            or "2026-09-29" not in body
            or "<script" in body
            or "<image" in body
        ):
            raise ValueError("AGGREGATE_CHART_LABEL_OR_EMBED_MISMATCH")
    return {
        "status": "PUBLIC_AGGREGATES_AND_FROZEN_HASHES_VERIFIED",
        "reports": 8,
        "charts": 6,
        "numeric_source_access": False,
        "independent_validation": False,
    }
