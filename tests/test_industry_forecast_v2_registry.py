"""Public aggregate lineage and inactive branches; never execute factual research."""

import json

import pytest

from strategies.industry_forecast.registry import ROOT, families, resolve, validate_v2


def fixture():
    family = json.loads((ROOT / "config/research/swl1-ridge-v2-family.json").read_bytes())
    artifacts = {
        key: json.loads((ROOT / ref["path"]).read_bytes())
        for key, ref in family.items()
        if key.endswith("_reference")
    }
    return family, artifacts


@pytest.mark.parametrize(
    "state",
    [
        "FAILED_VALIDATION",
        "AWAITING_PROSPECTIVE_FINAL_OOS",
        "NO_DEVELOPMENT_CANDIDATE",
        "VALIDATION_INTERVAL_NOT_UNSEEN",
        "NOT_RESEARCHABLE_WITH_CURRENT_DATA",
    ],
)
def test_legal_research_branches_remain_inactive(state):
    family, artifacts = fixture()
    status = artifacts["status_reference"]
    family["scientific_status"] = status["scientific_status"] = state
    if state == "AWAITING_PROSPECTIVE_FINAL_OOS":
        status["validation_passed"] = artifacts["validation_reference"]["passed"] = True
    elif state != "FAILED_VALIDATION":
        status.update(candidate_hash=None, validation_opened=False, validation_passed=None)
        family["model_contract_hash"] = family["protocol_reference"]["sha256"]
        for key in ("candidate_reference", "validation_reference"):
            family.pop(key)
            artifacts.pop(key)
        for row in artifacts["development_reference"]["leaderboard"]:
            row["admitted"] = False
    validate_v2(family, artifacts)
    family["forward_eligible"] = True
    with pytest.raises(ValueError, match="CONTRACT_MISMATCH"):
        validate_v2(family, artifacts)


@pytest.mark.parametrize("mutation", ["candidate", "anchor", "reopen", "oos"])
def test_lineage_and_lifecycle_tampering_fails_closed(mutation):
    family, artifacts = fixture()
    if mutation == "candidate":
        artifacts["validation_reference"]["lineage"]["candidate_hash"] = "f" * 64
    elif mutation == "anchor":
        artifacts["status_reference"]["public_preregistration_anchor"]["external_merge_witness"][
            "exact_remote_bytes_verified"
        ] = False
    elif mutation == "reopen":
        artifacts["status_reference"]["validation_reopened"] = True
    else:
        artifacts["status_reference"]["final_oos_opened"] = True
    with pytest.raises(ValueError, match="CONTRACT_MISMATCH"):
        validate_v2(family, artifacts)


def test_public_registry_keeps_four_independent_generations_and_real_evidence():
    registry = families()
    assert [f["family_id"] for f in registry] == [
        "swl2_ridge_v1",
        "swl2_ridge_v2",
        "swl1_ridge_v1",
        "swl1_ridge_v2",
    ]
    v2 = resolve("swl1-ridge-v2")
    assert v2["model_universe_size"] == 30 and v2["taxonomy_universe_size"] == 31
    assert v2["validation_status"] == "FAIL" and v2["candidate_hash"]
    assert len(v2["research_evidence"]["development"]["leaderboard"]) == 16
    assert v2["research_evidence"]["validation"]["metrics"]["signal_count"] == 126
    assert v2["primary_series"] == "RECONSTRUCTED_SWL1_EQUAL_WEIGHT"
    with pytest.raises(ValueError, match="FORWARD_INELIGIBLE"):
        resolve("swl1-ridge-v2", require_forward=True)
