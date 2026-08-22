"""Derive findings from check results with EA-quality recommendations."""
from __future__ import annotations

from hc_report.kb_loader import load_kb
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
        recommendation=load_kb().get_recommendation(check.check_id, ocp_version=ocp_version),
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
        recommendation=load_kb().get_recommendation(primary.check_id, ocp_version=ocp_version),
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


def derive_findings(checks: list[CheckResult], ocp_version: str = "latest") -> list[Finding]:
    """Group FAIL, WARNING, and INFO-with-finding_on_info checks into P0–P3 findings.

    INFO checks become P3 only when the KB sets finding_on_info; keyword
    P0/P2 lists are not applied to INFO.
    """
    finding_counter: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    pairs: list[tuple[CheckResult, str]] = []

    fail_checks = [check for check in checks if check.status == "FAIL" and check.source != "ccx"]
    warn_checks = [check for check in checks if check.status == "WARNING" and check.source != "ccx"]
    ccx_fail_checks = [check for check in checks if check.status == "FAIL" and check.source == "ccx"]
    ccx_warn_checks = [check for check in checks if check.status == "WARNING" and check.source == "ccx"]

    _append_keyword_pairs(fail_checks, _P0_KEYWORDS, "P0", pairs)
    _append_remaining_pairs(fail_checks, "P1", pairs)
    _append_keyword_pairs(warn_checks, _P2_KEYWORDS, "P2", pairs)
    _append_remaining_pairs(warn_checks, "P3", pairs)
    _append_remaining_pairs(ccx_fail_checks, "P2", pairs)
    _append_remaining_pairs(ccx_warn_checks, "P3", pairs)
    info_finding_checks = [
        check for check in checks
        if check.status == "INFO" and check.source != "ccx" and _finding_on_info(check)
    ]
    _append_remaining_pairs(info_finding_checks, "P3", pairs)

    included: list[tuple[CheckResult, str]] = []
    for check, priority in pairs:
        if _include_in_findings(check):
            included.append((check, priority))

    findings: list[Finding] = []
    for members, priority in _collapse_finding_groups(included):
        if len(members) > 1:
            findings.append(_make_grouped_finding(members, priority, finding_counter, ocp_version))
            continue
        findings.append(_make_finding(members[0], priority, finding_counter, ocp_version))
    return findings
