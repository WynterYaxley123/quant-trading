"""ENGINEERING_DRY_RUN_ONLY: synthetic sources and temporary Shadow roots."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from decimal import Decimal

import pytest
from test_registry_sidecar import industry_codes, registry_doc
from test_shadow import advance, inputs, read

from strategies.etf_quant.domain import IndustryRanking
from strategies.etf_quant.domain.industry_level import default_taxonomy
from strategies.etf_quant.mapping.pit import IDENTITY, load_pit_evidence, select_pit_mappings
from strategies.etf_quant.mapping.registry import load_registry
from strategies.etf_quant.runtime import shadow
from strategies.etf_quant.runtime.storage import GateError, digest, json_bytes


def _record(
    root,
    code,
    etf,
    index,
    *,
    available="2026-09-02T18:00:00+08:00",
    valid_through="2026-10-31",
    target_weight=60,
    other_weight=40,
):
    other = next(c for c in industry_codes() if c != code)
    rows = [
        {"security_code": "600001", "weight_pct": target_weight},
        {"security_code": "600002", "weight_pct": other_weight},
    ]
    classes = [
        {
            "security_code": "600001",
            "l2_code": code,
            "effective_date": "2026-09-01",
            "available_at": "2026-09-02T17:00:00+08:00",
        },
        {
            "security_code": "600002",
            "l2_code": other,
            "effective_date": "2026-09-01",
            "available_at": "2026-09-02T17:00:00+08:00",
        },
    ]
    weight_body = json_bytes({"constituents": rows, "declared_constituent_count": 2})
    class_body = json_bytes({"classifications": classes})
    root.mkdir(exist_ok=True)
    weight_file, class_file = f"weights_{index}.json", f"class_{index}.json"
    (root / weight_file).write_bytes(weight_body)
    (root / class_file).write_bytes(class_body)
    return {
        "industry_code": code,
        "etf_code": etf,
        "etf_name": "SYNTHETIC ETF",
        "benchmark_code": f"SYN_{index}",
        "weight_source_type": "OFFICIAL_WEIGHT",
        "weight_source_provider": "SYNTHETIC TEST ONLY",
        "source_publication_at": "2026-09-02T17:15:00+08:00",
        "evidence_observed_at": "2026-09-02T17:30:00+08:00",
        "available_at": available,
        "constituent_effective_date": "2026-09-01",
        "weight_effective_date": "2026-09-01",
        "valid_through": valid_through,
        "declared_constituent_count": 2,
        "weight_source_url": f"https://www.csindex.com.cn/test/{weight_file}",
        "weight_source_file": weight_file,
        "weight_source_sha256": digest(weight_body),
        "classification_source_url": f"https://www.swsresearch.com/test/{class_file}",
        "classification_source_file": class_file,
        "classification_source_sha256": digest(class_body),
        "constituents": rows,
        "classifications": classes,
    }


def _book(tmp_path, records):
    path = tmp_path / "pit_book.json"
    path.write_bytes(
        json_bytes({"schema_version": "1.0.0", "identity": IDENTITY, "records": records})
    )
    return load_pit_evidence(path, source_root=tmp_path / "official")


def _setup(tmp_path, *, expiring=False, cash_proxy=False):
    p, _ = inputs(tmp_path)
    doc, evidence = registry_doc(tmp_path)
    codes = industry_codes()
    doc["entries"] = doc["entries"][:1]
    registry_path = tmp_path / "strict_registry.json"
    registry_path.write_bytes(json_bytes(doc))
    reg = load_registry(registry_path, evidence_root=evidence)
    root = tmp_path / "official"
    rows = [
        _record(
            root,
            code,
            f"51000{i}.SH",
            i,
            valid_through=str(advance(p).cutoff) if expiring and i == 1 else "2026-10-31",
        )
        for i, code in enumerate(codes[1:4], start=1)
    ]
    if cash_proxy:
        rows.append(_record(root, codes[4], "510004.SH", 4, available="2026-09-24T17:30:00+08:00"))
    return p, reg, rows, _book(tmp_path, rows)


def _run(p, reg, book, root):
    return shadow.daily_cycle(
        p,
        reg,
        root,
        now=p.created_at + timedelta(hours=1),
        code_commit="d" * 40,
        classification_version="SWCLASS2021",
        execution_policy="B40_WITH_CASH",
        pit_evidence=book,
    )


def test_pit_future_evidence_same_day_boundary_and_listing_fail_closed(tmp_path):
    p, reg, rows, book = _setup(tmp_path, cash_proxy=True)
    ranks = tuple(IndustryRanking(i + 1, code, 5 - i) for i, code in enumerate(industry_codes()))
    t0 = p.created_at + timedelta(hours=1)
    out = select_pit_mappings(reg, ranks, p, book, signal_at=t0)
    assert len(out["slots"]) == 5 and len(out["selected"]) == 4
    assert out["slots"][-1]["etf_code"] is None  # available tomorrow, not on 2026-09-23
    same_day = deepcopy(rows)
    same_day[-1]["available_at"] = "2026-09-23T19:00:00+08:00"
    late = _book(tmp_path, same_day)
    assert select_pit_mappings(reg, ranks, p, late, signal_at=t0)["slots"][-1]["etf_code"] is None
    assert (
        select_pit_mappings(reg, ranks, p, late, signal_at=t0 + timedelta(hours=1))["slots"][-1][
            "etf_code"
        ]
        == "510004.SH"
    )
    p.tables["instruments"].loc[p.tables["instruments"].symbol == "510001.SH", "list_date"] = (
        p.cutoff + timedelta(days=1)
    )
    assert select_pit_mappings(reg, ranks, p, book, signal_at=t0)["slots"][1]["etf_code"] is None


def test_incomplete_weight_hash_and_unmapped_classification_fail_closed(tmp_path):
    p, reg, rows, _ = _setup(tmp_path)
    ranks = tuple(IndustryRanking(i + 1, code, 5 - i) for i, code in enumerate(industry_codes()))
    damaged = deepcopy(rows)
    damaged[0]["constituents"][1]["weight_pct"] = 20
    with pytest.raises(GateError, match="SCHEMA"):
        _book(tmp_path, damaged)  # extraction differs from the pinned official bytes
    root = tmp_path / "official"
    body = json_bytes({"constituents": damaged[0]["constituents"], "declared_constituent_count": 2})
    (root / damaged[0]["weight_source_file"]).write_bytes(body)
    damaged[0]["weight_source_sha256"] = digest(body)
    book = _book(tmp_path, damaged)
    assert (
        select_pit_mappings(reg, ranks, p, book, signal_at=p.created_at + timedelta(hours=1))[
            "slots"
        ][1]["etf_code"]
        is None
    )
    tampered = deepcopy(damaged)
    tampered[0]["weight_source_sha256"] = "0" * 64
    with pytest.raises(GateError, match="HASH"):
        _book(tmp_path, tampered)


def test_spoofed_official_host_and_future_classification_are_rejected(tmp_path):
    p, reg, rows, book = _setup(tmp_path)
    spoofed = deepcopy(rows)
    spoofed[0]["weight_source_url"] = "https://csindex.com.cn.evil.invalid/weights"
    with pytest.raises(GateError, match="SOURCE_IDENTITY"):
        _book(tmp_path, spoofed)
    future = deepcopy(rows)
    future[0]["classifications"][0]["available_at"] = "2026-10-01T17:00:00+08:00"
    body = json_bytes({"classifications": future[0]["classifications"]})
    (tmp_path / "official" / future[0]["classification_source_file"]).write_bytes(body)
    future[0]["classification_source_sha256"] = digest(body)
    with pytest.raises(GateError, match="CLASSIFICATION_TIME"):
        _book(tmp_path, future)


@pytest.mark.parametrize("target,other", [(39, 61), (45, 55)])
def test_b40_threshold_and_largest_are_independent_fail_closed(tmp_path, target, other):
    p, reg, rows, book = _setup(tmp_path)
    changed = deepcopy(rows)
    changed[0]["constituents"][0]["weight_pct"] = target
    changed[0]["constituents"][1]["weight_pct"] = other
    body = json_bytes({"constituents": changed[0]["constituents"], "declared_constituent_count": 2})
    (tmp_path / "official" / changed[0]["weight_source_file"]).write_bytes(body)
    changed[0]["weight_source_sha256"] = digest(body)
    changed_book = _book(tmp_path, changed)
    ranks = tuple(IndustryRanking(i + 1, code, 5 - i) for i, code in enumerate(industry_codes()))
    selected = select_pit_mappings(
        reg, ranks, p, changed_book, signal_at=p.created_at + timedelta(hours=1)
    )
    assert selected["slots"][1]["etf_code"] is None


def test_full_synthetic_t1_dry_run_four_etfs_cash_no_formal_state(tmp_path):
    p, reg, rows, book = _setup(tmp_path)
    root = tmp_path / "DRY_RUN_ONLY" / "runtime"
    first = _run(p, reg, book, root)
    assert first["status"] == "WAITING_FOR_T1_OPEN" and first["epoch"] is None
    view, state = read(root)
    assert state["pending"] and view["trades"] == view["nav"] == []
    assert len(state["pending"]["targets"]) == 4
    assert len(state["pending"]["slots"]) == 5
    assert sum(s["cash_retained_weight"] for s in state["pending"]["slots"]) == pytest.approx(
        view["mappings"]["cash_weight"]
    )
    assert view["mappings"]["cash_weight"] + view["mappings"]["risk_asset_weight"] == pytest.approx(
        1
    )
    q = advance(p)
    assert _run(q, reg, book, root)["status"] == "RUNNING"
    view, state = read(root)
    assert len(view["holdings"]) == 4 and len(view["trades"]) == 4 and len(view["nav"]) == 1
    assert all(
        t["intent"]["asset_id"] != "CASH"
        and t["market_execution_at"] < t["processed_at"]
        and t["intent_persisted_at"] < t["market_execution_at"]
        for t in view["trades"]
    )
    assert all(t["execution_price_source"] == "FINALIZED_T1_RAW_OPEN" for t in view["trades"])
    assert state["pending"] is None and state["rebalance_count"] == 1
    assert _run(q, reg, book, root)["status"] == "IDEMPOTENT_NO_CHANGE"


def test_cash_to_proxy_then_t1_buy_and_no_retroactive_intent(tmp_path):
    p, reg, rows, book = _setup(tmp_path, cash_proxy=True)
    root = tmp_path / "DRY_RUN_ONLY" / "runtime"
    _run(p, reg, book, root)
    q = advance(p)
    _run(q, reg, book, root)
    _, state = read(root)
    assert state["pending"] and len(state["pending"]["members"]) == 5
    assert any(t["reason"] == "MAPPING_BECAME_AVAILABLE" for t in state["pending"]["transitions"])
    r = advance(q)
    _run(r, reg, book, root)
    view, state = read(root)
    assert len(view["holdings"]) == 5
    assert any(
        t["intent"]["side"] == "BUY" and t["intent"]["asset_id"] == "510004.SH"
        for t in view["trades"]
    )
    assert state["pending"] is None


def test_proxy_to_cash_t1_sell_and_cash_persists(tmp_path):
    p, reg, rows, book = _setup(tmp_path, expiring=True)
    root = tmp_path / "DRY_RUN_ONLY" / "runtime"
    _run(p, reg, book, root)
    q = advance(p)
    _run(q, reg, book, root)
    _, state = read(root)
    assert len(state["pending"]["members"]) == 3
    assert any(
        t["reason"] == "LIQUIDITY_OR_EVIDENCE_FAILED" for t in state["pending"]["transitions"]
    )
    r = advance(q)
    _run(r, reg, book, root)
    view, state = read(root)
    assert any(
        t["intent"]["side"] == "SELL" and t["intent"]["asset_id"] == "510001.SH"
        for t in view["trades"]
    )
    assert len(view["holdings"]) == 3 and state["pending"] is None


def test_proxy_to_strict_precedence_and_t1_replacement(tmp_path):
    p, reg, rows, book = _setup(tmp_path)
    root = tmp_path / "DRY_RUN_ONLY" / "runtime"
    _run(p, reg, book, root)
    q = advance(p)
    doc, evidence = registry_doc(tmp_path)
    new_strict = deepcopy(doc["entries"][0])
    new_strict.update(
        industry_code=industry_codes()[1],
        industry_name=default_taxonomy().name_of(industry_codes()[1]),
        etf_code="510005.SH",
        tracking_index_code="SYN_NEW_STRICT",
        source_retrieved_at="2026-09-24T16:00:00+08:00",
        evidence_observed_at="2026-09-24T16:30:00+08:00",
        verified_at="2026-09-24T17:00:00+08:00",
        available_at="2026-09-24T17:30:00+08:00",
        effective_from="2026-09-24",
    )
    doc["entries"] = [doc["entries"][0], new_strict]
    registry_path = tmp_path / "strict_next.json"
    registry_path.write_bytes(json_bytes(doc))
    next_reg = load_registry(registry_path, evidence_root=evidence)
    _run(q, next_reg, book, root)
    _, state = read(root)
    assert "510005.SH" in state["pending"]["members"]
    assert "510001.SH" not in state["pending"]["members"]
    assert any(t["reason"] == "STRICT_SUPERSEDED_PROXY" for t in state["pending"]["transitions"])
    r = advance(q)
    _run(r, next_reg, book, root)
    view, state = read(root)
    assert any(
        t["intent"]["side"] == "SELL" and t["intent"]["asset_id"] == "510001.SH"
        for t in view["trades"]
    )
    assert any(
        t["intent"]["side"] == "BUY" and t["intent"]["asset_id"] == "510005.SH"
        for t in view["trades"]
    )


def test_proxy_a_to_b_and_no_weight_only_rebalance(tmp_path):
    p, reg, rows, book = _setup(tmp_path, expiring=True)
    root = tmp_path / "DRY_RUN_ONLY" / "runtime"
    _run(p, reg, book, root)
    q = advance(p)
    replacement = _record(
        tmp_path / "official",
        industry_codes()[1],
        "510005.SH",
        5,
        available="2026-09-24T17:30:00+08:00",
    )
    next_book = _book(tmp_path, [*rows, replacement])
    _run(q, reg, next_book, root)
    _, state = read(root)
    assert (
        "510005.SH" in state["pending"]["members"]
        and "510001.SH" not in state["pending"]["members"]
    )
    assert any(
        t["reason"] == "PROXY_OR_INSTRUMENT_REPLACED" for t in state["pending"]["transitions"]
    )


def test_strict_expiry_to_admitted_proxy(tmp_path):
    p, _, rows, _ = _setup(tmp_path)
    doc, evidence = registry_doc(tmp_path)
    doc["entries"] = doc["entries"][:1]
    doc["entries"][0]["effective_to"] = "2026-09-25"
    path = tmp_path / "expiring_strict.json"
    path.write_bytes(json_bytes(doc))
    reg = load_registry(path, evidence_root=evidence)
    proxy = _record(tmp_path / "official", industry_codes()[0], "510005.SH", 5)
    book = _book(tmp_path, [*rows, proxy])
    root = tmp_path / "DRY_RUN_ONLY" / "runtime"
    _run(p, reg, book, root)
    q = advance(p)
    _run(q, reg, book, root)
    _, state = read(root)
    assert (
        "510005.SH" in state["pending"]["members"]
        and "510000.SH" not in state["pending"]["members"]
    )
    assert any(
        t["reason"] == "STRICT_EXPIRED_PROXY_ADMITTED" for t in state["pending"]["transitions"]
    )


def test_same_day_post_decision_evidence_is_not_backdated(tmp_path):
    p, reg, rows, book = _setup(tmp_path)
    root = tmp_path / "DRY_RUN_ONLY" / "runtime"
    _run(p, reg, book, root)
    late = _record(
        tmp_path / "official",
        industry_codes()[4],
        "510004.SH",
        4,
        available="2026-09-23T19:00:00+08:00",
    )
    q = advance(p)
    next_book = _book(tmp_path, [*rows, late])
    _run(q, reg, next_book, root)
    _, state = read(root)
    assert "510004.SH" in state["pending"]["members"]
    assert state["pending"]["signal_date"] == str(q.cutoff)


def test_delayed_accounting_uses_t1_open_not_close(tmp_path):
    p, reg, rows, book = _setup(tmp_path)
    root = tmp_path / "DRY_RUN_ONLY" / "runtime"
    _run(p, reg, book, root)
    q = advance(p)
    index = q.tables["etf_bars"].index[
        (q.tables["etf_bars"].symbol == "510001.SH") & (q.tables["etf_bars"].trade_date == q.cutoff)
    ]
    q.tables["etf_bars"].loc[index, ["open", "high", "low", "close"]] = [1.2, 1.3, 0.9, 1.0]
    _run(q, reg, book, root)
    view, _ = read(root)
    fill = next(t for t in view["trades"] if t["intent"]["asset_id"] == "510001.SH")
    assert Decimal(fill["reference_open"]) == Decimal("1.2")
    assert Decimal(fill["price"]) > Decimal("1.2")
    assert fill["economic_execution_at"] == fill["market_execution_at"]
    assert fill["market_execution_at"] < fill["evidence_available_at"] <= fill["processed_at"]
    assert fill["accounting_mode"] == "DELAYED_T1_OPEN_ACCOUNTING"
    assert fill["execution_evidence"] == "NOT_REALTIME_EXECUTION_EVIDENCE"


def test_b40_all_cash_does_not_create_epoch_or_synthetic_cash_symbol(tmp_path):
    p, reg, rows, book = _setup(tmp_path)
    doc, evidence = registry_doc(tmp_path)
    doc["entries"] = []
    path = tmp_path / "empty_registry.json"
    path.write_bytes(json_bytes(doc))
    empty_reg = load_registry(path, evidence_root=evidence)
    empty_book = _book(tmp_path, [])
    root = tmp_path / "DRY_RUN_ONLY" / "runtime"
    assert _run(p, empty_reg, empty_book, root)["status"] == "CASH_ONLY_NO_EPOCH"
    view, state = read(root)
    assert view["mappings"]["cash_weight"] == pytest.approx(1)
    assert state["pending"] is state["portfolio"] is state["epoch"] is None
    assert state["members"] == [] and view["trades"] == view["nav"] == []
    assert all(slot["etf_code"] is None for slot in view["mappings"]["slots"])


def test_no_t2_substitute_and_missing_t1_bar_does_not_advance_state(tmp_path):
    p, reg, rows, book = _setup(tmp_path)
    root = tmp_path / "DRY_RUN_ONLY" / "runtime"
    _run(p, reg, book, root)
    latest = (root / "latest.json").read_bytes()
    q = advance(p)
    q.tables["etf_bars"].drop(
        q.tables["etf_bars"].index[
            (q.tables["etf_bars"].symbol == "510001.SH")
            & (q.tables["etf_bars"].trade_date == q.cutoff)
        ],
        inplace=True,
    )
    with pytest.raises(GateError, match="T1_EXECUTION_BAR"):
        _run(q, reg, book, root)
    assert (root / "latest.json").read_bytes() == latest
    r = advance(q)
    _run(r, reg, book, root)
    view, state = read(root)
    assert state["recovery_events"][0]["status"] == "ABANDONED_MISSED_T1"
    assert state["recovery_events"][0]["retroactive_fill_allowed"] is False
    assert view["trades"] == []
    assert not state["pending"] or state["pending"]["signal_date"] == str(r.cutoff)


def test_liquidity_window_never_reads_future_bar(tmp_path):
    p, reg, rows, book = _setup(tmp_path)
    ranks = tuple(IndustryRanking(i + 1, code, 5 - i) for i, code in enumerate(industry_codes()))
    t = p.created_at + timedelta(hours=1)
    before = select_pit_mappings(reg, ranks, p, book, signal_at=t)["slots"][1]["mean_amount_cny"]
    future = deepcopy(p.tables["etf_bars"].loc[p.tables["etf_bars"].symbol == "510001.SH"].iloc[-1])
    future["trade_date"] = advance(p).cutoff
    future["amount"] = 1e15
    import pandas as pd

    p.tables["etf_bars"] = pd.concat(
        [p.tables["etf_bars"], pd.DataFrame([future])], ignore_index=True
    )
    after = select_pit_mappings(reg, ranks, p, book, signal_at=t)["slots"][1]["mean_amount_cny"]
    assert after == before


def test_strict_default_and_explicit_policy_are_isolated(tmp_path):
    p, reg, rows, book = _setup(tmp_path)
    strict_root = tmp_path / "strict"
    assert (
        shadow.daily_cycle(
            p,
            reg,
            strict_root,
            now=p.created_at + timedelta(hours=1),
            code_commit="d" * 40,
            classification_version="SWCLASS2021",
        )["status"]
        == "MAPPING_ADMISSION_BLOCKED"
    )
    with pytest.raises(GateError, match="EXPLICIT_PIT"):
        shadow.daily_cycle(
            p,
            reg,
            tmp_path / "missing",
            now=p.created_at + timedelta(hours=1),
            code_commit="d" * 40,
            execution_policy="B40_WITH_CASH",
        )
    assert not (tmp_path / "missing").exists()
