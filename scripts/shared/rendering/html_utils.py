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


_H2_HEADING = re.compile(r"<h2\b[^>]*>.*?</h2>", re.IGNORECASE | re.DOTALL)
_CHAPTER_NUMBER = re.compile(r"chapter\s+(\d+)")
_HEADING_ID = re.compile(r'\bid="([^"]+)"', re.IGNORECASE)
_TOC_LINE = re.compile(
    r"(?P<number>\d+)\.\s+(?P<title>[^<]+?)(?=(?P<ending><br\s*/?>|</p>|</li>|$))",
    re.IGNORECASE,
)
_TOC_LIST_ITEM = re.compile(
    r"<li\b[^>]*>(?P<inner>.*?)</li>",
    re.IGNORECASE | re.DOTALL,
)
_TRAILING_BREAK = re.compile(r"<br\s*/?>\s*$", re.IGNORECASE)


def _heading_chapter_number(heading_html: str) -> int | None:
    if not is_report_chapter_heading(heading_html):
        return None
    number_match = _CHAPTER_NUMBER.search(_heading_plain_text(heading_html))
    if not number_match:
        return None
    return int(number_match.group(1))


def _chapter_heading_ids(html: str) -> tuple[dict[int, str], list[re.Match[str]]]:
    matches = list(_H2_HEADING.finditer(html))
    chapter_ids: dict[int, str] = {}
    for match in matches:
        heading_html = match.group(0)
        chapter_number = _heading_chapter_number(heading_html)
        if chapter_number is None:
            continue
        id_match = _HEADING_ID.search(heading_html)
        if not id_match:
            continue
        chapter_ids[chapter_number] = id_match.group(1)
    return chapter_ids, matches


def _wrap_toc_list_items(chapter_two_body: str, chapter_ids: dict[int, str]) -> str:
    """Wrap pandoc <ol><li> Chapter 2 rows (numbers live in the list, not the text)."""
    chapter_number = 0

    def replace_item(match: re.Match[str]) -> str:
        nonlocal chapter_number
        inner = match.group("inner")
        if re.search(r"<a\b", inner, re.IGNORECASE):
            return match.group(0)
        chapter_number += 1
        heading_id = chapter_ids.get(chapter_number)
        if not heading_id:
            return match.group(0)
        title = _TRAILING_BREAK.sub("", inner).strip()
        return (
            f'<li><a class="hc-toc-link" href="#{heading_id}">'
            f"{title}</a></li>"
        )

    return _TOC_LIST_ITEM.sub(replace_item, chapter_two_body)


def _wrap_numbered_toc_lines(chapter_two_body: str, chapter_ids: dict[int, str]) -> str:
    def replace_line(match: re.Match[str]) -> str:
        start = match.start()
        preceding = chapter_two_body[max(0, start - 32) : start]
        last_anchor = preceding.casefold().rfind("<a")
        still_open = last_anchor != -1 and ">" not in preceding[last_anchor:]
        if still_open:
            return match.group(0)
        chapter_number = int(match.group("number"))
        heading_id = chapter_ids.get(chapter_number)
        if not heading_id:
            return match.group(0)
        title = match.group("title")
        ending = match.group("ending") or ""
        return (
            f'<a class="hc-toc-link" href="#{heading_id}">'
            f"{chapter_number}. {title}</a>{ending}"
        )

    return _TOC_LINE.sub(replace_line, chapter_two_body)


def _wrap_toc_lines(chapter_two_body: str, chapter_ids: dict[int, str]) -> str:
    listed = _wrap_toc_list_items(chapter_two_body, chapter_ids)
    return _wrap_numbered_toc_lines(listed, chapter_ids)


def linkify_chapter_toc(html: str) -> str:
    """Turn Chapter 2 numbered lines into fragment links to chapter heading ids."""
    chapter_ids, matches = _chapter_heading_ids(html)
    if not chapter_ids or not matches:
        return html
    chapter_two_match = None
    for match in matches:
        if _heading_chapter_number(match.group(0)) == 2:
            chapter_two_match = match
            break
    if chapter_two_match is None:
        return html
    chapter_two_index = matches.index(chapter_two_match)
    body_start = chapter_two_match.end()
    if chapter_two_index + 1 < len(matches):
        body_end = matches[chapter_two_index + 1].start()
    else:
        body_close = re.search(r"</body>", html, re.IGNORECASE)
        body_end = body_close.start() if body_close else len(html)
    rewritten = _wrap_toc_lines(html[body_start:body_end], chapter_ids)
    return html[:body_start] + rewritten + html[body_end:]


def wrap_narrative_chapters(html: str) -> str:
    """Wrap Chapter 3 and Chapter 8 h2 ranges for PDF paragraph spacing."""
    matches = list(_H2_HEADING.finditer(html))
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
