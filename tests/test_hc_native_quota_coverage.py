"""Allowlisted tests for native user-project quota coverage (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.day2 import _evaluate_quota_coverage
from hc_report.kb_loader import load_kb


def _quota_status(namespaces_data: dict, resourcequota_data: dict, limitrange_data: dict) -> str:
    checks = _evaluate_quota_coverage(
        namespaces_data, resourcequota_data, limitrange_data, "7.6", "Day-2",
    )
    assert checks[0].check_id == "7.6.quota.coverage"
    return checks[0].status


def test_quota_coverage_fail_when_user_ns_bare() -> None:
    namespaces_data = {"items": [{"metadata": {"name": "app"}}]}
    resourcequota_data = {"items": []}
    limitrange_data = {"items": []}
    assert _quota_status(namespaces_data, resourcequota_data, limitrange_data) == "FAIL"


def test_quota_coverage_pass_when_rq_present() -> None:
    namespaces_data = {"items": [{"metadata": {"name": "app"}}]}
    resourcequota_data = {"items": [{"metadata": {"name": "compute", "namespace": "app"}}]}
    limitrange_data = {"items": []}
    assert _quota_status(namespaces_data, resourcequota_data, limitrange_data) == "PASS"


def test_quota_coverage_skips_openshift_namespace() -> None:
    namespaces_data = {
        "items": [
            {"metadata": {"name": "openshift-monitoring"}},
            {"metadata": {"name": "app"}},
        ]
    }
    resourcequota_data = {"items": [{"metadata": {"name": "compute", "namespace": "app"}}]}
    limitrange_data = {"items": []}
    assert _quota_status(namespaces_data, resourcequota_data, limitrange_data) == "PASS"


def test_quota_alias_not_rq_and_parents_retargeted() -> None:
    knowledge_base = load_kb()
    leaf = knowledge_base.get_entry("7.6.tsr.6_1_1_1_quota_resources_project_assignment")
    assert leaf.content_from == "7.6.quota.coverage"
    assert leaf.include_in_findings is False
    parent = knowledge_base.get_entry("7.6.tsr.6_1_1_quota_and_resources")
    cluster = knowledge_base.get_entry("7.6.tsr.6_1_1_2_cluster_quota_configuration")
    assert parent.content_from == "7.6.quota.coverage"
    assert cluster.content_from == "7.6.quota.coverage"
