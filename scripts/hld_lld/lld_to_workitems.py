#!/usr/bin/env python3
"""
lld_to_workitems.py — Deterministic LLD-to-work-item exporter.

Parses LLD Phase*.md files and exports each LLD section as a standalone
markdown work-item file suitable for a Kanban board.  Optionally produces
a Jira-compatible CSV for bulk import.

Configuration is read from project.yaml (auto-detected or via --config).

Usage:
    python3 lld_to_workitems.py                          # markdown output
    python3 lld_to_workitems.py --format csv             # CSV only
    python3 lld_to_workitems.py --format both            # markdown + CSV
    python3 lld_to_workitems.py --output-dir ./sprint3   # custom output dir
    python3 lld_to_workitems.py --phases phase1 phase2   # yaml phase ids
    python3 lld_to_workitems.py --phases 1 2             # integer tokens → phase1, phase2
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from config import find_project_yaml, load_config

SCRIPT_DIR = Path(__file__).resolve().parent

SECTION_HEADING_RE = re.compile(r"^## (LLD-(\d+):\s*(.+))$")
SUBSECTION_RE = re.compile(r"^### (.+)$")
ADR_TAG_RE = re.compile(r"\*\(ADR ([^)]+)\)\*")
CG_ROW_RE = re.compile(r"^\|\s*(CG-\S+)\s*\|(.+)")
AC_ROW_RE = re.compile(r"^\|\s*(AC-\S+)\s*\|(.+)")
DEP_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$")
TIER_HEADER_RE = re.compile(r"^\|.*DC.*\|.*Tier 2.*\|.*Tier 3 Site.*\|", re.IGNORECASE)


def _build_phase_maps(config: dict) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Build phase file/name/dir maps keyed by yaml phase id."""
    phase_files = {}
    phase_names = {}
    phase_dir_names = {}
    for phase in config["phases"]:
        phase_id = str(phase["id"])
        phase_files[phase_id] = phase["lld_file"]
        phase_names[phase_id] = f"{phase_id} — {phase['name']}"
        phase_dir_names[phase_id] = phase["dir_name"]
    return phase_files, phase_names, phase_dir_names


def _normalize_phase_token(token: str) -> str:
    """Map CLI tokens to yaml ids. Digits become phaseN (not list index)."""
    if token.isdigit():
        return f"phase{token}"
    return token


@dataclass
class LLDSection:
    lld_id: str
    lld_number: int
    title: str
    full_heading: str
    description: str = ""
    adr_refs: str = ""
    completion_gates: list[str] = field(default_factory=list)
    dependencies: list[tuple[str, str]] = field(default_factory=list)
    impl_full: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    has_tier_variance: bool = False
    tier_scope: str = ""
    raw_subsections: dict[str, str] = field(default_factory=dict)


def _build_section(match: re.Match, section_lines: list[str]) -> LLDSection:
    """Parse a single LLD section block into an LLDSection."""
    full_heading = match.group(1)
    lld_number = int(match.group(2))
    title = match.group(3).strip()
    lld_id = f"LLD-{lld_number:02d}"
    sec = LLDSection(lld_id=lld_id, lld_number=lld_number, title=title, full_heading=full_heading)
    subsections = _split_subsections(section_lines)
    sec.raw_subsections = subsections

    desc_text = subsections.get("_description", "").strip()
    adr_match = ADR_TAG_RE.search(desc_text)
    if adr_match:
        sec.adr_refs = f"ADR {adr_match.group(1)}"
        desc_text = ADR_TAG_RE.sub("", desc_text).strip()
    sec.description = desc_text

    cg_raw = subsections.get("Prerequisites", "") or subsections.get("Completion Gates", "")
    for line in cg_raw.split("\n"):
        match = CG_ROW_RE.match(line)
        if match:
            cg_id = match.group(1).strip()
            columns = []
            for column_text in match.group(2).split("|"):
                columns.append(column_text.strip())
            item = columns[0] if columns else ""
            sec.completion_gates.append(f"{cg_id}: {item}")

    _parse_dependencies(sec, subsections.get("Dependencies", ""))
    sec.impl_full = subsections.get("Implementation Procedure", "").strip()

    for line in subsections.get("Acceptance Criteria", "").split("\n"):
        match = AC_ROW_RE.match(line)
        if match:
            ac_id = match.group(1).strip()
            columns = []
            for column_text in match.group(2).split("|"):
                columns.append(column_text.strip())
            criterion = columns[0] if columns else ""
            sec.acceptance_criteria.append(f"{ac_id}: {criterion}")

    tier_variance_lines = []
    for line in subsections.get("Tier Variance", "").strip().split("\n"):
        if line.strip():
            tier_variance_lines.append(line)
    has_tier_header = False
    for line in tier_variance_lines:
        if TIER_HEADER_RE.match(line):
            has_tier_header = True
            break
    if tier_variance_lines and has_tier_header:
        sec.has_tier_variance = True
        sec.tier_scope = "DC, Tier 2, Tier 3 Site (variance exists)"
    else:
        sec.tier_scope = "DC, Tier 2, Tier 3 Site (no variance)"

    return sec


def parse_phase_file(filepath: Path) -> tuple[str, list[LLDSection]]:
    text = filepath.read_text(encoding="utf-8")
    lines = text.split("\n")

    phase_title = ""
    for line in lines:
        if line.startswith("# "):
            phase_title = line.lstrip("# ").strip()
            break

    section_starts: list[tuple[int, re.Match]] = []
    for line_index, line in enumerate(lines):
        match = SECTION_HEADING_RE.match(line)
        if match:
            section_starts.append((line_index, match))

    sections: list[LLDSection] = []
    for index, (start_line, match) in enumerate(section_starts):
        end_line = section_starts[index + 1][0] if index + 1 < len(section_starts) else len(lines)
        sections.append(_build_section(match, lines[start_line:end_line]))

    return phase_title, sections


def _parse_dependencies(sec: LLDSection, dep_text: str) -> None:
    """Parse the ### Dependencies table into (blocked_by, reason) tuples."""
    past_header = False
    for line in dep_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("|--") or stripped.startswith("| Blocked"):
            past_header = True
            continue
        if not past_header:
            continue
        match = DEP_ROW_RE.match(stripped)
        if match:
            blocked_by = match.group(1).strip()
            reason = match.group(2).strip()
            if blocked_by and blocked_by != "Blocked By":
                sec.dependencies.append((blocked_by, reason))


def _split_subsections(section_lines: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    current_key = "_description"
    current_lines: list[str] = []

    for line in section_lines[1:]:
        match = SUBSECTION_RE.match(line)
        if match:
            result[current_key] = "\n".join(current_lines)
            current_key = match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)

    result[current_key] = "\n".join(current_lines)
    return result


def render_work_item_md(sec: LLDSection, phase_id: str, phase_dir_names: dict, phase_names: dict) -> str:
    blocked_by_summary = ", ".join(blocked_by for blocked_by, _ in sec.dependencies) if sec.dependencies else "None"

    lines = [
        f"# [{phase_dir_names[phase_id].split('_')[0]}-{sec.lld_id}] {sec.title}",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Phase | {phase_names[phase_id]} |",
        f"| LLD Section | {sec.lld_id} |",
        f"| ADR | {sec.adr_refs or '—'} |",
        f"| Tier Scope | {sec.tier_scope} |",
        f"| Blocked By | {blocked_by_summary} |",
        "",
    ]

    if sec.description:
        lines += ["## Description", "", sec.description, ""]

    if sec.dependencies:
        lines += ["## Dependencies", "", "| Blocked By | Reason |", "|------------|--------|"]
        for blocked_by, reason in sec.dependencies:
            lines.append(f"| {blocked_by} | {reason} |")
        lines.append("")

    if sec.completion_gates:
        lines += ["## Definition of Done"]
        for completion_gate in sec.completion_gates:
            lines.append(f"- [ ] {completion_gate}")
        lines.append("")

    if sec.impl_full:
        lines += ["## Implementation Procedure", "", sec.impl_full, ""]

    if sec.acceptance_criteria:
        lines += ["## Acceptance Criteria"]
        for criterion in sec.acceptance_criteria:
            lines.append(f"- [ ] {criterion}")
        lines.append("")

    return "\n".join(lines)


def render_csv_row(sec: LLDSection, phase_id: str, phase_dir_names: dict, phase_names: dict) -> dict[str, str]:
    ac_text = "; ".join(sec.acceptance_criteria) if sec.acceptance_criteria else ""
    cg_text = "; ".join(sec.completion_gates) if sec.completion_gates else ""
    blocked_by = ", ".join(blocked_by for blocked_by, _ in sec.dependencies) if sec.dependencies else ""
    return {
        "Summary": f"[{phase_dir_names[phase_id].split('_')[0]}-{sec.lld_id}] {sec.title}",
        "Description": sec.description,
        "Component": sec.lld_id,
        "Epic Link": phase_names[phase_id],
        "Labels": sec.adr_refs,
        "Acceptance Criteria": ac_text,
        "Definition of Done": cg_text,
        "Tier Scope": sec.tier_scope,
        "Blocked By": blocked_by,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export LLD sections as work-item markdown files and/or Jira CSV.")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to project.yaml (default: auto-detect)",
    )
    parser.add_argument(
        "--format",
        choices=["md", "csv", "both"],
        default="md",
        help="Output format (default: md)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: from config or Work_Items/)",
    )
    parser.add_argument(
        "--phases",
        nargs="+",
        default=None,
        help="Yaml phase ids (phase1, phase4) or integers (4 → phase4). Default: all in yaml order.",
    )
    parser.add_argument(
        "--lld-dir",
        type=Path,
        default=None,
        help="Path to LLD directory (default: from config)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    phase_files, phase_names, phase_dir_names = _build_phase_maps(config)

    project_root = find_project_yaml(args.config).parent if args.config else find_project_yaml().parent
    lld_dir = args.lld_dir or (project_root / config["paths"]["lld"])
    output_dir = args.output_dir or (project_root / config["paths"]["work_items"])
    if args.phases:
        phases_to_process = [_normalize_phase_token(token) for token in args.phases]
    else:
        phases_to_process = list(phase_files.keys())

    emit_md = args.format in ("md", "both")
    emit_csv = args.format in ("csv", "both")

    all_csv_rows: list[dict[str, str]] = []
    total_items = 0

    for phase_id in phases_to_process:
        if phase_id not in phase_files:
            print(f"  WARNING: Phase {phase_id} not configured, skipping", file=sys.stderr)
            continue

        filepath = lld_dir / phase_files[phase_id]
        if not filepath.exists():
            print(f"  WARNING: {filepath} not found, skipping", file=sys.stderr)
            continue

        _phase_title, sections = parse_phase_file(filepath)
        print(f"  Phase {phase_id}: {len(sections)} sections parsed from {phase_files[phase_id]}")

        if emit_md:
            phase_dir = output_dir / phase_dir_names[phase_id]
            phase_dir.mkdir(parents=True, exist_ok=True)

            for sec in sections:
                safe_title = re.sub(r"[^\w\-]", "_", sec.title).strip("_")
                filename = f"{sec.lld_id}_{safe_title}.md"
                md_content = render_work_item_md(sec, phase_id, phase_dir_names, phase_names)
                (phase_dir / filename).write_text(md_content, encoding="utf-8")

        if emit_csv:
            for sec in sections:
                all_csv_rows.append(render_csv_row(sec, phase_id, phase_dir_names, phase_names))

        total_items += len(sections)

    if emit_csv and all_csv_rows:
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / "summary.csv"
        fieldnames = [
            "Summary",
            "Description",
            "Component",
            "Epic Link",
            "Labels",
            "Acceptance Criteria",
            "Definition of Done",
            "Tier Scope",
            "Blocked By",
        ]
        with open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_csv_rows)
        print(f"  CSV: {csv_path} ({len(all_csv_rows)} rows)")

    print(f"\n  Total work items exported: {total_items}")


if __name__ == "__main__":
    main()
