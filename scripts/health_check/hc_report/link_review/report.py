"""Write the SME-facing KB link-review CSV and markdown reports."""
from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from hc_report.link_review.finalize import url_change_requested
from hc_report.link_review.models import LinkSuggestion

CSV_COLUMNS = (
    "check_id",
    "toml_file",
    "title",
    "version_key",
    "verdict",
    "confidence",
    "current_url",
    "suggested_url",
    "evidence",
)

_EVIDENCE_MARKDOWN_LIMIT = 120
_ACTION_VERDICTS = frozenset({"REPLACE", "HTTP-404", "HTTP-FAILED", "BLOCKED-DOCS"})
_TABLE_HEADER = (
    "| check_id | toml_file | title | version_key | verdict | confidence | "
    "current_url | suggested_url | evidence |"
)


def _reportable_suggestion(suggestion: LinkSuggestion) -> bool:
    return url_change_requested(suggestion)


def write_review_report(
    suggestions: list[LinkSuggestion],
    output_directory: Path,
    *,
    docs_root: Path,
    docs_index_size: int,
) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    ordered = sorted(suggestions, key=_suggestion_sort_key)
    _write_csv(ordered, output_directory / "kb_link_review.csv")
    _write_markdown(
        ordered,
        output_directory / "kb_link_review.md",
        docs_root=docs_root,
        docs_index_size=docs_index_size,
    )


def _suggestion_sort_key(suggestion: LinkSuggestion) -> tuple[str, str]:
    return suggestion.check_id, suggestion.version_key


def _write_csv(suggestions: list[LinkSuggestion], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(CSV_COLUMNS))
        writer.writeheader()
        for suggestion in suggestions:
            writer.writerow(
                {
                    "check_id": suggestion.check_id,
                    "toml_file": suggestion.toml_file,
                    "title": suggestion.title,
                    "version_key": suggestion.version_key,
                    "verdict": suggestion.verdict,
                    "confidence": suggestion.confidence,
                    "current_url": suggestion.current_url,
                    "suggested_url": suggestion.suggested_url,
                    "evidence": suggestion.evidence,
                }
            )


def _write_markdown(
    suggestions: list[LinkSuggestion],
    path: Path,
    *,
    docs_root: Path,
    docs_index_size: int,
) -> None:
    counts = Counter(suggestion.verdict for suggestion in suggestions)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines: list[str] = [
        "# KB documentation link review",
        "",
        f"- docs_root: `{docs_root}`",
        f"- index_size: {docs_index_size}",
        f"- generated_utc: {generated}",
        f"- suggestion_rows: {len(suggestions)}",
        "",
        "## Verdict counts",
        "",
        "| verdict | count |",
        "|---|---|",
    ]
    for verdict in (
        "KEEP",
        "REPLACE",
        "BOOK-HINT",
        "PROXY-4.19/4.21",
        "BLOCKED-DOCS",
        "EXTERNAL-UNCHECKED",
        "HTTP-404",
        "HTTP-FAILED",
    ):
        lines.append(f"| {verdict} | {counts.get(verdict, 0)} |")
    lines.extend(
        [
            "",
            "## Recommended changes (REPLACE, HTTP-404, HTTP-FAILED, BLOCKED-DOCS)",
            "",
            _TABLE_HEADER,
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for suggestion in suggestions:
        if suggestion.verdict not in _ACTION_VERDICTS:
            continue
        if not _reportable_suggestion(suggestion):
            continue
        lines.append(_markdown_row(suggestion))
    lines.extend(
        [
            "",
            "## Informational (no TOML change suggested)",
            "",
            _TABLE_HEADER,
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for suggestion in suggestions:
        if suggestion.verdict in _ACTION_VERDICTS or suggestion.verdict == "KEEP":
            continue
        if not _reportable_suggestion(suggestion):
            continue
        lines.append(_markdown_row(suggestion))
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _markdown_row(suggestion: LinkSuggestion) -> str:
    cells = [
        _markdown_cell(suggestion.check_id),
        _markdown_cell(suggestion.toml_file),
        _markdown_cell(suggestion.title),
        _markdown_cell(suggestion.version_key),
        _markdown_cell(suggestion.verdict),
        _markdown_cell(suggestion.confidence),
        _markdown_cell(suggestion.current_url),
        _markdown_cell(suggestion.suggested_url),
        _markdown_cell(suggestion.evidence, limit=_EVIDENCE_MARKDOWN_LIMIT),
    ]
    return "| " + " | ".join(cells) + " |"


def _markdown_cell(text: str, limit: int = 0) -> str:
    cleaned = text.replace("|", "\\|").replace("\n", " ")
    if limit and len(cleaned) > limit:
        return cleaned[:limit]
    return cleaned
