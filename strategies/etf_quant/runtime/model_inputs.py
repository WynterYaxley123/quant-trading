"""Bind the already admitted model universe and historical as-of seed.

This layer is model warmup evidence. Execution PIT is supplied independently
to the mapping layer; no membership publication timestamp is manufactured.
"""
from datetime import date
import json
from pathlib import Path

from .exports import SCHEMAS, PROVENANCE, decode_table
from .storage import GateError, contained, digest

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "config/common_model_universe_v1.json"


def load_model_contract(path=CONTRACT_PATH):
    body = Path(path).read_bytes()
    doc = json.loads(body)
    codes = doc["industries"]
    if (doc.get("contract") != "COMMON_MODEL_UNIVERSE_V1"
            or doc.get("training_date_policy") != "COMPLETE_ADMITTED_MODEL_UNIVERSE"
            or doc.get("classification_mode") != "TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE"
            or doc.get("historical_classification_pit") != "NOT_STRICT_HISTORICAL_CLASSIFICATION_PIT"
            or len(codes) != doc["industry_count"] or len(codes) < 5
            or codes != sorted(set(codes))):
        raise GateError("MODEL_INPUT_CONTRACT_BLOCKER")
    return {**doc, "contract_sha256": digest(body)}


def bind_model_inputs(provider, reference_snapshot):
    """Read only the byte-verified historical membership bootstrap snapshot.

    Latest exports deliberately begin at the warmup start and cannot carry
    its preceding month-end classification. The frozen engineering export
    contains that seed. Future exports still supply every later snapshot.
    """
    contract = load_model_contract()
    root = Path(reference_snapshot).resolve(strict=True)
    if any((p / ".git").exists() for p in (root, *root.parents)):
        raise GateError("EXPLICIT_EXTERNAL_MODEL_REFERENCE_REQUIRED")
    manifest_bytes = contained(root, "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if (root.name != contract["reference_snapshot_id"]
            or digest(manifest_bytes) != contract["reference_manifest_sha256"]
            or manifest["source_commit"] != provider.manifest["source_commit"]):
        raise GateError("MODEL_REFERENCE_HASH_BLOCKER")
    entry = manifest["datasets"]["industry_membership"]
    payload = contained(root, "industry_membership.csv").read_bytes()
    if (digest(payload) != contract["reference_membership_sha256"]
            or entry["file_sha256"] != contract["reference_membership_sha256"]):
        raise GateError("MODEL_REFERENCE_HASH_BLOCKER")
    frame = decode_table(payload, entry["columns"], {**SCHEMAS["industry_membership"], **PROVENANCE})
    first = date.fromisoformat(contract["warmup_start"])
    eligible = frame.loc[(frame.as_of_date <= first) & (frame.source == "sw")
                         & (frame.classification_system == "sw")]
    if eligible.empty:
        raise GateError("MODEL_MEMBERSHIP_BOOTSTRAP_REQUIRED")
    seed = eligible.loc[eligible.as_of_date == eligible.as_of_date.max()].copy()
    if seed.duplicated("symbol").any():
        raise GateError("MODEL_MEMBERSHIP_BOOTSTRAP_BLOCKER")
    provider.model_input_contract = contract
    provider.model_membership_seed = seed
    return contract
