"""Collapse no-op suggestions so the SME report only shows real URL changes."""
from __future__ import annotations

from dataclasses import replace

from hc_report.link_review.models import LinkSuggestion

_ACTION_VERDICTS = frozenset({"REPLACE", "HTTP-404", "HTTP-FAILED", "BLOCKED-DOCS"})


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
