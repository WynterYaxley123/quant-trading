"""Stdlib transport for the unchanged pinned SDK forward/export lifecycle."""

from pathlib import Path

import run as transport
from docker_mounts import bind_mount


def refresh_command(config, target, after):
    image = config.get("developer_image", "quant-trading-forward:local")
    if image.startswith("quant-research"):
        raise transport.GateError("INDEPENDENT_REFRESH_IMAGE_REQUIRED")
    mounts = [(transport.REPO, "/workspace", True)]
    for field, dest, readonly, file in (
        ("docker_source_root", "/cnequity", True, False),
        ("source_config", "/source.toml", True, True),
        ("export_config", "/export.toml", True, True),
        ("operational_lake_root", "/operational-lake", False, False),
        ("snapshot", "/seed-snapshot", True, False),
        ("export_root", "/source-control/exports", False, False),
        ("sidecar_root", "/source-control", False, False),
    ):
        source = (
            transport.external_file(config[field])
            if file
            else transport.external_directory(config[field])
        )
        mounts.append((source, dest, readonly))
    lake = Path(config["operational_lake_root"]).resolve()
    # Config explicitly names an owned copy, never the shared canonical lake.
    if lake.name != "forward-source-lake":
        raise transport.GateError("OWNED_FORWARD_SOURCE_LAKE_REQUIRED")
    argv = [config.get("docker_executable", "docker"), "run", "--rm"]
    for source, dest, readonly in mounts:
        argv += bind_mount(source, dest, readonly=readonly)
    return argv + [
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-e",
        "PYTHONPATH=/workspace:/cnequity/src",
        "-w",
        "/workspace",
        image,
        "python",
        "-B",
        "services/cnequity-sidecar/forward.py",
        "--root",
        "/source-control",
        "--source-config",
        "/source.toml",
        "--export-config",
        "/export.toml",
        "--docker-source",
        "/cnequity",
        "--target",
        str(target),
        "--after",
        str(after),
    ]


def refresh_v2_bars(config, snapshot):
    from datetime import date

    meta = transport.verify_snapshot_files(snapshot)
    day = date.fromisoformat(meta["data_cutoff"])
    argv = [config.get("docker_executable", "docker"), "run", "--rm"]
    for source, dest, readonly in (
        (transport.REPO, "/workspace", True),
        (transport.external_directory(config["docker_source_root"]), "/cnequity", True),
        (transport.external_directory(config["liquidity_root"]), "/liquidity", False),
    ):
        argv += bind_mount(source, dest, readonly=readonly)
    argv += [
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-e",
        "PYTHONPATH=/workspace:/cnequity/src",
        "-w",
        "/workspace",
        config.get("developer_image", "quant-trading-forward:local"),
        "python",
        "-B",
        "-m",
        "strategies.etf_quant_v2.refresh",
        "--registry",
        "/workspace/strategies/etf_quant_v2/config/mapping-registry.json",
        "--source",
        "/cnequity",
        "--output",
        "/liquidity",
        "--day",
        str(day),
    ]
    result = transport.call(argv, timeout=3600)
    if result.returncode:
        raise transport.GateError("V2_FACTUAL_LIQUIDITY_REFRESH_BLOCKER")
    return transport.result_json(result)
