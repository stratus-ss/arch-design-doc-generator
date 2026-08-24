"""Public-contract tests for KB priority_hint override on findings."""
from __future__ import annotations

from hc_report.findings import derive_findings
from hc_report.models import CheckResult

QUOTA_AND_MTV_CHECK_IDS = (
    "7.6.rq",
    "7.6.tsr.6_1_1_quota_and_resources",
    "7.6.tsr.6_1_1_1_quota_resources_project_assignment",
    "7.6.tsr.6_1_1_2_cluster_quota_configuration",
    "7.4.tsr.4_8_5_1_1_quota_and_resources",
    "7.4.tsr.4_12_1_1_1_mtv_installation_and_state",
    "7.4.tsr.4_12_1_1_2_operator_subscription_posture",
    "7.4.tsr.4_12_1_2_mtv_supported_configuration",
)


def make_check_result(
    check_id: str,
    *,
    status: str = "FAIL",
    description: str = "",
    evidence: str = "fail evidence",
) -> CheckResult:
    category_id = "7.4" if check_id.startswith("7.4.") else "7.6"
    return CheckResult(
        category_id=category_id,
        category_name="synthetic",
        check_id=check_id,
        description=description or check_id,
        status=status,
        evidence=evidence,
        source="deterministic",
    )


def test_quota_and_mtv_fail_findings_are_p3() -> None:
    # Bug: Listed quota/MTV FAILs still encode as P1
    # Mutant: Skip _hinted_priority and keep FAIL→P1
    # Contract: public
    for check_id in QUOTA_AND_MTV_CHECK_IDS:
        findings = derive_findings([make_check_result(check_id)])
        assert len(findings) == 1
        assert findings[0].priority == "P3"
        assert findings[0].check_id == check_id


def test_quota_warning_with_p2_keyword_is_p3() -> None:
    # Bug: WARNING with a P2 keyword on a hinted quota check stays P2
    # Mutant: Skip hint so "cpu" in description encodes WARNING as P2
    # Contract: public
    check = make_check_result(
        "7.6.rq",
        status="WARNING",
        description="cpu memory pressure",
        evidence="warn evidence",
    )
    findings = derive_findings([check])
    assert len(findings) == 1
    assert findings[0].priority == "P3"
    assert findings[0].check_id == "7.6.rq"


def test_unhinted_fail_stays_p1() -> None:
    # Bug: Every FAIL becomes P3 once hints exist
    # Mutant: Always return "P3" from _hinted_priority
    # Contract: public
    check = make_check_result(
        "7.6.csr_pending",
        description="Pending CSRs",
        evidence="pending",
    )
    findings = derive_findings([check])
    assert len(findings) == 1
    assert findings[0].priority == "P1"
