"""Point-in-time execution evidence for the explicitly opted-in B40 runtime.

The external book is an audited, immutable extraction of official constituent
weights and Shenwan classifications. It is never generated from today's ETF
names or the research candidate. Source bytes and the extraction are hashed;
publication, observation and availability remain separate timestamps.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
import re

from ..domain.industry_level import ETF_QUANT_INDUSTRY_LEVEL_V1, default_taxonomy
from ..portfolio.policy import IndustryCandidate, POLICY_B40_WITH_CASH
from ..runtime.exports import observed_time
from ..runtime.storage import GateError, contained, digest, json_bytes
from .liquidity import LIQUIDITY_SESSIONS, assess_liquidity, liquidity_window
from .partial import select_mappings_partial
from .proxy import OFFICIAL_WEIGHT, build_benchmark_exposure, parse_weight_pct
from .registry import active


IDENTITY = "POINT_IN_TIME_EXECUTION_EVIDENCE_V1"
OFFICIAL_HOST_SUFFIXES = ("csindex.com.cn", "cnindex.com.cn", "sse.com.cn", "szse.cn", "swsresearch.com")


def _official_url(url):
    if not isinstance(url, str):
        return False
    match = re.fullmatch(r"https:[/]{2}([^/@:\s]+)(/[^\s#]+)", url)
    if match is None:
        return False
    host = match.group(1).lower()
    return any(
        host == suffix or host.endswith("." + suffix) for suffix in OFFICIAL_HOST_SUFFIXES)


def _source(root: Path, record: dict, prefix: str) -> bytes:
    name, expected, url = (record.get(prefix + field) for field in ("_file", "_sha256", "_url"))
    if (not isinstance(name, str) or not name or "/" in name or "\\" in name
            or not isinstance(expected, str) or len(expected) != 64
            or any(c not in "0123456789abcdef" for c in expected) or not _official_url(url)):
        raise GateError("PIT_OFFICIAL_SOURCE_IDENTITY_BLOCKER")
    body = contained(root, name).read_bytes()
    if digest(body) != expected:
        raise GateError("PIT_OFFICIAL_SOURCE_HASH_BLOCKER")
    return body


@dataclass(frozen=True)
class PITRecord:
    industry_code: str
    etf_code: str
    etf_name: str
    benchmark_code: str
    available_at: datetime
    source_publication_at: datetime
    evidence_observed_at: datetime
    constituent_effective_date: date
    weight_effective_date: date
    valid_through: date
    exposure: object
    evidence_id: str
    evidence_hash: str


@dataclass(frozen=True)
class PITEvidenceBook:
    records: tuple[PITRecord, ...]
    sha256: str

    def prefix(self, decision_at: datetime):
        return {r.evidence_id: {"date": str(r.available_at.date()), "available_at": r.available_at.isoformat(),
                                "hash": r.evidence_hash}
                for r in self.records if r.available_at <= decision_at}


def load_pit_evidence(path: Path, *, source_root: Path) -> PITEvidenceBook:
    """Verify an external extraction and both original official byte streams.

    Constituents are an explicit extraction, not a market-data download.
    Classification rows must be present with their own PIT availability; an
    unclassified security remains unmapped and cannot prove B40 dominance.
    """
    try:
        body = path.read_bytes()
        doc = json.loads(body)
        if doc.get("schema_version") != "1.0.0" or doc.get("identity") != IDENTITY or not isinstance(doc.get("records"), list):
            raise GateError("PIT_EVIDENCE_SCHEMA_BLOCKER")
        result, keys = [], set()
        taxonomy = default_taxonomy()
        for raw in doc["records"]:
            if not isinstance(raw, dict):
                raise GateError("PIT_EVIDENCE_SCHEMA_BLOCKER")
            key = (raw.get("industry_code"), raw.get("etf_code"), raw.get("benchmark_code"), raw.get("available_at"))
            if key in keys or not all(isinstance(x, str) and x for x in key):
                raise GateError("PIT_EVIDENCE_SCHEMA_BLOCKER")
            keys.add(key)
            taxonomy.assert_level(raw["industry_code"])
            if (not isinstance(raw.get("etf_name"), str) or not raw["etf_name"]
                    or raw.get("weight_source_type") != OFFICIAL_WEIGHT):
                raise GateError("PIT_EVIDENCE_SCHEMA_BLOCKER")
            published = observed_time(raw["source_publication_at"])
            observed = observed_time(raw["evidence_observed_at"])
            available = observed_time(raw["available_at"])
            constituent_date = date.fromisoformat(raw["constituent_effective_date"])
            weight_date = date.fromisoformat(raw["weight_effective_date"])
            valid_through = date.fromisoformat(raw["valid_through"])
            if (not published <= observed <= available or max(constituent_date, weight_date) > available.date()
                    or valid_through < weight_date):
                raise GateError("PIT_EVIDENCE_TIME_BLOCKER")
            # Original official bytes are pinned independently from the extraction.
            weight_body = _source(source_root, raw, "weight_source")
            classification_body = _source(source_root, raw, "classification_source")
            extracted = raw.get("constituents")
            classes = raw.get("classifications")
            # The adapter accepts only official JSON exports whose rows can be
            # compared byte-for-byte after JSON decoding; PDF/XLS extraction
            # requires separate audited tooling and is never self-certified.
            if (not isinstance(extracted, list) or not isinstance(classes, list)
                    or json.loads(weight_body).get("constituents") != extracted
                    or json.loads(classification_body).get("classifications") != classes):
                raise GateError("PIT_EVIDENCE_SCHEMA_BLOCKER")
            stock_to_l2 = {}
            for cls in classes:
                taxonomy.assert_level(cls["l2_code"])
                if (not isinstance(cls["security_code"], str) or not cls["security_code"]
                        or observed_time(cls["available_at"]) > available
                        or date.fromisoformat(cls["effective_date"]) > weight_date):
                    raise GateError("PIT_CLASSIFICATION_TIME_BLOCKER")
                if cls["security_code"] in stock_to_l2:
                    raise GateError("PIT_CLASSIFICATION_DUPLICATE_BLOCKER")
                stock_to_l2[cls["security_code"]] = cls["l2_code"]
            if type(raw.get("declared_constituent_count")) is not int or raw["declared_constituent_count"] <= 0:
                raise GateError("PIT_EVIDENCE_SCHEMA_BLOCKER")
            if (json.loads(weight_body).get("declared_constituent_count") != raw["declared_constituent_count"]
                    or len({row.get("security_code") for row in extracted}) != len(extracted)
                    or any(not isinstance(row.get("security_code"), str) or not row["security_code"] for row in extracted)
                    or any((w := parse_weight_pct(row.get("weight_pct"))) is None or w < 0 or w > 100
                           for row in extracted)):
                raise GateError("PIT_EVIDENCE_SCHEMA_BLOCKER")
            exposure = build_benchmark_exposure(benchmark_code=raw["benchmark_code"], benchmark_name=None,
                constituents=extracted, stock_to_l2=stock_to_l2,
                weight_source_type=raw["weight_source_type"], constituent_date=str(constituent_date),
                constituent_count_declared=raw["declared_constituent_count"],
                index_provider=raw.get("weight_source_provider"), weight_source_url=raw["weight_source_url"],
                evidence_observed_at=observed.isoformat())
            # Incomplete extraction is retained as evidence but never admitted.
            result.append(PITRecord(raw["industry_code"], raw["etf_code"], raw["etf_name"],
                raw["benchmark_code"], available, published, observed, constituent_date, weight_date, valid_through,
                exposure, digest(json_bytes(key)), digest(json_bytes(raw))))
        return PITEvidenceBook(tuple(result), digest(body))
    except GateError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        raise GateError("PIT_EVIDENCE_SCHEMA_BLOCKER") from error


def select_pit_mappings(registry, rankings, provider, book: PITEvidenceBook, *, signal_at: datetime):
    """Rank first; admit each original Top5 slot using only evidence known by T."""
    if book is None or not isinstance(book, PITEvidenceBook):
        raise GateError("EXPLICIT_PIT_EVIDENCE_REQUIRED")
    day = signal_at.astimezone(provider.created_at.tzinfo).date()
    if day != provider.cutoff or day not in provider.sessions or len(rankings) < 5:
        raise GateError("PIT_MAPPING_CALENDAR_BLOCKER")
    window, execution_day = liquidity_window(provider, day)
    if window is None or execution_day is None:
        raise GateError("PIT_MAPPING_CALENDAR_BLOCKER")
    pools, provenance, diagnostics = {}, {}, []
    for rank in rankings[:5]:
        code = rank.industry_code
        candidates = []
        strict_rows = [row for row in registry.entries if row["industry_code"] == code
                       and active(row, day, signal_at) and active(row, execution_day, signal_at)]
        for row in strict_rows:
            liq = assess_liquidity(provider, row["etf_code"], window)
            candidate = IndustryCandidate(code, row["industry_name"], rank.score, row["etf_code"],
                row["tracking_index_code"], "STRICT_MAPPING", 100., 0., 100., True,
                "COMPLETE_WEIGHT_SET", liq.status, liq.mean_amount_cny)
            candidates.append(candidate)
            provenance[(code, row["etf_code"])] = {"evidence_id": row["source_sha256"],
                "evidence_hash": row["source_sha256"], "evidence_available_at": row["available_at"].isoformat(),
                "benchmark_date": str(row["effective_from"]), "source_publication_at": row["source_retrieved_at"].isoformat(),
                "evidence_observed_at": row["evidence_observed_at"].isoformat(), "etf_name": row["etf_name"]}
        if not strict_rows:
            current_records = {}
            for record in book.records:
                if (record.industry_code != code or record.available_at > signal_at
                        or record.weight_effective_date > day or record.valid_through < execution_day):
                    continue
                key = (record.etf_code, record.benchmark_code)
                previous = current_records.get(key)
                if previous is None or (record.weight_effective_date, record.available_at) > (
                        previous.weight_effective_date, previous.available_at):
                    current_records[key] = record
            for record in current_records.values():
                purity = record.exposure.purity(code)
                liq = assess_liquidity(provider, record.etf_code, window)
                quality = record.exposure.weight_quality if record.exposure.unmapped_weight == 0 else "INCOMPLETE_WEIGHT_SET"
                candidate = IndustryCandidate(code, default_taxonomy().name_of(code), rank.score, record.etf_code, record.benchmark_code,
                    "PROXY_EXPOSURE", purity.target_l2_exposure, purity.second_largest_l2_exposure,
                    purity.dominance_margin, purity.target_is_largest_l2, quality, liq.status, liq.mean_amount_cny)
                candidates.append(candidate)
                provenance[(code, record.etf_code)] = {"evidence_id": record.evidence_id,
                    "evidence_hash": record.evidence_hash, "evidence_available_at": record.available_at.isoformat(),
                    "benchmark_date": str(record.weight_effective_date), "constituent_effective_date": str(record.constituent_effective_date),
                    "source_publication_at": record.source_publication_at.isoformat(),
                    "evidence_observed_at": record.evidence_observed_at.isoformat(), "etf_name": record.etf_name}
        pools[code] = candidates
        diagnostics.extend({"industry_code": code, "etf_code": c.etf_code, "mapping_type": c.mapping_type,
            "admitted": c.passes_b40, "reason": c.b40_rejection_reason(),
            "liquidity_status": c.liquidity_status} for c in candidates)
    selected = select_mappings_partial([(r.industry_code, r.score) for r in rankings[:5]], pools,
                                       execution_policy=POLICY_B40_WITH_CASH)
    entries = []
    for rank, candidate in zip(rankings[:5], selected):
        evidence = provenance.get((candidate.l2_code, candidate.etf_code), {})
        entries.append({"industry_code": candidate.l2_code, "industry_name": candidate.l2_name,
            "industry_rank": rank.rank, "score": rank.score, "mapping_type": candidate.mapping_type,
            "etf_code": candidate.etf_code, "etf_name": evidence.get("etf_name"),
            "tracking_index_code": candidate.benchmark_code, "target_l2_exposure": candidate.target_l2_exposure,
            "target_is_largest_l2": candidate.target_is_largest_l2,
            "liquidity_status": candidate.liquidity_status, "mean_amount_cny": candidate.mean_amount_cny,
            "liquidity_window": [str(d) for d in window],
            "execution_reason": "B40_ADMITTED" if candidate.etf_code else "NO_ORDER_UNEXECUTABLE_SIGNAL", **evidence})
    return {"status": "READY", "selected": [entry for entry in entries if entry["etf_code"]],
        "slots": entries, "diagnostics": diagnostics, "reason": None, "industry_level": ETF_QUANT_INDUSTRY_LEVEL_V1,
        "liquidity_sessions": LIQUIDITY_SESSIONS, "liquidity_window": [str(d) for d in window],
        "taxonomy_identity": registry.taxonomy_identity, "execution_date": execution_day,
        "evidence_book_hash": book.sha256}
