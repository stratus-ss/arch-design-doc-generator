#!/usr/bin/env python3
"""
Pre-process pandoc HTML before WeasyPrint:
  1. Replace emoji status indicators with CSS-styled <span> badges
     (emoji require color-emoji fonts which are not in the container)
  2. Inject PDF-specific CSS fixups (table column widths, badge styles)

Usage:
    python3 pdf_preprocess.py input.html output.html
"""
import sys
from pathlib import Path

from html_utils import (
    NARRATIVE_PARAGRAPH_CSS,
    demote_priority_leak_headings,
    inject_colgroups,
    wrap_narrative_chapters,
)

# ── Emoji → badge mappings ────────────────────────────────────────────────────

_EMOJI_BADGES = [
    # (emoji_char, css_class, display_text)
    ("🟢", "badge-pass",    "PASS"),
    ("🔴", "badge-fail",    "FAIL"),
    ("🟡", "badge-warn",    "WARNING"),
    ("🔵", "badge-info",    "INFO"),
    ("⚪", "badge-na",      "N/A"),
    ("⚫", "badge-none",    "NONE"),
    ("⏭", "badge-skip",    "SKIPPED"),
    # Also handle the text forms that may appear alongside emoji
    ("🟢 PASS",    "badge-pass",    "PASS"),
    ("🔴 FAIL",    "badge-fail",    "FAIL"),
    ("🟡 WARNING", "badge-warn",    "WARNING"),
    ("🟡 LIMITATION", "badge-warn", "LIMITATION"),
    ("🔵 INFO",    "badge-info",    "INFO"),
    ("⚪ NOT APPLICABLE", "badge-na", "NOT APPLICABLE"),
    ("⚪ SKIPPED", "badge-skip",    "SKIPPED"),
    ("⚪ EXCEPTION", "badge-na",    "EXCEPTION"),
    ("⚫ NONE",    "badge-none",    "NONE"),
    ("⏭ SKIPPED", "badge-skip",    "SKIPPED"),
]

_BADGE_CSS = """
<style id="pdf-badges">
/* ── Status badges (replaces emoji for PDF rendering) ─────────────────── */
.badge-pass, .badge-fail, .badge-warn, .badge-info, .badge-na, .badge-skip, .badge-none {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 3px;
  font-size: 8pt;
  font-weight: 700;
  letter-spacing: 0.03em;
  white-space: nowrap;
}
.badge-pass { background: #f2faf1; color: #166534; border: 1px solid #d9e9d3; }
.badge-fail { background: #fae9e7; color: #991b1b; border: 1px solid #f4cccc; }
.badge-warn { background: #fdf6e7; color: #854d0e; border: 1px solid #fbe4cc; }
.badge-info { background: #f1f9f9; color: #1a5276; border: 1px solid #cfe2f2; }
.badge-na   { background: #f5f5f5; color: #475569; border: 1px solid #d9d9d9; }
.badge-skip { background: #f5f5f5; color: #475569; border: 1px solid #d9d9d9; }
.badge-none { background: #efefef; color: #333333; border: 1px solid #bfbfbf; }

/* ── Uniform table column widths ─────────────────────────────────────── */
/* colgroup elements are injected per-table by pdf_preprocess.py        */
table {
  table-layout: fixed;
  width: 100%;
}
td, th { overflow-wrap: break-word; word-break: break-word; }

/* Cover metadata: keep labels on one line (overrides global word-break) */
div.cover-meta table { width: 70%; table-layout: fixed; }
div.cover-meta th, div.cover-meta td {
  overflow-wrap: normal;
  word-break: normal;
}
div.cover-meta td:first-child { white-space: nowrap; width: 42%; }
div.cover-meta td:last-child {
  overflow-wrap: break-word;
  word-break: break-word;
}
""" + NARRATIVE_PARAGRAPH_CSS + """
</style>
"""


def replace_emoji(html: str) -> str:
    """Replace emoji+text status indicators with <span> badges.
    Process longest matches first to avoid partial replacements.
    """
    # Sort by descending length so "🟢 PASS" is matched before bare "🟢"
    for emoji_text, css_class, label in sorted(_EMOJI_BADGES, key=lambda badge: -len(badge[0])):
        span = f'<span class="{css_class}">{label}</span>'
        html = html.replace(emoji_text, span)
    return html


def inject_css(html: str) -> str:
    """Inject badge + table-layout CSS before </head>."""
    if "</head>" in html:
        return html.replace("</head>", _BADGE_CSS + "\n</head>", 1)
    # No <head>: prepend
    return _BADGE_CSS + html


def process(source_path: Path, destination_path: Path) -> None:
    html = source_path.read_text(encoding="utf-8")
    html = replace_emoji(html)
    html = inject_colgroups(html)
    html = demote_priority_leak_headings(html)
    html = wrap_narrative_chapters(html)
    html = inject_css(html)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} input.html output.html", file=sys.stderr)
        sys.exit(1)
    process(Path(sys.argv[1]), Path(sys.argv[2]))
