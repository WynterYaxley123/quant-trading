"""Offline date/metadata readiness only; no model or performance imports.

Never loads OHLCVA values, forward returns, factors, predictions or rankings.
Frozen identity verification uses source bytes/JSON rather than importing
the historical protocol module (which imports model/evaluation code).
"""

from __future__ import annotations

import ast
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re

import pandas as pd

from src.data.providers.shenwan_append_only import ENDPOINT, PROVIDER, semantic_hash
from src.data.providers.shenwan_sector import OHLCVA_COLUMNS, snapshot_id

ROOT = Path(__file__).resolve().parents[1]
BASE = "research/configs/f1_independent_validation_v1"
PROTOCOL = "research/f1_independent_validation_v1_protocol.py"
IDENTITIES = {
    "protocolHash": "2344cc685201476de957109b9fccc2681923e2c4591b5ed91740a56baf128410",
    "candidateDefinitionHash": "6c2b16555b6dfd5d848ea451b09e7b75f53da67747fc76fd052d93afd3ea156b",
    "splitPolicyHash": "3b6b2d754211169039439c8b377fd9eb26d5cb5db0f80d62cffc1d19c81a7038",
    "validationPhaseDefinitionHash": "28d3980e28b41b37d2a327aad6081e8312cf66d66762c13e33cc8ba814c8fa7f",
}
CONFIG_HASH = "39c603097c2cf49e61b610407dc0a7609a6b14426a125ead556ac9ed1008c9d8"
PARENT_SNAPSHOT = "872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500"
PARENT_CUTOFF = "2026-09-18"
PARENT_MARKET_SHA = "884c7dbaaacf6aa5652b63cde5153265ca383fe5bec18fa0a40c410a76b5a887"
SEAL = {"validation": "SEALED", "finalOos": "SEALED", "validationState": "UNSEEN",
        "validationOpened": False, "validationFirstOpenedAt": None,
        "validationPerformanceRead": False, "validationResultsGenerated": False,
        "finalOosPerformanceRead": False}
HORIZONS = (10, 40, 120)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def frozen_identity(root: Path = ROOT) -> tuple[dict, dict]:
    """Recompute the original hash payload without importing its code."""
    config, candidate, split = (_json(root / f"{BASE}{suffix}.json")
                                for suffix in ("", "_candidate", "_split"))
    source = (root / PROTOCOL).read_bytes()
    constants = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                constants[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    for name in ("FROZEN_CANDIDATE_HASH", "FROZEN_PHASE_HASH", "FROZEN_CONFIG_HASH", "FROZEN_PROTOCOL_HASH"):
        source, n = re.subn(rb"^" + name.encode() + rb' = "(?:[0-9a-f]{64}|<PENDING>)"$',
            name.encode() + b' = "<SELF>"', source, flags=re.MULTILINE)
        if n != 1:
            raise ValueError("VALIDATION_FROZEN_IDENTITY_DRIFT_BLOCKER")
    payload = {
        "researchType": constants["RESEARCH_TYPE"], "phase": "PREREGISTERED",
        "config": config, "candidate": candidate, "split": split,
        "documents": {constants[k]: sha(root / constants[k]) for k in ("DOCUMENT_PATH", "TRACE_PATH")},
        "protocolModuleIdentity": hashlib.sha256(source).hexdigest(),
        "constants": {"sourceResultCommit": constants["SOURCE_RESULT_COMMIT"],
                      "sourceHandoffCommit": constants["SOURCE_HANDOFF_COMMIT"],
                      "splitPolicyHash": constants["SPLIT_POLICY_HASH"],
                      "blocks": [list(b) for b in constants["BLOCKS"]],
                      "horizons": list(constants["HORIZONS"])},
    }
    actual = {"protocolHash": semantic_hash(payload), "candidateDefinitionHash": semantic_hash(candidate),
              "splitPolicyHash": split["splitPolicyHash"], "validationPhaseDefinitionHash": semantic_hash(split)}
    declarations = {"FROZEN_CANDIDATE_HASH": IDENTITIES["candidateDefinitionHash"],
                    "FROZEN_PHASE_HASH": IDENTITIES["validationPhaseDefinitionHash"],
                    "FROZEN_CONFIG_HASH": CONFIG_HASH, "FROZEN_PROTOCOL_HASH": IDENTITIES["protocolHash"]}
    if (actual != IDENTITIES or semantic_hash(config) != CONFIG_HASH
            or any(constants.get(k) != value for k, value in declarations.items())):
        raise ValueError("VALIDATION_FROZEN_IDENTITY_DRIFT_BLOCKER")
    if config["seal"] != SEAL:
        raise PermissionError("VALIDATION_SEAL_STATE_BLOCKER")
    for path, expected in config["sourceFileSha256"].items():
        if sha(root / path) != expected:
            raise ValueError(f"VALIDATION_FROZEN_IDENTITY_DRIFT_BLOCKER: {path}")
    return config, split


def source_development_identity(root: Path, config: dict) -> int:
    """Fingerprint existing source artifacts, never deserialize result values."""
    count = 0
    source = config["source"]
    for run in source["runs"]:
        folder = root / run["path"]
        if sha(folder / "metadata.json") != run["metadataSha256"]:
            raise ValueError("SOURCE_DEVELOPMENT_PROVENANCE_BLOCKER")
        metadata = _json(folder / "metadata.json")
        if (metadata["phase"] != "DEVELOPMENT" or metadata["developmentIds"] != "E001-E100"
                or metadata["protocolHash"] != source["protocolHash"]
                or metadata["executionGitCommit"] != source["implementationCommit"]
                or metadata["validation"] != "SEALED" or metadata["finalOos"] != "SEALED"
                or semantic_hash(metadata["contentSha256"]) != source["contentManifestHash"]
                or len(metadata["contentSha256"]) != source["filesPerRun"]):
            raise ValueError("SOURCE_DEVELOPMENT_PROVENANCE_BLOCKER")
        for relative, expected in metadata["contentSha256"].items():
            path = folder / relative
            if not path.resolve().is_relative_to(folder.resolve()) or sha(path) != expected:
                raise ValueError("SOURCE_DEVELOPMENT_PROVENANCE_BLOCKER")
            count += 1
    return count


def audit_result_seals(root: Path) -> dict:
    """Read filenames and metadata only, never result/performance payloads."""
    research = root / "reports/research"
    metadata_by_dir = {}
    for path in sorted(research.rglob("metadata.json")):
        metadata = _json(path)
        if (metadata.get("phase") != "DEVELOPMENT"
                or metadata.get("validation", metadata.get("validation_access")) != "SEALED"
                or metadata.get("finalOos", metadata.get("final_oos_access")) != "SEALED"
                or any(metadata.get(key) is True for key in (
                    "validationOpened", "validationPerformanceRead", "validationResultsGenerated",
                    "finalOosPerformanceRead", "validation_metrics_viewed", "oos_metrics_viewed"))):
            raise PermissionError("SEALED_RESULT_METADATA_BLOCKER")
        metadata_by_dir[path.parent] = metadata
    performance_names = {"predictions.csv", "per_date_predictions.csv", "per_date_metrics.csv",
                         "aggregate_metrics.json", "candidate_summary.json", "coefficients.csv"}
    for path in sorted(research.rglob("*")):
        relative = str(path.relative_to(research)).lower()
        if any(word in relative for word in ("validation", "final_oos", "finaloos")):
            raise PermissionError("SEALED_RESULT_PATH_BLOCKER")
        if path.is_file() and path.name in performance_names:
            if not any(parent in metadata_by_dir for parent in path.parents):
                raise PermissionError("UNOWNED_RESULT_FILE_BLOCKER")
    return {"sealedResultMetadataFilesChecked": len(metadata_by_dir), "sealedResultPathsAbsent": True}


def _calendar(dates) -> pd.DatetimeIndex:
    calendar = pd.DatetimeIndex(dates)
    if (calendar.empty or calendar.hasnans or calendar.tz is not None
            or calendar.has_duplicates or not calendar.is_monotonic_increasing
            or not calendar.equals(calendar.normalize())):
        raise ValueError("READINESS_CALENDAR_INTEGRITY_BLOCKER")
    return calendar


def calculate_readiness(*, calendar, ordinal_dates: dict[int, str], structural_dates,
                        cutoff: str, calendar_verified: bool,
                        snapshot_id_value: str, identities: dict | None = None,
                        parent_snapshot_id_value: str | None = None) -> dict:
    """Pure endpoint availability, NOT target values or authorization to open.

    Ordinals must come from the formal structural eligible calendar, not a
    weekday projection. This function also exposes partial horizon maturity
    for synthetic contracts; missing formal dates stay null in live output.
    """
    cal = _calendar(calendar)
    boundary = pd.Timestamp(cutoff)
    if pd.isna(boundary) or boundary.tz is not None or boundary != boundary.normalize():
        raise ValueError("READINESS_CUTOFF_BLOCKER")
    if not isinstance(calendar_verified, bool):
        raise TypeError("explicit calendar verification required")
    identity = dict(IDENTITIES if identities is None else identities)
    if identity != IDENTITIES:
        raise ValueError("VALIDATION_FROZEN_IDENTITY_DRIFT_BLOCKER")
    # Placeholders after the verified data cutoff are never usable sessions.
    observed = cal[cal <= boundary]
    structural = set(map(pd.Timestamp, structural_dates))
    supplied = {key: pd.Timestamp(day) for key, day in ordinal_dates.items()}
    if (any(isinstance(key, bool) or not isinstance(key, int) or not 1 <= key <= 460 for key in supplied)
            or any(pd.isna(day) or day.tz is not None or day != day.normalize() for day in supplied.values())
            or len(set(supplied.values())) != len(supplied)
            or list(sorted(supplied.values())) != [supplied[k] for k in sorted(supplied)]):
        raise ValueError("READINESS_ORDINAL_IDENTITY_BLOCKER")
    rows = []
    for ordinal in range(221, 281):
        signal = supplied.get(ordinal)
        ends, matured = {}, {}
        reasons = []
        if not calendar_verified:
            reasons.append("UNVERIFIED_OFFICIAL_TRADING_CALENDAR")
        if signal is None:
            reasons.append("FORMAL_ELIGIBLE_DATE_NOT_YET_AVAILABLE")
        elif signal not in observed:
            reasons.append("SIGNAL_SESSION_NOT_AVAILABLE_AT_CUTOFF")
        if signal is not None and signal not in structural:
            reasons.append("FORMAL_STRUCTURAL_ELIGIBILITY_NOT_MET")
        position = int(observed.get_loc(signal)) if signal in observed and calendar_verified else None
        for horizon in HORIZONS:
            end = observed[position + horizon] if position is not None and position + horizon < len(observed) else None
            ends[str(horizon)] = str(end.date()) if end is not None else None
            matured[str(horizon)] = end is not None
            if not matured[str(horizon)]:
                reasons.append(f"H{horizon}_ENDPOINT_UNAVAILABLE")
        ready = not reasons and all(matured.values())
        rows.append({"ordinal": ordinal, "signalDate": str(signal.date()) if signal is not None else None,
                     "labelEnds": ends, "horizonMatured": matured, "structuralEligible": signal in structural,
                     "allHorizonsMatured": all(matured.values()),
                     "structuralDataReady": calendar_verified and signal in observed and signal in structural,
                     "overallReady": ready, "ready": ready, "reasonCodes": reasons})
    ready_count = sum(row["ready"] for row in rows)
    reasons = Counter(reason for row in rows for reason in row["reasonCodes"])
    required = rows[-1]["labelEnds"]["120"] if ready_count == 60 else None
    return {"schemaVersion": 1, "researchType": "F1_VALIDATION_READINESS_V1", "performanceEvaluation": False,
            **identity, "snapshotId": snapshot_id_value, "cutoff": cutoff,
            "parentSnapshotId": parent_snapshot_id_value or snapshot_id_value,
            "latestSourceCutoff": cutoff, "sourceCutoff": cutoff,
            "readyCount": ready_count, "notReadyCount": 60 - ready_count,
            "total": 60,
            "ready": ready_count, "required": 60, "notReady": 60 - ready_count,
            "readinessStatus": "READY_FOR_HUMAN_REVIEW" if ready_count == 60 else "VALIDATION_NOT_READY",
            "fullValidationReadiness": ready_count == 60,
            "fullValidationReadinessGate": "PASS" if ready_count == 60 else "FAIL",
            "remainingReasons": dict(sorted(reasons.items())), "ordinals": rows,
            "perObservationReadiness": rows, "observations": rows, "finalOosRead": False,
            "fullReadinessLabelEnd": required, "nextFullReadinessDate": None,
            "nextFullReadinessDateReason": "NO_VERIFIED_FUTURE_CALENDAR_PROJECTION",
            "calendarVerified": calendar_verified, "validationOpeningAuthorized": False,
            "nextSafeAction": "HUMAN_REVIEW_REQUIRED_BEFORE_FORMAL_VALIDATION_OPEN" if ready_count == 60
                else "WAIT_FOR_MORE_LEGALLY_AVAILABLE_APPEND_ONLY_DATA", **SEAL}


def assert_monotonic(previous: dict, current: dict) -> None:
    for key, value in IDENTITIES.items():
        if previous.get(key) != value or current.get(key) != value:
            raise ValueError("VALIDATION_FROZEN_IDENTITY_DRIFT_BLOCKER")
    for record in (previous, current):
        if any(record.get(k) != v for k, v in SEAL.items()):
            raise PermissionError("VALIDATION_SEAL_STATE_BLOCKER")
        if [row["ordinal"] for row in record["ordinals"]] != list(range(221, 281)):
            raise ValueError("READINESS_ORDINAL_IDENTITY_BLOCKER")
        if record["ready"] != sum(row["ready"] for row in record["ordinals"]):
            raise ValueError("READINESS_COUNT_BLOCKER")
    if pd.Timestamp(current["cutoff"]) < pd.Timestamp(previous["cutoff"]):
        raise ValueError("READINESS_CUTOFF_REGRESSION_BLOCKER")
    for old, new in zip(previous["ordinals"], current["ordinals"]):
        if old["signalDate"] is not None and old["signalDate"] != new["signalDate"]:
            raise ValueError("READINESS_ORDINAL_IDENTITY_BLOCKER")
        if old["ready"] and not new["ready"]:
            raise ValueError("READINESS_REGRESSION_BLOCKER")
        for horizon in HORIZONS:
            key = str(horizon)
            if (old["labelEnds"][key] is not None and old["labelEnds"][key] != new["labelEnds"][key]):
                raise ValueError("READINESS_ENDPOINT_IDENTITY_BLOCKER")
    # This is only monotonicity, not proof of append lineage; never authorizes I/O.


def formal_eligible_dates(projection: pd.DataFrame, codes: list[str], *, start: str, end: str):
    """Date/quality-only equivalent of sector_index_baseline.audit_signal_range.

    Conservatively preserve its 120 warmup, six calendar months / 30 training
    dates, per-horizon purge and full-U0 validity through the H120 endpoint.
    No factor computation, target construction or model import occurs.
    """
    if (list(projection.columns) != ["date", "sector_code", "is_valid_ohlc"] or projection.empty
            or projection.duplicated(["date", "sector_code"]).any()
            or set(projection["sector_code"]) != set(codes)
            or projection["is_valid_ohlc"].dtype != bool):
        raise ValueError("STRUCTURAL_CALENDAR_INPUT_BLOCKER")
    frame = projection.loc[projection["date"].between(pd.Timestamp(start), pd.Timestamp(end))]
    calendar = _calendar(sorted(frame["date"].unique()))
    if str(calendar[0].date()) != start or str(calendar[-1].date()) != end:
        raise ValueError("STRUCTURAL_CALENDAR_RANGE_BLOCKER")
    grouped = frame.groupby("date").agg(observed=("sector_code", "nunique"), valid=("is_valid_ohlc", "sum"))
    full = grouped["observed"].eq(len(codes)) & grouped["valid"].eq(len(codes))
    bad = [0]
    for valid in full:
        bad.append(bad[-1] + int(not valid))
    eligible = []
    for i, day in enumerate(calendar):
        if i + 120 >= len(calendar):
            continue
        starts = []
        for h in HORIZONS:
            cutoff_i = i - h
            if cutoff_i < 0:
                break
            train_i = int(calendar.searchsorted(calendar[cutoff_i] - pd.DateOffset(months=6)))
            if cutoff_i - train_i + 1 < 30:
                break
            starts.append(train_i)
        if len(starts) != 3 or min(starts) < 120:
            continue
        if bad[i + 121] == bad[min(starts) - 120]:
            eligible.append(i)
    if eligible and eligible != list(range(eligible[0], eligible[-1] + 1)):
        raise ValueError("SPLIT_REPRODUCIBILITY_REVIEW: disjoint eligible calendar")
    return calendar, [str(calendar[i].date()) for i in eligible]


def inspect_parent(root: Path = ROOT) -> tuple[dict, dict]:
    """Strict parent-v1 audit. Unknown future snapshots fail closed.

    Future acceptance requires a real updater and reviewed lineage verifier;
    this version does not assume that changed metadata proves a valid append.
    """
    config, split = frozen_identity(root)
    seals = audit_result_seals(root)
    source_files = source_development_identity(root, config)
    processed = root / "data/processed/shenwan"
    admission_path = processed / "sector_admission.json"
    admission = _json(admission_path)
    policy = config["dataSnapshotPolicy"]
    if (admission["data_snapshot_id"] != PARENT_SNAPSHOT or admission["latest_date"] != PARENT_CUTOFF
            or sha(admission_path) != policy["sourceAdmissionSha256"]):
        raise ValueError("APPEND_ONLY_LINEAGE_REVIEW_REQUIRED_BLOCKER")
    verified = {}
    for name, expected in admission["canonical_hashes"].items():
        if Path(name).name != name:
            raise ValueError("MANIFEST_PATH_BLOCKER")
        actual = sha(processed / name)
        if actual != expected:
            raise ValueError(f"HISTORICAL_DATA_REVISION_BLOCKER: {name}")
        verified[name] = actual
    if verified["sector_ohlcva.csv"] != PARENT_MARKET_SHA:
        raise ValueError("HISTORICAL_DATA_REVISION_BLOCKER")
    manifest_path = root / "data/manifests/shenwan_sector_history_manifest.json"
    manifest = _json(manifest_path)
    raw_verified = {}
    for name, expected in admission["raw_fingerprints"].items():
        path = manifest_path if name == "sector_history_manifest.json" else root / "data/raw/shenwan" / name
        allowed = (root / "data/raw/shenwan").resolve()
        if name != "sector_history_manifest.json" and not path.resolve().is_relative_to(allowed):
            raise ValueError("MANIFEST_PATH_BLOCKER")
        if sha(path) != expected:
            raise ValueError(f"RAW_SOURCE_REVISION_BLOCKER: {name}")
        raw_verified[name] = expected
    if snapshot_id(raw_verified, code_fingerprints=admission["code_fingerprints"]) != PARENT_SNAPSHOT:
        raise ValueError("PARENT_SNAPSHOT_IDENTITY_BLOCKER")
    # Code fingerprints are checked too, not merely trusted from metadata.
    code_paths = {"admit_shenwan_sector.py": "scripts/data/admit_shenwan_sector.py",
                  "shenwan_official.py": "src/data/providers/shenwan_official.py",
                  "shenwan_sector.py": "src/data/providers/shenwan_sector.py",
                  "shenwan_sector_admission.py": "src/data/providers/shenwan_sector_admission.py"}
    if set(admission["code_fingerprints"]) != set(code_paths):
        raise ValueError("PARSER_IDENTITY_BLOCKER")
    for name, relative in code_paths.items():
        if sha(root / relative) != admission["code_fingerprints"][name]:
            raise ValueError("PARSER_IDENTITY_BLOCKER")
    market = processed / "sector_ohlcva.csv"
    with market.open(encoding="utf-8", newline="") as stream:
        columns = next(csv.reader(stream))
    if columns != list(OHLCVA_COLUMNS):
        raise ValueError("SCHEMA_DRIFT_BLOCKER")
    codes = sorted(pd.read_csv(processed / "sector_catalog.csv", usecols=["sector_code"], dtype=str)["sector_code"])
    if len(codes) != 124 or len(set(codes)) != 124 or semantic_hash(codes) != policy["codesSha256"]:
        raise ValueError("U0_IDENTITY_BLOCKER")
    if (manifest.get("provider") != PROVIDER or manifest.get("endpoint") != ENDPOINT
            or manifest.get("period") != "DAY" or manifest.get("sector_count") != 124
            or {row["sector_code"] for row in manifest["files"]} != set(codes)
            or len(manifest["files"]) != 124
            or {row["end_date"] for row in manifest["files"]} != {PARENT_CUTOFF}):
        raise ValueError("SOURCE_OR_MANIFEST_IDENTITY_BLOCKER")
    projection = pd.read_csv(market, usecols=["date", "sector_code", "is_valid_ohlc"],
        dtype={"sector_code": str, "is_valid_ohlc": bool}, parse_dates=["date"])
    if (len(projection) != manifest["total_rows"] or projection["date"].isna().any()
            or projection["date"].max() != pd.Timestamp(PARENT_CUTOFF)):
        raise ValueError("PARENT_ROWS_OR_CUTOFF_BLOCKER")
    calendar, eligible = formal_eligible_dates(projection, codes,
        start=admission["common_start_date"], end=admission["common_end_date"])
    if (len(eligible) < 239 or semantic_hash(eligible[:239]) != split["frozenPrefixSha256"]
            or any(eligible[int(k) - 1] != v for k, v in split["knownDateByOrdinal"].items())):
        raise ValueError("SPLIT_REPRODUCIBILITY_REVIEW")
    readiness = calculate_readiness(calendar=calendar,
        ordinal_dates={i + 1: day for i, day in enumerate(eligible[:460])}, structural_dates=eligible,
        cutoff=PARENT_CUTOFF, calendar_verified=True, snapshot_id_value=PARENT_SNAPSHOT)
    if readiness["ready"] != 19:
        raise ValueError("READINESS_BASELINE_REPRODUCTION_BLOCKER")
    common = projection.loc[projection["date"].between(calendar[0], calendar[-1])]
    missing = calendar.difference(common.loc[common["sector_code"].eq("801193"), "date"])
    invalid = projection.loc[~projection["is_valid_ohlc"], ["date", "sector_code"]]
    if len(invalid) != 20 or len(missing) != 336 or str(missing[-1].date()) != "2023-09-26":
        raise ValueError("KNOWN_ANOMALY_IDENTITY_BLOCKER")
    per = projection.groupby("sector_code")["date"].agg(["count", "min", "max"])
    pre = {"schemaVersion": 1, "parentSnapshotId": PARENT_SNAPSHOT, "oldCutoff": PARENT_CUTOFF,
        "provider": PROVIDER, "endpoint": ENDPOINT, "calendarSource": admission["calendar_source"],
        "adjustment": "OFFICIAL_INDEX_VALUES_UNTRANSFORMED", "volumeUnit": None, "amountUnit": None,
        "classificationVersion": admission["classification_version"], "strictPit": False,
        "historicalIndexRecalculationPolicy": admission["historical_index_recalculation_policy"],
        "u0Hash": semantic_hash(codes), "sectorCount": len(codes), "columns": columns,
        "schemaHash": semantic_hash({"version": admission["schema_version"], "columns": columns}),
        "rowCount": len(projection), "perSector": {
            code: {"rows": int(per.loc[code, "count"]), "firstDate": str(per.loc[code, "min"].date()),
                   "lastDate": str(per.loc[code, "max"].date())} for code in codes},
        "canonicalFilesSha256": {**verified, "sector_admission.json": sha(admission_path)},
        "rawFilesSha256": raw_verified, "codeFingerprints": admission["code_fingerprints"],
        "historicalPrefixBytesSha256": verified["sector_ohlcva.csv"],
        "historicalPrefixHashBasis": "ALL_PARENT_CSV_BYTES_ALL_ROWS_THROUGH_OLD_CUTOFF",
        "frozenEconomicHistorySha256": policy["frozenHistorySha256"],
        "economicHashCheckBasis": "EXACT_FROZEN_PARENT_FILE_SHA_NO_PRICE_VALUES_LOADED",
        "eligiblePrefixCount": 239, "eligiblePrefixSha256": semantic_hash(eligible[:239]),
        "knownAnomalies": {"invalidOhlcRows": len(invalid),
            "invalidRowKeysSha256": semantic_hash([[str(row.date.date()), row.sector_code]
                for row in invalid.itertuples(index=False)]),
            "invalidSidecarSha256": verified["sector_invalid_ohlc.csv"],
            "sector801193MissingCommonSessions": len(missing), "last801193MissingSession": str(missing[-1].date()),
            "missing801193DatesSha256": semantic_hash([str(day.date()) for day in missing])},
        "parentReadiness": {"ready": readiness["ready"], "required": 60, "notReady": readiness["notReady"]},
        "projectedColumns": list(projection.columns), "sourceRawRetrievedAt": manifest["retrieved_at"],
        "sourceDevelopmentFilesShaVerified": source_files,
        **IDENTITIES, **seals, **SEAL}
    return pre, readiness


def blocked_cycle(pre: dict, readiness: dict) -> dict:
    return {"schemaVersion": 1, "status": "PIPELINE_COMPLETE_DATA_UPDATE_BLOCKED",
            "blocker": "APPEND_ONLY_UPDATE_PATH_NOT_SAFE_BLOCKER",
            "reason": "NO_EXISTING_CANONICAL_SOURCE_FETCH_UPDATER; OFFLINE_IMPORTERS_REWRITE_FULL_TABLES_WITHOUT_OVERLAP_GUARD",
            "preUpdateManifestSha256": semantic_hash(pre), "readinessSha256": semantic_hash(readiness),
            "parentSnapshotId": pre["parentSnapshotId"], "oldCutoff": pre["oldCutoff"],
            "parentSnapshot": pre["parentSnapshotId"], "newSnapshot": None,
            "provider": pre["provider"], "updaterPath": None,
            "offlineImportersAudited": ["scripts/data/build_shenwan_catalog_and_quality.py", "scripts/data/admit_shenwan_sector.py"],
            "updateAttempted": False, "updateApplied": False, "fetchStatus": "NOT_RUN",
            "stagingStatus": "NOT_RUN", "overlapStatus": "NOT_RUN", "overlapRowsChecked": None,
            "historicalRevisions": None, "appendedRows": 0, "appendedDateRange": None,
            "historicalOverlapRowsChecked": None, "historicalRevisionCount": None,
            "oldRows": pre.get("rowCount"), "newRows": pre.get("rowCount"),
            "historicalPrefixHashBefore": pre.get("historicalPrefixBytesSha256"),
            "historicalPrefixHashAfter": pre.get("historicalPrefixBytesSha256"),
            "historicalPrefixIdentical": True, "duplicateCount": 0,
            "schemaIdentity": pre.get("schemaHash"), "U0Identity": pre.get("u0Hash"),
            "environmentChanged": False,
            "sourceLatestAvailableCutoff": None, "lastVerifiedLocalSourceCutoff": pre["oldCutoff"],
            "newSnapshotId": None, "currentSnapshotId": pre["parentSnapshotId"],
            "newCutoff": None, "currentCutoff": pre["oldCutoff"],
            "historicalPrefixUnchanged": True, "u0Unchanged": True, "knownAnomaliesPreserved": True,
            "readyBefore": readiness["ready"], "readyAfter": readiness["ready"],
            "notReadyAfter": readiness["notReady"], "readinessDelta": 0,
            "fullValidationReadiness": readiness["fullValidationReadiness"],
            "fullValidationReadinessGate": readiness["fullValidationReadinessGate"], **SEAL}
