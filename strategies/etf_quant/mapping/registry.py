"""Independent evidence registry at the frozen Shenwan **L2** production level.

Contract
--------
``ETF_QUANT_INDUSTRY_LEVEL_V1 = "SHENWAN_L2"``

A registry entry keys on a 4-digit Shenwan 2021 Level-2 code that must exist in
the sealed taxonomy artifact (``config/shenwan_industry_taxonomy_v1.json``) and
whose ``industry_name`` must equal that artifact's official name for the code.
The L3-keyed shape of the previous revision is refused outright: the frozen
model ranks Level 2, so a Level-3 key could never be exercised and would only
have hidden the granularity fork.

No fuzzy names, no prefix truncation, no inferred historical dates, and no
name-only admission are implemented here.
"""

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from ..domain.industry_level import (
    ETF_QUANT_INDUSTRY_LEVEL_V1,
    TAXONOMY_IDENTITY,
    TaxonomyError,
    default_taxonomy,
)
from ..runtime.exports import observed_time
from ..runtime.storage import GateError, contained, digest
from .liquidity import LIQUIDITY_SESSIONS, LiquidityLookup, assess_liquidity, liquidity_window

REGISTRY_IDENTITY = "VERIFIED_MAPPING_REGISTRY_V1"
VERIFICATION_STATES = ("VERIFIED", "UNVERIFIED", "REJECTED")
MAPPING_METHODS = ("TRACKING_INDEX_EXACT", "OFFICIAL_FUND_DOCUMENT")
CLASSIFICATION = "A_SHARE_INDUSTRY_OR_THEME_ETF"
#: Broad-market index codes that can never evidence a Shenwan Level-2 industry.
#: Keyed on the official index code, never on a fund or index name, so the guard
#: is deterministic and cannot be satisfied by a lucky title.
BROAD_MARKET_INDEX_CODES = frozenset(
    (
        "000001.SH",
        "000016.SH",
        "000300.SH",
        "000688.SH",
        "000852.SH",
        "000905.SH",
        "000906.SH",
        "000985.CSI",
        "399001.SZ",
        "399005.SZ",
        "399006.SZ",
        "399300.SZ",
        "399905.SZ",
        "399852.SZ",
        "000001",
        "000016",
        "000300",
        "000688",
        "000852",
        "000905",
        "000906",
        "000985",
        "399001",
        "399005",
        "399006",
    )
)
REQUIRED_FIELDS = (
    "industry_level",
    "industry_code",
    "industry_name",
    "etf_code",
    "etf_name",
    "mapping_method",
    "tracking_index_code",
    "tracking_index_name",
    "tracking_target",
    "classification",
    "verification_status",
    "verified",
    "evidence_source",
    "evidence_type",
    "evidence_observed_at",
    "verified_at",
    "effective_from",
    "effective_to",
    "notes",
    "available_at",
    "source_provider",
    "source_url",
    "source_file",
    "source_sha256",
    "source_retrieved_at",
)


@dataclass(frozen=True)
class VerifiedRegistry:
    entries: tuple[dict, ...]
    sha256: str
    industry_level: str = ETF_QUANT_INDUSTRY_LEVEL_V1
    taxonomy_identity: str = TAXONOMY_IDENTITY
    taxonomy_sha256: str | None = None
    identity: str = REGISTRY_IDENTITY


def load_registry(path: Path, *, evidence_root: Path | None = None) -> VerifiedRegistry:
    taxonomy = default_taxonomy()
    try:
        body = path.read_bytes()
        doc = json.loads(body)
        if (
            doc.get("schema_version") != "1.0.0"
            or doc.get("registry_identity") != REGISTRY_IDENTITY
            or doc.get("scope") != "CURRENT_FORWARD_ONLY"
            or doc.get("industry_level") != ETF_QUANT_INDUSTRY_LEVEL_V1
            or doc.get("taxonomy_identity") != TAXONOMY_IDENTITY
            or not isinstance(doc.get("entries"), list)
        ):
            raise GateError("MAPPING_REGISTRY_SCHEMA_BLOCKER")
        keys, entries = set(), []
        for raw in doc["entries"]:
            if not isinstance(raw, dict) or not all(k in raw for k in REQUIRED_FIELDS):
                raise GateError("MAPPING_REGISTRY_SCHEMA_BLOCKER")
            row = dict(raw)
            if (
                row["industry_level"] != ETF_QUANT_INDUSTRY_LEVEL_V1
                or not isinstance(row["industry_code"], str)
                or not re.fullmatch(r"[0-9]{4}", row["industry_code"])
                or not re.fullmatch(r"[0-9]{6}\.(SH|SZ)", row["etf_code"] or "")
                or row["verification_status"] not in VERIFICATION_STATES
                or not isinstance(row["verified"], bool)
            ):
                raise GateError("MAPPING_REGISTRY_SCHEMA_BLOCKER")
            try:
                taxonomy.assert_level(row["industry_code"])
                official_name = taxonomy.name_of(row["industry_code"])
            except TaxonomyError as error:
                raise GateError(error.code, error.details) from error
            if row["verified"] is not (row["verification_status"] == "VERIFIED"):
                raise GateError("MAPPING_VERIFICATION_FLAG_BLOCKER")
            if row["tracking_index_code"] in BROAD_MARKET_INDEX_CODES:
                # 510300 tracks 沪深300: a broad-market fund is never a Shenwan
                # Level-2 industry fund, whatever its name or category says.
                raise GateError(
                    "MAPPING_BROAD_INDEX_BLOCKER",
                    {
                        "etf_code": row["etf_code"],
                        "tracking_index_code": row["tracking_index_code"],
                    },
                )
            if row["industry_name"] != official_name:
                # A name that disagrees with the sealed taxonomy is drift, not a label.
                raise GateError(
                    "MAPPING_INDUSTRY_NAME_BLOCKER",
                    {
                        "industry_code": row["industry_code"],
                        "registry_name": row["industry_name"],
                        "taxonomy_name": official_name,
                    },
                )
            if row["classification"] != CLASSIFICATION and row["verification_status"] == "VERIFIED":
                raise GateError("MAPPING_EVIDENCE_BLOCKER")
            if row["classification"] != CLASSIFICATION and row["verification_status"] != "VERIFIED":
                raise GateError("MAPPING_REGISTRY_SCHEMA_BLOCKER")
            key = (row["industry_code"], row["etf_code"], row["effective_from"])
            if key in keys:
                raise GateError("MAPPING_REGISTRY_DUPLICATE_BLOCKER")
            keys.add(key)
            row["evidence_observed_at"] = observed_time(row["evidence_observed_at"])
            if row["verification_status"] == "VERIFIED":
                if (
                    row["mapping_method"] not in MAPPING_METHODS
                    or any(
                        not isinstance(row[k], str) or not row[k].strip()
                        for k in (
                            "industry_name",
                            "etf_name",
                            "tracking_index_code",
                            "tracking_index_name",
                            "tracking_target",
                            "evidence_source",
                            "source_provider",
                        )
                    )
                    or not isinstance(row["evidence_type"], str)
                    or not row["evidence_type"].strip()
                    or not re.fullmatch(r"https:[/]{2}[^/@\s]+[/][^\s]*", row["source_url"] or "")
                    or not re.fullmatch(
                        r"[a-zA-Z0-9_-]+\.(pdf|html|txt|xls|xlsx)", row["source_file"] or ""
                    )
                    or not re.fullmatch(r"[0-9a-f]{64}", row["source_sha256"] or "")
                    or evidence_root is None
                ):
                    raise GateError("MAPPING_EVIDENCE_BLOCKER")
                if (
                    digest(contained(evidence_root, row["source_file"]).read_bytes())
                    != row["source_sha256"]
                ):
                    raise GateError("MAPPING_EVIDENCE_HASH_BLOCKER")
                row["verified_at"] = observed_time(row["verified_at"])
                row["available_at"] = observed_time(row["available_at"])
                row["source_retrieved_at"] = observed_time(row["source_retrieved_at"])
                row["effective_from"] = date.fromisoformat(row["effective_from"])
                row["effective_to"] = (
                    date.fromisoformat(row["effective_to"]) if row["effective_to"] else None
                )
                if (
                    not row["source_retrieved_at"]
                    <= row["evidence_observed_at"]
                    <= row["verified_at"]
                    <= row["available_at"]
                    or row["effective_from"] < row["available_at"].date()
                    or row["effective_to"]
                    and row["effective_to"] <= row["effective_from"]
                ):
                    raise GateError("MAPPING_TEMPORAL_BLOCKER")
                if row["evidence_source"] != row["source_provider"]:
                    raise GateError("MAPPING_EVIDENCE_SOURCE_BLOCKER")
            entries.append(row)
        return VerifiedRegistry(tuple(entries), digest(body), taxonomy_sha256=taxonomy.sha256)
    except GateError:
        raise
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise GateError("MAPPING_REGISTRY_SCHEMA_BLOCKER") from error


def active(row, day, signal_at):
    return (
        row["verification_status"] == "VERIFIED"
        and row["classification"] == CLASSIFICATION
        and row["available_at"] <= signal_at
        and row["effective_from"] <= day
        and (row["effective_to"] is None or day < row["effective_to"])
    )


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
    if (
        r.asset_type != "etf"
        or r.list_date is None
        or r.list_date > day
        or r.delist_date is not None
        and r.delist_date <= day
        or r.prev_symbol is not None
    ):
        return None, "LISTING_OR_SYMBOL_CONTINUITY_UNPROVEN"
    frame = provider.tables["etf_bars"]
    rows = frame.loc[(frame.symbol == symbol) & (frame.trade_date == day)]
    if len(rows) != 1:
        return None, "BAR_MISSING_OR_DUPLICATE"
    b = rows.iloc[0].to_dict()
    if (
        not all(
            pd.notna(b[k]) and np.isfinite(b[k]) and b[k] > 0
            for k in ("open", "high", "low", "close", "volume", "amount")
        )
        or b["high"] < max(b["open"], b["close"], b["low"])
        or b["low"] > min(b["open"], b["high"], b["close"])
        or b["amount"] < 1
        or b["source"] not in ("tdx_protocol", "sina", "eastmoney", "exchange", "ths")
    ):
        return None, "INVALID_BAR_OR_TURNOVER_EVIDENCE"
    status = provider.tables["trading_status"]
    statuses = status.loc[(status.symbol == symbol) & (status.trade_date == day)]
    for s in statuses.to_dict("records"):
        if s["source"] in ("exchange", "sse", "szse") and (
            s["is_trading"] is not True or s["status"] != "normal"
        ):
            return None, "EXCHANGE_NONTRADABLE"
    # Proof is nonzero finalized real bar, never inferred risk_warning=False.
    return b, "FINALIZED_REAL_BAR_EVIDENCE"


def select_mappings(registry, rankings, provider, *, signal_at, require_execution=False):
    """Frozen L2 Top5 -> five distinct verified, liquidity-passing ETFs.

    Industry order is the frozen fused ranking. Within one industry the
    representative is the highest 20-session mean ``amount`` among admitted
    candidates; an ETF already taken by a higher-ranked industry is skipped and
    the next admitted candidate for that industry is tried. The industry itself
    is never silently replaced by a lower-ranked industry, and an ETF is never
    reused to pretend five assets exist.
    """
    taxonomy = default_taxonomy()
    if registry.industry_level != ETF_QUANT_INDUSTRY_LEVEL_V1:
        raise GateError(
            "INDUSTRY_LEVEL_CONTRACT_BLOCKER", {"registry_level": registry.industry_level}
        )
    signal_day = signal_at.date()
    if signal_day not in provider.sessions or provider.cutoff != signal_day:
        raise GateError("MAPPING_CALENDAR_BLOCKER")
    window, execution_day = liquidity_window(provider, signal_day)
    if window is None or execution_day is None:
        raise GateError("MAPPING_CALENDAR_BLOCKER")
    chosen, diagnostics, used, collision = [], [], set(), False
    lookup = LiquidityLookup.build(provider.tables)
    blocked_industries, missing_industries = [], []
    for rank in rankings[:5]:
        code = rank.industry_code
        try:
            taxonomy.assert_level(code)
        except TaxonomyError as error:
            raise GateError("INDUSTRY_LEVEL_CONTRACT_BLOCKER", error.details) from error
        admitted, blocked = [], []
        for row in (r for r in registry.entries if r["industry_code"] == code):
            if not active(row, signal_day, signal_at) or not active(row, execution_day, signal_at):
                blocked.append(
                    {
                        "etf_code": row["etf_code"],
                        "reason": "MAPPING_TEMPORAL_OR_VERIFICATION_BLOCKER",
                    }
                )
                continue
            liquidity = assess_liquidity(provider, row["etf_code"], window, lookup=lookup)
            if not liquidity.passed:
                blocked.append(
                    {
                        "etf_code": row["etf_code"],
                        "reason": "%s:%s" % (liquidity.status, liquidity.reason),
                    }
                )
                continue
            if require_execution:
                _, why = eligible_bar(provider, row["etf_code"], execution_day)
                if why != "FINALIZED_REAL_BAR_EVIDENCE":
                    blocked.append(
                        {"etf_code": row["etf_code"], "reason": "T1_OPEN_UNAVAILABLE:" + why}
                    )
                    continue
            admitted.append((liquidity, row))
        for entry in blocked:
            diagnostics.append(
                {
                    "industry_level": ETF_QUANT_INDUSTRY_LEVEL_V1,
                    "industry_code": code,
                    "verification_status": "NOT_EXECUTABLE",
                    "liquidity_sessions": 0,
                    "mean_amount_cny": None,
                    **entry,
                }
            )
        for liquidity, row in sorted(
            admitted, key=lambda v: (-(v[0].mean_amount_cny or 0.0), v[1]["etf_code"])
        ):
            diagnostics.append(
                {
                    "industry_level": ETF_QUANT_INDUSTRY_LEVEL_V1,
                    "industry_code": code,
                    "etf_code": row["etf_code"],
                    "reason": None,
                    "verification_status": row["verification_status"],
                    "liquidity_sessions": liquidity.sessions_present,
                    "mean_amount_cny": liquidity.mean_amount_cny,
                    "liquidity_window": [str(d) for d in window],
                }
            )
            if row["etf_code"] in used:
                # The frozen industry is never swapped for a lower-ranked one and
                # an ETF is never reused; the next admitted candidate is tried.
                collision = True
                continue
            used.add(row["etf_code"])
            chosen.append(
                {
                    **row,
                    "score": rank.score,
                    "industry_rank": rank.rank,
                    "mean_amount_cny": liquidity.mean_amount_cny,
                    "liquidity_sessions": liquidity.sessions_present,
                    "liquidity_window": [str(d) for d in window],
                }
            )
            break
        else:
            blocked_industries.append(code)
            if not admitted:
                missing_industries.append(code)
    if len(chosen) != 5 or len(used) != 5:
        # §16: fewer than five DISTINCT executable ETFs is its own verdict, and the
        # shortfall is reported separately so the cause is never hidden.
        if collision and missing_industries:
            shortfall = "MIXED"
        elif collision:
            shortfall = "CANDIDATE_COLLISION"
        else:
            shortfall = "NO_ADMISSIBLE_CANDIDATE"
        return {
            "status": "MAPPING_ADMISSION_BLOCKED",
            "selected": [],
            "diagnostics": diagnostics,
            "reason": "DISTINCT_EXECUTABLE_ETF_BLOCKER",
            "shortfall": shortfall,
            "distinct_etf_count": len(used),
            "industries_without_candidate": missing_industries,
            "blocked_industries": blocked_industries,
            "industry_level": ETF_QUANT_INDUSTRY_LEVEL_V1,
            "registry_hash": registry.sha256,
            "liquidity_window": [str(d) for d in window],
            "liquidity_sessions": LIQUIDITY_SESSIONS,
        }
    return {
        "status": "READY",
        "selected": chosen,
        "diagnostics": diagnostics,
        "reason": None,
        "industry_level": ETF_QUANT_INDUSTRY_LEVEL_V1,
        "registry_hash": registry.sha256,
        "taxonomy_identity": registry.taxonomy_identity,
        "liquidity_window": [str(d) for d in window],
        "liquidity_sessions": LIQUIDITY_SESSIONS,
        "execution_date": execution_day,
    }
