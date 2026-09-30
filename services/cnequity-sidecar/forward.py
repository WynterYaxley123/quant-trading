"""One bounded forward refresh through the PINNED upstream job/publish gates.

External isolated sidecar only. No direct curated writes or new provider.
"""
import argparse
from datetime import date, datetime, time, timezone
import json
from pathlib import Path
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
    settings = tomllib.loads(export_config.read_text(encoding="utf-8"))
    if Path(settings["paths"]["lake_root"]).resolve() != Path(cfg.data_root).resolve():
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
            result = JobEngine(cfg).run_job("etf_quant_forward", trade_date=session, steps=STEPS)
            receipts.append({"session": str(session), "run_id": result["run_id"], "status": result["status"]})
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
