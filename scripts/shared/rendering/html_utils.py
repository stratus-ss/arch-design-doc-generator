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
