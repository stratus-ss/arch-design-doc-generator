"""Public-contract tests for Chapter 6 finding grouping and suppression."""
from __future__ import annotations

from hc_report.findings import derive_findings
from hc_report.models import CheckResult


def _check_result(
    check_id: str,
    evidence: str,
    *,
    status: str = "FAIL",
    description: str = "",
    resource_name: str = "",
    source: str = "deterministic",
) -> CheckResult:
    return CheckResult(
        category_id="7.9",
        category_name="synthetic",
        check_id=check_id,
        description=description or check_id,
        status=status,
        evidence=evidence,
        resource_name=resource_name,
        source=source,
    )


def test_logging_not_configured_group_is_one_finding() -> None:
    checks = [
        _check_result(
            "7.4.tsr.4_1_2_logging_storage_type",
            "[FAIL] - reason: no instance configuration",
        ),
        _check_result(
            "7.4.tsr.4_1_4_logging_pod_status",
            "[FAIL] - reason: no pod found",
        ),
        _check_result(
            "7.4.tsr.4_1_5_2_loki_health",
            "[FAIL] - reason: no instance configuration",
        ),
    ]
    findings = derive_findings(checks)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.check_id == "7.4.tsr.4_1_2_logging_storage_type"
    assert len(finding.member_check_ids) == 3
    assert "7.4.tsr.4_1_2_logging_storage_type" in finding.member_check_ids
    assert "7.4.tsr.4_1_4_logging_pod_status" in finding.member_check_ids
    assert "7.4.tsr.4_1_5_2_loki_health" in finding.member_check_ids
    assert finding.title == "Cluster logging is not configured (no LokiStack)"
    assert finding.priority == "P1"


def test_logging_forwarders_and_scc_stay_separate() -> None:
    logging_storage = "7.4.tsr.4_1_2_logging_storage_type"
    logging_pods = "7.4.tsr.4_1_4_logging_pod_status"
    logging_loki = "7.4.tsr.4_1_5_2_loki_health"
    forwarder_id = "7.4.tsr.4_1_6_cluster_log_forwarders"
    logging_scc = "7.4.tsr.4_1_8_logging_security_context_constraints"
    checks = [
        _check_result(logging_storage, "[FAIL] - reason: no instance configuration"),
        _check_result(logging_pods, "[FAIL] - reason: no pod found"),
        _check_result(logging_loki, "[FAIL] - reason: no instance configuration"),
        _check_result(forwarder_id, "[FAIL] - reason: multi log forwarder"),
        _check_result(logging_scc, "[FAIL] - reason: logging SCC missing"),
    ]
    findings = derive_findings(checks)
    logging_finding = None
    forwarder_finding = None
    scc_finding = None
    for finding in findings:
        if finding.check_id == logging_storage:
            logging_finding = finding
        elif finding.check_id == forwarder_id:
            forwarder_finding = finding
        elif finding.check_id == logging_scc:
            scc_finding = finding
    assert logging_finding is not None
    assert forwarder_finding is not None
    assert scc_finding is not None
    assert len(findings) == 3
    assert logging_pods in logging_finding.member_check_ids
    assert logging_loki in logging_finding.member_check_ids
    assert forwarder_id not in logging_finding.member_check_ids
    assert logging_scc not in logging_finding.member_check_ids
    assert forwarder_finding.check_id == forwarder_id
    assert scc_finding.check_id == logging_scc


def test_sysreserved_group_lists_node_names() -> None:
    checks = [
        _check_result(
            "7.2.node.node-a.sysreserved",
            "[WARNING] - reason: systemReserved memory missing",
            status="WARNING",
            description="7.2.1.7 systemReserved: node-a",
            resource_name="node-a",
        ),
        _check_result(
            "7.2.node.node-b.sysreserved",
            "[WARNING] - reason: systemReserved memory missing",
            status="WARNING",
            description="7.2.1.7 systemReserved: node-b",
            resource_name="node-b",
        ),
    ]
    findings = derive_findings(checks)
    assert len(findings) == 1
    finding = findings[0]
    assert "node-a" in finding.description
    assert "node-b" in finding.description
    assert "Affected:" in finding.description
    assert len(finding.member_check_ids) == 2


def test_tsr_and_ccx_webhooks_are_not_findings() -> None:
    tsr_webhooks = "7.3.tsr.3_13_webhooks"
    ccx_webhooks = "7.7.ccx_internal.webhooks_check"
    checks = [
        _check_result(tsr_webhooks, "[FAIL] - reason: Failure Policy"),
        _check_result(ccx_webhooks, "[FAIL] - reason: webhook connectivity", source="ccx"),
    ]
    findings = derive_findings(checks)
    for finding in findings:
        assert finding.check_id != tsr_webhooks
        assert finding.check_id != ccx_webhooks
        assert tsr_webhooks not in finding.member_check_ids
        assert ccx_webhooks not in finding.member_check_ids


def test_validating_webhook_fail_still_creates_finding() -> None:
    check_id = "7.3.webhooks.validatingwebhooks"
    checks = [_check_result(check_id, "[FAIL] - reason: timeoutSeconds")]
    findings = derive_findings(checks)
    assert len(findings) == 1
    assert findings[0].check_id == check_id
