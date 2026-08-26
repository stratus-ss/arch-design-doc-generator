#!/usr/bin/env python3
"""Extract P0–P3 finding descriptions and check IDs from one HC report.

Reads a single rendered markdown report (explicit path, not a glob) and
prints Chapter 6.2 description bodies with check_id so a consultant can
draft the executive summary and conclusion and look up the KB TOML row.

Usage:
    python3 scripts/health_check/extract_finding_descriptions.py \\
        output/Health_Check_Report/Example_OpenShift_Health_Check_one-6x489.md
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_PRIORITY_HEADING = re.compile(r"^### (P[0-3]):\s")
_FINDING_HEADING = re.compile(r"^#### (6\.2\.\d+(?:\.\d+)+)\.\s+(.+?)\s*$")
_CHECK_ID_LINE = re.compile(r"^\*\*Check ID:\*\*\s+(.*)$")
_BACKTICK_VALUE = re.compile(r"`([^`]+)`")
_CHAPTER_HEADING = re.compile(r"^## Chapter (\d+)")


@dataclass
class FindingDescription:
    priority: str
    finding_id: str
    title: str
    check_ids: list[str] = field(default_factory=list)
    description: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Print P0–P3 finding descriptions and check IDs from one HC report."
        )
    )
    parser.add_argument(
        "report",
        type=Path,
        help="Path to one rendered HC report markdown file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional file to write (stdout is always used)",
    )
    return parser.parse_args()


def _priority_from_heading(line: str) -> str | None:
    match = _PRIORITY_HEADING.match(line)
    if not match:
        return None
    return match.group(1)


def _finding_from_heading(line: str) -> tuple[str, str] | None:
    match = _FINDING_HEADING.match(line)
    if not match:
        return None
    return match.group(1), match.group(2)


def _check_ids_from_line(line: str) -> list[str] | None:
    match = _CHECK_ID_LINE.match(line)
    if not match:
        return None
    values = _BACKTICK_VALUE.findall(match.group(1))
    if values:
        return values
    leftover = match.group(1).strip()
    return [leftover] if leftover else []


def _is_description_stop(line: str) -> bool:
    return line.startswith("**Observation:**") or line.startswith("**Recommendation:**")


def _flush_finding(
    current: FindingDescription | None,
    description_lines: list[str],
    findings: list[FindingDescription],
) -> None:
    if current is None:
        return
    current.description = "\n".join(description_lines).strip()
    findings.append(current)


def extract_finding_descriptions(markdown: str) -> list[FindingDescription]:
    findings: list[FindingDescription] = []
    current: FindingDescription | None = None
    current_priority = ""
    collecting_description = False
    description_lines: list[str] = []

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        chapter_match = _CHAPTER_HEADING.match(line)
        if chapter_match is not None and int(chapter_match.group(1)) >= 7:
            break

        priority = _priority_from_heading(line)
        if priority is not None:
            _flush_finding(current, description_lines, findings)
            current = None
            description_lines = []
            collecting_description = False
            current_priority = priority
            continue

        heading = _finding_from_heading(line)
        if heading is not None:
            _flush_finding(current, description_lines, findings)
            finding_id, title = heading
            current = FindingDescription(
                priority=current_priority,
                finding_id=finding_id,
                title=title,
            )
            description_lines = []
            collecting_description = False
            continue

        check_ids = _check_ids_from_line(line)
        if check_ids is not None and current is not None:
            current.check_ids = check_ids
            continue

        if line.startswith("**Description:**"):
            collecting_description = True
            remainder = line[len("**Description:**"):].strip()
            description_lines = [remainder] if remainder else []
            continue

        if _is_description_stop(line):
            collecting_description = False
            continue

        if collecting_description and current is not None:
            description_lines.append(line)

    _flush_finding(current, description_lines, findings)
    return findings


def format_finding_descriptions(
    findings: list[FindingDescription],
    report_path: Path,
    include_source_path: bool = True,
) -> str:
    counts = {priority: 0 for priority in ("P0", "P1", "P2", "P3")}
    for finding in findings:
        if finding.priority in counts:
            counts[finding.priority] += 1
    total = len(findings)
    lines: list[str] = []
    if include_source_path:
        lines.append(f"Finding descriptions from: {report_path}")
    lines.extend(
        [
            (
                f"Counts: P0={counts['P0']} P1={counts['P1']} "
                f"P2={counts['P2']} P3={counts['P3']} (total {total})"
            ),
            "",
        ]
    )
    last_priority = ""
    for finding in findings:
        if finding.priority != last_priority:
            lines.append(f"## {finding.priority}")
            lines.append("")
            last_priority = finding.priority
        check_id_text = " ".join(finding.check_ids) if finding.check_ids else "n/a"
        lines.append(f"### {finding.finding_id} — {finding.title}")
        lines.append(f"Check ID: {check_id_text}")
        lines.append("")
        if finding.description:
            lines.append(finding.description)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    report_path = args.report
    if not report_path.is_file():
        print(f"Error: report not found at {report_path}", file=sys.stderr)
        sys.exit(2)

    markdown = report_path.read_text(encoding="utf-8")
    findings = extract_finding_descriptions(markdown)
    rendered = format_finding_descriptions(findings, report_path)

    if args.output is not None:
        args.output.write_text(rendered, encoding="utf-8")

    sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
