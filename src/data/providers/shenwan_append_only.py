"""Pure staged-data audit. No fetching, repair, or canonical-file writer.

The existing Shenwan parser and snapshot algorithm remain authoritative.
Passing this contract is necessary, not sufficient, for a future authorized
updater: it must also verify staged raw bytes and atomic publication separately.
"""

from __future__ import annotations

import hashlib
import json
import re

import pandas as pd

from src.data.providers.shenwan_sector import OHLCVA_COLUMNS, _violations, snapshot_id

PROVIDER = "shenwan_research_official"
ENDPOINT = "https://www.swsresearch.com/institute-sw/api/index_publish/trend/?swindexcode={sector_code}&period=DAY"


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def semantic_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def frame_hash(frame: pd.DataFrame) -> str:
    """Full canonical row identity, including nulls, quality and provenance."""
    return hashlib.sha256(frame.to_csv(index=False, float_format="%.17g",
        na_rep="<NULL>", date_format="%Y-%m-%d", lineterminator="\n").encode()).hexdigest()


def _shape(frame: pd.DataFrame, codes: list[str]) -> None:
    if frame.empty or list(frame.columns) != list(OHLCVA_COLUMNS):
        raise ValueError("SCHEMA_DRIFT_BLOCKER")
    if not pd.api.types.is_datetime64_ns_dtype(frame["date"]):
        raise ValueError("DATE_SCHEMA_BLOCKER")
    dates = frame["date"]
    if dates.isna().any() or not dates.equals(dates.dt.normalize()):
        raise ValueError("DATE_INTEGRITY_BLOCKER")
    if frame.duplicated(["date", "sector_code"]).any():
        raise ValueError("DUPLICATE_CANONICAL_KEY_BLOCKER")
    if set(frame["sector_code"]) != set(codes):
        raise ValueError("U0_IDENTITY_BLOCKER")
    if frame["source_provider"].isna().any() or not frame["source_provider"].eq(PROVIDER).all():
        raise ValueError("SOURCE_DRIFT_BLOCKER")
    expected = frame["sector_code"].map(lambda code: ENDPOINT.format(sector_code=code))
    if not frame["source_url"].equals(expected.rename("source_url")):
        raise ValueError("SOURCE_ENDPOINT_DRIFT_BLOCKER")
    if frame["is_valid_ohlc"].dtype != bool:
        raise ValueError("QUALITY_FLAG_SCHEMA_BLOCKER")


def audit_source_overlap(parent_response: pd.DataFrame, staged_response: pd.DataFrame, *,
                         cutoff: str, sector_codes: list[str]) -> dict:
    """Compare parsed *raw responses*, before constructing a canonical append.

    Both inputs must use the existing parser at raw precision. Do not compare
    a rounded canonical CSV against a newly parsed raw response. Retrieval
    metadata may change on a new response; historical economic observations,
    missingness, names and quality flags may not. This cannot verify raw bytes
    by itself, and is never invoked on real unseen prices by the readiness CLI.
    """
    _shape(parent_response, sector_codes)
    _shape(staged_response, sector_codes)
    boundary = pd.Timestamp(cutoff)
    if pd.isna(boundary) or boundary.tz is not None or boundary != boundary.normalize():
        raise ValueError("CUTOFF_INTEGRITY_BLOCKER")
    columns = ["date", "sector_code", "sector_name", "open", "high", "low", "close",
               "volume", "amount", "is_valid_ohlc", "quality_violations"]
    def history(frame):
        return frame.loc[frame["date"].le(boundary), columns].sort_values(
            ["sector_code", "date"]).reset_index(drop=True)
    parent, overlap = history(parent_response), history(staged_response)
    if parent.empty or parent_response["date"].max() != boundary:
        raise ValueError("PARENT_SOURCE_CUTOFF_BLOCKER")
    if len(parent) != len(overlap):
        raise ValueError("SOURCE_HISTORICAL_DELETION_OR_BACKFILL_BLOCKER")
    if not parent.equals(overlap):
        raise ValueError("SOURCE_HISTORICAL_REVISION_BLOCKER")
    return {"status": "SOURCE_OVERLAP_CONTRACT_PASS", "overlapRowsChecked": len(parent),
            "historicalRevisions": 0, "historicalSourceValuesUnchanged": True,
            "historicalSourceHash": frame_hash(parent), "rawBytesVerifiedByThisFunction": False}


def audit_append_only(parent: pd.DataFrame, staged: pd.DataFrame, *,
                      cutoff: str, sector_codes: list[str], parent_snapshot: str,
                      parent_raw: dict[str, str], staged_raw: dict[str, str],
                      code_fingerprints: dict[str, str], as_of: str) -> dict:
    """Reject *any* historical mutation before a future writer is permitted.

    Input frames are full candidate tables, not patches. Old rows must retain
    exact order, dtype, values, missingness, flags and source provenance. New
    rows are never synthesized or filled here. Caller-supplied fingerprints
    must come from independently verified raw files, not this audit alone.
    """
    codes = sorted(sector_codes)
    if not codes or len(codes) != len(set(codes)) or not all(isinstance(c, str) for c in codes):
        raise ValueError("U0_IDENTITY_BLOCKER")
    _shape(parent, codes)
    _shape(staged, codes)
    if not parent.dtypes.equals(staged.dtypes):
        raise ValueError("SCHEMA_DRIFT_BLOCKER")
    boundary, now = pd.Timestamp(cutoff), pd.Timestamp(as_of)
    if (boundary.tz is not None or now.tz is not None or boundary != boundary.normalize()
            or now != now.normalize() or boundary > now or parent["date"].max() != boundary):
        raise ValueError("CUTOFF_INTEGRITY_BLOCKER")
    old = staged.loc[staged["date"].le(boundary)].reset_index(drop=True)
    original = parent.reset_index(drop=True)
    if len(old) != len(original):
        raise ValueError("HISTORICAL_ROW_DELETION_OR_BACKFILL_BLOCKER")
    if not old.equals(original):
        raise ValueError("HISTORICAL_DATA_REVISION_BLOCKER")
    if not staged.iloc[:len(parent)].reset_index(drop=True).equals(original):
        raise ValueError("HISTORICAL_PREFIX_ORDER_BLOCKER")
    new = staged.iloc[len(parent):]
    if not new["date"].gt(boundary).all() or not new["date"].le(now).all():
        raise ValueError("NON_APPEND_OR_FUTURE_PLACEHOLDER_BLOCKER")
    if snapshot_id(parent_raw, code_fingerprints=code_fingerprints) != parent_snapshot:
        raise ValueError("PARENT_SNAPSHOT_IDENTITY_BLOCKER")
    if set(parent_raw) != set(staged_raw):
        raise ValueError("RAW_SOURCE_SET_DRIFT_BLOCKER")
    for name, fingerprint in staged_raw.items():
        if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise ValueError("RAW_FINGERPRINT_BLOCKER")
        if (not name.startswith("sector_history/") and name != "sector_history_manifest.json"
                and fingerprint != parent_raw[name]):
            raise ValueError("CATALOG_OR_CLASSIFICATION_DRIFT_BLOCKER")
    for row in new.to_dict("records"):
        code = row["sector_code"]
        filename = f"sector_history/{code}.json"
        if (row["source_filename"] != filename or row["source_sha256"] != staged_raw.get(filename)
                or row["source_snapshot"] != row["source_sha256"]
                or staged_raw.get(filename) == parent_raw.get(filename)):
            raise ValueError("NEW_ROW_PROVENANCE_BLOCKER")
        parser_input = dict(row)
        for key in ("volume", "amount"):
            if pd.isna(parser_input[key]):
                parser_input[key] = None
        violations = _violations(parser_input)
        recorded = "" if pd.isna(row["quality_violations"]) else row["quality_violations"]
        if violations != recorded or row["is_valid_ohlc"] != (not violations):
            raise ValueError("NEW_ROW_QUALITY_PROVENANCE_BLOCKER")
        try:
            retrieved = pd.Timestamp(row["source_retrieved_at"])
            if (pd.isna(retrieved) or retrieved.tzinfo is None
                    or row["date"].date() > retrieved.date() or retrieved.date() > now.date()):
                raise ValueError()
        except (TypeError, ValueError):
            raise ValueError("NEW_ROW_RETRIEVAL_TIME_BLOCKER") from None
    new_snapshot = snapshot_id(staged_raw, code_fingerprints=code_fingerprints)
    if (new.empty and staged_raw != parent_raw) or (not new.empty and new_snapshot == parent_snapshot):
        raise ValueError("SNAPSHOT_LINEAGE_BLOCKER")
    before, after = frame_hash(original), frame_hash(old)
    return {
        "status": "APPEND_ONLY_CONTRACT_PASS", "parentSnapshotId": parent_snapshot,
        "snapshotId": new_snapshot, "oldCutoff": cutoff,
        "newCutoff": str(staged["date"].max().date()), "overlapRowsChecked": len(old),
        "oldRowCount": len(parent), "newRowCount": len(staged), "duplicateCount": 0,
        "historicalRevisions": 0, "appendedRows": len(new),
        "appendedDateRange": [str(new["date"].min().date()), str(new["date"].max().date())]
            if not new.empty else None,
        "appendedRowsBySector": {code: int(new["sector_code"].eq(code).sum()) for code in codes},
        "historicalPrefixHashBefore": before, "historicalPrefixHashAfter": after,
        "historicalPrefixUnchanged": before == after, "u0Hash": semantic_hash(codes),
        "parentInvalidOhlcCount": int((~parent["is_valid_ohlc"]).sum()),
        "historicalMissingnessPreserved": True, "dataApplied": False,
        "rawBytesVerifiedByThisFunction": False,
    }
