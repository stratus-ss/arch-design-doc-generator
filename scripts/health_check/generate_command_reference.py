#!/usr/bin/env python3
"""Generate a markdown reference of HC collection commands.

Parses `scripts/health_check/collect/[0-9][0-9]_*.sh` and extracts
`hc_capture_json` / `hc_capture_text` calls into a report-friendly table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SCRIPT_GLOB = "[0-9][0-9]_*.sh"
HEADER_RE = re.compile(r"^#\s*HC-\d+:\s*(.*?)\s+—\s+Chapter\s+([0-9.]+)\s*$")
CAPTURE_RE = re.compile(r'^hc_capture_(json|text)\s+"\$CATEGORY"\s+"([^"]+)"\s+(.+)$')
TRAILING_TRUE_RE = re.compile(r"\s*\|\|\s*true\s*$")


@dataclass
class CaptureCommand:
    check_name: str
    command: str
    section: str


@dataclass
class ScriptEntry:
    script_name: str
    title: str
    section: str
    commands: list[CaptureCommand]


def _escape_md_inline(text: str) -> str:
    return text.replace("`", r"\`").replace("|", r"\|")


def _iter_logical_lines(text: str) -> list[str]:
    logical: list[str] = []
    current = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if current:
            current = f"{current} {line.lstrip()}"
        else:
            current = line

        if current.endswith("\\"):
            current = current[:-1].rstrip()
            continue

        logical.append(current.strip())
        current = ""

    if current:
        logical.append(current.strip())
    return logical


def _parse_script(script_path: Path) -> ScriptEntry:
    lines = script_path.read_text(encoding="utf-8").splitlines()
    title = script_path.stem.replace("_", " ").title()
    section = "unknown"
    if len(lines) >= 2:
        header_match = HEADER_RE.match(lines[1].strip())
        if header_match:
            title = header_match.group(1).strip()
            section = header_match.group(2).strip()

    captures: list[CaptureCommand] = []
    for line in _iter_logical_lines("\n".join(lines)):
        match = CAPTURE_RE.match(line)
        if not match:
            continue
        capture_type, check_name, command_args = match.groups()
        command_args = TRAILING_TRUE_RE.sub("", command_args.strip())
        if capture_type == "json":
            command = f"oc {command_args} -o json"
        else:
            command = command_args
        captures.append(
            CaptureCommand(check_name=check_name, command=command, section=section)
        )

    return ScriptEntry(
        script_name=script_path.name,
        title=title,
        section=section,
        commands=captures,
    )


def generate_markdown(repo_root: Path) -> str:
    collect_dir = repo_root / "scripts" / "health_check" / "collect"
    scripts = sorted(collect_dir.glob(SCRIPT_GLOB))
    entries = [_parse_script(path) for path in scripts]

    output: list[str] = [
        "# Health Check Command Reference",
        "",
        "Generated from `scripts/health_check/collect/[0-9][0-9]_*.sh`.",
        "",
    ]

    for entry in entries:
        output.append(
            f"## {entry.script_name} — Chapter {entry.section}: {entry.title}"
        )
        output.append("")
        output.append("| Check Name | Command | Report Section |")
        output.append("|------------|---------|----------------|")

        if not entry.commands:
            output.append("| _(none found)_ | _(none found)_ | " + entry.section + " |")
        else:
            for capture in entry.commands:
                output.append(
                    f"| {capture.check_name} | `{_escape_md_inline(capture.command)}` | {capture.section} |"
                )
        output.append("")

    return "\n".join(output).rstrip() + "\n"


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    print(generate_markdown(repo_root), end="")


if __name__ == "__main__":
    main()
