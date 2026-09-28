"""The retrospective audit must preserve frozen Source-C gate and no-resume semantics."""
from datetime import date
import importlib.util
from pathlib import Path

import pytest


PATH = Path(__file__).resolve().parents[2] / "scripts" / "audit_etf_quant_readiness.py"
SPEC = importlib.util.spec_from_file_location("etf_quant_readiness_audit", PATH)
assert SPEC is not None and SPEC.loader is not None
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def group(*, current=10.0, previous=9.0, invalid=()):
    return [{"symbol": f"60000{i}.SH", "bar_valid": "True", "adj_is_exact": "True",
             "adj_close": str(current), "prev_adj_close": str(previous),
             "return_valid": "False" if i in invalid else "True"}
            for i in range(5)]


def test_source_c_base_adjacent_gate_and_broken_prefix():
    state = {}
    first = group()
    for row in first:
        row["return_valid"] = "False"  # no prior session: base, not fake return
    a = audit.advance_source_c(state, date(2025, 4, 10), "8010", first)
    assert a["source_c_valid"] and a["close"] == 1000.0
    b = audit.advance_source_c(state, date(2025, 4, 11), "8010", group(current=11, previous=10))
    assert b["source_c_valid"] and b["valid"] == 5 and b["close"] == pytest.approx(1100)
    c = audit.advance_source_c(state, date(2025, 4, 14), "8010", group(invalid={0}))
    assert not c["source_c_valid"] and c["valid"] == 4 and c["close"] is None
    d = audit.advance_source_c(state, date(2025, 4, 15), "8010", group())
    assert d["date_gate_valid"] and not d["source_c_valid"] and d["close"] is None
    assert d["reason"] == "RECURSIVE_PREFIX_BROKEN"


def test_audit_rejects_git_data_paths(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "matrix.csv").write_text("test", encoding="utf-8")
    with pytest.raises(ValueError, match="GIT_PATH_FOR_REAL_DATA_BLOCKED"):
        audit._external(tmp_path / "matrix.csv", directory=False)
