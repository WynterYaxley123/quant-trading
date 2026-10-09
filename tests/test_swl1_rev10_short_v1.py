"""Synthetic fixed-rule mathematics, private hash gates and prospective integration."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from examples.prospective_evidence_demo.fixture import event, observation, observed_payload, setup
from research.evidence.contracts import Denied, canonical, sha
from research.evidence.ledger import EvidenceLedger
from research.evidence.prospective import activation, maturity
from research.swl1_failure_forensics.boundary import sha as file_sha
from research.swl1_rev10_short_v1 import CODES, rank, score, summarize_ranking
from research.swl1_rev10_short_v1.prospective import ProspectiveAdapter
from research.swl1_rev10_short_v1.replay import load_spec, replay, write
from research.swl1_rev10_short_v1.review import build_review, private_preview
from research.swl1_short_horizon_exploration.signals import reversal_features

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    returns = np.random.default_rng(72).normal(0, 0.025, (25, 30))
    returns[0] = np.nan
    dates = tuple(pd.bdate_range("2023-01-02", periods=25).strftime("%Y-%m-%d"))
    return returns, dates


def test_exact_arithmetic_formula_and_existing_parity():
    returns, dates = fixture()
    values = score(returns, dates, CODES, asof=dates[-1], cutoff=dates[-1])
    np.testing.assert_allclose(values["rev10_score"], -returns[-10:].mean(axis=0), rtol=0, atol=0)
    np.testing.assert_allclose(values["rev10_score"], reversal_features(returns)[-1, :, 1])
    assert not np.allclose(values["rev10_score"], -(np.prod(1 + returns[-10:], axis=0) - 1))
    np.testing.assert_allclose(values["trailing_mean_return"], -values["rev10_score"])
    assert abs(values["relative_score"].sum()) < 1e-15
    assert rank(values["rev10_score"]) == rank(values["relative_score"])


@pytest.mark.parametrize("poison", [np.nan, np.inf, -1e100, 1e100])
def test_future_T_plus_one_never_enters_score(poison):
    returns, dates = fixture()
    base = score(returns, dates, CODES, asof=dates[15], cutoff=dates[15])
    returns[16:] = poison
    changed = score(returns, dates, CODES, asof=dates[15], cutoff=dates[15])
    for key in base:
        np.testing.assert_array_equal(base[key], changed[key])


def test_T_close_matters_and_warmup_6_11_unchanged():
    returns, dates = fixture()
    with pytest.raises(ValueError, match="SEED_WARMUP"):
        score(returns, dates, CODES, asof=dates[10], cutoff=dates[10])
    score(returns, dates, CODES, asof=dates[11], cutoff=dates[11])
    original = score(returns, dates, CODES, asof=dates[15], cutoff=dates[15])
    returns[15, 0] += 0.02
    assert score(returns, dates, CODES, asof=dates[15], cutoff=dates[15])["rev10_score"][
        0
    ] == pytest.approx(original["rev10_score"][0] - 0.002)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf, -1.0])
def test_incomplete_window_refused(bad):
    returns, dates = fixture()
    returns[-4, 3] = bad
    with pytest.raises(ValueError, match="FINITE_RETURNS"):
        score(returns, dates, CODES, asof=dates[-1], cutoff=dates[-1])


def test_fixed_universe_asof_and_order_refused():
    returns, dates = fixture()
    for codes, values in (
        (CODES[:-1], returns[:, :-1]),
        (CODES[::-1], returns),
        (CODES, returns.astype(np.float32)),
    ):
        with pytest.raises(ValueError):
            score(values, dates, codes, asof=dates[-1], cutoff=dates[-1])
    for spine, asof, cutoff in (
        (dates[::-1], dates[-1], dates[-1]),
        (dates, dates[-1], dates[-2]),
        (dates, "2023-99-99", dates[-1]),
    ):
        with pytest.raises(ValueError):
            score(returns, spine, CODES, asof=asof, cutoff=cutoff)


def test_stable_ties_bottom_direction_and_unknown_names():
    raw = np.zeros(30)
    assert rank(raw) == list(range(30)) and rank(raw, ascending=True) == list(range(30))
    raw[0], raw[-1] = -0.2, 0.2
    result = summarize_ranking(
        {"rev10_score": raw, "relative_score": raw - raw.mean(), "trailing_mean_return": -raw},
        names={},
        asof="2023-01-20",
        source_generation="synthetic",
    )
    assert result["count"] == 30 and result["top5"][0]["industry_code"] == CODES[-1]
    assert result["bottom5"][0]["industry_code"] == CODES[0]
    assert all(
        r["industry_name"] == r["industry_code"] and not r["name_verified"] for r in result["rows"]
    )


def test_corrupted_private_manifest_denied_before_numeric_or_json_read(tmp_path):
    write(tmp_path / "manifest.json", {"not": "authorized"})
    with pytest.raises(ValueError, match="PIN_MISMATCH"):
        private_preview(ROOT, tmp_path, "a" * 64)


def test_replay_pins_before_any_numeric_source_read(tmp_path):
    view = tmp_path / "view"
    view.mkdir()
    (view / "metadata.json").write_bytes(b"{}")
    (view / "returns.npy").write_bytes(b"must never decode")
    with pytest.raises(ValueError, match="VIEW_HASH_MISMATCH"):
        replay(ROOT, view, tmp_path / "preview")
    assert not (tmp_path / "preview").exists()


def test_offline_aggregates_without_private_preview(tmp_path):
    result = build_review(ROOT, tmp_path / "review")
    assert result["ranking_count"] == 0
    html = (tmp_path / "review/index.html").read_text()
    assert "+0.055633" in html and "+0.048998" in html
    assert "排名不可用" in html and "EXPLORATORY_POST_HOC" in html
    assert "cdn." not in html and "<script src=" not in html
    manifest = json.loads((tmp_path / "review/delivery-manifest.json").read_text())
    assert len(manifest["files"]) == 7 and manifest["preview_manifest_sha256"] is None


def synthetic_preview(tmp_path):
    """Private artifact contract fixture, explicitly unrelated to historical real returns."""
    spec, model_hash = load_spec(ROOT)
    returns, dates = fixture()
    names = {
        row["code"]: row["name"]
        for row in json.loads((ROOT / spec["universe_file"]).read_text())["metadata"]
    }
    ranking = summarize_ranking(
        score(returns, dates, CODES, asof=dates[-1], cutoff=dates[-1]),
        names=names,
        asof=dates[-1],
        source_generation="SYNTHETIC_ONLY_TEST_FIXTURE",
    )
    preview = tmp_path / "preview"
    preview.mkdir()
    write(preview / "ranking.json", ranking)
    write(
        preview / "scores.json", {"rows": sorted(ranking["rows"], key=lambda r: r["industry_code"])}
    )
    write(
        preview / "observation.json",
        {
            "status": "HISTORICAL_REPLAY",
            "namespace": "RESEARCH_REPLAY_ONLY",
            "formal_forecast": False,
            "future_numeric_rows_read": 0,
            "asof": dates[-1],
            "cutoff": spec["historical_cutoff"],
            "input_sha256": spec["view_sha256"],
            "names_reference_sha256": spec["universe_sha256"],
            "window_sessions": dates[-10:],
            "source_generation": "SYNTHETIC_ONLY_TEST_FIXTURE",
        },
    )
    manifest = {
        "namespace": "RESEARCH_REPLAY_ONLY",
        "model_hash": model_hash,
        "asof": dates[-1],
        "count": 30,
        "source_commit": spec["source_commit"],
        "files": {
            name: file_sha(preview / name)
            for name in ("observation.json", "ranking.json", "scores.json")
        },
        "implementation_sha256": {
            name: file_sha(ROOT / "research/swl1_rev10_short_v1" / name)
            for name in ("model.py", "replay.py")
        },
    }
    write(preview / "manifest.json", manifest)
    return preview, manifest, ranking


def test_offline_full_synthetic_preview_and_source_receipt(tmp_path):
    preview, _, ranking = synthetic_preview(tmp_path)
    result = build_review(ROOT, tmp_path / "review", preview, file_sha(preview / "manifest.json"))
    assert result["ranking_count"] == 30
    html = (tmp_path / "review/index.html").read_text()
    assert all(row["industry_code"] in html for row in ranking["rows"])
    assert "SYNTHETIC_ONLY_TEST_FIXTURE" in html
    assert "RESEARCH_REPLAY_ONLY" in html and "data-filter" in html
    receipt = json.loads((tmp_path / "review/delivery-manifest.json").read_text())
    assert receipt["files"]["index.html"] == file_sha(tmp_path / "review/index.html")
    assert "docs/research/swl1-rev10-preregistration-draft.zh-CN.md" in receipt["source_sha256"]


@pytest.mark.parametrize("corruption", ["name", "centering", "top5", "incomplete", "window"])
def test_offline_rehashed_inconsistent_artifacts_fail_closed(tmp_path, corruption):
    preview, manifest, ranking = synthetic_preview(tmp_path)
    if corruption == "name":
        ranking["rows"][0]["industry_name"] = "fabricated"
    elif corruption == "centering":
        ranking["rows"][0]["relative_score"] += 1
    elif corruption == "top5":
        ranking["top5"] = ranking["rows"][1:6]
    elif corruption == "incomplete":
        ranking["rows"].pop()
    else:
        observation = json.loads((preview / "observation.json").read_text())
        observation["window_sessions"].pop()
        write(preview / "observation.json", observation)
        manifest["files"]["observation.json"] = file_sha(preview / "observation.json")
    write(preview / "ranking.json", ranking)
    manifest["files"]["ranking.json"] = file_sha(preview / "ranking.json")
    write(preview / "manifest.json", manifest)
    with pytest.raises(ValueError, match="PRIVATE_PREVIEW"):
        private_preview(ROOT, preview, file_sha(preview / "manifest.json"))


def domain(tmp_path, *, active=True, facts=11):
    authority, registry, original, calendar, original_anchor = setup()
    protocol = replace(
        original, family_id="swl1_rev10_short_v1", model_universe=CODES, horizons=(10, 5)
    )
    anchor = authority.issue(
        "anchor", {**authority.verify(original_anchor, "anchor"), "protocol_hash": protocol.digest}
    )
    ledger = EvidenceLedger(
        tmp_path / "prospective" / "synthetic-rev10", protocol, registry, authority
    )

    def append(ident, kind, stamp, payload):
        body = event(protocol, kind, stamp, payload)
        ledger.append(ident, body, authority.issue("event", {"body_hash": sha(canonical(body))}))

    if active:
        append(
            "register",
            "PROTOCOL_REGISTERED",
            "2028-01-03T16:00:00+08:00",
            {"calendar": calendar.as_dict()},
        )
        append("admit", "SOURCE_ADMITTED", "2028-01-03T16:01:00+08:00", {})
        append(
            "activate",
            "ACTIVATION_BOUND",
            "2028-01-03T16:02:00+08:00",
            {
                "anchor": anchor.as_dict(),
                "first_session": activation(protocol, anchor, calendar, authority),
            },
        )
        for day in protocol.sessions[1 : facts + 1]:
            receipt = observation(protocol, registry, day)
            append(
                "observed-" + day,
                "FACT_SNAPSHOT_OBSERVED",
                day + "T16:05:00+08:00",
                observed_payload(receipt, authority),
            )
            append(
                "finalized-" + day,
                "FACT_FINALIZED",
                day + "T16:06:00+08:00",
                {"session": day, "receipt_hash": receipt.digest},
            )
    _, model_hash = load_spec(ROOT)
    return ledger, ProspectiveAdapter(ledger, model_hash), calendar, anchor


def test_production_and_unregistered_real_publication_denied(tmp_path):
    with pytest.raises(Denied, match="SIGNATURE_AUTHORITY"):
        ProspectiveAdapter.production()
    ledger, adapter, _, _ = domain(tmp_path, active=False)
    returns = np.zeros((11, 30))
    dates = ledger.protocol.sessions[1:12]
    proof = ledger.authority.issue("rev10_view", {})
    with pytest.raises(Denied, match="ACTIVATION"):
        adapter.infer(returns, dates, dates[-1], proof)
    with pytest.raises(Denied, match="REAL_FORECAST"):
        adapter.publish_real_forecast()


def test_authenticated_synthetic_inference_and_view_tampering(tmp_path):
    ledger, adapter, _, _ = domain(tmp_path)
    returns = np.random.default_rng(30).normal(0, 0.01, (11, 30))
    dates = ledger.protocol.sessions[1:12]
    status = ledger.status()
    claims = {
        "scope": "SYNTHETIC_ONLY",
        "protocol_hash": ledger.protocol.digest,
        "model_hash": adapter.model_hash,
        "source_hash": ledger.protocol.source_digest,
        "asof": dates[-1],
        "universe_hash": ledger.protocol.universe_hash,
        "dates_hash": sha(canonical(dates)),
        "payload_hash": sha(returns.tobytes()),
        "facts_hash": sha(canonical([status["finalized"][day].digest for day in dates])),
    }
    proof = ledger.authority.issue("rev10_view", claims)
    result = adapter.infer(returns, dates, dates[-1], proof)
    assert (
        result["count"] == 30
        and result["namespace"] == "SYNTHETIC_ONLY"
        and result["formal_forecast"] is False
    )
    np.testing.assert_allclose(
        [r["rev10_score"] for r in sorted(result["rows"], key=lambda r: r["industry_code"])],
        -returns[-10:].mean(axis=0),
    )
    returns[5, 3] += 0.1
    with pytest.raises(Denied, match="VIEW_MISMATCH"):
        adapter.infer(returns, dates, dates[-1], proof)
    with pytest.raises(Denied, match="BACKFILL"):
        adapter.infer(returns, (ledger.protocol.sessions[0], *dates[1:]), dates[-1], proof)


@pytest.mark.parametrize("horizon", [5, 10])
def test_exact_H5_H10_maturity_and_revision_quarantine(tmp_path, horizon):
    ledger, _, _, _ = domain(tmp_path, facts=22)
    status = ledger.status()
    signal = ledger.protocol.sessions[11]
    proofs = {
        day: ledger.authority.issue("fact", {"receipt_hash": receipt.digest})
        for day, receipt in status["finalized"].items()
    }
    args = dict(
        authorized_phase="development",
        registry=ledger.registry,
        authority=ledger.authority,
        first_session=status["first_session"],
        fact_proofs=proofs,
    )
    result = maturity(
        ledger.protocol, signal, horizon, status["finalized"], quarantined=set(), **args
    )
    assert (
        result["status"] == "MATURED"
        and result["maturity_session"] == ledger.protocol.sessions[11 + horizon]
    )
    blocked = maturity(
        ledger.protocol,
        signal,
        horizon,
        status["finalized"],
        quarantined={ledger.protocol.sessions[12]},
        **args,
    )
    assert blocked["status"] == "PENDING_MATURITY"
    incomplete = dict(status["finalized"])
    incomplete.pop(ledger.protocol.sessions[11 + horizon])
    assert (
        maturity(ledger.protocol, signal, horizon, incomplete, quarantined=set(), **args)["status"]
        == "PENDING_MATURITY"
    )
