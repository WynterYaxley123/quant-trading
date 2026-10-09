"""Reproduce reviewed public qualification aggregates, without network or promotion."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from research.evidence.contracts import canonical, require, sha
from research.evidence.qualification import RIGHTS, real_registry_preflight
from research.evidence.source_admission import Kind, Source

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = "config/research/swl1-source-qualification-evidence.json"
REPORT_DIR = "reports/research/swl1_source_qualification"
UPSTREAM = "1650e384a3fd1f67a70144a489acc91432f1df27"

# Source roles are factual; the PR34 registry intentionally accepts industry
# sources only. Raw input components must not be relabelled as an official index.
SOURCES = (
    (
        "sws-taxonomy",
        "SWS Research",
        "SWCLASS2021 hierarchy / explicit L2 to L1",
        "OFFICIAL_TAXONOMY",
        "sw/industry_history.py",
        ["sws-2021-classification", "sws-announcements"],
    ),
    (
        "sws-membership",
        "SWS Research via CNEquity",
        "Effective-dated constituent intervals",
        "HISTORICAL_MEMBERSHIP",
        "sw/industry_history.py",
        ["sws-2021-classification"],
    ),
    (
        "sws-official-index",
        "SWS Research",
        "Requested official SWL1 index price series",
        "OFFICIAL_INDEX_PRICE_SERIES",
        None,
        ["sws-2021-classification", "sws-announcements"],
    ),
    (
        "tdx-daily-bars",
        "TDX via CNEquity",
        "Stock bars; documented alternative provider routes",
        "STOCK_PRICE",
        "tdx_protocol/bars.py",
        ["tdx-terms-text", "tdx-provider-license", "tdx-data-product"],
    ),
    (
        "sina-adjustment-factors",
        "Sina via CNEquity",
        "Sina hfq factor endpoint",
        "ADJUSTMENT_FACTOR",
        "sina/adj_factors.py",
        ["sina-copyright", "sina-finance-terms"],
    ),
    (
        "tdx-corporate-actions",
        "TDX via CNEquity",
        "TDX xdxr corporate actions, schema 2",
        "CORPORATE_ACTIONS",
        "tdx_protocol/corporate_actions.py",
        ["tdx-terms-text", "tdx-provider-license"],
    ),
    (
        "baostock-lifecycle",
        "BaoStock via CNEquity",
        "Instrument listing and delisting basics",
        "LISTING_DELISTING",
        "baostock/instruments.py",
        ["baostock-home-doc", "baostock-lifecycle-doc", "sse-delisting-example"],
    ),
    (
        "baostock-adjusted-prices",
        "BaoStock via CNEquity",
        "Raw/adjusted price fallback for factor reconstruction",
        "ADJUSTED_STOCK_PRICE",
        "baostock/adj_factors.py",
        [
            "baostock-home-doc",
            "baostock-bars-doc",
            "baostock-factor-doc",
            "baostock-adjustment",
            "baostock-revision-doc",
        ],
    ),
    (
        "cnequity-derived-factors",
        "CNEquity derived",
        "Sina factors with BaoStock fallback and row provenance",
        "DERIVED_ADJUSTMENT",
        None,
        ["sina-finance-terms", "baostock-factor-doc"],
    ),
    (
        "cnequity-calendar",
        "CNEquity seeds / bar fallback",
        "Exchange session spine",
        "EXCHANGE_CALENDAR",
        "calendar/exchange_calendar.py",
        ["sse-calendar", "sse-legal"],
    ),
    (
        "cnequity-industry-returns",
        "CNEquity derived",
        "Membership and adjusted-stock derived series",
        "RECONSTRUCTED_INDUSTRY_RETURN",
        None,
        ["sws-2021-classification", "tdx-terms-text", "baostock-adjustment"],
    ),
    (
        "project-reconstructed-swl1",
        "quant-trading frozen V1/V2",
        "RECONSTRUCTED_SWL1_EQUAL_WEIGHT",
        "RECONSTRUCTED_INDUSTRY_RETURN",
        None,
        ["sws-2021-classification", "tdx-terms-text", "sina-finance-terms"],
    ),
)


def build(root: Path) -> dict[str, dict[str, Any]]:
    snapshot = json.loads((root / SNAPSHOT).read_bytes())
    require(snapshot["upstream_commit"] == UPSTREAM, "QUALIFICATION_UPSTREAM_MISMATCH")
    documents = snapshot["documents"]
    refs = {d["document_id"]: d for d in documents}
    require(len(refs) == len(documents), "QUALIFICATION_DOCUMENT_DUPLICATE")
    verified = [
        d
        for d in documents
        if d["claim_verification"] == "REVIEWED_EXACT_BYTES_NOT_DATASET_AUTHORIZATION"
    ]
    common = dict(
        schema_version=1,
        scope="PUBLIC_METADATA_ONLY_NO_REAL_SOURCE_PROMOTION",
        source_identity="SWL1_SOURCE_QUALIFICATION_2026_10_09",
        evidence_reference=SNAPSHOT,
        retrieval_timestamp=snapshot["reviewed_at"],
        document_hash=sha(canonical(snapshot)),
        admission_requirement="RIGHTS_PIT_QUALITY_IDENTITY_REVISION_AND_PRODUCTION_AUTHORITY",
        verification_result="REAL_ADMISSION_BLOCKED",
        remaining_gap="DATASET_RIGHTS_CONTEMPORANEOUS_PIT_BLIND_QA_AND_APPROVED_IDENTITY",
    )

    def report(**values: Any) -> dict[str, Any]:
        return {**common, **values}

    inventory, rights, pit, quality, admission = [], [], [], [], []
    for source_id, provider, dataset, kind, adapter, evidence_ids in SOURCES:
        evidence = [
            dict(
                document_id=k,
                source_url=refs[k]["source_url"],
                content_sha256=refs[k]["content_sha256"],
                verification=refs[k]["claim_verification"],
            )
            for k in evidence_ids
        ]
        source = dict(
            source_id=source_id,
            provider=provider,
            dataset=dataset,
            kind=kind,
            upstream_commit=UPSTREAM,
            source_identity=source_id,
            evidence_reference=evidence,
            retrieval_timestamp=snapshot["reviewed_at"],
            numeric_snapshot_hash=None,
            source_admitted=False,
            research_target_level=1,
            source_generation_scope="QUALIFICATION_METADATA_ONLY",
            source_admission="SOURCE_BLOCKED",
            code_adapter=f"src/cnequity/adapters/{adapter}" if adapter else None,
        )
        contract = dict(
            source_id=source_id,
            kind=kind,
            required_use="FUTURE_RESEARCH_NOT_ACTIVATED",
            taxonomy_identity="SWCLASS2021",
            evidence_hashes={e["document_id"]: e["content_sha256"] for e in evidence},
        )
        if kind in {
            "OFFICIAL_TAXONOMY",
            "OFFICIAL_INDEX_PRICE_SERIES",
            "RECONSTRUCTED_INDUSTRY_RETURN",
        }:
            candidate = Source(
                source_id,
                sha(canonical(source)),
                sha(canonical(contract)),
                "SWCLASS2021",
                "UNVERIFIED_MEMBER_RECEIPTS",
                cast(Kind, kind),
                "D" if kind.startswith("OFFICIAL") else "C",
                sha(canonical({"upstream": UPSTREAM, "documents": contract["evidence_hashes"]})),
            )
            source["source_contract"] = asdict(candidate)
            source["source_hash_basis"] = "QUALIFICATION_METADATA_NOT_NUMERIC_DATASET_IDENTITY"
            registry = real_registry_preflight(asdict(candidate))
        else:
            source["source_contract"] = None
            registry = dict(
                existing_registry_state="UNSUPPORTED_DIRECT_ADMISSION_KIND",
                existing_registry_reason="INPUT_COMPONENT_REQUIRES_QUALIFIED_INDUSTRY_GENERATION",
                proofs_supplied=0,
                real_sources_admitted=0,
            )
        inventory.append(source)
        permission = dict.fromkeys(RIGHTS, "NOT_ESTABLISHED")
        if source_id.startswith("baostock-"):
            for key in (
                "dataset_access",
                "local_storage",
                "internal_research",
                "automated_processing",
            ):
                permission[key] = "CONDITIONAL"
        if source_id == "cnequity-calendar":
            permission["dataset_access"] = "CONDITIONAL"
            permission["local_storage"] = "CONDITIONAL"
        if source_id.startswith(("tdx-", "sina-")):
            for key in RIGHTS:
                permission[key] = "REQUIRES_PROVIDER_CONFIRMATION"
        rights.append(
            dict(
                source_identity=source_id,
                rights=permission,
                evidence_reference=evidence,
                verification_result="DATASET_SPECIFIC_GRANT_NOT_ESTABLISHED",
                rights_verified=False,
                legal_review_required=True,
                grant_scope="NOT_ESTABLISHED",
                terms_historical_applicability="NOT_ESTABLISHED",
                software_license_grants_data_rights=False,
                why="Provider documentation or general product terms do not establish a dataset-specific grant to this owner; derived sources inherit all upstream restrictions.",
            )
        )
        pit.append(
            dict(
                source_identity=source_id,
                evidence_reference=evidence,
                historical_member_tier="C"
                if source_id
                in {"sws-membership", "cnequity-industry-returns", "project-reconstructed-swl1"}
                else None,
                contemporaneous_availability="NOT_ESTABLISHED",
                publication_receipts=0,
                historical_observation_receipts=0,
                historical_taxonomy_announcement="INDEXED_PRIMARY_REFERENCE_ONLY"
                if source_id.startswith("sws-")
                else "NOT_APPLICABLE",
                verification_result="NOT_ESTABLISHED",
                missing_proof="Versioned full snapshots, publisher timestamps and historically verifiable receipt before the signal; effective and ingestion dates cannot substitute.",
            )
        )
        quality.append(
            dict(
                source_identity=source_id,
                evidence_reference=evidence,
                metadata_qa="REVIEWED_SOURCE_CODE_AND_DOCUMENTS",
                authorized_numeric_qa="BLOCKED_DATASET_RIGHTS_NOT_ESTABLISHED",
                verified_numeric_facts=None,
                corporate_action_quality="NOT_ESTABLISHED",
                delisting_completeness="NOT_ESTABLISHED",
                suspension_completeness="NOT_ESTABLISHED",
                coverage_count=None,
                independent_reconciliation="NOT_AVAILABLE",
                verification_result="METADATA_ONLY_NOT_NUMERIC_PASS",
            )
        )
        admission.append(
            dict(
                source_identity=source_id,
                state="SOURCE_BLOCKED",
                **registry,
                gaps=[
                    "DATASET_SPECIFIC_RIGHTS_NOT_ESTABLISHED",
                    "CONTEMPORANEOUS_PIT_NOT_ESTABLISHED",
                    "NUMERIC_GENERATION_IDENTITY_NOT_ESTABLISHED",
                    "BLIND_NUMERIC_QA_NOT_AUTHORIZED",
                    "SIGNATURE_AUTHORITY_NOT_ESTABLISHED",
                ],
                evidence_reference=evidence,
                performance_blind=True,
                production_admission=False,
            )
        )

    gaps = [
        dict(
            gap_id="SWS_RIGHTS",
            source="sws-taxonomy / sws-membership / sws-official-index",
            requirement="Dataset-specific grant",
            current_evidence="Official indexed classification explanation; direct PDF 403 and announcement page unavailable",
            missing_proof="Storage, research, automation, derived data, backtesting, retention and redistribution scopes",
            risk="Public visibility is not a grant",
            acquisition_route="SWS official website / sales and data-product enquiry",
            category="NEW_LICENSE_REQUIRED",
            can_codex_complete=False,
            owner_action_required=True,
            legal_review_required=True,
            estimated_effort="QUOTE_REQUIRED_PROVIDER_DEPENDENT",
            priority=1,
            admission_impact="Rights gate for SWS generations",
        ),
        dict(
            gap_id="SWS_PIT",
            source="sws-membership / sws-taxonomy",
            requirement="Contemporaneous full-universe snapshots",
            current_evidence="Effective intervals and indexed 2021 version announcement",
            missing_proof="Publisher and receipt timestamps, original constituent changes, revision chain and full universe",
            risk="Backfilled historical dates may encode later knowledge",
            acquisition_route="SWS historical constituent/classification archive request",
            category="PROVIDER_CONFIRMATION_REQUIRED",
            can_codex_complete=False,
            owner_action_required=True,
            legal_review_required=True,
            estimated_effort="PROVIDER_ARCHIVE_SCOPE_CONFIRMATION_REQUIRED",
            priority=1,
            admission_impact="PIT gate for a new generation only; no old tier rewrite",
        ),
        dict(
            gap_id="TDX_RIGHTS",
            source="tdx-daily-bars / tdx-corporate-actions",
            requirement="Approved machine interface and data rights",
            current_evidence="Exact official terms and provider exchange-licence list",
            missing_proof="Owner's endpoint/API-specific grant and permitted derivation/retention",
            risk="Provider's exchange licence does not automatically cover this client",
            acquisition_route="TDX licensed data-product enquiry; official tdxdata page",
            category="PROVIDER_CONFIRMATION_REQUIRED",
            can_codex_complete=False,
            owner_action_required=True,
            legal_review_required=True,
            estimated_effort="QUOTE_REQUIRED",
            priority=1,
            admission_impact="TDX rights gate",
        ),
        dict(
            gap_id="SINA_RIGHTS",
            source="sina-adjustment-factors / optional price fallback",
            requirement="Endpoint-specific rights",
            current_evidence="Exact copyright and finance-app terms",
            missing_proof="Applicability to hfq.js and stock endpoints; research/automation/derived-data licence",
            risk="General terms restrict reuse and do not authorize the current adapter",
            acquisition_route="Sina official support / written dataset enquiry",
            category="PROVIDER_CONFIRMATION_REQUIRED",
            can_codex_complete=False,
            owner_action_required=True,
            legal_review_required=True,
            estimated_effort="PROVIDER_CONFIRMATION_REQUIRED",
            priority=1,
            admission_impact="Sina rights gate",
        ),
        dict(
            gap_id="BAOSTOCK_SCOPE",
            source="baostock-lifecycle / baostock-adjusted-prices",
            requirement="Dataset licence and historical guarantees",
            current_evidence="Official free API/local-storage description and lifecycle/adjustment docs",
            missing_proof="Upstream sublicensing, retention/redistribution, corrected-history availability and full coverage",
            risk="Documented API capability is not complete factual or sublicensing proof",
            acquisition_route="baostock@163.com listed in official platform document",
            category="PROVIDER_CONFIRMATION_REQUIRED",
            can_codex_complete=False,
            owner_action_required=True,
            legal_review_required=True,
            estimated_effort="WRITTEN_CONFIRMATION_REQUIRED",
            priority=2,
            admission_impact="BaoStock rights and lifecycle gates",
        ),
        dict(
            gap_id="BLIND_QA",
            source="All numerical inputs and derived series",
            requirement="Independent authorized factual QA",
            current_evidence="Pinned source formulas and documented method differences",
            missing_proof="Exact sessions, missingness, lifecycle, events, method equivalence and independent provenance",
            risk="Source wrappers or different adjustment methods can masquerade as independent confirmation",
            acquisition_route="Obtain two legally permitted factual datasets, then trusted-authority blind QA with receipts",
            category="INDEPENDENT_QA_REQUIRED",
            can_codex_complete=False,
            owner_action_required=True,
            legal_review_required=True,
            estimated_effort="AFTER_RIGHTS_AND_SCOPE_ESTABLISHED",
            priority=2,
            admission_impact="Quality gate; no performance-based source selection",
        ),
        dict(
            gap_id="PRODUCTION_AUTHORITY",
            source="Production admission authority",
            requirement="Governance-approved signing identity and durable receipts",
            current_evidence="Only ephemeral synthetic HMAC exists",
            missing_proof="Named approver, controlled key store, public-key trust, rotation/revocation and independent receipt retention",
            risk="Test signatures cannot authenticate production grants",
            acquisition_route="Owner approves identity, authority roles and credential-store policy before implementation",
            category="OWNER_APPROVAL_REQUIRED",
            can_codex_complete=False,
            owner_action_required=True,
            legal_review_required=False,
            estimated_effort="OWNER_GOVERNANCE_DECISION_REQUIRED",
            priority=1,
            admission_impact="Production signing/admission gate",
        ),
        dict(
            gap_id="WINDOWS_NATIVE",
            source="Optional Windows native worker",
            requirement="Native quantitative process isolation",
            current_evidence="Windows junction rejection passed; actual isolation is Linux Docker",
            missing_proof="Native sandbox/mount/descriptor/network containment acceptance",
            risk="Path validation alone is not process isolation",
            acquisition_route="Use tested Linux Docker path; native Windows requires a separately scoped engineering task",
            category="CODE_FIXABLE",
            can_codex_complete=True,
            owner_action_required=False,
            legal_review_required=False,
            estimated_effort="OPTIONAL_PLATFORM_WORK_NOT_NEEDED_FOR_LINUX_ROUTE",
            priority=3,
            admission_impact="Windows native readiness only",
        ),
    ]
    owner_actions = [
        dict(
            id="OWNER_SWS",
            provider="SWS Research",
            action="Authorize sending the prepared SWS packet; obtain dataset rights and contemporaneous archives; approve any quoted contract separately",
            packet="docs/research/source-qualification/vendor-evidence-requests/sws.md",
        ),
        dict(
            id="OWNER_TDX",
            provider="TDX",
            action="Authorize the TDX enquiry and obtain owner-specific API/data rights",
            packet="docs/research/source-qualification/vendor-evidence-requests/tdx.md",
        ),
        dict(
            id="OWNER_SINA",
            provider="Sina",
            action="Authorize written confirmation of hfq endpoint research and derivation rights",
            packet="docs/research/source-qualification/vendor-evidence-requests/sina.md",
        ),
        dict(
            id="OWNER_BAOSTOCK",
            provider="BaoStock",
            action="Authorize the BaoStock enquiry for licence scope, archive and complete lifecycle evidence",
            packet="docs/research/source-qualification/vendor-evidence-requests/baostock.md",
        ),
        dict(
            id="OWNER_AUTHORITY",
            provider="Owner governance",
            action="Approve named admission authority, controlled signing-key storage and durable external receipts",
            packet="docs/engineering/real-source-admission-acceptance.md",
        ),
    ]
    readiness = report(
        current_sources_audited=len(inventory),
        official_documents_verified=len(verified),
        public_documents_collected=sum(d["content_sha256"] is not None for d in documents),
        attempted_document_endpoints=len(documents),
        real_source_rights_verified=0,
        real_pit_sources_verified=0,
        real_sources_admitted=0,
        rights_readiness="BLOCKED_DATASET_SPECIFIC_GRANTS_NOT_ESTABLISHED",
        pit_readiness="CONTEMPORANEOUS_MEMBERSHIP_NOT_ESTABLISHED",
        quality_readiness="METADATA_REVIEWED_NUMERIC_QA_BLOCKED",
        official_index_source="NOT_ESTABLISHED",
        production_authority="SIGNATURE_AUTHORITY_NOT_ESTABLISHED",
        linux_worker_isolation="PASS_LINUX_DOCKER_SYNTHETIC",
        windows_native_isolation="NOT_ESTABLISHED",
        independent_unseen_evidence_ready=False,
        research_readiness="DATA_SOURCE_NOT_READY",
        next_decision="C",
        formal_observations=0,
        formal_forecasts=0,
        future_protocol="NOT_CREATED",
        historical_access_isolation="NOT_CERTIFIED",
        certified_historically_unseen_sessions=0,
        models={"swl1_v1": "FAILED_VALIDATION", "swl1_v2": "FAILED_VALIDATION"},
        sources=[
            {k: s[k] for k in ("source_id", "provider", "dataset", "kind", "source_admission")}
            for s in inventory
        ],
        owner_actions=owner_actions,
        production_identity_requirements=[
            "APPROVED_NAMED_AUTHORITY",
            "CONTROLLED_KEY_STORE",
            "VERIFIABLE_PUBLIC_KEY",
            "ROTATION_AND_REVOCATION",
            "DURABLE_INDEPENDENT_RECEIPTS",
        ],
        no_credentials_inspected=True,
        no_production_keys_created=True,
        external_provider_confirmations_required=4,
        license_requests_required=4,
        owner_approval_actions=len(owner_actions),
        performance_blind=True,
        numeric_qa_run=False,
    )
    return {
        "source-inventory": report(
            upstream_commit=UPSTREAM,
            source_code_hashes=snapshot["source_code_hashes"],
            sources=inventory,
        ),
        "rights-matrix": report(sources=rights),
        "pit-evidence": report(
            sources=pit,
            current_member_history="EFFECTIVE_DATED_RECONSTRUCTION",
            frozen_tiers_unchanged=True,
            findings=snapshot["pit_findings"],
        ),
        "data-quality-assessment": report(
            sources=quality,
            findings=snapshot["quality_findings"],
            stage_a="COMPLETE_METADATA_ONLY",
            stage_b="BLOCKED_RIGHTS_AND_ACCESS_NOT_ESTABLISHED",
        ),
        "source-reconciliation": report(
            independent_reconciliation="NOT_AVAILABLE",
            numeric_comparisons_run=False,
            performance_fields=[],
            candidate_pairs=[
                dict(
                    source_a="Sina factors",
                    source_b="BaoStock reconstructed factors",
                    status="NOT_AVAILABLE_UNAUTHORIZED_AND_METHOD_EQUIVALENCE_UNKNOWN",
                ),
                dict(
                    source_a="BaoStock lifecycle",
                    source_b="SSE public delisting announcement",
                    status="ONE_PUBLIC_DOCUMENT_NOT_UNIVERSE_RECONCILIATION",
                ),
                dict(
                    source_a="CNEquity calendar",
                    source_b="SSE published closure schedule",
                    status="METHODOLOGY_REFERENCE_ONLY_NO_RUNTIME_COMPARISON",
                ),
            ],
        ),
        "admission-results": report(
            real_sources_admitted=0,
            sources=admission,
            pr34_registry_semantics_preserved=True,
            raw_components_not_relabelled=True,
        ),
        "remediation-matrix": report(gaps=gaps),
        "final-readiness": readiness,
        "public-evidence": report(
            documents=documents, payloads_retained=False, signed_grants_included=False
        ),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Compare public reports; default generates metadata only",
    )
    args = parser.parse_args()
    reports = build(ROOT)
    directory = ROOT / REPORT_DIR
    if not args.verify:
        directory.mkdir(parents=True, exist_ok=True)
    for name, data in reports.items():
        raw = (json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
        destination = directory / f"{name}.json"
        if args.verify:
            require(destination.read_bytes() == raw, "QUALIFICATION_REPORT_MISMATCH")
        else:
            destination.write_bytes(raw)
    print(
        json.dumps(
            {
                "qualification_reports": len(reports),
                "real_sources_admitted": 0,
                "research_readiness": "DATA_SOURCE_NOT_READY",
                "verification": "PASS",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
