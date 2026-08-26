#!/usr/bin/env python3
"""Map Health Check report markdown to unique HTML/PDF export paths."""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
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


def _export_filename(markdown_name: str, extension: str) -> str:
    suffix = "." + extension.lstrip(".")
    stem = markdown_name
    if stem.endswith(".md"):
        stem = stem[: -len(".md")]
    if not stem.endswith(suffix):
        stem += suffix
    return stem


def resolve_export_path(
    source_markdown: Path,
    report_directory: Path,
    export_root: Path,
    extension: str,
) -> Path:
    relative = source_markdown.resolve().relative_to(report_directory.resolve())
    return (
        export_root / relative.parent / _export_filename(relative.name, extension)
    ).resolve()


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


EXIT_OVERWRITE_CONSENT_REQUIRED = 4
WARNING_RULE_WIDTH = 72
WARNING_TITLE_PRUNED_SIBLING = "PRUNED SIBLING IGNORED"
WARNING_TITLE_OUTSIDE_TREE = "SOURCE OUTSIDE REPORT TREE"


class NamedSourceError(Exception):
    """Raised when a named --source path cannot be exported."""


@dataclass
class NamedSourcePlan:
    source_markdown: Path
    destination: Path
    warning_entries: list[tuple[str, list[str]]]
    needs_overwrite_consent: bool


def emit_unmissable_warning(
    title: str, body_lines: list[str], stream: object | None = None
) -> None:
    output = sys.stderr if stream is None else stream
    rule = "=" * WARNING_RULE_WIDTH
    print(rule, file=output)
    print(f"WARNING: {title}", file=output)
    print(rule, file=output)
    for line in body_lines:
        print(line, file=output)
    print(rule, file=output)


def is_inside_report_tree(
    source_markdown: Path, report_directory: Path
) -> bool:
    return source_markdown.resolve().is_relative_to(report_directory.resolve())


def pruned_sibling_path(source_markdown: Path) -> Path:
    if source_markdown.name.endswith("_pruned.md"):
        return source_markdown
    return source_markdown.with_name(source_markdown.stem + "_pruned.md")


def validate_named_source(
    source_markdown: Path, report_directory: Path
) -> str | None:
    resolved = source_markdown.resolve()
    if resolved.is_dir():
        return (
            "Error: REPORT must be a markdown file, not a directory: "
            f"{source_markdown}"
        )
    if not resolved.is_file():
        return f"Error: report not found: {source_markdown}"
    if resolved.suffix != ".md":
        return f"Error: source is not markdown: {source_markdown}"
    if _is_sidecar_markdown(resolved.name):
        return (
            "Error: sidecar markdown cannot be exported: "
            f"{source_markdown}"
        )
    if is_inside_report_tree(resolved, report_directory):
        relative = resolved.relative_to(report_directory.resolve())
        if relative.parts[0] in SKIP_DIRECTORY_NAMES:
            return (
                "Error: source is under HTML/ or PDFs/: "
                f"{source_markdown}"
            )
    return None


def resolve_named_export_path(
    source_markdown: Path,
    report_directory: Path,
    export_root: Path,
    extension: str,
) -> Path:
    resolved = source_markdown.resolve()
    if is_inside_report_tree(resolved, report_directory):
        return resolve_export_path(
            resolved, report_directory, export_root, extension
        )
    return (export_root / _export_filename(resolved.name, extension)).resolve()


def destination_needs_overwrite_consent(
    source_markdown: Path,
    destination: Path,
    report_directory: Path,
) -> bool:
    if not destination.exists():
        return False
    if is_inside_report_tree(source_markdown, report_directory):
        return False
    return True


def prepare_named_source_export(
    source_markdown: Path,
    report_directory: Path,
    export_root: Path,
    extension: str,
) -> NamedSourcePlan:
    error_message = validate_named_source(source_markdown, report_directory)
    if error_message is not None:
        raise NamedSourceError(error_message)
    resolved_source = source_markdown.resolve()
    destination = resolve_named_export_path(
        resolved_source, report_directory, export_root, extension
    )
    warning_entries: list[tuple[str, list[str]]] = []
    sibling = pruned_sibling_path(resolved_source)
    if (
        not resolved_source.name.endswith("_pruned.md")
        and sibling.is_file()
    ):
        warning_entries.append(
            (
                WARNING_TITLE_PRUNED_SIBLING,
                [
                    "You asked to export:",
                    f"  {resolved_source}",
                    "A delivery file exists next to it:",
                    f"  {sibling.resolve()}",
                    "Export will use the file you named, not the pruned sibling.",
                ],
            )
        )
    if not is_inside_report_tree(resolved_source, report_directory):
        warning_entries.append(
            (
                WARNING_TITLE_OUTSIDE_TREE,
                [
                    f"Source is outside the report tree: {resolved_source}",
                    f"Destination will be: {destination}",
                    "FORCE is not required because of location.",
                ],
            )
        )
    return NamedSourcePlan(
        source_markdown=resolved_source,
        destination=destination,
        warning_entries=warning_entries,
        needs_overwrite_consent=destination_needs_overwrite_consent(
            resolved_source, destination, report_directory
        ),
    )


def run_discover_export(
    report_directory: Path, export_root: Path, extension: str
) -> int:
    try:
        mapping = build_export_mapping(
            report_directory, export_root, extension
        )
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


def run_named_source_export(
    source_markdown: Path,
    report_directory: Path,
    export_root: Path,
    extension: str,
    allow_overwrite: bool,
) -> int:
    try:
        plan = prepare_named_source_export(
            source_markdown, report_directory, export_root, extension
        )
    except NamedSourceError as error:
        print(str(error), file=sys.stderr)
        return 1
    for title, body_lines in plan.warning_entries:
        emit_unmissable_warning(title, body_lines)
    print(f"{plan.source_markdown}\t{plan.destination}")
    if plan.needs_overwrite_consent and not allow_overwrite:
        return EXIT_OVERWRITE_CONSENT_REQUIRED
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="hc_export_paths.py",
        description="Map Health Check report markdown to HTML/PDF paths.",
    )
    parser.add_argument("report_directory")
    parser.add_argument("export_root")
    parser.add_argument("extension")
    parser.add_argument("--source", default=None)
    parser.add_argument(
        "--allow-overwrite", action="store_true", default=False
    )
    parsed = parser.parse_args(arguments)
    report_directory = Path(parsed.report_directory)
    export_root = Path(parsed.export_root)
    if parsed.source is not None:
        return run_named_source_export(
            Path(parsed.source),
            report_directory,
            export_root,
            parsed.extension,
            parsed.allow_overwrite,
        )
    return run_discover_export(
        report_directory, export_root, parsed.extension
    )


if __name__ == "__main__":
    raise SystemExit(main())
