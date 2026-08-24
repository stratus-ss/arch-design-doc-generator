"""Derive findings from check results with EA-quality recommendations."""
from __future__ import annotations

import json
import re
from pathlib import Path

from hc_report.kb_loader import NEEDS_REVIEW_MARKER, load_kb
from hc_report.models import CheckResult, Finding


def _get_impact(check: CheckResult) -> tuple[str, str, str]:
    impact = load_kb().get_impact(check.check_id)
    if impact is None:
        return "", "", ""
    return impact


_P0_KEYWORDS = ("node ready", "cluster operator", "critical alert", "etcd member", "crashloop")
_P2_KEYWORDS = ("cpu", "memory", "disk", "upgrade", "update", "version", "warning alert",
                "channel", "privileged", "not bound", "not default", "deprecated", "automatic")

_PRIORITY_PREFIX: dict[str, str] = {"P0": "6.2.1", "P1": "6.2.2", "P2": "6.2.3", "P3": "6.2.4"}
_VALID_PRIORITY_HINTS = frozenset({"P0", "P1", "P2", "P3"})
_SCORED_CCX_STATUSES = frozenset({"FAIL", "WARNING"})
_SKIP_CCX_GROUPS = frozenset({"skip", "skips"})
_TITLE_KEY_RE = re.compile(r"[^a-z0-9]+")
_UNMAPPED_CCX_RECOMMENDATION = (
    "Review this Red Hat Insights (CCX) result from the TSR export. "
    "It is scored FAIL or WARNING and is not mapped to a Chapter 7 check. "
    "Confirm the Insights message in Observation, then remediate or document "
    "why it is accepted."
)


def _include_in_findings(check: CheckResult) -> bool:
    entry = load_kb().get_entry(check.check_id)
    if entry is None:
        return True
    return entry.include_in_findings


def _finding_on_info(check: CheckResult) -> bool:
    entry = load_kb().get_entry(check.check_id)
    if entry is None:
        return False
    return entry.finding_on_info


def _hinted_priority(check: CheckResult, encoded_priority: str) -> str:
    entry = load_kb().get_entry(check.check_id)
    if entry is None:
        return encoded_priority
    hint = entry.priority_hint
    if hint in _VALID_PRIORITY_HINTS:
        return hint
    return encoded_priority


def _make_finding(
    check: CheckResult,
    priority: str,
    counter: dict[str, int],
    ocp_version: str = "latest",
) -> Finding:
    counter[priority] += 1
    impact, impact_scope, impact_detail = _get_impact(check)
    title = load_kb().get_title(check.check_id) or check.description
    return Finding(
        id=f"{_PRIORITY_PREFIX[priority]}.{counter[priority]}",
        title=title,
        priority=priority,
        description=check.evidence,
        recommendation=_recommendation_for(check, ocp_version),
        impact=impact,
        impact_scope=impact_scope,
        impact_detail=impact_detail,
        check_id=check.check_id,
    )


def _join_member_evidence(members: list[CheckResult]) -> str:
    names: list[str] = []
    seen_names: set[str] = set()
    for member in members:
        name = member.resource_name
        if not name or name in seen_names:
            continue
        names.append(name)
        seen_names.add(name)
    joined_evidence = "\n\n".join(member.evidence for member in members)
    if not names:
        return joined_evidence
    return f"Affected: {', '.join(names)}\n\n{joined_evidence}"


def _make_grouped_finding(
    members: list[CheckResult],
    priority: str,
    counter: dict[str, int],
    ocp_version: str = "latest",
) -> Finding:
    sorted_members = sorted(members, key=lambda member: member.check_id)
    primary = sorted_members[0]
    member_check_ids = tuple(member.check_id for member in sorted_members)
    title = load_kb().get_title(primary.check_id) or primary.description
    for member in sorted_members:
        entry = load_kb().get_entry(member.check_id)
        if entry is None or not entry.finding_group_title:
            continue
        title = entry.finding_group_title
        break
    counter[priority] += 1
    impact, impact_scope, impact_detail = _get_impact(primary)
    return Finding(
        id=f"{_PRIORITY_PREFIX[priority]}.{counter[priority]}",
        title=title,
        priority=priority,
        description=_join_member_evidence(members),
        recommendation=_recommendation_for(primary, ocp_version),
        impact=impact,
        impact_scope=impact_scope,
        impact_detail=impact_detail,
        check_id=primary.check_id,
        member_check_ids=member_check_ids,
    )


def _append_keyword_pairs(
    checks: list[CheckResult],
    keywords: tuple[str, ...],
    priority: str,
    pairs: list[tuple[CheckResult, str]],
) -> None:
    """Append a (check, priority) pair for each check whose description matches a keyword."""
    for check in checks:
        if any(keyword in check.description.lower() for keyword in keywords):
            pairs.append((check, priority))


def _append_remaining_pairs(
    checks: list[CheckResult],
    priority: str,
    pairs: list[tuple[CheckResult, str]],
) -> None:
    """Append remaining checks whose description is not already in the collected pairs."""
    existing_titles = {check.description for check, _ in pairs}
    for check in checks:
        if check.description in existing_titles:
            continue
        pairs.append((check, priority))
        existing_titles.add(check.description)


def _collapse_finding_groups(
    pairs: list[tuple[CheckResult, str]],
) -> list[tuple[list[CheckResult], str]]:
    """Preserve first-seen group order. Ungrouped checks stay singletons."""
    group_members: dict[str, list[CheckResult]] = {}
    group_priority: dict[str, str] = {}
    group_order: list[str] = []
    ungrouped_serial = 0
    for check, priority in pairs:
        entry = load_kb().get_entry(check.check_id)
        group_key = ""
        if entry is not None:
            group_key = entry.finding_group
        if not group_key:
            group_key = f"ungrouped:{ungrouped_serial}"
            ungrouped_serial += 1
        if group_key not in group_members:
            group_order.append(group_key)
            group_members[group_key] = [check]
            group_priority[group_key] = priority
            continue
        group_members[group_key].append(check)
    collapsed: list[tuple[list[CheckResult], str]] = []
    for group_key in group_order:
        collapsed.append((group_members[group_key], group_priority[group_key]))
    return collapsed


def _title_key(text: str) -> str:
    return _TITLE_KEY_RE.sub("", text.lower())


def _recommendation_for(check: CheckResult, ocp_version: str) -> str:
    recommendation = load_kb().get_recommendation(check.check_id, ocp_version=ocp_version)
    if recommendation != NEEDS_REVIEW_MARKER:
        return recommendation
    if check.source != "ccx" or load_kb().get_entry(check.check_id) is not None:
        return recommendation
    return f"{NEEDS_REVIEW_MARKER}\n\n{_UNMAPPED_CCX_RECOMMENDATION}"


def _normalize_ccx_status(raw_status: str) -> str:
    status = raw_status.strip().upper()
    if status == "WARN":
        return "WARNING"
    return status


def _is_scored_ccx_record(record: dict) -> bool:
    if str(record.get("source", "")).lower() != "ccx":
        return False
    group = str(record.get("group", "")).lower()
    tsr_ref = str(record.get("tsr_ref", "")).lower()
    if group in _SKIP_CCX_GROUPS or tsr_ref == "ccx:skip":
        return False
    return _normalize_ccx_status(str(record.get("status", ""))) in _SCORED_CCX_STATUSES


def _check_from_ccx_record(record: dict) -> CheckResult | None:
    check_id = str(record.get("check_id", "")).strip()
    title = str(record.get("title", "")).strip()
    if not check_id or not title:
        return None
    evidence = str(record.get("evidence", "")).strip() or title
    tags = record.get("tags", [])
    return CheckResult(
        category_id=str(record.get("category_id", "7.7") or "7.7"),
        category_name=str(record.get("category_name", "Security and Compliance")),
        check_id=check_id,
        description=title,
        status=_normalize_ccx_status(str(record.get("status", ""))),
        evidence=evidence,
        source="ccx",
        tsr_ref=str(record.get("tsr_ref", "")).strip(),
        tags=tags if isinstance(tags, list) else [],
    )


def scored_ccx_checks_for_findings(
    tsr_records: list[dict],
    existing_checks: list[CheckResult],
) -> list[CheckResult]:
    """CCX FAIL/WARNING leaves that are not already Chapter 7 checks.

    Skip-panel rows stay out. Returned checks are for derive_findings only —
    do not append them to the Chapter 7 check list.
    """
    seen_ids = {check.check_id for check in existing_checks}
    seen_titles = {_title_key(check.description) for check in existing_checks}
    extras: list[CheckResult] = []
    for record in tsr_records:
        if not _is_scored_ccx_record(record):
            continue
        extra = _check_from_ccx_record(record)
        if extra is None:
            continue
        if extra.check_id in seen_ids or _title_key(extra.description) in seen_titles:
            continue
        extras.append(extra)
        seen_ids.add(extra.check_id)
        seen_titles.add(_title_key(extra.description))
    return extras


def _tsr_records_from_path(tsr_runtime_path: Path | None) -> list[dict]:
    if tsr_runtime_path is None or not tsr_runtime_path.is_file():
        return []
    payload = json.loads(tsr_runtime_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    entries = payload.get("checks", []) if isinstance(payload, dict) else []
    if not isinstance(entries, list):
        return []
    return [row for row in entries if isinstance(row, dict)]


def derive_findings_with_tsr(
    checks: list[CheckResult],
    tsr_runtime_path: Path | None,
    ocp_version: str = "latest",
) -> list[Finding]:
    """Derive Chapter 6 findings, adding scored CCX FAIL/WARNING from TSR runtime."""
    extras = scored_ccx_checks_for_findings(
        _tsr_records_from_path(tsr_runtime_path),
        checks,
    )
    return derive_findings(checks, ocp_version=ocp_version, scored_ccx_checks=extras)


def derive_findings(
    checks: list[CheckResult],
    ocp_version: str = "latest",
    *,
    scored_ccx_checks: list[CheckResult] | None = None,
) -> list[Finding]:
    """Group FAIL, WARNING, and INFO-with-finding_on_info checks into P0–P3 findings.

    INFO checks become P3 only when the KB sets finding_on_info; keyword
    P0/P2 lists are not applied to INFO. scored_ccx_checks are findings-only
    and must not be mixed into the Chapter 7 check list by the caller.
    A non-empty valid KB priority_hint overrides status-and-keyword encoding
    (including FAIL to P1 and WARNING to P2).
    """
    finding_checks = list(checks)
    if scored_ccx_checks:
        finding_checks.extend(scored_ccx_checks)
    finding_counter: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    pairs: list[tuple[CheckResult, str]] = []

    fail_checks = [
        check for check in finding_checks if check.status == "FAIL" and check.source != "ccx"
    ]
    warn_checks = [
        check for check in finding_checks
        if check.status == "WARNING" and check.source != "ccx"
    ]
    ccx_fail_checks = [
        check for check in finding_checks if check.status == "FAIL" and check.source == "ccx"
    ]
    ccx_warn_checks = [
        check for check in finding_checks
        if check.status == "WARNING" and check.source == "ccx"
    ]

    _append_keyword_pairs(fail_checks, _P0_KEYWORDS, "P0", pairs)
    _append_remaining_pairs(fail_checks, "P1", pairs)
    _append_keyword_pairs(warn_checks, _P2_KEYWORDS, "P2", pairs)
    _append_remaining_pairs(warn_checks, "P3", pairs)
    _append_remaining_pairs(ccx_fail_checks, "P2", pairs)
    _append_remaining_pairs(ccx_warn_checks, "P3", pairs)
    info_finding_checks = [
        check for check in finding_checks
        if check.status == "INFO" and check.source != "ccx" and _finding_on_info(check)
    ]
    _append_remaining_pairs(info_finding_checks, "P3", pairs)

    hinted_pairs: list[tuple[CheckResult, str]] = []
    for check, priority in pairs:
        hinted_pairs.append((check, _hinted_priority(check, priority)))

    included: list[tuple[CheckResult, str]] = []
    for check, priority in hinted_pairs:
        if _include_in_findings(check):
            included.append((check, priority))

    findings: list[Finding] = []
    for members, priority in _collapse_finding_groups(included):
        if len(members) > 1:
            findings.append(_make_grouped_finding(members, priority, finding_counter, ocp_version))
            continue
        findings.append(_make_finding(members[0], priority, finding_counter, ocp_version))
    return findings
