"""Synthetic date/boolean infrastructure tests. Never run F1/V0/V1 models."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import shutil

import pandas as pd
import pytest

from research import f1_validation_readiness_v1 as ready
from scripts.data.update_market_data_and_validation_readiness import export_audit
from src.data.providers.shenwan_append_only import canonical_bytes


@pytest.fixture
def context():
    # Synthetic dates ONLY; this calendar is not exported as official data.
    cal = pd.date_range("2020-01-01", periods=700, freq="D")
    dates = {ordinal: str(cal[ordinal - 1].date()) for ordinal in range(1, 461)}
    return {"calendar": cal, "ordinal_dates": dates, "structural_dates": list(dates.values()),
            "cutoff": str(cal[699].date()), "calendar_verified": True,
            "snapshot_id_value": "synthetic"}


def test_parent_19_of_60_contract(context):
    context["ordinal_dates"] = {k: v for k, v in context["ordinal_dates"].items() if k <= 239}
    result = ready.calculate_readiness(**context)
    assert result["ready"] == 19 and result["notReady"] == 41
    assert len(result["ordinals"]) == 60 and result["fullValidationReadiness"] is False
    assert result["ordinals"][19]["signalDate"] is None


@pytest.mark.parametrize("observed_count,matured", [(230, [True, False, False]),
    (260, [True, True, False]), (340, [True, True, True])])
def test_horizon_endpoint_maturity_without_values(context, observed_count, matured):
    context["cutoff"] = str(context["calendar"][observed_count].date())
    row = ready.calculate_readiness(**context)["ordinals"][0]
    assert list(row["horizonMatured"].values()) == matured
    assert row["ready"] is all(matured)


def test_all_60_ready_does_not_open_anything(context):
    result = ready.calculate_readiness(**context)
    assert result["ready"] == 60 and result["fullValidationReadiness"] is True
    assert result["nextSafeAction"] == "HUMAN_REVIEW_REQUIRED_BEFORE_FORMAL_VALIDATION_OPEN"
    assert result["validationOpeningAuthorized"] is False
    for key, value in ready.SEAL.items():
        assert result[key] == value


def test_unverified_calendar_never_ready(context):
    context["calendar_verified"] = False
    result = ready.calculate_readiness(**context)
    assert result["ready"] == 0
    assert all(row["labelEnds"]["120"] is None for row in result["ordinals"])


def test_future_calendar_placeholders_are_not_observed(context):
    context["cutoff"] = str(context["calendar"][225].date())
    result = ready.calculate_readiness(**context)
    assert result["ready"] == 0 and result["ordinals"][0]["labelEnds"]["10"] is None
    assert result["fullReadinessLabelEnd"] is None and result["nextFullReadinessDate"] is None


def test_structural_failure_blocks_mature_endpoints(context):
    context["structural_dates"] = []
    result = ready.calculate_readiness(**context)
    assert result["ready"] == 0 and result["ordinals"][0]["horizonMatured"]["120"] is True
    assert "FORMAL_STRUCTURAL_ELIGIBILITY_NOT_MET" in result["ordinals"][0]["reasonCodes"]


@pytest.mark.parametrize("defect", ["duplicate", "reverse", "intraday", "timezone", "null", "empty"])
def test_bad_calendar_rejected(context, defect):
    cal = context["calendar"]
    context["calendar"] = {"duplicate": [cal[0], cal[0]], "reverse": cal[::-1],
        "intraday": cal + pd.Timedelta(hours=1), "timezone": cal.tz_localize("UTC"),
        "null": [pd.NaT], "empty": []}[defect]
    with pytest.raises(ValueError, match="CALENDAR"):
        ready.calculate_readiness(**context)


@pytest.mark.parametrize("key", list(ready.IDENTITIES))
def test_each_frozen_hash_enforced(context, key):
    context["identities"] = {**ready.IDENTITIES, key: "changed"}
    with pytest.raises(ValueError, match="FROZEN_IDENTITY"):
        ready.calculate_readiness(**context)


def test_monotonic_append_and_determinism(context):
    old_context = {**context, "cutoff": str(context["calendar"][338].date())}
    old = ready.calculate_readiness(**old_context)
    new = ready.calculate_readiness(**context)
    ready.assert_monotonic(old, new)
    assert new["ready"] >= old["ready"]
    assert canonical_bytes(new) == canonical_bytes(ready.calculate_readiness(**context))


def test_monotonicity_rejects_loss_of_readiness(context):
    old = ready.calculate_readiness(**context)
    new = ready.calculate_readiness(**{**context, "structural_dates": []})
    with pytest.raises(ValueError, match="REGRESSION"):
        ready.assert_monotonic(old, new)


@pytest.mark.parametrize("key", ["validationOpened", "validationPerformanceRead", "validationResultsGenerated", "finalOosPerformanceRead"])
def test_monotonicity_rejects_broken_seal(context, key):
    old = ready.calculate_readiness(**context)
    new = deepcopy(old)
    new[key] = True
    with pytest.raises(PermissionError, match="SEAL"):
        ready.assert_monotonic(old, new)


def test_readiness_has_no_performance_payload(context):
    result = ready.calculate_readiness(**context)
    for key in ("returns", "predictions", "rankIC", "spread", "ranking", "labels", "model"):
        assert key not in result
    assert all(set(row) == {"ordinal", "signalDate", "labelEnds", "horizonMatured", "structuralEligible", "ready", "reasonCodes",
                           "allHorizonsMatured", "structuralDataReady", "overallReady"}
               for row in result["ordinals"])


def test_runtime_imports_no_model_or_evaluator_modules():
    code = "import sys; import research.f1_validation_readiness_v1; assert not any(n in sys.modules for n in ('research.f1_independent_validation_v1_protocol','research.sector_index_baseline','research.sector_development_baseline','strategies.sw_sector_rotation.src.model.model'))"
    subprocess.run([sys.executable, "-c", code], check=True)


def test_blocked_cycle_does_not_claim_fetch_or_snapshot(context):
    value = ready.calculate_readiness(**context)
    pre = {"parentSnapshotId": "synthetic", "oldCutoff": context["cutoff"], "provider": "synthetic"}
    manifest = ready.blocked_cycle(pre, value)
    assert manifest["updateAttempted"] is manifest["updateApplied"] is False
    assert manifest["historicalRevisions"] is manifest["overlapRowsChecked"] is None
    assert manifest["sourceLatestAvailableCutoff"] is manifest["newSnapshotId"] is None
    assert manifest["appendedRows"] == 0 and manifest["readinessDelta"] == 0


@pytest.mark.parametrize("path", ["data/processed/shenwan", "research", "reports/research/validation", "data/manifests/f1_validation_readiness_v1"])
def test_export_refuses_canonical_or_frozen_paths(tmp_path, path):
    with pytest.raises(ValueError, match="PATH"):
        export_audit(tmp_path, tmp_path / path, {"readiness.json": {}})
    assert not (tmp_path / path).exists()


def test_export_exclusive_and_deterministic(tmp_path):
    destination = tmp_path / "data/manifests/f1_validation_readiness_v1/synthetic"
    data = {"readiness.json": {"a": 1, "unknown": None}}
    export_audit(tmp_path, destination, data)
    assert (destination / "readiness.json").read_bytes() == canonical_bytes(data["readiness.json"])
    with pytest.raises(FileExistsError):
        export_audit(tmp_path, destination, data)


def test_export_filename_cannot_escape(tmp_path):
    destination = tmp_path / "data/manifests/f1_validation_readiness_v1/synthetic"
    with pytest.raises(ValueError, match="FILENAME"):
        export_audit(tmp_path, destination, {"../evil.json": {}})


def test_frozen_identity_recomputed_without_execution():
    config, split = ready.frozen_identity()
    assert config["seal"] == ready.SEAL and split["validationOrdinalIds"] == list(range(221, 281))


def test_result_audit_reads_only_owned_development_metadata(tmp_path):
    run = tmp_path / "reports/research/development/run"
    run.mkdir(parents=True)
    (run / "metadata.json").write_text(json.dumps({"phase": "DEVELOPMENT", "validation_access": "SEALED", "final_oos_access": "SEALED"}))
    (run / "predictions.csv").write_bytes(b"not parseable as CSV: never read")
    assert ready.audit_result_seals(tmp_path)["sealedResultMetadataFilesChecked"] == 1
    (run / "validation.txt").touch()
    with pytest.raises(PermissionError, match="PATH"):
        ready.audit_result_seals(tmp_path)


def test_result_audit_rejects_unowned_outputs(tmp_path):
    folder = tmp_path / "reports/research/run"
    folder.mkdir(parents=True)
    (folder / "predictions.csv").touch()
    with pytest.raises(PermissionError, match="UNOWNED"):
        ready.audit_result_seals(tmp_path)


def test_structural_calculator_matches_existing_date_only_semantics():
    # Test-only import of the old structural audit; no model call/value input.
    from research.sector_index_baseline import audit_signal_range
    cal = pd.date_range("2020-01-01", periods=950, freq="D")
    projection = pd.DataFrame([(day, code, True) for day in cal for code in ("a", "b")],
                              columns=["date", "sector_code", "is_valid_ohlc"])
    metadata = {"admission_level": "FIXED_CLASSIFICATION_RESEARCH", "strict_pit": False,
                "common_start_date": str(cal[0].date()), "common_end_date": str(cal[-1].date())}
    old = audit_signal_range(projection, ["a", "b"], metadata)
    _, new = ready.formal_eligible_dates(projection, ["a", "b"], start=metadata["common_start_date"], end=metadata["common_end_date"])
    assert len(new) == old["signal_only_session_count"]
    assert [new[0], new[-1]] == [old["signal_only_eligible_start"], old["signal_only_eligible_end"]]


def test_missing_sector_not_filled_into_structural_window():
    cal = pd.date_range("2020-01-01", periods=950, freq="D")
    projection = pd.DataFrame([(day, code, True) for day in cal for code in ("a", "b")
                              if not (code == "b" and day == cal[100])],
                              columns=["date", "sector_code", "is_valid_ohlc"])
    original = projection.copy()
    _, dates = ready.formal_eligible_dates(projection, ["a", "b"], start=str(cal[0].date()), end=str(cal[-1].date()))
    assert projection.equals(original) and dates
    assert pd.Timestamp(dates[0]) > cal[100]


@pytest.mark.parametrize("kind", ["config", "candidate", "split", "protocol_declaration", "protocol_code", "document", "core_source"])
def test_frozen_identity_rejects_actual_file_drift(tmp_path, kind):
    config, _ = ready.frozen_identity()
    paths = [f"{ready.BASE}{suffix}.json" for suffix in ("", "_candidate", "_split")]
    paths += [ready.PROTOCOL, "docs/research/shenwan_f1_independent_validation_v1.md",
              "docs/research/shenwan_f1_independent_validation_v1_selection_trace.md"]
    paths += list(config["sourceFileSha256"])
    for relative in paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ready.ROOT / relative, destination)
    selected = {"config": paths[0], "candidate": paths[1], "split": paths[2],
                "protocol_declaration": ready.PROTOCOL, "protocol_code": ready.PROTOCOL,
                "document": paths[4], "core_source": "strategies/sw_sector_rotation/src/model/model.py"}[kind]
    path = tmp_path / selected
    if kind in {"config", "candidate", "split"}:
        data = json.loads(path.read_text())
        data["unexpectedChange"] = True
        path.write_text(json.dumps(data))
    elif kind == "protocol_declaration":
        path.write_bytes(path.read_bytes().replace(ready.IDENTITIES["protocolHash"].encode(), b"0" * 64))
    else:
        path.write_bytes(path.read_bytes() + b"\n# drift\n")
    with pytest.raises(ValueError, match="FROZEN_IDENTITY"):
        ready.frozen_identity(tmp_path)


def test_readiness_only_cli_calls_no_update_or_writer(monkeypatch, context, capsys):
    from scripts.data import update_market_data_and_validation_readiness as cli
    result = ready.calculate_readiness(**context)
    pre = {"parentSnapshotId": "synthetic", "oldCutoff": context["cutoff"], "provider": "synthetic"}
    monkeypatch.setattr(cli, "inspect_parent", lambda: (pre, result))
    monkeypatch.setattr(cli, "export_audit", lambda *_: pytest.fail("unsolicited audit write"))
    assert cli.main(["--readiness-only"]) == 0
    assert json.loads(capsys.readouterr().out)["validationOpened"] is False


def test_update_cli_fails_closed_without_fetch(monkeypatch, context, capsys):
    from scripts.data import update_market_data_and_validation_readiness as cli
    result = ready.calculate_readiness(**context)
    pre = {"parentSnapshotId": "synthetic", "oldCutoff": context["cutoff"], "provider": "synthetic"}
    monkeypatch.setattr(cli, "inspect_parent", lambda: (pre, result))
    assert cli.main(["--update-append-only"]) == 2
    value = json.loads(capsys.readouterr().out)
    assert value["updateAttempted"] is False and value["fetchStatus"] == "NOT_RUN"


def test_monotonicity_rejects_changed_ordinal_date(context):
    old = ready.calculate_readiness(**context)
    new = deepcopy(old)
    new["ordinals"][0]["signalDate"] = "2001-01-01"
    with pytest.raises(ValueError, match="ORDINAL_IDENTITY"):
        ready.assert_monotonic(old, new)
