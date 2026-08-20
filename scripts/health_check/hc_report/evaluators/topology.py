"""Evaluators for 7.2 Topology Checks."""
from __future__ import annotations

from typing import NamedTuple

from hc_report.evaluators._common import (
    _MASTER_MIN_CPU,
    _MASTER_MIN_MEM_GIB,
    _MIN_DISK_DOCUMENTATION_URL,
    _MIN_DISK_GIB,
    _WORKER_MIN_CPU,
    _WORKER_MIN_MEM_GIB,
    _find_condition,
    _get_items,
    _is_missing,
    _node_capacity,
    _node_info,
    _not_applicable,
    _parse_cpu_cores,
    _parse_lsblk_size_gib,
    _parse_quantity_gib,
    _resource_labels,
    _resource_metadata,
    _resource_status,
)
from hc_report.evaluators._shared_checks import node_roles
from hc_report.models import CheckResult


class _NodeContext(NamedTuple):
    """Identity fields shared by all per-node check functions."""

    category_id: str
    category_name: str
    short_name: str
    name: str
    role_prefix: str


def _kubeletconfig_pool_roles(item: dict) -> set[str]:
    """Extract MCP role names from KubeletConfig selector labels."""
    selector = item.get("spec", {}).get("machineConfigPoolSelector", {}).get("matchLabels", {})
    prefix = "pools.operator.machineconfiguration.openshift.io/"
    return {
        key[len(prefix):]
        for key in selector
        if key.startswith(prefix)
    }


def _summarize_kubeletconfig_system_reserved(kubeletconfig_data: dict) -> dict:
    """Build role-based systemReserved coverage from KubeletConfig resources."""
    summary = {
        "has_any_kubeletconfig": False,
        "has_any_system_reserved": False,
        "has_global_system_reserved": False,
        "roles_with_system_reserved": set(),
        "roles_without_system_reserved": set(),
    }
    if _is_missing(kubeletconfig_data):
        return summary

    items = _get_items(kubeletconfig_data)
    if not items:
        return summary

    summary["has_any_kubeletconfig"] = True
    for item in items:
        spec = item.get("spec", {})
        kubelet_config = spec.get("kubeletConfig", {})
        has_system_reserved = bool(kubelet_config.get("systemReserved"))
        roles = _kubeletconfig_pool_roles(item)

        if has_system_reserved:
            summary["has_any_system_reserved"] = True

        if roles:
            if has_system_reserved:
                summary["roles_with_system_reserved"].update(roles)
            else:
                summary["roles_without_system_reserved"].update(roles)
            continue

        if has_system_reserved:
            summary["has_global_system_reserved"] = True

    return summary


def _check_node_conditions(conditions: list, node_context: _NodeContext, role_label: str) -> CheckResult:
    ready_condition = _find_condition(conditions, "Ready")
    memory_pressure = _find_condition(conditions, "MemoryPressure")
    disk_pressure = _find_condition(conditions, "DiskPressure")
    pid_pressure = _find_condition(conditions, "PIDPressure")

    if ready_condition.get("status") != "True":
        ready_status, ready_evidence = "FAIL", f"Node not Ready: {ready_condition.get('message', '')[:150]}"
    elif memory_pressure.get("status") == "True":
        ready_status, ready_evidence = "WARNING", "MemoryPressure condition active"
    elif disk_pressure.get("status") == "True":
        ready_status, ready_evidence = "WARNING", "DiskPressure condition active"
    elif pid_pressure.get("status") == "True":
        ready_status, ready_evidence = "WARNING", "PIDPressure condition active"
    else:
        ready_status, ready_evidence = "PASS", f"Ready. Role: {role_label}"
    return CheckResult(node_context.category_id, node_context.category_name, f"{node_context.category_id}.node.{node_context.short_name}.ready",
                        f"{node_context.role_prefix}.1 Node Ready: {node_context.short_name}", ready_status, ready_evidence, node_context.name)


def _check_node_os(node_info: dict, node_context: _NodeContext) -> CheckResult:
    os_image = node_info.get("osImage", "unknown")
    kernel = node_info.get("kernelVersion", "unknown")
    return CheckResult(node_context.category_id, node_context.category_name, f"{node_context.category_id}.node.{node_context.short_name}.os",
                        f"{node_context.role_prefix}.2 OS Version: {node_context.short_name}", "INFO",
                        f"{os_image}. Kernel: {kernel}", node_context.name)


def _check_node_cpu(capacity: dict, node_context: _NodeContext, min_cpu: float, role_label: str) -> CheckResult:
    cpu_cores = _parse_cpu_cores(capacity.get("cpu", "0"))
    cpu_status = "FAIL" if cpu_cores < min_cpu else "PASS"
    cpu_evidence = (f"{cpu_cores:.0f} cores — below minimum {min_cpu} for {role_label} nodes"
              if cpu_status == "FAIL"
              else f"{cpu_cores:.0f} cores (minimum {min_cpu} required for {role_label})")
    return CheckResult(node_context.category_id, node_context.category_name, f"{node_context.category_id}.node.{node_context.short_name}.cpu",
                        f"{node_context.role_prefix}.3 CPU: {node_context.short_name}", cpu_status, cpu_evidence, node_context.name)


def _check_node_memory(capacity: dict, node_context: _NodeContext, min_memory: float, role_label: str) -> tuple[CheckResult, float]:
    memory_gib = _parse_quantity_gib(capacity.get("memory", "0"))
    memory_status = "FAIL" if memory_gib < min_memory else "PASS"
    memory_evidence = (f"{memory_gib:.1f} GiB — below minimum {min_memory} GiB for {role_label} nodes"
              if memory_status == "FAIL"
              else f"{memory_gib:.1f} GiB (minimum {min_memory} GiB required)")
    result = CheckResult(node_context.category_id, node_context.category_name, f"{node_context.category_id}.node.{node_context.short_name}.memory",
                          f"{node_context.role_prefix}.4 Memory: {node_context.short_name}", memory_status, memory_evidence, node_context.name)
    return result, memory_gib


def _lookup_actual_disk_gib(hardware_data: dict, short_name: str) -> float | None:
    """Look up the largest physical disk (GiB) for a node from 11_hardware sysinfo
    data, if it was collected. Returns None when unavailable so callers can fall
    back to the node's reported ephemeral-storage capacity.
    """
    node_hardware = hardware_data.get(f"node_hw_{short_name}", {})
    if not node_hardware or node_hardware.get("_hc_error") or node_hardware.get("_hc_not_found"):
        return None
    disk_sizes = [_parse_lsblk_size_gib(disk.get("size", "0")) for disk in node_hardware.get("disks", [])]
    disk_sizes = [size for size in disk_sizes if size > 0]
    return max(disk_sizes) if disk_sizes else None


def _check_node_disk(capacity: dict, node_context: _NodeContext, hardware_data: dict | None = None) -> CheckResult:
    actual_disk_gib = _lookup_actual_disk_gib(hardware_data or {}, node_context.short_name)
    if actual_disk_gib is not None:
        disk_gib, signal_source = actual_disk_gib, "actual disk size (sysinfo)"
    else:
        disk_gib = _parse_quantity_gib(capacity.get("ephemeral-storage", "0"))
        signal_source = "ephemeral-storage capacity"
    disk_status = "WARNING" if disk_gib < _MIN_DISK_GIB else "PASS"
    disk_evidence = (f"{disk_gib:.1f} GiB ({signal_source}) — below recommended {_MIN_DISK_GIB} GiB minimum"
               if disk_status == "WARNING"
               else f"{disk_gib:.1f} GiB ({signal_source}), meets {_MIN_DISK_GIB} GiB minimum")
    return CheckResult(node_context.category_id, node_context.category_name, f"{node_context.category_id}.node.{node_context.short_name}.disk",
                        f"{node_context.role_prefix}.5 Disk: {node_context.short_name}", disk_status, disk_evidence, node_context.name,
                        doc_ref=_MIN_DISK_DOCUMENTATION_URL)


def _check_node_kubelet(node_info: dict, node_context: _NodeContext) -> CheckResult:
    kubelet_version = node_info.get("kubeletVersion", "unknown")
    container_runtime = node_info.get("containerRuntimeVersion", "unknown")
    return CheckResult(node_context.category_id, node_context.category_name, f"{node_context.category_id}.node.{node_context.short_name}.kubelet",
                        f"{node_context.role_prefix}.6 Kubelet Version: {node_context.short_name}", "INFO",
                        f"kubelet {kubelet_version}. CRI: {container_runtime}", node_context.name)


def _check_single_node(
    item: dict, category_id: str, category_name: str, role_prefix: str, kubeletconfig_summary: dict,
    hardware_data: dict | None = None,
) -> list[CheckResult]:
    """Produce the per-node hardware checks (ready, OS, CPU, memory, disk, kubelet)."""
    name = item.get("metadata", {}).get("name", "unknown")
    short_name = name.split(".")[0]
    node_status = item.get("status", {})
    conditions = node_status.get("conditions", [])
    node_info = node_status.get("nodeInfo", {})
    capacity = node_status.get("capacity", {})
    labels = item.get("metadata", {}).get("labels", {})

    roles = node_roles(labels)
    is_master = "master" in roles or "control-plane" in roles
    min_cpu = _MASTER_MIN_CPU if is_master else _WORKER_MIN_CPU
    min_memory = _MASTER_MIN_MEM_GIB if is_master else _WORKER_MIN_MEM_GIB
    role_label = "/".join(sorted(roles)) if roles else "worker"

    node_context = _NodeContext(category_id, category_name, short_name, name, role_prefix)
    memory_check, memory_gib = _check_node_memory(capacity, node_context, min_memory, role_label)

    checks: list[CheckResult] = [
        _check_node_conditions(conditions, node_context, role_label),
        _check_node_os(node_info, node_context),
        _check_node_cpu(capacity, node_context, min_cpu, role_label),
        memory_check,
        _check_node_disk(capacity, node_context, hardware_data),
        _check_node_kubelet(node_info, node_context),
    ]
    checks += _check_system_reserved(
        item, category_id, category_name, short_name, name, role_prefix, memory_gib, roles, kubeletconfig_summary,
    )
    return checks


def _check_system_reserved(
    item: dict, category_id: str, category_name: str, short_name: str, name: str,
    role_prefix: str, memory_gib: float, node_roles: set[str], kubeletconfig_summary: dict,
) -> list[CheckResult]:
    """Check systemReserved memory configuration."""
    if memory_gib < 64.0:
        return []

    kubelet_config = item.get("status", {}).get("config", {})
    if kubelet_config.get("systemReserved"):
        return []

    roles_with_reserved = kubeletconfig_summary.get("roles_with_system_reserved", set())
    roles_without_reserved = kubeletconfig_summary.get("roles_without_system_reserved", set())
    has_global_reserved = bool(kubeletconfig_summary.get("has_global_system_reserved"))
    has_any_kubeletconfig = bool(kubeletconfig_summary.get("has_any_kubeletconfig"))
    has_any_reserved = bool(kubeletconfig_summary.get("has_any_system_reserved"))
    role_label = "/".join(sorted(node_roles)) if node_roles else "worker"

    if node_roles & roles_with_reserved or has_global_reserved:
        return []

    if node_roles & roles_without_reserved:
        detail = (
            f"Matching KubeletConfig for role '{role_label}' does not define "
            "systemReserved memory. Set spec.kubeletConfig.systemReserved.memory to at least 1-2Gi."
        )
    elif has_any_kubeletconfig and has_any_reserved:
        detail = (
            f"Role '{role_label}' has no role-matching KubeletConfig with systemReserved. "
            "Verify MachineConfigPool selector labels and node role mapping."
        )
    elif has_any_kubeletconfig:
        detail = (
            "KubeletConfig resources exist but none define systemReserved memory. "
            "Set spec.kubeletConfig.systemReserved.memory (at least 1-2Gi)."
        )
    else:
        detail = (
            "Verify systemReserved is set appropriately in KubeletConfig "
            "— inadequate reservation can cause OOM"
        )

    return [CheckResult(
        category_id, category_name, f"{category_id}.node.{short_name}.sysreserved",
        f"{role_prefix}.7 systemReserved: {short_name}", "WARNING",
        f"Node has {memory_gib:.0f} GiB RAM. {detail}",
        name,
    )]


def _evaluate_node_hardware(nodes_data: dict, category_id: str, category_name: str,
                        role_prefix: str = "7.1.4", kubeletconfig_data: dict | None = None,
                        hardware_data: dict | None = None) -> list[CheckResult]:
    """Per-node hardware checks: ready, OS, CPU, memory, disk, kubelet version."""
    if _is_missing(nodes_data):
        return [_not_applicable(f"{category_id}.nodes", "Node Hardware", category_id, category_name)]
    items = _get_items(nodes_data, default_single=True)
    kubeletconfig_summary = _summarize_kubeletconfig_system_reserved(kubeletconfig_data or {})
    checks: list[CheckResult] = []
    for item in items:
        checks += _check_single_node(item, category_id, category_name, role_prefix, kubeletconfig_summary, hardware_data)
    return checks


def _evaluate_mcp(mcp_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """MachineConfigPool: updated, not degraded, machine counts."""
    if _is_missing(mcp_data):
        return [_not_applicable(f"{category_id}.mcp", "MachineConfigPools", category_id, category_name)]

    items = _get_items(mcp_data, default_single=True)
    checks = []
    for pool in items:
        name = pool.get("metadata", {}).get("name", "unknown")
        pool_status = pool.get("status", {})
        conditions = pool_status.get("conditions", [])
        total = pool_status.get("machineCount", 0)
        ready = pool_status.get("readyMachineCount", 0)
        degraded = pool_status.get("degradedMachineCount", 0)
        updated = pool_status.get("updatedMachineCount", 0)

        is_degraded = _find_condition(conditions, "Degraded").get("status") == "True"
        is_updated = _find_condition(conditions, "Updated").get("status") == "True"
        is_updating = _find_condition(conditions, "Updating").get("status") == "True"

        if is_degraded or degraded > 0:
            status = "FAIL"
            evidence = f"{degraded}/{total} machines degraded in pool '{name}'"
        elif is_updating:
            status = "WARNING"
            evidence = f"Pool '{name}' updating: {updated}/{total} updated, {ready}/{total} ready"
        elif not is_updated and total > 0:
            status = "WARNING"
            evidence = f"Pool '{name}' not fully updated: {updated}/{total} updated"
        else:
            status = "PASS"
            evidence = f"Pool '{name}': {total} machines, {ready} ready, {updated} updated — all current"

        checks.append(CheckResult(category_id, category_name, f"{category_id}.mcp.{name}",
                                  f"MachineConfigPool: {name}", status, evidence, name))
    return checks


def _evaluate_etcd(data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Etcd operator CRD health."""
    if _is_missing(data):
        return [_not_applicable(f"{category_id}.etcd", "Etcd Health", category_id, category_name)]

    status_obj = data.get("status") or {}
    conditions = status_obj.get("conditions") or []

    etcd_available = _find_condition(conditions, "EtcdMembersAvailable")
    degraded = _find_condition(conditions, "EtcdMembersDegraded")
    quorum_at_risk = _find_condition(conditions, "EtcdMembersProgressing")

    checks = []
    if degraded.get("status") == "True":
        checks.append(CheckResult(category_id, category_name, f"{category_id}.etcd.members",
                                  "Etcd Member Health", "FAIL",
                                  degraded.get("message", "Members degraded")[:200]))
    elif etcd_available.get("status") == "False":
        checks.append(CheckResult(category_id, category_name, f"{category_id}.etcd.members",
                                  "Etcd Member Health", "WARNING",
                                  etcd_available.get("message", "Not all members available")[:200]))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.etcd.members",
                                  "Etcd Member Health", "PASS",
                                  "All etcd members available and not degraded"))

    if quorum_at_risk.get("status") == "True":
        checks.append(CheckResult(category_id, category_name, f"{category_id}.etcd.quorum",
                                  "Etcd Quorum", "WARNING",
                                  quorum_at_risk.get("message", "Quorum at risk")[:200]))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.etcd.quorum",
                                  "Etcd Quorum", "PASS", "Etcd quorum not at risk"))
    return checks


def _split_etcd_pods(items: list) -> tuple[list, list]:
    """Split a pod list into (etcd_pods, guard_pods)."""

    def pod_name(pod: dict) -> str:
        return pod.get("metadata", {}).get("name", "")

    etcd_pods = [pod for pod in items if "etcd-" in pod_name(pod) and "guard" not in pod_name(pod)]
    guard_pods = [pod for pod in items if "etcd-guard" in pod_name(pod)]
    return etcd_pods, guard_pods


def _check_etcd_pod_health(etcd_pods: list, category_id: str, category_name: str) -> CheckResult:
    failed = [
        _resource_metadata(pod).get("name")
        for pod in etcd_pods
        if _resource_status(pod).get("phase") != "Running"
    ]
    if failed:
        return CheckResult(category_id, category_name, f"{category_id}.etcd.pod_health",
                            "Etcd Pod Status", "FAIL",
                            f"{len(failed)}/{len(etcd_pods)} etcd pods not Running: "
                            f"{', '.join(str(failed_name) for failed_name in failed)}")
    return CheckResult(category_id, category_name, f"{category_id}.etcd.pod_health",
                        "Etcd Pod Status", "PASS",
                        f"All {len(etcd_pods)} etcd pods Running on dedicated control plane nodes")


def _check_etcd_guard_pods(guard_pods: list, category_id: str, category_name: str) -> CheckResult | None:
    if not guard_pods:
        return None
    all_guards_ok = all(_resource_status(pod).get("phase") == "Running" for pod in guard_pods)
    return CheckResult(category_id, category_name, f"{category_id}.etcd.guards",
                        "Etcd Guard Pods",
                        "PASS" if all_guards_ok else "WARNING",
                        f"{len(guard_pods)} guard pods "
                        f"{'all Running' if all_guards_ok else 'some not Running'}")


def _evaluate_etcd_pods(pods_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Check etcd pods are all running."""
    if _is_missing(pods_data):
        return [_not_applicable(f"{category_id}.etcd.pods", "Etcd Pods", category_id, category_name)]

    items = _get_items(pods_data)
    etcd_pods, guard_pods = _split_etcd_pods(items)

    if not etcd_pods:
        return [_not_applicable(f"{category_id}.etcd.pods", "Etcd Pods", category_id, category_name, "No etcd pods found")]

    checks = [_check_etcd_pod_health(etcd_pods, category_id, category_name)]
    guard_check = _check_etcd_guard_pods(guard_pods, category_id, category_name)
    if guard_check:
        checks.append(guard_check)
    return checks


def evaluate_topology(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Dispatch evaluators for 7.2 Topology Checks."""
    checks: list[CheckResult] = []
    checks += _evaluate_topology_aggregate(category_data, results, category_id, category_name)
    checks += _evaluate_node_hardware(
        category_data.get("nodes", {}),
        category_id,
        category_name,
        "7.2.1",
        category_data.get("kubeletconfig", {}),
        results.get("11_hardware", {}),
    )
    checks += _evaluate_mcp(category_data.get("machineconfigpool", {}), category_id, category_name)
    checks += _evaluate_etcd(category_data.get("etcd", {}), category_id, category_name)
    checks += _evaluate_etcd_pods(category_data.get("etcd_pods", {}), category_id, category_name)
    return checks


# ---------------------------------------------------------------------------
# TSR 2.x Aggregate Topology Checks
# ---------------------------------------------------------------------------

def _topology_roles(items: list[dict]) -> tuple[list[dict], list[dict]]:
    masters = []
    workers = []
    for item in items:
        roles = node_roles(_resource_labels(item))
        if "master" in roles or "control-plane" in roles:
            masters.append(item)
        if "worker" in roles:
            workers.append(item)
    return masters, workers


def _evaluate_topology_versions(items: list[dict], category_id: str, category_name: str) -> list[CheckResult]:
    kubelet_versions = {_node_info(item).get("kubeletVersion", "unknown") for item in items}
    os_images = {_node_info(item).get("osImage", "unknown") for item in items}
    return [
        CheckResult(category_id, category_name, f"{category_id}.topo.consistent_ocp",
                    "2.1.1 Consistent OCP Release",
                    "PASS" if len(kubelet_versions) == 1 else "WARNING",
                    f"All {len(items)} nodes running kubelet {next(iter(kubelet_versions))}"
                    if len(kubelet_versions) == 1 else f"Version skew detected: {', '.join(sorted(kubelet_versions))}"),
        CheckResult(category_id, category_name, f"{category_id}.topo.consistent_os",
                    "2.1.2 Consistent OS Release",
                    "PASS" if len(os_images) == 1 else "WARNING",
                    f"All nodes running: {next(iter(os_images))}"
                    if len(os_images) == 1 else f"Mixed OS: {', '.join(sorted(os_images))}"),
    ]


def _evaluate_topology_masters(masters: list[dict], category_id: str, category_name: str) -> list[CheckResult]:
    if len(masters) == 3:
        master_count = CheckResult(category_id, category_name, f"{category_id}.topo.master_count",
                                   "2.2.1 Number of Master Nodes", "PASS",
                                   f"{len(masters)} master nodes — standard HA topology")
    elif len(masters) == 1:
        master_count = CheckResult(category_id, category_name, f"{category_id}.topo.master_count",
                                   "2.2.1 Number of Master Nodes", "INFO",
                                   "1 master node — Single Node OpenShift (SNO)")
    else:
        master_count = CheckResult(category_id, category_name, f"{category_id}.topo.master_count",
                                   "2.2.1 Number of Master Nodes", "WARNING",
                                   f"{len(masters)} master nodes — non-standard count")
    master_zones = set()
    for master in masters:
        labels = _resource_labels(master)
        zone = (
            labels.get("topology.kubernetes.io/zone")
            or labels.get("failure-domain.beta.kubernetes.io/zone")
            or ""
        )
        if zone:
            master_zones.add(zone)
    if len(master_zones) >= 3:
        master_zone = CheckResult(category_id, category_name, f"{category_id}.topo.master_az",
                                  "2.2.2 Master AV Zone Labels", "PASS",
                                  f"Masters spread across {len(master_zones)} zones: {', '.join(sorted(master_zones))}")
    elif master_zones:
        master_zone = CheckResult(category_id, category_name, f"{category_id}.topo.master_az",
                                  "2.2.2 Master AV Zone Labels", "WARNING",
                                  f"Masters in only {len(master_zones)} zone(s): {', '.join(sorted(master_zones))}. Recommend spreading across 3+ zones for HA")
    else:
        master_zone = CheckResult(category_id, category_name, f"{category_id}.topo.master_az",
                                  "2.2.2 Master AV Zone Labels", "WARNING",
                                  "No topology.kubernetes.io/zone labels on masters — AZ distribution cannot be verified")
    return [master_count, master_zone]


def _evaluate_topology_ingress(ingress_data: dict, workers: list[dict], category_id: str, category_name: str) -> list[CheckResult]:
    if _is_missing(ingress_data):
        return [
            CheckResult(category_id, category_name, f"{category_id}.topo.haproxy_ha",
                        "2.2.3 HAProxy HA", "SKIPPED",
                        "IngressController data not available in collection"),
            CheckResult(category_id, category_name, f"{category_id}.topo.routing_scale",
                        "2.3.3 Routing Scaling", "SKIPPED",
                        "IngressController data not available"),
        ]
    ic_items = _get_items(ingress_data, default_single=True)
    if not ic_items:
        return [
            CheckResult(category_id, category_name, f"{category_id}.topo.haproxy_ha",
                        "2.2.3 HAProxy HA", "SKIPPED",
                        "No IngressController resources found"),
            CheckResult(category_id, category_name, f"{category_id}.topo.routing_scale",
                        "2.3.3 Routing Scaling", "SKIPPED",
                        "No IngressController found"),
        ]
    replicas = ic_items[0].get("spec", {}).get("replicas", 2)
    available = ic_items[0].get("status", {}).get("availableReplicas", 0)
    haproxy = CheckResult(category_id, category_name, f"{category_id}.topo.haproxy_ha",
                          "2.2.3 HAProxy HA", "PASS" if replicas >= 2 and available >= 2 else "WARNING",
                          f"IngressController: {available}/{replicas} replicas available"
                          if replicas >= 2 and available >= 2 else f"IngressController: {available}/{replicas} replicas — single replica lacks HA")
    routing = CheckResult(category_id, category_name, f"{category_id}.topo.routing_scale",
                          "2.3.3 Routing Scaling", "PASS",
                          f"Router replicas: {replicas}. Worker nodes: {len(workers)}")
    return [haproxy, routing]


def _evaluate_topology_network_scale(items: list[dict], category_id: str, category_name: str) -> list[CheckResult]:
    total_pod_capacity = sum(int(_node_capacity(item).get("pods", "0") or "0") for item in items)
    return [
        CheckResult(category_id, category_name, f"{category_id}.topo.sdn_nodes",
                    "2.3.1 SDN Number of Nodes", "PASS",
                    f"{len(items)} nodes in cluster network"),
        CheckResult(category_id, category_name, f"{category_id}.topo.sdn_pods",
                    "2.3.2 SDN Number of Pods", "PASS",
                    f"Total pod capacity: {total_pod_capacity} across {len(items)} nodes"),
    ]


def _evaluate_topology_aggregate(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """TSR 2.1-2.3: version consistency, master topology, network scaling."""
    nodes_data = category_data.get("nodes", {})
    if _is_missing(nodes_data):
        return [_not_applicable(f"{category_id}.topo", "Topology Aggregate", category_id, category_name)]
    items = _get_items(nodes_data, default_single=True)
    if not items:
        return []
    masters, workers = _topology_roles(items)
    ingress_data = results.get("05_components", {}).get("ingresscontroller", {})
    checks: list[CheckResult] = []
    checks += _evaluate_topology_versions(items, category_id, category_name)
    checks += _evaluate_topology_masters(masters, category_id, category_name)
    checks += _evaluate_topology_ingress(ingress_data, workers, category_id, category_name)
    checks += _evaluate_topology_network_scale(items, category_id, category_name)
    return checks
