"""Small, committable summary artifacts for the Codex handoff.

Produces only metadata: identifiers, hashes, counts and availability instants.
No constituent rows, no classification tables, no raw provider bytes.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

RUNTIME = Path(
    os.environ.get(
        "ETF_QUANT_PIT_ROOT", r"D:\QuantForge\runtime\etf-quant-v1\production-pit-evidence-v1"
    )
)
REPORTS = RUNTIME / "reports"
PACKAGES = RUNTIME / "packages"
REPO = Path(__file__).resolve().parents[2]


def _load(path: Path):
    return json.loads(path.read_bytes().decode("utf-8"))


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def package_inventory(folder: str) -> dict:
    directory = PACKAGES / folder
    if not directory.exists():
        return {"count": 0, "hashes": {}}
    hashes = {}
    for path in sorted(directory.glob("*.json")):
        hashes[path.stem] = _load(path).get("package_hash") or _sha(path)
    return {"count": len(hashes), "hashes": hashes}


def main() -> int:
    registry = _load(REPORTS / "production_pit_evidence_registry_v1.json")
    build = _load(REPORTS / "build_report_v1.json")  # noqa: F841 -- Keep validation/construction side effects even when result is unused.
    top5 = _load(REPORTS / "production_pit_current_top5_status_v1.json")
    manifest = _load(REPORTS / "raw_source_manifest_v1.json")
    cross = _load(REPORTS / "classification_cross_check_v1.json")
    book_path = RUNTIME / "adapter-tests" / "production_evidence_book_v1.json"
    book = _load(book_path)

    weights = package_inventory("weights")
    exposures = package_inventory("exposure")
    classifications = package_inventory("classification")

    summary = {
        "schema_version": "1.0.0",
        "artifact": "DEEPSEEK_PRODUCTION_PIT_EVIDENCE_MANIFEST_V1",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "branch": "agent/deepseek-production-pit-evidence-v1",
        "base_sha": "42eb601bfc80991847e301f14387cdff77323b96",
        "registry": {
            "registry_id": registry["registry_id"],
            "identity": registry["identity"],
            "created_at": registry["created_at"],
            "production_available_from": registry["production_available_from"],
            "availability_semantics": registry["availability_semantics"],
            "schema_version": registry["schema_version"],
            "builder_code_hash": registry["builder_code_hash"],
            "derivation_code_hash": registry["derivation_code_hash"],
            "classification_snapshot_id": registry["classification_snapshot_id"],
            "cneqity_pin": registry["cneqity_pin"],
            "known_limitations": registry["known_limitations"],
        },
        "counts": registry["counts"],
        "evidence_packages": {
            "benchmark_weight_packages": weights["count"],
            "derived_exposure_packages": exposures["count"],
            "per_benchmark_classification_packages": classifications["count"],
            "adapter_book_records": len(book["records"]),
            "adapter_book_sha256": _sha(book_path),
            "pinned_raw_sources": manifest["source_count"],
            "pinned_raw_bytes": manifest["total_bytes"],
        },
        "package_hash_manifest": {
            "weights": weights["hashes"],
            "exposure": exposures["hashes"],
        },
        "raw_hash_manifest_digest": sha256(
            json.dumps(
                [row["source_sha256"] for row in manifest["sources"]],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "adapter_compatibility": {
            "loader": "strategies.etf_quant.mapping.pit.load_pit_evidence",
            "selector": "strategies.etf_quant.mapping.pit.select_pit_mappings",
            "real_package_tests": "tests/etf_quant/test_production_pit_adapter.py",
            "adapter_modified": False,
            "records_loadable": len(book["records"]),
        },
        "no_backfill": {
            "audit_module": "tests/etf_quant/test_production_pit_no_backfill_audit.py",
            "historical_decision_date_tested": "2026-09-24",
            "evidence_visible_at_2026_09_24": 0,
            "earliest_availability_in_book": min(
                record["available_at"] for record in book["records"]
            ),
        },
        "current_top5_status": top5["summary"],
        "current_top5_detail": [
            {
                "industry_code": row["industry_code"],
                "industry_name": row["industry_name"],
                "status": row["status"],
                "best_benchmark": (row["best_candidate"] or {}).get("benchmark_code"),
                "best_target_l2_exposure": (row["best_candidate"] or {}).get("target_l2_exposure"),
                "best_target_is_largest": (row["best_candidate"] or {}).get("target_is_largest"),
            }
            for row in top5["industries"]
        ],
        "research_cross_check_only": cross,
        "runtime_paths": {
            "root": str(RUNTIME),
            "raw_sources": str(RUNTIME / "adapter-sources"),
            "packages": str(PACKAGES),
            "reports": str(REPORTS),
            "raw_collection": str(RUNTIME / "raw"),
        },
        "builder_commands": [
            "python scripts/etf_quant/build_production_pit_evidence.py "
            "--observed-at <ISO8601 with offset>",
            "python scripts/etf_quant/build_production_pit_top5_status.py",
            "python scripts/etf_quant/build_production_pit_manifest.py",
        ],
        "shadow_epoch_created": False,
        "formal_business_records_created": 0,
    }
    target = REPORTS / "deepseek_production_pit_evidence_manifest_v1.json"
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("written:", target)

    # Committable copies: metadata only.
    commit_dir = REPO / "reports" / "etf_quant"
    commit_dir.mkdir(parents=True, exist_ok=True)
    small_registry = {key: value for key, value in registry.items() if key != "index"}
    small_registry["index_summary"] = {
        "tracking_packages_indexed_in_book": True,
        "weight_package_ids": sorted(weights["hashes"]),
        "exposure_package_ids": sorted(exposures["hashes"]),
    }
    (commit_dir / "production_pit_evidence_registry_v1.json").write_text(
        json.dumps(small_registry, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (commit_dir / "production_pit_current_top5_status_v1.json").write_text(
        json.dumps(top5, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (commit_dir / "deepseek_production_pit_evidence_manifest_v1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    for name in (
        "production_pit_evidence_registry_v1.json",
        "production_pit_current_top5_status_v1.json",
        "deepseek_production_pit_evidence_manifest_v1.json",
    ):
        path = commit_dir / name
        print(f"  {name}: {path.stat().st_size} B sha256={_sha(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
