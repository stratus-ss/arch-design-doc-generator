#!/usr/bin/env python3
"""Build TSR/CCX crosswalk catalog JSON from a TSR HTML export."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from hc_report._text import slugify as _slugify


def _make_entry(
    category_id: str,
    category_name: str,
    source: str,
    group: str,
    title: str,
    status_hint: str = "SKIPPED",
    tsr_ref: str = "",
) -> dict:
    prefix = "tsr" if source == "tsr" else f"ccx_{group}"
    return {
        "check_id": f"{category_id}.{prefix}.{_slugify(title)}",
        "category_id": category_id,
        "category_name": category_name,
        "source": source,
        "group": group,
        "title": re.sub(r"\s+", " ", title).strip(),
        "status_hint": status_hint,
        "tsr_ref": tsr_ref,
        "tags": [],
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

_CCX_STATUS_MAP = {"fail": "FAIL", "pass": "PASS", "info": "INFO", "skip": "SKIPPED", "warning": "WARNING"}


def _collect_tsr_sections(tsr_html: str) -> list[dict]:
    """Extract catalog entries from TSR sections 1–7."""
    results: list[dict] = []
    marker = 'pf-v6-c-tree-view__node-text">'
    for panel_id, next_btn, category_id, category_name, ref in _SECTION_MAP:
        start = tsr_html.find(f'id="{panel_id}"')
        if start < 0:
            continue
        end = tsr_html.find(f'id="{next_btn}"', start)
        if end < 0:
            end = len(tsr_html)
        section = tsr_html[start:end]
        position = 0
        while True:
            index = section.find(marker, position)
            if index < 0:
                break
            end_index = section.find("</span>", index)
            if end_index < 0:
                break
            title = section[index + len(marker):end_index]
            title = re.sub(r"<[^>]+>", "", title)
            title = re.sub(r"\s+", " ", title).strip()
            if title:
                title_match = re.match(r"^(\d+(?:\.\d+)+)", title)
                tsr_ref = title_match.group(1) if title_match else ref
                results.append(
                    _make_entry(category_id, category_name, "tsr", f"section{ref}", title, "SKIPPED", tsr_ref)
                )
            position = end_index + 7
    return results


def _collect_summary(tsr_html: str) -> list[dict]:
    """Extract pre-check entries (e.g. must-gather) from the summary panel."""
    summary_start = tsr_html.find('id="summary-of-checks-panel"')
    if summary_start < 0:
        return []
    summary_end = tsr_html.find('id="1. Basic Checks-btn"', summary_start)
    summary_section = tsr_html[summary_start:summary_end if summary_end > summary_start else len(tsr_html)]
    results: list[dict] = []
    for item in re.findall(r'pf-v6-c-tree-view__node-text">([^<]+)</span>', summary_section):
        title = re.sub(r"\s+", " ", item).strip()
        if title.lower().startswith("openshift must gather"):
            results.append(_make_entry("7.1", "Base Platform Checks", "tsr", "pre", title, "INFO", "pre"))
    return results


def _collect_ccx(tsr_html: str) -> list[dict]:
    """Extract CCX advisory entries from the ccx-checks-section."""
    ccx_start = tsr_html.find('id="ccx-checks-section-panel"')
    ccx_end = tsr_html.find('id="escalations-btn"', ccx_start) if ccx_start >= 0 else -1
    if ccx_start < 0 or ccx_end <= ccx_start:
        return []
    ccx_section = tsr_html[ccx_start:ccx_end]
    group_ranges = [
        ("external", 'id="External-panel"', 'id="Internal-btn"'),
        ("internal", 'id="Internal-panel"', 'id="Skips-btn"'),
        ("skip", 'id="Skips-panel"', None),
    ]
    results: list[dict] = []
    for group, start_marker, end_marker in group_ranges:
        group_start = ccx_section.find(start_marker)
        if group_start < 0:
            continue
        group_end = (
            ccx_section.find(end_marker, group_start) if end_marker else len(ccx_section)
        )
        if group_end < 0:
            group_end = len(ccx_section)
        group_section = ccx_section[group_start:group_end]
        for part in group_section.split("<b>Check:</b>")[1:]:
            chunk = part[:5000]
            title = chunk.split("<br", 1)[0]
            title = re.sub(r"<[^>]+>", "", title)
            title = re.sub(r"\s+", " ", title).strip()
            if not title:
                continue
            status_match = re.search(r"<b>Status:</b>\s*([^<\n]+)", chunk, re.I)
            status = _CCX_STATUS_MAP.get(
                (status_match.group(1).strip().lower() if status_match else "skip"),
                "SKIPPED",
            )
            tags: list[str] = []
            for badge in re.findall(r"border-radius:1rem[^>]*>([^<]+)</span>", chunk):
                tags.append(re.sub(r"\s+", " ", badge).strip().lower())
            entry = _make_entry(
                "7.7", "Security and Compliance", "ccx", group, title, status, f"CCX:{group}"
            )
            entry["tags"] = tags
            results.append(entry)
    return results


def _build_catalog(tsr_html: str) -> dict:
    seen: set[str] = set()
    entries: list[dict] = []
    for entry in _collect_tsr_sections(tsr_html) + _collect_summary(tsr_html) + _collect_ccx(tsr_html):
        if entry["check_id"] not in seen:
            seen.add(entry["check_id"])
            entries.append(entry)
    return {
        "schema_version": 1,
        "entries": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build TSR/CCX crosswalk catalog from TSR HTML")
    parser.add_argument("--input-html", type=Path, required=True, help="Path to TSR HTML export")
    parser.add_argument("--output-json", type=Path, required=True, help="Output crosswalk catalog JSON path")
    args = parser.parse_args()

    html = args.input_html.read_text(encoding="utf-8", errors="ignore")
    catalog = _build_catalog(html)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {args.output_json} ({len(catalog['entries'])} entries)")


if __name__ == "__main__":
    main()
