"""Hash-only historical preservation: never decode sealed or research performance."""

import json
from pathlib import Path

from research.evidence.contracts import sha

ROOT = Path(__file__).resolve().parents[1]


def test_all_preexisting_frozen_research_and_certificates_are_byte_identical():
    manifest = json.loads(
        (ROOT / "reports/engineering/swl1-data-first-historical-invariance.json").read_bytes()
    )
    assert manifest["base_sha"] == "b5556a0a19040f5650ca9d8d03b4f141effdbf30"
    assert len(manifest["files"]) >= 124
    for name, expected in manifest["files"].items():
        target = (ROOT / name).resolve(strict=True)
        assert target.is_relative_to(ROOT)
        assert sha(target.read_bytes()) == expected, name


def test_new_readiness_never_reopens_history_or_creates_a_family():
    readiness = json.loads(
        (ROOT / "reports/research/swl1_data_first/prospective-readiness.json").read_bytes()
    )
    assert readiness["historical_numeric_access_isolation"] == "NOT_CERTIFIED"
    assert readiness["certified_historically_unseen_sessions"] == 0
    assert set(readiness["models"].values()) == {"FAILED_VALIDATION"}
    assert readiness["future_protocol"] == "NOT_CREATED"
    assert readiness["formal_observations"] == 0
    assert readiness["live_activation"] is False
    registry = json.loads((ROOT / "config/research/industry-forecast-families.json").read_bytes())
    assert len(registry["additional_families"]) == 2
