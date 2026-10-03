"""Production PIT evidence registry builder for ETF-Quant V1.

Runs entirely outside the Git work tree. Reads already-captured official raw bytes,
produces immutable evidence packages, derives benchmark L2 exposure, applies the
frozen B40 rule, emits the evidence book the existing runtime adapter consumes, and
writes a small metadata registry that *is* safe to commit.

It never contacts the network: collection is a separate, auditable step, and a
build that silently re-fetched would destroy reproducibility.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


# Explicit external roots support other machines; existing deployment defaults
# remain compatible. This builder is not part of the portable demo/test flow.
RUNTIME = Path(
    os.environ.get(
        "ETF_QUANT_PIT_ROOT", r"D:\QuantForge\runtime\etf-quant-v1\production-pit-evidence-v1"
    )
)
PRIOR = Path(
    os.environ.get("ETF_QUANT_PROXY_ROOT", r"D:\QuantForge\runtime\etf-quant-v1\proxy-exposure-v1")
)
SUBAGENTS = RUNTIME / "subagents"
BUILD = RUNTIME / "build"
RAW = RUNTIME / "raw"
PACKAGES = RUNTIME / "packages"
SOURCE_ROOT = RUNTIME / "adapter-sources"
REPORTS = RUNTIME / "reports"

CSI_REVERSE = PRIOR / "official-sources" / "raw" / "csi_reverse"
SWS_RAW_L2 = RAW / "sws" / "raw_members"
SWS_CATALOG = RAW / "sws" / "catalog"
SWS_FULL_CATALOG = RAW / "sws" / "raw_catalog" / "sws_index_name_all.json"

#: The provider endpoint that actually produced the benchmark weight evidence.
#: The first build recorded a sibling path that answers `code=500` when called
#: without the reverse-lookup body; an independent audit re-fetched it and caught
#: the mistake. This is the endpoint the collector really used.
CSI_WEIGHT_ENDPOINT = "https://www.csindex.com.cn/csindex-home/indexInfo/index-sample-information"
CSI_WEIGHT_METHOD = "POST {searchInput:<security>,pageNum,pageSize,sortField,sortOrder}"

#: SWS industry-index membership endpoint, verbatim capture.
SWS_MEMBERSHIP_ENDPOINT = (
    "https://www.swsresearch.com/institute-sw/api/index_publish/details/component_stocks/"
)
SWS_CATALOG_ENDPOINT = "https://www.swsresearch.com/institute-sw/api/index_publish/current/"

WEIGHT_SUM_BAND = (99.0, 100.5)
TARGET_L2_CODES = ("3701", "3703", "3706", "4803", "4901")
