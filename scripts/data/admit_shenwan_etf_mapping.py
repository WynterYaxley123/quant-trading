"""Offline ETF mapping/tradability audit.  Never imports or downloads quotes."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import asdict, fields
from datetime import datetime
from pathlib import Path
from typing import TypedDict, cast

import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.data.mapping_official_evidence import (  # noqa: E402 -- Standalone CLI checkout bootstrap.
    _evidence_diagnostics as _evidence_diagnostics,
)
from scripts.data.mapping_official_evidence import (  # noqa: E402 -- Standalone CLI checkout bootstrap.
    _load_official_evidence as _load_official_evidence,
)
from scripts.data.mapping_official_evidence import (  # noqa: E402 -- CLI checkout bootstrap.
    _read_rows as _read_rows,
)
from scripts.data.mapping_proxy_contract import (  # noqa: E402 -- CLI checkout bootstrap.
    EvidenceIntegrityFailure as EvidenceIntegrityFailure,
)
from scripts.data.mapping_proxy_contract import (  # noqa: E402 -- Standalone CLI checkout bootstrap.
    ProxyAdmissionEvidence as ProxyAdmissionEvidence,
)
from scripts.data.mapping_proxy_contract import (  # noqa: E402 -- Standalone CLI checkout bootstrap.
    _on_date as _on_date,
)
from scripts.data.mapping_proxy_contract import (  # noqa: E402 -- Standalone CLI checkout bootstrap.
    current_proxy_status as current_proxy_status,
)
from scripts.data.mapping_proxy_contract import (  # noqa: E402 -- Standalone CLI checkout bootstrap.
    historical_proxy_admissible as historical_proxy_admissible,
)
from scripts.data.mapping_proxy_evidence import (  # noqa: E402 -- CLI checkout bootstrap.
    _load_proxy_evidence as _load_proxy_evidence,
)
from scripts.data.mapping_proxy_evidence import (  # noqa: E402 -- Standalone CLI checkout bootstrap.
    _proxy_diagnostics as _proxy_diagnostics,
)
from src.data.loaders.shenwan_sector_loader import (  # noqa: E402
    load_sector_catalog,
    load_sector_panel,
)
from src.data.providers.etf_local import read_local_etf_snapshot  # noqa: E402
from src.data.providers.shenwan_official import sha256_file  # noqa: E402
from src.data.providers.shenwan_sector import candidate_research_range  # noqa: E402
from strategies.sw_sector_rotation.src.portfolio.sector_etf_mapping import (  # noqa: E402
    MappingEvidence,
    daily_mapping_availability,
    mapping_admission,
    resolve_primary_mapping,
    validate_mapping_evidence,
)


class MappingEvidenceInput(TypedDict):
    sector_code: str
    sector_name: str
    etf_code: str | None
    etf_name: str | None
    market: str | None
    tracking_index_code: str | None
    tracking_index_name: str | None
    mapping_status: str
    mapping_effective_from: str | None
    mapping_effective_to: str | None
    etf_listing_date: str | None
    source_provider: str | None
    source_url: str | None
    source_file: str | None
    source_retrieved_at: str | None
    source_sha256: str | None
    evidence_type: str | None
    is_primary: bool
    notes: str | None


def _mapping_rows(path: Path | None, catalog: pd.DataFrame) -> list[MappingEvidence]:
    if path is None:
        # Explicitly unknown; the legacy example is not tracking evidence.
        return [
            MappingEvidence(
                str(r.sector_code),
                str(r.sector_name),
                notes="No locally verified ETF tracking/effective-date evidence",
            )
            for r in catalog.itertuples()
        ]
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {f.name for f in fields(MappingEvidence)}
    if not required.issubset(frame.columns):
        raise ValueError(
            f"mapping evidence schema missing: {sorted(required - set(frame.columns))}"
        )
    out = []
    for item in frame.to_dict("records"):
        values = {key: (item[key] or None) for key in required}
        values["is_primary"] = item["is_primary"].strip().lower() == "true"
        if item["is_primary"].strip().lower() not in {"true", "false"}:
            raise ValueError("is_primary must be true or false")
        row = MappingEvidence(**cast(MappingEvidenceInput, values))
        if row.source_file:
            source = Path(row.source_file)
            if not source.is_file() or sha256_file(source) != row.source_sha256:
                raise ValueError(f"mapping source_file SHA256 mismatch: {source}")
        out.append(row)
    return out


def build(
    *,
    sector_dir: Path,
    hikyuu_dir: Path,
    output_dir: Path,
    mapping_file: Path | None = None,
    evidence_dir: Path | None = None,
) -> dict:
    sector_meta = json.loads((sector_dir / "sector_admission.json").read_text(encoding="utf-8"))
    if (
        sector_meta.get("admission_level") != "FIXED_CLASSIFICATION_RESEARCH"
        or sector_meta.get("strict_pit") is not False
    ):
        raise ValueError("sector admission changed; do not silently upgrade PIT semantics")
    catalog = load_sector_catalog(sector_dir)
    codes = {str(r.sector_code): str(r.sector_name) for r in catalog.itertuples()}
    evidence = _load_official_evidence(
        _ROOT,
        evidence_dir or _ROOT / "data/processed/shenwan_etf_mapping",
        codes,
    )
    diagnostics = _evidence_diagnostics(evidence, codes)
    rows = _mapping_rows(mapping_file, catalog)
    validate_mapping_evidence(rows, codes)
    etfs, bars = read_local_etf_snapshot(hikyuu_dir)
    etf_meta = {r.etf_code: r for r in etfs.itertuples()}
    bar_lookup = {
        (r.etf_code, r.date): {
            "etf_code": r.etf_code,
            "date": r.date,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
        }
        for r in bars.itertuples()
    }

    common_start, common_end = sector_meta["common_start_date"], sector_meta["common_end_date"]
    panel = load_sector_panel(list(codes), common_start, common_end, processed_dir=sector_dir)
    sector_start, sector_end = candidate_research_range(panel, sector_meta)
    if (sector_start, sector_end) != (
        sector_meta["research_eligible_start"],
        sector_meta["research_eligible_end"],
    ):
        raise ValueError("sector candidate range differs from verified canonical metadata")
    all_dates = sorted(panel["date"].dt.strftime("%Y-%m-%d").unique().tolist())
    next_session = {day: all_dates[i + 1] for i, day in enumerate(all_dates[:-1])}
    candidate_dates = [day for day in all_dates if sector_start <= day <= sector_end]
    proxy_evidence = _load_proxy_evidence(
        _ROOT,
        evidence_dir or _ROOT / "data/processed/shenwan_etf_mapping",
        evidence,
        codes,
        sector_meta["admission_level"],
    )
    proxy_report = _proxy_diagnostics(proxy_evidence, candidate_dates)
    audit_dates = sorted(set(candidate_dates) | {common_end})
    sector_valid = {
        (str(r.sector_code), cast(datetime, r.date).strftime("%Y-%m-%d")): bool(r.is_valid_ohlc)
        for r in panel.itertuples()
    }
    daily = []
    for day in audit_dates:
        execution_date = next_session.get(day)
        for code in codes:
            mapping = resolve_primary_mapping(rows, code, day)
            etf_code = mapping.etf_code if mapping else None
            bar = (
                bar_lookup.get((etf_code, execution_date)) if etf_code and execution_date else None
            )
            availability = daily_mapping_availability(
                rows,
                code,
                day,
                execution_date=execution_date,
                bar=bar,
                sector_bar_valid=sector_valid.get((code, day), False),
            )
            availability["etf_code"] = etf_code
            availability["local_etf_metadata_present"] = bool(etf_code in etf_meta)
            daily.append(availability)
    daily_frame = pd.DataFrame(daily)
    candidate = daily_frame.loc[daily_frame["date"].isin(candidate_dates)]
    coverage = (
        candidate.groupby("date")
        .agg(
            mapped_sector_count=("is_mapping_active", "sum"),
            available_sector_count=("is_etf_executable", "sum"),
            executable_sector_count=("is_executable", "sum"),
            sector_factor_count=("sector_bar_valid", "sum"),
        )
        .reset_index()
    )
    for col in ("mapped", "available", "executable"):
        coverage[f"{col}_ratio"] = coverage[f"{col}_sector_count"] / len(codes)
    counts = coverage["executable_sector_count"].astype(int).tolist()
    level = mapping_admission(rows, codes, counts)
    mapped_codes = sorted(
        {r.sector_code for r in rows if r.mapping_status == "VALIDATED" and r.is_primary}
    )
    etf_codes = [
        cast(str, r.etf_code) for r in rows if r.sector_code in mapped_codes and r.is_primary
    ]
    duplicates = sorted({code for code in etf_codes if etf_codes.count(code) > 1})
    complete_dates = [day for day, count in zip(coverage["date"], counts) if count >= 5]
    report = {
        "status": level,
        "mapping_admission": level,
        **diagnostics,
        **proxy_report,
        "sector_data_admission": sector_meta["admission_level"],
        "strict_pit": False,
        "pit_notice": "NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST",
        "sector_data_snapshot_id": sector_meta["data_snapshot_id"],
        "level2_sector_count": len(codes),
        "mapped_sector_count": len(mapped_codes),
        "unmapped_sector_count": len(codes) - len(mapped_codes),
        "unmapped_sectors": [
            {"sector_code": code, "sector_name": name}
            for code, name in codes.items()
            if code not in mapped_codes
        ],
        "mapping_coverage_ratio": len(mapped_codes) / len(codes),
        "strict_validated_coverage_ratio": len(mapped_codes) / len(codes),
        "validated_primary_etf_count": len(etf_codes),
        "formal_executable_universe_count": int(
            daily_frame.loc[daily_frame["date"].eq(common_end), "is_executable"].sum()
        )
        + proxy_report["proxy_formal_executable_count"],
        "unique_etf_count": len(set(etf_codes)),
        "duplicate_etfs_across_sectors": duplicates,
        "multiple_candidate_sectors": sorted(
            {r.sector_code for r in rows if r.mapping_status == "MULTIPLE_CANDIDATES"}
        ),
        "listing_date_complete_count": sum(bool(r.etf_listing_date) for r in rows if r.is_primary),
        "mapping_effective_from_complete_count": sum(
            bool(r.mapping_effective_from) for r in rows if r.is_primary
        ),
        "mapping_provenance_complete_count": sum(
            bool(r.source_provider and r.source_retrieved_at and (r.source_url or r.source_file))
            for r in rows
            if r.is_primary
        ),
        "local_etf_count": len(etfs),
        "local_listing_date_known_count": int(etfs["listing_date"].notna().sum()),
        "etf_159915": {
            "official_listing_date": next(
                r["official_listing_date"] for r in evidence["catalog"] if r["etf_code"] == "159915"
            ),
            "local_market_data_available": bool(etf_meta.get("sz159915")),
            "local_hikyuu_bar_count": int(cast(int, etf_meta["sz159915"].bar_count)),
            "independent_raw_refresh": False,
            "listing_source": "official evidence; not Hikyuu first bar",
        },
        "latest_common_date": common_end,
        "latest_executable_sector_count": int(
            daily_frame.loc[daily_frame["date"].eq(common_end), "is_executable"].sum()
        ),
        "candidate_session_count": len(counts),
        "historical_executable_min": min(counts) if counts else None,
        "historical_executable_median": statistics.median(counts) if counts else None,
        "historical_executable_mean": statistics.mean(counts) if counts else None,
        "historical_executable_max": max(counts) if counts else None,
        "historical_executable_coverage_ratio_min": min(counts) / len(codes) if counts else None,
        "historical_executable_coverage_ratio_median": statistics.median(counts) / len(codes)
        if counts
        else None,
        "historical_executable_coverage_ratio_mean": statistics.mean(counts) / len(codes)
        if counts
        else None,
        "historical_executable_coverage_ratio_max": max(counts) / len(codes) if counts else None,
        "days_with_executable_ge_5": sum(c >= 5 for c in counts),
        "days_with_executable_lt_5": sum(c < 5 for c in counts),
        "sector_only_eligible_start": sector_start,
        "sector_only_eligible_end": sector_end,
        "sector_plus_etf_candidate_start": min(complete_dates) if complete_dates else None,
        "sector_plus_etf_candidate_end": max(complete_dates) if complete_dates else None,
        "sector_801193_missing_candidate_sessions": len(candidate_dates)
        - sum(sector_valid.get(("801193", day), False) for day in candidate_dates),
        "sector_801193_missing_common_sessions": len(all_dates)
        - sum(sector_valid.get(("801193", day), False) for day in all_dates),
        "candidate_range_note": (
            "Existing sector-only rule reserves 120 prior sessions for features, "
            "six calendar months for training with a 120-session label/purge boundary, "
            "and 120 future sessions for labels. Next-session execution has not been "
            "separately proven or added to this date calculation."
        ),
        "limitations": [
            "Legacy example is unverified and excluded from canonical mapping.",
            "Hikyuu stock.startDate / first local bar do not prove official ETF listing.",
            "Official Layer-1 ETF-to-tracking-index evidence exists, but no official Layer-2 direct equivalence is proven.",
            "Current tracking relationships do not establish historical mapping_effective_from.",
            "Daily bar presence and OHLC do not prove absence of suspension/limit restrictions.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([asdict(r) for r in rows]).to_csv(
        output_dir / "etf_mapping_evidence.csv", index=False
    )
    etfs.to_csv(output_dir / "etf_local_metadata.csv", index=False)
    daily_frame.to_csv(output_dir / "etf_daily_availability.csv", index=False)
    coverage.to_csv(output_dir / "etf_daily_coverage.csv", index=False)
    (output_dir / "etf_mapping_admission.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sector-dir", type=Path, default=Path("data/processed/shenwan"))
    parser.add_argument("--hikyuu-dir", type=Path, default=Path("data/hikyuu"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/processed/shenwan_etf_mapping")
    )
    parser.add_argument("--mapping-file", type=Path, default=None)
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                sector_dir=args.sector_dir,
                hikyuu_dir=args.hikyuu_dir,
                output_dir=args.output_dir,
                mapping_file=args.mapping_file,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
