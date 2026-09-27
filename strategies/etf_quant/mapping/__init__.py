"""Provisional schema validation only; no fuzzy/production mapping implementation."""
from ..domain import ETFMapping, MappingAdmission, MappingResult


def validate_candidate(mapping: ETFMapping) -> MappingResult:
    if mapping.admission_status is MappingAdmission.REJECTED:
        return MappingResult(mapping.industry_code, MappingAdmission.REJECTED, (mapping,), ("EXPLICITLY_REJECTED",))
    required = ("industry_name", "etf_code", "etf_name", "mapping_method", "tracking_index_code",
                "tracking_index_name", "effective_from", "verified_at", "available_at", "mapping_confidence")
    missing = tuple("UNKNOWN:" + name for name in required if getattr(mapping, name) is None)
    return MappingResult(mapping.industry_code,
        MappingAdmission.INCOMPLETE if missing else MappingAdmission.PENDING_CONTRACT,
        (mapping,), (*missing, "PENDING_DEEPSEEK_CONTRACT"))
