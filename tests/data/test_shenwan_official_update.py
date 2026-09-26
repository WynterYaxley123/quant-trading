"""Synthetic infrastructure contracts; no model, returns or live network."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import subprocess

import pytest


@pytest.fixture
def api():
    from src.data.providers import shenwan_official_update as module
    return module


def bar(day="2026-09-18", code="801012", **changes):
    row = dict(swindexcode=code, bargaindate=day, openindex=10, maxindex=12,
               minindex=9, closeindex=11, bargainamount=100, bargainsum=1000,
               hike=1, markup=0.1)
    return {**row, **changes}


def payload(rows):
    return json.dumps(dict(code="200", message="ok", data=rows)).encode()


def test_exact_source_urls(api):
    for kind in ("current", "trend"):
        url = api.source_url(kind, page=1, code="801012")
        api.check_url(url, kind, code="801012")


@pytest.mark.parametrize("defect", ["host", "http", "path", "port", "userinfo", "query", "fragment"])
def test_source_drift_rejected(api, defect):
    url = api.source_url("trend", code="801012")
    url = {"host": url.replace("www.swsresearch.com", "example.com"),
           "http": url.replace("https:", "http:"), "path": url.replace("institute-sw/", ""),
           "port": url.replace(".com/", ".com:444/"),
           "userinfo": url.replace("https://", "https://user@"),
           "query": url + "&period=WEEK", "fragment": url + "#x"}[defect]
    with pytest.raises(ValueError, match="SOURCE_IDENTITY"):
        api.check_url(url, "trend", code="801012")


def test_trend_numeric_semantics_and_missingness(api):
    parsed = api.parse_trend(payload([bar(bargainamount=None)]), "801012", "2026-09-27")
    assert parsed["2026-09-18"]["bargainamount"] is None
    assert parsed["2026-09-18"]["openindex"] == Decimal("10.0")


@pytest.mark.parametrize("defect", ["wrapper", "field", "code", "date", "future", "duplicate", "nonfinite", "string"])
def test_schema_fail_closed(api, defect):
    rows = [bar()]
    if defect == "field": del rows[0]["closeindex"]
    if defect == "code": rows[0]["swindexcode"] = "801013"
    if defect == "date": rows[0]["bargaindate"] = "2026-9-18"
    if defect == "future": rows[0]["bargaindate"] = "2026-09-28"
    if defect == "duplicate": rows *= 2
    if defect == "nonfinite": rows[0]["closeindex"] = float("nan")
    if defect == "string": rows[0]["closeindex"] = "ten"
    raw = payload(rows) if defect != "wrapper" else b'{"code":"500","data":[]}'
    with pytest.raises(ValueError): api.parse_trend(raw, "801012", "2026-09-27")


def test_decimal_not_float_rounding(api):
    old = api.parse_trend(payload([bar(closeindex=11)]), "801012", "2026-09-27")
    new = api.parse_trend(payload([bar(closeindex=11.0)]), "801012", "2026-09-27")
    assert api.overlap_audit(old, new, "2026-09-18")["revisionCount"] == 0
    raw = payload([bar()]).replace(b'"closeindex": 11', b'"closeindex": 11.000000000000000001')
    new = api.parse_trend(raw, "801012", "2026-09-27")
    assert api.overlap_audit(old, new, "2026-09-18")["revisionCount"] == 1


@pytest.mark.parametrize("defect", ["revision", "deletion", "gapfill", "invalidrepair", "missingness"])
def test_full_historical_revisions(api, defect):
    old_rows = [bar(), bar("2026-09-16", maxindex=5)]
    new_rows = deepcopy(old_rows)
    if defect == "revision": new_rows[0]["closeindex"] += 0.01
    if defect == "deletion": new_rows.pop()
    if defect == "gapfill": new_rows.append(bar("2026-09-17"))
    if defect == "invalidrepair": new_rows[1]["maxindex"] = 12
    if defect == "missingness": new_rows[0]["bargainamount"] = None
    old = api.parse_trend(payload(old_rows), "801012", "2026-09-27")
    new = api.parse_trend(payload(new_rows), "801012", "2026-09-27")
    audit = api.overlap_audit(old, new, "2026-09-18")
    assert audit["revisionCount"] > 0 and audit["overlapRowsChecked"] == len(old)


def test_current_day_excluded_no_weekday_calendar(api):
    rows = api.parse_trend(payload([bar(), bar("2026-09-27")]), "801012", "2026-09-27")
    delta, excluded = api.finalized_delta(rows, "2026-09-18", "2026-09-27")
    assert not delta and excluded == ["2026-09-27"]


def test_invalid_new_bar_retained(api):
    rows = api.parse_trend(payload([bar("2026-09-26", maxindex=5)]), "801012", "2026-09-27")
    delta, _ = api.finalized_delta(rows, "2026-09-18", "2026-09-27")
    assert len(delta) == 1 and api.quality(delta[0]) != ""


def test_catalog_comparison_does_not_mutate_frozen(api):
    frozen = {"801012": "old", "801013": "same"}
    current = {"801012": "new", "801014": "added"}
    audit = api.compare_catalog(frozen, current)
    assert audit["removedOfficialCodes"] == ["801013"]
    assert audit["addedOfficialCodes"] == ["801014"]
    assert audit["renamedCodes"] == [{"sectorCode": "801012", "oldName": "old", "newName": "new"}]
    assert frozen == {"801012": "old", "801013": "same"}


def test_catalog_http_next_not_followed(api):
    raw = json.dumps(dict(code="200", message="ok", data=dict(count=1,
        next="http://www.swsresearch.com/api/index_publish/current/?page=2", results=[
            dict(swindexcode="801012", swindexname="test", l3=None, l4=None)]))).encode()
    names, count, advertised = api.parse_catalog(raw)
    assert names == {"801012": "test"} and count == 1 and advertised.startswith("http:")


def test_all_frozen_required(api):
    with pytest.raises(ValueError, match="FROZEN_SECTOR"):
        api.require_full_coverage(["801012", "801013"], {"801012": {}})


@pytest.fixture(scope="module")
def chain(tmp_path_factory):
    folder = tmp_path_factory.mktemp("tls-chain")
    def run(*args):
        subprocess.run(["openssl", *args], cwd=folder, check=True, capture_output=True)
    run("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "root.key", "-out", "root.pem",
        "-subj", "/CN=Synthetic Root", "-days", "2", "-addext", "basicConstraints=critical,CA:TRUE")
    run("req", "-new", "-newkey", "rsa:2048", "-nodes", "-keyout", "int.key", "-out", "int.csr", "-subj", "/CN=Synthetic Intermediate")
    (folder / "int.ext").write_text("basicConstraints=critical,CA:TRUE,pathlen:0\nkeyUsage=critical,keyCertSign,cRLSign\n")
    run("x509", "-req", "-in", "int.csr", "-CA", "root.pem", "-CAkey", "root.key", "-CAcreateserial",
        "-out", "int.pem", "-days", "1", "-extfile", "int.ext")
    run("req", "-new", "-newkey", "rsa:2048", "-nodes", "-keyout", "leaf.key", "-out", "leaf.csr", "-subj", "/CN=www.swsresearch.com")
    (folder / "leaf.ext").write_text("basicConstraints=critical,CA:FALSE\nsubjectAltName=DNS:www.swsresearch.com\nextendedKeyUsage=serverAuth\n")
    run("x509", "-req", "-in", "leaf.csr", "-CA", "int.pem", "-CAkey", "int.key", "-CAcreateserial",
        "-out", "leaf.pem", "-days", "1", "-extfile", "leaf.ext")
    return folder


def test_strict_standard_chain(chain):
    from src.data.providers.shenwan_tls import verify_chain
    assert verify_chain(chain / "leaf.pem", chain / "root.pem", chain / "int.pem")["verified"]


def test_missing_intermediate_and_local_completion(chain):
    from src.data.providers.shenwan_tls import verify_chain
    with pytest.raises(ValueError, match="TLS"):
        verify_chain(chain / "leaf.pem", chain / "root.pem")
    assert verify_chain(chain / "leaf.pem", chain / "root.pem", chain / "int.pem")["verified"]


@pytest.mark.parametrize("defect", ["wrong", "expired", "hostname"])
def test_invalid_tls_material(chain, defect):
    from src.data.providers.shenwan_tls import verify_chain
    kwargs = {"hostname": "wrong.example"} if defect == "hostname" else {}
    if defect == "expired": kwargs["at_time"] = 2100000000
    intermediate = chain / ("root.pem" if defect == "wrong" else "int.pem")
    with pytest.raises(ValueError, match="TLS"):
        verify_chain(chain / "leaf.pem", chain / "root.pem", intermediate, **kwargs)


def test_no_disabled_tls_or_performance_imports():
    import ast
    root = Path(__file__).resolve().parents[2]
    for name in ("shenwan_tls.py", "shenwan_official_update.py"):
        source = (root / "src/data/providers" / name).read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                assert not any(k.arg == "verify" and isinstance(k.value, ast.Constant) and k.value.value is False for k in node.keywords)
                assert not (isinstance(node.func, ast.Attribute) and node.func.attr in ("disable_warnings", "_create_unverified_context"))
            if isinstance(node, ast.ImportFrom):
                assert not any(x in (node.module or "").lower() for x in ("validation_runner", "sector_index_baseline", "evaluation", "ridge"))


@pytest.mark.integration
def test_real_base_golden_snapshot_only_identity(api):
    from src.data.providers.shenwan_sector import snapshot_id
    root = Path(__file__).resolve().parents[2]
    admission = json.loads((root / "data/processed/shenwan/sector_admission.json").read_text())
    assert snapshot_id(admission["raw_fingerprints"], code_fingerprints=admission["code_fingerprints"]) == "872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500"


def test_atomic_pointer_failure_preserves_parent(api, tmp_path):
    pointer = tmp_path / "current.json"
    api.atomic_json(pointer, {"snapshotId": "old"})
    with pytest.raises(RuntimeError):
        api.atomic_json(pointer, {"snapshotId": "new"}, before_replace=lambda: (_ for _ in ()).throw(RuntimeError("crash")))
    assert json.loads(pointer.read_text())["snapshotId"] == "old"


def test_atomic_pointer_publish(api, tmp_path):
    pointer = tmp_path / "current.json"
    api.atomic_json(pointer, {"snapshotId": "old"})
    api.atomic_json(pointer, {"snapshotId": "new"})
    assert json.loads(pointer.read_text())["snapshotId"] == "new"


def test_readiness_sixty_still_sealed():
    import pandas as pd
    from research.f1_validation_readiness_v1 import calculate_readiness, SEAL, assert_monotonic
    calendar = pd.date_range("2020-01-01", periods=700)
    args = dict(calendar=calendar, ordinal_dates={i + 1: str(d.date()) for i, d in enumerate(calendar[:460])},
                structural_dates=calendar[:460], cutoff=str(calendar[-1].date()), calendar_verified=True, snapshot_id_value="synthetic")
    result = calculate_readiness(**args)
    assert result["ready"] == 60
    assert_monotonic(result, result)
    assert all(result[k] == v for k, v in SEAL.items())
    assert not result["validationOpened"] and not result["finalOosRead"]


@pytest.fixture
def synthetic_store(api, tmp_path):
    """Small COMPLETE synthetic acquisition/store, never exported as market data."""
    import pandas as pd
    from src.data.providers.shenwan_sector import OHLCVA_COLUMNS, snapshot_id
    root = tmp_path
    raw = root / "data/raw/shenwan/sector_history"
    processed = root / "data/processed/shenwan"
    raw.mkdir(parents=True)
    processed.mkdir(parents=True)
    codes = ["801012", "801013"]
    fingerprints, rows = {}, []
    for code in codes:
        path = raw / (code + ".json")
        api.durable_bytes(path, payload([bar(code=code)]))
        fingerprints["sector_history/" + code + ".json"] = api.sha(path)
        rows.append(dict(zip(OHLCVA_COLUMNS, ["2026-09-18", code, code,
            10, 12, 9, 11, 100, 1000, api.PROVIDER, api.source_url("trend", code=code),
            "2026-09-20T00:00:00+08:00", "sector_history/" + code + ".json",
            api.sha(path), api.sha(path), 0, True, ""])))
    manifest = root / "data/manifests/shenwan_sector_history_manifest.json"
    api.durable_bytes(manifest, b'{}\n')
    fingerprints["sector_history_manifest.json"] = api.sha(manifest)
    frame = pd.DataFrame(rows, columns=OHLCVA_COLUMNS)
    frame["date"] = pd.to_datetime(frame["date"])
    frame.to_csv(processed / "sector_ohlcva.csv", index=False)
    pd.DataFrame({"sector_code": codes, "sector_name": codes}).to_csv(processed / "sector_catalog.csv", index=False)
    (processed / "stock_classification_canonical.csv").write_text("classification_version,available_at\n,\n")
    frame.iloc[:0].assign(root_cause_class="SOURCE_INVALID").to_csv(processed / "sector_invalid_ohlc.csv", index=False)
    summary, coverage = api.audit_coverage(frame, pd.DataFrame())
    coverage.to_csv(processed / "sector_coverage.csv", index=False)
    meta = {**summary, "data_snapshot_id": snapshot_id(fingerprints), "raw_fingerprints": fingerprints,
            "code_fingerprints": {}, "classification_version": None, "strict_pit": False,
            "canonical_hashes": {p.name: api.sha(p) for p in processed.glob("*.csv")}}
    api.durable_bytes(processed / "sector_admission.json", api.encoded(meta))
    parent = api.read_parent(root)
    folder = root / "data/staging/shenwan_official/synthetic"
    folder.mkdir(parents=True)
    info = {"status": "STAGED", "runId": "synthetic", "parentSnapshotId": parent["snapshotId"],
            "oldCutoff": parent["cutoff"], "provider": api.PROVIDER, "today": "2026-09-27",
            "fetchedAt": "2026-09-27T00:00:00+08:00", "sourceHealth": {"status": "PASS", "tlsMode": "SYNTHETIC"}, "files": {}}
    for code in codes:
        path = folder / (code + ".json")
        api.durable_bytes(path, payload([bar(code=code), bar("2026-09-21", code=code, bargainamount=None)]))
        info["files"][code] = {"responseHash": api.sha(path), "sourceUrl": api.source_url("trend", code=code),
                                "fetchedAt": info["fetchedAt"], "redirectChain": []}
    api.atomic_json(folder / "stage.json", info)
    return root, parent, folder


def test_transaction_preview_no_publish(api, synthetic_store):
    root, parent, folder = synthetic_store
    result = api.apply_stage(root, folder, "synthetic-git", dry_run=True)
    assert result["status"] == "DRY_RUN_PASS" and not result["updateApplied"]
    assert api.read_parent(root)["snapshotId"] == parent["snapshotId"]
    assert not (root / api.LINEAGE / "current.json").exists()
    assert not (root / "data/raw/shenwan/sector_history_append").exists()


def test_full_publish_lineage_prefix_and_idempotency(api, synthetic_store):
    root, parent, folder = synthetic_store
    result = api.apply_stage(root, folder, "synthetic-git")
    current = api.read_parent(root)
    assert result["updateApplied"] and current["cutoff"] == "2026-09-21" and current["rowCount"] == 4
    assert current["manifest"]["parentSnapshotId"] == parent["snapshotId"]
    assert api.prefix_hash(current["processed"] / "sector_ohlcva.csv", parent["cutoff"]) == api.sha(parent["processed"] / "sector_ohlcva.csv")
    assert current["admission"]["classification_version"] is None and not current["admission"]["strict_pit"]
    assert api.resolve_current(root) == current["processed"]
    # Same source, but a fresh stage bound to the actual current parent.
    info = api.read_json(folder / "stage.json")
    info.update(parentSnapshotId=current["snapshotId"], oldCutoff=current["cutoff"])
    api.atomic_json(folder / "stage.json", info)
    again = api.apply_stage(root, folder, "synthetic-git", dry_run=True)
    assert again["status"] == "NO_NEW_CANONICAL_DATA" and again["audit"]["totalNewRows"] == 0
    assert api.read_parent(root)["snapshotId"] == current["snapshotId"]


@pytest.mark.parametrize("point", ["before_materialization", "after_delta", "after_processed", "before_pointer"])
def test_transaction_crashes_leave_usable_golden(api, synthetic_store, point):
    root, parent, folder = synthetic_store
    def crash(name):
        if name == point: raise RuntimeError("synthetic crash")
    with pytest.raises(RuntimeError, match="synthetic crash"):
        api.apply_stage(root, folder, "synthetic-git", checkpoint=crash)
    current = api.read_parent(root)
    assert current["snapshotId"] == parent["snapshotId"]
    assert api.sha(current["processed"] / "sector_ohlcva.csv") == api.sha(parent["processed"] / "sector_ohlcva.csv")


def test_failure_after_commit_is_published_not_rolled_back(api, synthetic_store):
    root, parent, folder = synthetic_store
    def crash(name):
        if name == "after_pointer": raise RuntimeError("post commit crash")
    with pytest.raises(RuntimeError): api.apply_stage(root, folder, "synthetic-git", checkpoint=crash)
    assert api.read_parent(root)["snapshotId"] != parent["snapshotId"]


def test_revision_rejects_entire_cycle(api, synthetic_store):
    root, parent, folder = synthetic_store
    info = api.read_json(folder / "stage.json")
    path = folder / "801012.json"
    path.write_bytes(payload([bar(closeindex=11.01), bar("2026-09-21")]))
    info["files"]["801012"]["responseHash"] = api.sha(path)
    api.atomic_json(folder / "stage.json", info)
    result = api.apply_stage(root, folder, "synthetic-git")
    assert result["status"] == "HISTORICAL_SOURCE_REVISION_DETECTED_BLOCKER"
    assert not result["updateApplied"] and api.read_parent(root)["snapshotId"] == parent["snapshotId"]


def test_staging_tampering_rejected(api, synthetic_store):
    root, parent, folder = synthetic_store
    with (folder / "801012.json").open("ab") as stream: stream.write(b" ")
    with pytest.raises(ValueError, match="HASH"): api.apply_stage(root, folder, "synthetic-git")


def test_pointer_hash_tampering_rejected(api, synthetic_store):
    root, _, folder = synthetic_store
    api.apply_stage(root, folder, "synthetic-git")
    pointer = root / api.LINEAGE / "current.json"
    value = api.read_json(pointer)
    value["manifestSha256"] = "0" * 64
    api.atomic_json(pointer, value)
    with pytest.raises(ValueError, match="LINEAGE"): api.read_parent(root)


def test_path_escape_rejected(api, tmp_path):
    with pytest.raises(ValueError, match="PATH"): api.safe_path(tmp_path, "../outside")


def test_concurrent_lock_fail_closed(api, tmp_path):
    with api.publication_lock(tmp_path):
        with pytest.raises(ValueError, match="lock"):
            with api.publication_lock(tmp_path): pass


def test_complete_stage_then_audit_all_series(api, synthetic_store):
    root, parent, _ = synthetic_store
    called = []
    class Client:
        def fetch(self, kind, *, code):
            called.append(code)
            data = payload([bar(code=code), bar("2026-09-21", code=code)])
            return data, {"sourceUrl": api.source_url(kind, code=code), "fetchedAt": api.now(),
                          "responseHash": __import__("hashlib").sha256(data).hexdigest(), "redirectChain": []}
    folder = api.stage(root, parent, Client(), {"status": "PASS", "tlsMode": "SYNTHETIC"}, "all-series")
    audit, _ = api.audit_stage(root, parent, folder)
    assert called == sorted(parent["names"])
    assert audit["sectorCount"] == 2 and audit["totalOverlapRows"] == 2 and audit["totalNewRows"] == 2


def test_partial_stage_retains_evidence_never_publishes(api, synthetic_store):
    root, parent, _ = synthetic_store
    class Client:
        def fetch(self, kind, *, code):
            if code == "801013": raise ValueError("FROZEN_SECTOR_SOURCE_UNAVAILABLE_BLOCKER")
            data = payload([bar(code=code)])
            return data, {"sourceUrl": api.source_url(kind, code=code), "fetchedAt": api.now(),
                          "responseHash": __import__("hashlib").sha256(data).hexdigest(), "redirectChain": []}
    with pytest.raises(ValueError, match="FROZEN_SECTOR"):
        api.stage(root, parent, Client(), {"status": "PASS"}, "partial")
    folder = root / "data/staging/shenwan_official/partial"
    assert (folder / "801012.json").exists() and api.read_json(folder / "stage.json")["status"] == "BLOCKED"
    with pytest.raises(ValueError): api.audit_stage(root, parent, folder)
    assert api.read_parent(root)["snapshotId"] == parent["snapshotId"]


def test_request_uses_verified_bundle_no_redirect_implicit(api, monkeypatch):
    calls = []
    class Response:
        is_redirect = False
        status_code = 200
        content = payload([bar()])
        headers = {}
    class Session:
        def get(self, url, **kwargs):
            calls.append(kwargs)
            return Response()
    monkeypatch.setattr(api, "prepare_tls", lambda: ("verified-test-bundle", {}))
    monkeypatch.setattr(api.requests, "Session", Session)
    client = api.OfficialClient()
    client.fetch("trend")
    assert calls[0]["verify"] == "verified-test-bundle" and calls[0]["allow_redirects"] is False


def test_untrusted_redirect_recorded_then_rejected(api, monkeypatch):
    class Response:
        is_redirect = True
        status_code = 302
        headers = {"Location": "https://other.example/data"}
    class Session:
        def get(self, url, **kwargs): return Response()
    monkeypatch.setattr(api, "prepare_tls", lambda: ("verified-test-bundle", {}))
    monkeypatch.setattr(api.requests, "Session", Session)
    client = api.OfficialClient()
    with pytest.raises(ValueError, match="SOURCE_IDENTITY"): client.fetch("trend")
    assert client.requests[0]["location"] == "https://other.example/data"


def test_dynamic_second_parent_cutoff(api, synthetic_store):
    root, _, folder = synthetic_store
    api.apply_stage(root, folder, "synthetic-git")
    parent = api.read_parent(root)
    info = api.read_json(folder / "stage.json")
    info.update(parentSnapshotId=parent["snapshotId"], oldCutoff=parent["cutoff"], runId="second")
    second = folder.parent / "second"
    second.mkdir()
    for code in parent["names"]:
        path = second / (code + ".json")
        path.write_bytes(payload([bar(code=code), bar("2026-09-21", code=code, bargainamount=None),
                                 bar("2026-09-22", code=code)]))
        info["files"][code]["responseHash"] = api.sha(path)
    api.atomic_json(second / "stage.json", info)
    result = api.apply_stage(root, second, "synthetic-git")
    assert result["audit"]["oldCutoff"] == "2026-09-21" and result["audit"]["totalOverlapRows"] == 4
    current = api.read_parent(root)
    assert current["cutoff"] == "2026-09-22" and current["rowCount"] == 6
    assert current["manifest"]["parentSnapshotId"] == parent["snapshotId"]


def test_http_block_is_not_schema_drift_or_success(api):
    class Client:
        tls = {"tlsMode": "SYNTHETIC"}
        requests = []
        def catalog(self): raise ValueError("OFFICIAL_ENDPOINT_BLOCKED: HTTP 508")
        def fetch(self, *args, **kwargs): raise ValueError("OFFICIAL_ENDPOINT_BLOCKED: HTTP 508")
    health = api.probe(Client(), {"names": {"801012": "synthetic"}})
    assert health["status"] == "OFFICIAL_ENDPOINT_BLOCKED"
    assert health["schemaCompatible"] is None and health["trendSchemaStatus"] == "NOT_RUN"


def test_staged_run_id_escape_rejected(api, synthetic_store):
    root, parent, folder = synthetic_store
    info = api.read_json(folder / "stage.json")
    info["runId"] = "../../escape"
    api.atomic_json(folder / "stage.json", info)
    with pytest.raises(ValueError, match="RUN_ID"): api.apply_stage(root, folder, "synthetic-git")
    assert api.read_parent(root)["snapshotId"] == parent["snapshotId"]


def test_final_manifest_gate_precedes_materialization(api, synthetic_store):
    root, parent, folder = synthetic_store
    audit, delta = api.audit_stage(root, parent, folder)
    candidate = api.prepare_candidate(root, parent, folder, audit, delta, "synthetic-git")
    candidate["manifest"]["processedPath"] = "data/other-target"
    with pytest.raises(ValueError, match="final manifest"): api.publish(root, parent, candidate)
    assert not (root / api.LINEAGE / "current.json").exists()


def test_corrupt_orphan_base_manifest_never_becomes_parent(api, synthetic_store):
    root, parent, folder = synthetic_store
    base_path = root / api.LINEAGE / (parent["baseId"] + ".json")
    api.durable_bytes(base_path, b'{"corrupted":"orphan"}\n')
    with pytest.raises(ValueError, match="golden manifest"):
        api.apply_stage(root, folder, "synthetic-git")
    assert not (root / api.LINEAGE / "current.json").exists()
    assert api.read_parent(root)["snapshotId"] == parent["snapshotId"]
