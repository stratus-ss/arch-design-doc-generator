"""Parse TSR HTML exports into structured check records with real statuses."""
from __future__ import annotations

import re
from html import unescape

from hc_report._text import slugify as _slugify

_STATUS_MAP = {
    "PASS": "PASS",
    "FAIL": "FAIL",
    "WARNING": "WARNING",
    "WARN": "WARNING",
    "INFO": "INFO",
    "NA": "NOT_APPLICABLE",
    "NOT_APPLICABLE": "NOT_APPLICABLE",
    "SKIP": "SKIPPED",
    "SKIPPED": "SKIPPED",
}

_SECTION_MAP = [
    ("1. Basic Checks-panel", "2. Topology Checks-btn", "7.1", "Base Platform Checks", "1"),
    ("2. Topology Checks-panel", "3. Component Checks-btn", "7.2", "Topology Checks", "2"),
    ("3. Component Checks-panel", "4. Layered Products-btn", "7.3", "Component Checks", "3"),
    ("4. Layered Products-panel", "5. Cluster Health-btn", "7.4", "Layered Products", "4"),
    ("5. Cluster Health-panel", "6. Day-2 Operations-btn", "7.5", "Cluster Health", "5"),
    ("6. Day-2 Operations-panel", "7. Security and Compliance-btn", "7.6", "Day-2 Operations", "6"),
    ("7. Security and Compliance-panel", "ccx-checks-section-btn", "7.7", "Security and Compliance", "7"),
]

_EVIDENCE_MAX = 2000

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = text.replace("\t", " ")
    # Some captured command output (e.g. `oc get storageclass`) is colorized
    # terminal output with raw ANSI SGR escape sequences baked into the TSR
    # HTML (bold/color codes around table headers). These aren't HTML tags
    # so the tag-stripping above never touches them, and left in place they
    # render as literal garbage like `[1mNAME ...[0m` in the final report.
    text = _ANSI_ESCAPE_RE.sub("", text)
    # Some Result cells are pre-formatted fixed-width tables (e.g. `oc get
    # nodes`-style output) using column padding of 3+ spaces, not real HTML
    # <table> markup. A bare `[ \t]+ -> " "` collapse would destroy that
    # alignment (renderer.py needs a 3+ space run to detect column
    # boundaries), but preserving the full original padding width verbatim
    # wastes the fixed evidence-length budget (_EVIDENCE_MAX) on cosmetic
    # terminal-alignment spaces, which previously pushed real table rows
    # past the truncation cutoff. Normalize any wide gap down to a fixed
    # 3-space marker: the column-boundary signal survives, incidental 1-2
    # space tag-stripping artifacts are left alone, and the byte cost per
    # gap no longer scales with the original column width.
    text = re.sub(r" {3,}", "   ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_status(raw: str) -> str:
    return _STATUS_MAP.get(raw.strip().upper(), "SKIPPED")


def _extract_leaf_check(
    leaf_html: str, section_number: str, category_id: str, category_name: str
) -> dict | None:
    """Parse one leaf-extra table block into a check record."""
    status_match = re.search(r">Status</td>\s*<td[^>]*>\s*<b>(\w+)</b>", leaf_html, re.I)
    if not status_match:
        return None

    status = _normalize_status(status_match.group(1))

    check_match = re.search(
        r">Check</td>\s*<td[^>]*>(.*?)</td>", leaf_html, re.S | re.I
    )
    title = ""
    context = ""
    if check_match:
        raw_check = check_match.group(1)
        context_match = re.search(r"<p>(.*?)</p>", raw_check, re.S)
        if context_match:
            context = _strip_html(context_match.group(1))
        title_part = re.sub(r"<p>.*?</p>", "", raw_check, flags=re.S)
        title = _strip_html(title_part)

    if not title:
        return None

    tags: list[str] = []
    tags_match = re.search(r">Tags</td>\s*<td[^>]*>(.*?)</td>", leaf_html, re.S | re.I)
    if tags_match:
        for badge in re.findall(r'av-tag-badge["\s>]*>([^<]+)', tags_match.group(1)):
            cleaned = badge.strip().lower()
            if cleaned:
                tags.append(cleaned)

    evidence = ""
    result_match = re.search(r">Result</td>\s*<td[^>]*>(.*?)</td>", leaf_html, re.S | re.I)
    if result_match:
        evidence = _strip_html(result_match.group(1))[:_EVIDENCE_MAX]

    ref_match = re.match(r"^(\d+(?:\.\d+)*)", title)
    tsr_ref = ref_match.group(1) if ref_match else section_number

    return {
        "check_id": f"{category_id}.tsr.{_slugify(title)}",
        "title": title,
        "section": int(section_number),
        "category_id": category_id,
        "category_name": category_name,
        "source": "tsr",
        "status": status,
        "evidence": evidence,
        "tags": tags,
        "context": context,
        "tsr_ref": tsr_ref,
    }


def _parse_sections(html: str) -> list[dict]:
    """Extract leaf-level checks from TSR sections 1-7."""
    results: list[dict] = []
    seen_ids: set[str] = set()

    for panel_id, next_btn, category_id, category_name, section_number in _SECTION_MAP:
        start = html.find(f'id="{panel_id}"')
        if start < 0:
            continue
        end = html.find(f'id="{next_btn}"', start)
        if end < 0:
            end = len(html)
        section = html[start:end]

        leaves = section.split('<div class="leaf-extra"')
        for leaf_raw in leaves[1:]:
            close_index = leaf_raw.find("</div>\n                </div>\n")
            if close_index < 0:
                close_index = min(len(leaf_raw), 10000)
            leaf_block = leaf_raw[:close_index]

            record = _extract_leaf_check(leaf_block, section_number, category_id, category_name)
            if record and record["check_id"] not in seen_ids:
                seen_ids.add(record["check_id"])
                results.append(record)

    return results


def _parse_ccx_section(html: str) -> list[dict]:
    """Extract CCX advisory checks from the ccx-checks-section."""
    ccx_start = html.find('id="ccx-checks-section-panel"')
    if ccx_start < 0:
        return []
    ccx_end = html.find('id="escalations-btn"', ccx_start)
    if ccx_end < 0:
        ccx_end = len(html)
    ccx_section = html[ccx_start:ccx_end]

    group_ranges = [
        ("external", 'id="External-panel"', 'id="Internal-btn"'),
        ("internal", 'id="Internal-panel"', 'id="Skips-btn"'),
        ("skip", 'id="Skips-panel"', None),
    ]

    results: list[dict] = []
    seen_ids: set[str] = set()

    for group, start_marker, end_marker in group_ranges:
        group_start = ccx_section.find(start_marker)
        if group_start < 0:
            continue
        group_end = ccx_section.find(end_marker, group_start) if end_marker else len(ccx_section)
        if group_end < 0:
            group_end = len(ccx_section)
        group_section = ccx_section[group_start:group_end]

        for part in group_section.split("<b>Check:</b>")[1:]:
            record = _extract_ccx_check(part[:8000], group)
            if record and record["check_id"] not in seen_ids:
                seen_ids.add(record["check_id"])
                results.append(record)

    return results


def _extract_ccx_check(chunk: str, group: str) -> dict | None:
    """Parse one CCX check entry from its HTML fragment."""
    title_raw = chunk.split("<br", 1)[0]
    title = _strip_html(title_raw)
    if not title:
        return None

    status_match = re.search(r"<b>Status:</b>\s*([^<\n]+)", chunk, re.I)
    status = _normalize_status(status_match.group(1).strip() if status_match else "skip")

    tags = []
    for badge in re.findall(r"border-radius:1rem[^>]*>([^<]+)</span>", chunk):
        cleaned = _strip_html(badge).lower()
        if cleaned:
            tags.append(cleaned)

    evidence = ""
    message_match = re.search(r"<b>Message:</b>\s*(.*?)(?:</td>|$)", chunk, re.S)
    if message_match:
        evidence = _strip_html(message_match.group(1))[:_EVIDENCE_MAX]

    check_id = f"7.7.ccx_{group}.{_slugify(title)}"
    return {
        "check_id": check_id,
        "title": title,
        "section": 8,
        "category_id": "7.7",
        "category_name": "Security and Compliance",
        "source": "ccx",
        "group": group,
        "status": status,
        "evidence": evidence,
        "tags": tags,
        "context": "",
        "tsr_ref": f"CCX:{group}",
    }


def parse_tsr_html(html: str) -> list[dict]:
    """Parse a TSR HTML export into a flat list of check records."""
    checks = _parse_sections(html)
    checks.extend(_parse_ccx_section(html))
    return checks
