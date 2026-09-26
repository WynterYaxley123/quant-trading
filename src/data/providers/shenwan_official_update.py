"""Strict official acquisition and transactional immutable BASE + DELTA snapshots.

The only publication boundary is current.json. The legacy canonical directory is
an immutable golden generation; readers resolve the pointer once, then verify the
entire selected generation. No evaluator/model dependency is permitted here.
"""
from __future__ import annotations

from contextlib import contextmanager
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from .shenwan_sector import (OHLCVA_COLUMNS, PARSER_VERSION, SCHEMA_VERSION,
    TRANSFORM_VERSION, _violations, audit_coverage, snapshot_id)
from .shenwan_tls import HOST, prepare_tls

PROVIDER = "shenwan_research_official"
BASE_URL = "https://www.swsresearch.com/institute-sw/api/index_publish/"
LINEAGE = "data/manifests/shenwan_sector_snapshots"
FIELDS = ("openindex", "maxindex", "minindex", "closeindex", "bargainamount", "bargainsum")
BAR_FIELDS = {"swindexcode", "bargaindate", *FIELDS, "hike", "markup"}
UPDATER_VERSION = "shenwan-official-append-only-v1"


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def semantic_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def source_url(kind: str, *, page: int = 1, code: str = "801012") -> str:
    if kind == "current":
        query = {"page": page, "page_size": 50, "indextype": "二级行业"}
    elif kind == "trend":
        query = {"swindexcode": code, "period": "DAY"}
    else:
        raise ValueError("SHENWAN_SOURCE_IDENTITY_BLOCKER: endpoint")
    return BASE_URL + kind + "/?" + urlencode(query)


def check_url(url: str, kind: str, *, code: str | None = None) -> None:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    valid = (parsed.scheme == "https" and parsed.netloc == HOST and not parsed.fragment
             and parsed.path == f"/institute-sw/api/index_publish/{kind}/")
    if kind == "trend":
        valid &= (set(query) == {"swindexcode", "period"} and query.get("period") == ["DAY"]
                  and len(query.get("swindexcode", [])) == 1
                  and bool(re.fullmatch(r"\d{6}", query.get("swindexcode", [""])[0])))
        if code is not None:
            valid &= query.get("swindexcode") == [code]
    elif kind == "current":
        valid &= (set(query) == {"page", "page_size", "indextype"}
                  and query.get("page_size") == ["50"] and query.get("indextype") == ["二级行业"]
                  and len(query.get("page", [])) == 1
                  and bool(re.fullmatch(r"[1-9]\d*", query.get("page", [""])[0])))
    else:
        valid = False
    if not valid:
        raise ValueError("SHENWAN_SOURCE_IDENTITY_BLOCKER: " + url)


def wrapper(raw: bytes, *, decimals: bool = False) -> dict:
    try:
        data = json.loads(raw, parse_float=Decimal if decimals else float,
                          parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    except (ValueError, UnicodeError) as error:
        raise ValueError("SHENWAN_OFFICIAL_SCHEMA_DRIFT_BLOCKER: JSON") from error
    if not isinstance(data, dict) or set(data) != {"code", "message", "data"} or str(data["code"]) != "200":
        raise ValueError("SHENWAN_OFFICIAL_SCHEMA_DRIFT_BLOCKER: wrapper")
    return data


def parse_trend(raw: bytes, code: str, today: str) -> dict[str, dict]:
    data = wrapper(raw, decimals=True)["data"]
    if not isinstance(data, list) or not data:
        raise ValueError("FROZEN_SECTOR_SOURCE_UNAVAILABLE_BLOCKER: empty " + code)
    rows = {}
    for source in data:
        if not isinstance(source, dict) or set(source) != BAR_FIELDS or str(source["swindexcode"]) != code:
            raise ValueError("SHENWAN_OFFICIAL_SCHEMA_DRIFT_BLOCKER: bar " + code)
        day = source["bargaindate"]
        if not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            raise ValueError("SHENWAN_OFFICIAL_SCHEMA_DRIFT_BLOCKER: date")
        if date.fromisoformat(day) > date.fromisoformat(today) or day in rows:
            raise ValueError("SHENWAN_OFFICIAL_SCHEMA_DRIFT_BLOCKER: future/duplicate date")
        for key in (*FIELDS, "hike", "markup"):
            value = source[key]
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
                    raise ValueError("SHENWAN_OFFICIAL_SCHEMA_DRIFT_BLOCKER: numeric type")
                try:
                    if not Decimal(value).is_finite(): raise InvalidOperation
                except InvalidOperation as error:
                    raise ValueError("SHENWAN_OFFICIAL_SCHEMA_DRIFT_BLOCKER: numeric") from error
        rows[day] = source
    return dict(sorted(rows.items()))


def parse_catalog(raw: bytes) -> tuple[dict[str, str], int, str | None]:
    data = wrapper(raw)["data"]
    if not isinstance(data, dict) or not {"count", "results", "next"}.issubset(data):
        raise ValueError("SHENWAN_OFFICIAL_SCHEMA_DRIFT_BLOCKER: catalog")
    names = {}
    if not isinstance(data["count"], int) or data["count"] <= 0 or not isinstance(data["results"], list):
        raise ValueError("SHENWAN_OFFICIAL_SCHEMA_DRIFT_BLOCKER: catalog count")
    for row in data["results"]:
        code, name = str(row.get("swindexcode", "")), row.get("swindexname")
        if not re.fullmatch(r"\d{6}", code) or not isinstance(name, str) or not name or code in names:
            raise ValueError("SHENWAN_OFFICIAL_SCHEMA_DRIFT_BLOCKER: catalog code/name")
        # The real frozen catalog rows contain l3..l11, not an indextype field.
        # Level identity comes from the exact authorized query, not invented data.
        names[code] = name
    return names, data["count"], data["next"]


def compare_catalog(frozen: dict, current: dict) -> dict:
    return {"currentOfficialCatalogCount": len(current), "frozenU0Count": len(frozen),
            "addedOfficialCodes": sorted(current.keys() - frozen.keys()),
            "removedOfficialCodes": sorted(frozen.keys() - current.keys()),
            "renamedCodes": [{"sectorCode": c, "oldName": frozen[c], "newName": current[c]}
                             for c in sorted(frozen.keys() & current.keys()) if frozen[c] != current[c]]}


def require_full_coverage(codes: list[str], responses: dict) -> None:
    if set(codes) != set(responses) or len(codes) != len(set(codes)):
        raise ValueError("FROZEN_SECTOR_SOURCE_UNAVAILABLE_BLOCKER: incomplete frozen U0")


def overlap_audit(old: dict, new: dict, cutoff: str) -> dict:
    old = {day: row for day, row in old.items() if day <= cutoff}
    new = {day: row for day, row in new.items() if day <= cutoff}
    missing, added = sorted(old.keys() - new.keys()), sorted(new.keys() - old.keys())
    revisions = []
    for day in sorted(old.keys() & new.keys()):
        for field in FIELDS:
            if old[day][field] != new[day][field]:
                revisions.append({"date": day, "field": field,
                                  "oldValue": str(old[day][field]), "newValue": str(new[day][field])})
    return {"overlapRowsChecked": len(old), "matchedRowsCompared": len(old.keys() & new.keys()),
            "revisionCount": len(revisions) + len(missing) + len(added),
            "fieldRevisionCount": len(revisions), "missingHistoricalRows": missing,
            "historicalGapFills": added, "fieldRevisions": revisions}


def finalized_delta(rows: dict, cutoff: str, today: str) -> tuple[list[dict], list[str]]:
    # No documented finalization condition exists for the current natural day.
    return ([row for day, row in rows.items() if cutoff < day < today],
            [day for day in rows if day > cutoff and day == today])


def quality(source: dict) -> str:
    return _violations(dict(zip(("open", "high", "low", "close", "volume", "amount"),
                                [source[field] for field in FIELDS])))


def decimal_json(rows: list[dict]) -> bytes:
    """Exact source numeric tokens; never cast high-precision Decimal through float."""
    def emit(value):
        if isinstance(value, Decimal): return str(value)
        if value is None: return "null"
        if isinstance(value, dict):
            return "{" + ",".join(json.dumps(k) + ":" + emit(v) for k, v in sorted(value.items())) + "}"
        if isinstance(value, list): return "[" + ",".join(emit(v) for v in value) + "]"
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    return (emit({"code": "200", "message": "ok", "data": rows}) + "\n").encode()


def sync_dir(folder: Path) -> None:
    if os.name != "nt":
        fd = os.open(folder, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)


def durable_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    sync_dir(path.parent)


def atomic_json(path: Path, value: dict, *, before_replace=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    durable_bytes(temp, encoded(value))
    if before_replace: before_replace()
    os.replace(temp, path)
    sync_dir(path.parent)


def safe_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve() / "data"):
        raise ValueError("MANIFEST_PATH_BLOCKER")
    return candidate


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_files(root: Path, fingerprints: dict) -> None:
    for path, digest in fingerprints.items():
        if sha(safe_path(root, path)) != digest:
            raise ValueError("HISTORICAL_DATA_REVISION_BLOCKER: " + path)


def prefix_hash(path: Path, cutoff: str) -> str:
    """Full original CSV lines, including missingness, precision and provenance."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        header = next(stream)
        digest.update(header)
        columns = next(csv.reader([header.decode()]))
        date_index = columns.index("date")
        for line in stream:
            # Frozen canonical has one physical line per CSV row; guard builders too.
            row = next(csv.reader([line.decode()]))
            if row[date_index] <= cutoff: digest.update(line)
    return digest.hexdigest()


def resolve_current(root: Path) -> Path:
    pointer = root / LINEAGE / "current.json"
    if not pointer.exists(): return root / "data/processed/shenwan"
    value = read_json(pointer)
    manifest_path = safe_path(root, value["manifestPath"])
    if sha(manifest_path) != value["manifestSha256"]:
        raise ValueError("SNAPSHOT_LINEAGE_BLOCKER: pointer hash")
    manifest = read_json(manifest_path)
    if manifest["snapshotId"] != value["snapshotId"]:
        raise ValueError("SNAPSHOT_LINEAGE_BLOCKER: pointer identity")
    return safe_path(root, manifest["processedPath"])


def read_parent(root: Path) -> dict:
    base = root / "data/processed/shenwan"
    admission = read_json(base / "sector_admission.json")
    base_id = snapshot_id(admission["raw_fingerprints"], code_fingerprints=admission["code_fingerprints"])
    if base_id != admission["data_snapshot_id"]:
        raise ValueError("SNAPSHOT_BACKWARD_COMPATIBILITY_BLOCKER")
    raw_files = {}
    for name, digest in admission["raw_fingerprints"].items():
        relative = ("data/manifests/shenwan_sector_history_manifest.json" if name == "sector_history_manifest.json"
                    else "data/raw/shenwan/" + name)
        raw_files[relative] = digest
    verify_files(root, raw_files)
    verify_files(root, {"data/processed/shenwan/" + name: digest for name, digest in admission["canonical_hashes"].items()})
    pointer = root / LINEAGE / "current.json"
    manifest = None
    if pointer.exists():
        ref = read_json(pointer)
        next_id = ref["snapshotId"]
        seen = set()
        while next_id != base_id:
            if next_id in seen or not re.fullmatch(r"[a-f0-9]{64}", next_id):
                raise ValueError("SNAPSHOT_LINEAGE_BLOCKER: cycle/id")
            seen.add(next_id)
            path = root / LINEAGE / (next_id + ".json")
            item = read_json(path)
            if manifest is None:
                if ref["manifestPath"] != str(path.relative_to(root)).replace(os.sep, "/") or sha(path) != ref["manifestSha256"]:
                    raise ValueError("SNAPSHOT_LINEAGE_BLOCKER: pointer")
                manifest = item
            if (item["snapshotId"] != next_id or item["historicalRevisionCount"] != 0
                or item["frozenU0Hash"] != semantic_hash(sorted(pd.read_csv(base / "sector_catalog.csv", dtype=str)["sector_code"]))) :
                raise ValueError("SNAPSHOT_LINEAGE_BLOCKER: snapshot/U0")
            if snapshot_id(item["rawFingerprints"], code_fingerprints=item["codeFingerprints"]) != next_id:
                raise ValueError("SNAPSHOT_LINEAGE_BLOCKER: id algorithm")
            verify_files(root, item["rawFiles"])
            verify_files(root, item["canonicalFiles"])
            parent_path = root / LINEAGE / (item["parentSnapshotId"] + ".json")
            if sha(parent_path) != item["parentManifestHash"]:
                raise ValueError("SNAPSHOT_LINEAGE_BLOCKER: parent hash")
            parent = read_json(parent_path)
            new_market = safe_path(root, item["processedPath"]) / "sector_ohlcva.csv"
            old_market = safe_path(root, parent["processedPath"]) / "sector_ohlcva.csv"
            if (item["oldCutoff"] != parent["newCutoff"] or item["newCutoff"] <= item["oldCutoff"]
                or prefix_hash(new_market, item["oldCutoff"]) != sha(old_market)
                or item["historicalPrefixHash"] != sha(old_market)):
                raise ValueError("POST_PUBLISH_PREFIX_IDENTITY_FAILURE")
            next_id = item["parentSnapshotId"]
        base_manifest = read_json(root / LINEAGE / (base_id + ".json"))
        if base_manifest["canonicalFiles"].get("data/processed/shenwan/sector_admission.json") != sha(base / "sector_admission.json"):
            raise ValueError("SNAPSHOT_LINEAGE_BLOCKER: golden base")
    processed = safe_path(root, manifest["processedPath"]) if manifest else base
    meta = read_json(processed / "sector_admission.json")
    codes = pd.read_csv(base / "sector_catalog.csv", dtype=str)
    names = dict(zip(codes["sector_code"], codes["sector_name"]))
    raw_fps = manifest["rawFingerprints"] if manifest else admission["raw_fingerprints"]
    parent = {"snapshotId": meta["data_snapshot_id"], "cutoff": meta["latest_date"],
              "rowCount": meta["total_rows"], "processed": processed, "admission": meta,
              "names": names, "rawFiles": manifest["rawFiles"] if manifest else raw_files,
              "rawFingerprints": raw_fps, "codeFingerprints": manifest["codeFingerprints"] if manifest else admission["code_fingerprints"],
              "manifest": manifest, "baseId": base_id}
    if manifest and (parent["snapshotId"] != manifest["snapshotId"] or parent["cutoff"] != manifest["newCutoff"]):
        raise ValueError("SNAPSHOT_LINEAGE_BLOCKER: admission")
    return parent


class OfficialClient:
    def __init__(self):
        self.verify, self.tls = prepare_tls()
        self.session = requests.Session()
        # Public frontend request semantics: the edge (Tengine) rejects
        # non-browser User-Agents with an empty-body HTTP 508. Only this
        # browser-compatible UA is added; no cookies, auth, or bypass.
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
        self.requests = []

    def fetch(self, kind: str, *, code: str = "801012", page: int = 1) -> tuple[bytes, dict]:
        url = source_url(kind, code=code, page=page)
        initial, chain = url, []
        for _ in range(4):
            check_url(url, kind, code=code if kind == "trend" else None)
            response = self.session.get(url, verify=self.verify, timeout=(15, 60), allow_redirects=False)
            evidence = {"url": url, "httpStatus": response.status_code, "location": response.headers.get("Location")}
            chain.append(evidence)
            self.requests.append(evidence)
            if response.is_redirect:
                target = urljoin(url, response.headers.get("Location", ""))
                check_url(target, kind, code=code if kind == "trend" else None)
                if parse_qs(urlparse(target).query) != parse_qs(urlparse(initial).query):
                    raise ValueError("SHENWAN_SOURCE_IDENTITY_BLOCKER: redirect query")
                url = target
                continue
            if response.status_code != 200:
                raise ValueError(f"OFFICIAL_ENDPOINT_BLOCKED: HTTP {response.status_code} {url}")
            return response.content, {"sourceUrl": initial, "redirectChain": chain, "fetchedAt": now(),
                                      "responseHash": hashlib.sha256(response.content).hexdigest()}
        raise ValueError("SHENWAN_SOURCE_IDENTITY_BLOCKER: redirect limit")

    def catalog(self) -> tuple[dict, list[dict]]:
        names, evidence, count = {}, [], None
        for page in range(1, 101):
            raw, trace = self.fetch("current", page=page)
            part, expected, advertised = parse_catalog(raw)
            if (count is not None and expected != count) or names.keys() & part.keys():
                raise ValueError("SHENWAN_OFFICIAL_SCHEMA_DRIFT_BLOCKER: pagination")
            count = expected
            names.update(part)
            evidence.append({**trace, "advertisedNextNotFollowed": advertised})
            if len(names) == count: return names, evidence
            if not part or len(names) > count:
                break
            # Construct the next HTTPS authorized endpoint, never follow HTTP next.
        raise ValueError("SHENWAN_OFFICIAL_SCHEMA_DRIFT_BLOCKER: catalog incomplete")


def probe(client: OfficialClient, parent: dict) -> dict:
    health = {"schemaVersion": 1, "provider": PROVIDER, "sourceHost": HOST,
              "catalogEndpoint": source_url("current"), "trendEndpoint": source_url("trend"),
              **client.tls, "sourceReachable": False, "schemaCompatible": None,
              "sourceIdentity": "NOT_RUN", "frozenSectorCoverage": None,
              "latestFinalizedSourceDate": None, "validationOpened": False}
    errors = []
    try:
        names, evidence = client.catalog()
        health.update(catalogStatus="PASS", catalogSchemaStatus="PASS",
                      catalogAudit=compare_catalog(parent["names"], names), catalogRequests=evidence)
    except (ValueError, requests.RequestException) as error:
        health.update(catalogStatus="FAIL", catalogSchemaStatus="FAIL" if "SCHEMA_DRIFT" in str(error) else "NOT_RUN")
        errors.append(str(error))
    try:
        raw, evidence = client.fetch("trend", code="801012")
        rows = parse_trend(raw, "801012", now()[:10])
        dates = [day for day in rows if day < now()[:10]]
        health.update(trendStatus="PASS", trendSchemaStatus="PASS", trendRequest=evidence, trendSchema=sorted(BAR_FIELDS),
                      representativeSector="801012", representativeRows=len(rows),
                      latestFinalizedSourceDate=max(dates) if dates else None)
    except (ValueError, requests.RequestException) as error:
        health.update(trendStatus="FAIL", trendSchemaStatus="FAIL" if "SCHEMA_DRIFT" in str(error) else "NOT_RUN")
        errors.append(str(error))
    health["sourceReachable"] = not errors
    schema_statuses = [health["catalogSchemaStatus"], health["trendSchemaStatus"]]
    health["schemaCompatible"] = False if "FAIL" in schema_statuses else True if not errors else None
    health["sourceIdentity"] = "FAIL" if any("SOURCE_IDENTITY" in e for e in errors) else "PASS"
    health["requests"] = client.requests.copy()
    health["errors"] = errors
    health["status"] = "PASS" if not errors else "OFFICIAL_ENDPOINT_BLOCKED"
    return health


def stage(root: Path, parent: dict, client: OfficialClient, health: dict, run_id: str) -> Path:
    if health["status"] != "PASS":
        raise ValueError("OFFICIAL_ENDPOINT_BLOCKED: health gate")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", run_id):
        raise ValueError("RUN_ID_BLOCKER")
    folder = root / "data/staging/shenwan_official" / run_id
    folder.mkdir(parents=True, exist_ok=False)
    info = {"schemaVersion": 1, "runId": run_id, "parentSnapshotId": parent["snapshotId"],
            "oldCutoff": parent["cutoff"], "fetchedAt": now(), "today": now()[:10],
            "provider": PROVIDER, "sourceHealth": health, "files": {}, "status": "FETCHING"}
    try:
        for code in sorted(parent["names"]):
            raw, evidence = client.fetch("trend", code=code)
            path = folder / (code + ".json")
            durable_bytes(path, raw)
            # Save bytes and provenance even if schema is malformed.
            info["files"][code] = evidence
            atomic_json(folder / "stage.json", info)
            parse_trend(raw, code, info["today"])
        require_full_coverage(sorted(parent["names"]), info["files"])
        info["status"] = "STAGED"
    except Exception as error:
        info.update(status="BLOCKED", blocker=str(error))
        atomic_json(folder / "stage.json", info)
        raise
    atomic_json(folder / "stage.json", info)
    return folder


def old_series(root: Path, parent: dict, code: str, today: str) -> dict:
    rows = {}
    paths = [relative for relative in parent["rawFiles"]
             if relative.endswith("/" + code + ".json")
             and ("/sector_history/" in relative or "/sector_history_append/" in relative)]
    for relative in sorted(paths, key=lambda x: ("/sector_history_append/" in x, x)):
        part = parse_trend(safe_path(root, relative).read_bytes(), code, today)
        if rows.keys() & part.keys():
            raise ValueError("SNAPSHOT_LINEAGE_BLOCKER: raw duplicate")
        rows.update(part)
    if not rows:
        raise ValueError("SNAPSHOT_LINEAGE_BLOCKER: missing base raw")
    return dict(sorted(rows.items()))


def audit_stage(root: Path, parent: dict, folder: Path) -> tuple[dict, dict]:
    if not folder.resolve().is_relative_to((root / "data/staging/shenwan_official").resolve()):
        raise ValueError("STAGING_PATH_BLOCKER")
    info = read_json(folder / "stage.json")
    if (info.get("runId") != folder.name or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", info.get("runId", ""))):
        raise ValueError("STAGING_RUN_ID_BLOCKER")
    if (info["status"] != "STAGED" or info["parentSnapshotId"] != parent["snapshotId"]
        or info["oldCutoff"] != parent["cutoff"] or info["provider"] != PROVIDER
        or info["sourceHealth"]["status"] != "PASS"):
        raise ValueError("STAGING_PARENT_OR_SOURCE_BLOCKER")
    fetched = datetime.fromisoformat(info["fetchedAt"])
    if (fetched.tzinfo is None or fetched.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat() != info["today"]
        or info["today"] > now()[:10]):
        raise ValueError("STAGING_SOURCE_TIMING_BLOCKER")
    require_full_coverage(sorted(parent["names"]), info["files"])
    if {p.stem for p in folder.glob("*.json") if p.name not in {"stage.json", "audit.json"}} != set(parent["names"]):
        raise ValueError("FROZEN_SECTOR_SOURCE_UNAVAILABLE_BLOCKER: file set")
    # Re-evaluate finality on audit/application date, conservatively keeping any
    # date excluded at fetch time excluded until a new fetch confirms it.
    today = min(info["today"], now()[:10])
    records, deltas = {}, {}
    for code in sorted(parent["names"]):
        evidence = info["files"][code]
        check_url(evidence["sourceUrl"], "trend", code=code)
        path = folder / (code + ".json")
        if sha(path) != evidence["responseHash"]:
            raise ValueError("STAGING_HASH_BLOCKER")
        new = parse_trend(path.read_bytes(), code, info["today"])
        old = old_series(root, parent, code, now()[:10])
        overlap = overlap_audit(old, new, parent["cutoff"])
        delta, excluded = finalized_delta(new, parent["cutoff"], today)
        deltas[code] = delta
        records[code] = {"sectorCode": code, **evidence, **overlap, "newRows": len(delta),
                         "newStart": delta[0]["bargaindate"] if delta else None,
                         "newEnd": delta[-1]["bargaindate"] if delta else None,
                         "excludedSessions": excluded,
                         "exclusionReason": "UNCONFIRMED_FINAL_SESSION" if excluded else None,
                         "newInvalidOhlc": sum(bool(quality(row)) for row in delta)}
    revisions = sum(record["revisionCount"] for record in records.values())
    count = sum(record["newRows"] for record in records.values())
    dates = [row["bargaindate"] for delta in deltas.values() for row in delta]
    audit = {"schemaVersion": 1, "runId": info["runId"], "provider": PROVIDER,
             "parentSnapshotId": parent["snapshotId"], "oldCutoff": parent["cutoff"],
             "newCutoff": max(dates) if dates else parent["cutoff"], "sectorCount": len(records),
             "frozenU0Hash": semantic_hash(sorted(parent["names"])), "perSector": records,
             "totalOverlapRows": sum(row["overlapRowsChecked"] for row in records.values()),
             "totalRevisions": revisions, "totalNewRows": count,
             "missingHistoricalRows": sum(len(row["missingHistoricalRows"]) for row in records.values()),
             "historicalGapFills": sum(len(row["historicalGapFills"]) for row in records.values()),
             "newInvalidOhlc": sum(row["newInvalidOhlc"] for row in records.values()),
             "appendDateRange": [min(dates), max(dates)] if dates else None,
             "status": "HISTORICAL_SOURCE_REVISION_DETECTED_BLOCKER" if revisions else
                 "PASS" if count else "NO_NEW_CANONICAL_DATA",
             "fetchedAt": info["fetchedAt"], "endpoint": BASE_URL + "trend/",
             "sourceHealth": info["sourceHealth"]}
    atomic_json(folder / "audit.json", audit)
    return audit, deltas


def csv_line(values: list, newline: str) -> bytes:
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator=newline).writerow(values)
    return stream.getvalue().encode()


def build_market(parent: dict, path: Path, deltas: dict, append: dict) -> tuple[int, list[dict]]:
    old_path = parent["processed"] / "sector_ohlcva.csv"
    invalid_new, count = [], 0
    with old_path.open("rb") as old, path.open("xb") as new:
        header = next(old)
        if next(csv.reader([header.decode()])) != list(OHLCVA_COLUMNS):
            raise ValueError("SHENWAN_OFFICIAL_SCHEMA_DRIFT_BLOCKER: canonical columns")
        new.write(header)
        newline = "\r\n" if header.endswith(b"\r\n") else "\n"
        def emit(code):
            nonlocal count
            if code is None: return
            provenance = append["perSector"][code]
            for position, source in enumerate(deltas[code]):
                bad = quality(source)
                row = dict(zip(OHLCVA_COLUMNS, [source["bargaindate"], code, parent["names"][code],
                    *[source[key] for key in FIELDS], PROVIDER, provenance["sourceUrl"],
                    provenance["fetchedAt"], provenance["deltaRawPath"].removeprefix("data/raw/shenwan/"),
                    provenance["deltaRawHash"], provenance["deltaRawHash"], position, not bool(bad), bad]))
                new.write(csv_line([row[col] for col in OHLCVA_COLUMNS], newline))
                if bad: invalid_new.append(row)
                count += 1
        previous, previous_day = None, None
        old_rows = 0
        for line in old:
            parsed = next(csv.reader([line.decode()]))
            if len(parsed) != len(OHLCVA_COLUMNS):
                raise ValueError("TRANSACTIONAL_UPDATE_BLOCKER: multiline/malformed canonical")
            day, code = parsed[:2]
            if code != previous:
                if previous is not None and code <= previous:
                    raise ValueError("TRANSACTIONAL_UPDATE_BLOCKER: parent order")
                emit(previous)
                previous, previous_day = code, None
            if code not in parent["names"] or day > parent["cutoff"] or (previous_day and day <= previous_day):
                raise ValueError("TRANSACTIONAL_UPDATE_BLOCKER: parent keys")
            previous_day = day
            new.write(line)  # Preserve original prefix bytes/provenance, no normalization.
            old_rows += 1
        emit(previous)
        new.flush()
        os.fsync(new.fileno())
    if old_rows != parent["rowCount"] or count != append["totalNewRows"]:
        raise ValueError("TRANSACTIONAL_UPDATE_BLOCKER: row count")
    if prefix_hash(path, parent["cutoff"]) != sha(old_path):
        raise ValueError("POST_PUBLISH_PREFIX_IDENTITY_FAILURE")
    return old_rows + count, invalid_new


def base_lineage(root: Path, parent: dict) -> dict:
    base = root / "data/processed/shenwan"
    meta = read_json(base / "sector_admission.json")
    return {"schemaVersion": 1, "snapshotId": parent["baseId"], "parentSnapshotId": None,
            "processedPath": "data/processed/shenwan", "newCutoff": meta["latest_date"],
            "newRowCount": meta["total_rows"], "provider": PROVIDER,
            "rawBaseManifestHash": sha(root / "data/manifests/shenwan_sector_history_manifest.json"),
            "rawFingerprints": meta["raw_fingerprints"], "codeFingerprints": meta["code_fingerprints"],
            "canonicalFiles": {"data/processed/shenwan/" + name: sha(base / name)
                               for name in [*meta["canonical_hashes"], "sector_admission.json"]},
            "note": "Immutable original base; original snapshot_id algorithm unchanged."}


def prepare_candidate(root: Path, parent: dict, folder: Path, audit: dict, deltas: dict, git_commit: str) -> dict:
    if audit["status"] != "PASS":
        raise ValueError(audit["status"])
    # A new preview is private; rejected/crashed candidates never become current.
    work = Path(tempfile.mkdtemp(prefix="candidate_", dir=folder))
    delta_dir, processed = work / "delta", work / "processed"
    delta_dir.mkdir()
    processed.mkdir()
    append = {key: value for key, value in audit.items() if key != "sourceHealth"}
    append["perSector"] = {code: dict(record) for code, record in audit["perSector"].items()}
    raw_files, raw_fps = dict(parent["rawFiles"]), dict(parent["rawFingerprints"])
    run = audit["runId"]
    for code, rows in deltas.items():
        record = append["perSector"][code]
        record.update(deltaRawPath=None, deltaRawHash=None)
        if not rows: continue
        relative = f"data/raw/shenwan/sector_history_append/{run}/{code}.json"
        path = delta_dir / (code + ".json")
        durable_bytes(path, decimal_json(rows))
        record.update(deltaRawPath=relative, deltaRawHash=sha(path))
        raw_files[relative] = sha(path)
        raw_fps[relative.removeprefix("data/raw/shenwan/")] = sha(path)
    durable_bytes(delta_dir / "manifest.json", encoded(append))
    relative = f"data/raw/shenwan/sector_history_append/{run}/manifest.json"
    raw_files[relative] = sha(delta_dir / "manifest.json")
    raw_fps[relative.removeprefix("data/raw/shenwan/")] = raw_files[relative]
    code_fps = dict(parent["codeFingerprints"])
    code_fps.update({"shenwan_official_update_v1.py": sha(Path(__file__)),
                     "shenwan_tls_v1.py": sha(Path(__file__).with_name("shenwan_tls.py"))})
    identifier = snapshot_id(raw_fps, code_fingerprints=code_fps)
    row_count, new_invalid = build_market(parent, processed / "sector_ohlcva.csv", deltas, append)
    for filename in ("sector_catalog.csv", "stock_classification_canonical.csv"):
        durable_bytes(processed / filename, (parent["processed"] / filename).read_bytes())
    sidecar = (parent["processed"] / "sector_invalid_ohlc.csv").read_bytes()
    columns = next(csv.reader([sidecar.splitlines()[0].decode()]))
    newline = "\r\n" if sidecar.splitlines(keepends=True)[0].endswith(b"\r\n") else "\n"
    extra = b"".join(csv_line([row.get(col, "SOURCE_INVALID" if col == "root_cause_class" else None)
                               for col in columns], newline) for row in new_invalid)
    durable_bytes(processed / "sector_invalid_ohlc.csv", sidecar + extra)
    projection = pd.read_csv(processed / "sector_ohlcva.csv",
        usecols=["date", "sector_code", "sector_name", "is_valid_ohlc"], dtype={"sector_code": str}, parse_dates=["date"])
    catalog = pd.read_csv(processed / "sector_catalog.csv", dtype={"sector_code": str})
    summary, coverage = audit_coverage(projection, catalog)
    durable_bytes(processed / "sector_coverage.csv", coverage.to_csv(index=False).encode())
    metadata = {**parent["admission"], **summary, "data_snapshot_id": identifier,
                "raw_fingerprints": raw_fps, "code_fingerprints": code_fps,
                "append_lineage_version": 1, "parent_snapshot_id": parent["snapshotId"],
                # The original research eligibility/admission is NOT upgraded here.
                "admission_scope_note": "Append-only market-data generation; no new PIT or Validation authorization.",
                "volume_nonnull_ratio": None, "amount_nonnull_ratio": None,
                "canonical_hashes": {filename: sha(processed / filename)
                                      for filename in parent["admission"]["canonical_hashes"]}}
    durable_bytes(processed / "sector_admission.json", encoded(metadata))
    output_relative = f"data/processed/shenwan_snapshots/{identifier}"
    parent_manifest_path = root / LINEAGE / (parent["snapshotId"] + ".json")
    parent_manifest_hash = sha(parent_manifest_path) if parent_manifest_path.exists() else hashlib.sha256(encoded(base_lineage(root, parent))).hexdigest()
    manifest = {"schemaVersion": 1, "lineageVersion": 1, "snapshotId": identifier,
        "parentSnapshotId": parent["snapshotId"], "parentManifestHash": parent_manifest_hash,
        "createdAt": now(), "provider": PROVIDER, "catalogSource": BASE_URL + "current/",
        "trendSource": BASE_URL + "trend/", "tlsVerificationMode": audit["sourceHealth"]["tlsMode"],
        "oldCutoff": parent["cutoff"], "newCutoff": audit["newCutoff"],
        "frozenU0Hash": audit["frozenU0Hash"], "sectorCount": len(parent["names"]),
        "oldRowCount": parent["rowCount"], "newRowCount": row_count,
        "appendedRowCount": audit["totalNewRows"], "appendRunId": run,
        "appendManifestPath": relative, "appendManifestHash": sha(delta_dir / "manifest.json"),
        "rawBaseManifestHash": sha(root / "data/manifests/shenwan_sector_history_manifest.json"),
        "parserVersion": PARSER_VERSION, "dataSchemaVersion": SCHEMA_VERSION, "transformVersion": TRANSFORM_VERSION,
        "updaterVersion": UPDATER_VERSION, "codeFingerprints": code_fps, "rawFingerprints": raw_fps,
        "rawFiles": raw_files, "canonicalHashes": metadata["canonical_hashes"],
        "canonicalFiles": {output_relative + "/" + name: sha(processed / name)
                           for name in [*metadata["canonical_hashes"], "sector_admission.json"]},
        "processedPath": output_relative, "historicalPrefixHash": sha(parent["processed"] / "sector_ohlcva.csv"),
        "historicalRevisionCount": 0, "knownAnomalyFingerprint": {
            "parentInvalidSidecarHash": sha(parent["processed"] / "sector_invalid_ohlc.csv"),
            "newInvalidCount": audit["newInvalidOhlc"], "parentMissingnessPreserved": True},
        "sourceFetchTimestamp": audit["fetchedAt"], "gitCommit": git_commit,
        "validationOpened": False, "finalOosRead": False}
    durable_bytes(work / "snapshot.json", encoded(manifest))
    return {"work": work, "manifest": manifest, "append": append}


@contextmanager
def publication_lock(root: Path):
    path = root / LINEAGE / "update.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise ValueError("TRANSACTIONAL_UPDATE_BLOCKER: concurrent/stale lock; human review required") from error
    try:
        os.write(fd, encoded({"pid": os.getpid(), "createdAt": now()}))
        os.fsync(fd)
        yield
    finally:
        os.close(fd)
        path.unlink()
        sync_dir(path.parent)


def publish(root: Path, parent: dict, candidate: dict, *, checkpoint=lambda name: None) -> dict:
    manifest, work = candidate["manifest"], candidate["work"]
    if (not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", manifest["appendRunId"])
        or not re.fullmatch(r"[a-f0-9]{64}", manifest["snapshotId"])
        or manifest["processedPath"] != "data/processed/shenwan_snapshots/" + manifest["snapshotId"]
        or manifest["parentSnapshotId"] != parent["snapshotId"]
        or manifest["historicalRevisionCount"] != 0
        or manifest["appendedRowCount"] <= 0
        or manifest["frozenU0Hash"] != semantic_hash(sorted(parent["names"]))
        or manifest["snapshotId"] != snapshot_id(manifest["rawFingerprints"], code_fingerprints=manifest["codeFingerprints"])):
        raise ValueError("TRANSACTIONAL_UPDATE_BLOCKER: final manifest gate")
    if not work.resolve().is_relative_to((root / "data/staging/shenwan_official").resolve()):
        raise ValueError("TRANSACTIONAL_UPDATE_BLOCKER: candidate path")
    with publication_lock(root):
        current = read_parent(root)
        if current["snapshotId"] != parent["snapshotId"]:
            raise ValueError("TRANSACTIONAL_UPDATE_BLOCKER: parent changed")
        if sha(parent["processed"] / "sector_ohlcva.csv") != manifest["historicalPrefixHash"]:
            raise ValueError("TRANSACTIONAL_UPDATE_BLOCKER: parent changed")
        if prefix_hash(work / "processed/sector_ohlcva.csv", parent["cutoff"]) != manifest["historicalPrefixHash"]:
            raise ValueError("POST_PUBLISH_PREFIX_IDENTITY_FAILURE")
        for relative, digest in manifest["canonicalFiles"].items():
            if sha(work / "processed" / Path(relative).name) != digest:
                raise ValueError("TRANSACTIONAL_UPDATE_BLOCKER: candidate changed")
        for record in candidate["append"]["perSector"].values():
            if record["newRows"] and sha(work / "delta" / (record["sectorCode"] + ".json")) != record["deltaRawHash"]:
                raise ValueError("TRANSACTIONAL_UPDATE_BLOCKER: delta changed")
        if sha(work / "delta/manifest.json") != manifest["appendManifestHash"]:
            raise ValueError("TRANSACTIONAL_UPDATE_BLOCKER: append manifest changed")
        checkpoint("before_materialization")
        base_path = root / LINEAGE / (parent["baseId"] + ".json")
        golden_manifest_bytes = encoded(base_lineage(root, parent))
        if base_path.exists():
            if base_path.read_bytes() != golden_manifest_bytes:
                raise ValueError("SNAPSHOT_LINEAGE_BLOCKER: existing golden manifest changed")
        else:
            durable_bytes(base_path, golden_manifest_bytes)
        parent_path = root / LINEAGE / (parent["snapshotId"] + ".json")
        if sha(parent_path) != manifest["parentManifestHash"]:
            raise ValueError("SNAPSHOT_LINEAGE_BLOCKER: parent metadata changed")
        raw_dest = safe_path(root, "data/raw/shenwan/sector_history_append/" + manifest["appendRunId"])
        generation = safe_path(root, manifest["processedPath"])
        for source, dest in ((work / "delta", raw_dest), (work / "processed", generation)):
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                raise ValueError("TRANSACTIONAL_UPDATE_BLOCKER: immutable target exists; retain orphan for review")
            os.rename(source, dest)
            sync_dir(dest.parent)
            checkpoint("after_" + source.name)
        versioned = root / LINEAGE / (manifest["snapshotId"] + ".json")
        durable_bytes(versioned, encoded(manifest))
        verify_files(root, manifest["rawFiles"])
        verify_files(root, manifest["canonicalFiles"])
        # This ONE atomic replacement is the only current-snapshot commit point.
        atomic_json(root / LINEAGE / "current.json", {"schemaVersion": 1,
            "snapshotId": manifest["snapshotId"], "manifestPath": str(versioned.relative_to(root)).replace(os.sep, "/"),
            "manifestSha256": sha(versioned)}, before_replace=lambda: checkpoint("before_pointer"))
        checkpoint("after_pointer")
        accepted = read_parent(root)  # Full lineage and prefix audit after publication.
        if accepted["snapshotId"] != manifest["snapshotId"]:
            raise ValueError("POST_PUBLISH_PREFIX_IDENTITY_FAILURE")
        return manifest


def apply_stage(root: Path, folder: Path, git_commit: str, *, dry_run: bool = False, checkpoint=lambda name: None) -> dict:
    parent = read_parent(root)
    audit, deltas = audit_stage(root, parent, folder)
    if audit["status"] != "PASS":
        return {"status": audit["status"], "updateApplied": False, "audit": audit}
    candidate = prepare_candidate(root, parent, folder, audit, deltas, git_commit)
    result = {"status": "DRY_RUN_PASS" if dry_run else "UPDATE_APPLIED", "updateApplied": False,
              "audit": audit, "previewSnapshotId": candidate["manifest"]["snapshotId"],
              "transactionPreview": "PASS", "historicalPrefixIdentity": "PASS"}
    if not dry_run:
        result["snapshot"] = publish(root, parent, candidate, checkpoint=checkpoint)
        result["updateApplied"] = True
    return result


def current_readiness(root: Path) -> tuple[dict, dict]:
    # Existing frozen date/boolean-only implementation is authoritative. Its
    # golden inspector stays unchanged and verifies all frozen research seals.
    from research.f1_validation_readiness_v1 import (inspect_parent, frozen_identity,
        formal_eligible_dates, calculate_readiness, assert_monotonic)
    pre, baseline = inspect_parent(root)
    parent = read_parent(root)
    if parent["snapshotId"] == pre["parentSnapshotId"]:
        return pre, baseline
    _, split = frozen_identity(root)
    projection = pd.read_csv(parent["processed"] / "sector_ohlcva.csv",
        usecols=["date", "sector_code", "is_valid_ohlc"], dtype={"sector_code": str, "is_valid_ohlc": bool}, parse_dates=["date"])
    calendar, eligible = formal_eligible_dates(projection, sorted(parent["names"]),
        start=parent["admission"]["common_start_date"], end=parent["admission"]["common_end_date"])
    if semantic_hash(eligible[:239]) != split["frozenPrefixSha256"]:
        raise ValueError("SPLIT_REPRODUCIBILITY_REVIEW")
    readiness = calculate_readiness(calendar=calendar,
        ordinal_dates={i + 1: day for i, day in enumerate(eligible[:460])}, structural_dates=eligible,
        cutoff=parent["cutoff"], calendar_verified=True, snapshot_id_value=parent["snapshotId"],
        parent_snapshot_id_value=parent["manifest"]["parentSnapshotId"])
    assert_monotonic(baseline, readiness)
    # Compare against the actual immediately prior accepted generation as well.
    prior_manifest = read_json(root / LINEAGE / (parent["manifest"]["parentSnapshotId"] + ".json"))
    if prior_manifest["snapshotId"] != pre["parentSnapshotId"]:
        prior_dir = safe_path(root, prior_manifest["processedPath"])
        prior_meta = read_json(prior_dir / "sector_admission.json")
        prior_projection = pd.read_csv(prior_dir / "sector_ohlcva.csv", usecols=list(projection.columns),
            dtype={"sector_code": str, "is_valid_ohlc": bool}, parse_dates=["date"])
        prior_calendar, prior_eligible = formal_eligible_dates(prior_projection, sorted(parent["names"]),
            start=prior_meta["common_start_date"], end=prior_meta["common_end_date"])
        prior_ready = calculate_readiness(calendar=prior_calendar,
            ordinal_dates={i + 1: day for i, day in enumerate(prior_eligible[:460])}, structural_dates=prior_eligible,
            cutoff=prior_meta["latest_date"], calendar_verified=True, snapshot_id_value=prior_meta["data_snapshot_id"])
        assert_monotonic(prior_ready, readiness)
    return pre, readiness
