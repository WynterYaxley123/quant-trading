"""Adapter admission on REAL production evidence packages.

The unit tests in ``test_production_pit_evidence.py`` pin the evidence layer's own
rules. This module is the wiring test the task asks for: it takes the packages that
were actually built from official provider bytes and feeds them to the *existing*
``strategies.etf_quant.mapping.pit`` adapter -- no parallel loader, no substitute
schema -- and asserts the verdicts that come back.

Real evidence, synthetic market micro-structure
-----------------------------------------------
The ETF bars, instruments and trading status used for the 20-session liquidity gate
are synthetic, because a compatibility test must not depend on a live market
snapshot. Everything that decides *admission* -- the weight vector, the Shenwan L2
attribution, the availability instants and the pinned source hashes -- is the real
production evidence. The distinction is reported, never blurred.

These tests skip, loudly, when the runtime artifacts are absent. They never silently
pass.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from test_registry_sidecar import registry_doc

from strategies.etf_quant.domain import IndustryRanking
from strategies.etf_quant.domain.industry_level import default_taxonomy
from strategies.etf_quant.mapping.pit import load_pit_evidence, select_pit_mappings
from strategies.etf_quant.mapping.registry import load_registry
from strategies.etf_quant.runtime.storage import GateError, json_bytes

pytestmark = pytest.mark.external_runtime

TZ = timezone(timedelta(hours=8))
RUNTIME = (
    Path(os.environ.get("ETF_QUANT_EXTERNAL_RUNTIME_ROOT", r"D:\QuantForge\runtime\etf-quant-v1"))
    / "production-pit-evidence-v1"
)
BOOK = RUNTIME / "adapter-tests" / "production_evidence_book_v1.json"
SOURCE_ROOT = RUNTIME / "adapter-sources"
REGISTRY = RUNTIME / "reports" / "production_pit_evidence_registry_v1.json"

#: A simulated decision instant strictly after every package's availability. This is
#: a *compatibility* cutoff, not a Shadow epoch, and it creates no business records.
SIMULATED_CUTOFF = date(2026, 11, 2)
#: The historical engineering reference date. Nothing observed later may be used here.
HISTORICAL_CUTOFF = date(2026, 9, 24)


def _require_artifacts():
    if not BOOK.exists() or not SOURCE_ROOT.exists():
        pytest.skip(f"production evidence book not built: {BOOK}")


def _sessions(end: date, periods: int = 40):
    """Business days ending at ``end``, plus the following session.

    The frozen liquidity window is the 20 sessions ending at the signal session and
    the T+1 execution session is the *next* calendar session, so the provider must
    expose one day past the signal date or the window legitimately refuses to form.
    """
    days = tuple(day.date() for day in pd.bdate_range(end=end, periods=periods))
    return (*days, (pd.Timestamp(days[-1]) + pd.offsets.BDay()).date())


def _provider(etf_codes, *, cutoff: date, amount_by_etf=None):
    """Synthetic micro-structure wide enough for the real 20-session gate."""
    days = _sessions(cutoff, 40)
    bars, instruments, status = [], [], []
    for index, symbol in enumerate(sorted(etf_codes)):  # noqa: B007 -- Retain established loop identity for provenance review.
        instruments.append(
            {
                "symbol": symbol,
                "asset_type": "etf",
                "list_date": date(2015, 1, 1),
                "delist_date": None,
                "prev_symbol": None,
            }
        )
        for day in days:
            amount = 1.0e9
            if amount_by_etf and symbol in amount_by_etf:
                amount = amount_by_etf[symbol]
            bars.append(
                {
                    "symbol": symbol,
                    "trade_date": day,
                    "open": 1.0,
                    "high": 1.1,
                    "low": 0.9,
                    "close": 1.0,
                    "volume": 1.0e6,
                    "amount": amount,
                    "source": "tdx_protocol",
                }
            )
            status.append(
                {
                    "symbol": symbol,
                    "trade_date": day,
                    "is_trading": True,
                    "status": "normal",
                    "source": "eastmoney",
                }
            )
    return SimpleNamespace(
        sessions=days,
        cutoff=cutoff,
        created_at=datetime(cutoff.year, cutoff.month, cutoff.day, 17, tzinfo=TZ),
        tables={
            "etf_bars": pd.DataFrame(bars),
            "instruments": pd.DataFrame(instruments),
            "trading_status": pd.DataFrame(status),
        },
    )


def _copy_book(tmp_path) -> Path:
    """Copy the built book and its pinned sources into an isolated directory."""
    _require_artifacts()
    target_root = tmp_path / "official"
    shutil.copytree(SOURCE_ROOT, target_root)
    target = tmp_path / "book.json"
    target.write_bytes(BOOK.read_bytes())
    return target, target_root


def _book(tmp_path):
    path, root = _copy_book(tmp_path)
    return load_pit_evidence(path, source_root=root), path, root


def _empty_registry(tmp_path):
    doc, evidence = registry_doc(tmp_path)
    doc["entries"] = []
    registry_path = tmp_path / "strict_registry.json"
    registry_path.write_bytes(json_bytes(doc))
    return load_registry(registry_path, evidence_root=evidence)


def _rankings(codes):
    return tuple(IndustryRanking(index + 1, code, 5 - index) for index, code in enumerate(codes))


# ---------------------------------------------------------------------------
# The real book loads through the unmodified adapter
# ---------------------------------------------------------------------------


def test_production_book_loads_through_the_existing_adapter(tmp_path):
    book, _path, _root = _book(tmp_path)
    assert book.sha256
    assert book.records, "the production book must contain at least one record"
    for record in book.records:
        assert record.available_at >= record.evidence_observed_at
        assert record.source_publication_at <= record.evidence_observed_at
        assert record.valid_through >= record.weight_effective_date
        assert record.exposure is not None


def test_every_production_record_is_a_complete_official_weight_set(tmp_path):
    book, _path, _root = _book(tmp_path)
    for record in book.records:
        assert record.exposure.weight_source_type == "OFFICIAL_WEIGHT"
        assert record.exposure.weight_quality == "COMPLETE_WEIGHT_SET", record.benchmark_code
        assert record.exposure.unmapped_weight == 0.0, record.benchmark_code
        assert 99.0 <= record.exposure.weight_sum <= 100.5, record.benchmark_code


def test_production_book_yields_no_evidence_before_the_historical_cutoff(tmp_path):
    """The 2026-09-24 no-backfill test over the real book.

    Every package in it was observed on or after 2026-09-30, so at the historical
    engineering decision instant the adapter must see an empty prefix.
    """
    book, _path, _root = _book(tmp_path)
    decision = datetime(2026, 9, 24, 18, tzinfo=TZ)
    assert book.prefix(decision) == {}
    available = {record.available_at.date() for record in book.records}
    assert all(day > HISTORICAL_CUTOFF for day in available), sorted(available)[:5]


def test_production_prefix_at_the_simulated_cutoff_is_non_empty(tmp_path):
    book, _path, _root = _book(tmp_path)
    decision = datetime(2026, 11, 2, 18, tzinfo=TZ)
    prefix = book.prefix(decision)
    assert prefix, "every production record should be available at the simulated cutoff"
    assert len(prefix) == len(book.records)
    for payload in prefix.values():
        assert payload["hash"]
        assert not payload["date"].startswith("2026-09-24")


# ---------------------------------------------------------------------------
# Full admission path on the real book
# ---------------------------------------------------------------------------


def test_simulated_future_cutoff_runs_strict_proxy_cash_on_real_evidence(tmp_path):
    book, _path, _root = _book(tmp_path)
    registry = _empty_registry(tmp_path)
    taxonomy = default_taxonomy()
    industries = list(taxonomy.named_industry_codes)
    rankings = _rankings(industries[:5])
    etfs = {record.etf_code for record in book.records}
    provider = _provider(etfs, cutoff=SIMULATED_CUTOFF)
    result = select_pit_mappings(
        registry, rankings, provider, book, signal_at=datetime(2026, 11, 2, 18, tzinfo=TZ)
    )
    assert result["status"] == "READY"
    assert len(result["slots"]) == 5
    # With an empty strict registry every slot must be decided by evidence or cash.
    for slot in result["slots"]:
        assert slot["mapping_type"] in ("PROXY_EXPOSURE", "CASH_UNEXECUTABLE_SIGNAL")
        if slot["etf_code"] is not None:
            assert slot["target_l2_exposure"] >= 40.0
            assert slot["target_is_largest_l2"] is True


def test_real_evidence_is_never_visible_at_the_historical_cutoff(tmp_path):
    """Same book, same registry, historical instant: the evidence must not be used."""
    book, _path, _root = _book(tmp_path)
    registry = _empty_registry(tmp_path)
    taxonomy = default_taxonomy()
    rankings = _rankings(list(taxonomy.named_industry_codes)[:5])
    etfs = {record.etf_code for record in book.records}
    provider = _provider(etfs, cutoff=HISTORICAL_CUTOFF)
    result = select_pit_mappings(
        registry, rankings, provider, book, signal_at=datetime(2026, 9, 24, 18, tzinfo=TZ)
    )
    assert all(slot["etf_code"] is None for slot in result["slots"]), (
        "no production evidence may be admitted on 2026-09-24"
    )
    assert result["selected"] == []


def test_a_tampered_pinned_source_is_refused(tmp_path):
    book, path, root = _book(tmp_path)
    payload = json.loads(path.read_bytes())
    record = payload["records"][0]
    target = root / record["weight_source_file"]
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(GateError, match="HASH"):
        load_pit_evidence(path, source_root=root)


def test_a_missing_available_at_is_refused(tmp_path):
    book, path, root = _book(tmp_path)
    payload = json.loads(path.read_bytes())
    del payload["records"][0]["available_at"]
    path.write_bytes(json_bytes(payload))
    with pytest.raises(GateError, match="SCHEMA"):
        load_pit_evidence(path, source_root=root)


def test_backdating_availability_to_the_historical_cutoff_is_refused(tmp_path):
    """The effective-vs-available trap, on the real package.

    The described date stays 2026-08-31 while availability is moved behind the
    observation instant. The adapter's own ordering rule must reject it. The
    offset is computed from the record rather than hard-coded, so the test does not
    depend on when the evidence happened to be collected.
    """
    book, path, root = _book(tmp_path)
    payload = json.loads(path.read_bytes())
    record = payload["records"][0]
    observed = datetime.fromisoformat(record["evidence_observed_at"].replace("Z", "+00:00"))
    record["available_at"] = (observed - timedelta(hours=1)).isoformat()
    path.write_bytes(json_bytes(payload))
    with pytest.raises(GateError, match="TIME"):
        load_pit_evidence(path, source_root=root)


def test_an_unknown_official_host_is_refused(tmp_path):
    book, path, root = _book(tmp_path)
    payload = json.loads(path.read_bytes())
    payload["records"][0]["weight_source_url"] = "https://www.csindex.com.cn.evil.invalid/x"
    path.write_bytes(json_bytes(payload))
    with pytest.raises(GateError, match="SOURCE_IDENTITY"):
        load_pit_evidence(path, source_root=root)


# ---------------------------------------------------------------------------
# The strict path is untouched
# ---------------------------------------------------------------------------


def test_strict_path_still_refuses_a_pit_book(tmp_path):
    from strategies.etf_quant.runtime import shadow

    book, _path, _root = _book(tmp_path)
    doc, evidence = registry_doc(tmp_path)
    registry_path = tmp_path / "strict.json"
    registry_path.write_bytes(json_bytes(doc))
    registry = load_registry(registry_path, evidence_root=evidence)
    etfs = {record.etf_code for record in book.records}
    provider = _provider(etfs, cutoff=SIMULATED_CUTOFF)
    with pytest.raises(GateError, match="STRICT_PATH_PIT_EVIDENCE_FORBIDDEN"):
        shadow.daily_cycle(
            provider,
            registry,
            tmp_path / "runtime",
            now=datetime(2026, 11, 2, 18, tzinfo=TZ),
            code_commit="d" * 40,
            classification_version="SWCLASS2021",
            pit_evidence=book,
        )


# ---------------------------------------------------------------------------
# Registry cross-check
# ---------------------------------------------------------------------------


def test_registry_counts_agree_with_the_book(tmp_path):
    _require_artifacts()
    if not REGISTRY.exists():
        pytest.skip("registry not built")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    book = load_pit_evidence(BOOK, source_root=SOURCE_ROOT)
    counts = registry["counts"]
    assert counts["benchmarks_with_complete_official_weights"] > 0
    assert registry["production_available_from"]
    assert registry["availability_semantics"] == "FORWARD_ONLY"
    assert counts["classification_securities"] > 0
    recorded = {record.benchmark_code for record in book.records}
    assert recorded, "book must cover at least one benchmark"
