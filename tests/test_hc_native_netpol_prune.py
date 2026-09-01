"""Allowlisted tests for native orphan user NetworkPolicies (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.day2 import _evaluate_netpol_orphan
from hc_report.kb_loader import load_kb


def _policy(namespace: str, name: str, match_labels: dict | None) -> dict:
    pod_selector: dict = {}
    if match_labels is not None:
        pod_selector["matchLabels"] = match_labels
    return {
        "metadata": {"name": name, "namespace": namespace},
        "spec": {"podSelector": pod_selector},
    }


def _pod(namespace: str, name: str, labels: dict) -> dict:
    return {
        "metadata": {"name": name, "namespace": namespace, "labels": labels},
        "status": {"phase": "Running"},
    }


def _orphan_status(networkpolicy_data: dict, pods_data: dict) -> str:
    checks = _evaluate_netpol_orphan(networkpolicy_data, pods_data, "7.6", "Day-2")
    assert checks[0].check_id == "7.6.netpol.orphan"
    return checks[0].status


def test_netpol_orphan_fail_when_labels_match_zero_pods() -> None:
    networkpolicy_data = {
        "items": [_policy("app", "deny-web", {"app": "web"})],
    }
    pods_data = {"items": [_pod("app", "db", {"app": "db"})]}
    assert _orphan_status(networkpolicy_data, pods_data) == "FAIL"


def test_netpol_empty_selector_not_orphan() -> None:
    networkpolicy_data = {"items": [_policy("app", "deny-all", None)]}
    pods_data = {"items": []}
    assert _orphan_status(networkpolicy_data, pods_data) == "PASS"


def test_netpol_info_when_no_user_policies() -> None:
    networkpolicy_data = {
        "items": [_policy("openshift-monitoring", "allow", {"app": "prom"})],
    }
    pods_data = {"items": []}
    assert _orphan_status(networkpolicy_data, pods_data) == "INFO"


def test_netpol_alias_not_prune_netpol() -> None:
    knowledge_base = load_kb()
    entry = knowledge_base.get_entry("7.6.tsr.6_1_5_3_network_policy_pruning")
    assert entry.content_from == "7.6.netpol.orphan"
    assert entry.include_in_findings is False
    assert entry.content_from != "7.6.prune.netpol"
