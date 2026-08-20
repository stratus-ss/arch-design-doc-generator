"""KB link-review helpers: collapse no-ops, then apply accepted REPLACE rows."""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

from hc_report.link_review.models import LinkSuggestion

_ACTION_VERDICTS = frozenset({"REPLACE", "HTTP-404", "HTTP-FAILED", "BLOCKED-DOCS"})
APPLYABLE_VERDICT = "REPLACE"
HTTP_OK_MARK = "HTTP 200"
_DEFAULT_KB_DIRECTORY = Path(__file__).resolve().parent.parent / "kb"


def url_change_requested(suggestion: LinkSuggestion) -> bool:
    if suggestion.verdict in _ACTION_VERDICTS:
        return True
    if not suggestion.suggested_url:
        return False
    return suggestion.current_url != suggestion.suggested_url


def suppress_unchanged_suggestions(
    suggestions: list[LinkSuggestion],
) -> list[LinkSuggestion]:
    finalized: list[LinkSuggestion] = []
    for suggestion in suggestions:
        if suggestion.suggested_url and suggestion.current_url == suggestion.suggested_url:
            finalized.append(replace(suggestion, verdict="KEEP"))
            continue
        finalized.append(suggestion)
    return finalized


def row_is_applyable(row: dict[str, str]) -> bool:
    verdict = (row.get("verdict") or "").strip()
    suggested_url = (row.get("suggested_url") or "").strip()
    evidence = row.get("evidence") or ""
    return (
        verdict == APPLYABLE_VERDICT
        and bool(suggested_url)
        and HTTP_OK_MARK in evidence
    )


def links_table_for_check(toml_text: str, check_id: str) -> tuple[int, int]:
    check_marker = f'check_id = "{check_id}"'
    check_index = toml_text.find(check_marker)
    if check_index < 0:
        raise ValueError(f"check_id not found: {check_id}")
    table_start = toml_text.find("[checks.links]", check_index)
    if table_start < 0:
        raise ValueError(f"no [checks.links] table for {check_id}")
    next_check = toml_text.find("[[checks]]", table_start)
    table_end = len(toml_text) if next_check < 0 else next_check
    return table_start, table_end


def replace_version_link(
    table_text: str,
    version_key: str,
    current_url: str,
    suggested_url: str,
) -> str:
    if version_key == "default":
        prefix = 'default = "'
    else:
        prefix = f'"{version_key}" = "'
    prefix_index = table_text.find(prefix)
    if prefix_index < 0:
        raise ValueError(f"version key not found: {version_key}")
    url_start = prefix_index + len(prefix)
    url_end = table_text.find('"', url_start)
    if url_end < 0:
        raise ValueError(f"unterminated URL for version key {version_key}")
    found_url = table_text[url_start:url_end]
    if found_url != current_url:
        raise ValueError(
            f"current_url mismatch: csv has {current_url!r}, toml has {found_url!r}"
        )
    return table_text[:url_start] + suggested_url + table_text[url_end:]


def apply_replace_rows_from_csv(csv_path: Path, kb_directory: Path) -> int:
    if not csv_path.is_file():
        print(f"ERROR: csv not found: {csv_path}", file=sys.stderr)
        return 1
    with csv_path.open(encoding="utf-8", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))
    skipped = 0
    rows_by_file: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row_is_applyable(row):
            rows_by_file[row.get("toml_file") or ""].append(row)
        else:
            skipped += 1
    applied = 0
    errors = 0
    for toml_file, file_rows in rows_by_file.items():
        file_applied, file_errors = _apply_rows_to_toml(
            kb_directory / toml_file, file_rows
        )
        applied += file_applied
        errors += file_errors
    print(f"applied={applied} skipped={skipped} errors={errors}")
    return 1 if errors else 0


def apply_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply REPLACE rows from kb_link_review.csv into KB TOML [checks.links]."
    )
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--kb-dir", type=Path, default=_DEFAULT_KB_DIRECTORY)
    arguments = parser.parse_args(argv)
    return apply_replace_rows_from_csv(arguments.csv, arguments.kb_dir)


def _apply_rows_to_toml(
    toml_path: Path, file_rows: list[dict[str, str]]
) -> tuple[int, int]:
    if not toml_path.is_file():
        for row in file_rows:
            _print_row_error(row, f"toml not found: {toml_path}")
        return 0, len(file_rows)
    original_text = toml_path.read_text(encoding="utf-8")
    working_text = original_text
    error_count = 0
    for row in file_rows:
        try:
            table_start, table_end = links_table_for_check(
                working_text, row["check_id"]
            )
            new_table = replace_version_link(
                working_text[table_start:table_end],
                row["version_key"],
                row["current_url"],
                row["suggested_url"],
            )
            working_text = (
                working_text[:table_start] + new_table + working_text[table_end:]
            )
        except (KeyError, ValueError) as error:
            error_count += 1
            _print_row_error(row, str(error))
    if error_count:
        return 0, error_count
    if working_text != original_text:
        toml_path.write_text(working_text, encoding="utf-8")
    return len(file_rows), 0


def _print_row_error(row: dict[str, str], message: str) -> None:
    check_id = row.get("check_id") or "?"
    version_key = row.get("version_key") or "?"
    print(f"ERROR: {check_id} {version_key}: {message}", file=sys.stderr)
