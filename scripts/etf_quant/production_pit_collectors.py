"""Production PIT evidence registry builder for ETF-Quant V1.

Runs entirely outside the Git work tree. Reads already-captured official raw bytes,
produces immutable evidence packages, derives benchmark L2 exposure, applies the
frozen B40 rule, emits the evidence book the existing runtime adapter consumes, and
writes a small metadata registry that *is* safe to commit.

It never contacts the network: collection is a separate, auditable step, and a
build that silently re-fetched would destroy reproducibility.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

# Explicit external roots support other machines; existing deployment defaults
# remain compatible. This builder is not part of the portable demo/test flow.
from scripts.etf_quant.production_pit_settings import (
    CSI_REVERSE,
    REPORTS,
    SUBAGENTS,
    SWS_CATALOG,
    SWS_FULL_CATALOG,
    SWS_RAW_L2,
    WEIGHT_SUM_BAND,
)
from scripts.etf_quant.production_pit_settings import REPO as REPO
from strategies.etf_quant.domain.industry_level import default_taxonomy  # noqa: E402
from strategies.etf_quant.evidence import (  # noqa: E402
    SourcePin,
    TrackingRelation,
    build_tracking_relations_from_sse_catalog,
    build_tracking_relations_from_szse_catalog,
    sha256_bytes,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def code_hash_of(module_file: Path) -> str:
    return hashlib.sha256(module_file.read_bytes()).hexdigest()


def load_csi_index_register() -> dict[str, dict]:
    """The official CSI index register, used only to confirm an index exists."""
    candidates = list((SUBAGENTS / "B-csi-weights").glob("csi_index-list_query-index-item.json"))
    register = {}
    for path in candidates:
        doc = load_json(path)
        for row in doc.get("data") or []:
            code = str(row.get("indexCode") or "").strip()
            if code:
                register[code] = {
                    "name": row.get("indexName") or "",
                    "cons_number": row.get("consNumber"),
                }
    return register


def collect_csi_weight_vectors(
    *,
    register: dict[str, dict],
    observed_at: str,
    available_at: str,
    valid_from: str,
    scope: frozenset[str] | None = None,
) -> tuple[dict[str, dict], dict]:
    """Rebuild every benchmark whose reverse-query rows form a complete vector.

    Completeness is decided by the arithmetic, never asserted: the counted
    constituents must equal the count the provider declares on its own rows, and
    the weights must land inside the band the runtime uses.

    ``scope`` restricts the rebuild to benchmarks an ETF actually references, so a
    build pins only the weight vectors that can reach a decision.
    """
    by_index: dict[str, dict[str, dict]] = {}
    for path in sorted(CSI_REVERSE.glob("*.json")):
        try:
            doc = load_json(path)
        except Exception:
            continue
        if doc.get("error"):
            continue
        security = path.stem
        for row in doc.get("data") or []:
            index_code = str(row.get("indexCode") or "").strip()
            if not index_code:
                continue
            if scope is not None and index_code not in scope:
                continue
            by_index.setdefault(index_code, {})[
                str(row.get("securityCode") or security).zfill(6)
            ] = {
                "weight_pct": row.get("weightPct"),
                "cons_number": row.get("consNumber"),
                "security_name": row.get("securityName"),
                "index_name": row.get("indexName"),
                "registry_file": str(path),
            }

    vectors, rejected = (
        {},
        {"sum_out_of_band": 0, "count_mismatch": 0, "no_registry_entry": 0, "unparsable": 0},
    )
    for index_code, members in sorted(by_index.items()):
        if index_code not in register:
            rejected["no_registry_entry"] += 1
            continue
        rows, declared_values, total = [], set(), 0.0
        for security, payload in sorted(members.items()):
            raw_weight = payload["weight_pct"]
            text = raw_weight.strip().rstrip("%") if isinstance(raw_weight, str) else raw_weight
            try:
                weight = float(text)
            except (TypeError, ValueError):
                continue
            if not 0.0 <= weight <= 100.0:
                continue
            rows.append(
                {
                    "security_code": security,
                    "security_name": payload["security_name"],
                    "weight_pct": weight,
                }
            )
            total += weight
            if payload["cons_number"] is not None:
                declared_values.add(str(payload["cons_number"]).strip())
        if not rows:
            rejected["unparsable"] += 1
            continue
        registry_count = register[index_code].get("cons_number")
        declared = None
        if registry_count is not None and str(registry_count).strip().isdigit():
            declared = int(str(registry_count).strip())
        declared_set = {
            int(float(value))
            for value in declared_values
            if re.fullmatch(r"[0-9]+(\.[0-9]+)?", value)
        }
        if declared is None and len(declared_set) == 1:
            declared = declared_set.pop()
        if declared is None:
            rejected["count_mismatch"] += 1
            continue
        total = round(total, 6)
        if len(rows) != declared:
            rejected["count_mismatch"] += 1
            continue
        if not (WEIGHT_SUM_BAND[0] <= total <= WEIGHT_SUM_BAND[1]):
            rejected["sum_out_of_band"] += 1
            continue
        vectors[index_code] = {
            "rows": rows,
            "declared": declared,
            "weight_sum": total,
            "index_name": register[index_code].get("name")
            or members[list(members)[0]]["index_name"],
            "registry_files": sorted({payload["registry_file"] for payload in members.values()}),
        }
    return vectors, rejected


def sws_catalog_name_map() -> dict[str, str]:
    """``801012`` -> ``1105`` style mapping, established by *name* equality only.

    The provider's industry index codes are not arithmetically derivable from the
    sealed taxonomy codes, so the link is made through the official name the
    provider publishes and the official name the sealed taxonomy records. A name
    that does not match exactly, or that matches more than one taxonomy code, is
    dropped — never guessed.
    """
    taxonomy = default_taxonomy()
    by_name: dict[str, list[str]] = {}
    for code in taxonomy.named_industry_codes:
        by_name.setdefault(taxonomy.name_of(code), []).append(code)
    mapping = {}
    # The mapping is read from the UNFILTERED official index-name catalogue, not from
    # the ``indextype=二级行业`` query. That query is the provider's own tagging and it
    # omits ten of the 134 industries the sealed taxonomy names, which silently starved
    # the classification and failed benchmarks closed for no real reason. The
    # unfiltered catalogue resolves all 134, each with exactly one name match.
    rows: list[dict] = []
    if SWS_FULL_CATALOG.exists():
        rows = load_json(SWS_FULL_CATALOG).get("data") or []
    else:
        for path in sorted(SWS_CATALOG.glob("*.json")):
            rows.extend((load_json(path).get("data") or {}).get("results") or [])
    for row in rows:
        index_code = str(row.get("swindexcode") or "").strip()
        name = str(row.get("swindexname") or "").strip()
        if not index_code or not name:
            continue
        matches = by_name.get(name, [])
        if len(matches) == 1:
            mapping[index_code] = matches[0]
    return mapping


def collect_sws_classification(
    *, observed_at: str, available_at: str
) -> tuple[
    dict[str, tuple[str, str, str, str]], dict, list[str], dict, dict[str, str], dict[str, str]
]:
    """Union of official Shenwan L2 industry-index memberships, from verbatim bytes.

    Reads ``raw/sws/raw_members/`` -- the provider's responses stored exactly as
    received, verified to re-fetch to identical SHA-256. The first pass wrapped each
    response in a local envelope, which made the recorded hash unreproducible; that
    tree is kept aside as a superseded draft and is not used here.

    Returns the resolved mapping, conflicts, unparsable rows, diagnostics, the
    earliest official ``beginningdate`` per security, and the retrieval ledger that
    ties every consumed byte stream to its URL and hash.
    """
    index_to_l2 = sws_catalog_name_map()
    taxonomy = default_taxonomy()
    assignments: dict[str, list[tuple[str, str]]] = {}
    per_l2: dict[str, int] = {}
    unparsed = []
    effective: dict[str, str] = {}
    provenance: dict[str, str] = {}
    ledger = {}
    ledger_path = REPORTS / "sws_raw_retrieval_ledger.jsonl"
    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            ledger[str(row.get("index_code"))] = row

    files = sorted(SWS_RAW_L2.glob("*.json"))
    for path in files:
        index_code = path.stem
        l2_code = index_to_l2.get(index_code)
        body = path.read_bytes()
        provenance[index_code] = sha256_bytes(body)
        if l2_code is None:
            continue
        doc = json.loads(body.decode("utf-8"))
        results = (doc.get("data") or {}).get("results") or []
        declared = (doc.get("data") or {}).get("count")
        if declared is not None and len(results) != int(declared):
            unparsed.append(f"INCOMPLETE:{index_code}:{len(results)}!={declared}")
            continue
        per_l2[l2_code] = per_l2.get(l2_code, 0) + len(results)
        for row in results:
            security = str(row.get("stockcode") or "").strip()
            if not re.fullmatch(r"[0-9]{6}", security):
                unparsed.append(f"{index_code}:{security}")
                continue
            assignments.setdefault(security, []).append((l2_code, index_code))
            beginning = row.get("beginningdate")
            if isinstance(beginning, str) and beginning:
                day = beginning[:10]
                if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day):  # noqa: SIM102 -- Preserve independently documented frozen validation branches.
                    if security not in effective or day < effective[security]:
                        effective[security] = day

    resolved: dict[str, tuple[str, str, str, str]] = {}
    conflicts: dict[str, list[str]] = {}
    for security, memberships in sorted(assignments.items()):
        codes = sorted({code for code, _index in memberships})
        if len(codes) > 1:
            conflicts[security] = codes
            continue
        l2 = codes[0]
        resolved[security] = (l2[:2], taxonomy.name_of(l2), l2, taxonomy.name_of(l2))
    diagnostics = {
        "catalog_index_to_l2": len(index_to_l2),
        "member_files": len(files),
        "verbatim_files": len(provenance),
        "ledger_entries": len(ledger),
        "securities_seen": len(assignments),
        "securities_classified": len(resolved),
        "securities_conflicted": len(conflicts),
        "unparsable_rows": len(unparsed),
        "l2_industries_covered": len(per_l2),
        "securities_with_official_beginningdate": len(effective),
        "unmapped_catalog_indices": len(files) - len(index_to_l2),
    }
    return resolved, conflicts, unparsed, diagnostics, effective, provenance


def collect_tracking_relations(
    *, pin: SourcePin, observed_at: str, available_at: str, valid_from: str
) -> tuple[list, dict]:
    relations: list[TrackingRelation] = []
    diagnostics = {}
    sse_pages = sorted((SUBAGENTS / "E-etf-tracking" / "raw").glob("sse_etf_catalog_p*.json"))
    sse_rows: list[dict] = []
    for page in sse_pages:
        body = page.read_bytes()
        doc = json.loads(body.decode("utf-8"))
        sse_rows.extend((doc.get("pageHelp") or {}).get("data") or [])
        pin.pin_bytes(
            relative_path=f"exchange/sse_etf_catalog_{page.stem.split('_')[-1]}.json",
            body=body,
            source_url="https://query.sse.com.cn/commonSoaQuery.do",
            content_type="application/json;charset=UTF-8",
            evidence_observed_at=observed_at,
            source_retrieved_at=observed_at,
            note="SSE fund catalogue page",
        )
    if sse_rows:
        source = pin.require_pinned(
            f"exchange/sse_etf_catalog_{sse_pages[0].stem.split('_')[-1]}.json"
        )
        sse_relations = build_tracking_relations_from_sse_catalog(
            catalog_rows=sse_rows,
            observed_at=observed_at,
            available_at=available_at,
            source=source,
            valid_from=valid_from,
        )
        relations.extend(sse_relations)
        diagnostics["sse_rows"] = len(sse_rows)
        diagnostics["sse_relations"] = len(sse_relations)
        diagnostics["sse_pages"] = len(sse_pages)

    szse_rows: list[dict] = []
    szse_dir = SUBAGENTS / "C-cni-szse"
    pages = sorted(szse_dir.glob("szse_etf_list_p*.json"))
    for page in pages:
        body = page.read_bytes()
        doc = json.loads(body.decode("utf-8"))
        block = doc[0] if isinstance(doc, list) and doc else {}
        szse_rows.extend(block.get("data") or [])
        pin.pin_bytes(
            relative_path=f"exchange/szse_etf_list_{page.stem.split('_')[-1]}.json",
            body=body,
            source_url="https://www.szse.cn/api/report/ShowReport/data",
            content_type="application/json",
            evidence_observed_at=observed_at,
            source_retrieved_at=observed_at,
            note="SZSE ETF catalogue page",
        )
    if szse_rows and pages:
        source = pin.require_pinned(f"exchange/szse_etf_list_{pages[0].stem.split('_')[-1]}.json")
        szse_relations = build_tracking_relations_from_szse_catalog(
            catalog_rows=szse_rows,
            observed_at=observed_at,
            available_at=available_at,
            source=source,
            valid_from=valid_from,
        )
        relations.extend(szse_relations)
        diagnostics["szse_rows"] = len(szse_rows)
        diagnostics["szse_relations"] = len(szse_relations)
        diagnostics["szse_pages"] = len(pages)
    return relations, diagnostics
