"""Report rendering: slot builders and template substitution."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from html import escape

from hc_report.evaluators._common import _CATEGORY_MAP
from hc_report.kb_loader import NEEDS_REVIEW_MARKER, load_kb
from hc_report.models import CheckResult, Finding
from hc_report.notes import get_note

_BADGE: dict[str, str] = {
    "PASS":           "🟢 PASS",
    "FAIL":           "🔴 FAIL",
    "WARNING":        "🟡 WARNING",
    "INFO":           "🔵 INFO",
    "NOT_APPLICABLE": "⚪ NOT APPLICABLE",
    "SKIPPED":        "⚪ SKIPPED",
    "NONE":           "⚫ NONE",
}

_TSR_TITLE_RE = re.compile(r"^(\d+(?:\.\d+)*\.?)\s+(.+)$")
_WHITESPACE_RE = re.compile(r"\s+")
_ANCHOR_TOKEN_RE = re.compile(r"[^a-z0-9]+")
_FAILURE_REASON_RE = re.compile(
    r"\[(PASS|FAIL|WARNING|INFO|NOT APPLICABLE)\]",
    re.IGNORECASE,
)
_SUMMARY_MAX_LENGTH = 220
_SUMMARY_MIN_SENTENCE_CHARS = 40
_SUMMARY_MIN_USABLE_CHARS = 8
_UNUSABLE_SUMMARY_VALUES = frozenset({"n/a", "none", "unknown", "na"})


def _md_table_cell(text: str) -> str:
    """Escape pipes and convert newlines so pandoc keeps markdown table cells intact."""
    if not text:
        return ""
    return text.replace("|", "\\|").replace("\n", "<br>")


_TABLE_SEPARATOR_RE = re.compile(r"^[-| :]+$")


def _is_table_separator(line: str) -> bool:
    """True for ASCII table separator rows like ``-----|-----``."""
    stripped = line.strip()
    if stripped.count("-") < 3:
        return False
    return bool(_TABLE_SEPARATOR_RE.match(stripped))


def _split_pipe_cells(line: str) -> list[str]:
    """Split a pipe-delimited row into stripped cell values.

    Does NOT drop leading/trailing empty cells. A trailing ``|`` is
    ambiguous on its own — it looks identical whether it's ``| a | b |``
    wrapping syntax or a genuinely empty last column (e.g. ``true |`` with
    an empty final column) — and real TSR evidence rows are never wrapped
    (they look like ``a | b | c``, no outer pipes), so treating every
    trailing/leading empty as a wrapper artifact silently drops real empty
    column values and desyncs the cell count from the header, rejecting an
    otherwise-valid table row as a column-count mismatch.
    """
    cells = []
    for cell in line.strip().split("|"):
        cells.append(cell.strip())
    return cells


def _collapse_ws(text: str) -> str:
    """Collapse incidental multi-space runs (e.g. from HTML tag stripping) to one space."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def _clean_evidence_for_cell(text: str) -> str:
    """Flatten raw evidence into readable text safe to embed as one markdown
    table cell (the ``Result`` row).

    TSR/CCX evidence sometimes embeds small ASCII/markdown-style tables — a
    header row, a ``---|---`` separator row, and pipe-delimited data rows —
    straight from a captured command's output. Dumped verbatim into a table
    cell, the separator row is pure table-drawing noise with no structure
    left to align once flattened, and reads like the report broke. This
    drops separator rows entirely and rewrites any remaining pipe-delimited
    row into a plain ``·``-joined list, so nothing looks like a stray
    fragment of a markdown table.
    """
    if not text:
        return ""
    body = _normalize_evidence_body(text)
    cleaned_lines: list[str] = []
    for line in body.splitlines():
        if _is_table_separator(line):
            continue
        if "|" in line:
            cells = [cell for cell in _split_pipe_cells(line) if cell]
            line = " · ".join(cells) if cells else line
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _sanitize_anchor_id(text: str) -> str:
    """Normalize a string into a stable HTML anchor token."""
    if not text:
        return "item"
    normalized = _ANCHOR_TOKEN_RE.sub("-", text.lower()).strip("-")
    return normalized or "item"


def _finding_anchor_id(finding_id: str) -> str:
    return f"finding-{_sanitize_anchor_id(finding_id)}"


def _evidence_anchor_id(check_id: str) -> str:
    return f"evidence-{_sanitize_anchor_id(check_id)}"


def _build_finding_anchor(finding_id: str, check_id: str) -> str:
    """Emit an invisible HTML anchor for a rendered finding block."""
    attrs = [f'id="{_finding_anchor_id(finding_id)}"']
    if check_id and check_id != "n/a":
        attrs.append(f'data-check-id="{escape(check_id, quote=True)}"')
        attrs.append(f'data-evidence-id="{_evidence_anchor_id(check_id)}"')
    return f"<span {' '.join(attrs)}></span>"


def _build_evidence_anchor(check_id: str, finding_ids: list[str]) -> str:
    """Emit an invisible HTML anchor for a raw evidence block."""
    attrs = [
        f'id="{_evidence_anchor_id(check_id)}"',
        f'data-check-id="{escape(check_id, quote=True)}"',
    ]
    linked_finding_ids = [_finding_anchor_id(fid) for fid in finding_ids if fid]
    if linked_finding_ids:
        attrs.append(f'data-finding-ids="{",".join(linked_finding_ids)}"')
    return f"<span {' '.join(attrs)}></span>"


_RESULT_STATUS_RE = re.compile(r"\[(PASS|FAIL|WARNING|INFO|NOT APPLICABLE)\]")


def _normalize_evidence_body(text: str) -> str:
    """Trim lines and collapse excess blank lines without changing non-whitespace."""
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines()]
    normalized: list[str] = []
    blank_pending = False
    for line in lines:
        if not line:
            blank_pending = True
            continue
        if blank_pending and normalized:
            normalized.append("")
        blank_pending = False
        normalized.append(line)
    return "\n".join(normalized)


def _truncate_at_word_boundary(text: str, max_length: int) -> str:
    """Truncate text at a word boundary, appending ellipsis if shortened."""
    if len(text) <= max_length:
        return text
    truncated = text[:max_length].rsplit(" ", 1)[0]
    return truncated + "…"


def _extract_failure_reason(evidence: str) -> str:
    """Return the first FAIL remainder, else the first WARNING remainder."""
    first_fail = ""
    first_warning = ""
    for line in evidence.splitlines():
        for match in _FAILURE_REASON_RE.finditer(line):
            status = match.group(1).upper()
            if status not in {"FAIL", "WARNING"}:
                continue
            remainder = line[match.end():].lstrip()
            if remainder.startswith("-"):
                remainder = remainder[1:].lstrip()
            if remainder[:7].casefold() == "reason:":
                remainder = remainder[7:].lstrip()
            next_tag = _FAILURE_REASON_RE.search(remainder)
            if next_tag:
                remainder = remainder[: next_tag.start()]
            remainder = remainder.strip()
            if status == "FAIL" and not first_fail:
                first_fail = remainder
            elif status == "WARNING" and not first_warning:
                first_warning = remainder
            if first_fail:
                return first_fail
    return first_fail or first_warning


def _clean_summary_prose(text: str) -> str:
    """Flatten, strip status tags, capitalize, and end with a sentence mark."""
    flattened = _WHITESPACE_RE.sub(" ", text).replace("|", " ").strip()
    flattened = _FAILURE_REASON_RE.sub("", flattened)
    flattened = _WHITESPACE_RE.sub(" ", flattened).strip()
    if not flattened:
        return ""
    characters = list(flattened)
    for index, character in enumerate(characters):
        if character.isalpha():
            characters[index] = character.upper()
            flattened = "".join(characters)
            break
    if flattened[-1] not in ".!?":
        flattened += "."
    return flattened


def _truncate_summary_sentence(text: str, max_length: int = _SUMMARY_MAX_LENGTH) -> str:
    """Prefer a sentence end inside the cap; else truncate at a word boundary."""
    if len(text) <= max_length:
        return text
    window = text[:max_length]
    sentence_end = max(window.rfind("."), window.rfind("!"), window.rfind("?"))
    if sentence_end >= _SUMMARY_MIN_SENTENCE_CHARS:
        return window[: sentence_end + 1].strip()
    return _truncate_at_word_boundary(text, max_length)


def _match_summary_pattern(finding: Finding) -> str:
    """Return the first matching KB summary_patterns text, or empty."""
    if not finding.check_id:
        return ""
    entry = load_kb().get_entry(finding.check_id)
    if entry is None:
        return ""
    haystack = (finding.description or "").casefold()
    for pattern in entry.summary_patterns:
        if pattern.contains.casefold() in haystack:
            return pattern.text
    return ""


def _finish_summary_prose(text: str) -> str:
    """Clean, omit unusable text, and truncate at sentence then word boundary."""
    cleaned = _clean_summary_prose(text)
    folded = cleaned.rstrip(".!?").casefold()
    if (
        not cleaned
        or len(cleaned) < _SUMMARY_MIN_USABLE_CHARS
        or not any(character.isascii() and character.isalpha() for character in cleaned)
        or folded in _UNUSABLE_SUMMARY_VALUES
    ):
        return ""
    return _truncate_summary_sentence(cleaned)


def _chapter_finding_summary(finding: Finding) -> str:
    """One-line Chapter 4 / §6.1 summary: pattern, then FAIL/WARNING, never KB description."""
    evidence = finding.description or ""
    source = _match_summary_pattern(finding)
    if not source:
        source = _extract_failure_reason(evidence)
    if not source and not _RESULT_STATUS_RE.search(evidence):
        source = evidence
    return _finish_summary_prose(source)


def _status_count_sentence(evidence: str) -> str:
    """Status-count sentence for tagged evidence; empty when there are no tags."""
    if not evidence:
        return ""
    statuses = _RESULT_STATUS_RE.findall(evidence)
    if not statuses:
        return ""
    total = len(statuses)
    fail_count = statuses.count("FAIL")
    warn_count = statuses.count("WARNING")
    pass_count = statuses.count("PASS")
    parts = []
    if fail_count:
        parts.append(f"**{fail_count}** FAIL")
    if warn_count:
        parts.append(f"**{warn_count}** WARNING")
    if pass_count:
        parts.append(f"{pass_count} PASS")
    info_not_applicable_count = total - fail_count - warn_count - pass_count
    if info_not_applicable_count:
        parts.append(f"{info_not_applicable_count} INFO/N/A")
    return f"{total} sub-checks evaluated: {', '.join(parts)}"


def _finding_observation(finding: Finding) -> str:
    """§6.2 Observation: count, then pattern, then first FAIL/WARNING reason."""
    evidence = finding.description or ""
    count_sentence = _status_count_sentence(evidence)
    pattern_text = _finish_summary_prose(_match_summary_pattern(finding))
    extracted_raw = _extract_failure_reason(evidence)
    if not extracted_raw and not count_sentence:
        extracted_raw = evidence
    extracted_text = _finish_summary_prose(extracted_raw)
    if pattern_text and extracted_text and pattern_text.casefold() == extracted_text.casefold():
        extracted_text = ""
    blocks = [block for block in (count_sentence, pattern_text, extracted_text) if block]
    return "\n\n".join(blocks)


def _split_finding_title(title: str) -> tuple[str, str]:
    """Split a TSR-prefixed title into (display_title, tsr_ref)."""
    if not title:
        return "", "n/a"
    match = _TSR_TITLE_RE.match(title)
    if not match:
        return title, "n/a"
    tsr_ref = match.group(1).rstrip(".")
    return match.group(2), tsr_ref


def _build_cluster_id_table(meta: dict) -> str:
    rows = [
        "| Field | Value |",
        "|-------|-------|",
        f"| Cluster Name | {meta['cluster_name']} |",
        f"| OCP Version | {meta['ocp_version']} |",
        f"| Install Type | {meta['install_type']} |",
        f"| Update Channel | {meta['channel']} |",
        f"| Data Capture Date | {meta['capture_date']} |",
        f"| Case Number | {meta['case_number']} |",
        f"| Author | {meta['author']} |",
    ]
    return "\n".join(rows)


def _build_stats_rows(checks: list[CheckResult]) -> str:
    checks_by_category: dict[str, list[CheckResult]] = defaultdict(list)
    for check in checks:
        checks_by_category[check.category_id].append(check)

    category_names = {category_id: name for _, (category_id, name) in _CATEGORY_MAP.items()}
    category_order = ["7.1", "7.2", "7.3", "7.4", "7.5", "7.6", "7.7", "7.8", "7.9"]
    rows = []
    for category_id in category_order:
        category_checks = checks_by_category.get(category_id, [])
        if not category_checks:
            continue
        counts = Counter(check.status for check in category_checks)
        total = len(category_checks)
        skipped_or_not_applicable = counts.get("NOT_APPLICABLE", 0) + counts.get("SKIPPED", 0)
        rows.append(
            f"| {category_names.get(category_id, category_id)} | {counts.get('PASS', 0)} | "
            f"{counts.get('WARNING', 0)} | {counts.get('FAIL', 0)} | {counts.get('INFO', 0)} | "
            f"{skipped_or_not_applicable} | {total} |"
        )
    return "\n".join(rows)


def _build_check_results_table(
    checks: list[CheckResult],
    category_id: str,
    finding_ids_by_check: dict[str, list[str]] | None = None,
    ocp_version: str = "latest",
) -> str:
    """Render one 2-column table per check."""
    category_checks = [check for check in checks if check.category_id == category_id]
    if not category_checks:
        return "_No data collected for this category._"

    blocks = []
    finding_ids_by_check = finding_ids_by_check or {}
    for check in category_checks:
        badge = _BADGE.get(check.status, check.status)
        result_cell = _md_table_cell(_clean_evidence_for_cell(check.evidence))
        anchor = _build_evidence_anchor(check.check_id, finding_ids_by_check.get(check.check_id, []))
        display_title = load_kb().get_title(check.check_id) or check.description
        rows = (
            f"| **Check** | **{_md_table_cell(display_title)}** |\n"
            f"|:---|:---|\n"
            f"| **Status** | {badge} |\n"
            f"| **Result** | {result_cell} |"
        )
        if check.source and check.source != "deterministic":
            rows += f"\n| **Source** | {_md_table_cell(check.source)} |"
        if check.tsr_ref:
            rows += f"\n| **Reference** | {_md_table_cell(check.tsr_ref)} |"
        if check.tags:
            tags = ", ".join(_md_table_cell(tag) for tag in check.tags)
            rows += f"\n| **Tags** | {tags} |"
        note_data = get_note(check.check_id, ocp_version=ocp_version)
        if note_data:
            note_text, doc_link = note_data
            rows += f"\n| **Note** | {_md_table_cell(note_text)} |"
            if doc_link:
                rows += f"\n| **Links** | {_md_table_cell(doc_link)} |"
        # Anchor before the table so fragment links land at the top of the
        # evidence block. A standalone <span> on its own line with surrounding
        # blank lines does not interfere with pandoc markdown table parsing.
        blocks.append(anchor + "\n\n" + rows + "\n")
    return "\n---\n\n".join(blocks)


def _build_findings_sections(findings: list[Finding], ocp_version: str = "latest") -> str:
    if not findings:
        return "_No findings requiring remediation._"

    knowledge_base = load_kb()
    sections = []
    labels = {"P0": "P0: Critical", "P1": "P1: High", "P2": "P2: Medium", "P3": "P3: Low"}
    for priority in ["P0", "P1", "P2", "P3"]:
        priority_findings = [finding for finding in findings if finding.priority == priority]
        if not priority_findings:
            continue
        sections.append(f"### {labels[priority]}\n")
        for finding in priority_findings:
            display, tsr = _split_finding_title(finding.title)
            check_id = finding.check_id or "n/a"
            sections.append(f"#### {finding.id}. {display}\n")
            if finding.member_check_ids:
                member_ids = " ".join(f"`{member_id}`" for member_id in finding.member_check_ids)
                sections.append(f"**Check ID:** {member_ids}")
            else:
                sections.append(f"**Check ID:** `{check_id}`")
            sections.append(f"**TSR ref:** {tsr}\n")
            kb_desc = knowledge_base.get_description(check_id) if check_id != "n/a" else ""
            if kb_desc:
                sections.append(f"**Description:**\n\n{kb_desc}\n")
            # Anchor after Observation so pandoc keeps #### as a heading and
            # HTML injection shows "View evidence" on its own line under Observation.
            sections.append(
                f"**Observation:**\n\n{_finding_observation(finding)}\n\n"
                f"{_build_finding_anchor(finding.id, check_id)}\n"
            )
            sections.append(f"**Recommendation:**\n\n{finding.recommendation}\n")
            impact_block = _format_impact_block(finding)
            if impact_block:
                sections.append(f"{impact_block}")
    return "\n".join(sections)


def _format_impact_block(finding: Finding) -> str:
    if not finding.impact:
        return f"**Level of Impact:** {NEEDS_REVIEW_MARKER}\n"
    if finding.impact == "none":
        label = "None"
    else:
        label = finding.impact.replace("-", " ").title()
    scope = f" ({finding.impact_scope})" if finding.impact_scope else ""
    detail = f" — {finding.impact_detail}" if finding.impact_detail else ""
    return f"**Level of Impact:** {label}{scope}{detail}\n"


def _build_critical_findings(findings: list[Finding]) -> str:
    critical = [finding for finding in findings if finding.priority in ("P0", "P1")]
    if not critical:
        return "_No critical or high-priority findings identified._"
    lines = ["| Priority | Finding | Summary |", "|----------|---------|---------|"]
    for finding in critical:
        display, _tsr = _split_finding_title(finding.title)
        summary = _chapter_finding_summary(finding)
        lines.append(f"| {finding.priority} | {finding.id} — {display} | {summary} |")
    return "\n".join(lines)


def _critical_summary_bullet(finding: Finding) -> str:
    display, _tsr = _split_finding_title(finding.title)
    summary = _chapter_finding_summary(finding)
    if summary:
        return f"- **{finding.id} — {display}**: {summary}"
    return f"- **{finding.id} — {display}**"


def _build_critical_findings_summary(findings: list[Finding]) -> str:
    p0_findings = [finding for finding in findings if finding.priority == "P0"]
    p1_findings = [finding for finding in findings if finding.priority == "P1"]
    lines = []
    if p0_findings:
        lines.append(f"**{len(p0_findings)} Critical (P0) finding(s)** require immediate action:\n")
        for finding in p0_findings:
            lines.append(_critical_summary_bullet(finding))
        lines.append("")
    if p1_findings:
        lines.append(f"**{len(p1_findings)} High (P1) finding(s)** require near-term attention:\n")
        for finding in p1_findings:
            lines.append(_critical_summary_bullet(finding))
    return "\n".join(lines) if lines else "_No critical findings._"


def render_report(
    template: str, meta: dict, checks: list[CheckResult], findings: list[Finding],
    exec_summary: str, findings_narrative: str, data_collection_method: str,
    ocp_version: str = "latest",
) -> str:
    status_counts = Counter(check.status for check in checks)
    total = len(checks)
    skip_count = status_counts.get("NOT_APPLICABLE", 0) + status_counts.get("SKIPPED", 0)
    finding_ids_by_check: dict[str, list[str]] = defaultdict(list)
    for finding in findings:
        if finding.check_id:
            finding_ids_by_check[finding.check_id].append(finding.id)

    slots = {
        "CLIENT":                     meta["client_name"],
        "CLIENT_PREFIX":              meta["client_prefix"],
        "CLUSTER_NAME":               meta["cluster_name"],
        "OCP_VERSION":                meta["ocp_version"],
        "CAPTURE_DATE":               meta["capture_date"],
        "REPORT_DATE":                meta["report_date"],
        "CASE_NUMBER":                meta["case_number"],
        "AUTHOR":                     meta["author"],
        "INSTALL_TYPE":               meta["install_type"],
        "CHANNEL":                    meta["channel"],
        "EXEC_SUMMARY":               exec_summary,
        "TOTAL_CHECKS":               str(total),
        "PASS_COUNT":                 str(status_counts.get("PASS", 0)),
        "WARNING_COUNT":              str(status_counts.get("WARNING", 0)),
        "FAIL_COUNT":                 str(status_counts.get("FAIL", 0)),
        "INFO_COUNT":                 str(status_counts.get("INFO", 0)),
        "SKIP_COUNT":                 str(skip_count),
        "FINDING_COUNT":              str(len(findings)),
        "CRITICAL_FINDINGS_SUMMARY":  _build_critical_findings_summary(findings),
        "CLUSTER_ID_TABLE":           _build_cluster_id_table(meta),
        "DATA_COLLECTION_METHOD":     data_collection_method,
        "STATS_TABLE_ROWS":           _build_stats_rows(checks),
        "FINDINGS_NARRATIVE":         findings_narrative,
        "CRITICAL_FINDINGS":          _build_critical_findings(findings),
        "FINDINGS_SECTIONS":          _build_findings_sections(findings, ocp_version=ocp_version),
        "CHECK_RESULTS_7_1":          _build_check_results_table(checks, "7.1", finding_ids_by_check, ocp_version=ocp_version),
        "CHECK_RESULTS_7_2":          _build_check_results_table(checks, "7.2", finding_ids_by_check, ocp_version=ocp_version),
        "CHECK_RESULTS_7_3":          _build_check_results_table(checks, "7.3", finding_ids_by_check, ocp_version=ocp_version),
        "CHECK_RESULTS_7_4":          _build_check_results_table(checks, "7.4", finding_ids_by_check, ocp_version=ocp_version),
        "CHECK_RESULTS_7_5":          _build_check_results_table(checks, "7.5", finding_ids_by_check, ocp_version=ocp_version),
        "CHECK_RESULTS_7_6":          _build_check_results_table(checks, "7.6", finding_ids_by_check, ocp_version=ocp_version),
        "CHECK_RESULTS_7_7":          _build_check_results_table(checks, "7.7", finding_ids_by_check, ocp_version=ocp_version),
        "CHECK_RESULTS_7_8":          _build_check_results_table(checks, "7.8", finding_ids_by_check, ocp_version=ocp_version),
        "CHECK_RESULTS_7_9":          _build_check_results_table(checks, "7.9", finding_ids_by_check, ocp_version=ocp_version),
    }

    result = template
    for key, value in slots.items():
        result = result.replace(f"{{{key}}}", value)
    return result


def find_unfilled_slots(text: str) -> list[str]:
    return re.findall(r"\{[A-Z_]{2,}\}", text)
