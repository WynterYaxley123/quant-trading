"""Production STRICT pit evidence summary (metadata only).

Reads the already-built immutable production packages and the frozen verified
mapping registry, re-derives the constituent-set containment proof for every
benchmark whose official weight vector is complete, and writes one small
machine-readable summary. It performs no collection, changes no package, and
carries no constituent rows -- only mapping metadata, package identifiers,
hashes and availability instants.

The output answers one question honestly: for each target L2, does the
production evidence prove the strict containment condition, and does the frozen
verified registry carry active strict rows for it?
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.etf_quant.runtime_paths import evidence_root  # noqa: E402
from strategies.etf_quant.domain.industry_level import default_taxonomy  # noqa: E402
from strategies.etf_quant.evidence.schema import WEIGHT_COMPLETE  # noqa: E402
from strategies.etf_quant.evidence.strict import (  # noqa: E402
    CONTAINMENT_IDENTITY,
    derive_strict_mapping_evidence,
    prove_constituent_containment,
)

RUNTIME = evidence_root("PIT")
PACKAGES = RUNTIME / "packages"
BOOK = RUNTIME / "adapter-tests" / "production_evidence_book_v1.json"
REGISTRY = REPO / "strategies" / "etf_quant" / "config" / "verified_mappings_v1.json"
TARGET = REPO / "reports" / "etf_quant" / "production_strict_pit_evidence_summary_v1.json"

HISTORICAL_REFERENCE_CUTOFF = "2026-09-24"


def _load(path: Path):
    return json.loads(path.read_bytes().decode("utf-8"))


def _sha(path: Path) -> str:
    from hashlib import sha256

    return sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def main() -> int:
    taxonomy = default_taxonomy()
    snapshot_doc = _load(PACKAGES / "classification" / "SWS_L2_CURRENT_SNAPSHOT_20260929.json")
    snapshot = snapshot_doc["snapshot"]
    stock_to_l2 = {row["security_code"]: row["shenwan_l2_code"] for row in snapshot["rows"]}
    snapshot_hash = snapshot_doc.get("package_hash")

    registry_doc = _load(REGISTRY)
    verified_rows = [
        row for row in registry_doc["entries"] if row.get("verification_status") == "VERIFIED"
    ]

    # ETF -> benchmark tracking pairs, taken from the already-built book.
    book = _load(BOOK)
    tracking: dict[str, list[str]] = {}
    for record in book["records"]:
        tracking.setdefault(record["benchmark_code"], []).append(record["etf_code"])

    entries = []
    proven = rejected = 0
    for path in sorted((PACKAGES / "exposure").glob("*.json")):
        exposure_doc = _load(path)
        exposure = exposure_doc["exposure"]
        benchmark = exposure["benchmark_code"]
        weights_doc = _load(PACKAGES / "weights" / f"{benchmark}_weights_v1.json")
        vector = weights_doc["vector"]
        constituents = [row["security_code"] for row in vector["rows"]]
        target = exposure["largest_l2_code"]
        proof = prove_constituent_containment(
            constituents=constituents, stock_to_l2=stock_to_l2, target_l2_code=target
        )
        weight_quality = vector["weight_quality"]
        record = derive_strict_mapping_evidence(
            benchmark_code=benchmark,
            target_l2_code=target,
            target_l2_name=taxonomy.name_of(target),
            etf_code=(sorted(set(tracking.get(benchmark, ()))) or ["UNTRACKED"])[0],
            etf_name="",
            constituents=constituents,
            stock_to_l2=stock_to_l2,
            target_l2_exposure=float(dict(exposure["l2_weights"])[target]),
            target_is_largest=exposure["largest_l2_code"] == target,
            unmapped_weight=float(exposure["unmapped_weight"]),
            weight_quality=weight_quality,
            production_available_at=exposure["production_available_at"],
            input_package_hashes=exposure["input_package_hashes"],
            available_from=exposure["production_available_at"],
        )
        strict_rows = [
            {
                "etf_code": row["etf_code"],
                "etf_name": row["etf_name"],
                "tracking_index_code": row["tracking_index_code"],
                "mapping_method": row["mapping_method"],
                "source_sha256": row["source_sha256"],
                "source_retrieved_at": row["source_retrieved_at"],
                "evidence_observed_at": row["evidence_observed_at"],
                "verified_at": row["verified_at"],
                "available_at": row["available_at"],
                "effective_from": row["effective_from"],
            }
            for row in verified_rows
            if row["industry_code"] == target and row["tracking_index_code"] == benchmark
        ]
        if record.admission_status == "ADMITTED":
            proven += 1
        else:
            rejected += 1
        entries.append(
            {
                "benchmark_code": benchmark,
                "target_l2_code": target,
                "target_l2_name": taxonomy.name_of(target),
                "containment": proof.as_dict(),
                "containment_proven": proof.proven,
                "weight_quality": weight_quality,
                "weight_quality_recomputed": vector["weight_quality"] == WEIGHT_COMPLETE,
                "declared_constituent_count": vector["declared_constituent_count"],
                "weight_sum": vector["weight_sum"],
                "target_l2_exposure": record.target_l2_exposure,
                "target_is_largest": record.target_is_largest,
                "unmapped_weight": record.unmapped_weight
                if hasattr(record, "unmapped_weight")
                else float(exposure["unmapped_weight"]),
                "mapping_type": record.mapping_type,
                "admission_status": record.admission_status,
                "rejection_reason": record.rejection_reason,
                "production_available_at": record.production_available_at,
                "constituent_effective_date": vector["constituent_effective_date"],
                "package_ids": {
                    "weights": f"{benchmark}_weights_v1",
                    "exposure": f"{benchmark}_l2_exposure_v1",
                    "classification_snapshot": snapshot["snapshot_id"],
                },
                "package_hashes": {
                    "weights_package_hash": weights_doc.get("package_hash"),
                    "exposure_package_hash": exposure_doc.get("package_hash"),
                    "classification_package_hash": snapshot_hash,
                },
                "input_package_hashes": list(exposure["input_package_hashes"]),
                "tracked_etf_codes": sorted(set(tracking.get(benchmark, ()))),
                "verified_strict_rows": strict_rows,
            }
        )

    summary: dict = {
        "schema_version": "1.0.0",
        "artifact": "PRODUCTION_STRICT_PIT_EVIDENCE_SUMMARY_V1",
        "identity": CONTAINMENT_IDENTITY,
        "generated_at": _now(),
        "historical_reference_cutoff": HISTORICAL_REFERENCE_CUTOFF,
        "historical_reference_note": (
            "Forward-only like every other production package: nothing here may be "
            f"used at {HISTORICAL_REFERENCE_CUTOFF}. This summary is a derived "
            "review artifact over already-built immutable packages; it performs no "
            "collection and changes no package."
        ),
        "strict_semantics": (
            "benchmark constituent set is contained in the target L2 membership set "
            "(every constituent classified, every classification equal to the target, "
            "on a complete official weight vector with zero unmapped weight). "
            "Runtime STRICT admission still flows through VERIFIED_MAPPING_REGISTRY_V1 "
            "unchanged; this summary is evidence-layer proof, not a new admission path."
        ),
        "counts": {
            "exposure_packages_scanned": len(entries),
            "containment_proven": proven,
            "containment_rejected": rejected,
            "verified_strict_rows_total": len(verified_rows),
            "verified_strict_rows_matched": sum(len(e["verified_strict_rows"]) for e in entries),
        },
        "verified_registry": {
            "identity": registry_doc["registry_identity"],
            "path": str(REGISTRY.relative_to(REPO)).replace("\\", "/"),
            "sha256": _sha(REGISTRY),
            "rows": [
                {
                    "industry_code": row["industry_code"],
                    "etf_code": row["etf_code"],
                    "tracking_index_code": row["tracking_index_code"],
                    "mapping_method": row["mapping_method"],
                    "source_sha256": row["source_sha256"],
                    "source_file": row["source_file"],
                    "available_at": row["available_at"],
                    "effective_from": row["effective_from"],
                    "verification_status": row["verification_status"],
                }
                for row in registry_doc["entries"]
            ],
        },
        "classification_snapshot": {
            "snapshot_id": snapshot["snapshot_id"],
            "package_hash": snapshot_hash,
            "security_count": snapshot["security_count"],
            "conflict_count": snapshot["conflict_count"],
            "evidence_available_at": snapshot["evidence_available_at"],
        },
        "entries": entries,
        "top5_strict_view": [
            {
                "industry_code": code,
                "industry_name": taxonomy.name_of(code),
                "strict_status": (
                    "STRICT_PIT_AVAILABLE_VIA_VERIFIED_REGISTRY"
                    if any(row["industry_code"] == code for row in verified_rows)
                    else "NO_VERIFIED_STRICT_ROW"
                ),
                "containment_proven_benchmarks": sorted(
                    e["benchmark_code"]
                    for e in entries
                    if e["target_l2_code"] == code and e["containment_proven"]
                ),
                "production_exposure_label_note": (
                    "DeepSeek's production_pit_current_top5_status_v1.json labels this "
                    "industry from the exposure-derived (proxy) channel only; the "
                    "runtime resolves STRICT first from the verified registry."
                ),
            }
            for code in ("3706", "3703", "4901", "4803", "3701")
        ],
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"containment proven: {proven} / {len(entries)}")
    print(f"verified strict rows matched: {summary['counts']['verified_strict_rows_matched']}")
    print(f"written: {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
