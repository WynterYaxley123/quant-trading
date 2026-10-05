"""Synthetic-only formal lifecycle; no production namespace or market downloads."""

from dataclasses import replace
from datetime import timedelta

import pytest
from test_b40_runtime_dry_run import _book, _setup
from test_shadow import advance, read

from strategies.etf_quant.runtime import formal
from strategies.etf_quant.runtime.oneshot import one_shot
from strategies.etf_quant.runtime.storage import GateError


def setup(tmp_path, cash=False):
    p, reg, rows, book = _setup(tmp_path)
    # Explicit synthetic calendar, not a weekday-derived production calendar.
    for name, table in p.tables.items():  # noqa: B007 -- Retain established loop identity for provenance review.
        for col in ("trade_date", "as_of_date"):
            if col in table:
                table[col] = table[col].map(lambda d: d + timedelta(days=7))
    p.cutoff += timedelta(days=7)
    p.created_at += timedelta(days=7)
    p.sessions = tuple(d + timedelta(days=7) for d in p.sessions)
    if cash:
        reg = replace(reg, entries=())
        book = _book(tmp_path, [])
    contract = formal.FormalContract(
        "SYNTHETIC_CANDIDATE",
        "1" * 64,
        "SYNTHETIC_REGISTRY",
        "2" * 64,
        reg.sha256,
        book.sha256,
        "2026-09-29T22:00:00+08:00",
        p.manifest["source_commit"],
    )
    return p, reg, book, contract


def run(p, reg, book, contract, root):
    return one_shot(
        p,
        reg,
        root,
        now=p.created_at + timedelta(hours=1),
        code_commit="d" * 40,
        formal_contract=contract,
        pit_evidence=book,
        classification_version="SWCLASS2021",
    )


def test_formal_t0_epoch_signal_intent_atomic_and_idempotent(tmp_path):
    p, reg, book, contract = setup(tmp_path)
    root = tmp_path / "SYNTHETIC_FORMAL"
    result = run(p, reg, book, contract, root)
    assert result["status"] == "STARTED"
    view, state = read(root)
    epoch = state["shadow_epoch"]
    assert epoch["first_signal_date"] == str(p.cutoff)
    assert epoch["candidate_hash"] == contract.candidate_hash
    assert epoch["initial_cash"] == "10000" and epoch["initial_positions"] == []
    assert state["epoch"] is state["portfolio"] is None  # Accounting has not started.
    assert state["pending"]["epoch_id"] == epoch["epoch_id"]
    assert state["pending"]["signal_id"] == state["formal_signal"]["signal_id"]
    assert len(state["formal_signal"]["top5"]) == 5
    assert len(state["formal_signal"]["model_hashes"]) == 3
    assert view["trades"] == view["nav"] == []
    before = (root / "latest.json").read_bytes()
    assert run(p, reg, book, contract, root)["status"] == "ALREADY_PROCESSED"
    assert (root / "latest.json").read_bytes() == before
    assert len(list((root / "runs").iterdir())) == 1
    assert epoch["simulation_only"] and not epoch["broker_enabled"] and not epoch["real_order_path"]


def test_all_cash_is_valid_epoch_no_order(tmp_path):
    p, reg, book, contract = setup(tmp_path, cash=True)
    root = tmp_path / "SYNTHETIC_CASH"
    assert run(p, reg, book, contract, root)["status"] == "STARTED"
    view, state = read(root)
    assert state["shadow_epoch"]["cash_weight"] == pytest.approx(1)
    assert state["shadow_epoch"]["risk_asset_weight"] == 0
    assert state["pending"] is None and state["formal_signal"]["t1_status"] == "NO_ORDER"
    assert view["status"]["phase"] == "SHADOW_CASH_ONLY"


def test_t1_accounting_references_same_immutable_t0_epoch(tmp_path):
    p, reg, book, contract = setup(tmp_path)
    root = tmp_path / "SYNTHETIC_FORMAL"
    run(p, reg, book, contract, root)
    _, initial = read(root)
    q = advance(p)
    for name in ("etf_bars", "trading_status"):
        old = p.tables[name].loc[p.tables[name].trade_date == p.cutoff].copy()
        old["trade_date"] = q.cutoff
        import pandas as pd

        q.tables[name] = pd.concat([p.tables[name], old], ignore_index=True)
    assert run(q, reg, book, contract, root)["status"] == "STARTED"
    view, state = read(root)
    assert state["shadow_epoch"] == initial["shadow_epoch"]
    assert state["epoch"]["shadow_epoch_id"] == initial["shadow_epoch"]["epoch_id"]
    assert state["trades"] and all(
        t["shadow_epoch_id"] == state["shadow_epoch"]["epoch_id"] for t in state["trades"]
    )
    assert all(
        t["economic_execution_at"] < t["evidence_available_at"] <= t["processed_at"]
        for t in state["trades"]
    )
    assert len(state["nav"]) == 1 and state["nav"][0]["timestamp"] == state["epoch"]["started_at"]


def test_missed_t1_retires_old_epoch_without_fill_and_continues_current_signal(tmp_path):
    p, reg, book, contract = setup(tmp_path)
    root = tmp_path / "SYNTHETIC_MISSED_V1"
    run(p, reg, book, contract, root)
    _, old = read(root)
    q = advance(advance(p))
    import pandas as pd

    for name in ("etf_bars", "trading_status"):
        rows = p.tables[name].loc[p.tables[name].trade_date == p.cutoff].copy()
        rows["trade_date"] = q.cutoff
        q.tables[name] = pd.concat([q.tables[name], rows], ignore_index=True)
    result = run(q, reg, book, contract, root)
    assert result["status"] == "STARTED"
    view, state = read(root)
    assert state["recovery_events"][0]["original_intent"] == old["pending"]
    assert state["terminal_epochs"][0]["epoch_id"] == old["shadow_epoch"]["epoch_id"]
    assert state["terminal_epochs"][0]["fillable"] is False
    assert state["shadow_epoch"]["epoch_id"].endswith("0002")
    assert state["formal_signal"]["signal_date"] == str(q.cutoff)
    # The synthetic evidence expires before this session: cash is the lawful
    # next signal, rather than weakening its mapping gate to create an order.
    assert state["pending"] is None
    assert state["formal_signal"]["cash_weight"] == pytest.approx(1)
    assert view["trades"] == view["nav"] == []
    before = (root / "latest.json").read_bytes()
    assert run(q, reg, book, contract, root)["status"] == "ALREADY_PROCESSED"
    assert (root / "latest.json").read_bytes() == before


@pytest.mark.parametrize(
    "mutation,status",
    [
        ("preclose", "WAITING_FOR_MARKET_CLOSE"),
        ("old_cutoff", "WAITING_FOR_FINALIZED_DATA"),
        ("future_export", "WAITING_FOR_FINALIZED_DATA"),
        ("future_pit", "WAITING_FOR_PIT_EVIDENCE"),
        ("non_session", "READY_NO_SIGNAL"),
        ("source", "BLOCKED_INTEGRITY"),
    ],
)
def test_waiting_and_invalid_source_do_not_publish_business_state(tmp_path, mutation, status):
    p, reg, book, contract = setup(tmp_path)
    now = p.created_at + timedelta(hours=1)
    if mutation == "preclose":
        now = now.replace(hour=14)
    if mutation == "old_cutoff":
        p.cutoff -= timedelta(days=1)
    if mutation == "future_export":
        p.created_at = now + timedelta(hours=1)
    if mutation == "future_pit":
        contract = replace(contract, available_from=(now + timedelta(hours=1)).isoformat())
    if mutation == "non_session":
        p.sessions = tuple(d for d in p.sessions if d != p.cutoff)
    if mutation == "source":
        p.manifest["source_commit"] = "WRONG"
    root = tmp_path / "SYNTHETIC_WAIT"
    result = one_shot(
        p,
        reg,
        root,
        now=now,
        code_commit="d" * 40,
        formal_contract=contract,
        pit_evidence=book,
        classification_version="SWCLASS2021",
    )
    assert result["status"] == status and not root.exists()


def test_historical_backfill_duplicate_signal_and_provenance_drift_rejected(tmp_path):
    p, reg, book, contract = setup(tmp_path)
    backdated = replace(contract, available_from=p.created_at.isoformat())
    assert run(p, reg, book, backdated, tmp_path / "BACKFILL")["status"] == "BLOCKED_INTEGRITY"
    root = tmp_path / "SYNTHETIC_FORMAL"
    run(p, reg, book, contract, root)
    view, state = read(root)
    with pytest.raises(GateError, match="DUPLICATE_FORMAL_SIGNAL"):
        formal.record_signal(
            state,
            view,
            view["mappings"],
            contract,
            now=p.created_at,
            code_commit="d" * 40,
            strategy_hash="s",
        )
    before = (root / "latest.json").read_bytes()
    assert (
        run(p, reg, book, replace(contract, candidate_hash="f" * 64), root)["status"]
        == "BLOCKED_INTEGRITY"
    )
    assert (root / "latest.json").read_bytes() == before


def test_candidate_readonly_hash_and_fail_closed(tmp_path):
    p, reg, book, contract = setup(tmp_path)
    candidate = tmp_path / "candidate.json"
    registry = tmp_path / "pit_registry.json"
    candidate.write_bytes(b'{"synthetic":true}')
    registry.write_bytes(b"{}")
    before = candidate.read_bytes()
    with pytest.raises(GateError, match="CERTIFIED_INPUT_HASH"):
        formal.load_formal_contract(candidate, registry, reg, book)
    assert candidate.read_bytes() == before
