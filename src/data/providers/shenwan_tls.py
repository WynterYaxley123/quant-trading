"""Adapter-scoped strict chain completion. Never grants trust to a leaf/new root."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import tempfile

import certifi

HOST = "www.swsresearch.com"
CERT_DIR = Path(__file__).resolve().parents[1] / "certs"


def command(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError("STRICT_TLS_VERIFICATION_BLOCKER: " + result.stdout + result.stderr)
    return result.stdout


def certificate_info(path: Path) -> dict:
    info = command(["openssl", "x509", "-in", str(path), "-noout", "-subject", "-issuer", "-serial", "-dates"])
    return dict(line.split("=", 1) for line in info.splitlines() if "=" in line)


def verify_chain(leaf: Path, roots: Path, intermediate: Path | None = None,
                 *, hostname: str = HOST, at_time: int | None = None) -> dict:
    """No partial-chain flag: intermediate must itself reach original trusted roots."""
    extra = ["-attime", str(at_time)] if at_time is not None else []
    verification = ["openssl", "verify", "-CAfile", str(roots), *extra]
    if intermediate is not None:
        leaf_info, issuer_info = certificate_info(leaf), certificate_info(intermediate)
        if leaf_info["issuer"] != issuer_info["subject"]:
            raise ValueError("STRICT_TLS_VERIFICATION_BLOCKER: issuer mismatch")
        text = command(["openssl", "x509", "-in", str(intermediate), "-noout", "-text"])
        if "CA:TRUE" not in text:
            raise ValueError("STRICT_TLS_VERIFICATION_BLOCKER: issuer is not a CA")
        command([*verification, str(intermediate)])
        verification += ["-untrusted", str(intermediate)]
    args = [*verification, "-verify_hostname", hostname, "-purpose", "sslserver", str(leaf)]
    output = command(args)
    return {"verified": True, "verificationCommand": args, "verificationOutput": output.strip()}


def prepare_tls() -> tuple[str, dict]:
    """Read server certificates with a verifying diagnostic, then verify independently.

    A failed s_client is only certificate evidence, never an accepted HTTP response.
    Bundled intermediate is used only if the supplied server chain cannot verify.
    Requests subsequently repeats normal hostname and certificate verification.
    """
    roots = Path(certifi.where())
    addresses = sorted({row[4][0] for row in socket.getaddrinfo(HOST, 443)})
    with socket.create_connection((HOST, 443), timeout=15) as stream:
        peer = stream.getpeername()[0]
    result = subprocess.run(["openssl", "s_client", "-connect", HOST + ":443", "-servername", HOST,
                             "-showcerts", "-verify_return_error", "-CAfile", str(roots)],
                            input="", text=True, capture_output=True, timeout=30)
    certs = re.findall(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", result.stdout, re.S)
    if not certs:
        raise ValueError("STRICT_TLS_VERIFICATION_BLOCKER: no diagnostic certificates")
    # Temp TLS material is public and adapter-scoped; no global CA mutations.
    folder = Path(tempfile.mkdtemp(prefix="shenwan_strict_tls_"))
    leaf = folder / "leaf.pem"
    leaf.write_text(certs[0] + "\n", encoding="ascii")
    supplied = folder / "supplied.pem"
    supplied.write_text("\n".join(certs[1:]) + "\n", encoding="ascii")
    info = certificate_info(leaf)
    audit = {"dns": addresses, "tcp443": True, "peer": peer, "leaf": info,
             "serverCertificateCount": len(certs), "originalRoots": str(roots),
             "originalRootsSha256": hashlib.sha256(roots.read_bytes()).hexdigest(),
             "sClientReturnCode": result.returncode, "sClientDiagnostic": result.stderr.strip()}
    try:
        proof = verify_chain(leaf, roots, supplied if len(certs) > 1 else None)
        audit.update(tlsMode="STANDARD_STRICT", tlsChainComplete=True,
                     intermediatePinned=False, intermediateSha256=None, **proof)
        return str(roots), audit
    except ValueError as error:
        audit["standardVerificationError"] = str(error)
    if len(certs) != 1 or "unable to get local issuer certificate" not in result.stderr:
        raise ValueError("STRICT_TLS_VERIFICATION_BLOCKER: not a missing-intermediate case")
    intermediate = CERT_DIR / "geotrust_g2_tls_cn_2022.pem"
    pin = json.loads((CERT_DIR / "geotrust_g2_tls_cn_2022.json").read_text())
    digest = hashlib.sha256(intermediate.read_bytes()).hexdigest()
    leaf_text = command(["openssl", "x509", "-in", str(leaf), "-noout", "-text"])
    if digest != pin["sha256"] or ("CA Issuers - URI:" + pin["sourceAiaUrl"]) not in leaf_text:
        raise ValueError("STRICT_TLS_VERIFICATION_BLOCKER: pin/AIA drift")
    proof = verify_chain(leaf, roots, intermediate)
    bundle = folder / "adapter-only-bundle.pem"
    bundle.write_bytes(roots.read_bytes() + intermediate.read_bytes())
    audit.update(tlsMode="PROJECT_LOCAL_STRICT_CHAIN_COMPLETION", tlsChainComplete=False,
                 intermediatePinned=True, intermediateSha256=digest,
                 intermediate=certificate_info(intermediate), **proof)
    return str(bundle), audit
