"""Install ONLY into the caller's dedicated sidecar venv from the audited lock.

No global installation, project Docker mutation, floating dependency resolution,
credential configuration or market-data initialization is performed here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tomllib
import urllib.request
from pathlib import Path

PIN = "1650e384a3fd1f67a70144a489acc91432f1df27"
REPO = "https://github.com/rootSunc/CNEquity"
BUILD_TOOLS = {"setuptools": "80.9.0", "wheel": "0.45.1"}

# Data files the pinned release needs at runtime but whose glob is absent from
# `[tool.setuptools.package-data]`, so a wheel/sdist install silently omits them
# while a source checkout still has them on disk. The omission is invisible until
# the exact code path that reads the file runs.
#
#   adapters/eastmoney/seeds/bse_code_mapping.json
#     Read by `adapters/eastmoney/corporate_actions_migration._code_mapping` and by
#     `steps/delisted.renamed_symbols`. Its absence makes `cne delisted backfill`
#     and `cne delisted status` fail with FileNotFoundError. Those commands publish
#     the delisted-recovery receipts that `delisted_recovery_covers` requires
#     before the daily_bars ownership batch can settle, so the omission blocks
#     compaction of the whole dataset, not just one command.
#
# The missing files are restored from the pinned source checkout (never patched or
# synthesised), and each restore is verified against the source file's SHA-256 so a
# partial or tampered copy cannot pass. Upstream is left untouched.
OMITTED_PACKAGE_DATA = ("adapters/eastmoney/seeds/bse_code_mapping.json",)


def restore_omitted_package_data(source: Path, site_packages: Path) -> list[dict]:
    """Copy package data the pinned build omits, verifying each file's digest."""
    restored = []
    for relative in OMITTED_PACKAGE_DATA:
        origin = source / "src" / "cnequity" / relative
        destination = site_packages / "cnequity" / relative
        if not origin.is_file():
            raise ValueError("OMITTED_PACKAGE_DATA_MISSING_FROM_SOURCE:" + relative)
        payload = origin.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == digest:
            restored.append({"path": relative, "sha256": digest, "action": "already_present"})
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise ValueError("OMITTED_PACKAGE_DATA_RESTORE_BLOCKER:" + relative)
        restored.append({"path": relative, "sha256": digest, "action": "restored"})
    return restored


def locked_runtime(lock, environment):
    from pip._vendor.packaging.markers import Marker

    packages = lock["package"]
    root = next(p for p in packages if p["name"] == "cnequity")
    chosen: dict[str, dict[str, object]] = {}

    def visit(dependency):
        if dependency.get("marker") and not Marker(dependency["marker"]).evaluate(environment):
            return
        name = dependency["name"]
        matches = [
            p
            for p in packages
            if p["name"] == name
            and ("version" not in dependency or p["version"] == dependency["version"])
        ]
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
    hashes = {
        a["hash"]
        for a in [*package.get("wheels", []), *([package["sdist"]] if "sdist" in package else [])]
    }
    if not hashes or any(not h.startswith("sha256:") or len(h) != 71 for h in hashes):
        raise ValueError("MISSING_LOCKED_ARTIFACT_HASH")
    return f"{package['name']}=={package['version']} " + " ".join(
        "--hash=" + h for h in sorted(hashes)
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    if Path(sys.prefix).resolve() != root / "venv" or sys.prefix == sys.base_prefix:
        raise ValueError("ISOLATED_VENV_REQUIRED")
    source = root / "source"
    commit = subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    dirty = subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(source), "status", "--porcelain"], text=True
    ).strip()
    if commit != PIN or dirty:
        raise ValueError("AUDITED_SOURCE_PIN_BLOCKER")
    lock_bytes = (source / "uv.lock").read_bytes()
    from pip._vendor.packaging.markers import default_environment

    packages = locked_runtime(tomllib.loads(lock_bytes.decode()), default_environment())
    # The upstream runtime lock excludes build tooling. Pin and hash these two
    # build requirements separately rather than allow pip's unbounded build env.
    build = []
    for name, version in BUILD_TOOLS.items():
        with urllib.request.urlopen(
            f"https://pypi.org/pypi/{name}/{version}/json", timeout=30
        ) as response:
            metadata = json.load(response)
        hashes = sorted({"sha256:" + a["digests"]["sha256"] for a in metadata["urls"]})
        if not hashes:
            raise ValueError("BUILD_TOOL_HASH_BLOCKER")
        build.append(f"{name}=={version} " + " ".join("--hash=" + h for h in hashes))
    runtime_lock = root / "runtime-requirements.lock"
    build_lock = root / "build-requirements.lock"
    runtime_lock.write_text(
        "\n".join(hashed_requirement(p) for p in packages) + "\n", encoding="utf-8"
    )
    build_lock.write_text("\n".join(build) + "\n", encoding="utf-8")
    for requirements in (build_lock, runtime_lock):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-deps",
                "--no-build-isolation",
                "--require-hashes",
                "-r",
                str(requirements),
            ],
            check=True,
        )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-deps",
            "--no-build-isolation",
            str(source),
        ],
        check=True,
    )
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
    from importlib.metadata import version as installed_version

    if installed_version("cnequity") != "0.11.0":
        raise ValueError("INSTALLED_VERSION_BLOCKER")
    import cnequity as installed

    payload_files = restore_omitted_package_data(
        source, Path(installed.__file__).resolve().parent.parent
    )
    print(
        json.dumps(
            {
                "status": "ISOLATED_SIDECAR_INSTALLED",
                "source_commit": PIN,
                "version": "0.11.0",
                "upstream_lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
                "runtime_dependencies": len(packages),
                "build_tools": BUILD_TOOLS,
                "restored_package_data": payload_files,
            }
        )
    )


if __name__ == "__main__":
    main()
