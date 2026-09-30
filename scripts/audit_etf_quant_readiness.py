"""Memory-bounded, retrospective ETF-Quant data/factor/model readiness audit.

Consumes the repo-external, pinned-CNEquity constituent matrix, never the lake
directly. Uses the existing frozen Source-C date gate and 19-factor engine.
It never emits a formal signal, fit, intent, fill, NAV or performance result.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
import hashlib
from itertools import groupby
import json
import math
import os
from pathlib import Path
import uuid

import numpy as np
import pandas as pd

from strategies.etf_quant.config import FACTORS_19
from strategies.etf_quant.data.source_c import industry_date
from strategies.etf_quant.domain import StrategyConfig
from strategies.etf_quant.factors import compute_close_factors


CONTRACT = "ETF_QUANT_RETROSPECTIVE_READINESS_AUDIT_V1"


def _external(path: Path, *, directory: bool) -> Path:
    resolved = path.resolve(strict=True)
    if resolved.is_dir() != directory:
        raise ValueError("EXPECTED_EXTERNAL_DIRECTORY_OR_FILE")
    if any((p / ".git").exists() for p in (resolved, *resolved.parents)):
        raise ValueError("GIT_PATH_FOR_REAL_DATA_BLOCKED")
    return resolved


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _flag(value: str) -> bool:
    if value not in ("True", "False"):
        raise ValueError("MATRIX_BOOLEAN_SCHEMA_BLOCKER")
    return value == "True"


def advance_source_c(state: dict, day: date, code: str, rows: list[dict]) -> dict:
    """Apply frozen 5/80% gate; mirror strict recursive-prefix lifecycle.

    The frozen runtime starts an unstarted series at 1000 from current bars,
    requires adjacent-session returns thereafter, and never restarts after a
    broken prefix. The matrix already rejected nonexact/invalid bar returns.
    """
    symbols = [r["symbol"] for r in rows]
    if len(symbols) != len(set(symbols)) or not symbols:
        raise ValueError("DUPLICATE_OR_EMPTY_CONSTITUENT_GROUP")
    eligible = len(rows)
    startable = [r for r in rows if _flag(r["bar_valid"])
                 and _flag(r["adj_is_exact"]) and r["adj_close"]]
    previous = state.get(code)
    if previous is None:
        previous = {"started": False, "broken": False, "level": None}
        state[code] = previous
    started, broken = previous["started"], previous["broken"]

    if not started:
        valid = len(startable)
        ratio = valid / eligible
        passed = valid >= 5 and ratio >= .8
        if passed:
            previous.update(started=True, level=1000.0)
        return {"date": day, "industry_code": code, "eligible": eligible,
                "valid": valid, "coverage": ratio, "date_gate_valid": passed,
                "source_c_valid": passed, "close": previous["level"] if passed else None,
                "reason": "BASE_INIT" if passed else "BASE_INSUFFICIENT_COVERAGE"}

    valid_rows = [r for r in rows if _flag(r["return_valid"])]
    closes = {r["symbol"]: float(r["adj_close"]) for r in valid_rows}
    prevs = {r["symbol"]: float(r["prev_adj_close"]) for r in valid_rows}
    exact = {r["symbol"]: True for r in valid_rows}
    result = industry_date(day, code, symbols, closes, prevs, exact)
    if result.valid != len(valid_rows):
        raise ValueError("MATRIX_SOURCE_C_VALID_COUNT_MISMATCH")
    if not result.valid_date:
        previous["broken"] = True
    if result.valid_date and not broken and result.industry_return is not None:
        level = previous["level"] * (1.0 + result.industry_return)
        if not math.isfinite(level) or level <= 0:
            raise ValueError("SOURCE_C_LEVEL_INVALID")
        previous["level"] = level
    usable = result.valid_date and not previous["broken"]
    return {"date": day, "industry_code": code, "eligible": eligible,
            "valid": result.valid, "coverage": result.coverage_ratio,
            "date_gate_valid": result.valid_date, "source_c_valid": usable,
            "close": previous["level"] if usable else None,
            "reason": "RECURSIVE_PREFIX_BROKEN" if previous["broken"] else
                      "INSUFFICIENT_COVERAGE" if not result.valid_date else None}


def _write_json(outdir: Path, name: str, value: dict) -> Path:
    path = outdir / name
    if path.exists():
        raise ValueError("IMMUTABLE_AUDIT_OUTPUT_EXISTS")
    temp = outdir / ("." + name + "." + uuid.uuid4().hex + ".partial")
    with temp.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    return path


def audit(matrix_path: Path, summary_path: Path, outdir: Path) -> dict:
    matrix_path = _external(matrix_path, directory=False)
    summary_path = _external(summary_path, directory=False)
    outdir = _external(outdir, directory=True)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if (summary.get("contract") != "PRODUCTION_CONSTITUENT_COVERAGE_MATRIX_V3"
            or summary.get("matrix_file") != matrix_path.name
            or summary.get("matrix_sha256") != _sha256(matrix_path)):
        raise ValueError("MATRIX_INPUT_HASH_OR_CONTRACT_BLOCKER")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    state: dict[str, dict] = {}
    records: list[dict] = []
    unresolved_with_bar = 0
    with matrix_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        needed = {"trade_date", "industry_code", "symbol", "instrument_resolved",
                  "bar_available", "bar_valid", "adj_is_exact", "return_valid",
                  "adj_close", "prev_adj_close"}
        if not needed.issubset(reader.fieldnames or []):
            raise ValueError("MATRIX_COLUMNS_BLOCKER")
        last_key = None
        for (day_s, code), group in groupby(reader, key=lambda r: (r["trade_date"], r["industry_code"])):
            key = day_s, code
            if last_key is not None and key <= last_key:
                raise ValueError("MATRIX_DATE_INDUSTRY_ORDER_BLOCKER")
            rows = list(group)
            unresolved_with_bar += sum(not _flag(r["instrument_resolved"]) and _flag(r["bar_available"])
                                       for r in rows)
            records.append(advance_source_c(state, date.fromisoformat(day_s), code, rows))
            last_key = key
    if len(records) != summary["industry_sessions"]:
        raise ValueError("MATRIX_GROUP_COUNT_BLOCKER")
    days = sorted({r["date"] for r in records})
    codes = sorted({r["industry_code"] for r in records})
    if len(days) != summary["sessions"] or len(records) != len(days) * len(codes):
        raise ValueError("MATRIX_INCOMPLETE_RECTANGLE_BLOCKER")
    frame = pd.DataFrame(records)
    closes = frame.pivot(index="date", columns="industry_code", values="close")
    closes.index = pd.DatetimeIndex(closes.index)
    closes = closes.reindex(index=pd.DatetimeIndex(days), columns=codes)
    factors = {code: compute_close_factors(closes[code]) for code in codes}
    ready = {code: np.isfinite(factors[code].to_numpy(dtype=float)) for code in codes}
    factor_rows = []
    contiguous = closes.notna().rolling(120, min_periods=120).sum() == 120
    per_factor = Counter()
    signal_ready = {}
    for i, day in enumerate(days):
        for code in codes:
            flags = {factor: bool(ready[code][i, j]) for j, factor in enumerate(FACTORS_19)}
            values = factors[code].iloc[i]
            per_factor.update(k for k, v in flags.items() if v)
            all_ready = all(flags.values())
            row = {"trade_date": day.isoformat(), "industry_code": code,
                   "source_c_valid": bool(pd.notna(closes.iloc[i][code])),
                   "source_c_close": float(closes.iloc[i][code]) if pd.notna(closes.iloc[i][code]) else None,
                   "lookback_ready": bool(contiguous.iloc[i][code]),
                   **{name + "_finite": value for name, value in flags.items()},
                   **{name: float(values[name]) if flags[name] else None for name in FACTORS_19},
                   "all_required_factors_ready": all_ready,
                   "invalid_reason": None if all_ready else "SOURCE_C_LEVEL_INVALID" if pd.isna(closes.iloc[i][code])
                                     else "FACTOR_LOOKBACK_INCOMPLETE"}
            factor_rows.append(row)
            if i == len(days) - 1:
                signal_ready[code] = flags

    factor_path = outdir / f"etf_quant_factor_readiness_{run_id}.csv"
    temp = outdir / ("." + factor_path.name + "." + uuid.uuid4().hex + ".partial")
    with temp.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(factor_rows[0]))
        writer.writeheader()
        writer.writerows(factor_rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, factor_path)

    config = StrategyConfig()
    position = {day: i for i, day in enumerate(days)}
    horizon_reports = {}
    individually_mature = defaultdict(dict)
    eligible_by_horizon_date = defaultdict(lambda: defaultdict(set))
    for spec in config.horizons:
        h = int(spec.horizon)
        cutoff = days[-1 - h]
        window_start = (pd.Timestamp(cutoff) - pd.DateOffset(months=6)).date()
        candidate_days = [d for d in days if window_start <= d <= cutoff]
        full_dates = 0
        drop_reasons = Counter()
        per_industry = Counter()
        for day in candidate_days:
            end = days[position[day] + h]
            eligible = 0
            for code in codes:
                source_start, source_end = closes.at[pd.Timestamp(day), code], closes.at[pd.Timestamp(end), code]
                if not math.isfinite(source_start) or not math.isfinite(source_end):
                    drop_reasons["SOURCE_C_START_OR_LABEL_END_INVALID"] += 1
                elif not np.isfinite(factors[code].loc[pd.Timestamp(day), list(spec.factor_names)].to_numpy(dtype=float)).all():
                    drop_reasons["FEATURE_NONFINITE"] += 1
                else:
                    eligible += 1
                    per_industry[code] += 1
                    eligible_by_horizon_date[h][day].add(code)
            full_dates += eligible == len(codes)
        individually_mature[h] = dict(per_industry)
        horizon_reports[str(h)] = {
            "label_cutoff": cutoff.isoformat(), "window_start": window_start.isoformat(),
            "candidate_training_dates": len(candidate_days), "label_end_mature_dates": len(candidate_days),
            "training_dates_full_frozen_universe": full_dates,
            "training_observations_full_frozen_universe": full_dates * len(codes),
            "eligible_individual_observations": sum(per_industry.values()),
            "feature_dimensions": len(spec.factor_names),
            "signal_date_feature_ready_industries": sum(all(signal_ready[c][f] for f in spec.factor_names) for c in codes),
            "drop_reasons_industry_observations": dict(drop_reasons),
            "minimum_training_days": spec.minimum_valid_training_days,
            "actual_ridge_fit": False,
        }

    diagnostic_common = [code for code in codes if all(
        all(signal_ready[code][f] for f in spec.factor_names)
        and individually_mature[int(spec.horizon)].get(code, 0) >= spec.minimum_valid_training_days
        for spec in config.horizons)]
    for spec in config.horizons:
        h = int(spec.horizon)
        horizon_reports[str(h)]["training_dates_diagnostic_common_universe"] = sum(
            set(diagnostic_common).issubset(eligible)
            for eligible in eligible_by_horizon_date[h].values())
        horizon_reports[str(h)]["training_observations_diagnostic_common_universe"] = (
            horizon_reports[str(h)]["training_dates_diagnostic_common_universe"] * len(diagnostic_common))
    report = {
        "contract": CONTRACT,
        "classification": "HISTORICAL_ENGINEERING_VALIDATION_ONLY",
        "formal_model_run": False,
        "prediction_generated": False,
        "performance_read": False,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "fixed_data_cutoff": days[-1].isoformat(),
        "source_matrix": str(matrix_path), "source_matrix_sha256": summary["matrix_sha256"],
        "factor_matrix": str(factor_path), "factor_matrix_sha256": _sha256(factor_path),
        "sessions": len(days), "industries": len(codes),
        "industry_sessions": len(records),
        "source_c_usable_industry_sessions": int(closes.notna().to_numpy().sum()),
        "source_c_usable_industries_at_cutoff": int(closes.iloc[-1].notna().sum()),
        "factor_finite_counts": dict(per_factor),
        "all_19_finite_industry_sessions": sum(r["all_required_factors_ready"] for r in factor_rows),
        "all_19_finite_industries_at_cutoff": sum(r["all_required_factors_ready"] for r in factor_rows[-len(codes):]),
        "unresolved_identity_with_market_bar_member_sessions": unresolved_with_bar,
        "horizons": horizon_reports,
        "diagnostic_common_universe": diagnostic_common,
        "diagnostic_common_universe_size": len(diagnostic_common),
        "diagnostic_common_universe_is_formal_policy": False,
        "availability_warning": "Historical membership publication times UNKNOWN; data observed after fixed cutoff; no ex-ante model fit or prediction asserted.",
    }
    path = _write_json(outdir, f"etf_quant_readiness_{run_id}.json", report)
    return {"report": str(path), "factor_matrix": str(factor_path),
            "source_c_usable": report["source_c_usable_industry_sessions"],
            "source_c_cutoff_industries": report["source_c_usable_industries_at_cutoff"],
            "all_19_finite_cutoff_industries": report["all_19_finite_industries_at_cutoff"],
            "diagnostic_common_universe_size": len(diagnostic_common)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.matrix, args.summary, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
