#!/usr/bin/env python3

"""Build the standalone content_census_report.py script from source sections."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SECTION_ORDER = (
    "_header.py",
    "models.py",
    "analysis.py",
    "clawhub_catalog_data.py",
    "clawhub_slug_index_data.py",
    "reference_utils.py",
    "clawhub_catalog.py",
    "file_knowledge.py",
    "file_type_knowledge.py",
    "report.py",
    "report_payloads.py",
    "report_helpers.py",
    "live_scan.py",
)


def _build_text(source_dir: Path) -> str:
    chunks: list[str] = []
    for name in SECTION_ORDER:
        path = source_dir / name
        chunks.append(path.read_text(encoding="utf-8"))
    return "".join(chunks)


def build_single_file(source_dir: Path, output_path: Path) -> None:
    output_path.write_text(_build_text(source_dir), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        default="src_content_census",
        help="Directory containing the source sections.",
    )
    parser.add_argument(
        "--output",
        default="content_census_report.py",
        help="Generated standalone script path.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the generated content differs from the output file.",
    )
    args = parser.parse_args(argv)

    source_dir = Path(args.source_dir)
    output_path = Path(args.output)
    built_text = _build_text(source_dir)

    if args.check:
        try:
            current_text = output_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return 1
        return 0 if current_text == built_text else 1

    output_path.write_text(built_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
