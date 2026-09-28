"""Pure audit classification tests; no CNEquity lake or network access."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from datetime import date

import pytest


PATH = Path(__file__).resolve().parents[2] / "services" / "cnequity-sidecar" / "coverage_matrix.py"
SPEC = importlib.util.spec_from_file_location("coverage_matrix_audit", PATH)
assert SPEC is not None and SPEC.loader is not None
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


GOOD = (11.0, True, 100, 11.0, 11.5, 10.5, 11.0, "tdx_protocol")
PRIOR = (10.0, True, 100, 10.0, 10.5, 9.5, 10.0, "tdx_protocol")
INSTRUMENT = {"symbol": "600000.SH", "asset_type": "stock", "list_date": None}


def test_exact_calendar_adjacent_return_only():
    assert audit.classify(INSTRUMENT, GOOD, PRIOR) is None
    assert audit.classify(INSTRUMENT, GOOD, None) == "PREVIOUS_BAR_MISSING"
    # Earlier sparse-prior audit would have counted a last-available bar;
    # the production matrix must not substitute it for the prior session.
    assert audit.legacy_return_valid(GOOD, PRIOR)


@pytest.mark.parametrize("instrument,current,previous,reason", [
    (None, GOOD, PRIOR, "INSTRUMENT_UNRESOLVED"),
    ({"symbol": "689009.SH", "asset_type": "cdr"}, GOOD, PRIOR, "CDR_UNSUPPORTED"),
    (INSTRUMENT, None, PRIOR, "BAR_MISSING"),
    (INSTRUMENT, (11., True, 0, 11., 11.5, 10.5, 11., "tdx_protocol"), PRIOR, "BAR_INVALID"),
    (INSTRUMENT, (11., False, 100, 11., 11.5, 10.5, 11., "tdx_protocol"), PRIOR, "ADJ_NON_EXACT"),
    (INSTRUMENT, GOOD, (10., False, 100, 10., 10.5, 9.5, 10., "tdx_protocol"), "PREVIOUS_ADJ_NON_EXACT"),
])
def test_member_gap_taxonomy(instrument, current, previous, reason):
    assert audit.classify(instrument, current, previous) == reason


def test_unverified_list_date_is_never_a_prelisting_permission():
    suspect = {**INSTRUMENT, "list_date": "2026-09-24"}
    assert audit.classify(suspect, None, PRIOR) == "BAR_MISSING"


def test_stored_dates_are_diagnostics_not_gate_exemptions():
    suspect = {**INSTRUMENT, "list_date": date(2026, 9, 24),
               "delist_date": date(2024, 1, 1)}
    assert audit.stored_date_diagnostics(suspect, date(2025, 4, 10),
                                         "BAR_MISSING") == (True, True)
    assert audit.classify(suspect, None, PRIOR) == "BAR_MISSING"
    assert audit.stored_date_diagnostics(suspect, date(2025, 4, 10),
                                         None) == (False, False)


def test_window_absence_and_rename_are_diagnostic_not_silent_repair():
    assert audit.classify(INSTRUMENT, None, PRIOR, symbol="600000.SH",
                          window_symbols=set()) == "MEMBERSHIP_ONLY_NO_MARKET_DATA"
    assert audit.classify(None, GOOD, PRIOR, symbol="000001.SZ",
                          known_prev_symbols={"000001.SZ"}) == "CODE_MAPPING_GAP"
    assert audit.industry_failure_reason(4, 4, audit.Counter()) == "INSUFFICIENT_ELIGIBLE_CONSTITUENTS"


def test_output_must_be_outside_git(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "nested").mkdir()
    with pytest.raises(ValueError, match="OUTPUT_OR_LAKE_INSIDE_GIT_BLOCKED"):
        audit._outside_repo(tmp_path / "nested")
