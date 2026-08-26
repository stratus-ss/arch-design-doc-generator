#!/usr/bin/env python3
"""Map Health Check report markdown to unique HTML/PDF export paths."""
from __future__ import annotations

import sys
from pathlib import Path

SKIP_DIRECTORY_NAMES: frozenset[str] = frozenset({"HTML", "PDFs"})
_SIDECAR_SUFFIXES: tuple[str, ...] = (
    "_exec_sections.md",
    "_exec_sections.prompt.md",
    "_summary_conclusion.md",
    "_summary_conclusion.prompt.md",
)
_WRITTEN_REPORT_PREFIXES: tuple[str, ...] = (
    "Report written to: ",
    "Pruned report written to: ",
)


def _is_sidecar_markdown(filename: str) -> bool:
    return any(filename.endswith(suffix) for suffix in _SIDECAR_SUFFIXES)


def _prefer_pruned_markdown(paths: list[Path]) -> list[Path]:
    path_set = set(paths)
    preferred: list[Path] = []
    for path in paths:
        if path.name.endswith("_pruned.md"):
            preferred.append(path)
            continue
        pruned_peer = path.with_name(path.stem + "_pruned.md")
        if pruned_peer in path_set:
            continue
        preferred.append(path)
    return preferred


class ExportPathCollision(Exception):
    """Raised when two markdown sources resolve to the same export destination."""

    def __init__(
        self, destination: Path, first_source: Path, second_source: Path
    ) -> None:
        self.destination = destination
        self.first_source = first_source
        self.second_source = second_source
        message = (
            "Export path collision:\n"
            f"  destination: {destination}\n"
            f"  first source: {first_source}\n"
            f"  second source: {second_source}"
        )
        super().__init__(message)


def discover_report_markdown(report_directory: Path) -> list[Path]:
    report_root = report_directory.resolve()
    candidates = list(report_directory.glob("*.md")) + list(
        report_directory.glob("*/*.md")
    )
    discovered: list[Path] = []
    for candidate in candidates:
        relative = candidate.resolve().relative_to(report_root)
        if relative.parts[0] in SKIP_DIRECTORY_NAMES:
            continue
        if _is_sidecar_markdown(candidate.name):
            continue
        discovered.append(candidate.resolve())
    return sorted(_prefer_pruned_markdown(discovered), key=str)


def draft_targets_from_generate_log(log_text: str) -> list[Path]:
    """Return markdown paths this generate_report run wrote.

    Parses stdout lines from hc_report/cli.py. Does not scan the report
    directory, so prior-run markdown is not drafted.
    """
    written: list[Path] = []
    for line in log_text.splitlines():
        for prefix in _WRITTEN_REPORT_PREFIXES:
            if line.startswith(prefix):
                written.append(Path(line[len(prefix):].strip()))
                break
    return sorted(_prefer_pruned_markdown(written), key=str)


def resolve_export_path(
    source_markdown: Path,
    report_directory: Path,
    export_root: Path,
    extension: str,
) -> Path:
    relative = source_markdown.resolve().relative_to(report_directory.resolve())
    suffix = "." + extension.lstrip(".")
    base_name = relative.name
    if base_name.endswith(".md"):
        base_name = base_name[: -len(".md")]
    if not base_name.endswith(suffix):
        base_name += suffix
    return (export_root / relative.parent / base_name).resolve()


def build_export_mapping(
    report_directory: Path,
    export_root: Path,
    extension: str,
) -> list[tuple[Path, Path]]:
    mapping: list[tuple[Path, Path]] = []
    destinations: dict[Path, Path] = {}
    for source_markdown in discover_report_markdown(report_directory):
        destination = resolve_export_path(
            source_markdown, report_directory, export_root, extension
        )
        prior_source = destinations.get(destination)
        if prior_source is not None:
            raise ExportPathCollision(destination, prior_source, source_markdown)
        destinations[destination] = source_markdown
        mapping.append((source_markdown, destination))
    return mapping


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 3:
        print(
            "Usage: hc_export_paths.py <report_directory> <export_root> <extension>",
            file=sys.stderr,
        )
        return 1
    report_directory = Path(arguments[0])
    export_root = Path(arguments[1])
    extension = arguments[2]
    try:
        mapping = build_export_mapping(report_directory, export_root, extension)
    except ExportPathCollision as error:
        print(str(error), file=sys.stderr)
        return 1
    if not mapping:
        print(
            f"Error: no report markdown found in {report_directory}/",
            file=sys.stderr,
        )
        print("Run 'make hc-report' first.", file=sys.stderr)
        return 1
    for source_markdown, destination in mapping:
        print(f"{source_markdown}\t{destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
