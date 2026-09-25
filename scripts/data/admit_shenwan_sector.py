"""只读申万 raw，验证哈希并生成 canonical、质量与准入文件。

运行：docker compose exec quant-research python scripts/data/admit_shenwan_sector.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd  # noqa: E402

from src.data.providers.shenwan_official import (  # noqa: E402
    DEFAULT_RAW_DIR, STOCK_CLASSIFICATION_FILENAME, ShenwanRawDataError,
    sha256_file, verify_manifest,
)
from src.data.providers.shenwan_sector import (  # noqa: E402
    PARSER_VERSION, SCHEMA_VERSION, TRANSFORM_VERSION, audit_coverage,
    candidate_research_range, load_history_manifest, load_raw_catalog,
    parse_classification_with_intervals, parse_sector_ohlcva, snapshot_id,
)
from src.data.providers.shenwan_sector_admission import evaluate_admission  # noqa: E402


def build(raw_dir: Path, history_manifest: Path, processed_dir: Path) -> dict:
    raw_dir = raw_dir.resolve()
    processed_dir = processed_dir.resolve()
    if raw_dir == processed_dir or raw_dir in processed_dir.parents:
        raise ShenwanRawDataError("processed 目录不得位于 raw 目录内")
    classification_records = verify_manifest(raw_dir)
    classification_record = next(
        (r for r in classification_records if r.original_filename == STOCK_CLASSIFICATION_FILENAME), None
    )
    if classification_record is None:
        raise ShenwanRawDataError("未登记官方 StockClassifyUse_stock.xls")
    manifest, history_by_code = load_history_manifest(raw_dir, history_manifest)
    catalog, catalog_hashes = load_raw_catalog(raw_dir, retrieved_at=manifest.get("retrieved_at"))
    classification = parse_classification_with_intervals(raw_dir)
    market = parse_sector_ohlcva(raw_dir, catalog, history_by_code)
    summary, coverage = audit_coverage(market, catalog)
    start, end = candidate_research_range(market, summary)

    fingerprints = {
        STOCK_CLASSIFICATION_FILENAME: classification_record.sha256,
        **catalog_hashes,
        **{f"sector_history/{code}.json": item["sha256"] for code, item in history_by_code.items()},
        "sector_history_manifest.json": sha256_file(history_manifest),
    }
    code_fingerprints = {
        "shenwan_sector.py": sha256_file(_ROOT / "src/data/providers/shenwan_sector.py"),
        "shenwan_official.py": sha256_file(_ROOT / "src/data/providers/shenwan_official.py"),
        "shenwan_sector_admission.py": sha256_file(_ROOT / "src/data/providers/shenwan_sector_admission.py"),
        "admit_shenwan_sector.py": sha256_file(Path(__file__)),
    }
    identifier = snapshot_id(fingerprints, code_fingerprints=code_fingerprints)
    decision = evaluate_admission(
        catalog, market, classification, provenance_verified=True,
        candidate_start=start, candidate_end=end,
    )
    invalid = market.loc[~market["is_valid_ohlc"]].copy()
    invalid["root_cause_class"] = "SOURCE_INVALID"
    # 原始 JSON 本身违反 high/low 关系；保留整行和 source_row，禁止静默修复。
    duplicates = int(classification.duplicated().sum())
    conflicts = int(
        classification.groupby(["symbol", "effective_from"])["sector_code"]
        .nunique().gt(1).sum()
    )
    summary.update({
        "sector_name_coverage": float(catalog["sector_name"].notna().mean()),
        "volume_nonnull_ratio": float(market["volume"].notna().mean()),
        "amount_nonnull_ratio": float(market["amount"].notna().mean()),
        "classification_row_count": len(classification),
        "classification_unique_symbols": int(classification["symbol"].nunique()),
        "classification_unique_sector_codes": int(classification["sector_code"].nunique()),
        "classification_duplicate_count": duplicates,
        "classification_conflict_count": conflicts,
        "classification_version": None,
        "effective_to_official_present": bool(classification["effective_to_official"].notna().any()),
        "effective_to_derived_count": int(classification["effective_to_derived"].notna().sum()),
        "available_at_present": bool(classification["available_at"].notna().any()),
        "research_eligible_start": start,
        "research_eligible_end": end,
        "data_snapshot_id": identifier,
        "admission_level": decision.level,
        "strict_pit": decision.strict_pit,
        "admission_reasons": decision.reasons,
        "parser_version": PARSER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "transform_version": TRANSFORM_VERSION,
        "raw_fingerprints": fingerprints,
        "code_fingerprints": code_fingerprints,
        "catalog_provenance_note": (
            "source URL and retrieved_at reconstructed from committed acquisition script "
            "and history manifest; raw API response contains L2 indextype pagination evidence"
        ),
        "volume_amount_units": None,
        "historical_index_recalculation_policy": None,
    })
    processed_dir.mkdir(parents=True, exist_ok=True)
    catalog.to_csv(processed_dir / "sector_catalog.csv", index=False, date_format="%Y-%m-%d")
    market.to_csv(processed_dir / "sector_ohlcva.csv", index=False, date_format="%Y-%m-%d", float_format="%.12g")
    classification.to_csv(processed_dir / "stock_classification_canonical.csv", index=False, date_format="%Y-%m-%d")
    coverage.to_csv(processed_dir / "sector_coverage.csv", index=False)
    invalid.to_csv(processed_dir / "sector_invalid_ohlc.csv", index=False, date_format="%Y-%m-%d", float_format="%.12g")
    summary["canonical_hashes"] = {
        name: sha256_file(processed_dir / name)
        for name in (
            "sector_catalog.csv", "sector_ohlcva.csv",
            "stock_classification_canonical.csv", "sector_coverage.csv",
            "sector_invalid_ohlc.csv",
        )
    }
    (processed_dir / "sector_admission.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--history-manifest", type=Path, default=Path("data/manifests/shenwan_sector_history_manifest.json"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/shenwan"))
    args = parser.parse_args()
    result = build(args.raw_dir, args.history_manifest, args.processed_dir)
    compact = {k: v for k, v in result.items() if k not in {"raw_fingerprints"}}
    print(json.dumps(compact, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
