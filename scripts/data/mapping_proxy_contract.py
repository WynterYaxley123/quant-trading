"""Offline ETF mapping/tradability audit.  Never imports or downloads quotes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


class EvidenceIntegrityFailure(RuntimeError):
    """The official-evidence chain is inconsistent; admission must stop."""


@dataclass(frozen=True)
class ProxyAdmissionEvidence:
    """Derived proxy evidence; deliberately not a direct MappingEvidence row."""

    etf_code: str
    sector_code: str
    mapping_kind: str = "PROXY_MAPPING"
    official_direct_equivalence: bool = False
    methodology_official: bool = (
        False  # official index basic info is not an archived methodology version
    )
    methodology_historical_version_confirmed: bool = False
    methodology_available_at: str | None = None
    methodology_available_before_signal: bool = False
    methodology_valid_from: str | None = None
    methodology_valid_to: str | None = None
    composition_source_type: str = "NO_CONSTITUENT_EVIDENCE"
    composition_coverage_type: str = "NONE"
    composition_source_official: bool = False
    composition_as_of_date: str | None = None
    composition_available_at: str | None = None
    composition_valid_from: str | None = None
    composition_valid_to: str | None = None
    available_before_signal: bool = False
    constituent_count: int = 0
    classified_count: int = 0
    count_share: float | None = None  # percent of observed constituents
    weight_share: float | None = None  # percent of observed weight, never inferred
    other_l2_count: int = 0
    other_l2_summary: str | None = None
    unclassified_count: int = 0
    relationship_documented_from: str | None = None
    official_listing_date: str | None = None
    tradable_start_candidate: str | None = None
    relationship_effective_from: str | None = None  # confirmed, not a candidate date
    relationship_effective_to: str | None = None
    relationship_evidence_available_at: str | None = None
    relationship_available_before_signal: bool = False
    relationship_continuity_status: str = "UNPROVEN"
    relationship_continuity_proven_at: str | None = None
    relationship_continuity_valid_through: str | None = None
    index_change_event_found: bool | None = None
    index_change_search_note: str | None = None
    sw_classification_status: str = "FIXED_CLASSIFICATION_RESEARCH"
    sw_classification_valid_from: str | None = None
    sw_classification_valid_to: str | None = None
    sw_classification_available_at: str | None = None
    sw_classification_available_before_signal: bool = False


def _on_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def current_proxy_status(e: ProxyAdmissionEvidence) -> str:
    """Descriptive concentration of *observed* material, not admission."""
    if not e.methodology_official or not e.composition_source_official or not e.constituent_count:
        return "PROXY_CURRENT_INSUFFICIENT"
    if e.composition_source_type == "ETF_REPLICATION_BASKET_PROXY":
        strong_observed = (
            e.count_share is not None
            and e.count_share >= 90
            and e.unclassified_count == 0
            and e.other_l2_count / e.constituent_count <= 0.10
        )
    elif e.composition_source_type == "TOP10_ONLY_PROXY":
        strong_observed = (
            e.count_share is not None
            and e.count_share >= 80
            and e.weight_share is not None
            and e.weight_share >= 85
            and e.unclassified_count <= 1
        )
    elif e.composition_source_type == "FULL_INDEX_CONSTITUENTS_WITH_WEIGHTS":
        strong_observed = (
            e.count_share is not None
            and e.count_share >= 90
            and e.weight_share is not None
            and e.weight_share >= 90
            and e.unclassified_count == 0
            and e.other_l2_count / e.constituent_count <= 0.10
        )
    else:
        return "PROXY_CURRENT_INSUFFICIENT"
    return "PROXY_CURRENT_STRONG" if strong_observed else "PROXY_CURRENT_MIXED"


def historical_proxy_admissible(
    e: ProxyAdmissionEvidence,
    research_date: str,
    *,
    require_historical_sw: bool = True,
) -> bool:
    """Point-in-time gate. A later snapshot or an unproven interval never backfills t."""
    t = date.fromisoformat(research_date)
    if e.mapping_kind != "PROXY_MAPPING" or e.official_direct_equivalence:
        return False
    if (
        not e.methodology_official
        or not e.methodology_historical_version_confirmed
        or not e.composition_source_official
    ):
        return False
    m_available = _on_date(e.methodology_available_at)
    m_start, m_end = _on_date(e.methodology_valid_from), _on_date(e.methodology_valid_to)
    if (
        m_available is None
        or m_start is None
        or m_end is None
        or m_available > t
        or not m_start <= t <= m_end
        or (m_available == t and not e.methodology_available_before_signal)
    ):
        return False
    # PCF is an ETF creation basket, and Top10 is a subset. Neither proves the full index.
    if e.composition_source_type != "FULL_INDEX_CONSTITUENTS_WITH_WEIGHTS":
        return False
    if (
        e.count_share is None
        or e.count_share < 90
        or e.weight_share is None
        or e.weight_share < 90
        or e.constituent_count <= 0
        or e.unclassified_count != 0
        or e.count_share > 100
        or e.weight_share > 100
        or not 0 <= e.other_l2_count <= e.constituent_count
        or e.other_l2_count / e.constituent_count > 0.10
    ):
        return False
    observed, available = _on_date(e.composition_as_of_date), _on_date(e.composition_available_at)
    if observed is None or available is None or observed > t or available > t:
        return False
    c_start, c_end = _on_date(e.composition_valid_from), _on_date(e.composition_valid_to)
    if (c_start is None) != (c_end is None):
        return False
    if c_start is not None and c_end is not None:
        if not c_start <= t <= c_end:
            return False
    elif observed != t:
        return False  # one snapshot is not an indefinite effective interval
    if available == t and not e.available_before_signal:
        return False  # date-only same-day publication timing is insufficient
    r_start, r_end = _on_date(e.relationship_effective_from), _on_date(e.relationship_effective_to)
    r_available = _on_date(e.relationship_evidence_available_at)
    continuity_proven = _on_date(e.relationship_continuity_proven_at)
    continuity_through = _on_date(e.relationship_continuity_valid_through)
    if (
        r_start is None
        or r_start > t
        or (r_end is not None and t > r_end)
        or e.relationship_continuity_status != "PROVEN_CONTINUOUS"
        or r_available is None
        or r_available > t
        or (r_available == t and not e.relationship_available_before_signal)
        or continuity_proven is None
        or continuity_proven > t
        or continuity_through is None
        or continuity_through < t
        or (continuity_proven == t and not e.relationship_available_before_signal)
    ):
        return False
    # A search finding no index-change notice is not affirmative continuity proof.
    if require_historical_sw:
        s_start, s_end = (
            _on_date(e.sw_classification_valid_from),
            _on_date(e.sw_classification_valid_to),
        )
        s_available = _on_date(e.sw_classification_available_at)
        if (
            e.sw_classification_status != "HISTORICAL_PIT"
            or s_start is None
            or s_end is None
            or s_available is None
            or not s_start <= t <= s_end
            or s_available > t
            or (s_available == t and not e.sw_classification_available_before_signal)
        ):
            return False
    return True
