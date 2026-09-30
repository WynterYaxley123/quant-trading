"""Pinned, isolated lake reader/exporter; never a model or trading runner."""
from __future__ import annotations

import argparse
import hashlib
from datetime import date, datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

from bootstrap import PIN, REPO
from proxy_policy import POLICY_DIRECT, POLICIES, ProxyPolicyError, proxy_policy

# File boundary utilities only. Quant models execute exclusively in Docker.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from strategies.etf_quant.runtime.exports import SCHEMAS, export_snapshot
from strategies.etf_quant.runtime.storage import GateError, atomic_bytes, external_root, json_bytes

IDENTITY = {"provider": "CNEQUITY_PINNED_SIDECAR", "source_repo": REPO, "source_commit": PIN,
    "source_version": "0.11.0", "cnequity_version": "0.11.0", "source_identity": "CNEQUITY_LOCAL_LAKE_V1",
    "classification_version": "SWCLASS2021"}
DATASETS = {"trading_calendar": "trading_calendar", "stock_bars": "daily_bars",
    "industry_membership": "industry_members", "etf_bars": "daily_bars", "instruments": "instruments",
    "trading_status": "trading_status", "benchmark_csi300": "index_bars"}


def lake_fingerprint(lake):
    """Detect concurrent source mutation; no filesystem timestamp-only shortcut."""
    records = []
    for path in sorted(lake.rglob("*.parquet")):
        if any(part in ("curated", "derived") for part in path.relative_to(lake).parts):
            checksum = hashlib.sha256()
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    checksum.update(block)
            records.append((path.relative_to(lake).as_posix(), checksum.hexdigest()))
    return hashlib.sha256(json_bytes(records)).hexdigest()


def verify_install(root):
    root = root.resolve(strict=True)
    if Path(sys.prefix).resolve() != (root / "venv").resolve() or sys.prefix == sys.base_prefix:
        raise GateError("ISOLATED_SIDECAR_REQUIRED")
    source = root / "source"
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=source, text=True)
    if commit != PIN or dirty or version("cnequity") != "0.11.0":
        raise GateError("PINNED_SOURCE_BLOCKER")


def export_lake(config, load, *, observed_at=None):
    """No downloads: query the existing lake, preserve original row provenance.

    No as_of is passed to non-PIT datasets. No derived industry_index is read.
    Explicit symbols avoid upstream's stock-only ETF universe filtering.
    """
    started = datetime.now(timezone.utc) if observed_at is None else observed_at
    settings = config["export"]
    if any(not isinstance(config["paths"].get(k), str) or not config["paths"][k].strip()
           or not Path(config["paths"][k]).is_absolute() for k in ("lake_root", "export_root")):
        raise GateError("EXPLICIT_EXTERNAL_PATHS_REQUIRED")
    if settings.get("classification_version") != IDENTITY["classification_version"]:
        raise GateError("CLASSIFICATION_VERSION_BLOCKER")
    start, cutoff = date.fromisoformat(settings["start"]), date.fromisoformat(settings["cutoff"])
    calendar_end = date.fromisoformat(settings["calendar_end"])
    if start > cutoff or calendar_end < cutoff:
        raise GateError("EXPORT_DATE_RANGE_BLOCKER")
    etfs = settings["etf_symbols"]
    if not isinstance(etfs, list) or len(set(etfs)) != len(etfs) or any(not re.fullmatch(r"\d{6}\.(SH|SZ)", s) for s in etfs):
        raise GateError("EXPLICIT_ETF_SCOPE_BLOCKER")
    lake = external_root(Path(config["paths"]["lake_root"]))
    before = lake_fingerprint(lake)
    queries, tables = {}, {}
    adjustment_rejected_rows = 0
    # Membership must be complete, not narrowed to stocks with available prices.
    query = {"start": start.isoformat(), "end": cutoff.isoformat(), "data_root": lake}
    membership = load("industry_members", **query)
    rows = [r for r in membership.to_dicts() if r["source"] == "sw" and r["classification_system"] == "sw"]
    symbols = sorted({r["symbol"] for r in rows})
    if not symbols:
        raise GateError("SHENWAN_MEMBERSHIP_UNAVAILABLE")
    tables["industry_membership"] = rows
    queries["industry_membership"] = {"dataset": "industry_members", "start": str(start), "end": str(cutoff),
        "source_filter": "sw", "classification_system": "sw", "as_of": None,
        "availability_evidence": "HISTORICAL_MEMBERSHIP_PIT_UNPROVEN"}
    for target, dataset in DATASETS.items():
        if target == "industry_membership":
            continue
        args = {"start": str(start), "end": str(calendar_end if target == "trading_calendar" else cutoff), "data_root": lake}
        if target == "stock_bars":
            # The frozen constituent denominator includes the CDR. A global
            # strict query aborts on its unsupported factor, so inspect the
            # exactness flag and exclude only non-exact *price rows* here;
            # membership is never narrowed. ExportProvider still requires
            # every published adjusted close to be exact.
            args.update(symbols=symbols, adjust="hfq", strict_adj=False)
        elif target == "etf_bars":
            if not etfs:
                tables[target] = []
                queries[target] = {"dataset": dataset, "symbols": [], "adjust": None, "status": "NO_VERIFIED_ETF_SCOPE"}
                continue
            args.update(symbols=etfs, adjust=None)
        elif target == "instruments":
            args.pop("start")
            args.pop("end")
        elif target == "trading_status":
            if not etfs:
                tables[target] = []
                queries[target] = {"dataset": dataset, "symbols": [], "status": "NO_VERIFIED_ETF_SCOPE"}
                continue
            args.update(symbols=etfs)
        elif target == "benchmark_csi300":
            args.update(symbols=["000300.SH"])
        frame = load(dataset, **args)
        result = frame.to_dicts()
        if target == "stock_bars":
            adjustment_rejected_rows = sum(r.get("adj_is_exact") is not True for r in result)
            result = [r for r in result if r.get("adj_is_exact") is True]
        if target == "benchmark_csi300":
            result = [r for r in result if r.get("frequency") == "1d"]
        tables[target] = result
        queries[target] = {"dataset": dataset, **{k: str(v) if isinstance(v, Path) else v for k, v in args.items() if k != "data_root"},
                           "as_of": None}
        if target == "stock_bars":
            queries[target]["published_exact_only"] = True
            queries[target]["rejected_nonexact_rows"] = adjustment_rejected_rows
    completed = datetime.now(timezone.utc) if observed_at is None else observed_at
    if lake_fingerprint(lake) != before:
        raise GateError("SOURCE_LAKE_CHANGED_DURING_EXPORT_BLOCKER")
    return export_snapshot(Path(config["paths"]["export_root"]), tables, identity={**IDENTITY, "lake_fingerprint_sha256": before},
        created_at=completed, fetch_started_at=started, fetch_completed_at=completed, cutoff=cutoff, queries=queries,
        adjustment_rejected_rows=adjustment_rejected_rows,
        warnings=["NOT_EX_ANTE_AVAILABILITY_PROOF", "ETF_MAPPING_EXTERNAL_EVIDENCE_REQUIRED",
                  "CALENDAR_FUTURE_SESSIONS_ARE_NOT_FUTURE_PRICES", "NO_THIRD_PARTY_DATA_REDISTRIBUTION"])


def exception_chain(error, limit=6):
    """Class+message per link, so a transport fault is never reduced to a bare class name."""
    chain, current = [], error
    while current is not None and len(chain) < limit:
        chain.append({"class": type(current).__module__ + "." + type(current).__name__,
                      "message": str(current)[:300]})
        current = current.__cause__ or current.__context__
    return chain


def smoke_metadata(root, policy=POLICY_DIRECT):
    """One public classification request, strict upstream SSLContext; no market init.

    The pinned client enables httpx ``trust_env``, so it would otherwise inherit
    ambient proxy state; ``proxy_policy`` scopes that to an explicit decision.
    TLS is untouched: the upstream SSLContext still verifies the chain and hostname.
    """
    from cnequity.adapters.sw.industry_history import fetch_sw_industry_intervals, sw_client
    started = datetime.now(timezone.utc)
    base = {"source_commit": PIN, "tls_verification": "STRICT_UPSTREAM_SSL_CONTEXT",
            "proxy_policy": policy, "pit_evidence": False, "market_data_initialization": False,
            "source_data_distributed": False, "retries": 0}
    try:
        # Caller-configured timeout using the pinned public interface. TLS and
        # upstream headers are unchanged; no retries or source patching.
        with proxy_policy(policy):
            with sw_client(timeout=30.) as client:
                rows = fetch_sw_industry_intervals(client=client)
        report = {**base, "status": "NETWORK_METADATA_SMOKE_PASS", "rows": rows.height,
                  "columns": rows.columns, "source_version": version("cnequity"),
                  "classification_version": "SWCLASS2021",
                  "available_at": None, "source_published_at": None}
    except ProxyPolicyError as error:
        report = {**base, "status": "NETWORK_METADATA_SMOKE_BLOCKED",
                  "exception_class": type(error).__name__, "exception_chain": exception_chain(error),
                  "blocker": error.code}
    except Exception as error:
        report = {**base, "status": "NETWORK_METADATA_SMOKE_BLOCKED",
                  "exception_class": type(error).__name__, "exception_chain": exception_chain(error)}
    report.update(started_at=started.isoformat(), completed_at=datetime.now(timezone.utc).isoformat())
    # The diagnostic record must survive even if the artifact write fails, so a
    # storage fault can never be mistaken for a verified smoke outcome.
    try:
        logs = external_root(root / "logs")
        atomic_bytes(logs / ("metadata_smoke_" + started.strftime("%Y%m%dT%H%M%S") + ".json"), json_bytes(report))
    except Exception as error:
        report["evidence_write_warning"] = type(error).__name__
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["export", "smoke", "verify"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--proxy-policy", choices=list(POLICIES), default=POLICY_DIRECT,
                        help="direct (default) scopes away ambient proxy state; "
                             "inherit_environment is an explicit operator opt-in")
    parser.add_argument("--streaming", action="store_true",
                        help="bound export memory: scan stock bars one calendar session per pinned query; "
                             "publication bytes are identical to the batch exporter")
    args = parser.parse_args()
    verify_install(args.root)
    if args.command == "smoke":
        result = smoke_metadata(args.root, args.proxy_policy)
    elif args.command == "verify":
        result = {"status": "PINNED_SOURCE_PASS", **IDENTITY}
    else:
        if args.config is None:
            raise GateError("EXTERNAL_CONFIG_REQUIRED")
        config_path = args.config.resolve(strict=True)
        if any((p / ".git").exists() for p in config_path.parents):
            raise GateError("EXTERNAL_CONFIG_REQUIRED")
        from cnequity.query import load
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
        if args.streaming:
            from export_streaming import export_lake_streaming
            result = export_lake_streaming(config, load)
        else:
            result = export_lake(config, load)
    print(json.dumps(result))
    return 0 if "BLOCKED" not in result.get("status", "") else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GateError as error:
        print(json.dumps({"status": error.code}))
        raise SystemExit(2)
    except Exception as error:
        print(json.dumps({"status": "SIDECAR_INPUT_OR_QUERY_BLOCKED", "exception_class": type(error).__name__}))
        raise SystemExit(2)
