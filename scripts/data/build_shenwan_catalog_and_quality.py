"""生成申万行业目录 canonical CSV + OHLCVA manifest + 数据质量报告。

只读 raw，只写 processed 与 manifest。不修改任何 raw 文件。
"""

from __future__ import annotations

import csv
import glob
import hashlib
import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

RAW = Path("/workspace/data/raw/shenwan")
PROC = Path("/workspace/data/processed/shenwan")
CATALOG_DIR = RAW / "sector_catalog"
HIST_DIR = RAW / "sector_history"

CATALOG_URL = (
    "https://www.swsresearch.com/institute-sw/api/index_publish/current/"
    "?page={page}&page_size=50&indextype={indextype}"
)
HIST_URL = (
    "https://www.swsresearch.com/institute-sw/api/index_publish/trend/"
    "?swindexcode={code}&period=DAY"
)
RETRIEVED_AT = "2026-09-20T19:16:00+08:00"
INDEXTYPE_L1 = "一级行业"
INDEXTYPE_L2 = "二级行业"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def main() -> int:
    PROC.mkdir(parents=True, exist_ok=True)

    l1 = load_jsonl(CATALOG_DIR / "sws_index_catalog_L1.jsonl")
    l2 = load_jsonl(CATALOG_DIR / "sws_index_catalog_L2.jsonl")

    # ---------- Task A: canonical sector catalog ----------
    cat_path = PROC / "sws_index_sector_catalog.csv"
    with cat_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "sector_code",
                "sector_name",
                "level",
                "classification",
                "source_url",
                "retrieved_at",
                "catalog_sha256",
            ]
        )
        for rec in l2:
            w.writerow(
                [
                    rec["swindexcode"],
                    rec["swindexname"],
                    2,
                    "SW2021_INDEX",
                    CATALOG_URL.format(page="1..3", indextype=INDEXTYPE_L2),
                    RETRIEVED_AT,
                    sha256_file(CATALOG_DIR / "sws_index_catalog_L2.jsonl"),
                ]
            )
        for rec in l1:
            w.writerow(
                [
                    rec["swindexcode"],
                    rec["swindexname"],
                    1,
                    "SW2021_INDEX",
                    CATALOG_URL.format(page="1", indextype=INDEXTYPE_L1),
                    RETRIEVED_AT,
                    sha256_file(CATALOG_DIR / "sws_index_catalog_L1.jsonl"),
                ]
            )
    print(f"catalog CSV: {cat_path} rows={len(l2) + len(l1)} (L2={len(l2)} L1={len(l1)})")

    # ---------- Task B: history manifest + quality ----------
    hist_files = sorted(glob.glob(str(HIST_DIR / "*.json")))
    if len(hist_files) != len(l2):
        raise SystemExit(
            f"history file count {len(hist_files)} != catalog L2 count {len(l2)}"
        )

    name_by_code = {r["swindexcode"]: r["swindexname"] for r in l2}
    manifest: list[dict] = []
    total_rows = 0
    all_rows: list[dict] = []
    per_sector: list[dict] = []

    for f in hist_files:
        p = Path(f)
        code = p.stem
        payload = json.loads(p.read_text(encoding="utf-8"))
        rows = payload.get("data") or []
        if not rows:
            raise SystemExit(f"empty OHLCVA for {code}")
        dates = [r["bargaindate"] for r in rows]
        for r in rows:
            all_rows.append(
                {
                    "sector_code": code,
                    "sector_name": name_by_code.get(code),
                    **r,
                }
            )
        total_rows += len(rows)
        manifest.append(
            {
                "sector_code": code,
                "sector_name": name_by_code.get(code),
                "source_url": HIST_URL.format(code=code),
                "retrieved_at": RETRIEVED_AT,
                "sha256": sha256_file(p),
                "row_count": len(rows),
                "start_date": min(dates),
                "end_date": max(dates),
                "raw_path": f"data/raw/shenwan/sector_history/{code}.json",
                "bytes": p.stat().st_size,
            }
        )
        per_sector.append(
            {
                "sector_code": code,
                "sector_name": name_by_code.get(code),
                "row_count": len(rows),
                "start_date": min(dates),
                "end_date": max(dates),
                "duplicate_dates": len(dates) - len(set(dates)),
            }
        )

    # manifest 不是原始数据，写入 data/manifests/，避免污染 raw 目录的
    # "未登记文件" 校验（raw 目录只允许存放官方原文件）。
    man_dir = RAW.parent.parent / "manifests"
    man_dir.mkdir(parents=True, exist_ok=True)
    man_path = man_dir / "shenwan_sector_history_manifest.json"
    man_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "provider": "shenwan_research_official",
                "endpoint": HIST_URL.format(code="{sector_code}"),
                "period": "DAY",
                "retrieved_at": RETRIEVED_AT,
                "sector_count": len(manifest),
                "total_rows": total_rows,
                "files": manifest,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"history manifest: {man_path} sectors={len(manifest)} rows={total_rows}")

    # ---------- Task B quality report ----------
    import pandas as pd

    df = pd.DataFrame(all_rows)
    df["bargaindate"] = pd.to_datetime(df["bargaindate"], errors="raise")

    dup = int(df.duplicated(subset=["sector_code", "bargaindate"]).sum())
    bad_hi = int((df["maxindex"] < df[["openindex", "closeindex", "minindex"]].max(axis=1)).sum())
    bad_lo = int((df["minindex"] > df[["openindex", "closeindex", "maxindex"]].min(axis=1)).sum())
    nonpos = int((df[["openindex", "maxindex", "minindex", "closeindex"]] <= 0).sum().sum())
    neg_amt = int((df["bargainamount"] < 0).sum())
    neg_sum = int((df["bargainsum"] < 0).sum())
    null_amt = int(df["bargainamount"].isna().sum())
    null_sum = int(df["bargainsum"].isna().sum())

    invalid_rows = df[
        (df["maxindex"] < df[["openindex", "closeindex", "minindex"]].max(axis=1))
        | (df["minindex"] > df[["openindex", "closeindex", "maxindex"]].min(axis=1))
    ]

    per = pd.DataFrame(per_sector).sort_values("sector_code")
    ps = per.reset_index(drop=True)

    q = {
        "sector_count": len(manifest),
        "total_rows": total_rows,
        "earliest_date": str(df["bargaindate"].min().date()),
        "latest_date": str(df["bargaindate"].max().date()),
        "earliest_common_date": str(ps["start_date"].max()),
        "latest_common_date": str(ps["end_date"].min()),
        "duplicate_sector_date_rows": dup,
        "invalid_ohlc_high_lt_oc_l": bad_hi,
        "invalid_ohlc_low_gt_oc_h": bad_lo,
        "non_positive_index_values": nonpos,
        "negative_bargainamount": neg_amt,
        "negative_bargainsum": neg_sum,
        "null_bargainamount": null_amt,
        "null_bargainsum": null_sum,
        "shortest_history_rows": int(ps["row_count"].min()),
        "longest_history_rows": int(ps["row_count"].max()),
        "shortest_history_sector": ps.loc[ps["row_count"].idxmin(), "sector_code"],
        "longest_history_sector": ps.loc[ps["row_count"].idxmax(), "sector_code"],
    }

    dup_total = int(ps["duplicate_dates"].sum())
    q["duplicate_dates_total"] = dup_total

    # 每个行业相对二级行业公共交易日历的覆盖率
    common = sorted(
        set.intersection(*[set(g["bargaindate"]) for _, g in df.groupby("sector_code")])
    )
    cov = (
        df.groupby("sector_code")["bargaindate"]
        .apply(lambda s: len(set(s) & set(common)) / len(common))
        .to_dict()
    )

    report = {
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "raw_dir": str(HIST_DIR),
        "quality": q,
        "per_sector": per_sector,
        "common_trading_days": len(common),
        "common_trading_day_range": [str(common[0].date()), str(common[-1].date())],
        "coverage_min": round(min(cov.values()), 6),
        "coverage_max": round(max(cov.values()), 6),
        "invalid_ohlc_rows": [
            {
                "sector_code": r["sector_code"],
                "sector_name": r["sector_name"],
                "bargaindate": str(r["bargaindate"].date()),
                "openindex": r["openindex"],
                "maxindex": r["maxindex"],
                "minindex": r["minindex"],
                "closeindex": r["closeindex"],
            }
            for _, r in invalid_rows.iterrows()
        ],
    }
    rep_path = PROC / "shenwan_l2_ohlcva_quality_report.json"
    rep_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"quality report: {rep_path}")
    print(json.dumps(q, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
