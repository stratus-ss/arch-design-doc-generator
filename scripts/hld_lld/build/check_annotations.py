#!/usr/bin/env python3
"""Check mermaid blocks in HLD source files for drawio annotations.

Scans every source markdown file listed in project.yaml and reports,
for each mermaid block:

  ✓  annotation present and drawio PNG found
  !  no annotation — fuzzy matching will be attempted at build time
  ✗  annotation present but drawio PNG not found (build will warn/fallback)

Exit code:
  0  all annotated blocks resolve; unannotated blocks only produce warnings
  1  one or more annotations reference a missing drawio file
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from config import find_project_yaml, load_config

HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")
MD_LINK_RE = re.compile(r"\(([^)]+\.md)\)")
DRAWIO_ANNOTATION_RE = re.compile(r"<!--\s*drawio:\s*(.+?)\s*-->")

# Colours (disabled when stdout is not a tty)
_TTY = sys.stdout.isatty()
_GREEN = "\033[32m" if _TTY else ""
_YELLOW = "\033[33m" if _TTY else ""
_RED = "\033[31m" if _TTY else ""
_BOLD = "\033[1m" if _TTY else ""
_RESET = "\033[0m" if _TTY else ""


def _find_drawio_png(diagrams_root: Path, phase_tag: str, explicit_name: str) -> Path | None:
    """Resolve an annotated filename to an absolute path."""
    if not explicit_name.endswith(".drawio.png"):
        explicit_name += ".drawio.png"
    candidate = diagrams_root / phase_tag / explicit_name
    if candidate.exists():
        return candidate
    candidate = diagrams_root / explicit_name
    if candidate.exists():
        return candidate
    return None


def _phase_tag(basename: str) -> str:
    lower = basename.lower()
    for tag in ("phase1", "phase2", "phase3", "phase4", "combined"):
        if tag in lower:
            return tag
    return "misc"


def scan_file(source: Path, diagrams_root: Path) -> list[dict]:
    """Return one record per mermaid block found in src."""
    results = []
    phase_tag = _phase_tag(source.stem)
    last_heading = ""
    prev_nonblank = ""
    in_mermaid = False
    diagram_index = 0

    for line in source.read_text(encoding="utf-8").splitlines():
        match = HEADING_RE.match(line)
        if match:
            last_heading = match.group(1)

        if line == "```mermaid" and not in_mermaid:
            in_mermaid = True
            diagram_index += 1

            anno_match = DRAWIO_ANNOTATION_RE.match(prev_nonblank)
            if anno_match:
                explicit = anno_match.group(1).strip()
                resolved = _find_drawio_png(diagrams_root, phase_tag, explicit)
                status = "ok" if resolved else "missing"
            else:
                explicit = None
                resolved = None
                status = "unannotated"

            results.append(
                {
                    "file": source.name,
                    "heading": last_heading or f"(diagram {diagram_index})",
                    "annotation": explicit,
                    "resolved": resolved,
                    "status": status,
                }
            )
        elif in_mermaid and line == "```":
            in_mermaid = False

        if not in_mermaid and line.strip():
            prev_nonblank = line

    return results


def collect_source_files(config: dict, md_dir: Path) -> list[Path]:
    """Gather all unique HLD source files referenced via summary_map."""
    seen: set[str] = set()
    files: list[Path] = []
    hld_section = config.get("hld", {})
    summary_map = hld_section.get("summary_map", {})

    def _visit(relative_path: str) -> None:
        if not relative_path or relative_path in seen:
            return
        seen.add(relative_path)
        path = md_dir / relative_path
        if path.exists():
            files.append(path)
            for linked in MD_LINK_RE.findall(path.read_text(encoding="utf-8")):
                _visit(linked)

    for _, entry in sorted(summary_map.items()):
        _visit(entry.get("summary", ""))

    return files


def print_report(records: list[dict]) -> int:
    """Print a formatted table and return 1 if any annotations are broken."""
    counts = {"ok": 0, "unannotated": 0, "missing": 0}
    for record in records:
        counts[record["status"]] += 1

    col_file = max((len(record["file"]) for record in records), default=20)
    col_head = min(max((len(record["heading"]) for record in records), default=30), 50)
    col_anno = max((len(record["annotation"] or "(none)") for record in records), default=30)

    header = f"{'File':<{col_file}}  {'Heading':<{col_head}}  {'Annotation':<{col_anno}}  Status"
    print(f"\n{_BOLD}{header}{_RESET}")
    print("-" * len(header))

    for record in records:
        heading = record["heading"]
        if len(heading) > col_head:
            heading = heading[: col_head - 1] + "…"
        anno = record["annotation"] or "(none)"

        if record["status"] == "ok":
            symbol = f"{_GREEN}✓{_RESET}"
            status_text = f"{_GREEN}ok{_RESET}"
        elif record["status"] == "unannotated":
            symbol = f"{_YELLOW}!{_RESET}"
            status_text = f"{_YELLOW}unannotated{_RESET}"
        else:
            symbol = f"{_RED}✗{_RESET}"
            status_text = f"{_RED}file not found{_RESET}"

        print(f"{record['file']:<{col_file}}  {heading:<{col_head}}  {anno:<{col_anno}}  {symbol} {status_text}")

    print()
    print(
        f"Summary: {_GREEN}{counts['ok']} annotated{_RESET}  "
        f"{_YELLOW}{counts['unannotated']} unannotated{_RESET}  "
        f"{_RED}{counts['missing']} broken{_RESET}"
    )

    if counts["unannotated"]:
        print(
            f"\n{_YELLOW}Tip:{_RESET} Unannotated blocks fall back to fuzzy matching. "
            "Add <!-- drawio: FILENAME --> above the ```mermaid fence to pin the mapping."
        )
    if counts["missing"]:
        print(
            f"\n{_RED}Error:{_RESET} Broken annotations reference drawio files that don't exist. "
            "Check the filename or add the missing .drawio file to output/Diagrams/."
        )

    return 1 if counts["missing"] else 0


def main() -> int:
    project_root = find_project_yaml().parent
    config = load_config()
    md_dir = project_root / "output" / "HLD" / "markdown_files"
    diagrams_root = project_root / "output" / "Diagrams"

    sources = collect_source_files(config, md_dir)
    if not sources:
        print("No HLD source files found. Check hld.summary_map in project.yaml.")
        return 0

    all_records: list[dict] = []
    for source in sources:
        all_records.extend(scan_file(source, diagrams_root))

    if not all_records:
        print("No mermaid blocks found in HLD source files.")
        return 0

    return print_report(all_records)


if __name__ == "__main__":
    raise SystemExit(main())
