"""登记、校验并解析用户正常下载的申万官方原始文件。

本脚本不联网。在线下载与解析严格解耦，且不会修改 raw 文件。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.data.providers.shenwan_official import (  # noqa: E402
    DEFAULT_RAW_DIR,
    STOCK_CLASSIFICATION_FILENAME,
    STOCK_CLASSIFICATION_URL,
    ShenwanAdmissionError,
    assert_level_b_admissible,
    discover_raw_files,
    initialize_manifest,
    level_b_admission_issues,
    parse_stock_classification,
    register_raw_file,
    verify_manifest,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help="官方原始文件目录（默认 data/raw/shenwan）",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init-manifest", help="创建空 manifest（不覆盖现有文件）")
    commands.add_parser("discover", help="列出 raw 目录中的原始文件")
    commands.add_parser("verify", help="核对 manifest、文件存在性与 SHA256")

    def add_registration_arguments(command, *, classification_defaults: bool) -> None:
        command.add_argument(
            "--filename",
            default=STOCK_CLASSIFICATION_FILENAME if classification_defaults else None,
            required=not classification_defaults,
        )
        command.add_argument(
            "--source-url",
            default=STOCK_CLASSIFICATION_URL if classification_defaults else None,
            required=not classification_defaults,
        )
        command.add_argument(
            "--retrieved-at",
            default=None,
            help="带时区 ISO-8601；未知则保留 null，不使用文件 mtime 猜测",
        )
        command.add_argument(
            "--classification-version",
            default=None,
            help="仅填写有官方证据的版本；未知则保留 null",
        )
        command.add_argument("--notes", default="")

    register = commands.add_parser("register", help="登记任意后续官方原始文件")
    add_registration_arguments(register, classification_defaults=False)
    register_classification = commands.add_parser(
        "register-classification", help="登记官方分类文件"
    )
    add_registration_arguments(register_classification, classification_defaults=True)

    parse = commands.add_parser("parse-classification", help="解析为 canonical CSV")
    parse.add_argument("--filename", default=STOCK_CLASSIFICATION_FILENAME)
    parse.add_argument("--output", type=Path, required=True)
    parse.add_argument(
        "--require-level-b-admission",
        action="store_true",
        help="缺少任何 PIT 字段时拒绝写出",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "init-manifest":
        print(initialize_manifest(args.raw_dir))
        return 0
    if args.command == "discover":
        for path in discover_raw_files(args.raw_dir):
            print(path.name)
        return 0
    if args.command == "verify":
        records = verify_manifest(args.raw_dir)
        print(json.dumps({"verified_files": len(records)}, ensure_ascii=False))
        return 0
    if args.command in {"register", "register-classification"}:
        record = register_raw_file(
            args.filename,
            source_url=args.source_url,
            retrieved_at=args.retrieved_at,
            classification_version=args.classification_version,
            notes=args.notes,
            raw_dir=args.raw_dir,
        )
        print(json.dumps(record.__dict__, ensure_ascii=False, indent=2))
        return 0
    if args.command == "parse-classification":
        frame = parse_stock_classification(args.raw_dir, filename=args.filename)
        issues = level_b_admission_issues(frame)
        if args.require_level_b_admission:
            try:
                assert_level_b_admissible(frame)
            except ShenwanAdmissionError as exc:
                print(str(exc), file=sys.stderr)
                return 2
        output = args.output.resolve()
        raw_root = args.raw_dir.resolve()
        if output == raw_root or raw_root in output.parents:
            raise ValueError("解析结果不得写入 raw 目录")
        output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output, index=False)
        print(
            json.dumps(
                {
                    "output": str(output),
                    "rows": len(frame),
                    "level_b_admission": not issues,
                    "admission_issues": issues,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    raise AssertionError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
