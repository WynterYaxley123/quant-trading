"""Resumable primary-source ETF discovery and complete-weight exposure evidence.

Only mapping disclosures use this fetcher. Bars and liquidity use CNEquity.
Raw disclosures and constituent rows stay in the external research directory.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

import pandas as pd
import requests

from strategies.etf_quant.domain.industry_level import load_taxonomy

from .coverage import digest, external_directory, immutable_bytes, json_bytes
from .protocol import canonical_hash

HOSTS = {"query.sse.com.cn", "www.szse.cn", "oss-ch.csindex.com.cn", "www.cnindex.com.cn"}


def fetch(url: str, output: Path, observed_day: str) -> tuple[bytes, dict[str, Any]]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS:
        raise ValueError("OFFICIAL_MAPPING_ORIGIN_REQUIRED")
    key = canonical_hash({"url": url, "observed_day": observed_day})
    directory = output / "fetch" / key
    directory.mkdir(parents=True, exist_ok=True)
    body, receipt = directory / "body.bin", directory / "receipt.json"
    if receipt.exists():
        meta = json.loads(receipt.read_bytes())
        if digest(body) != meta["sha256"]:
            raise ValueError("DISCLOSURE_CACHE_HASH_ERROR")
        return body.read_bytes(), meta
    last: Exception | None = None
    for attempt in range(2):
        try:
            response = requests.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://" + str(parsed.hostname) + "/",
                },
                timeout=10,
                stream=True,
            )
            if response.status_code in (400, 403, 404):
                raise ValueError("OFFICIAL_DISCLOSURE_UNAVAILABLE:" + str(response.status_code))
            response.raise_for_status()
            if urlsplit(response.url).hostname not in HOSTS:
                raise ValueError("OFFICIAL_MAPPING_REDIRECT_DENIED")
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 32 * 1024 * 1024:
                    raise ValueError("DISCLOSURE_SIZE_LIMIT")
                chunks.append(chunk)
            value = b"".join(chunks)
            meta = {
                "url": url,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "sha256": hashlib.sha256(value).hexdigest(),
                "bytes": size,
            }
            immutable_bytes(body, value)
            immutable_bytes(receipt, json_bytes(meta))
            return value, meta
        except ValueError:
            raise
        except requests.RequestException as error:
            last = error
            time.sleep(0.5 * (attempt + 1))
    raise ValueError("OFFICIAL_DISCLOSURE_UNAVAILABLE") from last


def catalogue(output: Path, observed_day: str) -> list[dict[str, Any]]:
    url = "https://query.sse.com.cn/commonSoaQuery.do?" + urlencode(
        {
            "sqlId": "FUND_LIST",
            "isPagination": "true",
            "pageHelp.pageSize": 2000,
            "pageHelp.pageNo": 1,
        }
    )
    body, receipt = fetch(url, output, observed_day)
    doc = json.loads(body)
    rows = doc.get("result") or doc["pageHelp"]["data"]
    if len(rows) != doc["pageHelp"]["total"]:
        raise ValueError("INCOMPLETE_EXCHANGE_CATALOGUE")
    result = []
    for row in rows:
        if row["subClass"] != "03" or not row.get("INDEX_CODE"):
            continue
        result.append(
            {
                "etf_code": row["fundCode"] + ".SH",
                "name": row["fundAbbr"],
                "tracking_index": str(row["INDEX_CODE"]).strip(),
                "index_name": row["INDEX_NAME"],
                "listing_date": row["listingDate"],
                "fund_manager": row["companyName"],
                "source": receipt,
            }
        )
    url = "https://www.szse.cn/api/report/ShowReport?SHOWTYPE=xlsx&CATALOGID=1945&TABKEY=tab1"
    body, receipt = fetch(url, output, observed_day)
    frame = pd.read_excel(io.BytesIO(body), dtype=str).fillna("")
    # Exact named official fields. A schema change fails rather than guessing.
    required = {"证券代码", "证券简称", "拟合指数"}
    if not required.issubset(frame.columns):
        raise ValueError("SZSE_CATALOGUE_SCHEMA_CHANGED:" + str(list(frame.columns)))
    for row in frame.to_dict("records"):
        tokens = str(row["拟合指数"]).strip().split()
        if not tokens:
            continue
        index = tokens[0]
        if not re.fullmatch(r"[A-Z0-9]{6}", index):
            continue
        result.append(
            {
                "etf_code": str(row["证券代码"]).zfill(6) + ".SZ",
                "name": row["证券简称"],
                "tracking_index": index,
                "index_name": "",
                "listing_date": "",
                "fund_manager": row.get("基金管理人", ""),
                "source": receipt,
            }
        )
    immutable_bytes(output / "catalogue.json", json_bytes(result))
    return result


def exposure(
    code: str, membership: dict[str, str], output: Path, observed_day: str
) -> dict[str, Any]:
    candidates = [
        "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/closeweight/"
        + code
        + "closeweight.xls",
        "https://www.cnindex.com.cn/sample-detail/download-history?"
        + urlencode({"indexcode": code, "dateStr": "2026-09-30"}),
    ]
    errors = []
    for url in candidates:
        try:
            body, source = fetch(url, output, observed_day)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                frame = pd.read_excel(io.BytesIO(body), dtype=str).fillna("")
            cni = "cnindex.com.cn" in url
            if cni:
                code_column, weight_column, date_column = "样本代码", "权重（%）", "日期"
            else:
                code_column, weight_column, date_column = (
                    "成份券代码Constituent Code",
                    "权重(%)weight",
                    "日期Date",
                )
                if "指数代码 Index Code" not in frame or set(
                    frame["指数代码 Index Code"].str.zfill(6)
                ) != {code}:
                    raise ValueError("WRONG_INDEX_DISCLOSURE")
            if not {code_column, weight_column, date_column}.issubset(frame.columns) or frame.empty:
                raise ValueError("WEIGHT_DISCLOSURE_SCHEMA_OR_EMPTY")
            dates = set(frame[date_column])
            if len(dates) != 1:
                raise ValueError("MIXED_WEIGHT_DATES")
            date_value = next(iter(dates))
            effective = (
                pd.Timestamp(
                    date_value if "-" in date_value else datetime.strptime(date_value, "%Y%m%d")
                )
                .date()
                .isoformat()
            )
            weights: dict[str, float] = {}
            unknown, total = 0.0, 0.0
            seen = set()
            member_groups = set()
            for row in frame.to_dict("records"):
                security = str(row[code_column]).strip()
                if not cni:
                    security = security.zfill(6)
                exchange = str(row.get("交易所Exchange", ""))
                identity = (security, exchange)
                if identity in seen:
                    raise ValueError("DUPLICATE_CONSTITUENT")
                seen.add(identity)
                weight = float(row[weight_column])
                if not 0 <= weight <= 100:
                    raise ValueError("INVALID_WEIGHT")
                total += weight
                industry = (
                    membership.get(security)
                    if len(security) == 6
                    and (cni or exchange in ("上海证券交易所", "深圳证券交易所", "北京证券交易所"))
                    else None
                )
                member_groups.add(industry)
                if industry is None:
                    unknown += weight
                else:
                    weights[industry] = weights.get(industry, 0.0) + weight
            complete = abs(total - 100) <= 0.5
            ranked = sorted(weights, key=lambda key: (-weights[key], key))
            largest = ranked[0] if ranked else None
            second = weights[ranked[1]] if len(ranked) > 1 else 0.0
            result = {
                "index_code": code,
                "effective_date": effective,
                "source": source,
                "constituent_count": len(seen),
                "total_weight": total,
                "complete": complete,
                "unknown_weight": unknown,
                "industry_weights": weights,
                "largest_industry": largest,
                "largest_weight": weights.get(largest or "", 0),
                "second_weight": second,
                "dominance_proven_with_unknown_mass": largest is not None
                and weights[largest] >= second + unknown,
                "direct_containment": complete
                and unknown == 0
                and len(member_groups) == 1
                and None not in member_groups,
                "method": "FULL_OFFICIAL_WEIGHT_WORKBOOK;EXACT_SW2021_L3_TO_L2;NO_RENORMALIZATION",
            }
            key = canonical_hash(
                {
                    "source": source["sha256"],
                    "effective_date": effective,
                    "observed_day": observed_day,
                    "membership": canonical_hash(membership),
                    "parser": digest(Path(__file__)),
                }
            )
            (output / "parsed").mkdir(exist_ok=True)
            immutable_bytes(output / "parsed" / (key + ".json"), json_bytes(result))
            return result
        except (ValueError, KeyError, ImportError) as error:
            errors.append(type(error).__name__ + ":" + str(error)[:180])
    return {"index_code": code, "complete": False, "errors": errors}


def collect(prior: Path, output: Path, panel: Path) -> dict[str, Any]:
    observed_day = datetime.now(timezone.utc).date().isoformat()
    instruments = catalogue(output, observed_day)
    original = json.loads(
        (prior / "proxy-exposure-v1/official-sources/stock_to_l2_v1.json").read_bytes()
    )
    taxonomy = load_taxonomy().level3_to_level2
    membership = {
        symbol.split(".")[0]: taxonomy[code]
        for symbol, code in original["members"].items()
        if code in taxonomy
    }
    indices = sorted(
        {
            r["tracking_index"]
            for r in instruments
            if re.fullmatch(r"[A-Z0-9]{6}", r["tracking_index"])
        }
    )

    def get(code: str) -> dict[str, Any]:
        path = output / "indices" / (code + ".json")
        if path.exists():
            return json.loads(path.read_bytes())
        value = exposure(code, membership, output, observed_day)
        immutable_bytes(path, json_bytes(value))
        return value

    (output / "indices").mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(get, indices))
    by_index = {r["index_code"]: r for r in results}
    universe = json.loads((panel / "panel.json").read_bytes())["industries"]
    discovered = []
    for item in instruments:
        evidence = by_index.get(item["tracking_index"], {})
        if (
            evidence.get("complete")
            and evidence.get("dominance_proven_with_unknown_mass")
            and evidence.get("largest_weight", 0) >= 30
            and evidence.get("largest_industry") in universe
        ):
            discovered.append(item | {"evidence": evidence})
    report = {
        "observed_day": observed_day,
        "exchange_catalogue_etfs": len(instruments),
        "indices_attempted": len(indices),
        "complete_weight_indices": sum(r.get("complete", False) for r in results),
        "membership_source_sha256": digest(
            prior / "proxy-exposure-v1/official-sources/stock_to_l2_v1.json"
        ),
        "membership_as_of": original["reference_date"],
        "universe": universe,
        "candidates": discovered,
    }
    immutable_bytes(output / "discovery.json", json_bytes(report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--panel", type=Path, required=True)
    args = parser.parse_args()
    result = collect(
        external_directory(args.prior),
        external_directory(args.output),
        external_directory(args.panel),
    )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in ("universe", "candidates")}
            | {"candidates": len(result["candidates"])}
        )
    )


if __name__ == "__main__":
    main()
