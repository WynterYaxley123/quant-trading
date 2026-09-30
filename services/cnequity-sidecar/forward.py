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

from runner import verify_install
from proxy_policy import proxy_policy
from export_streaming import export_lake_streaming

# Upstream owns step scheduling, staging, batch settlement, validation,
# compaction and revision publication. This list only narrows the job's scope.
STEPS = ["trading_calendar", "instruments", "industry_members", "daily_bars",
         "index_bars", "corporate_actions", "trading_status", "compact",
         "derive_adj_factors", "trading_status_derive", "audit"]
JOB = "etf_quant_forward"


def session_job(engine, session):
    """Reuse/recover only this entry's exact pinned plan, never unknown jobs.

    Public SDK retry re-runs compact/derived/audit after the failed batch. It
    owns its bounded worker budget; this entry makes just one recovery call.
    A running job is not stolen, reconciled or restarted by this function.
    """
    for row in engine.manifest.list_runs(JOB):
        meta = json.loads(row["metadata_json"] or "{}")
        if meta.get("trade_date") != str(session):
            continue
        if (row["job_name"] != JOB or meta.get("backfill") is not False
                or meta.get("planned_steps") != STEPS):
            raise ValueError("FORWARD_JOB_PLAN_IDENTITY_BLOCKER")
        if row["status"] == "success":
            return {"run_id": row["run_id"], "status": "success", "action": "REUSED_VERIFIED_JOB"}
        if row["status"] in ("failed", "degraded", "warning"):
            result = engine.run_job(JOB, trade_date=session, steps=STEPS,
                                    run_id=row["run_id"], retry_failed_only=True)
            return {**result, "action": "UPSTREAM_FAILED_BATCH_RECOVERY"}
        return {"run_id": row["run_id"], "status": "pending", "action": "EXISTING_JOB_NOT_TERMINAL"}
    return {**engine.run_job(JOB, trade_date=session, steps=STEPS), "action": "NEW_FORWARD_JOB"}


def extended_path_text(value):
    """Local Windows filename plumbing, not a lake/source/methodology change."""
    path = PureWindowsPath(value)
    if not path.is_absolute():
        raise ValueError("EXPLICIT_ABSOLUTE_LAKE_REQUIRED")
    text = str(path)
    if text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text[2:]
    return "\\\\?\\" + text


def forward(root, source_config, export_config, target, after, *, now=None):
    verify_install(root)
    from cnequity.query import load
    from cnequity.config import load_config
    from cnequity.orchestrator.engine import JobEngine
    import cnequity.steps  # The pinned CLI registers these before constructing its engine.
    from cnequity.domain.market_time import SHANGHAI_TZ
    current = (datetime.now(timezone.utc) if now is None else now).astimezone(SHANGHAI_TZ)
    if target > current.date() or target == current.date() and current.time() < time(15, 5):
        return {"status": "WAITING_FOR_MARKET_CLOSE", "refresh_attempted": False}
    cfg = load_config(source_config)
    if os.name == "nt":
        # RawArchive's two hashes plus mkstemp suffix exceed legacy MAX_PATH.
        # CPython's explicit extended-length path reaches the SAME filesystem
        # location. No registry/global setting or upstream file is modified.
        original = cfg.data_root
        cfg.data_root = Path(extended_path_text(str(original)))
        if not cfg.data_root.samefile(original):
            raise ValueError("SOURCE_LAKE_CONFIG_MISMATCH")
    settings = tomllib.loads(export_config.read_text(encoding="utf-8"))
    if not Path(settings["paths"]["lake_root"]).samefile(cfg.data_root):
        raise ValueError("SOURCE_LAKE_CONFIG_MISMATCH")
    with proxy_policy("direct"):
        calendar = load("trading_calendar", start=str(after), end=str(target), data_root=cfg.data_root)
        sessions = sorted(r["trade_date"] for r in calendar.to_dicts()
                          if r["is_trading"] and after < r["trade_date"] <= target)
        if not sessions or sessions[-1] != target:
            return {"status": "WAITING_FOR_DATA", "reason": "OFFICIAL_CALENDAR_REQUIRED", "refresh_attempted": False}
        receipts = []
        for session in sessions:
            # Normal forward daily semantics, NOT backfill. No source code patch.
            result = session_job(JobEngine(cfg), session)
            receipts.append({"session": str(session), "run_id": result["run_id"],
                             "status": result["status"], "action": result["action"]})
            if result["status"] != "success":
                return {"status": "WAITING_FOR_DATA", "reason": "UPSTREAM_PUBLISH_NOT_READY",
                        "refresh_attempted": True, "receipts": receipts}
        settings["export"]["cutoff"] = str(target)
        result = export_lake_streaming(settings, load)
        return {"status": "REFRESH_EXPORTED", **result, "refresh_attempted": True, "receipts": receipts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source-config", type=Path, required=True)
    parser.add_argument("--export-config", type=Path, required=True)
    parser.add_argument("--target", type=date.fromisoformat, required=True)
    parser.add_argument("--after", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    try:
        with redirect_stdout(sys.stderr):
            result = forward(args.root, args.source_config, args.export_config, args.target, args.after)
    except Exception as error:
        # Provider readiness failure cannot produce a signal or invented cutoff.
        integrity = (getattr(error, "code", "") in ("PINNED_SOURCE_BLOCKER", "ISOLATED_SIDECAR_REQUIRED")
                     or isinstance(error, (ImportError, AttributeError, TypeError, NameError, ValueError)))
        result = {"status": "BLOCKED_INTEGRITY" if integrity else "WAITING_FOR_DATA", "reason": "UPSTREAM_REFRESH_NOT_READY",
                  "exception_class": type(error).__name__, "refresh_attempted": True}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
