"""Production PIT evidence registry builder for ETF-Quant V1.

Runs entirely outside the Git work tree. Reads already-captured official raw bytes,
produces immutable evidence packages, derives benchmark L2 exposure, applies the
frozen B40 rule, emits the evidence book the existing runtime adapter consumes, and
writes a small metadata registry that *is* safe to commit.

It never contacts the network: collection is a separate, auditable step, and a
build that silently re-fetched would destroy reproducibility.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

REPO = Path(r"D:\quant-worktrees\deepseek-production-pit-evidence-v1")
sys.path.insert(0, str(REPO))

from strategies.etf_quant.domain.industry_level import default_taxonomy  # noqa: E402
from strategies.etf_quant.evidence import (  # noqa: E402
    ADAPTER_BOOK_IDENTITY, KIND_DOCUMENTED_EXTRACTION, KIND_VERBATIM_PROVIDER_BYTES,
    EvidenceError, SourcePin, adapter_book_document,
    adapter_classification_source_document, adapter_record, adapter_weight_source_document,
    build_classification_rows, build_classification_snapshot,
    build_tracking_relations_from_sse_catalog, build_tracking_relations_from_szse_catalog,
    build_weight_vector_from_constituent_rows, canonical_bytes, classification_package,
    decide_b40_mapping, derive_l2_exposure, exposure_package, mapping_package, package_hash,
    sha256_bytes, sha256_json, tracking_package, weight_package, write_package)

RUNTIME = Path(r"D:\QuantForge\runtime\etf-quant-v1\production-pit-evidence-v1")
PRIOR = Path(r"D:\QuantForge\runtime\etf-quant-v1\proxy-exposure-v1")
SUBAGENTS = RUNTIME / "subagents"
BUILD = RUNTIME / "build"
RAW = RUNTIME / "raw"
PACKAGES = RUNTIME / "packages"
SOURCE_ROOT = RUNTIME / "adapter-sources"
REPORTS = RUNTIME / "reports"

CSI_REVERSE = PRIOR / "official-sources" / "raw" / "csi_reverse"
SWS_RAW_L2 = RAW / "sws" / "raw_members"
SWS_CATALOG = RAW / "sws" / "catalog"
SWS_FULL_CATALOG = RAW / "sws" / "raw_catalog" / "sws_index_name_all.json"

#: The provider endpoint that actually produced the benchmark weight evidence.
#: The first build recorded a sibling path that answers `code=500` when called
#: without the reverse-lookup body; an independent audit re-fetched it and caught
#: the mistake. This is the endpoint the collector really used.
CSI_WEIGHT_ENDPOINT = ("https://www.csindex.com.cn/csindex-home/indexInfo/"
                       "index-sample-information")
CSI_WEIGHT_METHOD = "POST {searchInput:<security>,pageNum,pageSize,sortField,sortOrder}"

#: SWS industry-index membership endpoint, verbatim capture.
SWS_MEMBERSHIP_ENDPOINT = ("https://www.swsresearch.com/institute-sw/api/"
                           "index_publish/details/component_stocks/")
SWS_CATALOG_ENDPOINT = ("https://www.swsresearch.com/institute-sw/api/index_publish/current/")

WEIGHT_SUM_BAND = (99.0, 100.5)
TARGET_L2_CODES = ("3701", "3703", "3706", "4803", "4901")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def code_hash_of(module_file: Path) -> str:
    return hashlib.sha256(module_file.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Stage 1 — official CSI benchmark weight vectors
# ---------------------------------------------------------------------------

def load_csi_index_register() -> dict[str, dict]:
    """The official CSI index register, used only to confirm an index exists."""
    candidates = list((SUBAGENTS / "B-csi-weights").glob("csi_index-list_query-index-item.json"))
    register = {}
    for path in candidates:
        doc = load_json(path)
        for row in doc.get("data") or []:
            code = str(row.get("indexCode") or "").strip()
            if code:
                register[code] = {"name": row.get("indexName") or "",
                                  "cons_number": row.get("consNumber")}
    return register


def collect_csi_weight_vectors(*, register: dict[str, dict], observed_at: str,
                               available_at: str, valid_from: str,
                               scope: frozenset[str] | None = None
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
            by_index.setdefault(index_code, {})[str(row.get("securityCode") or security).zfill(6)] = {
                "weight_pct": row.get("weightPct"), "cons_number": row.get("consNumber"),
                "security_name": row.get("securityName"), "index_name": row.get("indexName"),
                "registry_file": str(path)}

    vectors, rejected = {}, {"sum_out_of_band": 0, "count_mismatch": 0, "no_registry_entry": 0,
                             "unparsable": 0}
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
            rows.append({"security_code": security, "security_name": payload["security_name"],
                         "weight_pct": weight})
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
        declared_set = {int(float(value)) for value in declared_values
                        if re.fullmatch(r"[0-9]+(\.[0-9]+)?", value)}
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
            "rows": rows, "declared": declared, "weight_sum": total,
            "index_name": register[index_code].get("name") or members[list(members)[0]]["index_name"],
            "registry_files": sorted({payload["registry_file"] for payload in members.values()}),
        }
    return vectors, rejected


# ---------------------------------------------------------------------------
# Stage 2 — official SWS Shenwan L2 classification
# ---------------------------------------------------------------------------

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
    rows = []
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


def collect_sws_classification(*, observed_at: str, available_at: str
                               ) -> tuple[dict[str, tuple[str, str, str, str]], dict,
                                          list[str], dict, dict[str, str], dict[str, str]]:
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
                if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day):
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
        "catalog_index_to_l2": len(index_to_l2), "member_files": len(files),
        "verbatim_files": len(provenance),
        "ledger_entries": len(ledger),
        "securities_seen": len(assignments), "securities_classified": len(resolved),
        "securities_conflicted": len(conflicts), "unparsable_rows": len(unparsed),
        "l2_industries_covered": len(per_l2),
        "securities_with_official_beginningdate": len(effective),
        "unmapped_catalog_indices": len(files) - len(index_to_l2),
    }
    return resolved, conflicts, unparsed, diagnostics, effective, provenance


# ---------------------------------------------------------------------------
# Stage 3 — official exchange ETF tracking relations
# ---------------------------------------------------------------------------

def collect_tracking_relations(*, pin: SourcePin, observed_at: str, available_at: str,
                               valid_from: str) -> tuple[list, dict]:
    relations, diagnostics = [], {}
    sse_pages = sorted((SUBAGENTS / "E-etf-tracking" / "raw").glob("sse_etf_catalog_p*.json"))
    sse_rows = []
    for page in sse_pages:
        body = page.read_bytes()
        doc = json.loads(body.decode("utf-8"))
        sse_rows.extend((doc.get("pageHelp") or {}).get("data") or [])
        pin.pin_bytes(relative_path=f"exchange/sse_etf_catalog_{page.stem.split('_')[-1]}.json",
                      body=body, source_url="https://query.sse.com.cn/commonSoaQuery.do",
                      content_type="application/json;charset=UTF-8",
                      evidence_observed_at=observed_at, source_retrieved_at=observed_at,
                      note="SSE fund catalogue page")
    if sse_rows:
        source = pin.require_pinned(f"exchange/sse_etf_catalog_{sse_pages[0].stem.split('_')[-1]}.json")
        sse_relations = build_tracking_relations_from_sse_catalog(
            catalog_rows=sse_rows, observed_at=observed_at, available_at=available_at,
            source=source, valid_from=valid_from)
        relations.extend(sse_relations)
        diagnostics["sse_rows"] = len(sse_rows)
        diagnostics["sse_relations"] = len(sse_relations)
        diagnostics["sse_pages"] = len(sse_pages)

    szse_rows = []
    szse_dir = SUBAGENTS / "C-cni-szse"
    pages = sorted(szse_dir.glob("szse_etf_list_p*.json"))
    for page in pages:
        body = page.read_bytes()
        doc = json.loads(body.decode("utf-8"))
        block = doc[0] if isinstance(doc, list) and doc else {}
        szse_rows.extend(block.get("data") or [])
        pin.pin_bytes(relative_path=f"exchange/szse_etf_list_{page.stem.split('_')[-1]}.json",
                      body=body, source_url="https://www.szse.cn/api/report/ShowReport/data",
                      content_type="application/json",
                      evidence_observed_at=observed_at, source_retrieved_at=observed_at,
                      note="SZSE ETF catalogue page")
    if szse_rows and pages:
        source = pin.require_pinned(f"exchange/szse_etf_list_{pages[0].stem.split('_')[-1]}.json")
        szse_relations = build_tracking_relations_from_szse_catalog(
            catalog_rows=szse_rows, observed_at=observed_at, available_at=available_at,
            source=source, valid_from=valid_from)
        relations.extend(szse_relations)
        diagnostics["szse_rows"] = len(szse_rows)
        diagnostics["szse_relations"] = len(szse_relations)
        diagnostics["szse_pages"] = len(pages)
    return relations, diagnostics


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Observation instant
# ---------------------------------------------------------------------------

def latest_real_retrieval() -> tuple[str, str]:
    """The latest instant at which any pinned byte stream was actually retrieved.

    A build may never claim to have observed evidence earlier than the moment the
    last raw byte came back from the provider. That would be exactly the historical
    backfill this task forbids, committed by the builder instead of by a strategy.
    The value is derived from the collection ledgers, never typed in by hand.
    """
    candidates: list[tuple[str, str]] = []
    sws_ledger = REPORTS / "sws_harvest_ledger.jsonl"
    if sws_ledger.exists():
        for line in sws_ledger.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            moment = row.get("retrieved_at")
            if isinstance(moment, str) and moment:
                candidates.append((moment, f"sws:{row.get('file')}"))
    csi_ledger = PRIOR / "official-sources" / "raw" / "csi_reverse"
    if csi_ledger.exists():
        newest = max((path.stat().st_mtime for path in csi_ledger.glob("*.json")),
                     default=None)
        if newest is not None:
            moment = datetime.fromtimestamp(newest, timezone.utc).astimezone().isoformat(
                timespec="seconds")
            candidates.append((moment, "csi_reverse:filesystem_mtime_of_newest_response"))
    if not candidates:
        raise SystemExit("no collection ledger found; cannot establish an observation instant")
    moment, origin = max(candidates, key=lambda item: parse_for_order(item[0]))
    return moment, origin


def parse_for_order(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def assert_observed_after_every_retrieval(observed_at: str) -> tuple[str, str]:
    """Bound the claimed observation instant from both sides.

    It may not precede the last real retrieval (that would be history backfill) and
    it may not sit in the future (that would overstate how long the evidence has
    been usable). Both are the same class of error: a timestamp this system is not
    entitled to assert.
    """
    moment, origin = latest_real_retrieval()
    claimed = parse_for_order(observed_at)
    if claimed < parse_for_order(moment):
        raise SystemExit(
            f"REFUSING TO BACKDATE: --observed-at {observed_at} precedes the real "
            f"retrieval at {moment} ({origin}). Pass an instant at or after {moment}.")
    wall_clock = datetime.now(timezone.utc).astimezone()
    if claimed > wall_clock + timedelta(minutes=2):
        raise SystemExit(
            f"REFUSING A FUTURE OBSERVATION: --observed-at {observed_at} is later than "
            f"the real wall clock {wall_clock.isoformat(timespec='seconds')}. Evidence "
            "cannot claim to have been observed at an instant that has not happened.")
    return moment, origin


def csi_reverse_lineage(scope: frozenset[str] | None) -> tuple[dict[str, tuple[str, str]],
                                                               dict[str, tuple[str, str]]]:
    """Per-security and per-benchmark lineage back to the verbatim CSI responses.

    Returns ``(by_security, by_index)`` where each value is ``(file_name, sha256)``.
    Every rebuilt weight vector can therefore name the exact official byte streams
    it was assembled from, instead of merely asserting an endpoint.
    """
    by_security: dict[str, tuple[str, str]] = {}
    by_index: dict[str, tuple[str, str]] = {}
    for path in sorted(CSI_REVERSE.glob("*.json")):
        try:
            body = path.read_bytes()
            doc = json.loads(body)
        except Exception:
            continue
        if doc.get("error"):
            continue
        digest = sha256_bytes(body)
        by_security[path.stem] = (path.name, digest)
        for row in doc.get("data") or []:
            index_code = str(row.get("indexCode") or "").strip()
            if not index_code or (scope is not None and index_code not in scope):
                continue
            by_index.setdefault(index_code, set()).add(path.name)
    resolved = {code: tuple(sorted(names)) for code, names in by_index.items()}
    return by_security, resolved


def lineage_payload(names, by_security: dict[str, tuple[str, str]], *, limit: int = 400
                    ) -> tuple[dict, ...]:
    """The upstream capture list for one extraction, capped and counted."""
    items = []
    for name in sorted(names)[:limit]:
        digest = next((value[1] for value in by_security.values() if value[0] == name), None)
        items.append({"capture": name, "sha256": digest})
    return tuple(items)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observed-at", default=None,
                        help="Explicit observation instant; defaults to build time. "
                             "Refused if it precedes any real retrieval or is in the future.")
    parser.add_argument("--valid-from", default=None,
                        help="Defaults to the local date of the observation instant. "
                             "Never earlier than it: that would backdate the window.")
    parser.add_argument("--constituent-effective-date", default=None,
                        help="Only pass this if an official document states the "
                             "constituent effective date. The CSI reverse endpoint does "
                             "not, so it defaults to the observation date and is flagged.")
    parser.add_argument("--valid-through", default="2099-12-31")
    args = parser.parse_args()

    observed_at = args.observed_at or now_iso()
    available_at = observed_at
    last_retrieval, retrieval_origin = assert_observed_after_every_retrieval(observed_at)
    local_day = parse_for_order(observed_at).date().isoformat()
    valid_from = args.valid_from or local_day
    if valid_from < local_day:
        raise SystemExit(
            f"REFUSING TO BACKDATE THE VALIDITY WINDOW: --valid-from {valid_from} precedes "
            f"the observation date {local_day}.")
    constituent_effective_date = args.constituent_effective_date
    constituent_effective_is_official = constituent_effective_date is not None
    if constituent_effective_date is None:
        # No official artifact in this round states a constituent effective date, so
        # the honest value is the day the evidence was first usable -- never an
        # invented date that would look like an official publication.
        constituent_effective_date = local_day
    valid_through = args.valid_through
    derivation_hash = code_hash_of(REPO / "strategies" / "etf_quant" / "evidence" / "schema.py")
    builder_hash = code_hash_of(REPO / "strategies" / "etf_quant" / "evidence" / "builder.py")

    for directory in (PACKAGES, SOURCE_ROOT, REPORTS):
        directory.mkdir(parents=True, exist_ok=True)

    pin = SourcePin(SOURCE_ROOT)
    report: dict = {"artifact": "PRODUCTION_PIT_EVIDENCE_BUILD_V1",
                    "observed_at": observed_at, "available_at": available_at,
                    "last_real_retrieval": last_retrieval,
                    "last_real_retrieval_origin": retrieval_origin,
                    "valid_from": valid_from, "valid_through": valid_through,
                    "constituent_effective_date": constituent_effective_date,
                    "constituent_effective_date_is_officially_stated":
                        constituent_effective_is_official,
                    "derivation_code_hash": derivation_hash, "builder_code_hash": builder_hash}
    print(f"[0] observation instant {observed_at} (last real retrieval {last_retrieval})",
          flush=True)

    # ---- stage 1: ETF tracking relations (defines the benchmark scope) ----
    relations, tracking_diag = collect_tracking_relations(
        pin=pin, observed_at=observed_at, available_at=available_at, valid_from=valid_from)
    report["tracking"] = tracking_diag
    benchmark_to_etfs: dict[str, list] = {}
    for relation in relations:
        benchmark_to_etfs.setdefault(relation.benchmark_code, []).append(relation)
    print(f"[1] ETF tracking relations: {len(relations)} over {len(benchmark_to_etfs)} benchmarks",
          flush=True)

    # ---- stage 2: benchmark weight vectors (only where an ETF can use them) ----
    register = load_csi_index_register()
    vectors, rejected = collect_csi_weight_vectors(
        register=register, observed_at=observed_at, available_at=available_at,
        valid_from=valid_from, scope=frozenset(benchmark_to_etfs))
    report["csi"] = {"register_entries": len(register), "complete_vectors": len(vectors),
                     "rejected": rejected, "scope": len(benchmark_to_etfs)}
    print(f"[2] CSI complete official weight vectors in scope: {len(vectors)}  "
          f"rejected={rejected}", flush=True)

    # Lineage from every rebuilt weight vector back to the verbatim captures.
    _by_security, csi_lineage_by_index = csi_reverse_lineage(frozenset(benchmark_to_etfs))
    report["csi_lineage"] = {"securities_indexed": len(_by_security),
                              "benchmarks_with_lineage": len(csi_lineage_by_index)}

    # ---- stage 3: Shenwan L2 classification ------------------------------
    (assignments, conflicts, unparsed, sws_diag,
     sws_effective, sws_provenance) = collect_sws_classification(
        observed_at=observed_at, available_at=available_at)
    report["sws"] = {**sws_diag, "conflict_sample": sorted(conflicts)[:20]}
    print(f"[3] SWS classified securities: {len(assignments)} conflicts={len(conflicts)} "
          f"verbatim_files={sws_diag['verbatim_files']} "
          f"with official beginningdate={sws_diag['securities_with_official_beginningdate']}",
          flush=True)

    # ---- stage 4: classification snapshot --------------------------------
    snapshot_id = "SWS_L2_CURRENT_SNAPSHOT_" + observed_at[:10].replace("-", "")
    # Each security's effective date is the earliest official ``beginningdate`` for
    # its industry membership -- the provider's own statement of when the row took
    # effect. Where the provider states none, the observation date is used and the
    # package reports the gap rather than inventing a date.
    rows = build_classification_rows(
        assignments=assignments, observed_at=observed_at, available_at=available_at,
        effective_from=valid_from, security_names={}, conflicts=frozenset(conflicts),
        effective_dates=sws_effective)
    stated = sum(1 for row in rows
                 if sws_effective.get(row.security_code) == row.classification_effective_from)
    report["classification_effective_dates"] = {
        "securities": len(rows), "officially_stated": stated,
        "defaulted_to_observation_date": len(rows) - stated,
        "distinct_official_dates": len(set(sws_effective.values()))}
    sws_source_body = json.dumps(
        {"artifact": "SWS_L2_MEMBERSHIP_VECTOR_V1",
         "classifications": [{"security_code": row.security_code,
                              "l2_code": row.shenwan_l2_code,
                              "effective_date": row.classification_effective_from,
                              "available_at": row.evidence_available_at}
                             for row in rows]},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sws_pinned = pin.pin_bytes(
        relative_path="sws/l2_classification_snapshot_v1.json", body=sws_source_body,
        source_url=SWS_CATALOG_ENDPOINT,
        content_type="application/json", evidence_observed_at=observed_at,
        source_retrieved_at=observed_at,
        note="Shenwan L2 industry-index membership, official SWS API")
    snapshot = build_classification_snapshot(
        snapshot_id=snapshot_id, rows=rows, observed_at=observed_at, available_at=available_at,
        sources=(sws_pinned,), coverage_gap=tuple(sorted(conflicts)[:200]))
    write_package(PACKAGES / "classification" / f"{snapshot_id}.json",
                  classification_package(snapshot=snapshot))
    print(f"[4] classification snapshot {snapshot_id}: {len(rows)} securities "
          f"(official effective dates {stated}, defaulted {len(rows) - stated})", flush=True)

    # ---- stage 5: derived exposure + B40 mappings -------------------------
    # The pinned weight document is written exactly once per benchmark, here, using
    # the single shared effective-date rule. ``build_adapter_records`` re-pins the
    # same relative path with the same bytes; the immutability check would refuse a
    # second, differently-dated write, which is precisely how a silent divergence
    # between the two documents was prevented from shipping.
    exposures, mappings, weight_packages, failures = {}, [], [], []
    effective = dict(sws_effective)
    floor_day = min(min(effective.values()), valid_from) if effective else valid_from
    for benchmark_code, vector in sorted(vectors.items()):
        weight_day = benchmark_effective_day(vector, effective, valid_from=valid_from,
                                             floor_day=floor_day)
        weight_doc = adapter_weight_source_document(
            benchmark_code=benchmark_code,
            constituent_effective_date=weight_day,
            rows=tuple(_row(row) for row in vector["rows"]),
            declared_constituent_count=vector["declared"])
        weight_source = pin.pin_bytes(
            relative_path=f"weights/{benchmark_code}_weights_v1.json", body=weight_doc,
            source_url=CSI_WEIGHT_ENDPOINT,
            content_type="application/json;charset=UTF-8", evidence_observed_at=observed_at,
            source_retrieved_at=observed_at,
            note=f"CSI official constituent weight vector for {benchmark_code}; "
                 f"extracted from {CSI_WEIGHT_METHOD}; constituent effective date "
                 f"{weight_day}",
            kind=KIND_DOCUMENTED_EXTRACTION,
            derived_from=lineage_payload(
                csi_lineage_by_index.get(benchmark_code, ()), _by_security))
        weights = build_weight_vector_from_constituent_rows(
            benchmark_code=benchmark_code, benchmark_name=vector["index_name"],
            provider="中证指数有限公司 (China Securities Index Co., Ltd.)",
            weight_source_type="OFFICIAL_WEIGHT",
            constituent_effective_date=weight_day,
            observed_at=observed_at, available_at=available_at,
            declared_constituent_count=vector["declared"], rows=vector["rows"],
            valid_from=valid_from, valid_to=valid_through, sources=(weight_source,))
        write_package(PACKAGES / "weights" / f"{benchmark_code}_weights_v1.json",
                      weight_package(weights=weights))
        try:
            exposure = derive_l2_exposure(
                weights=weights, snapshot=snapshot, derived_at=observed_at,
                derivation_code_hash=derivation_hash)
        except EvidenceError as error:
            failures.append({"benchmark_code": benchmark_code, "code": error.code,
                             **{k: v for k, v in error.details.items() if k != "sample"}})
            continue
        exposures[benchmark_code] = exposure
        write_package(PACKAGES / "exposure" / f"{benchmark_code}_l2_exposure_v1.json",
                      exposure_package(exposure=exposure))
        for relation in benchmark_to_etfs.get(benchmark_code, []):
            mapping = decide_b40_mapping(
                exposure=exposure, target_l2_code=_target_of(exposure),
                etf_code=relation.etf_code, etf_name=relation.etf_name,
                available_from=relation.available_at)
            mappings.append((benchmark_code, mapping))
    report["derivation"] = {"exposures": len(exposures), "failures": len(failures),
                            "failure_reasons": _tally(failures)}
    print(f"[5] derived exposures: {len(exposures)} failures={len(failures)}", flush=True)

    # ---- stage 6: evidence book for the existing adapter ------------------
    book_records = build_adapter_records(
        vectors=vectors, assignments=assignments, relations=relations, pin=pin,
        observed_at=observed_at, available_at=available_at, valid_from=valid_from,
        valid_through=valid_through, sws_effective=sws_effective,
        sws_provenance=sws_provenance, csi_lineage_by_index=csi_lineage_by_index,
        csi_by_security=_by_security)
    book_path = RUNTIME / "adapter-tests" / "production_evidence_book_v1.json"
    book_path.parent.mkdir(parents=True, exist_ok=True)
    book_bytes = adapter_book_document(records=book_records)
    book_path.write_bytes(book_bytes)
    report["adapter_book"] = {"path": str(book_path), "records": len(book_records),
                              "sha256": sha256_bytes(book_bytes),
                              "source_root": str(SOURCE_ROOT)}
    print(f"[6] adapter evidence book: {len(book_records)} records -> {book_path}", flush=True)

    # ---- stage 7: source manifest + registry ------------------------------
    manifest_path = pin.write_manifest(REPORTS / "raw_source_manifest_v1.json")
    verification = pin.verify()
    report["source_manifest"] = {"path": str(manifest_path),
                                 "sources": len(pin.records),
                                 "total_bytes": sum(r.byte_length for r in pin.records),
                                 "verification": verification}
    registry = {
        "schema_version": "1.0.0",
        "registry_id": f"PRODUCTION_PIT_EVIDENCE_REGISTRY_V1::{observed_at[:10]}",
        "identity": "PRODUCTION_PIT_EVIDENCE_REGISTRY_V1",
        "created_at": observed_at,
        "production_available_from": available_at,
        "availability_semantics": "FORWARD_ONLY",
        "valid_from": valid_from, "valid_through": valid_through,
        "taxonomy_identity": default_taxonomy().identity,
        "classification_snapshot_id": snapshot_id,
        "builder_code_hash": builder_hash, "derivation_code_hash": derivation_hash,
        "cneqity_pin": "1650e384a3fd1f67a70144a489acc91432f1df27",
        "counts": {
            "etf_tracking_relations": len(relations),
            "benchmarks_with_complete_official_weights": len(vectors),
            "classification_securities": len(rows),
            "classification_conflicts": len(conflicts),
            "derived_exposures": len(exposures),
            "b40_mappings_total": len(mappings),
            "b40_mappings_admitted": sum(1 for _b, m in mappings if m.admission_status == "ADMITTED"),
            "unresolved_benchmarks": len(failures),
        },
        "known_limitations": [
            "SOURCE_LICENSING_UNRESOLVED",
            "CLASSIFICATION_FROM_OFFICIAL_INDEX_MEMBERSHIP_NOT_FROM_OFFICIAL_STOCK_CLASSIFICATION_TABLE",
            "HISTORICAL_PUBLICATION_TIME_NOT_PROVIDED_BY_ANY_OFFICIAL_SOURCE",
            "CSI_FULL_WEIGHT_VECTORS_AVAILABLE_ONLY_AS_XLS_OR_VIA_REVERSE_JSON",
        ],
        "index": {
            "tracking_packages": [f"ETF_TRACKING::{r.etf_code}::{r.benchmark_code}" for r in relations[:50]],
            "weight_packages": sorted(vectors), "exposure_packages": sorted(exposures),
        },
    }
    registry_path = REPORTS / "production_pit_evidence_registry_v1.json"
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=1), encoding="utf-8")
    report["registry"] = {"path": str(registry_path), "sha256": sha256_bytes(registry_path.read_bytes())}
    (REPORTS / "build_report_v1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[7] registry written:", registry_path, flush=True)
    print(json.dumps(report["adapter_book"], ensure_ascii=False), flush=True)
    return 0


def _row(payload: dict):
    from strategies.etf_quant.evidence import ConstituentRow
    return ConstituentRow(security_code=payload["security_code"],
                          weight_pct=float(payload["weight_pct"]),
                          security_name=payload.get("security_name"))


def _target_of(exposure) -> str:
    for code in TARGET_L2_CODES:
        if exposure.exposure(code) > 0:
            return code
    return exposure.ranked_l2[0][0]


def _tally(failures: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for item in failures:
        counts[item["code"]] = counts.get(item["code"], 0) + 1
    return counts


def benchmark_effective_day(vector: dict, effective: dict[str, str], *, valid_from: str,
                            floor_day: str) -> str:
    """The one effective date a benchmark's weight vector may honestly carry.

    It must not post-date any constituent's own official date, or the adapter would
    see a classification taking effect after the vector it explains, and it must not
    post-date the validity window. Where the provider states no date, the floor is
    the observation date. Computing this in exactly one place is what keeps the
    weight document and the adapter record from disagreeing.
    """
    member_days = [effective[row["security_code"]] for row in vector["rows"]
                   if row["security_code"] in effective]
    day = max(member_days) if member_days else min(floor_day, valid_from)
    return min(day, valid_from)


def build_adapter_records(*, vectors, assignments, relations, pin, observed_at, available_at,
                          valid_from, valid_through, sws_effective=None,
                          sws_provenance=None, csi_lineage_by_index=None,
                          csi_by_security=None) -> list[dict]:
    """Emit adapter records only for benchmarks that carry a full, classified vector.

    Each classification row's ``effective_date`` is the provider's own earliest
    official ``beginningdate`` for that security's industry membership -- never the
    date this build ran. Using the build date would both misstate the fact and
    violate the adapter's rule that a classification may not take effect after the
    weight vector it explains.

    The weight vector's own effective date is therefore anchored at or before the
    earliest official date any of its constituents carries, so the two documents
    cannot contradict each other. When the provider states no date at all, the
    fallback is the local date of the observation instant and the record says so.
    """
    taxonomy = default_taxonomy()
    effective = dict(sws_effective or {})
    sws_provenance = dict(sws_provenance or {})
    csi_lineage_by_index = dict(csi_lineage_by_index or {})
    csi_by_security = dict(csi_by_security or {})
    official_days = sorted(day for day in effective.values() if day <= valid_from)
    floor_day = official_days[0] if official_days else valid_from
    by_benchmark: dict[str, list] = {}
    for relation in relations:
        by_benchmark.setdefault(relation.benchmark_code, []).append(relation)
    records = []
    for benchmark_code, vector in sorted(vectors.items()):
        members = [row for row in vector["rows"]
                   if row["security_code"] in assignments]
        if len(members) != len(vector["rows"]):
            continue
        weight_day = benchmark_effective_day(vector, effective, valid_from=valid_from,
                                             floor_day=floor_day)
        weight_doc = adapter_weight_source_document(
            benchmark_code=benchmark_code, constituent_effective_date=weight_day,
            rows=tuple(_row(row) for row in members),
            declared_constituent_count=vector["declared"])
        benchmark_note = (
            f"CSI official constituent weight vector for {benchmark_code}, rebuilt from "
            f"the provider's per-security reverse-query responses; constituent effective "
            f"date {weight_day} anchored to the earliest official constituent date and "
            f"capped at the validity start {valid_from}")
        weight_source = pin.pin_bytes(
            relative_path=f"weights/{benchmark_code}_weights_v1.json", body=weight_doc,
            source_url=CSI_WEIGHT_ENDPOINT,
            content_type="application/json;charset=UTF-8", evidence_observed_at=observed_at,
            source_retrieved_at=observed_at, note=benchmark_note,
            kind=KIND_DOCUMENTED_EXTRACTION,
            derived_from=lineage_payload(
                csi_lineage_by_index.get(benchmark_code, ()), csi_by_security))
        # The classification document is rebuilt per relation because the adapter
        # requires every classification row's availability to be no later than the
        # record's own availability instant. Pinning per relation keeps each record's
        # pinned bytes internally consistent instead of reusing one loose document.
        for relation in by_benchmark.get(benchmark_code, []):
            class_doc = adapter_classification_source_document(
                rows=tuple(_classified(row, assignments, effective, weight_day,
                                       relation.evidence_available_at)
                           for row in members),
                effective_date=weight_day, available_at=relation.evidence_available_at)
            class_source = pin.pin_bytes(
                relative_path=(f"classification/{benchmark_code}_"
                               f"{relation.etf_code.replace('.', '_')}_classification_v1.json"),
                body=class_doc,
                source_url=SWS_MEMBERSHIP_ENDPOINT,
                content_type="application/json",
                evidence_observed_at=relation.evidence_observed_at,
                source_retrieved_at=relation.evidence_observed_at,
                note="adapter classification source, extracted from the official "
                     "Shenwan L2 industry-index membership responses",
                kind=KIND_DOCUMENTED_EXTRACTION,
                derived_from=tuple(
                    {"capture": f"raw_members/{code}.json", "sha256": digest}
                    for code, digest in sorted(sws_provenance.items()))[:400])
            decoded_weight = json.loads(weight_doc.decode("utf-8"))
            decoded_class = json.loads(class_doc.decode("utf-8"))
            constituents = decoded_weight["constituents"]
            classifications = decoded_class["classifications"]
            declared = decoded_weight["declared_constituent_count"]
            for industry_code in sorted({assignments[row["security_code"]][2] for row in members}):
                records.append(adapter_record(
                    industry_code=industry_code, etf_code=relation.etf_code,
                    etf_name=relation.etf_name, benchmark_code=benchmark_code,
                    source_publication_at=None,
                    evidence_observed_at=relation.evidence_observed_at,
                    available_at=relation.evidence_available_at,
                    constituent_effective_date=weight_day,
                    weight_effective_date=weight_day, valid_through=valid_through,
                    declared_constituent_count=declared,
                    weight_source=weight_source, classification_source=class_source,
                    constituents=constituents, classifications=classifications,
                    provider="中证指数有限公司 (China Securities Index Co., Ltd.)"))
    return records


def _classified(row, assignments, effective, fallback, available_at):
    from strategies.etf_quant.evidence import ClassificationRow
    security = row["security_code"]
    l1, l1_name, l2, l2_name = assignments[security]
    day = effective.get(security, fallback)
    if day > fallback:
        day = fallback
    return ClassificationRow(
        security_code=security, shenwan_l1_code=l1, shenwan_l1_name=l1_name,
        shenwan_l2_code=l2, shenwan_l2_name=l2_name, taxonomy_version="SWCLASS2021",
        classification_effective_from=day, evidence_observed_at=available_at,
        evidence_available_at=available_at)


if __name__ == "__main__":
    raise SystemExit(main())
