"""Non-profitability threshold study and independently frozen V2 registry."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from strategies.etf_quant.domain.industry_level import load_taxonomy
from strategies.etf_quant_v2.mapping import DIRECT, PROXY

from .coverage import digest, external_directory, immutable_bytes, json_bytes
from .protocol import canonical_hash


def build(
    discovery: Path, liquidity: Path, prior: Path, output: Path, candidate_sha256: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence = json.loads((discovery / "discovery.json").read_bytes())
    bars = json.loads(liquidity.read_bytes())
    amounts = {
        r["symbol"]: r["liquidity_amount"]
        for r in bars["receipts"]
        if r["liquidity_amount"] is not None
    }
    older = json.loads(
        (
            prior / "proxy-exposure-v1/exposure-matrix/benchmark_exposure_summary_v1.json"
        ).read_bytes()
    )
    old = {
        r["benchmark_code"]: r
        for r in older["rows"]
        if r["weight_quality"] == "COMPLETE_WEIGHT_SET"
    }
    rows = evidence["candidates"]
    indices = [json.loads(p.read_bytes()) for p in sorted((discovery / "indices").glob("*.json"))]
    study = []
    for threshold in (30, 40, 50):
        eligible = [r for r in rows if r["evidence"]["largest_weight"] >= threshold]
        executable = [r for r in eligible if r["etf_code"] in amounts]
        unique = {r["tracking_index"]: r["evidence"] for r in eligible}
        differences, stability, changed = [], [], 0
        for code, now in unique.items():
            before = old.get(code)
            if before is None or before.get("constituent_date", older["constituent_date"]) == now[
                "effective_date"
            ].replace("-", ""):
                continue
            same = before["largest_l2_code"] == now["largest_industry"]
            stability.append(same)
            if same:
                differences.append(abs(now["largest_weight"] - before["largest_l2_weight"]))
            changed += before["largest_l2_weight"] >= threshold and (
                not same or now["largest_weight"] < threshold
            )
        study.append(
            {
                "threshold_percent": threshold,
                "evidence_industry_coverage": len(
                    {r["evidence"]["largest_industry"] for r in eligible}
                ),
                "executable_industry_coverage": len(
                    {r["evidence"]["largest_industry"] for r in executable}
                ),
                "candidate_etfs": len(eligible),
                "liquidity_admitted_etfs": len(executable),
                "median_index_target_purity": median(
                    [r["largest_weight"] for r in unique.values()]
                ),
                "minimum_index_dominance_margin": min(
                    r["largest_weight"] - r["second_weight"] for r in unique.values()
                ),
                "median_valid_20d_amount": median([amounts[r["etf_code"]] for r in executable])
                if executable
                else None,
                "cross_industry_same_etf_collisions": len(executable)
                - len({r["etf_code"] for r in executable}),
                "report_date_comparable_indices": len(stability),
                "largest_industry_stability_fraction": sum(stability) / len(stability)
                if stability
                else None,
                "median_report_date_exposure_change_pp": median(differences)
                if differences
                else None,
                "report_date_admission_losses": changed,
            }
        )
    # Coverage is bounded by complete official disclosures and actual liquidity.
    # Choose the middle purity floor; neither returns nor model scores enter.
    chosen = 40
    eligible = [r for r in rows if r["evidence"]["largest_weight"] >= chosen]
    available = datetime.now(timezone.utc).isoformat()
    names = load_taxonomy().industry_names
    entries = []
    vectors = {}
    for item in sorted(eligible, key=lambda r: (r["evidence"]["largest_industry"], r["etf_code"])):
        value, source = item["evidence"], item["evidence"]["source"]
        direct = value["direct_containment"]
        code = value["largest_industry"]
        entries.append(
            {
                "industry_code": code,
                "industry_name": names.get(code, code),
                "etf_code": item["etf_code"],
                "etf_name": item["name"],
                "tracking_index": item["tracking_index"],
                "mapping_class": DIRECT if direct else PROXY,
                "compatibility_identifier": "STRICT_MAPPING" if direct else "PROXY_EXPOSURE",
                "confidence": "PRIMARY_FULL_CONSTITUENT_CONTAINMENT"
                if direct
                else "PRIMARY_COMPLETE_WEIGHT_DOMINANT_EXPOSURE",
                "active": True,
                "complete_weights": True,
                "complete_constituent_containment": direct,
                "target_is_largest": True,
                "target_exposure": 100.0 if direct else round(value["largest_weight"], 8),
                "second_exposure": round(value["second_weight"], 8),
                "unknown_exposure": round(value["unknown_weight"], 8),
                "evidence_date": value["effective_date"],
                "membership_date": evidence["membership_as_of"],
                "available_at": available,
                "weight_observed_at": source["observed_at"],
                "weight_source_url": source["url"],
                "weight_source_sha256": source["sha256"],
                "product_source_url": item["source"]["url"],
                "product_source_sha256": item["source"]["sha256"],
                "method": value["method"],
                "constituent_count": value["constituent_count"],
                "redistribution_rights": "REVIEW_REQUIRED",
            }
        )
        vectors[item["tracking_index"]] = {
            "benchmark_code": item["tracking_index"],
            "weights_by_l2": value["industry_weights"],
        }
    vector_bytes = json_bytes(vectors)
    immutable_bytes(output / "exposure-vectors.json", vector_bytes)
    direct_codes = {
        r["industry_code"]
        for r in entries
        if r["mapping_class"] == DIRECT and r["etf_code"] in amounts
    }
    covered = {r["industry_code"] for r in entries if r["etf_code"] in amounts}
    inventory = []
    for code in evidence["universe"]:
        disclosed_indices = {
            r["index_code"]
            for r in indices
            if r.get("complete") and r.get("industry_weights", {}).get(code, 0) > 0
        }
        candidates = [r for r in entries if r["industry_code"] == code]
        inventory.append(
            {
                "industry_code": code,
                "industry_name": names.get(code, code),
                "candidate_etf_codes": [r["etf_code"] for r in candidates],
                "disclosed_indices_with_nonzero_exposure": len(disclosed_indices),
                "mapping_class": DIRECT
                if code in direct_codes
                else PROXY
                if code in covered
                else "NO_RELIABLE_MAPPING",
                "cash_reason": None
                if code in covered
                else "NO_COMPLETE_DOMINANT_FRESH_EVIDENCE_AND_20_SESSION_LIQUID_ETF",
            }
        )
    registry = {
        "schema_version": 1,
        "identity": "ETF_QUANT_V2_INDEPENDENT_MAPPING_REGISTRY",
        "scope": "CURRENT_FORWARD_ONLY",
        "candidate_sha256": candidate_sha256,
        "proxy_threshold": chosen,
        "largest_exposure_required": True,
        "maximum_weight_age_days": 62,
        "maximum_membership_age_days": 45,
        "available_at": available,
        "frozen": True,
        "source_commit": "1650e384a3fd1f67a70144a489acc91432f1df27",
        "membership_source_sha256": evidence["membership_source_sha256"],
        "exposure_vectors_sha256": digest(output / "exposure-vectors.json"),
        "entries": entries,
        "industry_inventory": inventory,
    }
    registry["registry_sha256"] = canonical_hash(registry)
    report = {
        "candidate_sha256": candidate_sha256,
        "registry_sha256": registry["registry_sha256"],
        "frozen_at": available,
        "model_industries": len(inventory),
        "exchange_catalogue_etfs": evidence["exchange_catalogue_etfs"],
        "indices_attempted": evidence["indices_attempted"],
        "complete_weight_indices": evidence["complete_weight_indices"],
        "threshold_study": study,
        "chosen_proxy_threshold": chosen,
        "choice_reason": "40% retains dominant, complete-weight proxies lost at 50%, while rejecting the seven additional low-purity industries admitted at 30%; ranking is 20-session amount then code, never historical NAV. Reporting-date stability is separately disclosed, not assumed.",
        "direct_industries": len(direct_codes),
        "proxy_industries": len(covered - direct_codes),
        "executable_industry_coverage": len(covered),
        "unmapped_industries": len(inventory) - len(covered),
        "registry_candidate_etfs": len(entries),
        "liquidity_admitted_etfs": sum(r["etf_code"] in amounts for r in entries),
        "latest_liquidity_date": bars["data_cutoff"],
        "evidence_date_range": [
            min(r["evidence_date"] for r in entries),
            max(r["evidence_date"] for r in entries),
        ],
        "v1_registry_changed": False,
        "historical_profitability_used": False,
        "limitations": [
            "Coverage is a measured lower bound; unavailable complete official files remain unmapped.",
            "Classification uses current observed CNEquity/SW assignments, not independent Tier-A PIT proof.",
            "Complete weight snapshots are monthly; freshness is checked at every future signal.",
            "Official disclosure references do not grant redistribution rights to raw constituents.",
        ],
    }
    immutable_bytes(output / "registry.json", json_bytes(registry))
    immutable_bytes(output / "study.json", json_bytes(report))
    return registry, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discovery", type=Path, required=True)
    parser.add_argument("--liquidity", type=Path, required=True)
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-sha256", required=True)
    args = parser.parse_args()
    _, report = build(
        external_directory(args.discovery),
        args.liquidity,
        external_directory(args.prior),
        external_directory(args.output),
        args.candidate_sha256,
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
