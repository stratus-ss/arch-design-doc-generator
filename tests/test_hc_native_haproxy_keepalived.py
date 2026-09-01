"""Allowlisted tests for native keepalived VIP pods (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.topology import _evaluate_keepalived_pods
from hc_report.kb_loader import load_kb


def _keepalived_pod(name: str, phase: str = "Running", ready: bool = True) -> dict:
    return {
        "metadata": {"namespace": "openshift-kni-infra", "name": name},
        "status": {
            "phase": phase,
            "containerStatuses": [
                {"name": "keepalived", "ready": ready},
                {"name": "keepalived-monitor", "ready": ready},
            ],
        },
    }


def _keepalived_status(pods_data: dict) -> str:
    checks = _evaluate_keepalived_pods(pods_data, "7.2", "Topology Checks")
    assert checks[0].check_id == "7.2.topo.keepalived"
    return checks[0].status


def test_keepalived_pass_when_ready() -> None:
    pods_data = {
        "items": [
            _keepalived_pod("keepalived-master-0"),
            _keepalived_pod("keepalived-master-1"),
        ],
    }
    assert _keepalived_status(pods_data) == "PASS"


def test_keepalived_fail_when_not_ready() -> None:
    pods_data = {
        "items": [
            _keepalived_pod("keepalived-master-0"),
            _keepalived_pod("keepalived-master-1", ready=False),
        ],
    }
    assert _keepalived_status(pods_data) == "FAIL"


def test_keepalived_info_when_no_pods() -> None:
    pods_data = {
        "items": [
            {
                "metadata": {
                    "namespace": "openshift-ingress",
                    "name": "router-default-abc",
                },
                "status": {"phase": "Running"},
            },
        ],
    }
    assert _keepalived_status(pods_data) == "INFO"


def test_keepalived_does_not_retarget_haproxy_tsr() -> None:
    knowledge_base = load_kb()
    entry = knowledge_base.get_entry("7.2.tsr.2_2_3_haproxy_ha")
    native = knowledge_base.get_entry("7.2.topo.keepalived")
    assert entry.content_from == "7.2.topo.haproxy_ha"
    assert native is not None
