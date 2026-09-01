"""Allowlisted tests for native effective kubelet systemReserved (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.topology import (
    _check_system_reserved,
    _evaluate_system_reserved_effective,
)


def _nodes_payload(node_name: str, memory: str) -> dict:
    return {
        "items": [
            {
                "metadata": {"name": node_name},
                "status": {"capacity": {"memory": memory}},
            }
        ]
    }


def _gc_payload(node_name: str, reserved_memory: str) -> dict:
    return {
        "members": [
            {
                "node": node_name,
                "system_reserved_memory": reserved_memory,
            }
        ]
    }


def _reserved_status(node_image_gc_data: dict, nodes_data: dict) -> str:
    checks = _evaluate_system_reserved_effective(
        node_image_gc_data, nodes_data, "7.2", "Topology",
    )
    assert checks[0].check_id == "7.2.kubelet.system_reserved"
    return checks[0].status


def test_system_reserved_info_when_default_1gi_large_node() -> None:
    node_name = "master-0.example.com"
    assert _reserved_status(
        _gc_payload(node_name, "1Gi"),
        _nodes_payload(node_name, "70Gi"),
    ) == "INFO"


def test_system_reserved_pass_when_2gi() -> None:
    node_name = "master-0.example.com"
    assert _reserved_status(
        _gc_payload(node_name, "2Gi"),
        _nodes_payload(node_name, "70Gi"),
    ) == "PASS"


def test_system_reserved_warning_when_memory_missing() -> None:
    node_name = "master-0.example.com"
    assert _reserved_status(
        _gc_payload(node_name, ""),
        _nodes_payload(node_name, "70Gi"),
    ) == "WARNING"


def test_system_reserved_does_not_retune_per_node_sysreserved() -> None:
    item = {
        "metadata": {"name": "worker-01.example.com"},
        "status": {"config": {}},
    }
    summary = {
        "roles_with_system_reserved": set(),
        "roles_without_system_reserved": set(),
        "has_global_system_reserved": False,
        "has_any_kubeletconfig": False,
        "has_any_system_reserved": False,
    }
    checks = _check_system_reserved(
        item, "7.2", "Topology", "worker-01", "worker-01.example.com",
        "7.2.1", 70.0, {"worker"}, summary,
    )
    assert checks[0].status == "WARNING"
    assert checks[0].check_id == "7.2.node.worker-01.sysreserved"
