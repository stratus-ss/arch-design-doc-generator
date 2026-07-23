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
    python3 lld_to_workitems.py --expand-tiers            # per-tier work items
    python3 lld_to_workitems.py --phases 1 2              # specific phases only
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from config import load_config, find_project_yaml  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent

SECTION_HEADING_RE = re.compile(r"^## (LLD-(\d+):\s*(.+))$")
SUBSECTION_RE = re.compile(r"^### (.+)$")
ADR_TAG_RE = re.compile(r"\*\(ADR ([^)]+)\)\*")
CG_ROW_RE = re.compile(r"^\|\s*(CG-\S+)\s*\|(.+)")
AC_ROW_RE = re.compile(r"^\|\s*(AC-\S+)\s*\|(.+)")
DEP_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$")
TIER_HEADER_RE = re.compile(r"^\|.*DC.*\|.*Tier 2.*\|.*Tier 3 Site.*\|", re.IGNORECASE)


def _build_phase_maps(cfg: dict) -> tuple[dict[int, str], dict[int, str], dict[int, str]]:
    """Build phase file/name/dir maps from config."""
    phase_files = {}
    phase_names = {}
    phase_dir_names = {}
    for i, phase in enumerate(cfg["phases"], start=1):
        phase_files[i] = phase["lld_file"]
        phase_names[i] = f"Phase {i} — {phase['name']}"
        phase_dir_names[i] = phase["dir_name"]
    return phase_files, phase_names, phase_dir_names


@dataclass
class LLDSection:
    lld_id: str
    lld_num: int
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


def parse_phase_file(filepath: Path) -> tuple[str, list[LLDSection]]:
    text = filepath.read_text(encoding="utf-8")
    lines = text.split("\n")

    phase_title = ""
    for line in lines:
        if line.startswith("# "):
            phase_title = line.lstrip("# ").strip()
            break

    section_starts: list[tuple[int, re.Match]] = []
    for i, line in enumerate(lines):
        m = SECTION_HEADING_RE.match(line)
        if m:
            section_starts.append((i, m))

    sections: list[LLDSection] = []
    for idx, (start_line, match) in enumerate(section_starts):
        end_line = section_starts[idx + 1][0] if idx + 1 < len(section_starts) else len(lines)
        section_lines = lines[start_line:end_line]

        full_heading = match.group(1)
        lld_num = int(match.group(2))
        title = match.group(3).strip()
        lld_id = f"LLD-{lld_num:02d}"

        sec = LLDSection(
            lld_id=lld_id, lld_num=lld_num, title=title, full_heading=full_heading,
        )

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
            m = CG_ROW_RE.match(line)
            if m:
                cg_id = m.group(1).strip()
                cols = [c.strip() for c in m.group(2).split("|")]
                item = cols[0] if cols else ""
                sec.completion_gates.append(f"{cg_id}: {item}")

        dep_text = subsections.get("Dependencies", "")
        _parse_dependencies(sec, dep_text)

        impl_text = subsections.get("Implementation Procedure", "")
        sec.impl_full = impl_text.strip()

        for line in subsections.get("Acceptance Criteria", "").split("\n"):
            m = AC_ROW_RE.match(line)
            if m:
                ac_id = m.group(1).strip()
                cols = [c.strip() for c in m.group(2).split("|")]
                criterion = cols[0] if cols else ""
                sec.acceptance_criteria.append(f"{ac_id}: {criterion}")

        tv_text = subsections.get("Tier Variance", "")
        tv_lines = [l for l in tv_text.strip().split("\n") if l.strip()]
        if tv_lines and any(TIER_HEADER_RE.match(l) for l in tv_lines):
            sec.has_tier_variance = True
            sec.tier_scope = "DC, Tier 2, Tier 3 Site (variance exists)"
        else:
            sec.tier_scope = "DC, Tier 2, Tier 3 Site (no variance)"

        sections.append(sec)

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
        m = DEP_ROW_RE.match(stripped)
        if m:
            blocked_by = m.group(1).strip()
            reason = m.group(2).strip()
            if blocked_by and blocked_by != "Blocked By":
                sec.dependencies.append((blocked_by, reason))


def _split_subsections(section_lines: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    current_key = "_description"
    current_lines: list[str] = []

    for line in section_lines[1:]:
        m = SUBSECTION_RE.match(line)
        if m:
            result[current_key] = "\n".join(current_lines)
            current_key = m.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)

    result[current_key] = "\n".join(current_lines)
    return result


def render_work_item_md(sec: LLDSection, phase_num: int, phase_dir_names: dict, phase_names: dict) -> str:
    blocked_by_summary = ", ".join(b for b, _ in sec.dependencies) if sec.dependencies else "None"

    lines = [
        f"# [{phase_dir_names[phase_num].split('_')[0]}-{sec.lld_id}] {sec.title}",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Phase | {phase_names[phase_num]} |",
        f"| LLD Section | {sec.lld_id} |",
        f"| ADR | {sec.adr_refs or '—'} |",
        f"| Tier Scope | {sec.tier_scope} |",
        f"| Blocked By | {blocked_by_summary} |",
        "",
    ]

    if sec.description:
        lines += ["## Description", "", sec.description, ""]

    if sec.dependencies:
        lines += ["## Dependencies", "",
                   "| Blocked By | Reason |",
                   "|------------|--------|"]
        for blocked_by, reason in sec.dependencies:
            lines.append(f"| {blocked_by} | {reason} |")
        lines.append("")

    if sec.completion_gates:
        lines += ["## Definition of Done"]
        for cg in sec.completion_gates:
            lines.append(f"- [ ] {cg}")
        lines.append("")

    if sec.impl_full:
        lines += ["## Implementation Procedure", "", sec.impl_full, ""]

    if sec.acceptance_criteria:
        lines += ["## Acceptance Criteria"]
        for ac in sec.acceptance_criteria:
            lines.append(f"- [ ] {ac}")
        lines.append("")

    return "\n".join(lines)


def render_csv_row(sec: LLDSection, phase_num: int, phase_dir_names: dict, phase_names: dict) -> dict[str, str]:
    ac_text = "; ".join(sec.acceptance_criteria) if sec.acceptance_criteria else ""
    cg_text = "; ".join(sec.completion_gates) if sec.completion_gates else ""
    blocked_by = ", ".join(b for b, _ in sec.dependencies) if sec.dependencies else ""
    return {
        "Summary": f"[{phase_dir_names[phase_num].split('_')[0]}-{sec.lld_id}] {sec.title}",
        "Description": sec.description,
        "Component": sec.lld_id,
        "Epic Link": phase_names[phase_num],
        "Labels": sec.adr_refs,
        "Acceptance Criteria": ac_text,
        "Definition of Done": cg_text,
        "Tier Scope": sec.tier_scope,
        "Blocked By": blocked_by,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export LLD sections as work-item markdown files and/or Jira CSV."
    )
    parser.add_argument(
        "--config", type=Path, default=None,
        help="Path to project.yaml (default: auto-detect)",
    )
    parser.add_argument(
        "--format", choices=["md", "csv", "both"], default="md",
        help="Output format (default: md)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="Output directory (default: from config or Work_Items/)",
    )
    parser.add_argument(
        "--phases", type=int, nargs="+", default=None,
        help="Phase numbers to process (default: all)",
    )
    parser.add_argument(
        "--expand-tiers", action="store_true",
        help="Create separate work items per tier when variance exists",
    )
    parser.add_argument(
        "--lld-dir", type=Path, default=None,
        help="Path to LLD directory (default: from config)",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    phase_files, phase_names, phase_dir_names = _build_phase_maps(cfg)

    project_root = find_project_yaml(args.config).parent if args.config else find_project_yaml().parent
    lld_dir = args.lld_dir or (project_root / cfg["paths"]["lld"])
    output_dir = args.output_dir or (project_root / cfg["paths"]["work_items"])
    phases_to_process = args.phases or list(phase_files.keys())

    emit_md = args.format in ("md", "both")
    emit_csv = args.format in ("csv", "both")

    all_csv_rows: list[dict[str, str]] = []
    total_items = 0

    for phase_num in sorted(phases_to_process):
        if phase_num not in phase_files:
            print(f"  WARNING: Phase {phase_num} not configured, skipping", file=sys.stderr)
            continue

        filepath = lld_dir / phase_files[phase_num]
        if not filepath.exists():
            print(f"  WARNING: {filepath} not found, skipping", file=sys.stderr)
            continue

        phase_title, sections = parse_phase_file(filepath)
        print(f"  Phase {phase_num}: {len(sections)} sections parsed from {phase_files[phase_num]}")

        if emit_md:
            phase_dir = output_dir / phase_dir_names[phase_num]
            phase_dir.mkdir(parents=True, exist_ok=True)

            for sec in sections:
                safe_title = re.sub(r"[^\w\-]", "_", sec.title).strip("_")
                filename = f"{sec.lld_id}_{safe_title}.md"
                md_content = render_work_item_md(sec, phase_num, phase_dir_names, phase_names)
                (phase_dir / filename).write_text(md_content, encoding="utf-8")

        if emit_csv:
            for sec in sections:
                all_csv_rows.append(render_csv_row(sec, phase_num, phase_dir_names, phase_names))

        total_items += len(sections)

    if emit_csv and all_csv_rows:
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / "summary.csv"
        fieldnames = [
            "Summary", "Description", "Component", "Epic Link",
            "Labels", "Acceptance Criteria", "Definition of Done",
            "Tier Scope", "Blocked By",
        ]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_csv_rows)
        print(f"  CSV: {csv_path} ({len(all_csv_rows)} rows)")

    print(f"\n  Total work items exported: {total_items}")


if __name__ == "__main__":
    main()
