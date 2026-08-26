"""
Shared HTML post-processing utilities for HC report generation.
Used by both pdf_preprocess.py and html_collapsible.py.
"""
import re

# Column width profiles keyed by number of columns
_COL_WIDTHS = {
    2: ["18%", "82%"],
    3: ["20%", "40%", "40%"],
    4: ["18%", "27%", "27%", "28%"],
    5: ["18%", "20.5%", "20.5%", "20.5%", "20.5%"],
    6: ["18%", "16.4%", "16.4%", "16.4%", "16.4%", "16.4%"],
}

# Cover-meta is a label/value table; the default 18%/82% 2-col profile
# forces mid-word wrapping on labels like "Customer" and "Data Capture Date".
_COVER_META_COL_WIDTHS = {
    2: ["42%", "58%"],
}


def _count_cols(first_row_html: str) -> int:
    return len(re.findall(r'<t[hd][\s>]', first_row_html, re.IGNORECASE))


def _make_colgroup(column_count: int, widths_map: dict[int, list[str]] | None = None) -> str:
    widths = (widths_map or _COL_WIDTHS).get(column_count)
    if not widths:
        return ""
    cols = "".join(f'<col style="width:{width}">' for width in widths)
    return f"<colgroup>{cols}</colgroup>\n"


def _inject_colgroups_in_fragment(html: str, widths_map: dict[int, list[str]] | None = None) -> str:
    """Replace or inject <colgroup> in every <table> within a fragment."""

    def replace_table(table_match: re.Match) -> str:
        table_html = table_match.group(0)

        first_row = re.search(r'<tr[\s>].*?</tr>', table_html, re.DOTALL | re.IGNORECASE)
        if not first_row:
            return table_html

        column_count = _count_cols(first_row.group(0))
        colgroup = _make_colgroup(column_count, widths_map)
        if not colgroup:
            return table_html

        table_html = re.sub(
            r'<colgroup>.*?</colgroup>\s*',
            '',
            table_html,
            flags=re.DOTALL | re.IGNORECASE,
        )

        return re.sub(
            r'(<table[^>]*>)',
            r'\1\n' + colgroup,
            table_html,
            count=1,
            flags=re.IGNORECASE,
        )

    return re.sub(
        r'<table[\s\S]*?</table>',
        replace_table,
        html,
        flags=re.IGNORECASE,
    )


def inject_colgroups(html: str) -> str:
    """
    Replace or inject <colgroup> in every <table> with our explicit column
    widths. Pandoc generates its own colgroups (50%/50% for 2-col tables)
    which must be overwritten, not skipped.

    Tables inside ``div.cover-meta`` get a wider label column so PDF/HTML
    cover metadata does not wrap mid-word.
    """
    parts = re.split(
        r'(<div\s+class="cover-meta"[^>]*>[\s\S]*?</div>)',
        html,
        flags=re.IGNORECASE,
    )
    fragments: list[str] = []
    for part in parts:
        if re.match(r'<div\s+class="cover-meta"', part, flags=re.IGNORECASE):
            fragments.append(_inject_colgroups_in_fragment(part, _COVER_META_COL_WIDTHS))
        else:
            fragments.append(_inject_colgroups_in_fragment(part))
    return "".join(fragments)


NARRATIVE_CHAPTER_CLASS = "hc-narrative-chapter"

NARRATIVE_PARAGRAPH_CSS = """\n.hc-narrative-chapter p {
  margin-top: 0;
  margin-bottom: 1em;
}
"""


def _heading_plain_text(heading_html: str) -> str:
    """Strip tags, collapse whitespace, and casefold for keyword matching."""
    text = re.sub(r"<[^>]+>", "", heading_html)
    return " ".join(text.split()).casefold()


def is_narrative_chapter_heading(heading_html: str) -> bool:
    text = _heading_plain_text(heading_html)
    chapter_three = "chapter 3" in text and "executive summary" in text
    chapter_eight = "chapter 8" in text and "conclusions" in text
    return chapter_three or chapter_eight


def is_report_chapter_heading(heading_html: str) -> bool:
    text = _heading_plain_text(heading_html)
    return bool(re.match(r"chapter\s+\d", text))


_PRIORITY_LEAK_HEADING = re.compile(r"^(p[0-3]\b|6\.2\.)")


def _is_priority_leak_heading(heading_html: str) -> bool:
    return bool(_PRIORITY_LEAK_HEADING.match(_heading_plain_text(heading_html)))


def demote_priority_leak_headings(html: str) -> str:
    """Rewrite stray P0–P3 / 6.2. h2 headings to h4 so they are not chapters."""

    def replace_heading(match: re.Match[str]) -> str:
        heading_html = match.group(0)
        if not _is_priority_leak_heading(heading_html):
            return heading_html
        opening = re.sub(r"<h2\b", "<h4", heading_html, count=1, flags=re.IGNORECASE)
        return re.sub(r"</h2>", "</h4>", opening, count=1, flags=re.IGNORECASE)

    return re.sub(
        r"<h2\b[^>]*>.*?</h2>",
        replace_heading,
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )


def wrap_narrative_chapters(html: str) -> str:
    """Wrap Chapter 3 and Chapter 8 h2 ranges for PDF paragraph spacing."""
    heading_pattern = re.compile(r"<h2\b[^>]*>.*?</h2>", re.IGNORECASE | re.DOTALL)
    matches = list(heading_pattern.finditer(html))
    if not matches:
        return html
    for index in range(len(matches) - 1, -1, -1):
        match = matches[index]
        if not is_narrative_chapter_heading(match.group(0)):
            continue
        start = match.start()
        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            body_close = re.search(r"</body>", html, re.IGNORECASE)
            end = body_close.start() if body_close else len(html)
        inner = html[start:end]
        html = (
            html[:start]
            + f'<div class="{NARRATIVE_CHAPTER_CLASS}">'
            + inner
            + "</div>"
            + html[end:]
        )
    return html
