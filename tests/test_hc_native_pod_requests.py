"""Allowlisted tests for native user-pod CPU/memory requests (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.day2 import _evaluate_pod_requests
from hc_report.kb_loader import load_kb


def _pod_item(
    namespace: str,
    name: str,
    *,
    cpu: object = "100m",
    memory: object = "128Mi",
    phase: str = "Running",
) -> dict:
    requests: dict = {}
    if cpu is not None:
        requests["cpu"] = cpu
    if memory is not None:
        requests["memory"] = memory
    return {
        "metadata": {"name": name, "namespace": namespace},
        "status": {"phase": phase},
        "spec": {"containers": [{"name": "app", "resources": {"requests": requests}}]},
    }


def _pod_requests_status(pods_data: dict) -> str:
    checks = _evaluate_pod_requests(pods_data, "7.6", "Day-2")
    assert checks[0].check_id == "7.6.pod.requests"
    return checks[0].status


def test_pod_requests_warning_when_missing_cpu() -> None:
    pods_data = {"items": [_pod_item("app", "web", cpu=None, memory="128Mi")]}
    assert _pod_requests_status(pods_data) == "WARNING"


def test_pod_requests_pass_when_both_set() -> None:
    pods_data = {"items": [_pod_item("app", "web")]}
    assert _pod_requests_status(pods_data) == "PASS"


def test_pod_requests_ignores_openshift_namespace() -> None:
    pods_data = {
        "items": [
            _pod_item("openshift-monitoring", "prom", cpu=None, memory=None),
            _pod_item("app", "web"),
        ]
    }
    assert _pod_requests_status(pods_data) == "PASS"


def test_pod_requests_alias_not_limitranges() -> None:
    knowledge_base = load_kb()
    entry = knowledge_base.get_entry("7.6.tsr.6_1_2_requests_and_limits")
    assert entry.content_from == "7.6.pod.requests"
    assert entry.include_in_findings is False
    assert entry.content_from not in {"7.6.limitranges", "7.6.req_limits"}
