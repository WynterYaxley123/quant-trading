"""Explicit public-document retrieval; hashes only, no dataset or payload retention."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from .contracts import instant, require, sha

MAX_DOCUMENT_BYTES = 6 * 1024 * 1024


@dataclass(frozen=True)
class DocumentTarget:
    document_id: str
    url: str
    publisher: str
    media: str = "text/html"
    method: str = "GET"


# Reviewed document endpoints only. Never expand this to a host-wide data downloader.
TARGETS = (
    DocumentTarget(
        "sws-2021-classification",
        "https://wxweb.swsresearch.com/swsreport/2021_08/328340.pdf",
        "SWS Research",
        "application/pdf",
    ),
    DocumentTarget(
        "sws-announcements",
        "https://www.swsresearch.com/institute_sw/allIndex/announcementIndex",
        "SWS Research",
    ),
    DocumentTarget("tdx-terms", "https://www.tdx.com.cn/about/yhxy/index.html?tabindex=0", "TDX"),
    DocumentTarget("sina-copyright", "https://corp.sina.com.cn/chn/copyright.html", "Sina"),
    DocumentTarget("sina-finance-terms", "https://finance.sina.cn/app/SFAuser.shtml", "Sina"),
    DocumentTarget("baostock-home", "https://www.baostock.com/", "BaoStock"),
    DocumentTarget(
        "baostock-adjustment",
        "https://www.baostock.com/helpdocs/pdf/BaoStock%E5%A4%8D%E6%9D%83%E5%9B%A0%E5%AD%90%E7%AE%80%E4%BB%8B.pdf",
        "BaoStock",
        "application/pdf",
    ),
    DocumentTarget("sse-legal", "https://www.sse.com.cn/home/legal/", "Shanghai Stock Exchange"),
    DocumentTarget(
        "sse-delisting-example",
        "https://www.sse.com.cn/disclosure/announcement/listing/stock/c/c_20260629_10823832.shtml",
        "Shanghai Stock Exchange",
    ),
    DocumentTarget(
        "sse-calendar",
        "https://www.sse.com.cn/disclosure/dealinstruc/closed/",
        "Shanghai Stock Exchange",
    ),
    DocumentTarget(
        "tdx-terms-text",
        "https://www.tdx.com.cn/about/yhxy/js/index.js?ver=20251224.1619",
        "TDX",
        "application/javascript",
    ),
    DocumentTarget("tdx-provider-license", "https://www.tdx.com.cn/article/license.html", "TDX"),
    DocumentTarget("tdx-data-product", "https://www.tdx.com.cn/tdxdata.html", "TDX"),
    DocumentTarget(
        "baostock-home-doc",
        "https://www.baostock.com/helpdocs/api/markdown/home.md",
        "BaoStock",
        "text/plain",
        "POST",
    ),
    DocumentTarget(
        "baostock-lifecycle-doc",
        "https://www.baostock.com/helpdocs/api/markdown/stockBasic.md",
        "BaoStock",
        "text/plain",
        "POST",
    ),
    DocumentTarget(
        "baostock-bars-doc",
        "https://www.baostock.com/helpdocs/api/markdown/stockKData.md",
        "BaoStock",
        "text/plain",
        "POST",
    ),
    DocumentTarget(
        "baostock-factor-doc",
        "https://www.baostock.com/helpdocs/api/markdown/factorInfo.md",
        "BaoStock",
        "text/plain",
        "POST",
    ),
    DocumentTarget(
        "baostock-revision-doc",
        "https://www.baostock.com/helpdocs/api/markdown/modifyRecord.md",
        "BaoStock",
        "text/plain",
        "POST",
    ),
    DocumentTarget(
        "baostock-industry-doc",
        "https://www.baostock.com/helpdocs/api/markdown/stockIndustry.md",
        "BaoStock",
        "text/plain",
        "POST",
    ),
)


def target(document_id: str) -> DocumentTarget:
    matches = [t for t in TARGETS if t.document_id == document_id]
    require(len(matches) == 1, "DOCUMENT_NOT_ALLOWLISTED")
    return matches[0]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        raise urllib.error.HTTPError(req.full_url, code, "REDIRECT_REJECTED", headers, fp)


def response_receipt(
    approved: DocumentTarget, *, final_url: str, media: str, raw: bytes, retrieved_at: str
) -> dict[str, Any]:
    """Pure transport validation. It does not verify dataset rights or claim truth."""
    require(approved == target(approved.document_id), "DOCUMENT_IDENTITY_INVALID")
    parts = urlsplit(final_url)
    require(
        parts.scheme == "https" and not parts.username and not parts.password,
        "DOCUMENT_URL_INVALID",
    )
    require(final_url == approved.url, "DOCUMENT_REDIRECT_REJECTED")
    require(media.split(";", 1)[0].strip().lower() == approved.media, "DOCUMENT_MEDIA_INVALID")
    require(0 < len(raw) <= MAX_DOCUMENT_BYTES, "DOCUMENT_SIZE_INVALID")
    if approved.media == "application/pdf":
        require(raw.startswith(b"%PDF-"), "DOCUMENT_PAYLOAD_INVALID")
        require(b"/JavaScript" not in raw and b"/Launch" not in raw, "DOCUMENT_ACTIVE_PAYLOAD")
    elif approved.media == "text/html":
        require(
            b"<html" in raw[:4096].lower() or b"<!doctype html" in raw[:4096].lower(),
            "DOCUMENT_PAYLOAD_INVALID",
        )
    else:
        require(not raw.startswith((b"PK", b"MZ", b"\x7fELF")), "DOCUMENT_PAYLOAD_INVALID")
    return {
        "document_id": approved.document_id,
        "source_url": approved.url,
        "final_url": final_url,
        "publisher": approved.publisher,
        "retrieved_at": retrieved_at,
        "content_sha256": sha(raw),
        "bytes": len(raw),
        "media_type": approved.media,
        "transport_status": "RETRIEVED_HASHED",
        "publisher_identity_basis": "REVIEWED_OFFICIAL_HTTPS_ENDPOINT",
        "original_retained": False,
        "claim_verification": "REVIEW_REQUIRED",
        "dataset_permission": "NOT_ESTABLISHED",
        "request_method": approved.method,
    }


def acquire(document_id: str) -> dict[str, Any]:
    """One credential-free request. No retry, redirect, JS, execution or disk payload."""
    approved = target(document_id)
    retrieved_at = datetime.now(UTC).isoformat()
    request = urllib.request.Request(
        approved.url,
        data=b"{}" if approved.method == "POST" else None,
        headers={
            "User-Agent": "quant-trading-source-qualification",
            "Accept": approved.media,
            "Content-Type": "application/json",
        },
        method=approved.method,
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
            require(response.status == 200, "DOCUMENT_HTTP_INVALID")
            raw = response.read(MAX_DOCUMENT_BYTES + 1)
            return response_receipt(
                approved,
                final_url=response.url,
                media=response.headers.get("Content-Type", ""),
                raw=raw,
                retrieved_at=retrieved_at,
            )
    except urllib.error.HTTPError as exc:
        return {
            "document_id": document_id,
            "source_url": approved.url,
            "publisher": approved.publisher,
            "retrieved_at": retrieved_at,
            "content_sha256": None,
            "transport_status": "REDIRECT_REJECTED"
            if 300 <= exc.code < 400
            else "HTTP_UNAVAILABLE",
            "http_status": exc.code,
            "original_retained": False,
            "claim_verification": "NOT_ESTABLISHED",
        }
    except (urllib.error.URLError, TimeoutError):
        return {
            "document_id": document_id,
            "source_url": approved.url,
            "publisher": approved.publisher,
            "retrieved_at": retrieved_at,
            "content_sha256": None,
            "transport_status": "TRANSPORT_UNAVAILABLE",
            "original_retained": False,
            "claim_verification": "NOT_ESTABLISHED",
        }


def verify_document(
    receipt: dict[str, Any], raw: bytes, *, document_id: str, markers: tuple[str, ...], now: str
) -> str:
    """Exact bytes/identity/scope check for reviewed claims, never a licence grant."""
    approved = target(document_id)
    require(
        receipt.get("document_id") == document_id
        and receipt.get("publisher") == approved.publisher
        and receipt.get("source_url") == approved.url,
        "DOCUMENT_IDENTITY_INVALID",
    )
    require(receipt.get("transport_status") == "RETRIEVED_HASHED", "DOCUMENT_NOT_RETRIEVED")
    response_receipt(
        approved,
        final_url=receipt.get("final_url", ""),
        media=receipt.get("media_type", ""),
        raw=raw,
        retrieved_at=receipt.get("retrieved_at", ""),
    )
    require(receipt.get("content_sha256") == sha(raw), "DOCUMENT_HASH_MISMATCH")
    age = (instant(now) - instant(receipt.get("retrieved_at", ""))).total_seconds()
    require(0 <= age <= 30 * 86400, "DOCUMENT_REVIEW_STALE")
    require(bool(markers), "DOCUMENT_CLAIM_REQUIRED")
    # Raw text/HTML only; PDF needs a separate reviewed extraction, never execution.
    require(approved.media != "application/pdf", "DOCUMENT_EXTRACTION_REQUIRED")
    encoding = "utf-8"
    declared = re.search(rb"charset\s*=\s*[\"']?([A-Za-z0-9_-]+)", raw[:8192], re.I)
    if declared and declared[1].lower() in {b"gb2312", b"gbk", b"gb18030"}:
        encoding = "gb18030"
    text = raw.decode(encoding, errors="replace")
    require(all(marker in text for marker in markers), "DOCUMENT_CLAIM_MISMATCH")
    return "REVIEWED_EXACT_BYTES_NOT_DATASET_AUTHORIZATION"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document_id", choices=[t.document_id for t in TARGETS])
    args = parser.parse_args()
    print(json.dumps(acquire(args.document_id), sort_keys=True))


if __name__ == "__main__":
    main()
