"""Fixed synthetic worker entry point; no authority secret/provider/ledger mount."""

from __future__ import annotations

import argparse
import json
import os
import socket
from pathlib import Path

from .contracts import Denied, require
from .numeric import Boundary, consume
from .prospective import Protocol


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pin", required=True)
    args = parser.parse_args()
    policy = json.loads(Path("/policy/policy.json").read_bytes())
    protocol = policy["protocol"]
    for key in ("model_universe", "horizons", "phases", "sessions"):
        protocol[key] = tuple(protocol[key])
    boundary = policy["boundary"]
    boundary["allowed_label_maturity"] = tuple(boundary["allowed_label_maturity"])
    result = consume(
        Path("/view"),
        pinned_manifest_hash=args.pin,
        protocol=Protocol(**protocol),
        boundary=Boundary(**boundary),
        source_hash=policy["source_hash"],
        data_contract_hash=policy["data_contract_hash"],
        now=policy["now"],
    )
    # Adversarial direct reads bypass the Python firewall to test actual OS mounts.
    forbidden = (
        "/mother/synthetic-mother.npz",
        "/delivery/mother.npz",
        "/source",
        "/workspace/.git",
        "/var/run/docker.sock",
        "/host",
        "/quantforge/runtime",
    )
    for name in forbidden:
        try:
            with open(name, "rb"):
                raise Denied("PROCESS_ISOLATION_FAILED")
        except (FileNotFoundError, PermissionError, IsADirectoryError):
            pass
    require(os.geteuid() != 0, "ROOT_WORKER_DENIED")
    require(os.readlink("/proc/self/ns/net") != "", "PROCESS_ISOLATION_FAILED")
    fds = []
    for p in Path("/proc/self/fd").iterdir():
        try:
            if p.name not in {"0", "1", "2"}:
                fds.append(os.readlink(p))
        except FileNotFoundError:
            pass
    require(not fds, "INHERITED_DESCRIPTOR_DENIED")
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=1):
            raise Denied("NETWORK_ACCESS_DENIED")
    except OSError:
        pass
    result.update(
        process_isolation="PASS_LINUX_DOCKER_SYNTHETIC",
        direct_mother_read="DENIED",
        inherited_descriptors=0,
        network="DENIED",
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
