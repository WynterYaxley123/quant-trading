"""Deterministic strict-L2 ETF coverage and hypothetical executable scan.

Two read-only tools used by the supply audit:

``coverage_summary``
    Counts how many Shenwan Level-2 industries are strictly executable over the
    current taxonomy, the 2026-09-24 model signal universe and the historical
    union. The three denominators are never merged.

``executable_scan``
    ``HYPOTHETICAL_EXECUTABLE_SCAN_V1`` — walks a fusion ranking from rank 1,
    counting a slot only when the industry has a strictly verified ETF and an
    as-yet-unused ETF can be chosen. This is a feasibility probe, not a policy:
    it is never wired into runtime execution and it never changes the frozen
    Top5 rule.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

STATUS_VOCABULARY = ("VERIFIED_PASS", "VERIFIED_REJECTED", "INSUFFICIENT_EVIDENCE", "NOT_RELEVANT")
LIQUIDITY_PASS = "LIQUIDITY_ADMISSION_PASS"
SCAN_CONTRACT = "HYPOTHETICAL_EXECUTABLE_SCAN_V1"
SCAN_STATUS = "FEASIBILITY_ANALYSIS_ONLY"
REQUIRED_MATRIX_FIELDS = ("l2_code", "l2_name", "l1_name", "strictly_executable",
                          "verified_etf_codes", "current_active", "model_signal_eligible")


class AuditError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def load_coverage_matrix(path: Path) -> dict:
    """Load and validate the committed coverage matrix.

    A row that does not declare executable status explicitly is rejected rather
    than defaulted: an absent verdict must never read as "executable".
    """
    doc = json.loads(Path(path).read_bytes())
    if doc.get("artifact") != "STRICT_L2_ETF_COVERAGE_MATRIX_V1" or doc.get("industry_level") != "SHENWAN_L2":
        raise AuditError("COVERAGE_MATRIX_SCHEMA_BLOCKER")
    rows = doc.get("rows")
    if not isinstance(rows, list) or not rows:
        raise AuditError("COVERAGE_MATRIX_SCHEMA_BLOCKER")
    seen = set()
    for row in rows:
        if not all(field in row for field in REQUIRED_MATRIX_FIELDS):
            raise AuditError("COVERAGE_MATRIX_SCHEMA_BLOCKER")
        if row["l2_code"] in seen or not isinstance(row["strictly_executable"], bool):
            raise AuditError("COVERAGE_MATRIX_SCHEMA_BLOCKER")
        seen.add(row["l2_code"])
        codes = row["verified_etf_codes"]
        if not isinstance(codes, list) or len(set(codes)) != len(codes):
            raise AuditError("COVERAGE_MATRIX_SCHEMA_BLOCKER")
        # Executability and a verified ETF list must agree in both directions.
        if row["strictly_executable"] != bool(codes):
            raise AuditError("COVERAGE_MATRIX_EXECUTABLE_EVIDENCE_BLOCKER")
    return doc


def coverage_summary(matrix: dict) -> dict:
    rows = matrix["rows"]

    def block(name: str, selector) -> dict:
        subset = [row for row in rows if selector(row)]
        executable = [row for row in subset if row["strictly_executable"]]
        return {"universe": name, "total_l2": len(subset), "executable_l2": len(executable),
                "non_executable_l2": len(subset) - len(executable),
                "coverage_ratio": (len(executable) / len(subset)) if subset else None}

    return {
        "current_active": block("CURRENT_ACTIVE_L2_UNIVERSE", lambda r: r["current_active"]),
        "model_signal_at_2026_09_24": block("MODEL_SIGNAL_UNIVERSE_AT_2026_09_24",
                                            lambda r: r["model_signal_eligible"]),
        "historical_union": block("HISTORICAL_L2_UNION", lambda r: r.get("historical_union", False)),
        "etf_count_distribution": _distribution(rows),
        "l1_coverage": _l1(rows),
    }


def _distribution(rows) -> dict:
    buckets = {"0": 0, "1": 0, "2": 0, "3-5": 0, ">5": 0}
    for row in rows:
        count = len(row["verified_etf_codes"])
        if count == 0:
            buckets["0"] += 1
        elif count == 1:
            buckets["1"] += 1
        elif count == 2:
            buckets["2"] += 1
        elif count <= 5:
            buckets["3-5"] += 1
        else:
            buckets[">5"] += 1
    return buckets


def _l1(rows) -> dict:
    out: dict[str, dict] = {}
    for row in rows:
        bucket = out.setdefault(row["l1_name"], {"l2_total": 0, "l2_executable": 0})
        bucket["l2_total"] += 1
        if row["strictly_executable"]:
            bucket["l2_executable"] += 1
    for bucket in out.values():
        bucket["coverage_ratio"] = bucket["l2_executable"] / bucket["l2_total"]
    return out


def executable_scan(ranking, matrix: dict, *, liquidity: dict | None = None,
                    target: int = 5, limit: int | None = None) -> dict:
    """HYPOTHETICAL_EXECUTABLE_SCAN_V1. Feasibility only; no side effects."""
    if limit is not None and limit <= 0:
        raise AuditError("SCAN_LIMIT_BLOCKER")
    entries = {row["l2_code"]: row for row in matrix["rows"]}
    passed = set()
    if liquidity is not None:
        passed = {code for code, row in (liquidity.get("results_by_code") or {}).items()
                  if row.get("status") == LIQUIDITY_PASS}
    ordered = sorted(ranking, key=lambda r: (r["rank"], r["industry_code"]))
    used: set[str] = set()
    selected: list[dict] = []
    depth: dict[int, int] = {}
    for position, row in enumerate(ordered, start=1):
        if limit is not None and position > limit:
            break
        entry = entries.get(row["industry_code"])
        if entry is None or not entry["strictly_executable"]:
            continue
        for code in sorted(entry["verified_etf_codes"]):
            if code in used:
                continue
            if liquidity is not None and code not in passed:
                continue
            used.add(code)
            selected.append({"rank": position, "l2_code": row["industry_code"],
                             "l2_name": entry["l2_name"], "etf_code": code,
                             "score": row.get("fused_score")})
            depth[len(selected)] = position
            break
        if len(selected) == target:
            break
    return {"contract": SCAN_CONTRACT, "status": SCAN_STATUS,
            "production_policy": "NOT_PRODUCTION_POLICY", "frozen_strategy": "NOT_FROZEN_STRATEGY",
            "target": target, "selected": selected, "scan_depth": depth,
            "distinct_etf_count": len(selected), "five_found": len(selected) == target,
            "ranking_length": len(ordered),
            "distinct_industries_reachable": sum(1 for r in matrix["rows"] if r["strictly_executable"])}


def top_n_feasibility(ranking, matrix: dict, *, liquidity=None,
                      limits=(5, 10, 15, 20, 30), target: int = 5) -> dict:
    out = {}
    for limit in limits:
        outcome = executable_scan(ranking, matrix, liquidity=liquidity, target=target, limit=limit)
        out[str(limit)] = {"executable_found": outcome["distinct_etf_count"],
                           "five_found": outcome["five_found"]}
    full = executable_scan(ranking, matrix, liquidity=liquidity, target=target)
    out["full"] = {"executable_found": full["distinct_etf_count"], "five_found": full["five_found"]}
    return out


def sealed_split_guard(source: dict) -> None:
    """Refuse any ranking that is not explicitly an engineering artefact."""
    if source.get("classification") != "HISTORICAL_ENGINEERING_VALIDATION_ONLY":
        raise AuditError("SEALED_SPLIT_GUARD_BLOCKER")
    for key in ("nav_or_performance_generated", "formal_shadow_epoch_created"):
        if source.get(key) is not False:
            raise AuditError("SEALED_SPLIT_GUARD_BLOCKER")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("coverage", "scan"))
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--ranking", type=Path)
    parser.add_argument("--liquidity", type=Path)
    args = parser.parse_args()
    matrix = load_coverage_matrix(args.matrix)
    if args.command == "coverage":
        print(json.dumps(coverage_summary(matrix), ensure_ascii=False, indent=1))
        return 0
    if args.ranking is None:
        raise AuditError("RANKING_REQUIRED")
    source = json.loads(args.ranking.read_bytes())
    sealed_split_guard(source)
    liquidity = json.loads(args.liquidity.read_bytes()) if args.liquidity else None
    result = executable_scan(source["full_engineering_ranking"], matrix, liquidity=liquidity)
    result["top_n_feasibility"] = top_n_feasibility(source["full_engineering_ranking"], matrix,
                                                    liquidity=liquidity)
    result["current_top5"] = [{"rank": r["rank"], "l2_code": r["industry_code"],
                               "strictly_executable": next(row["strictly_executable"]
                                                           for row in matrix["rows"]
                                                           if row["l2_code"] == r["industry_code"])}
                              for r in sorted(source["full_engineering_ranking"],
                                              key=lambda x: x["rank"])[:5]]
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
