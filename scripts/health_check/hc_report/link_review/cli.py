"""Host CLI for the KB documentation link-review report."""
from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from hc_report.kb_loader import KBEntry, KnowledgeBase, load_kb
from hc_report.link_review.docs_index import build_docs_index
from hc_report.link_review.finalize import suppress_unchanged_suggestions
from hc_report.link_review.http_check import (
    PageStatusChecker,
    apply_page_checks,
    build_page_status_checker,
    url_without_fragment,
)
from hc_report.link_review.match import suggest_documentation_link
from hc_report.link_review.models import HeadingRecord, LinkSuggestion
from hc_report.link_review.report import write_review_report

TOML_BY_PREFIX = {
    "7.1": "7_1_base_platform.toml",
    "7.2": "7_2_topology.toml",
    "7.3": "7_3_components.toml",
    "7.4": "7_4_layered.toml",
    "7.5": "7_5_cluster_health.toml",
    "7.6": "7_6_day2.toml",
    "7.7": "7_7_security.toml",
    "7.8": "7_8_metrics.toml",
    "7.9": "7_9_hardware.toml",
}

_DEFAULT_KB_DIR = Path(__file__).resolve().parent.parent / "kb"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Suggest precise documentation URLs for health-check KB links."
    )
    parser.add_argument("--kb-dir", type=Path, default=_DEFAULT_KB_DIR)
    parser.add_argument("--docs-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--validate-http",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="GET each unique suggested page URL (fragment stripped). Default: on.",
    )
    return parser


def run_link_review(
    kb_dir: Path,
    docs_root: Path,
    output_directory: Path,
    *,
    validate_http: bool = False,
    check_page_status: PageStatusChecker | None = None,
) -> int:
    if not docs_root.is_dir():
        print(f"docs root not found: {docs_root}", file=sys.stderr)
        return 1
    knowledge_base = load_kb(kb_dir)
    docs_index = build_docs_index(docs_root)
    heading_cache: dict[Path, list[HeadingRecord]] = {}
    suggestions = _suggestions_from_kb(knowledge_base, docs_index, heading_cache)
    if validate_http:
        checker = check_page_status or build_page_status_checker()
        unique_pages = {
            url_without_fragment(item.suggested_url)
            for item in suggestions
            if item.suggested_url and item.verdict != "EXTERNAL-UNCHECKED"
        }
        print(f"HTTP-checking {len(unique_pages)} unique suggested page URLs", file=sys.stderr)
        suggestions = apply_page_checks(suggestions, checker)
    suggestions = suppress_unchanged_suggestions(suggestions)
    write_review_report(
        suggestions,
        output_directory,
        docs_root=docs_root,
        docs_index_size=len(docs_index),
    )
    return 0


def main() -> None:
    parser = build_parser()
    arguments = parser.parse_args()
    sys.exit(
        run_link_review(
            kb_dir=arguments.kb_dir,
            docs_root=arguments.docs_root,
            output_directory=arguments.output_dir,
            validate_http=arguments.validate_http,
        )
    )


def _suggestions_from_kb(
    knowledge_base: KnowledgeBase,
    docs_index: dict,
    heading_cache: dict[Path, list[HeadingRecord]],
) -> list[LinkSuggestion]:
    suggestions = []
    for entry in knowledge_base.entries.values():
        suggestions.extend(
            _suggestions_for_entry(entry, docs_index, heading_cache)
        )
    for _, entry in knowledge_base.pattern_entries:
        suggestions.extend(
            _suggestions_for_entry(entry, docs_index, heading_cache)
        )
    return suggestions


def _suggestions_for_entry(
    entry: KBEntry,
    docs_index: dict,
    heading_cache: dict[Path, list[HeadingRecord]],
):
    toml_file = _toml_file_for_check(entry.check_id)
    suggestions = []
    for version_key, current_url in entry.links.items():
        suggestion = suggest_documentation_link(
            entry_title=entry.title,
            check_id=entry.check_id,
            description=entry.description,
            version_key=version_key,
            current_url=current_url,
            docs_index=docs_index,
            heading_cache=heading_cache,
        )
        suggestions.append(replace(suggestion, toml_file=toml_file))
    return suggestions


def _toml_file_for_check(check_id: str) -> str:
    parts = check_id.split(".")
    if len(parts) < 2:
        return ""
    prefix = f"{parts[0]}.{parts[1]}"
    return TOML_BY_PREFIX.get(prefix, "")
