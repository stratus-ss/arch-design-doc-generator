#!/usr/bin/env python3
"""Replace Chapter 6 Level of Impact lines from the HC knowledge-base TOML.

Matches each §6.2 finding by **Check ID** (first backtick id for grouped
findings) and rewrites the **Level of Impact:** line using the same
formatting as the report renderer. Other chapters and customized body
text are left unchanged.

Usage:
    python3 scripts/health_check/update_finding_loi.py REPORT.md --output UPDATED.md
    python3 scripts/health_check/update_finding_loi.py REPORT.md --in-place
    python3 scripts/health_check/update_finding_loi.py REPORT.md --dry-run
    python3 scripts/health_check/update_finding_loi.py --self-test REPORT.md
"""
from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
for extra_path in (_SCRIPT_DIR.parent / "shared" / "lib", _SCRIPT_DIR):
    extra = str(extra_path)
    if extra not in sys.path:
        sys.path.insert(0, extra)

from hc_report._text import parse_check_ids_from_line
from hc_report.kb_loader import KnowledgeBase, format_impact_line, load_kb

_CHAPTER_HEADING_PREFIX = "## Chapter "
_FINDING_HEADING_PREFIX = "#### "
_LEVEL_OF_IMPACT_PREFIX = "**Level of Impact:**"
_BACKUP_SUFFIX = ".loi.bak"


@dataclass(frozen=True)
class LoiReplacement:
    line_index: int
    check_id: str
    old_line: str
    new_line: str
    skipped_reason: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rewrite Chapter 6 Level of Impact lines from kb/*.toml by check_id"
        )
    )
    parser.add_argument(
        "report",
        type=Path,
        nargs="?",
        help="Path to one rendered HC report markdown file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write updated markdown here (does not modify the input file)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help=f"Overwrite the report after copying it to <name>{_BACKUP_SUFFIX}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned replacements; do not write a file",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run functional checks on a copy of REPORT; never write REPORT",
    )
    parser.add_argument(
        "--kb-dir",
        type=Path,
        default=None,
        help="Override knowledge-base directory (defaults to hc_report/kb)",
    )
    return parser.parse_args()


def chapter_slice(lines: list[str], chapter_number: int) -> tuple[int, int]:
    start: int | None = None
    end = len(lines)
    for index, line in enumerate(lines):
        if not line.startswith(_CHAPTER_HEADING_PREFIX):
            continue
        tail = line[len(_CHAPTER_HEADING_PREFIX):].lstrip()
        number_text = tail.split(".", 1)[0].split(" ", 1)[0]
        if not number_text.isdigit():
            continue
        number = int(number_text)
        if number == chapter_number and start is None:
            start = index
        elif start is not None and number > chapter_number:
            end = index
            break
    if start is None:
        raise ValueError(f"markdown has no {_CHAPTER_HEADING_PREFIX}{chapter_number}")
    return start, end


def planned_replacements(markdown: str, knowledge_base: KnowledgeBase) -> list[LoiReplacement]:
    lines = markdown.splitlines()
    start, end = chapter_slice(lines, 6)
    replacements: list[LoiReplacement] = []
    current_check_ids: list[str] = []
    for index in range(start, end):
        line = lines[index]
        if line.startswith(_FINDING_HEADING_PREFIX):
            current_check_ids = []
            continue
        extracted = parse_check_ids_from_line(line)
        if extracted:
            current_check_ids = extracted
            continue
        if not line.startswith(_LEVEL_OF_IMPACT_PREFIX):
            continue
        if not current_check_ids:
            replacements.append(
                LoiReplacement(
                    line_index=index,
                    check_id="",
                    old_line=line,
                    new_line=line,
                    skipped_reason="Level of Impact with no Check ID in this finding",
                )
            )
            continue
        check_id = current_check_ids[0]
        impact_tuple = knowledge_base.get_impact(check_id)
        if impact_tuple is None:
            if knowledge_base.get_entry(check_id) is None:
                replacements.append(
                    LoiReplacement(
                        line_index=index,
                        check_id=check_id,
                        old_line=line,
                        new_line=line,
                        skipped_reason="check_id not in knowledge base",
                    )
                )
                continue
            new_line = format_impact_line("", "", "")
        else:
            new_line = format_impact_line(*impact_tuple)
        replacements.append(
            LoiReplacement(
                line_index=index,
                check_id=check_id,
                old_line=line,
                new_line=new_line,
            )
        )
    return replacements


def apply_replacements(markdown: str, replacements: list[LoiReplacement]) -> str:
    lines = markdown.splitlines()
    newline = "\n" if markdown.endswith("\n") else ""
    for replacement in replacements:
        if replacement.skipped_reason:
            continue
        lines[replacement.line_index] = replacement.new_line
    return "\n".join(lines) + newline


def backup_path_for(report: Path) -> Path:
    return report.with_name(report.name + _BACKUP_SUFFIX)


def print_summary(replacements: list[LoiReplacement]) -> None:
    updated = 0
    unchanged = 0
    skipped = 0
    for replacement in replacements:
        if replacement.skipped_reason:
            skipped += 1
            print(
                f"SKIP  line {replacement.line_index + 1}  "
                f"{replacement.check_id or '-'}  {replacement.skipped_reason}",
                file=sys.stderr,
            )
            continue
        if replacement.old_line == replacement.new_line:
            unchanged += 1
            continue
        updated += 1
        print(f"UPDATE  {replacement.check_id}")
        print(f"  old: {replacement.old_line}")
        print(f"  new: {replacement.new_line}")
    print(
        f"{updated} updated, {unchanged} already current, {skipped} skipped",
        file=sys.stderr,
    )


def _assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: {actual!r} != {expected!r}")


def _synthetic_markdown() -> str:
    return (
        "## Chapter 5. Outside\n\n"
        "**Level of Impact:** must not change\n\n"
        "## Chapter 6. Observations and Recommendations\n\n"
        "#### 6.2.2.1. Monitoring configuration\n\n"
        "**Check ID:** `7.3.monitoring.config`\n\n"
        "**Level of Impact:** None\n\n"
        "#### 6.2.2.2. Grouped etcd\n\n"
        "**Check ID:** `7.3.tsr.3_5_7_etcd_log_errors` `7.3.tsr.3_5_5_etcd_compaction`\n\n"
        "**Level of Impact:** [NEEDS REVIEW]\n\n"
        "## Chapter 7. Detailed Findings\n\n"
        "**Check ID:** `7.3.monitoring.config`\n"
        "**Level of Impact:** must not change\n"
    )


def run_synthetic_self_test(knowledge_base: KnowledgeBase) -> None:
    original = _synthetic_markdown()
    replacements = planned_replacements(original, knowledge_base)
    updated = apply_replacements(original, replacements)
    start, end = chapter_slice(original.splitlines(), 6)
    original_lines = original.splitlines()
    updated_lines = updated.splitlines()
    _assert_equal(original_lines[:start], updated_lines[:start], "text before chapter 6")
    _assert_equal(original_lines[end:], updated_lines[end:], "text after chapter 6")
    monitoring = knowledge_base.get_impact("7.3.monitoring.config")
    etcd_errors = knowledge_base.get_impact("7.3.tsr.3_5_7_etcd_log_errors")
    if monitoring is None or etcd_errors is None:
        raise AssertionError("synthetic check_ids missing from knowledge base")
    expected_monitoring = format_impact_line(*monitoring)
    expected_etcd = format_impact_line(*etcd_errors)
    _assert_equal(
        expected_monitoring in updated,
        True,
        "monitoring LOI from first check_id",
    )
    _assert_equal(
        expected_etcd in updated,
        True,
        "grouped finding uses first check_id",
    )
    _assert_equal(
        "**Level of Impact:** must not change" in updated,
        True,
        "non-chapter-6 LOI preserved",
    )
    _assert_equal("**Level of Impact:** None\n" in updated, False, "stale None replaced")


def run_report_self_test(report: Path, knowledge_base: KnowledgeBase) -> None:
    original_bytes = report.read_bytes()
    markdown = original_bytes.decode("utf-8")
    replacements = planned_replacements(markdown, knowledge_base)
    updated = apply_replacements(markdown, replacements)
    if report.read_bytes() != original_bytes:
        raise AssertionError("self-test mutated the input report")
    original_lines = markdown.splitlines()
    updated_lines = updated.splitlines()
    start, end = chapter_slice(original_lines, 6)
    _assert_equal(original_lines[:start], updated_lines[:start], "prefix outside chapter 6")
    _assert_equal(original_lines[end:], updated_lines[end:], "suffix outside chapter 6")
    check_id_lines_before = [
        line for line in original_lines[start:end] if line.startswith("**Check ID:**")
    ]
    check_id_lines_after = [
        line for line in updated_lines[start:end] if line.startswith("**Check ID:**")
    ]
    _assert_equal(check_id_lines_before, check_id_lines_after, "Check ID lines")
    applied = [item for item in replacements if not item.skipped_reason]
    if not applied:
        raise AssertionError("chapter 6 had no Level of Impact lines")
    for replacement in applied:
        impact_tuple = knowledge_base.get_impact(replacement.check_id)
        if impact_tuple is None:
            expected = format_impact_line("", "", "")
        else:
            expected = format_impact_line(*impact_tuple)
        _assert_equal(
            updated_lines[replacement.line_index],
            expected,
            f"LOI for {replacement.check_id}",
        )


def main() -> int:
    args = parse_args()
    if args.report is None:
        print("error: REPORT path is required", file=sys.stderr)
        return 2
    report = args.report.expanduser().resolve()
    if not report.is_file():
        print(f"error: report not found: {report}", file=sys.stderr)
        return 2
    knowledge_base = load_kb(args.kb_dir)
    if args.self_test:
        run_synthetic_self_test(knowledge_base)
        run_report_self_test(report, knowledge_base)
        print("self-test passed (input report unchanged)")
        return 0
    if args.in_place and args.output is not None:
        print("error: use either --in-place or --output, not both", file=sys.stderr)
        return 2
    if not args.dry_run and not args.in_place and args.output is None:
        print("error: pass --output, --in-place, or --dry-run", file=sys.stderr)
        return 2
    markdown = report.read_text(encoding="utf-8")
    replacements = planned_replacements(markdown, knowledge_base)
    print_summary(replacements)
    if args.dry_run:
        return 0
    updated = apply_replacements(markdown, replacements)
    if args.in_place:
        backup = backup_path_for(report)
        shutil.copy2(report, backup)
        report.write_text(updated, encoding="utf-8")
        print(f"wrote {report} (backup {backup})", file=sys.stderr)
        return 0
    output_path = args.output.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(updated, encoding="utf-8")
    print(f"wrote {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
