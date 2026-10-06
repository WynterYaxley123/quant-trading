"""Current V2 labels never expose the historical gate as a current claim."""

import json
from pathlib import Path

import pytest

from strategies.etf_quant_v2.release import current_release

ROOT = Path(__file__).resolve().parents[1]


def original():
    release = json.loads((ROOT / "strategies/etf_quant_v2/config/release.json").read_bytes())
    labels = json.loads(
        (ROOT / "config/research/etf-quant-v2-scientific-status.json").read_bytes()
    )["labels"]
    return release, labels


def test_historical_gate_keeps_an_explicit_name():
    release, labels = original()
    current = current_release(release, labels)
    assert "classification" not in current
    assert current["historical_classification"] == release["classification"]
    assert current["scientific_status"] == "PROVISIONAL_HISTORICAL_RESEARCH_CANDIDATE"
    assert "HISTORICALLY_VALIDATED_STRONG" not in json.dumps(current)


@pytest.mark.parametrize(
    "patch",
    [{"classification": "PASS_WEAK"}, {"release_sha256": "0" * 64}, {"lot_size": 1}],
)
def test_overlay_cannot_replace_release_identity_fields(patch):
    release, labels = original()
    with pytest.raises(ValueError, match="V2_SCIENTIFIC_OVERLAY_IDENTITY_ERROR"):
        current_release(release, labels | patch)


def test_overlay_cannot_drop_a_label():
    release, labels = original()
    labels.pop("independent_statistical_confidence")
    with pytest.raises(ValueError, match="V2_SCIENTIFIC_OVERLAY_IDENTITY_ERROR"):
        current_release(release, labels)
