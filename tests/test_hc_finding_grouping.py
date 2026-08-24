"""Public-contract tests for Chapter 6 finding grouping and suppression."""
from __future__ import annotations

from hc_report.findings import (
    derive_findings,
    scored_ccx_checks_for_findings,
)
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


def test_day2_default_sc_is_hidden_from_findings() -> None:
    engine_id = "7.3.storage.default_sc"
    day2_id = "7.6.storage.default_sc"
    checks = [
        _check_result(engine_id, "[FAIL] - reason: no default StorageClass"),
        _check_result(day2_id, "[FAIL] - reason: no default StorageClass"),
    ]
    findings = derive_findings(checks)
    assert len(findings) == 1
    assert findings[0].check_id == engine_id
    assert day2_id not in findings[0].member_check_ids


def test_day2_pvcs_is_hidden_from_findings() -> None:
    engine_id = "7.3.storage.pvcs"
    day2_id = "7.6.storage.pvcs"
    checks = [
        _check_result(engine_id, "[FAIL] - reason: PVC not Bound"),
        _check_result(day2_id, "[FAIL] - reason: PVC not Bound"),
    ]
    findings = derive_findings(checks)
    assert len(findings) == 1
    assert findings[0].check_id == engine_id
    assert day2_id not in findings[0].member_check_ids


def test_operator_approval_groups_and_hides_day2() -> None:
    engine_id = "7.1.subs.approval"
    tsr_id = "7.3.tsr.3_2_3_operators_plan_approval"
    day2_id = "7.6.op_approval"
    checks = [
        _check_result(engine_id, "[FAIL] - reason: Automatic approval"),
        _check_result(tsr_id, "[FAIL] - reason: Automatic approval"),
        _check_result(day2_id, "[FAIL] - reason: Automatic approval"),
    ]
    findings = derive_findings(checks)
    assert len(findings) == 1
    finding = findings[0]
    assert engine_id in finding.member_check_ids
    assert tsr_id in finding.member_check_ids
    assert day2_id not in finding.member_check_ids
    assert finding.title == "Operator subscription installPlanApproval"


def test_dns_operator_and_tsr_5_12_group() -> None:
    engine_id = "7.3.dns.operator"
    tsr_id = "7.5.tsr.5_12_dns_health"
    checks = [
        _check_result(engine_id, "[FAIL] - reason: DNS Operator Degraded"),
        _check_result(tsr_id, "[FAIL] - reason: CoreDNS latency"),
    ]
    findings = derive_findings(checks)
    assert len(findings) == 1
    finding = findings[0]
    assert engine_id in finding.member_check_ids
    assert tsr_id in finding.member_check_ids
    assert finding.title == "DNS Operator / CoreDNS health"


def test_registry_tsr_and_ccx_group_keeps_ccx_member() -> None:
    tsr_id = "7.5.tsr.5_4_registry_health"
    ccx_id = "7.7.ccx_internal.image_registry_pods"
    checks = [
        _check_result(tsr_id, "[FAIL] - reason: registry pods unhealthy"),
        _check_result(ccx_id, "[FAIL] - reason: registry pods unhealthy", source="ccx"),
    ]
    findings = derive_findings(checks)
    assert len(findings) == 1
    finding = findings[0]
    assert tsr_id in finding.member_check_ids
    assert ccx_id in finding.member_check_ids


def test_apiserver_audit_and_tsr_7_1_2_group() -> None:
    engine_id = "7.6.apiserver.audit"
    tsr_id = "7.7.tsr.7_1_2_auditing"
    checks = [
        _check_result(engine_id, "[FAIL] - reason: Default audit profile"),
        _check_result(tsr_id, "[FAIL] - reason: Default audit profile"),
    ]
    findings = derive_findings(checks)
    assert len(findings) == 1
    finding = findings[0]
    assert engine_id in finding.member_check_ids
    assert tsr_id in finding.member_check_ids


def test_denied_csr_row_still_creates_finding() -> None:
    check_id = "7.7.csr"
    checks = [_check_result(check_id, "[FAIL] - reason: CSR Denied")]
    findings = derive_findings(checks)
    assert len(findings) == 1
    assert findings[0].check_id == check_id


# Bug: Scored CCX FAIL/WARNING absent from Chapter 7 never becomes a Chapter 6 finding
# Mutant: Ignore scored_ccx_checks in derive_findings
# Contract: public
def test_unmatched_scored_ccx_fail_becomes_finding() -> None:
    existing = [_check_result("7.1.identity.channel", "[PASS] channel ok", status="PASS")]
    extras = scored_ccx_checks_for_findings(
        [
            {
                "source": "ccx",
                "group": "external",
                "status": "FAIL",
                "check_id": "7.7.ccx_external.mcp_set_to_pause",
                "title": "Mcp Set To Pause",
                "evidence": "pool master is paused",
                "tsr_ref": "CCX:external",
                "category_id": "7.7",
                "category_name": "Security and Compliance",
            },
            {
                "source": "ccx",
                "group": "skip",
                "status": "FAIL",
                "check_id": "7.7.ccx_skip.ignored_skip_panel",
                "title": "Ignored Skip Panel",
                "evidence": "not applicable",
                "tsr_ref": "CCX:skip",
            },
            {
                "source": "ccx",
                "group": "internal",
                "status": "PASS",
                "check_id": "7.7.ccx_internal.version_check",
                "title": "Version Check",
                "evidence": "supported",
                "tsr_ref": "CCX:internal",
            },
        ],
        existing,
    )
    findings = derive_findings(existing, scored_ccx_checks=extras)
    assert [extra.check_id for extra in extras] == ["7.7.ccx_external.mcp_set_to_pause"]
    assert len(findings) == 1
    assert findings[0].check_id == "7.7.ccx_external.mcp_set_to_pause"
    assert findings[0].priority == "P2"
    assert "not mapped to a Chapter 7 check" in findings[0].recommendation


# Bug: Catalog CCX FAIL already in Chapter 7 is emitted twice in Chapter 6
# Mutant: Skip the existing-id / existing-title filter
# Contract: public
def test_catalog_ccx_fail_is_not_duplicated() -> None:
    existing = [
        _check_result(
            "7.7.ccx_internal.pods_check",
            "[FAIL] - reason: crashloop",
            source="ccx",
            description="Pods Check",
        )
    ]
    extras = scored_ccx_checks_for_findings(
        [
            {
                "source": "ccx",
                "group": "internal",
                "status": "FAIL",
                "check_id": "7.7.ccx_internal.pods_check",
                "title": "Pods Check",
                "evidence": "crashloop",
                "tsr_ref": "CCX:internal",
            }
        ],
        existing,
    )
    findings = derive_findings(existing, scored_ccx_checks=extras)
    assert extras == []
    assert len(findings) == 1
    assert findings[0].check_id == "7.7.ccx_internal.pods_check"
