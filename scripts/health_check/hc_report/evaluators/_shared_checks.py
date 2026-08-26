"""Shared evaluator helpers for reused check patterns."""
from __future__ import annotations

from hc_report.evaluators._common import (
    _find_condition,
    _get_items,
    _is_missing,
    _resource_labels,
)


def node_roles(labels: dict) -> set[str]:
    """Return normalized node-role names from node labels."""
    return {
        key.replace("node-role.kubernetes.io/", "")
        for key in labels
        if key.startswith("node-role.kubernetes.io/")
    }


def is_compact_cluster(items: list[dict], masters: list[dict]) -> bool:
    """True when every node is a master and every master also carries the
    'worker' role label — the supported 3-node compact/SNO-style topology
    where schedulable control-plane nodes are expected, not a misconfiguration.
    """
    if not masters or len(masters) != len(items):
        return False
    return all("worker" in node_roles(_resource_labels(node)) for node in masters)


def check_mcp_degraded(machine_config_pool_data: dict) -> tuple[list[str], list[str]]:
    """Return degraded and updating MachineConfigPool resource names."""
    if _is_missing(machine_config_pool_data):
        return [], []

    degraded: list[str] = []
    updating: list[str] = []
    for item in _get_items(machine_config_pool_data, default_single=True):
        name = item.get("metadata", {}).get("name", "?")
        conditions = item.get("status", {}).get("conditions", [])
        if _find_condition(conditions, "Degraded").get("status") == "True":
            degraded.append(name)
        if _find_condition(conditions, "Updating").get("status") == "True":
            updating.append(name)
    return degraded, updating


def check_csr_pending(csr_data: dict) -> tuple[list[str], list[str], list[str]]:
    """Return pending, approved, and denied CertificateSigningRequest names."""
    if _is_missing(csr_data):
        return [], [], []

    pending: list[str] = []
    approved: list[str] = []
    denied: list[str] = []
    for item in _get_items(csr_data):
        name = item.get("metadata", {}).get("name", "")
        conditions = item.get("status", {}).get("conditions", [])
        if not conditions:
            pending.append(name)
            continue
        if any(condition.get("type") == "Approved" for condition in conditions):
            approved.append(name)
        if any(condition.get("type") == "Denied" for condition in conditions):
            denied.append(name)
    return pending, approved, denied


def find_degraded_operators(cluster_operator_data: dict) -> list[str]:
    """Return cluster operator names with a Degraded condition."""
    if _is_missing(cluster_operator_data):
        return []

    degraded: list[str] = []
    for item in _get_items(cluster_operator_data, default_single=True):
        conditions = item.get("status", {}).get("conditions", [])
        if _find_condition(conditions, "Degraded").get("status") == "True":
            degraded.append(item.get("metadata", {}).get("name", "?"))
    return degraded
