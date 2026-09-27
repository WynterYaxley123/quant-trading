"""Independent evidence registry; no fuzzy names or inferred historical dates."""
from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

from ..runtime.exports import observed_time
from ..runtime.storage import GateError, contained, digest


@dataclass(frozen=True)
class VerifiedRegistry:
    entries: tuple[dict, ...]
    sha256: str
    identity: str = "VERIFIED_MAPPING_REGISTRY_V1"


def load_registry(path: Path, *, evidence_root: Path | None = None) -> VerifiedRegistry:
    try:
        body = path.read_bytes()
        doc = json.loads(body)
        if (doc.get("schema_version") != "1.0.0" or doc.get("registry_identity") != "VERIFIED_MAPPING_REGISTRY_V1"
                or doc.get("scope") != "CURRENT_FORWARD_ONLY" or not isinstance(doc.get("entries"), list)):
            raise GateError("MAPPING_REGISTRY_SCHEMA_BLOCKER")
        keys, entries = set(), []
        required = ("industry_code", "industry_name", "etf_code", "etf_name", "mapping_method",
                    "tracking_index_code", "tracking_index_name", "classification", "verification_status",
                    "verified_at", "effective_from", "effective_to", "notes", "available_at",
                    "source_provider", "source_url", "source_file", "source_sha256", "source_retrieved_at")
        for raw in doc["entries"]:
            if not isinstance(raw, dict) or not all(k in raw for k in required):
                raise GateError("MAPPING_REGISTRY_SCHEMA_BLOCKER")
            row = dict(raw)
            if (not re.fullmatch(r"[0-9]{6}", row["industry_code"])
                    or not re.fullmatch(r"[0-9]{6}\.(SH|SZ)", row["etf_code"])
                    or row["verification_status"] not in ("VERIFIED", "UNVERIFIED", "REJECTED")):
                raise GateError("MAPPING_REGISTRY_SCHEMA_BLOCKER")
            key = (row["industry_code"], row["etf_code"], row["effective_from"])
            if key in keys:
                raise GateError("MAPPING_REGISTRY_DUPLICATE_BLOCKER")
            keys.add(key)
            if row["verification_status"] == "VERIFIED":
                if (row["classification"] != "A_SHARE_INDUSTRY_OR_THEME_ETF"
                        or row["mapping_method"] not in ("TRACKING_INDEX_EXACT", "OFFICIAL_FUND_DOCUMENT")
                        or any(not isinstance(row[k], str) or not row[k].strip() for k in
                               ("industry_name", "etf_name", "tracking_index_code", "tracking_index_name", "source_provider"))
                        or not re.fullmatch(r"https:[/]{2}[^/@\s]+[/][^\s]*", row["source_url"] or "")
                        or not re.fullmatch(r"[a-zA-Z0-9_-]+\.(pdf|html|txt)", row["source_file"] or "")
                        or not re.fullmatch(r"[0-9a-f]{64}", row["source_sha256"] or "") or evidence_root is None):
                    raise GateError("MAPPING_EVIDENCE_BLOCKER")
                if digest(contained(evidence_root, row["source_file"]).read_bytes()) != row["source_sha256"]:
                    raise GateError("MAPPING_EVIDENCE_HASH_BLOCKER")
                row["verified_at"] = observed_time(row["verified_at"])
                row["available_at"] = observed_time(row["available_at"])
                row["source_retrieved_at"] = observed_time(row["source_retrieved_at"])
                row["effective_from"] = date.fromisoformat(row["effective_from"])
                row["effective_to"] = date.fromisoformat(row["effective_to"]) if row["effective_to"] else None
                if (not row["source_retrieved_at"] <= row["verified_at"] <= row["available_at"]
                        or row["effective_from"] < row["available_at"].date()
                        or row["effective_to"] and row["effective_to"] <= row["effective_from"]):
                    raise GateError("MAPPING_TEMPORAL_BLOCKER")
            entries.append(row)
        return VerifiedRegistry(tuple(entries), digest(body))
    except GateError:
        raise
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise GateError("MAPPING_REGISTRY_SCHEMA_BLOCKER") from error


def active(row, day, signal_at):
    return (row["verification_status"] == "VERIFIED" and row["classification"] == "A_SHARE_INDUSTRY_OR_THEME_ETF"
        and row["available_at"] <= signal_at and row["effective_from"] <= day
        and (row["effective_to"] is None or day < row["effective_to"]))


def eligible_bar(provider, symbol, day):
    """Positive finalized bar is evidence of trade, not an EastMoney assertion.

    A credible explicit halt/delist overrides the bar. Unknown/zero turnover
    fails closed. EastMoney's ETF board cannot prove an ETF is normal.
    """
    instruments = provider.tables["instruments"]
    inst = instruments.loc[instruments.symbol == symbol]
    if len(inst) != 1:
        return None, "INSTRUMENT_UNKNOWN"
    r = inst.iloc[0]
    if (r.asset_type != "etf" or r.list_date is None or r.list_date > day
            or r.delist_date is not None and r.delist_date <= day
            or r.prev_symbol is not None):
        return None, "LISTING_OR_SYMBOL_CONTINUITY_UNPROVEN"
    frame = provider.tables["etf_bars"]
    rows = frame.loc[(frame.symbol == symbol) & (frame.trade_date == day)]
    if len(rows) != 1:
        return None, "BAR_MISSING_OR_DUPLICATE"
    b = rows.iloc[0].to_dict()
    if (not all(pd.notna(b[k]) and np.isfinite(b[k]) and b[k] > 0 for k in ("open", "high", "low", "close", "volume", "amount"))
            or b["high"] < max(b["open"], b["close"], b["low"])
            or b["low"] > min(b["open"], b["close"], b["high"])
            or b["amount"] < 1 or b["source"] not in ("tdx_protocol", "sina", "eastmoney", "exchange")):
        return None, "INVALID_BAR_OR_TURNOVER_EVIDENCE"
    status = provider.tables["trading_status"]
    statuses = status.loc[(status.symbol == symbol) & (status.trade_date == day)]
    for s in statuses.to_dict("records"):
        if s["source"] in ("exchange", "sse", "szse") and (s["is_trading"] is not True or s["status"] != "normal"):
            return None, "EXCHANGE_NONTRADABLE"
    # Proof is nonzero finalized real bar, never inferred risk_warning=False.
    return b, "FINALIZED_REAL_BAR_EVIDENCE"


def select_mappings(registry, rankings, provider, *, signal_at, require_execution=False):
    signal_day = signal_at.date()
    if signal_day not in provider.sessions or provider.cutoff != signal_day:
        raise GateError("MAPPING_CALENDAR_BLOCKER")
    i = provider.sessions.index(signal_day)
    if i < 19 or i + 1 >= len(provider.sessions):
        raise GateError("MAPPING_CALENDAR_BLOCKER")
    execution_day = provider.sessions[i + 1]
    window = provider.sessions[i - 19:i + 1]
    chosen, diagnostics, used = [], [], set()
    # Frozen industry Top5, not a silent descent into lower-ranked industries.
    for rank in rankings[:5]:
        code = rank.industry_code
        admitted = []
        for row in (r for r in registry.entries if r["industry_code"] == code):
            reason = None
            if not active(row, signal_day, signal_at) or not active(row, execution_day, signal_at):
                reason = "MAPPING_TEMPORAL_OR_VERIFICATION_BLOCKER"
            bars = []
            if reason is None:
                for day in window:
                    bar, why = eligible_bar(provider, row["etf_code"], day)
                    if bar is None:
                        reason = "LIQUIDITY_20_SESSION_BLOCKER:" + why
                        break
                    bars.append(bar)
            if reason is None and require_execution:
                _, why = eligible_bar(provider, row["etf_code"], execution_day)
                if why != "FINALIZED_REAL_BAR_EVIDENCE":
                    reason = "T1_OPEN_UNAVAILABLE"
            if reason is None:
                admitted.append((float(np.mean([b["amount"] for b in bars])), row))
            diagnostics.append({"industry_code": code, "etf_code": row["etf_code"], "reason": reason,
                "verification_status": row["verification_status"], "liquidity_sessions": len(bars),
                "mean_amount_cny": None if reason else admitted[-1][0]})
        for liquidity, row in sorted(admitted, key=lambda v: (-v[0], v[1]["etf_code"])):
            if row["etf_code"] in used:
                continue
            used.add(row["etf_code"])
            chosen.append({**row, "score": rank.score, "industry_rank": rank.rank, "mean_amount_cny": liquidity})
            break
    if len(chosen) != 5 or len(used) != 5:
        return {"status": "MAPPING_ADMISSION_BLOCKED", "selected": [], "diagnostics": diagnostics,
                "reason": "FIVE_DISTINCT_VERIFIED_EXECUTABLE_ETFS_REQUIRED", "registry_hash": registry.sha256}
    return {"status": "READY", "selected": chosen, "diagnostics": diagnostics, "reason": None,
            "registry_hash": registry.sha256, "execution_date": execution_day}
