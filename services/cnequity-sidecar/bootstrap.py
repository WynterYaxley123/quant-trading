"""Install ONLY into the caller's dedicated sidecar venv from the audited lock.

No global installation, project Docker mutation, floating dependency resolution,
credential configuration or market-data initialization is performed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tomllib
import urllib.request

PIN = "1650e384a3fd1f67a70144a489acc91432f1df27"
REPO = "https://github.com/rootSunc/CNEquity"
BUILD_TOOLS = {"setuptools": "80.9.0", "wheel": "0.45.1"}


def locked_runtime(lock, environment):
    from pip._vendor.packaging.markers import Marker

    packages = lock["package"]
    root = next(p for p in packages if p["name"] == "cnequity")
    chosen = {}

    def visit(dependency):
        if dependency.get("marker") and not Marker(dependency["marker"]).evaluate(environment):
            return
        name = dependency["name"]
        matches = [p for p in packages if p["name"] == name
                   and ("version" not in dependency or p["version"] == dependency["version"])]
        if len(matches) != 1:
            raise ValueError("LOCK_RESOLUTION_BLOCKER")
        package = matches[0]
        if name in chosen:
            if chosen[name]["version"] != package["version"]:
                raise ValueError("LOCK_VERSION_COLLISION")
            return
        if package.get("source") != {"registry": "https://pypi.org/simple"}:
            raise ValueError("UNAPPROVED_PACKAGE_ORIGIN")
        chosen[name] = package
        for child in package.get("dependencies", []):
            visit(child)

    for dependency in root["dependencies"]:
        visit(dependency)
    return tuple(chosen[name] for name in sorted(chosen))


def hashed_requirement(package):
    hashes = {a["hash"] for a in [*package.get("wheels", []), *([package["sdist"]] if "sdist" in package else [])]}
    if not hashes or any(not h.startswith("sha256:") or len(h) != 71 for h in hashes):
        raise ValueError("MISSING_LOCKED_ARTIFACT_HASH")
    return f"{package['name']}=={package['version']} " + " ".join("--hash=" + h for h in sorted(hashes))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    if Path(sys.prefix).resolve() != root / "venv" or sys.prefix == sys.base_prefix:
        raise ValueError("ISOLATED_VENV_REQUIRED")
    source = root / "source"
    commit = subprocess.check_output(["git", "--no-optional-locks", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "--no-optional-locks", "-C", str(source), "status", "--porcelain"], text=True).strip()
    if commit != PIN or dirty:
        raise ValueError("AUDITED_SOURCE_PIN_BLOCKER")
    lock_bytes = (source / "uv.lock").read_bytes()
    from pip._vendor.packaging.markers import default_environment
    packages = locked_runtime(tomllib.loads(lock_bytes.decode()), default_environment())
    # The upstream runtime lock excludes build tooling. Pin and hash these two
    # build requirements separately rather than allow pip's unbounded build env.
    build = []
    for name, version in BUILD_TOOLS.items():
        with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=30) as response:
            metadata = json.load(response)
        hashes = sorted({"sha256:" + a["digests"]["sha256"] for a in metadata["urls"]})
        if not hashes:
            raise ValueError("BUILD_TOOL_HASH_BLOCKER")
        build.append(f"{name}=={version} " + " ".join("--hash=" + h for h in hashes))
    runtime_lock = root / "runtime-requirements.lock"
    build_lock = root / "build-requirements.lock"
    runtime_lock.write_text("\n".join(hashed_requirement(p) for p in packages) + "\n", encoding="utf-8")
    build_lock.write_text("\n".join(build) + "\n", encoding="utf-8")
    for requirements in (build_lock, runtime_lock):
        subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                        "--no-deps", "--no-build-isolation", "--require-hashes", "-r", str(requirements)], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                    "--no-deps", "--no-build-isolation", str(source)], check=True)
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
    from importlib.metadata import version
    if version("cnequity") != "0.11.0":
        raise ValueError("INSTALLED_VERSION_BLOCKER")
    print(json.dumps({"status": "ISOLATED_SIDECAR_INSTALLED", "source_commit": PIN,
                      "version": "0.11.0", "upstream_lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
                      "runtime_dependencies": len(packages), "build_tools": BUILD_TOOLS}))


if __name__ == "__main__":
    main()
