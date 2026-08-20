"""Derive findings from check results with EA-quality recommendations."""
from __future__ import annotations

from hc_report.kb_loader import NEEDS_REVIEW_MARKER, load_kb
from hc_report.models import CheckResult, Finding

_CATEGORY_FALLBACK: dict[str, tuple[str, str]] = {
    "7.1": (
        "Review cluster identity and base platform state with `oc get clusterversion` and "
        "`oc get clusteroperator`. Inspect node readiness via `oc get nodes` and subscription "
        "health with `oc get subscription -A`.",
        "https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/architecture/index",
    ),
    "7.2": (
        "Verify topology consistency with `oc get nodes -o wide` and check etcd member health "
        "using `oc get etcd cluster -o yaml`. Review MachineConfigPool status: "
        "`oc get machineconfigpool`.",
        "https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/architecture/index#about-control-planes_architecture-overview",
    ),
    "7.3": (
        "Check component health with `oc get co` for operator status, `oc get pods -n <ns>` "
        "for the affected namespace, and review events with `oc get events -A --sort-by=.lastTimestamp`. "
        "Inspect relevant operator logs for error details.",
        "https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/operators/index",
    ),
    "7.4": (
        "Review the layered product operator status with `oc get csv -A` and check pod health "
        "in the product namespace. Inspect the product's primary CR status conditions for "
        "degraded or progressing states.",
        "https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/operators/index",
    ),
    "7.5": (
        "Assess cluster health with `oc get nodes` for node conditions, `oc get co` for operator "
        "state, and `oc adm top nodes` for resource utilization. Review firing alerts via "
        "`oc get --raw /api/v1/namespaces/openshift-monitoring/services/alertmanager-main:web/proxy/api/v2/alerts`.",
        "https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/support/index#about-toolbox_gathering-cluster-data",
    ),
    "7.6": (
        "Review day-2 operational posture: check resource quotas with `oc get resourcequota -A`, "
        "node utilization via `oc adm top nodes`, and update history with "
        "`oc get clusterversion -o jsonpath='{.status.history}'`.",
        "https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/nodes/index",
    ),
    "7.7": (
        "Audit security posture: review SCCs with `oc get scc`, check OAuth configuration via "
        "`oc get oauth cluster -o yaml`, and inspect cluster role bindings with "
        "`oc get clusterrolebinding`. Run compliance scans if the Compliance Operator is installed.",
        "https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/security_and_compliance/index",
    ),
}


def _get_recommendation(check: CheckResult, ocp_version: str = "latest") -> str:
    """Return a detailed recommendation for the check, preferring the KB."""
    kb_recommendation = load_kb().get_recommendation(check.check_id, ocp_version)
    if kb_recommendation != NEEDS_REVIEW_MARKER:
        return kb_recommendation
    category = check.check_id.split(".")[0] + "." + check.check_id.split(".")[1] if "." in check.check_id else ""
    fallback_text, fallback_link = _CATEGORY_FALLBACK.get(category, (
        "Review the check evidence and consult Red Hat documentation for remediation guidance.",
        "https://docs.redhat.com/en/documentation/openshift_container_platform/latest",
    ))
    return f"{fallback_text}\n\nReference: {fallback_link}"


def _get_impact(check: CheckResult) -> tuple[str, str, str]:
    impact = load_kb().get_impact(check.check_id)
    if impact is None:
        return "", "", ""
    return impact


_P0_KEYWORDS = ("node ready", "cluster operator", "critical alert", "etcd member", "crashloop")
_P2_KEYWORDS = ("cpu", "memory", "disk", "upgrade", "update", "version", "warning alert",
                "channel", "privileged", "not bound", "not default", "deprecated", "automatic")

_PRIORITY_PREFIX: dict[str, str] = {"P0": "6.2.1", "P1": "6.2.2", "P2": "6.2.3", "P3": "6.2.4"}


def _make_finding(
    check: CheckResult,
    priority: str,
    counter: dict[str, int],
    ocp_version: str = "latest",
) -> Finding:
    counter[priority] += 1
    impact, impact_scope, impact_detail = _get_impact(check)
    return Finding(
        id=f"{_PRIORITY_PREFIX[priority]}.{counter[priority]}",
        title=check.description,
        priority=priority,
        description=check.evidence,
        recommendation=_get_recommendation(check, ocp_version=ocp_version),
        impact=impact,
        impact_scope=impact_scope,
        impact_detail=impact_detail,
        check_id=check.check_id,
    )


def _append_keyword_findings(
    checks: list[CheckResult], keywords: tuple[str, ...], priority: str,
    counter: dict[str, int], findings: list[Finding], ocp_version: str = "latest",
) -> None:
    """Append a finding for each check whose description matches one of the given keywords."""
    for check in checks:
        if any(keyword in check.description.lower() for keyword in keywords):
            findings.append(_make_finding(check, priority, counter, ocp_version))


def _append_remaining_findings(
    checks: list[CheckResult],
    priority: str,
    counter: dict[str, int],
    findings: list[Finding],
    ocp_version: str = "latest",
) -> None:
    """Append a finding for each check not already represented by an existing finding title."""
    existing_titles = {finding.title for finding in findings}
    for check in checks:
        if check.description not in existing_titles:
            findings.append(_make_finding(check, priority, counter, ocp_version))
            existing_titles.add(check.description)


def derive_findings(checks: list[CheckResult], ocp_version: str = "latest") -> list[Finding]:
    """Group FAIL and WARNING checks (excluding INFO) into P0–P3 findings."""
    findings: list[Finding] = []
    finding_counter: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}

    fail_checks = [check for check in checks if check.status == "FAIL" and check.source != "ccx"]
    warn_checks = [check for check in checks if check.status == "WARNING" and check.source != "ccx"]
    ccx_fail_checks = [check for check in checks if check.status == "FAIL" and check.source == "ccx"]
    ccx_warn_checks = [check for check in checks if check.status == "WARNING" and check.source == "ccx"]

    _append_keyword_findings(fail_checks, _P0_KEYWORDS, "P0", finding_counter, findings, ocp_version)
    _append_remaining_findings(fail_checks, "P1", finding_counter, findings, ocp_version)
    _append_keyword_findings(warn_checks, _P2_KEYWORDS, "P2", finding_counter, findings, ocp_version)
    _append_remaining_findings(warn_checks, "P3", finding_counter, findings, ocp_version)
    _append_remaining_findings(ccx_fail_checks, "P2", finding_counter, findings, ocp_version)
    _append_remaining_findings(ccx_warn_checks, "P3", finding_counter, findings, ocp_version)

    return findings
