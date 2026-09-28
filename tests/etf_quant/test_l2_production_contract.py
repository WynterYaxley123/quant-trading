"""Frozen L2 production contract, verified mapping, 20-session liquidity, Top5.

These tests exercise the *contracts*, not a market view: every industry code and
industry name is read from the sealed taxonomy artifact, so a test can never
assert a name the project has no evidence for.
"""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from strategies.etf_quant.domain import IndustryRanking
from strategies.etf_quant.domain.industry_level import (ETF_QUANT_INDUSTRY_LEVEL_V1,
                                                        INDUSTRY_LEVEL_WIDTH, TaxonomyError,
                                                        default_taxonomy, load_taxonomy, parse_taxonomy)
from strategies.etf_quant.mapping.liquidity import (FAIL, INSUFFICIENT, LIQUIDITY_SESSIONS, PASS,
                                                    assess_liquidity, liquidity_window)
from strategies.etf_quant.mapping.registry import load_registry, select_mappings
from strategies.etf_quant.portfolio import AllocationStatus, size_targets
from strategies.etf_quant.runtime.storage import GateError, digest, json_bytes

TZ = timezone(timedelta(hours=8))
OBSERVED = datetime(2026, 9, 28, 20, tzinfo=TZ)
SIGNAL = datetime(2026, 9, 24, 18, tzinfo=TZ)


def taxonomy():
    return default_taxonomy()


def l2_codes(count):
    """Industry codes that the sealed taxonomy both defines and names."""
    codes = list(taxonomy().named_industry_codes)
    assert len(codes) >= count, "sealed taxonomy must name the production industries"
    return codes[:count]


# --------------------------------------------------------------------------- CP1


def test_industry_level_contract_is_frozen_at_shenwan_l2():
    assert ETF_QUANT_INDUSTRY_LEVEL_V1 == "SHENWAN_L2"
    assert INDUSTRY_LEVEL_WIDTH == 4
    assert taxonomy().industry_level == ETF_QUANT_INDUSTRY_LEVEL_V1
    assert taxonomy().level_width == 4


def test_taxonomy_is_sealed_and_evidence_backed():
    tx = taxonomy()
    assert tx.source_url.startswith("https://")
    assert len(tx.source_sha256) == 64 and len(tx.sha256) == 64
    assert tx.source_retrieved_at.tzinfo is not None
    assert tx.hierarchy_evidence and all(e["statement"].strip() for e in tx.hierarchy_evidence)
    assert tx.publisher.strip()
    # The Level-3 relation is a partition: no code belongs to two Level-2 parents.
    seen = {}
    for code, children in tx.level3_children.items():
        assert len(set(children)) == len(children) and children
        for child in children:
            assert child not in seen, "Level-3 code in two Level-2 parents"
            seen[child] = code
    assert len(seen) == len(tx.level3_to_level2)
    assert len(tx.level3_children) >= 100


def test_taxonomy_resolves_by_explicit_relation_and_never_truncates():
    tx = taxonomy()
    sample = sorted(tx.level3_to_level2)[0]
    assert tx.level2_of(sample) == tx.level3_to_level2[sample]
    with pytest.raises(TaxonomyError, match="INDUSTRY_TAXONOMY"):
        tx.level2_of("999999")           # well-formed but absent -> blocker, not "9999"
    with pytest.raises(TaxonomyError, match="INDUSTRY_TAXONOMY"):
        tx.level2_of("99999")            # wrong width
    with pytest.raises(TaxonomyError, match="INDUSTRY_LEVEL_CONTRACT"):
        tx.assert_level("999999")        # a Level-3 key can never be a production key


def test_taxonomy_loader_rejects_a_rewritten_artifact():
    tx = taxonomy()
    body = json.loads((load_taxonomy.__globals__["TAXONOMY_PATH"]).read_bytes())
    body["level_width"] = 6
    with pytest.raises(TaxonomyError, match="TAXONOMY_SCHEMA"):
        parse_taxonomy(json.dumps(body).encode())
    body = json.loads((load_taxonomy.__globals__["TAXONOMY_PATH"]).read_bytes())
    body["industries"][0]["level3_children"] = body["industries"][1]["level3_children"]
    with pytest.raises(TaxonomyError, match="TAXONOMY_DUPLICATE"):
        parse_taxonomy(json.dumps(body).encode())


# --------------------------------------------------------------------------- helpers


def provider(days=30, etfs=6, industry_count=5, codes=None, amount=1000.):
    sessions = tuple(pd.bdate_range(end="2026-09-25", periods=days).date)
    codes = l2_codes(industry_count) if codes is None else codes
    bars, instruments, status = [], [], []
    for i in range(etfs):
        symbol = "5100%02d.SH" % i
        instruments.append({"symbol": symbol, "asset_type": "etf", "list_date": date(2020, 1, 1),
                            "delist_date": None, "prev_symbol": None})
        for day in sessions:
            bars.append({"symbol": symbol, "trade_date": day, "open": 1., "high": 1.1, "low": .9, "close": 1.,
                         "volume": 1000., "amount": amount * (i + 1), "source": "tdx_protocol"})
            status.append({"symbol": symbol, "trade_date": day, "is_trading": True, "status": "normal",
                           "source": "eastmoney"})
    return SimpleNamespace(sessions=sessions, cutoff=SIGNAL.date(), created_at=OBSERVED,
                           tables={"etf_bars": pd.DataFrame(bars), "instruments": pd.DataFrame(instruments),
                                   "trading_status": pd.DataFrame(status)})


def evidence_file(tmp_path):
    folder = tmp_path / "evidence"
    folder.mkdir(exist_ok=True)
    body = b"SYNTHETIC TEST EVIDENCE ONLY - not a real fund document"
    (folder / "synthetic.txt").write_bytes(body)
    return folder, body


def registry_doc(tmp_path, industries=5, per_industry=1):
    folder, body = evidence_file(tmp_path)
    codes = l2_codes(industries)
    entries, index = [], 0
    for code in codes:
        for _ in range(per_industry):
            entries.append({
                "industry_level": ETF_QUANT_INDUSTRY_LEVEL_V1, "industry_code": code,
                "industry_name": taxonomy().name_of(code), "etf_code": "5100%02d.SH" % index,
                "etf_name": "SYNTHETIC", "mapping_method": "OFFICIAL_FUND_DOCUMENT",
                "tracking_index_code": "SYN_%d" % index, "tracking_index_name": "SYNTHETIC",
                "tracking_target": "SYNTHETIC TEST TARGET",
                "classification": "A_SHARE_INDUSTRY_OR_THEME_ETF", "verification_status": "VERIFIED",
                "verified": True, "evidence_source": "SYNTHETIC", "evidence_type": "FUND_CONTRACT",
                "evidence_observed_at": "2026-08-01T09:00:00+08:00",
                "verified_at": "2026-08-01T10:00:00+08:00", "effective_from": "2026-08-02",
                "effective_to": None, "notes": "SYNTHETIC TEST ONLY",
                "available_at": "2026-08-01T10:00:00+08:00", "source_provider": "SYNTHETIC",
                "source_url": "https://example.invalid/synthetic", "source_file": "synthetic.txt",
                "source_sha256": digest(body), "source_retrieved_at": "2026-08-01T08:00:00+08:00"})
            index += 1
    return {"schema_version": "1.0.0", "registry_identity": "VERIFIED_MAPPING_REGISTRY_V1",
            "scope": "CURRENT_FORWARD_ONLY", "industry_level": ETF_QUANT_INDUSTRY_LEVEL_V1,
            "taxonomy_identity": taxonomy().identity, "entries": entries}, folder


def loaded(tmp_path, doc=None, **kw):
    original, folder = registry_doc(tmp_path, **kw)
    path = tmp_path / "registry.json"
    path.write_bytes(json_bytes(original if doc is None else doc))
    return load_registry(path, evidence_root=folder)


def rank(codes):
    return tuple(IndustryRanking(i + 1, code, 5. - i) for i, code in enumerate(codes))


def selected(tmp_path, doc=None, p=None, **kw):
    document, folder = registry_doc(tmp_path, **kw)
    path = tmp_path / "registry.json"
    path.write_bytes(json_bytes(document if doc is None else doc))
    reg = load_registry(path, evidence_root=folder)
    return select_mappings(reg, rank(l2_codes(5)), provider() if p is None else p, signal_at=SIGNAL)


# --------------------------------------------------------------------------- CP1 mapping contract


def test_registry_rejects_a_level3_keyed_entry(tmp_path):
    doc, _ = registry_doc(tmp_path)
    doc["entries"][0]["industry_code"] = "370101"
    with pytest.raises(GateError, match="SCHEMA"):
        loaded(tmp_path, doc)


def test_registry_rejects_a_level3_declared_registry(tmp_path):
    doc, _ = registry_doc(tmp_path)
    doc["industry_level"] = "SHENWAN_L3"
    with pytest.raises(GateError, match="SCHEMA"):
        loaded(tmp_path, doc)


def test_registry_rejects_industry_name_drift(tmp_path):
    doc, _ = registry_doc(tmp_path)
    doc["entries"][0]["industry_name"] = "SOME OTHER INDUSTRY"
    with pytest.raises(GateError, match="NAME"):
        loaded(tmp_path, doc)


def test_registry_rejects_broad_market_index_mapping(tmp_path):
    doc, _ = registry_doc(tmp_path)
    doc["entries"][0]["tracking_index_code"] = "000300.SH"
    with pytest.raises(GateError, match="BROAD_INDEX"):
        loaded(tmp_path, doc)


def test_registry_requires_evidence_observation_time(tmp_path):
    doc, _ = registry_doc(tmp_path)
    doc["entries"][0]["evidence_observed_at"] = "2026-09-28T11:00:00+08:00"  # after verified_at
    with pytest.raises(GateError, match="TEMPORAL"):
        loaded(tmp_path, doc)


def test_registry_cannot_backdate_effective_from(tmp_path):
    doc, _ = registry_doc(tmp_path)
    doc["entries"][0]["effective_from"] = "2026-07-01"   # before the evidence existed
    with pytest.raises(GateError, match="TEMPORAL"):
        loaded(tmp_path, doc)


def test_registry_verified_flag_must_match_status(tmp_path):
    doc, _ = registry_doc(tmp_path)
    doc["entries"][0]["verified"] = False
    with pytest.raises(GateError, match="VERIFICATION_FLAG"):
        loaded(tmp_path, doc)


def test_registry_requires_evidence_source_to_equal_provider(tmp_path):
    doc, _ = registry_doc(tmp_path)
    doc["entries"][0]["evidence_source"] = "SOMETHING ELSE"
    with pytest.raises(GateError, match="EVIDENCE_SOURCE"):
        loaded(tmp_path, doc)


# --------------------------------------------------------------------------- CP5 liquidity


def test_liquidity_window_is_exactly_the_twenty_sessions_ending_at_signal():
    p = provider(days=30)
    window, execution = liquidity_window(p, SIGNAL.date())
    assert len(window) == LIQUIDITY_SESSIONS == 20
    assert window[-1] == SIGNAL.date() and window == tuple(p.sessions[-21:-1])
    assert execution == p.sessions[-1]
    short = provider(days=10)
    assert liquidity_window(short, short.sessions[-1]) == (None, None)


def test_liquidity_missing_amount_is_admission_fail_never_averaged():
    p = provider(days=30)
    window, _ = liquidity_window(p, SIGNAL.date())
    p.tables["etf_bars"].loc[(p.tables["etf_bars"].symbol == "510000.SH")
                             & (p.tables["etf_bars"].trade_date == window[7]), "amount"] = None
    result = assess_liquidity(p, "510000.SH", window)
    assert result.status == FAIL and result.mean_amount_cny is None
    assert result.reason == "AMOUNT_EVIDENCE_MISSING" and result.sessions_present == 7


def test_liquidity_zero_and_sub_yuan_amount_are_feed_artefacts():
    p = provider(days=30)
    window, _ = liquidity_window(p, SIGNAL.date())
    for bad in (0., 0.5, -1.):
        p.tables["etf_bars"].loc[(p.tables["etf_bars"].symbol == "510001.SH")
                                 & (p.tables["etf_bars"].trade_date == window[3]), "amount"] = bad
        result = assess_liquidity(p, "510001.SH", window)
        assert result.status == FAIL and result.mean_amount_cny is None
    assert result.reason == "AMOUNT_BELOW_FEED_FLOOR"


def test_liquidity_insufficient_history_is_not_shortened():
    p = provider(days=30)
    window, _ = liquidity_window(p, SIGNAL.date())
    p.tables["instruments"].loc[p.tables["instruments"].symbol == "510002.SH", "list_date"] = window[5]
    result = assess_liquidity(p, "510002.SH", window)
    assert result.status == INSUFFICIENT and result.mean_amount_cny is None
    with pytest.raises(ValueError, match="twenty"):
        assess_liquidity(p, "510002.SH", window[:5])


def test_liquidity_passes_only_on_twenty_complete_sessions():
    p = provider(days=30)
    window, _ = liquidity_window(p, SIGNAL.date())
    result = assess_liquidity(p, "510000.SH", window)
    assert result.status == PASS and result.sessions_present == 20 and result.mean_amount_cny == 1000.


def test_liquidity_unproven_listing_date_fails_closed():
    p = provider(days=30)
    window, _ = liquidity_window(p, SIGNAL.date())
    p.tables["instruments"].loc[p.tables["instruments"].symbol == "510003.SH", "list_date"] = None
    assert assess_liquidity(p, "510003.SH", window).reason == "LISTING_DATE_UNPROVEN"


# --------------------------------------------------------------------------- CP6 distinct Top5


def test_five_distinct_verified_executable_etfs(tmp_path):
    result = selected(tmp_path)
    assert result["status"] == "READY"
    assert len(result["selected"]) == 5
    assert len({r["etf_code"] for r in result["selected"]}) == 5
    assert all(r["industry_level"] == ETF_QUANT_INDUSTRY_LEVEL_V1 for r in result["selected"])
    assert all(len(r["liquidity_window"]) == 20 for r in result["selected"])
    assert result["liquidity_sessions"] == LIQUIDITY_SESSIONS


def test_collision_falls_back_to_the_next_admitted_candidate(tmp_path):
    codes = l2_codes(5)
    doc, folder = registry_doc(tmp_path, industries=4)
    # Industry 5 gets two candidates: the ETF industry 1 will already have taken,
    # and a distinct one it must fall back to.
    shared = deepcopy(doc["entries"][0])
    shared["industry_code"] = codes[4]
    shared["industry_name"] = taxonomy().name_of(codes[4])
    shared["etf_code"] = doc["entries"][0]["etf_code"]
    distinct = deepcopy(shared)
    distinct["etf_code"] = "510005.SH"
    doc["entries"].extend([shared, distinct])
    result = selected(tmp_path, doc)
    assert result["status"] == "READY"
    assert len({r["etf_code"] for r in result["selected"]}) == 5
    chosen = next(r for r in result["selected"] if r["industry_code"] == codes[4])
    assert chosen["etf_code"] == "510005.SH"            # fell back, never reused


def test_one_industry_without_a_verified_candidate_blocks_distinct_five(tmp_path):
    doc, folder = registry_doc(tmp_path, industries=4)   # only 4 industries covered
    result = selected(tmp_path, doc)
    assert result["status"] == "MAPPING_ADMISSION_BLOCKED"
    assert result["reason"] == "DISTINCT_EXECUTABLE_ETF_BLOCKER"
    assert result["shortfall"] == "NO_ADMISSIBLE_CANDIDATE"
    assert result["distinct_etf_count"] == 4
    assert result["industries_without_candidate"] == [l2_codes(5)[4]]
    assert result["selected"] == []


def test_duplicate_etf_cannot_be_reused_to_fake_five_assets(tmp_path):
    codes = l2_codes(5)
    doc, folder = registry_doc(tmp_path, industries=1)
    base = doc["entries"][0]
    doc["entries"] = []
    for code in codes:
        row = deepcopy(base)
        row["industry_code"] = code
        row["industry_name"] = taxonomy().name_of(code)
        doc["entries"].append(row)           # every industry points at the SAME ETF
    result = selected(tmp_path, doc)
    assert result["status"] == "MAPPING_ADMISSION_BLOCKED"
    assert result["reason"] == "DISTINCT_EXECUTABLE_ETF_BLOCKER"
    assert result["shortfall"] == "CANDIDATE_COLLISION"
    assert result["distinct_etf_count"] == 1
    assert result["selected"] == []


def test_industry_rankings_must_be_level2_keys(tmp_path):
    doc, folder = registry_doc(tmp_path)
    path = tmp_path / "registry.json"
    path.write_bytes(json_bytes(doc))
    reg = load_registry(path, evidence_root=folder)
    with pytest.raises(GateError, match="INDUSTRY_LEVEL_CONTRACT"):
        select_mappings(reg, rank(["370601", "370301", "490101", "480301", "370101"]),
                        provider(), signal_at=SIGNAL)


def test_liquidity_representative_is_highest_mean_amount_then_lowest_code(tmp_path):
    doc, folder = registry_doc(tmp_path, industries=5)
    codes = l2_codes(5)
    # Two candidates for the first industry with different 20-session mean amount.
    bigger = deepcopy(doc["entries"][0])
    bigger["etf_code"] = "510010.SH"
    doc["entries"].append(bigger)
    result = selected(tmp_path, doc, provider(etfs=11))
    chosen = next(r for r in result["selected"] if r["industry_code"] == codes[0])
    assert chosen["etf_code"] == "510010.SH"          # amount 11000 beats 1000
    assert chosen["mean_amount_cny"] == 11000.
    # Ties break on ascending ETF code.
    p = provider(etfs=11)
    p.tables["etf_bars"].loc[p.tables["etf_bars"].symbol == "510010.SH", "amount"] = 1000.
    result = selected(tmp_path, doc, p)
    chosen = next(r for r in result["selected"] if r["industry_code"] == codes[0])
    assert chosen["etf_code"] == "510000.SH"


# --------------------------------------------------------------------------- CP7 portfolio


def test_capped_softmax_is_finite_positive_summing_to_one_within_cap():
    scores = {"510300.SH": 2.4, "510500.SH": 1.8, "159915.SZ": 1.2, "512880.SH": 1.1, "512800.SH": 1.0}
    result = size_targets(scores)
    assert result.status == AllocationStatus.READY
    weights = {t.asset_id: t.target_weight for t in result.targets}
    assert set(weights) == set(scores) and len(weights) == 5
    assert all(np.isfinite(v) and v > 0 for v in weights.values())
    assert abs(sum(weights.values()) - 1) < 1e-12
    assert max(weights.values()) <= 0.35 + 1e-12
    assert result.unallocated_weight == 0.


def test_capped_softmax_redistributes_from_a_dominant_asset():
    scores = {"A.SH": 40., "B.SH": 1., "C.SH": 1., "D.SH": 1., "E.SH": 1.}
    weights = {t.asset_id: t.target_weight for t in size_targets(scores).targets}
    assert weights["A.SH"] == pytest.approx(0.35)
    assert abs(sum(weights.values()) - 1) < 1e-12
    assert max(weights.values()) <= 0.35 + 1e-12


def test_capped_softmax_refuses_fewer_than_five_assets():
    result = size_targets({"A.SH": 1., "B.SH": 1., "C.SH": 1., "D.SH": 1.})
    assert result.status == AllocationStatus.INSUFFICIENT_ASSETS and result.targets == ()
    assert result.unallocated_weight == 1.0


def test_weights_are_never_computed_before_five_distinct_etfs(tmp_path):
    """No portfolio is producible while the mapping layer is blocked."""
    codes = l2_codes(5)
    doc, folder = registry_doc(tmp_path, industries=1)
    base = doc["entries"][0]
    doc["entries"] = []
    for code in codes:
        row = deepcopy(base)
        row["industry_code"] = code
        row["industry_name"] = taxonomy().name_of(code)
        doc["entries"].append(row)
    result = selected(tmp_path, doc)
    assert result["selected"] == []
    assert "weights" not in result and "targets" not in result
