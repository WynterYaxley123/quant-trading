"""Non-executing F1 Validation preregistration and pure synthetic contracts.

No prices/labels are loaded, no model is fit, no actual Validation training
set is built. The CLI audits identities and result metadata/filenames only.
Opening has no I/O implementation here; a future authorized runner must
persist its one-way record before accessing any Validation value.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

import pandas as pd

from research import horizon_component_replacement_v1_protocol as source_protocol
from research.sector_development_protocol import canonical_hash, PHASES, phase_for_ordinal, split_policy_hash
from strategies.sw_sector_rotation.src.common.temporal_integrity import temporal_boundaries, training_window
from strategies.sw_sector_rotation.src.model.model import DEFAULT_TRAIN_MONTHS, MIN_TRAIN_DATES

RESEARCH_TYPE = "F1_INDEPENDENT_VALIDATION_V1"
CONFIG_PATH = "research/configs/f1_independent_validation_v1.json"
CANDIDATE_PATH = "research/configs/f1_independent_validation_v1_candidate.json"
SPLIT_PATH = "research/configs/f1_independent_validation_v1_split.json"
DOCUMENT_PATH = "docs/research/shenwan_f1_independent_validation_v1.md"
TRACE_PATH = "docs/research/shenwan_f1_independent_validation_v1_selection_trace.md"
SOURCE_RESULT_COMMIT = "91b89a97a9a2b54e133d2979c695d7c3da22626e"
SOURCE_HANDOFF_COMMIT = "e388fdce6d846019b854704a1967ca0a6b12afd6"
SPLIT_POLICY_HASH = "3b6b2d754211169039439c8b377fd9eb26d5cb5db0f80d62cffc1d19c81a7038"
BLOCKS = (("VB1", 221, 240), ("VB2", 241, 260), ("VB3", 261, 280))
HORIZONS = (10, 40, 120)
FROZEN_CANDIDATE_HASH = "6c2b16555b6dfd5d848ea451b09e7b75f53da67747fc76fd052d93afd3ea156b"
FROZEN_PHASE_HASH = "28d3980e28b41b37d2a327aad6081e8312cf66d66762c13e33cc8ba814c8fa7f"
FROZEN_CONFIG_HASH = "39c603097c2cf49e61b610407dc0a7609a6b14426a125ead556ac9ed1008c9d8"
FROZEN_PROTOCOL_HASH = "2344cc685201476de957109b9fccc2681923e2c4591b5ed91740a56baf128410"


def _root(root: Path | None = None) -> Path:
    return Path(root) if root is not None else Path(__file__).resolve().parents[1]


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_definition_hash(root: Path | None = None) -> str:
    return canonical_hash(_json(_root(root) / CANDIDATE_PATH))


def validation_phase_definition_hash(root: Path | None = None) -> str:
    return canonical_hash(_json(_root(root) / SPLIT_PATH))


def _self_hash() -> str:
    source = Path(__file__).read_bytes()
    for name in ("FROZEN_CANDIDATE_HASH", "FROZEN_PHASE_HASH", "FROZEN_CONFIG_HASH", "FROZEN_PROTOCOL_HASH"):
        source, count = re.subn(
            rb"^" + name.encode() + rb' = "(?:[0-9a-f]{64}|<PENDING>)"$',
            name.encode() + b' = "<SELF>"', source, flags=re.MULTILINE,
        )
        if count != 1:
            raise ValueError("VALIDATION_PROTOCOL_IDENTITY_BLOCKER")
    return hashlib.sha256(source).hexdigest()


def protocol_payload(root: Path | None = None) -> dict:
    repo = _root(root)
    return {
        "researchType": RESEARCH_TYPE,
        "phase": "PREREGISTERED",
        "config": _json(repo / CONFIG_PATH),
        "candidate": _json(repo / CANDIDATE_PATH),
        "split": _json(repo / SPLIT_PATH),
        "documents": {p: _sha(repo / p) for p in (DOCUMENT_PATH, TRACE_PATH)},
        "protocolModuleIdentity": _self_hash(),
        "constants": {"sourceResultCommit": SOURCE_RESULT_COMMIT,
                      "sourceHandoffCommit": SOURCE_HANDOFF_COMMIT,
                      "splitPolicyHash": SPLIT_POLICY_HASH,
                      "blocks": [list(b) for b in BLOCKS], "horizons": list(HORIZONS)},
    }


def protocol_hash(root: Path | None = None) -> str:
    return canonical_hash(protocol_payload(root))


def verify_protocol(root: Path | None = None) -> dict:
    repo = _root(root)
    payload = protocol_payload(repo)
    config, candidate, split = (payload[k] for k in ("config", "candidate", "split"))
    if (canonical_hash(config) != FROZEN_CONFIG_HASH
            or canonical_hash(candidate) != FROZEN_CANDIDATE_HASH
            or canonical_hash(split) != FROZEN_PHASE_HASH
            or canonical_hash(payload) != FROZEN_PROTOCOL_HASH
            or config["candidateDefinitionHash"] != FROZEN_CANDIDATE_HASH
            or config["validationPhaseDefinitionHash"] != FROZEN_PHASE_HASH):
        raise ValueError("VALIDATION_PREREGISTRATION_SEMANTIC_CONFLICT_BLOCKER")
    source_protocol.verify_protocol(repo)
    source = source_protocol.load_config(repo)
    for role, original in (("candidate", "F1_H10_REPLACEMENT"), ("control", "F0_CONTROL")):
        definition = candidate[role]
        if (definition["sourceCandidateId"] != original
                or definition["components"] != source["componentMappings"][original]):
            raise ValueError("F1_CANDIDATE_DRIFT_BLOCKER")
        for horizon, component in definition["components"].items():
            if definition["factors"][horizon] != source["factorLists"][component]:
                raise ValueError("F1_CANDIDATE_DRIFT_BLOCKER")
    if (split_policy_hash() != SPLIT_POLICY_HASH
            or split["phases"] != [{"phase": p, "start": s, "end": e} for p, s, e in PHASES]
            or split["blocks"] != derive_validation_blocks()
            or split["validationOrdinalIds"] != list(range(221, 281))
            or DEFAULT_TRAIN_MONTHS != 6 or MIN_TRAIN_DATES != 30):
        raise ValueError("VALIDATION_PREREGISTRATION_SEMANTIC_CONFLICT_BLOCKER")
    for path, expected in config["sourceFileSha256"].items():
        if _sha(repo / path) != expected:
            raise ValueError(f"F1_CANDIDATE_DRIFT_BLOCKER: {path}")
    assert_preregistration_seal(config["seal"])
    return payload


def derive_validation_blocks() -> list[dict]:
    _, first, last = next(p for p in PHASES if p[0] == "validation")
    if last - first + 1 != 60:
        raise ValueError("VALIDATION_SPLIT_POLICY_BLOCKER")
    return [{"id": f"VB{i + 1}", "first": first + 20 * i,
             "last": first + 20 * (i + 1) - 1} for i in range(3)]


def assert_preregistration_seal(record: dict) -> None:
    expected = {"validation": "SEALED", "finalOos": "SEALED", "validationState": "UNSEEN",
                "validationOpened": False, "validationFirstOpenedAt": None,
                "validationPerformanceRead": False, "validationResultsGenerated": False,
                "finalOosPerformanceRead": False}
    if record != expected:
        raise PermissionError("VALIDATION_SEAL_STATE_BLOCKER")


def _calendar(dates) -> pd.DatetimeIndex:
    cal = pd.DatetimeIndex(dates)
    if (cal.empty or cal.hasnans or cal.tz is not None
            or not cal.equals(cal.normalize()) or cal.has_duplicates
            or not cal.is_monotonic_increasing):
        raise ValueError("VALIDATION_CALENDAR_INTEGRITY_BLOCKER")
    return cal


def _training_context(calendar, eligible_calendar, signal_date, horizon):
    if isinstance(horizon, bool) or horizon not in HORIZONS:
        raise ValueError("VALIDATION_HORIZON_BLOCKER")
    cal, eligible = _calendar(calendar), _calendar(eligible_calendar)
    signal = pd.Timestamp(signal_date)
    if not eligible.isin(cal).all() or signal not in eligible:
        raise ValueError("VALIDATION_CALENDAR_INTEGRITY_BLOCKER")
    ordinal = int(eligible.get_loc(signal)) + 1
    if phase_for_ordinal(ordinal) != "validation":
        raise PermissionError("VALIDATION_EVALUATION_PHASE_BLOCKER")
    position = int(cal.get_loc(signal))
    boundary = temporal_boundaries(cal[:position + 1], signal, horizon, DEFAULT_TRAIN_MONTHS)
    if boundary is None:
        raise ValueError("VALIDATION_LEGAL_LABEL_WINDOW_BLOCKER")
    return cal, eligible, signal, position, boundary


def training_source_admission(*, calendar, eligible_calendar, signal_date,
                              observation_date, horizon: int,
                              valid_target: bool, valid_features: bool) -> dict:
    """Pure phase/date mask; caller validity comes from the frozen pipeline.

    Does not fetch or validate actual target values. Minimum-30 applies to
    the assembled dates, not to this individual-source predicate.
    """
    cal, eligible, signal, signal_i, boundary = _training_context(
        calendar, eligible_calendar, signal_date, horizon)
    origin = pd.Timestamp(observation_date)
    if not isinstance(valid_target, bool) or not isinstance(valid_features, bool):
        raise TypeError("explicit frozen-pipeline validity flags are required")
    if origin not in cal:
        raise ValueError("VALIDATION_CALENDAR_INTEGRITY_BLOCKER")
    origin_i = int(cal.get_loc(origin))
    phase = phase_for_ordinal(int(eligible.get_loc(origin)) + 1) if origin in eligible else (
        "pre_development" if origin < eligible[0] else "unassigned")
    end_i = origin_i + horizon
    label_end = cal[end_i] if end_i < len(cal) else None
    if origin >= signal:
        reason = "NOT_STRICTLY_HISTORICAL"
    elif label_end is None or end_i > signal_i or origin > boundary.label_cutoff:
        reason = "UNMATURED_LABEL"
    elif phase not in {"pre_development", "development", "purge_1", "validation"}:
        reason = "PHASE_NOT_TRAINING_ADMITTED"
    elif not boundary.train_start <= origin <= boundary.label_cutoff:
        reason = "OUTSIDE_ROLLING_WINDOW"
    elif not valid_target:
        reason = "INVALID_TARGET"
    elif not valid_features:
        reason = "INVALID_FEATURES"
    else:
        reason = None
    return {"accepted": reason is None, "reason": reason, "sourcePhase": phase,
            "observationDate": str(origin.date()),
            "labelEnd": str(label_end.date()) if label_end is not None else None}


def training_audit_contract_fixture(*, calendar, eligible_calendar, signal_date,
                                    horizon: int, observation_dates,
                                    valid_target_dates, valid_feature_dates) -> dict:
    """Pure dates/validity contract for synthetic fixtures and future audits.

    No I/O, target values or model. Preregistration must never call this with
    real Validation origins. Future actual audit must independently recheck
    validity, fixed-U0 row coverage and resulting training data.
    """
    cal, eligible, signal, _, boundary = _training_context(
        calendar, eligible_calendar, signal_date, horizon)
    dates = _calendar(observation_dates)
    targets = {pd.Timestamp(d) for d in valid_target_dates}
    features = {pd.Timestamp(d) for d in valid_feature_dates}
    checks = [training_source_admission(
        calendar=cal, eligible_calendar=eligible, signal_date=signal,
        observation_date=d, horizon=horizon, valid_target=d in targets,
        valid_features=d in features) for d in dates]
    legal = [pd.Timestamp(c["observationDate"]) for c in checks if c["accepted"]]
    accepted = training_window(legal, boundary, MIN_TRAIN_DATES)
    accepted_set = set(accepted)
    mapping = {"pre_development": "preDevelopment", "development": "development",
               "purge_1": "purge1", "validation": "earlierValidation"}
    counts = Counter(mapping[c["sourcePhase"]] for c in checks
                     if pd.Timestamp(c["observationDate"]) in accepted_set)
    ends = [pd.Timestamp(c["labelEnd"]) for c in checks
            if pd.Timestamp(c["observationDate"]) in accepted_set]
    return {"signalDate": str(signal.date()), "horizon": horizon,
            "trainingWindowStart": str(boundary.train_start.date()),
            "trainingWindowEnd": str(boundary.label_cutoff.date()),
            "candidateTrainingDates": [str(d.date()) for d in dates],
            "acceptedTrainingDates": [str(d.date()) for d in accepted],
            "acceptedTrainingDateCount": len(accepted),
            "legalDateCountBeforeMinimum": len(legal),
            "rejectedUnmaturedCount": sum(c["reason"] == "UNMATURED_LABEL" for c in checks),
            "rejectedFutureOriginCount": sum(c["reason"] == "NOT_STRICTLY_HISTORICAL" for c in checks),
            "latestAcceptedTrainingDate": str(accepted[-1].date()) if accepted else None,
            "latestAcceptedLabelEndDate": str(max(ends).date()) if ends else None,
            "phaseSourceCounts": {v: counts[v] for v in mapping.values()},
            "futureLeakCount": sum(d >= signal or e > signal for d, e in zip(accepted, ends)),
            "status": "ELIGIBLE" if accepted else "INSUFFICIENT_TRAINING_DATA"}


def validate_opening_transition(previous: dict, proposed: dict, *,
                                explicit_authorization: bool = False,
                                root: Path | None = None) -> None:
    """Validate an external future one-way audit record; never writes/opens."""
    config = verify_protocol(root)["config"]
    if previous.get("validationOpened") is True:
        validate_opening_transition(config["seal"], previous,
                                    explicit_authorization=True, root=root)
        if (previous.get("validationState") != "OBSERVED"
                or any(proposed.get(k) != previous.get(k)
                       for k in config["futureOpening"]["requiredFields"])):
            raise PermissionError("OBSERVED_VALIDATION_CANNOT_RESET_OR_REWRITE_OPENING")
        return
    assert_preregistration_seal(previous)
    if explicit_authorization is not True:
        raise PermissionError("EXPLICIT_VALIDATION_AUTHORIZATION_REQUIRED")
    expected = {"validationOpened": True, "validationState": "OBSERVED",
                "validationProtocolHash": FROZEN_PROTOCOL_HASH,
                "candidateDefinitionHash": FROZEN_CANDIDATE_HASH,
                "validationPhaseDefinitionHash": FROZEN_PHASE_HASH,
                "splitPolicyHash": SPLIT_POLICY_HASH,
                "candidateSourceCommit": SOURCE_RESULT_COMMIT, "finalOos": "SEALED"}
    if any(proposed.get(k) != v for k, v in expected.items()):
        raise ValueError("VALIDATION_OPENING_AUDIT_IDENTITY_BLOCKER")
    if not re.fullmatch(r"[0-9a-f]{40}", proposed.get("executionGitCommit", "")):
        raise ValueError("VALIDATION_OPENING_AUDIT_IDENTITY_BLOCKER")
    try:
        timestamp = datetime.fromisoformat(proposed["validationFirstOpenedAt"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("VALIDATION_OPENING_TIMESTAMP_BLOCKER") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
        raise ValueError("VALIDATION_OPENING_TIMESTAMP_BLOCKER")


def guard_validation_evaluation(phase: str, ordinals, record: dict, *,
                                explicit_authorization: bool = False,
                                root: Path | None = None) -> None:
    """Output guard for a separately authorized future runner, not a runner."""
    if phase != "validation":
        raise PermissionError("FINAL_OOS_AND_OTHER_PHASES_INACCESSIBLE")
    if (explicit_authorization is not True or record.get("validationOpened") is not True
            or record.get("validationState") != "OBSERVED" or record.get("finalOos") != "SEALED"):
        raise PermissionError("EXPLICIT_VALIDATION_OPENING_REQUIRED")
    if not ordinals or any(type(n) is not int or not 221 <= n <= 280 for n in ordinals):
        raise PermissionError("PURGE_AND_NON_VALIDATION_EVALUATION_FORBIDDEN")
    if len(ordinals) != len(set(ordinals)):
        raise ValueError("VALIDATION_EVALUATION_DUPLICATE_ORDINAL")
    validate_opening_transition(verify_protocol(root)["config"]["seal"], record,
                                explicit_authorization=True, root=root)


def _finite(value) -> float:
    if isinstance(value, bool) or value is None or not math.isfinite(float(value)):
        raise ValueError("VALIDATION_REQUIRED_METRIC_INCOMPLETE")
    return float(value)


def validation_decision(*, v1_rankic, v1_spread, v0_rankic, v0_spread,
                        rankic_by_horizon: dict, block_rankic: dict) -> dict:
    """Pure frozen gate stack; tests use synthetic numbers, never live results."""
    wr, ws, cr, cs = map(_finite, (v1_rankic, v1_spread, v0_rankic, v0_spread))
    if set(rankic_by_horizon) != set(HORIZONS) or set(block_rankic) != {b[0] for b in BLOCKS}:
        raise ValueError("VALIDATION_REQUIRED_METRIC_INCOMPLETE")
    horizons = {h: _finite(v) for h, v in rankic_by_horizon.items()}
    blocks = {b: _finite(v) for b, v in block_rankic.items()}
    level1 = wr > 0 and ws > 0
    relative = (wr > cr and ws >= cs) or (ws > cs and wr >= cr)
    red = any(v < -0.02 for v in horizons.values())
    temporal = sum(v > 0 for v in blocks.values()) >= 2 and sum(v < -0.02 for v in blocks.values()) <= 1
    failures = [name for name, failed in (
        ("VALIDATION_LEVEL1_FAIL", not level1), ("VALIDATION_RELATIVE_GATE_FAIL", not relative),
        ("VALIDATION_HORIZON_RED_FLAG", red), ("VALIDATION_TEMPORAL_STABILITY_FAIL", not temporal)) if failed]
    return {"status": "VALIDATION_FAIL" if failures else "VALIDATION_PASS",
            "level1Passed": level1, "relativeGatePassed": relative,
            "horizonRedFlag": red, "temporalPassed": temporal, "failureReasons": failures,
            "nextEligibleAction": "POST_VALIDATION_DEVELOPMENT" if failures else "FINAL_OOS_PREREGISTRATION_ELIGIBLE",
            "finalOos": "SEALED", "executable": False, "tradable": False}


def result_leak_scan(reports_root: Path) -> dict:
    """Live metadata/filename audit; never reads predictions, labels or metrics."""
    root = Path(reports_root)
    if not root.exists():
        return {"clean": True, "findings": [], "metadataCount": 0}
    if not root.is_dir():
        raise ValueError("VALIDATION_RESULT_SCAN_ROOT_BLOCKER")
    findings, metadata_by_dir = set(), {}
    for path in root.rglob("metadata.json"):
        try:
            meta = _json(path)
        except (ValueError, UnicodeError):
            findings.add(str(path.relative_to(root)))
            continue
        metadata_by_dir[path.parent] = meta
        phase = meta.get("phase")
        if (phase != "DEVELOPMENT"
                or meta.get("validation", meta.get("validation_access")) != "SEALED"
                or meta.get("finalOos", meta.get("final_oos_access")) != "SEALED"
                or any(meta.get(k) is True for k in (
                    "validationOpened", "validationPerformanceRead", "validationResultsGenerated",
                    "finalOosPerformanceRead", "validation_metrics_viewed", "oos_metrics_viewed"))):
            findings.add(str(path.relative_to(root)))
    performance_names = {"predictions.csv", "per_date_predictions.csv", "per_date_metrics.csv",
                         "aggregate_metrics.json", "candidate_summary.json", "coefficients.csv"}
    for path in root.rglob("*"):
        relative = str(path.relative_to(root))
        if any(s in relative.lower() for s in ("validation", "final_oos", "finaloos")):
            findings.add(relative)
        if path.is_file() and path.name in performance_names:
            owner = next((p for p in path.parents if p in metadata_by_dir), None)
            if owner is None:
                findings.add(relative)
    return {"clean": not findings, "findings": sorted(findings),
            "metadataCount": len(metadata_by_dir)}


def assert_no_validation_results(reports_root: Path) -> dict:
    result = result_leak_scan(reports_root)
    if not result["clean"]:
        raise PermissionError("VALIDATION_INDEPENDENCE_ALREADY_COMPROMISED_BLOCKER: " + repr(result["findings"]))
    return result


def preregistration_gate(root: Path | None = None, reports_root: Path | None = None) -> dict:
    """Runtime live audit, not an ordinary real-filesystem-absence unit test."""
    repo = _root(root)
    payload = verify_protocol(repo)
    config = payload["config"]
    scan = assert_no_validation_results(reports_root or repo / "reports/research")
    source = config["source"]
    git = ["git", "-c", f"safe.directory={repo.resolve()}"]
    for commit in (source["resultCommit"], source["handoffCommit"], source["implementationCommit"],
                   source["preregistrationCommit"], source["preregistrationHandoffCommit"]):
        subprocess.run(git + ["merge-base", "--is-ancestor", commit, "HEAD"], cwd=repo, check=True)
    files = 0
    for run in source["runs"]:
        folder = repo / run["path"]
        if _sha(folder / "metadata.json") != run["metadataSha256"]:
            raise ValueError("SOURCE_DEVELOPMENT_PROVENANCE_BLOCKER")
        meta = _json(folder / "metadata.json")
        if (meta["phase"] != "DEVELOPMENT" or meta["developmentIds"] != "E001-E100"
                or meta["protocolHash"] != source["protocolHash"]
                or meta["executionGitCommit"] != source["implementationCommit"]
                or meta["validation"] != "SEALED" or meta["finalOos"] != "SEALED"
                or canonical_hash(meta["contentSha256"]) != source["contentManifestHash"]
                or len(meta["contentSha256"]) != source["filesPerRun"]):
            raise ValueError("SOURCE_DEVELOPMENT_PROVENANCE_BLOCKER")
        for path, expected in meta["contentSha256"].items():
            if _sha(folder / path) != expected:
                raise ValueError("SOURCE_DEVELOPMENT_PROVENANCE_BLOCKER")
            files += 1
    # Fingerprint admission metadata only, without parsing any market values.
    if _sha(repo / "data/processed/shenwan/sector_admission.json") != config["dataSnapshotPolicy"]["sourceAdmissionSha256"]:
        raise ValueError("VALIDATION_DATA_SNAPSHOT_POLICY_BLOCKER")
    return {"status": "VALIDATION_PREREGISTRATION_GATE_PASS", "researchType": RESEARCH_TYPE,
            "candidateDefinitionHash": FROZEN_CANDIDATE_HASH, "validationPhaseDefinitionHash": FROZEN_PHASE_HASH,
            "splitPolicyHash": SPLIT_POLICY_HASH, "protocolHash": FROZEN_PROTOCOL_HASH,
            "sourceArtifactFilesVerified": files, "independence": scan, "seal": config["seal"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_root())
    parser.add_argument("--reports-root", type=Path)
    args = parser.parse_args()
    print(json.dumps(preregistration_gate(args.repo_root, args.reports_root), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
