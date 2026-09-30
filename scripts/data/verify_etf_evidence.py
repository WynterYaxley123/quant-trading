#!/usr/bin/env python3
"""Offline integrity check for the ETF official-evidence chain.

Verifies that the three layers agree:
    disk PDF  <->  data/raw/etf_evidence/documents_manifest.json  <->  evidence_catalog.csv

No network.  Read-only.  Exit code 0 = all checks pass, 1 = failure.

Usage:
    python scripts/data/verify_etf_evidence.py [--repo-root PATH]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_etf_evidence(repo_root: str | os.PathLike = ".") -> dict:
    root = Path(repo_root)
    docs_dir = root / "data" / "raw" / "etf_evidence" / "documents"
    man_path = root / "data" / "raw" / "etf_evidence" / "documents_manifest.json"
    cat_path = root / "data" / "processed" / "shenwan_etf_mapping" / "evidence_catalog.csv"

    problems: list[str] = []
    report: dict = {"checks": {}, "problems": problems}

    # 1. manifest file exists
    if not man_path.is_file():
        problems.append(f"CHECK1 manifest missing: {man_path}")
        return report
    report["checks"]["1_manifest_exists"] = True
    manifest = json.loads(man_path.read_text(encoding="utf-8"))

    # flatten registered files (primary + extra_docs)
    registered: dict[str, dict] = {}
    duplicates: list[str] = []
    for code, rec in manifest.items():
        entries = ([dict(rec, _role="primary")] if rec.get("document") else []) + \
                  [dict(e, _role="extra") for e in rec.get("extra_docs", [])]
        for e in entries:
            fn = e.get("document")
            if not fn:
                problems.append(f"CHECK2 entry without filename under {code}")
                continue
            if fn in registered:
                duplicates.append(fn)
                problems.append(f"CHECK10 duplicate manifest entry: {fn} "
                                f"({registered[fn]['_code']} and {code})")
            registered[fn] = dict(e, _code=code)
    report["checks"]["2_manifest_filename_unique"] = not duplicates
    report["checks"]["10_duplicate_manifest_entries"] = not duplicates
    report["duplicate_manifest_entries"] = duplicates

    # disk inventory
    disk = {}
    if docs_dir.is_dir():
        for p in sorted(docs_dir.iterdir()):
            if p.is_file():
                disk[p.name] = {"size": p.stat().st_size, "sha256": _sha256(p)}
    report["disk_pdf_count"] = len(disk)
    report["manifest_file_count"] = len(registered)

    # 3/4/5. per-registered-file checks
    missing, sha_bad, size_bad = [], [], []
    for fn, e in registered.items():
        p = docs_dir / fn
        if not p.is_file():
            missing.append(fn)
            problems.append(f"CHECK3 registered but not on disk: {fn}")
            continue
        if disk[fn]["sha256"] != e.get("sha256"):
            sha_bad.append(fn)
            problems.append(f"CHECK4 sha256 mismatch: {fn} "
                            f"manifest={str(e.get('sha256'))[:16]} disk={disk[fn]['sha256'][:16]}")
        if int(disk[fn]["size"]) != int(e.get("bytes", -1)):
            size_bad.append(fn)
            problems.append(f"CHECK5 size mismatch: {fn} manifest={e.get('bytes')} disk={disk[fn]['size']}")
    report["checks"]["3_disk_file_exists"] = not missing
    report["checks"]["4_sha256_match"] = not sha_bad
    report["checks"]["5_size_match"] = not size_bad
    report["missing_on_disk"] = missing
    report["sha_mismatch"] = sha_bad
    report["size_mismatch"] = size_bad

    # orphan PDFs: on disk, in no manifest entry
    orphans = sorted(f for f in disk if f not in registered)
    report["orphan_pdfs"] = orphans
    report["orphan_pdf_count"] = len(orphans)

    # 6/7/8/9. catalog checks
    cat_missing, cat_sha_bad, cat_url_bad, cat_orphan = [], [], [], []
    rows = []
    if cat_path.is_file():
        rows = list(csv.DictReader(cat_path.open(encoding="utf-8", newline="")))
    report["catalog_row_count"] = len(rows)
    for r in rows:
        code, sd = r.get("etf_code", ""), r.get("source_document", "")
        if not sd or not (docs_dir / sd).is_file():
            cat_missing.append(code)
            problems.append(f"CHECK6 catalog source_document missing on disk: {code} -> {sd!r}")
            continue
        if r.get("source_sha256") != disk[sd]["sha256"]:
            cat_sha_bad.append(code)
            problems.append(f"CHECK7 catalog source_sha256 mismatch: {code} -> {sd}")
        e = registered.get(sd)
        if e is None:
            cat_orphan.append(code)
            problems.append(f"CHECK9 catalog references unregistered PDF: {code} -> {sd}")
        elif (e.get("source_url") or "") != (r.get("source_url") or ""):
            cat_url_bad.append(code)
            problems.append(f"CHECK8 catalog source_url disagrees with manifest: {code} -> {sd}")
        if e is not None and e["_code"] != code:
            problems.append(f"catalog {code} references a document registered to {e['_code']}: {sd}")
    report["checks"]["6_catalog_source_document_exists"] = not cat_missing
    report["checks"]["7_catalog_source_sha256_match"] = not cat_sha_bad
    report["checks"]["8_catalog_source_url_agrees"] = not cat_url_bad
    report["checks"]["9_no_catalog_orphan_reference"] = not cat_orphan
    report["catalog_missing_source_document"] = cat_missing
    report["catalog_sha_mismatch"] = cat_sha_bad
    report["catalog_url_mismatch"] = cat_url_bad
    report["catalog_orphan_reference"] = cat_orphan

    report["integrity_pass"] = not problems
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = ap.parse_args()
    rep = verify_etf_evidence(args.repo_root)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        print("ETF EVIDENCE INTEGRITY CHECK")
        print(f"  repo_root              : {args.repo_root}")
        print(f"  disk PDF count         : {rep.get('disk_pdf_count')}")
        print(f"  manifest file count    : {rep.get('manifest_file_count')}")
        print(f"  catalog rows           : {rep.get('catalog_row_count')}")
        print(f"  orphan PDF count       : {rep.get('orphan_pdf_count')}")
        for k, v in rep["checks"].items():
            print(f"  {'PASS' if v else 'FAIL'}  {k}")
        if rep["problems"]:
            print("\nPROBLEMS:")
            for p in rep["problems"]:
                print("  -", p)
        print("\nINTEGRITY:", "PASS" if rep["integrity_pass"] else "FAIL")
    return 0 if rep["integrity_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
