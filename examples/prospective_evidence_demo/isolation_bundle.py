"""Authority preparation for a separate Docker worker; only synthetic files."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

import numpy as np

from research.evidence.contracts import canonical, sha
from research.evidence.numeric import Boundary, grant_claims, materialize

from .fixture import setup


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--poison", choices=("positive", "negative", "nan"), default="positive")
    args = parser.parse_args()
    root = args.output
    root.mkdir(parents=True, exist_ok=False)
    authority, registry, protocol, calendar, anchor = setup()
    source = registry.get(protocol.source_digest).source
    boundary = Boundary(
        "development",
        protocol.sessions[1],
        protocol.sessions[15],
        protocol.sessions[15],
        protocol.sessions[11],
        (10,),
        "2029-01-01T00:00:00Z",
    )
    n = len(protocol.sessions)
    features = np.arange(n * 3 * 2, dtype=float).reshape(n, 3, 2)
    returns = np.arange(n * 3, dtype=float).reshape(n, 3)
    returns[12:] = {"positive": 9e200, "negative": -9e200, "nan": np.nan}[args.poison]
    mother = root / "synthetic-mother.npz"
    np.savez_compressed(
        mother,
        sessions=np.array(protocol.sessions),
        universe=np.array(protocol.model_universe),
        features=features,
        returns=returns,
    )
    facts_hash = sha(b"isolated synthetic finalized receipts")
    grant = authority.issue("phase", grant_claims(protocol, boundary, facts_hash))
    now = "2028-02-01T16:00:00+08:00"
    manifest = materialize(
        mother,
        root / "views" / "view",
        protocol,
        boundary,
        grant,
        registry,
        authority,
        now=now,
        facts_hash=facts_hash,
        activation_anchor=anchor,
        calendar=calendar,
    )
    policy = {
        "protocol": asdict(protocol),
        "boundary": asdict(boundary),
        "source_hash": source.source_hash,
        "data_contract_hash": source.data_contract_hash,
        "now": now,
    }
    (root / "policy").mkdir()
    (root / "policy" / "policy.json").write_bytes(canonical(policy))
    (root / "launch.json").write_bytes(
        canonical({"pin": sha(canonical(manifest)), "content_hash": manifest["content_hash"]})
    )


if __name__ == "__main__":
    main()
