"""Synthetic forward contracts and pre-transition numerical parity; no private facts."""

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta
from types import ModuleType, SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from strategies.etf_quant.runtime.industry import IndustrySeries
from strategies.etf_quant.runtime.prediction import current_predictions
from strategies.etf_quant.runtime.storage import digest, json_bytes
from strategies.etf_quant_v2.facts import ForwardFacts, factors_from_closes
from strategies.swl2_ridge import ledger
from strategies.swl2_ridge.adapter import prediction, v1_prediction, v2_specification
from strategies.swl2_ridge.engine import (
    SHANGHAI,
    first_session,
    mature,
    publication_gate,
    publish,
    view,
)
from strategies.swl2_ridge.facts import SERIES_TYPE, TARGET
from strategies.swl2_ridge.metrics import aggregate, compare, evaluate
from strategies.swl2_ridge.registry import ROOT, families, resolve, verify_model
from strategies.swl2_ridge.retirement import guard_legacy_write


@pytest.fixture(scope="module")
def synthetic():
    family = resolve("swl2-ridge-v1")
    codes = family["industry_codes"]
    days = tuple(d.date() for d in pd.bdate_range("2024-01-02", "2028-07-31"))
    signal = datetime(2028, 1, 4, 16, tzinfo=SHANGHAI)
    index = days.index(signal.date())
    rng = np.random.default_rng(951)
    closes = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.008, (len(days), len(codes))), axis=0))
    frame = pd.DataFrame(closes, index=pd.DatetimeIndex(days), columns=codes)
    return family, days, signal, index, frame


def inputs_at(synthetic, day):
    family, days, _, _, frame = synthetic
    now = datetime.combine(day, datetime.min.time().replace(hour=16), SHANGHAI)
    prefix = frame.loc[: str(day)]
    codes = family["industry_codes"]
    provider = SimpleNamespace(
        cutoff=day, created_at=now, model_input_contract={"industries": codes}
    )
    inputs = {
        "calendar": days,
        "cutoff": day,
        "available_at": now,
        "series": IndustrySeries(prefix, (), tuple(codes)),
        "provider": provider,
        "closes": prefix,
        "segments": None,
        "names": {c: f"Synthetic {c}" for c in codes},
        "taxonomy_identity": family["taxonomy_identity"],
        "provenance": {
            "data_source": "SYNTHETIC_ADMITTED_SOURCE_C",
            "source_commit": "a" * 40,
            "snapshot_sha256": "b" * 64,
            "data_cutoff": str(day),
            "available_at": now.isoformat(),
            "realized_series_type": SERIES_TYPE,
            "historical_membership": "RECONSTRUCTED",
        },
    }
    inputs["provenance"]["signal_levels_hash"] = digest(
        json_bytes(prefix.loc[str(day), sorted(codes)].to_dict())
    )
    return inputs, now


def binding(family, now):
    return {
        "schema_version": 1,
        "family_id": family["family_id"],
        "source_commit": "d" * 40,
        "merge_commit": "e" * 40,
        "merge_at": (now - timedelta(days=4)).isoformat(),
        "freeze_at": (now - timedelta(days=1)).isoformat(),
        "model_contract_hash": family["model_contract_hash"],
    }


def synthetic_prediction(family):
    rows = [
        {
            "industry_code": c,
            "industry_name": f"Synthetic {c}",
            "fused_rank": i + 1,
            "fused_score": float(len(family["industry_codes"]) - i),
            "horizons": {
                str(h): {
                    "raw_prediction": float(-i),
                    "cross_section_zscore": float(-i),
                    "rank": i + 1,
                }
                for h in (10, 40, 120)
            },
        }
        for i, c in enumerate(family["industry_codes"])
    ]
    return {"cross_section": rows, "models": []}


def publish_synthetic(tmp_path, synthetic):
    family, _, now, _, _ = synthetic
    inputs, _ = inputs_at(synthetic, now.date())
    root = tmp_path / "industry-forecast" / family["family_id"]
    bind = binding(family, now)
    predicted = synthetic_prediction(family)
    assert publish(root, family, bind, inputs, predicted, now) == "APPENDED"
    return root, bind, inputs, predicted


def test_canonical_registry_and_frozen_pins():
    assert [f["display_name"] for f in families()] == ["SWL2-Ridge-V1", "SWL2-Ridge-V2"]
    assert all(verify_model(f) == f["model_contract_hash"] for f in families())
    assert [len(f["industry_codes"]) for f in families()] == [107, 124]
    with pytest.raises(ValueError, match="UNKNOWN"):
        resolve("V1")


def test_v1_model_invariance(synthetic):
    inputs, now = inputs_at(synthetic, synthetic[2].date())
    _, raw, fused = current_predictions(inputs["series"], inputs["provider"], signal_at=now)
    result = v1_prediction(inputs["series"], inputs["provider"], now)
    assert result["rankings"] == [(r.industry_code, r.score) for r in fused.rankings]
    for h, scores in raw.items():
        assert {p.industry_code: p.prediction for p in scores} == {
            c: v["raw_prediction"] for c, v in result["components"][str(int(h))].items()
        }
    assert result["rankings"][:5] == [(r.industry_code, r.score) for r in fused.rankings[:5]]
    actual = prediction(synthetic[0], inputs, now)["cross_section"]
    assert [(r["industry_code"], r["fused_score"]) for r in actual] == result["rankings"]
    for h, scores in dict(fused.horizon_zscores).items():
        expected = {p.industry_code: p.prediction for p in scores}
        ordered = sorted(raw[h], key=lambda p: (-p.prediction, p.industry_code))
        for row in actual:
            component = row["horizons"][str(int(h))]
            assert component["cross_section_zscore"] == expected[row["industry_code"]]
            assert component["rank"] == next(
                i + 1 for i, p in enumerate(ordered) if p.industry_code == row["industry_code"]
            )


def test_v2_model_invariance_against_actual_base_source(synthetic, monkeypatch):
    family, days, now, index, frame = synthetic
    family = resolve("swl2-ridge-v2")
    rng = np.random.default_rng(1234)
    frame = pd.DataFrame(
        100
        * np.exp(
            np.cumsum(rng.normal(0, 0.008, (len(days), family["model_universe_size"])), axis=0)
        ),
        index=pd.DatetimeIndex(days),
        columns=family["industry_codes"],
    )
    prefix = frame.iloc[: index + 1]
    forward = ForwardFacts(
        days[: index + 1],
        tuple(frame.columns),
        factors_from_closes(prefix.to_numpy(), days[: index + 1]),
        prefix.to_numpy(),
        np.zeros(prefix.shape, dtype=np.int64),
        now,
        "a" * 64,
        {},
    )
    observations, current = forward.model_inputs(now.date())
    source = subprocess.check_output(
        [
            "git",
            "show",
            json.loads(
                (ROOT / "config/research/swl2-industry-forecast-transition.json").read_bytes()
            )["base_sha"]
            + ":strategies/etf_quant_v2/runtime.py",
        ],
        cwd=ROOT,
        text=True,
    )
    module = ModuleType("strategies.etf_quant_v2.pre_transition")
    sys.modules[module.__name__] = module
    exec(compile(source, "<frozen-base-source>", "exec"), module.__dict__)
    expected = module.prepare_signal(
        v2_specification(),
        observations,
        current,
        calendar=days,
        signal_at=now,
        snapshot_available_at=now,
        finalized=True,
        mapping_pools={},
        exposure_vectors={},
        mapping_available_at=now,
    )
    inputs, _ = inputs_at(synthetic, now.date())
    inputs.update(
        observations=observations,
        current_factors=current,
        names={c: f"Synthetic {c}" for c in family["industry_codes"]},
    )
    import strategies.etf_quant_v2.runtime as legacy

    monkeypatch.setattr(
        legacy, "select_mappings", lambda *a, **k: pytest.fail("ETF mapping called")
    )
    monkeypatch.setattr(legacy, "evaluate_policy", lambda *a, **k: pytest.fail("ETF sizing called"))
    actual = prediction(family, inputs, now)
    assert [(r["industry_code"], r["fused_score"]) for r in actual["cross_section"]] == expected[
        "rankings"
    ]
    assert actual["models"] == expected["models"]
    for row in actual["cross_section"]:
        for model in expected["models"]:
            cols = [
                list(
                    __import__("strategies.etf_quant.config", fromlist=["FACTORS_19"]).FACTORS_19
                ).index(n)
                for n in model["factors"]
            ]
            value = (
                np.asarray(current[row["industry_code"]])[cols] @ np.asarray(model["coefficients"])
                + model["intercept"]
            )
            assert row["horizons"][str(model["horizon"])]["raw_prediction"] == pytest.approx(
                value, abs=1e-12
            )

    for h in (10, 40, 120):
        values = {
            r["industry_code"]: r["horizons"][str(h)]["raw_prediction"]
            for r in actual["cross_section"]
        }
        population = np.array(list(values.values()))
        ordered = sorted(values, key=lambda c: (-values[c], c))
        for row in actual["cross_section"]:
            component = row["horizons"][str(h)]
            assert component["cross_section_zscore"] == pytest.approx(
                (values[row["industry_code"]] - population.mean()) / population.std(), abs=1e-12
            )
            assert component["rank"] == ordered.index(row["industry_code"]) + 1
    assert (
        actual["cross_section"][:5]
        == sorted(actual["cross_section"], key=lambda r: r["fused_rank"])[:5]
    )


@pytest.mark.parametrize(
    "change,reason",
    [
        ("pre_transition", "PRE_TRANSITION"),
        ("historical", "RETROSPECTIVE"),
        ("future_cutoff", "FUTURE"),
        ("future_available", "FUTURE_FACTUAL"),
        ("partial", "FINALIZED"),
        ("calendar", "CALENDAR"),
    ],
)
def test_forward_only(synthetic, change, reason):
    family, days, now, _, _ = synthetic
    inputs, _ = inputs_at(synthetic, now.date())
    bind = binding(family, now)
    if change == "pre_transition":
        bind["freeze_at"] = now.isoformat()
    if change == "historical":
        inputs["cutoff"] = days[days.index(now.date()) - 1]
    if change == "future_cutoff":
        inputs["cutoff"] = days[days.index(now.date()) + 1]
    if change == "future_available":
        inputs["available_at"] = now + timedelta(seconds=1)
    if change == "partial":
        inputs["available_at"] = now.replace(hour=14)
    if change == "calendar":
        inputs["calendar"] = tuple(reversed(days))
    with pytest.raises(ValueError, match=reason):
        publication_gate(bind, inputs, now)


def test_dynamic_first_date_after_late_merge(synthetic):
    family, days, now, _, _ = synthetic
    bind = binding(family, now)
    bind["merge_at"] = now.isoformat()
    assert first_session(bind, days) == str(days[days.index(now.date()) + 1])
    assert first_session(bind, tuple(d for d in days if d <= now.date())) is None


def test_immutable_duplicate_and_full_cross_section(tmp_path, synthetic):
    root, bind, inputs, predicted = publish_synthetic(tmp_path, synthetic)
    before = ledger.read(root)
    assert len(before["events"][0]["body"]["cross_section"]) == 107
    assert (
        publish(root, synthetic[0], bind, inputs, predicted, synthetic[2])
        == "NOOP_ALREADY_PUBLISHED"
    )
    assert ledger.read(root) == before
    with pytest.raises(ValueError, match="FULL_FROZEN"):
        publish(
            root,
            synthetic[0],
            bind,
            inputs,
            {"cross_section": predicted["cross_section"][:5]},
            synthetic[2],
        )
    for key in ("source_commit", "model_contract_hash"):
        changed = bind | {key: "f" * len(bind[key])}
        with pytest.raises(ValueError, match="BINDING|SOURCE"):
            publish(root, synthetic[0], changed, inputs, predicted, synthetic[2])


@pytest.mark.parametrize("horizon", [10, 40, 120])
def test_exact_session_maturity_and_finalization(tmp_path, synthetic, horizon):
    root, _, _, _ = publish_synthetic(tmp_path, synthetic)
    _, days, _, index, _ = synthetic
    inputs, now = inputs_at(synthetic, days[index + horizon - 1])
    assert not any(e["horizon"] == horizon for e in mature(root, inputs, now))
    inputs, now = inputs_at(synthetic, days[index + horizon])
    inputs["available_at"] = now + timedelta(seconds=1)
    with pytest.raises(ValueError, match="FINALIZED"):
        mature(root, inputs, now)
    inputs["available_at"] = now
    missing = inputs["closes"].copy()
    missing.iloc[-1, 0] = np.nan
    inputs["closes"] = missing
    assert not any(e["horizon"] == horizon for e in mature(root, inputs, now))
    inputs, now = inputs_at(synthetic, days[index + horizon])
    events = mature(root, inputs, now)
    assert next(e for e in events if e["horizon"] == horizon)["maturity_date"] == str(
        days[index + horizon]
    )
    before = ledger.read(root)
    mature(root, inputs, now)
    assert ledger.read(root) == before


def test_missing_middle_session_does_not_bridge(tmp_path, synthetic):
    root, _, _, _ = publish_synthetic(tmp_path, synthetic)
    _, days, _, index, _ = synthetic
    inputs, now = inputs_at(synthetic, days[index + 10])
    inputs["closes"] = inputs["closes"].drop(pd.Timestamp(days[index + 3]))
    assert mature(root, inputs, now) == []


def test_revised_signal_fact_rejected(tmp_path, synthetic):
    root, _, _, _ = publish_synthetic(tmp_path, synthetic)
    _, days, now, index, _ = synthetic
    inputs, later = inputs_at(synthetic, days[index + 10])
    inputs["closes"] = inputs["closes"].copy()
    inputs["closes"].loc[str(now.date()), synthetic[0]["industry_codes"][0]] *= 1.1
    with pytest.raises(ValueError, match="REVISED"):
        mature(root, inputs, later)


def test_publication_crash_recovery_without_refit(tmp_path, synthetic, monkeypatch):
    family, _, now, _, _ = synthetic
    inputs, _ = inputs_at(synthetic, now.date())
    root = tmp_path / "industry-forecast" / family["family_id"]
    original = ledger.publish_account_generation
    from strategies.etf_quant.runtime import storage

    atomic = storage.atomic_bytes

    def crash(path, body):
        if path.name == "latest.json":
            raise RuntimeError("CRASH_BEFORE_POINTER")
        atomic(path, body)

    monkeypatch.setattr(storage, "atomic_bytes", crash)
    with pytest.raises(RuntimeError, match="CRASH"):
        publish(root, family, binding(family, now), inputs, synthetic_prediction(family), now)
    monkeypatch.setattr(storage, "atomic_bytes", atomic)
    monkeypatch.setattr(
        ledger,
        "publish_account_generation",
        lambda *a, **k: pytest.fail("retry refitted/republished"),
    )
    assert (
        publish(root, family, binding(family, now), inputs, synthetic_prediction(family), now)
        == "NOOP_ALREADY_PUBLISHED"
    )
    assert len(ledger.read(root)["events"]) == 1
    monkeypatch.setattr(ledger, "publish_account_generation", original)


def test_stale_os_lock_and_tamper(tmp_path, synthetic):
    root, bind, inputs, predicted = publish_synthetic(tmp_path, synthetic)
    (root / ".forecast.guard").write_bytes(b"stale process metadata")
    assert (
        publish(root, synthetic[0], bind, inputs, predicted, synthetic[2])
        == "NOOP_ALREADY_PUBLISHED"
    )
    state = ledger.read(root)
    run = root / "runs" / state["pointer"]["run_id"]
    (run / "events.json").write_bytes(b"{}")
    with pytest.raises(ValueError):
        ledger.read(root)


def test_python_generation_is_readable_by_node_api(tmp_path, synthetic):
    root, _, _, _ = publish_synthetic(tmp_path, synthetic)
    family, days, _, index, _ = synthetic
    inputs, now = inputs_at(synthetic, days[index + 120])
    expected = mature(root, inputs, now)
    code = "import {observe} from './services/industry-forecast-api/server.mjs'; const v=await observe(process.argv[1],JSON.parse(process.argv[2]),Number(process.argv[3])); console.log(JSON.stringify(v));"
    actual = json.loads(
        subprocess.check_output(
            [
                "node",
                "--input-type=module",
                "-e",
                code,
                str(root.parent),
                json.dumps(family),
                str(int(now.timestamp() * 1000)),
            ],
            cwd=ROOT,
            text=True,
        )
    )
    assert actual["current"]["industry_count"] == 107
    assert [
        {k: v for k, v in e.items() if k not in {"event_hash", "event_type"}}
        for e in actual["evaluations"]
    ] == expected
    assert all(
        projected["event_hash"] == digest(json_bytes(original))
        and projected["event_type"] == "EVALUATION_EVENT"
        for projected, original in zip(actual["evaluations"], expected, strict=True)
    )
    for horizon in (10, 40, 120):
        reference = aggregate(expected, horizon)
        observed = next(r for r in actual["metrics"] if r["horizon"] == horizon)
        assert observed["mean_rank_ic"] == pytest.approx(reference["mean_rank_ic"])
        assert observed["top5_bottom5_spread"] == pytest.approx(reference["top5_bottom5_spread"])


def test_namespace_symlink_rejected_before_read_or_write(tmp_path, synthetic):
    root, bind, inputs, predicted = publish_synthetic(tmp_path / "outside", synthetic)
    alias = tmp_path / "industry-forecast" / synthetic[0]["family_id"]
    alias.parent.mkdir()
    alias.symlink_to(root, target_is_directory=True)
    before = ledger.read(root)
    with pytest.raises(ValueError, match="NAMESPACE_PATH"):
        ledger.read(alias)
    with pytest.raises(ValueError, match="NAMESPACE_PATH"):
        publish(alias, synthetic[0], bind, inputs, predicted, synthetic[2])
    assert ledger.read(root) == before


def test_full_body_storage_does_not_consume_cumulative_index_budget(
    tmp_path, synthetic, monkeypatch
):
    monkeypatch.setattr(ledger, "MAX_BODY", 4096)
    root, _, _, _ = publish_synthetic(tmp_path, synthetic)
    _, days, _, index, _ = synthetic
    inputs, now = inputs_at(synthetic, days[index + 120])
    assert len(mature(root, inputs, now)) == 3
    state = ledger.read(root)
    run = root / "runs" / state["pointer"]["run_id"]
    assert (run / "events.json").stat().st_size < 4096
    assert sum(p.stat().st_size for p in (root / "objects").glob("*.json")) > 4096
    object_path = next((root / "objects").glob("*.json"))
    object_path.write_bytes(b"tampered immutable object")
    with pytest.raises(ValueError, match="OBJECT_HASH"):
        ledger.read(root)


def test_metrics_math_nulls_ties_and_common_window(synthetic):
    family = synthetic[0]
    rows = synthetic_prediction(family)["cross_section"]
    raw = {r["industry_code"]: -r["fused_rank"] / 1000 for r in rows}
    metrics = evaluate(rows, raw, 10)
    assert metrics["rank_ic"] == pytest.approx(1)
    assert metrics["top5_overlap_count"] == 5 and metrics["mean_absolute_rank_error"] == 0
    assert metrics["top5_mean_return"] == pytest.approx(-0.003)
    assert metrics["bottom5_mean_return"] == pytest.approx(-0.105)
    assert metrics["top5_bottom5_spread"] == pytest.approx(0.102)
    empty = aggregate([], 10)
    assert (
        empty["mean_rank_ic"] is None
        and empty["top5_mean_return"] is None
        and empty["matured_forecast_dates"] == 0
    )
    assert evaluate(rows, dict.fromkeys(raw, 0.1), 10)["rank_ic"] is None
    event = {
        "signal_date": "2028-01-04",
        "horizon": 10,
        "metrics": metrics,
        "taxonomy_identity": family["taxonomy_identity"],
        "target_contract": TARGET,
        "target_cross_section_hash": "a" * 64,
        "realized_series_type": SERIES_TYPE,
    }
    other = event | {"signal_date": "2028-01-05"}
    assert compare([event, other], [event], 10)["matured_common_dates"] == ["2028-01-04"]
    assert compare([event], [event], 10)["difference_v2_minus_v1"]["mean_rank_ic"] == 0
    changed = json.loads(json.dumps(event))
    changed["metrics"]["realized"][0]["realized_return"] += 0.01
    with pytest.raises(ValueError, match="TARGET_MISMATCH"):
        compare([event], [changed], 10)
    events = [event | {"signal_date": f"2028-01-{i + 1:02}"} for i in range(20)]
    assert aggregate(events, 10)["rolling"][0]["rank_ic"] == pytest.approx(1)


def test_current_path_never_calls_mapping_or_accounting(tmp_path, synthetic, monkeypatch):
    import strategies.etf_quant.mapping.partial as mapping
    import strategies.etf_quant.portfolio.policy as policy
    import strategies.etf_quant_v2.accounting as accounting

    monkeypatch.setattr(policy, "evaluate_policy", lambda *a, **k: pytest.fail("ETF policy called"))
    monkeypatch.setattr(
        accounting, "settle_t_plus_one", lambda *a, **k: pytest.fail("ETF accounting called")
    )
    for name in ("select_mappings",):
        if hasattr(mapping, name):
            monkeypatch.setattr(mapping, name, lambda *a, **k: pytest.fail("ETF mapping called"))
    root, _, inputs, _ = publish_synthetic(tmp_path, synthetic)
    predicted = prediction(synthetic[0], inputs, synthetic[2])
    assert len(predicted["cross_section"]) == 107
    public = view(root, synthetic[0])
    assert public["metrics"][0]["mean_rank_ic"] is None
    assert not any(p.name in {"account.json", "state.json", "view.json"} for p in root.rglob("*"))
    assert not any(
        k in json.dumps(public)
        for k in ('"cash"', '"nav"', '"commission"', '"slippage"', '"shares"')
    )


def test_legacy_write_retired_and_cli_has_zero_writes(tmp_path, monkeypatch):
    monkeypatch.delenv("SWL2_LEGACY_SYNTHETIC_REPLAY_ROOT")
    with pytest.raises(ValueError, match="RETIRED"):
        guard_legacy_write(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "services/etf-quant-runner/one_shot.py",
            "--config",
            str(tmp_path / "does-not-exist.json"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2 and "RETIRED" in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_runner_preflight_and_duplicate_skip_model(tmp_path, synthetic, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "forecast_runner", ROOT / "services/industry-forecast-runner/run_forecast.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    family, _, now, _, _ = synthetic
    inputs, _ = inputs_at(synthetic, now.date())
    monkeypatch.setattr(module, "load", lambda *a: inputs)
    monkeypatch.setattr(module, "prediction", lambda *a: synthetic_prediction(family))
    config = {
        "runtime_root": str(tmp_path / "industry-forecast"),
        "families": {family["family_id"]: {}},
    }
    options = dict(
        now=now,
        source_commit="d" * 40,
        merge_commit="e" * 40,
        merge_at=(now - timedelta(days=5)).isoformat(),
        dry_run=False,
        preflight=True,
    )
    module.invoke(family, config, **options)
    assert not (tmp_path / "industry-forecast").exists()
    options["preflight"] = False
    module.invoke(family, config, **options)  # freeze only, same-day publication denied
    later = now + timedelta(days=1)
    inputs, _ = inputs_at(synthetic, later.date())
    monkeypatch.setattr(module, "load", lambda *a: inputs)
    options["now"] = later
    assert module.invoke(family, config, **options)["status"] == "APPENDED"
    monkeypatch.setattr(module, "prediction", lambda *a: pytest.fail("duplicate model call"))
    assert module.invoke(family, config, **options)["status"] == "NOOP_ALREADY_PUBLISHED"
    from strategies.etf_quant.runtime.storage import GateError, process_lock

    monkeypatch.setattr(module, "load", lambda *a: pytest.fail("concurrent retry loaded facts"))
    with process_lock(tmp_path / "industry-forecast" / family["family_id"] / ".runner.guard"):
        with pytest.raises(GateError, match="CONCURRENT"):
            module.invoke(family, config, **options)


def test_taxonomy_and_frozen_universe_metadata_fail_closed(tmp_path):
    from shutil import copytree

    from strategies.swl2_ridge.registry import universe_metadata

    first, second = families()
    assert first["taxonomy_universe_size"] == second["taxonomy_universe_size"] == 134
    assert first["model_universe_size"] == 107
    assert second["model_universe_size"] == 124
    assert len(first["taxonomy_only_industries"]) == 27
    assert len(second["taxonomy_only_industries"]) == 10
    assert len(set(first["industry_codes"]) & set(second["industry_codes"])) == 107
    copytree(ROOT / "config", tmp_path / "config")
    copytree(ROOT / "strategies/etf_quant/config", tmp_path / "strategies/etf_quant/config")
    altered = json.loads(json.dumps(second))
    altered["industry_codes"] = altered["industry_codes"][:-1]
    with pytest.raises(ValueError, match="UNIVERSE_MISMATCH"):
        universe_metadata(altered, tmp_path)
    path = tmp_path / second["frozen_universe_reference"]["path"]
    path.write_text("{}")
    with pytest.raises(ValueError, match="REFERENCE_MISMATCH"):
        universe_metadata(second, tmp_path)


def test_family_native_targets_differ_but_common_raw_returns_compare():
    first, second = families()
    raw = {c: i / 1000 for i, c in enumerate(second["industry_codes"])}
    left = evaluate(
        synthetic_prediction(first)["cross_section"],
        {c: raw[c] for c in first["industry_codes"]},
        10,
    )
    right = evaluate(synthetic_prediction(second)["cross_section"], raw, 10)
    first_mean = np.mean([raw[c] for c in first["industry_codes"]])
    second_mean = np.mean(list(raw.values()))
    assert first_mean != second_mean
    assert left["realized"][0]["scientific_target"] == pytest.approx(
        raw[first["industry_codes"][0]] - first_mean
    )
    assert right["realized"][0]["scientific_target"] == pytest.approx(
        raw[second["industry_codes"][0]] - second_mean
    )

    def event(metrics):
        return dict(
            signal_date="2028-01-04",
            horizon=10,
            metrics=metrics,
            taxonomy_identity=first["taxonomy_identity"],
            target_contract=TARGET,
            realized_series_type=SERIES_TYPE,
        )

    result = compare([event(left)], [event(right)], 10)
    assert result["common_industry_counts"] == {"2028-01-04": 107}
    assert result["centered_target_equality_required"] is False
    assert result["raw_return_compatibility"] == "VERIFIED"
    assert result["swl2_ridge_v1"]["mean_absolute_rank_error"] is not None
    changed = json.loads(json.dumps(right))
    changed["realized"][0]["realized_return"] += 0.01
    with pytest.raises(ValueError, match="TARGET_MISMATCH"):
        compare([event(left)], [event(changed)], 10)


def test_body_and_index_limits_preserve_original_publication(tmp_path, synthetic, monkeypatch):
    root, bind, inputs, predicted = publish_synthetic(tmp_path, synthetic)
    before = ledger.read(root)
    body = dict(
        before["events"][0]["body"], signal_date="2028-01-05", oversized="x" * ledger.MAX_EVENT_BODY
    )
    with pytest.raises(ValueError, match="EVENT_SIZE_LIMIT"):
        ledger.append(root, bind, "oversized", body)
    monkeypatch.setattr(ledger, "MAX_EVENTS", 1)
    with pytest.raises(ValueError, match="EVENT_COUNT_LIMIT"):
        ledger.append(root, bind, "second", dict(body, oversized=""))
    assert ledger.read(root) == before


def test_evaluation_crash_recovers_identical_outcome(tmp_path, synthetic, monkeypatch):
    from strategies.etf_quant.runtime import storage

    root, _, _, _ = publish_synthetic(tmp_path, synthetic)
    _, days, _, index, _ = synthetic
    inputs, now = inputs_at(synthetic, days[index + 10])
    atomic = storage.atomic_bytes

    def crash(path, body):
        if path.name == "latest.json":
            raise RuntimeError("EVALUATION_CRASH")
        atomic(path, body)

    monkeypatch.setattr(storage, "atomic_bytes", crash)
    with pytest.raises(RuntimeError, match="EVALUATION_CRASH"):
        mature(root, inputs, now)
    objects = {p.name: p.read_bytes() for p in (root / "objects").iterdir()}
    monkeypatch.setattr(storage, "atomic_bytes", atomic)
    ledger.recover(root)
    recovered = ledger.read(root)
    assert len(mature(root, inputs, now)) == 1
    assert ledger.read(root) == recovered
    assert {p.name: p.read_bytes() for p in (root / "objects").iterdir()} == objects


def test_revised_evaluation_facts_fail_closed_after_maturity(tmp_path, synthetic):
    root, _, _, _ = publish_synthetic(tmp_path, synthetic)
    _, days, _, index, _ = synthetic
    inputs, now = inputs_at(synthetic, days[index + 10])
    assert len(mature(root, inputs, now)) == 1
    before = ledger.read(root)
    inputs["closes"] = inputs["closes"].copy()
    inputs["closes"].iloc[-1, 0] *= 1.001
    with pytest.raises(ValueError, match="EVALUATION_FACTS_REVISED"):
        mature(root, inputs, now)
    assert ledger.read(root) == before
