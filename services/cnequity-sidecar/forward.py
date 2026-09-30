"""One bounded forward refresh through the PINNED upstream job/publish gates.

External isolated sidecar only. No direct curated writes or new provider.
"""
import argparse
from contextlib import redirect_stdout
from datetime import date, datetime, time, timezone
import json
import os
from pathlib import Path, PureWindowsPath
import sys
import tomllib
import re

from runner import verify_install, lake_fingerprint
from proxy_policy import proxy_policy
from export_streaming import export_lake_streaming
from finalization import SessionJournal, admission

# Upstream owns step scheduling, staging, batch settlement, validation,
# compaction and revision publication. This list only narrows the job's scope.
STEPS = ["trading_calendar", "instruments", "industry_members", "daily_bars",
         "index_bars", "corporate_actions", "trading_status", "compact",
         "derive_adj_factors", "trading_status_derive", "audit"]
JOB = "etf_quant_forward"


def session_job(engine, session, *, force_observation=False):
    """Reuse/recover only this entry's exact pinned plan, never unknown jobs.

    Public SDK retry re-runs compact/derived/audit after the failed batch. It
    owns its bounded worker budget; this entry makes just one recovery call.
    A running job is not stolen, reconciled or restarted by this function.
    """
    matches = []
    for row in engine.manifest.list_runs(JOB):
        meta = json.loads(row["metadata_json"] or "{}")
        if meta.get("trade_date") != str(session):
            continue
        if (row["job_name"] != JOB or meta.get("backfill") is not False
                or meta.get("planned_steps") != STEPS):
            raise ValueError("FORWARD_JOB_PLAN_IDENTITY_BLOCKER")
        matches.append(row)
    if force_observation:
        return {**engine.run_job(JOB, trade_date=session, steps=STEPS),
                "action": "CURRENT_IDENTITY_REOBSERVATION"}
    # A later failed attempt cannot erase an admissible success for this day.
    matches.sort(key=lambda r: r["status"] != "success")
    for row in matches:
        if row["status"] == "success":
            return {"run_id": row["run_id"], "status": "success", "action": "REUSED_VERIFIED_JOB"}
        if row["status"] == "failed":
            if hasattr(engine, "config"):
                failed = engine.manifest.get_failed_batches(row["run_id"])
                # Renew one bounded worker opportunity on a later invocation;
                # a lifetime-exhausted retry counter must not strand recovered
                # providers forever. No successful batch is re-requested.
                engine.config.max_retries = max(engine.config.max_retries,
                    max((r["retry_count"] for r in failed), default=0) + 1)
            result = engine.run_job(JOB, trade_date=session, steps=STEPS,
                                    run_id=row["run_id"], retry_failed_only=True)
            return {**result, "action": "UPSTREAM_FAILED_BATCH_RECOVERY"}
        if row["status"] in ("degraded", "warning"):
            # A tolerated missing-key warning settles worker batches as
            # success. Failed-only retry cannot fetch those keys again and
            # would leave the entry stuck forever on the OLD logical receipt.
            # Make ONE normal upstream observation, with all original gates.
            return {**engine.run_job(JOB, trade_date=session, steps=STEPS),
                    "action": "NEW_FORWARD_JOB_AFTER_DEGRADED"}
        return {"run_id": row["run_id"], "status": "pending", "action": "EXISTING_JOB_NOT_TERMINAL"}
    return {**engine.run_job(JOB, trade_date=session, steps=STEPS), "action": "NEW_FORWARD_JOB"}


def enable_source_compatibility(cfg, settings):
    from source_compatibility import enable
    return enable(cfg, settings)


def failure_details(engine, run_id, session):
    rows = engine.manifest.get_dataset_results(run_id)
    unready = [{k: r[k] for k in ("dataset", "stage", "status", "criticality", "error_code")}
               for r in rows if r["status"] not in ("success", "skipped")]
    local = any(re.search(r"unsafe raw archive|WinError|MAX_PATH|UnicodeDecodeError|"
                         r"WINDOWS_.*ROOT|SOURCE_LAKE_CONFIG", r["error_message"] or "", re.I)
                for r in rows if "error_message" in r.keys())
    return {"classification": "LOCAL_ENGINEERING_FAILURE" if local else "PROVIDER_DATA_FAILURE",
            "reason_code": "LOCAL_STORAGE_FAILURE" if local else "SOURCE_SESSION_INCOMPLETE",
            "session": str(session), "unready_stages": unready,
            "retryable": not local, "next_action": "RERUN_ONE_SHOT" if not local else "REPAIR_LOCAL_STORAGE"}


def scope_observation(cfg, run_id, session):
    from expected_bars import observe
    return observe(cfg, run_id, session)


def exception_status(error):
    chain, seen = [], set()
    current = error
    while current is not None and id(current) not in seen:
        chain.append(current); seen.add(id(current))
        current = current.__cause__ or current.__context__
    for e in chain:
        code = getattr(e, "code", "")
        if code in ("PINNED_SOURCE_BLOCKER", "ISOLATED_SIDECAR_REQUIRED") or isinstance(e,(ImportError,AttributeError,TypeError,NameError)):
            return "BLOCKED_CODE_INTEGRITY", "LOCAL_ENGINEERING_FAILURE"
        if code or isinstance(e, ValueError) or (isinstance(e,OSError) and
             (e.filename is not None or getattr(e,"winerror",None) in (3,5,123,206))):
            return "BLOCKED_DATA_INTEGRITY", "LOCAL_ENGINEERING_FAILURE"
    return "WAITING_FOR_PROVIDER_DATA", "PROVIDER_DATA_FAILURE"


def windows_storage_path_gate(root):
    """Both lexical writer and resolved containment paths must fit Win32.

    Model the pinned RawArchive + atomic writer filename, not market data.
    DuckDB also cannot consume an extended-length glob. No SDK guard is patched.
    """
    root = PureWindowsPath(root)
    if not root.is_absolute() or str(root).startswith("\\\\?\\"):
        raise ValueError("WINDOWS_NORMAL_ABSOLUTE_IO_ROOT_REQUIRED")
    probe = (root / "meta/raw/corporate_actions/source=eastmoney/captured_date=2000-01-01"
             / ("." + "a"*64 + "." + "b"*64 + ".json." + "c"*8 + ".tmp"))
    if len(str(probe).encode("utf-16-le")) // 2 >= 260:
        raise ValueError("WINDOWS_SHORT_PHYSICAL_IO_ROOT_REQUIRED")


def configure_io_root(cfg, paths):
    r"""Optional explicit short alias, authenticated as the SAME physical lake.

    Windows native DuckDB globs do not accept \\?\ paths, while atomic raw
    archive filenames exceed MAX_PATH below the original long root. A local
    short PHYSICAL root fixes both, with the old access path retained by junction.
    A short junction to a long physical root is insufficient: resolve() can add
    an extended prefix only to the long leaf, breaking upstream containment.
    Existing storage link/containment checks remain entirely upstream-owned.
    """
    export_lake = Path(paths["lake_root"])
    io_root = Path(paths.get("lake_io_root", paths["lake_root"]))
    if not export_lake.is_absolute() or not io_root.is_absolute():
        raise ValueError("EXPLICIT_ABSOLUTE_LAKE_REQUIRED")
    if not export_lake.samefile(cfg.data_root) or not io_root.samefile(cfg.data_root):
        raise ValueError("SOURCE_LAKE_CONFIG_MISMATCH")
    if os.name == "nt":
        windows_storage_path_gate(str(io_root))
        windows_storage_path_gate(str(io_root.resolve(strict=True)))
    # Preserve lexical short spelling for RawPayloadArchive; resolving here
    # would recreate the long pathname. Readers still validate real identity.
    cfg.data_root = io_root


def forward(root, source_config, export_config, target, after, *, now=None, observation=None):
    verify_install(root)
    from cnequity.query import load
    from cnequity.config import load_config
    from cnequity.orchestrator.engine import JobEngine
    import cnequity.steps  # The pinned CLI registers these before constructing its engine.
    from cnequity.domain.market_time import SHANGHAI_TZ
    current = (datetime.now(timezone.utc) if now is None else now).astimezone(SHANGHAI_TZ)
    if target > current.date() or target == current.date() and current.time() < time(15, 5):
        return {"status": "WAITING_FOR_MARKET_CLOSE", "classification": "EXPECTED_MARKET_STATE",
                "reason_code": "SESSION_NOT_CLOSED", "refresh_attempted": False}
    cfg = load_config(source_config)
    settings = tomllib.loads(export_config.read_text(encoding="utf-8"))
    configure_io_root(cfg, settings["paths"])
    with proxy_policy("direct"):
        calendar = load("trading_calendar", start=settings["export"].get("start", str(after)),
                        end=str(target), data_root=cfg.data_root)
        all_sessions = sorted(r["trade_date"] for r in calendar.to_dicts() if r["is_trading"])
        if not all_sessions or all_sessions[-1] != target:
            return {"status": "BLOCKED_DATA_INTEGRITY", "classification": "LOCAL_ENGINEERING_FAILURE",
                    "reason_code": "OFFICIAL_CALENDAR_REQUIRED", "refresh_attempted": False}
        journal = SessionJournal(settings, after, all_sessions)
        if observation is not None:
            observation["latest_finalized"] = journal.latest
        compatibility = enable_source_compatibility(cfg, settings)
        sessions = [d for d in all_sessions if d > journal.cutoff]
        receipts = []
        for session in sessions:
            # Normal forward daily semantics, NOT backfill. No source code patch.
            engine = JobEngine(cfg)
            result = session_job(engine, session, force_observation=compatibility.get("repair_required", False))
            compatibility["repair_required"] = False
            # A tolerated success with unresolved factual keys must remain
            # retryable on a later invocation, rather than be reused forever.
            if (result["status"] == "success" and result["action"] == "REUSED_VERIFIED_JOB"
                    and scope_observation(cfg, result["run_id"], session)["missing_count"]):
                result = session_job(engine, session, force_observation=True)
                result["action"] = "NEW_FORWARD_JOB_AFTER_UNFINALIZED_SCOPE"
            # A failed-only recovery can introduce an irrelevant research
            # warning through the SDK finalization plan. Reobserve once using
            # our exact normal plan rather than retain that stale warning.
            if result["status"] in ("degraded", "warning") and result["action"] == "UPSTREAM_FAILED_BATCH_RECOVERY":
                result = session_job(engine, session, force_observation=True)
            receipts.append({"session": str(session), "run_id": result["run_id"],
                             "status": result["status"], "action": result["action"]})
            if result["status"] != "success":
                # Identifiers/enums only. Do not publish native stderr,
                # response bodies, network configuration or secret values.
                details = failure_details(engine, result["run_id"], session)
                details["daily_bars"] = scope_observation(cfg, result["run_id"], session)
                receipts[-1].update(details)
                return {"status": "BLOCKED_DATA_INTEGRITY" if details["classification"] == "LOCAL_ENGINEERING_FAILURE"
                        else "WAITING_FOR_PROVIDER_DATA", "reason_code": details["reason_code"],
                        "refresh_attempted": True, "receipts": receipts, "latest_finalized": journal.latest}
            missing_stages = admission(engine.manifest.get_dataset_results(result["run_id"]), STEPS)
            if missing_stages:
                return {"status": "BLOCKED_DATA_INTEGRITY", "reason_code": "SUCCESS_RECEIPT_INCOMPLETE",
                        "missing_stages": missing_stages, "session": str(session),
                        "refresh_attempted": True, "receipts": receipts, "latest_finalized": journal.latest}
            scope = scope_observation(cfg, result["run_id"], session)
            receipts[-1]["daily_bars"] = scope
            if scope["missing_count"]:
                return {"status": "WAITING_FOR_PROVIDER_DATA", "reason_code": "PROVIDER_MISSING",
                        "session": str(session), "refresh_attempted": True, "receipts": receipts,
                        "latest_finalized": journal.latest}
            settings["export"]["cutoff"] = str(session)
            # Use the identical short physical spelling for writer AND reader.
            settings["paths"]["lake_root"] = str(cfg.data_root)
            journal.prepare(session, receipts[-1]["run_id"], lake_fingerprint(cfg.data_root))
            result = export_lake_streaming(settings, load)
            journal.publish(session, result, receipts[-1]["run_id"])
            if observation is not None:
                observation["latest_finalized"] = journal.latest
            receipts[-1]["finalization"] = "FINALIZED"
        return {"status": "REFRESH_EXPORTED", **(journal.latest or {}),
                "latest_finalized": journal.latest, "refresh_attempted": bool(receipts), "receipts": receipts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source-config", type=Path, required=True)
    parser.add_argument("--export-config", type=Path, required=True)
    parser.add_argument("--target", type=date.fromisoformat, required=True)
    parser.add_argument("--after", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    observation = {}
    try:
        with redirect_stdout(sys.stderr):
            result = forward(args.root, args.source_config, args.export_config, args.target, args.after,
                             observation=observation)
    except Exception as error:
        # Provider readiness failure cannot produce a signal or invented cutoff.
        code = getattr(error, "code", "")
        status, classification = exception_status(error)
        result = {"status": status, "reason_code": code or type(error).__name__,
                  "classification": classification, "exception_class": type(error).__name__,
                  "retryable": classification == "PROVIDER_DATA_FAILURE", "refresh_attempted": True,
                  "latest_finalized": observation.get("latest_finalized")}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
