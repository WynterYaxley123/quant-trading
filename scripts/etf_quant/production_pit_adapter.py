"""Production PIT evidence registry builder for ETF-Quant V1.

Runs entirely outside the Git work tree. Reads already-captured official raw bytes,
produces immutable evidence packages, derives benchmark L2 exposure, applies the
frozen B40 rule, emits the evidence book the existing runtime adapter consumes, and
writes a small metadata registry that *is* safe to commit.

It never contacts the network: collection is a separate, auditable step, and a
build that silently re-fetched would destroy reproducibility.
"""

from __future__ import annotations

import json

from scripts.etf_quant.production_pit_lineage import lineage_payload

# Explicit external roots support other machines; existing deployment defaults
# remain compatible. This builder is not part of the portable demo/test flow.
from scripts.etf_quant.production_pit_settings import (
    CSI_WEIGHT_ENDPOINT,
    SWS_MEMBERSHIP_ENDPOINT,
    TARGET_L2_CODES,
)
from scripts.etf_quant.production_pit_settings import REPO as REPO
from strategies.etf_quant.domain.industry_level import default_taxonomy  # noqa: E402
from strategies.etf_quant.evidence import (  # noqa: E402
    KIND_DOCUMENTED_EXTRACTION,
    adapter_classification_source_document,
    adapter_record,
    adapter_weight_source_document,
)


def _row(payload: dict):
    from strategies.etf_quant.evidence import ConstituentRow

    return ConstituentRow(
        security_code=payload["security_code"],
        weight_pct=float(payload["weight_pct"]),
        security_name=payload.get("security_name"),
    )


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


def benchmark_effective_day(
    vector: dict, effective: dict[str, str], *, valid_from: str, floor_day: str
) -> str:
    """The one effective date a benchmark's weight vector may honestly carry.

    It must not post-date any constituent's own official date, or the adapter would
    see a classification taking effect after the vector it explains, and it must not
    post-date the validity window. Where the provider states no date, the floor is
    the observation date. Computing this in exactly one place is what keeps the
    weight document and the adapter record from disagreeing.
    """
    member_days = [
        effective[row["security_code"]]
        for row in vector["rows"]
        if row["security_code"] in effective
    ]
    day = max(member_days) if member_days else min(floor_day, valid_from)
    return min(day, valid_from)


def build_adapter_records(
    *,
    vectors,
    assignments,
    relations,
    pin,
    observed_at,
    available_at,
    valid_from,
    valid_through,
    sws_effective=None,
    sws_provenance=None,
    csi_lineage_by_index=None,
    csi_by_security=None,
) -> list[dict]:
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
    taxonomy = default_taxonomy()  # noqa: F841 -- Keep validation/construction side effects even when result is unused.
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
        members = [row for row in vector["rows"] if row["security_code"] in assignments]
        if len(members) != len(vector["rows"]):
            continue
        weight_day = benchmark_effective_day(
            vector, effective, valid_from=valid_from, floor_day=floor_day
        )
        weight_doc = adapter_weight_source_document(
            benchmark_code=benchmark_code,
            constituent_effective_date=weight_day,
            rows=tuple(_row(row) for row in members),
            declared_constituent_count=vector["declared"],
        )
        benchmark_note = (
            f"CSI official constituent weight vector for {benchmark_code}, rebuilt from "
            f"the provider's per-security reverse-query responses; constituent effective "
            f"date {weight_day} anchored to the earliest official constituent date and "
            f"capped at the validity start {valid_from}"
        )
        weight_source = pin.pin_bytes(
            relative_path=f"weights/{benchmark_code}_weights_v1.json",
            body=weight_doc,
            source_url=CSI_WEIGHT_ENDPOINT,
            content_type="application/json;charset=UTF-8",
            evidence_observed_at=observed_at,
            source_retrieved_at=observed_at,
            note=benchmark_note,
            kind=KIND_DOCUMENTED_EXTRACTION,
            derived_from=lineage_payload(
                csi_lineage_by_index.get(benchmark_code, ()), csi_by_security
            ),
        )
        # The classification document is rebuilt per relation because the adapter
        # requires every classification row's availability to be no later than the
        # record's own availability instant. Pinning per relation keeps each record's
        # pinned bytes internally consistent instead of reusing one loose document.
        for relation in by_benchmark.get(benchmark_code, []):
            class_doc = adapter_classification_source_document(
                rows=tuple(
                    _classified(
                        row, assignments, effective, weight_day, relation.evidence_available_at
                    )
                    for row in members
                ),
                effective_date=weight_day,
                available_at=relation.evidence_available_at,
            )
            class_source = pin.pin_bytes(
                relative_path=(
                    f"classification/{benchmark_code}_"
                    f"{relation.etf_code.replace('.', '_')}_classification_v1.json"
                ),
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
                    for code, digest in sorted(sws_provenance.items())
                )[:400],
            )
            decoded_weight = json.loads(weight_doc.decode("utf-8"))
            decoded_class = json.loads(class_doc.decode("utf-8"))
            constituents = decoded_weight["constituents"]
            classifications = decoded_class["classifications"]
            declared = decoded_weight["declared_constituent_count"]
            for industry_code in sorted({assignments[row["security_code"]][2] for row in members}):
                records.append(
                    adapter_record(
                        industry_code=industry_code,
                        etf_code=relation.etf_code,
                        etf_name=relation.etf_name,
                        benchmark_code=benchmark_code,
                        source_publication_at=None,
                        evidence_observed_at=relation.evidence_observed_at,
                        available_at=relation.evidence_available_at,
                        constituent_effective_date=weight_day,
                        weight_effective_date=weight_day,
                        valid_through=valid_through,
                        declared_constituent_count=declared,
                        weight_source=weight_source,
                        classification_source=class_source,
                        constituents=constituents,
                        classifications=classifications,
                        provider="中证指数有限公司 (China Securities Index Co., Ltd.)",
                    )
                )
    return records


def _classified(row, assignments, effective, fallback, available_at):
    from strategies.etf_quant.evidence import ClassificationRow

    security = row["security_code"]
    l1, l1_name, l2, l2_name = assignments[security]
    day = effective.get(security, fallback)
    if day > fallback:
        day = fallback
    return ClassificationRow(
        security_code=security,
        shenwan_l1_code=l1,
        shenwan_l1_name=l1_name,
        shenwan_l2_code=l2,
        shenwan_l2_name=l2_name,
        taxonomy_version="SWCLASS2021",
        classification_effective_from=day,
        evidence_observed_at=available_at,
        evidence_available_at=available_at,
    )
