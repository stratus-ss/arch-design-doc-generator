#!/usr/bin/env python3
"""Resequence Chapter 6 finding numbers after a consultant reorders sections.

Walks §6.2 in document order, assigns 6.2.{band}.{n} from the ### P0–P3
heading each finding sits under, then rewrites headings, §6.1, and
finding-* anchors (including Chapter 7 data-finding-ids).

Usage:
    python3 scripts/health_check/renumber_finding_sections.py REPORT.md
    python3 scripts/health_check/renumber_finding_sections.py --dry-run REPORT.md
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_PRIORITY_PREFIX: dict[str, str] = {
    "P0": "6.2.1",
    "P1": "6.2.2",
    "P2": "6.2.3",
    "P3": "6.2.4",
}
_CHAPTER_HEADING = re.compile(r"^## Chapter (\d+)")
_PRIORITY_HEADING = re.compile(r"^### (P[0-3]):\s")
_FINDING_HEADING = re.compile(r"^#### (6\.2\.\d+(?:\.\d+)+)\.\s+(.+?)\s*$")
_CRITICAL_ROW = re.compile(
    r"^\| (P[0-3]) \| (6\.2\.\d+(?:\.\d+)+) — (.+?) \| (.*) \|$"
)
_ANCHOR_TOKEN = re.compile(r"[^a-z0-9]+")
_CRITICAL_HEADING = "### 6.1 Critical Findings Summary"
_SECTION_6_2_HEADING = "### 6.2 Observations and Recommendations by Priority"
_EMPTY_CRITICAL = "_No critical or high-priority findings identified._"
_PLACEHOLDER_ID_PREFIX = "@@FINDING_ID_"
_PLACEHOLDER_ANCHOR_PREFIX = "@@FINDING_ANCHOR_"
_PLACEHOLDER_SUFFIX = "@@"


@dataclass
class FindingPlacement:
    old_id: str
    title: str
    priority: str
    summary: str
    new_id: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rewrite §6.2 finding numbers (and §6.1 / finding anchors) "
            "from document order under each P0–P3 band"
        )
    )
    parser.add_argument(
        "report",
        type=Path,
        help="Path to one rendered HC report markdown file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the old→new mapping; do not write the file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write to this path instead of replacing the report in place",
    )
    return parser.parse_args()


def sanitize_anchor_id(text: str) -> str:
    if not text:
        return "item"
    normalized = _ANCHOR_TOKEN.sub("-", text.lower()).strip("-")
    return normalized or "item"


def finding_anchor_id(finding_id: str) -> str:
    return f"finding-{sanitize_anchor_id(finding_id)}"


def _placeholder_id(finding_id: str) -> str:
    return f"{_PLACEHOLDER_ID_PREFIX}{finding_id}{_PLACEHOLDER_SUFFIX}"


def _placeholder_anchor(finding_id: str) -> str:
    return f"{_PLACEHOLDER_ANCHOR_PREFIX}{finding_id}{_PLACEHOLDER_SUFFIX}"


def _replace_finding_id_token(text: str, old_id: str, new_id: str) -> str:
    # Headings are `#### 6.2.2.1. Title` (dot after the id). Do not treat that
    # separator as another numeric component, and do not match 6.2.2.1 inside 6.2.2.10.
    pattern = re.compile(r"(?<![\d.])" + re.escape(old_id) + r"(?!\.?\d)")
    return pattern.sub(new_id, text)


def _replace_finding_anchor_token(text: str, old_id: str, new_token: str) -> str:
    old_anchor = finding_anchor_id(old_id)
    pattern = re.compile(r"(?<![0-9])" + re.escape(old_anchor) + r"(?![0-9])")
    return pattern.sub(new_token, text)


def parse_critical_summaries(markdown: str) -> dict[str, str]:
    summaries: dict[str, str] = {}
    for line in markdown.splitlines():
        match = _CRITICAL_ROW.match(line)
        if match is None:
            continue
        summaries[match.group(2)] = match.group(4).strip()
    return summaries


def collect_finding_placements(markdown: str) -> list[FindingPlacement]:
    placements: list[FindingPlacement] = []
    current_chapter = 0
    current_priority = ""
    collecting_observation = False
    in_section_6_2 = False

    for line_number, raw_line in enumerate(markdown.splitlines(), start=1):
        line = raw_line.rstrip()
        chapter_match = _CHAPTER_HEADING.match(line)
        if chapter_match is not None:
            current_chapter = int(chapter_match.group(1))
            if current_chapter >= 7:
                break
            continue

        if line.startswith(_SECTION_6_2_HEADING):
            in_section_6_2 = True
            continue

        if current_chapter != 6 or not in_section_6_2:
            continue

        priority = _PRIORITY_HEADING.match(line)
        if priority is not None:
            current_priority = priority.group(1)
            collecting_observation = False
            continue

        heading = _FINDING_HEADING.match(line)
        if heading is not None:
            if not current_priority:
                raise ValueError(
                    f"line {line_number}: finding {heading.group(1)} is not "
                    "under a ### P0–P3 heading"
                )
            placements.append(
                FindingPlacement(
                    old_id=heading.group(1),
                    title=heading.group(2),
                    priority=current_priority,
                    summary="",
                )
            )
            collecting_observation = False
            continue

        if not placements:
            continue

        if line.startswith("**Observation:**"):
            collecting_observation = True
            remainder = line[len("**Observation:**"):].strip()
            if remainder and not placements[-1].summary:
                placements[-1].summary = remainder
            continue

        if line.startswith("**Recommendation:**") or line.startswith("**Description:**"):
            collecting_observation = False
            continue

        if not collecting_observation or placements[-1].summary:
            continue
        if not line or line.startswith("<span"):
            continue
        placements[-1].summary = line

    return placements


def assign_new_ids(placements: list[FindingPlacement]) -> None:
    counters: dict[str, int] = {priority: 0 for priority in _PRIORITY_PREFIX}
    for placement in placements:
        counters[placement.priority] += 1
        prefix = _PRIORITY_PREFIX[placement.priority]
        placement.new_id = f"{prefix}.{counters[placement.priority]}"


def apply_table_summaries(
    placements: list[FindingPlacement],
    summaries: dict[str, str],
) -> None:
    for placement in placements:
        table_summary = summaries.get(placement.old_id)
        if table_summary:
            placement.summary = table_summary


def apply_id_map(markdown: str, placements: list[FindingPlacement]) -> str:
    rewritten = markdown
    ordered = sorted(placements, key=lambda item: len(item.old_id), reverse=True)
    for placement in ordered:
        rewritten = _replace_finding_id_token(
            rewritten, placement.old_id, _placeholder_id(placement.old_id)
        )
        rewritten = _replace_finding_anchor_token(
            rewritten, placement.old_id, _placeholder_anchor(placement.old_id)
        )
    for placement in placements:
        rewritten = rewritten.replace(_placeholder_id(placement.old_id), placement.new_id)
        rewritten = rewritten.replace(
            _placeholder_anchor(placement.old_id),
            finding_anchor_id(placement.new_id),
        )
    return rewritten


def build_critical_table(placements: list[FindingPlacement]) -> str:
    critical = [
        placement
        for placement in placements
        if placement.priority in ("P0", "P1")
    ]
    if not critical:
        return _EMPTY_CRITICAL
    lines = [
        "| Priority | Finding | Summary |",
        "|----------|---------|---------|",
    ]
    for placement in critical:
        summary = placement.summary or ""
        lines.append(
            f"| {placement.priority} | {placement.new_id} — {placement.title} "
            f"| {summary} |"
        )
    return "\n".join(lines)


def rebuild_critical_summary(markdown: str, placements: list[FindingPlacement]) -> str:
    heading_at = markdown.find(_CRITICAL_HEADING)
    section_at = markdown.find(_SECTION_6_2_HEADING)
    if heading_at == -1:
        raise ValueError("report missing ### 6.1 Critical Findings Summary")
    if section_at == -1 or section_at < heading_at:
        raise ValueError(
            "report missing ### 6.2 Observations and Recommendations by Priority"
        )
    table = build_critical_table(placements)
    return (
        markdown[:heading_at]
        + _CRITICAL_HEADING
        + "\n\n"
        + table
        + "\n\n"
        + markdown[section_at:]
    )


def renumber_finding_sections(markdown: str) -> tuple[str, list[FindingPlacement]]:
    placements = collect_finding_placements(markdown)
    apply_table_summaries(placements, parse_critical_summaries(markdown))
    assign_new_ids(placements)
    rewritten = apply_id_map(markdown, placements)
    rewritten = rebuild_critical_summary(rewritten, placements)
    if not rewritten.endswith("\n"):
        rewritten += "\n"
    return rewritten, placements


def format_mapping(placements: list[FindingPlacement]) -> str:
    if not placements:
        return "No §6.2 finding headings found.\n"
    lines = []
    changed = 0
    for placement in placements:
        marker = "" if placement.old_id == placement.new_id else " *"
        if placement.old_id != placement.new_id:
            changed += 1
        lines.append(
            f"{placement.old_id} -> {placement.new_id} "
            f"{placement.priority} {placement.title}{marker}"
        )
    lines.append(f"Changed: {changed} of {len(placements)}")
    return "\n".join(lines) + "\n"


def atomic_write(path: Path, text: str) -> None:
    temporary_path = path.with_name(path.name + ".tmp")
    temporary_path.write_text(text, encoding="utf-8")
    temporary_path.replace(path)


def main() -> None:
    args = parse_args()
    report_path = args.report
    if not report_path.is_file():
        print(f"Error: report not found at {report_path}", file=sys.stderr)
        sys.exit(2)

    markdown = report_path.read_text(encoding="utf-8")
    try:
        rewritten, placements = renumber_finding_sections(markdown)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    sys.stdout.write(format_mapping(placements))

    if args.dry_run:
        return

    destination = args.output if args.output is not None else report_path
    if destination.resolve() == report_path.resolve() and rewritten == markdown:
        return
    atomic_write(destination, rewritten)


if __name__ == "__main__":
    main()
