"""Current Top5 production evidence status.

Reports, for each of the five historical engineering Top5 industries, what the
*production* evidence registry can actually support -- which is a statement about
what would be available at a future decision instant, not a result for 2026-09-24.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "etf_quant"))

import build_production_pit_evidence as build  # noqa: E402

from strategies.etf_quant.domain.industry_level import default_taxonomy  # noqa: E402
from strategies.etf_quant.evidence import SourcePin  # noqa: E402

RUNTIME = Path(
    os.environ.get(
        "ETF_QUANT_PIT_ROOT", r"D:\QuantForge\runtime\etf-quant-v1\production-pit-evidence-v1"
    )
)
REPORTS = RUNTIME / "reports"
PACKAGES = RUNTIME / "packages"
SOURCE_ROOT = RUNTIME / "adapter-sources"

TOP5 = ("3706", "3703", "4901", "4803", "3701")
INDUSTRY_NAMES = {
    "3706": "医疗服务",
    "3703": "生物制品",
    "4901": "证券Ⅱ",
    "4803": "股份制银行Ⅱ",
    "3701": "化学制药",
}


def load_json(path: Path):
    return json.loads(path.read_bytes().decode("utf-8"))


def rebuild_tracking(observed_at: str) -> dict[str, list[dict]]:
    """Re-derive ETF -> benchmark relations from the pinned official catalogues.

    The catalogs themselves are the pinned evidence; the parsed relation is a
    deterministic function of them, so it can be rebuilt at audit time instead of
    being stored a second time.
    """
    pin = SourcePin(SOURCE_ROOT)
    relations, _diagnostics = build.collect_tracking_relations(
        pin=pin, observed_at=observed_at, available_at=observed_at, valid_from="2026-09-30"
    )
    by_benchmark: dict[str, list[dict]] = {}
    for relation in relations:
        by_benchmark.setdefault(relation.benchmark_code, []).append(relation.as_dict())
    return by_benchmark


def main() -> int:
    taxonomy = default_taxonomy()
    registry = load_json(REPORTS / "production_pit_evidence_registry_v1.json")
    build_report = load_json(REPORTS / "build_report_v1.json")
    book = load_json(RUNTIME / "adapter-tests" / "production_evidence_book_v1.json")
    tracking = rebuild_tracking(registry["created_at"])

    # Derived exposure per benchmark, recomputed from the package artifacts.
    exposures: dict[str, dict] = {}
    for path in sorted((PACKAGES / "exposure").glob("*.json")):
        document = load_json(path)
        exposures[document["exposure"]["benchmark_code"]] = document["exposure"]

    by_industry: dict[str, list[dict]] = {code: [] for code in TOP5}
    for benchmark_code, exposure in sorted(exposures.items()):
        weights = {code: weight for code, weight in exposure["l2_weights"]}
        for target in TOP5:
            if target not in weights:
                continue
            others = [w for code, w in weights.items() if code != target]
            second = max(others) if others else 0.0
            target_weight = float(weights[target])
            largest = exposure["largest_l2_code"] == target
            production_available_at = exposure["production_available_at"]
            etfs = tracking.get(benchmark_code, [])
            by_industry[target].append(
                {
                    "benchmark_code": benchmark_code,
                    "target_l2_exposure": round(target_weight, 6),
                    "target_is_largest": largest,
                    "dominance_margin": round(target_weight - second, 6),
                    "production_available_at": production_available_at,
                    "input_package_hashes": exposure["input_package_hashes"],
                    "etf_candidates": sorted(r["etf_code"] for r in etfs),
                    "passes_b40": target_weight >= 40.0 and largest,
                }
            )

    industries = []
    for code in TOP5:
        candidates = sorted(
            by_industry[code], key=lambda row: (-row["target_l2_exposure"], row["benchmark_code"])
        )
        admitted = [row for row in candidates if row["passes_b40"]]
        if admitted:
            status = "PRODUCTION_PIT_PROXY_AVAILABLE"
            best = admitted[0]
        elif candidates:
            status = "PRODUCTION_EVIDENCE_PRESENT_BUT_B40_REJECTED"
            best = candidates[0]
        else:
            status = "EVIDENCE_INCOMPLETE_FAIL_CLOSED_TO_CASH"
            best = None
        industries.append(
            {
                "industry_code": code,
                "industry_name": INDUSTRY_NAMES.get(code) or taxonomy.name_of(code),
                "status": status,
                "admitted_proxy_benchmarks": len(admitted),
                "candidate_benchmarks": len(candidates),
                "best_candidate": best,
                "candidates": [
                    {
                        "benchmark_code": row["benchmark_code"],
                        "target_l2_exposure": row["target_l2_exposure"],
                        "target_is_largest": row["target_is_largest"],
                        "dominance_margin": row["dominance_margin"],
                        "production_available_at": row["production_available_at"],
                        "passes_b40": row["passes_b40"],
                        "etf_count": len(row["etf_candidates"]),
                        "etf_codes": row["etf_candidates"][:5],
                    }
                    for row in candidates[:6]
                ],
            }
        )

    strict_rows = [
        row for row in book["records"] if row["industry_code"] in TOP5 and row["etf_code"]
    ]
    strict_registry = (  # noqa: F841 -- Keep validation/construction side effects even when result is unused.
        load_json(REPORTS / "strict_mapping_status_v1.json")
        if (REPORTS / "strict_mapping_status_v1.json").exists()
        else None
    )

    report = {
        "schema_version": "1.0.0",
        "artifact": "PRODUCTION_PIT_CURRENT_TOP5_STATUS_V1",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "reference_note": (
            "This is the FUTURE-AVAILABLE evidence state, not a 2026-09-24 run result. "
            "Every package is forward-only with production_available_at on or after "
            "2026-09-30, so none of it may be used at 2026-09-24."
        ),
        "historical_engineering_top5": list(TOP5),
        "production_available_from": registry["production_available_from"],
        "classification_snapshot_id": registry["classification_snapshot_id"],
        "registry_id": registry["registry_id"],
        "industries": industries,
        "summary": {
            "proxy_available": sum(
                1 for row in industries if row["status"] == "PRODUCTION_PIT_PROXY_AVAILABLE"
            ),
            "rejected_by_b40": sum(
                1
                for row in industries
                if row["status"] == "PRODUCTION_EVIDENCE_PRESENT_BUT_B40_REJECTED"
            ),
            "fail_closed_to_cash": sum(
                1 for row in industries if row["status"].startswith("EVIDENCE_INCOMPLETE")
            ),
            "strict_pit_records": len(strict_rows),
        },
        "known_gaps": build_report.get("derivation", {}).get("failure_reasons", {}),
    }
    target = REPORTS / "production_pit_current_top5_status_v1.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    for row in industries:
        best = row["best_candidate"]
        detail = (
            f"best={best['benchmark_code']} exposure={best['target_l2_exposure']:.2f} "
            f"largest={best['target_is_largest']} etfs={len(best['etf_candidates'])}"
            if best
            else "no complete official benchmark evidence"
        )
        print(f"  {row['industry_code']} {row['industry_name']:<12} {row['status']:<45} {detail}")
    print("written:", target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
