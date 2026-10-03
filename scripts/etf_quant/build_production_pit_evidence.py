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
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.etf_quant.production_pit_adapter import (  # noqa: E402 -- Standalone CLI must first resolve its checkout.
    _classified as _classified,
)
from scripts.etf_quant.production_pit_adapter import (  # noqa: E402 -- Standalone CLI must first resolve its checkout.
    _row,
    _tally,
    _target_of,
    benchmark_effective_day,
    build_adapter_records,
)
from scripts.etf_quant.production_pit_collectors import (  # noqa: E402 -- Standalone CLI must first resolve its checkout.
    code_hash_of,
    collect_csi_weight_vectors,
    collect_sws_classification,
    collect_tracking_relations,
    load_csi_index_register,
    now_iso,
)
from scripts.etf_quant.production_pit_collectors import (  # noqa: E402 -- Standalone CLI must first resolve its checkout.
    load_json as load_json,
)
from scripts.etf_quant.production_pit_collectors import (  # noqa: E402 -- Standalone CLI must first resolve its checkout.
    sws_catalog_name_map as sws_catalog_name_map,
)
from scripts.etf_quant.production_pit_lineage import (  # noqa: E402 -- Standalone CLI must first resolve its checkout.
    assert_observed_after_every_retrieval,
    csi_reverse_lineage,
    lineage_payload,
    parse_for_order,
)
from scripts.etf_quant.production_pit_lineage import (  # noqa: E402 -- Standalone CLI must first resolve its checkout.
    latest_real_retrieval as latest_real_retrieval,
)

# Explicit external roots support other machines; existing deployment defaults
# remain compatible. This builder is not part of the portable demo/test flow.
from scripts.etf_quant.production_pit_settings import (  # noqa: E402 -- Standalone CLI must first resolve its checkout.
    CSI_WEIGHT_ENDPOINT,
    CSI_WEIGHT_METHOD,
    PACKAGES,
    REPORTS,
    RUNTIME,
    SOURCE_ROOT,
    SWS_CATALOG_ENDPOINT,
)
from strategies.etf_quant.domain.industry_level import default_taxonomy  # noqa: E402
from strategies.etf_quant.evidence import (  # noqa: E402
    KIND_DOCUMENTED_EXTRACTION,
    EvidenceError,
    SourcePin,
    adapter_book_document,
    adapter_weight_source_document,
    build_classification_rows,
    build_classification_snapshot,
    build_weight_vector_from_constituent_rows,
    classification_package,
    decide_b40_mapping,
    derive_l2_exposure,
    exposure_package,
    sha256_bytes,
    weight_package,
    write_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--observed-at",
        default=None,
        help="Explicit observation instant; defaults to build time. "
        "Refused if it precedes any real retrieval or is in the future.",
    )
    parser.add_argument(
        "--valid-from",
        default=None,
        help="Defaults to the local date of the observation instant. "
        "Never earlier than it: that would backdate the window.",
    )
    parser.add_argument(
        "--constituent-effective-date",
        default=None,
        help="Only pass this if an official document states the "
        "constituent effective date. The CSI reverse endpoint does "
        "not, so it defaults to the observation date and is flagged.",
    )
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
            f"the observation date {local_day}."
        )
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
    report: dict = {
        "artifact": "PRODUCTION_PIT_EVIDENCE_BUILD_V1",
        "observed_at": observed_at,
        "available_at": available_at,
        "last_real_retrieval": last_retrieval,
        "last_real_retrieval_origin": retrieval_origin,
        "valid_from": valid_from,
        "valid_through": valid_through,
        "constituent_effective_date": constituent_effective_date,
        "constituent_effective_date_is_officially_stated": constituent_effective_is_official,
        "derivation_code_hash": derivation_hash,
        "builder_code_hash": builder_hash,
    }
    print(
        f"[0] observation instant {observed_at} (last real retrieval {last_retrieval})", flush=True
    )

    # ---- stage 1: ETF tracking relations (defines the benchmark scope) ----
    relations, tracking_diag = collect_tracking_relations(
        pin=pin, observed_at=observed_at, available_at=available_at, valid_from=valid_from
    )
    report["tracking"] = tracking_diag
    benchmark_to_etfs: dict[str, list] = {}
    for relation in relations:
        benchmark_to_etfs.setdefault(relation.benchmark_code, []).append(relation)
    print(
        f"[1] ETF tracking relations: {len(relations)} over {len(benchmark_to_etfs)} benchmarks",
        flush=True,
    )

    # ---- stage 2: benchmark weight vectors (only where an ETF can use them) ----
    register = load_csi_index_register()
    vectors, rejected = collect_csi_weight_vectors(
        register=register,
        observed_at=observed_at,
        available_at=available_at,
        valid_from=valid_from,
        scope=frozenset(benchmark_to_etfs),
    )
    report["csi"] = {
        "register_entries": len(register),
        "complete_vectors": len(vectors),
        "rejected": rejected,
        "scope": len(benchmark_to_etfs),
    }
    print(
        f"[2] CSI complete official weight vectors in scope: {len(vectors)}  rejected={rejected}",
        flush=True,
    )

    # Lineage from every rebuilt weight vector back to the verbatim captures.
    _by_security, csi_lineage_by_index = csi_reverse_lineage(frozenset(benchmark_to_etfs))
    report["csi_lineage"] = {
        "securities_indexed": len(_by_security),
        "benchmarks_with_lineage": len(csi_lineage_by_index),
    }

    # ---- stage 3: Shenwan L2 classification ------------------------------
    (assignments, conflicts, unparsed, sws_diag, sws_effective, sws_provenance) = (
        collect_sws_classification(observed_at=observed_at, available_at=available_at)
    )
    report["sws"] = {**sws_diag, "conflict_sample": sorted(conflicts)[:20]}
    print(
        f"[3] SWS classified securities: {len(assignments)} conflicts={len(conflicts)} "
        f"verbatim_files={sws_diag['verbatim_files']} "
        f"with official beginningdate={sws_diag['securities_with_official_beginningdate']}",
        flush=True,
    )

    # ---- stage 4: classification snapshot --------------------------------
    snapshot_id = "SWS_L2_CURRENT_SNAPSHOT_" + observed_at[:10].replace("-", "")
    # Each security's effective date is the earliest official ``beginningdate`` for
    # its industry membership -- the provider's own statement of when the row took
    # effect. Where the provider states none, the observation date is used and the
    # package reports the gap rather than inventing a date.
    rows = build_classification_rows(
        assignments=assignments,
        observed_at=observed_at,
        available_at=available_at,
        effective_from=valid_from,
        security_names={},
        conflicts=frozenset(conflicts),
        effective_dates=sws_effective,
    )
    stated = sum(
        1
        for row in rows
        if sws_effective.get(row.security_code) == row.classification_effective_from
    )
    report["classification_effective_dates"] = {
        "securities": len(rows),
        "officially_stated": stated,
        "defaulted_to_observation_date": len(rows) - stated,
        "distinct_official_dates": len(set(sws_effective.values())),
    }
    sws_source_body = json.dumps(
        {
            "artifact": "SWS_L2_MEMBERSHIP_VECTOR_V1",
            "classifications": [
                {
                    "security_code": row.security_code,
                    "l2_code": row.shenwan_l2_code,
                    "effective_date": row.classification_effective_from,
                    "available_at": row.evidence_available_at,
                }
                for row in rows
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    sws_pinned = pin.pin_bytes(
        relative_path="sws/l2_classification_snapshot_v1.json",
        body=sws_source_body,
        source_url=SWS_CATALOG_ENDPOINT,
        content_type="application/json",
        evidence_observed_at=observed_at,
        source_retrieved_at=observed_at,
        note="Shenwan L2 industry-index membership, official SWS API",
    )
    snapshot = build_classification_snapshot(
        snapshot_id=snapshot_id,
        rows=rows,
        observed_at=observed_at,
        available_at=available_at,
        sources=(sws_pinned,),
        coverage_gap=tuple(sorted(conflicts)[:200]),
    )
    write_package(
        PACKAGES / "classification" / f"{snapshot_id}.json",
        classification_package(snapshot=snapshot),
    )
    print(
        f"[4] classification snapshot {snapshot_id}: {len(rows)} securities "
        f"(official effective dates {stated}, defaulted {len(rows) - stated})",
        flush=True,
    )

    # ---- stage 5: derived exposure + B40 mappings -------------------------
    # The pinned weight document is written exactly once per benchmark, here, using
    # the single shared effective-date rule. ``build_adapter_records`` re-pins the
    # same relative path with the same bytes; the immutability check would refuse a
    # second, differently-dated write, which is precisely how a silent divergence
    # between the two documents was prevented from shipping.
    exposures, mappings, failures = {}, [], []
    effective = dict(sws_effective)
    floor_day = min(min(effective.values()), valid_from) if effective else valid_from
    for benchmark_code, vector in sorted(vectors.items()):
        weight_day = benchmark_effective_day(
            vector, effective, valid_from=valid_from, floor_day=floor_day
        )
        weight_doc = adapter_weight_source_document(
            benchmark_code=benchmark_code,
            constituent_effective_date=weight_day,
            rows=tuple(_row(row) for row in vector["rows"]),
            declared_constituent_count=vector["declared"],
        )
        weight_source = pin.pin_bytes(
            relative_path=f"weights/{benchmark_code}_weights_v1.json",
            body=weight_doc,
            source_url=CSI_WEIGHT_ENDPOINT,
            content_type="application/json;charset=UTF-8",
            evidence_observed_at=observed_at,
            source_retrieved_at=observed_at,
            note=f"CSI official constituent weight vector for {benchmark_code}; "
            f"extracted from {CSI_WEIGHT_METHOD}; constituent effective date "
            f"{weight_day}",
            kind=KIND_DOCUMENTED_EXTRACTION,
            derived_from=lineage_payload(
                csi_lineage_by_index.get(benchmark_code, ()), _by_security
            ),
        )
        weights = build_weight_vector_from_constituent_rows(
            benchmark_code=benchmark_code,
            benchmark_name=vector["index_name"],
            provider="中证指数有限公司 (China Securities Index Co., Ltd.)",
            weight_source_type="OFFICIAL_WEIGHT",
            constituent_effective_date=weight_day,
            observed_at=observed_at,
            available_at=available_at,
            declared_constituent_count=vector["declared"],
            rows=vector["rows"],
            valid_from=valid_from,
            valid_to=valid_through,
            sources=(weight_source,),
        )
        write_package(
            PACKAGES / "weights" / f"{benchmark_code}_weights_v1.json",
            weight_package(weights=weights),
        )
        try:
            exposure = derive_l2_exposure(
                weights=weights,
                snapshot=snapshot,
                derived_at=observed_at,
                derivation_code_hash=derivation_hash,
            )
        except EvidenceError as error:
            failures.append(
                {
                    "benchmark_code": benchmark_code,
                    "code": error.code,
                    **{k: v for k, v in error.details.items() if k != "sample"},
                }
            )
            continue
        exposures[benchmark_code] = exposure
        write_package(
            PACKAGES / "exposure" / f"{benchmark_code}_l2_exposure_v1.json",
            exposure_package(exposure=exposure),
        )
        for relation in benchmark_to_etfs.get(benchmark_code, []):
            mapping = decide_b40_mapping(
                exposure=exposure,
                target_l2_code=_target_of(exposure),
                etf_code=relation.etf_code,
                etf_name=relation.etf_name,
                available_from=relation.available_at,
            )
            mappings.append((benchmark_code, mapping))
    report["derivation"] = {
        "exposures": len(exposures),
        "failures": len(failures),
        "failure_reasons": _tally(failures),
    }
    print(f"[5] derived exposures: {len(exposures)} failures={len(failures)}", flush=True)

    # ---- stage 6: evidence book for the existing adapter ------------------
    book_records = build_adapter_records(
        vectors=vectors,
        assignments=assignments,
        relations=relations,
        pin=pin,
        observed_at=observed_at,
        available_at=available_at,
        valid_from=valid_from,
        valid_through=valid_through,
        sws_effective=sws_effective,
        sws_provenance=sws_provenance,
        csi_lineage_by_index=csi_lineage_by_index,
        csi_by_security=_by_security,
    )
    book_path = RUNTIME / "adapter-tests" / "production_evidence_book_v1.json"
    book_path.parent.mkdir(parents=True, exist_ok=True)
    book_bytes = adapter_book_document(records=book_records)
    book_path.write_bytes(book_bytes)
    report["adapter_book"] = {
        "path": str(book_path),
        "records": len(book_records),
        "sha256": sha256_bytes(book_bytes),
        "source_root": str(SOURCE_ROOT),
    }
    print(f"[6] adapter evidence book: {len(book_records)} records -> {book_path}", flush=True)

    # ---- stage 7: source manifest + registry ------------------------------
    manifest_path = pin.write_manifest(REPORTS / "raw_source_manifest_v1.json")
    verification = pin.verify()
    report["source_manifest"] = {
        "path": str(manifest_path),
        "sources": len(pin.records),
        "total_bytes": sum(r.byte_length for r in pin.records),
        "verification": verification,
    }
    registry = {
        "schema_version": "1.0.0",
        "registry_id": f"PRODUCTION_PIT_EVIDENCE_REGISTRY_V1::{observed_at[:10]}",
        "identity": "PRODUCTION_PIT_EVIDENCE_REGISTRY_V1",
        "created_at": observed_at,
        "production_available_from": available_at,
        "availability_semantics": "FORWARD_ONLY",
        "valid_from": valid_from,
        "valid_through": valid_through,
        "taxonomy_identity": default_taxonomy().identity,
        "classification_snapshot_id": snapshot_id,
        "builder_code_hash": builder_hash,
        "derivation_code_hash": derivation_hash,
        "cneqity_pin": "1650e384a3fd1f67a70144a489acc91432f1df27",
        "counts": {
            "etf_tracking_relations": len(relations),
            "benchmarks_with_complete_official_weights": len(vectors),
            "classification_securities": len(rows),
            "classification_conflicts": len(conflicts),
            "derived_exposures": len(exposures),
            "b40_mappings_total": len(mappings),
            "b40_mappings_admitted": sum(
                1 for _b, m in mappings if m.admission_status == "ADMITTED"
            ),
            "unresolved_benchmarks": len(failures),
        },
        "known_limitations": [
            "SOURCE_LICENSING_UNRESOLVED",
            "CLASSIFICATION_FROM_OFFICIAL_INDEX_MEMBERSHIP_NOT_FROM_OFFICIAL_STOCK_CLASSIFICATION_TABLE",
            "HISTORICAL_PUBLICATION_TIME_NOT_PROVIDED_BY_ANY_OFFICIAL_SOURCE",
            "CSI_FULL_WEIGHT_VECTORS_AVAILABLE_ONLY_AS_XLS_OR_VIA_REVERSE_JSON",
        ],
        "index": {
            "tracking_packages": [
                f"ETF_TRACKING::{r.etf_code}::{r.benchmark_code}" for r in relations[:50]
            ],
            "weight_packages": sorted(vectors),
            "exposure_packages": sorted(exposures),
        },
    }
    registry_path = REPORTS / "production_pit_evidence_registry_v1.json"
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=1), encoding="utf-8")
    report["registry"] = {
        "path": str(registry_path),
        "sha256": sha256_bytes(registry_path.read_bytes()),
    }
    (REPORTS / "build_report_v1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print("[7] registry written:", registry_path, flush=True)
    print(json.dumps(report["adapter_book"], ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
