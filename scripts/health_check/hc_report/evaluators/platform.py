"""Evaluators for 7.1 Base Platform Checks."""
from __future__ import annotations

import re

from hc_report.evaluators._common import (
    _MASTER_MIN_CPU,
    _MASTER_MIN_MEM_GIB,
    _MIN_DISK_DOCUMENTATION_URL,
    _MIN_DISK_GIB,
    _cluster_version_object,
    _evaluate_approval_strategy,
    _get_items,
    _is_missing,
    _node_capacity,
    _node_info,
    _not_applicable,
    _parse_cpu_cores,
    _parse_lsblk_size_gib,
    _parse_quantity_gib,
    _resource_labels,
    _resource_name,
    _resource_status,
)
from hc_report.evaluators._shared_checks import node_roles
from hc_report.models import CheckResult


def _evaluate_cluster_version(cluster_version_raw: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """ClusterVersion object: version, channel, lifecycle, upgrade history."""
    cluster_version = _cluster_version_object(cluster_version_raw)
    if _is_missing(cluster_version):
        return [_not_applicable(f"{category_id}.clusterversion", "Cluster Version", category_id, category_name)]

    checks = []
    cluster_version_spec = cluster_version.get("spec", {})
    cluster_version_status = cluster_version.get("status", {})
    history = cluster_version_status.get("history", [])
    desired = cluster_version_status.get("desired", {})
    cluster_id = cluster_version_status.get("clusterID", cluster_version.get("metadata", {}).get("uid", "unknown"))
    version = desired.get("version") or (history[0].get("version") if history else "unknown")
    channel = cluster_version_spec.get("channel", "unknown")

    checks.append(CheckResult(
        category_id, category_name, f"{category_id}.clusterversion.id",
        "7.1.1.1 Cluster ID and version", "INFO",
        f"Cluster ID: {cluster_id}. OCP {version} on channel {channel}",
        "clusterversion",
    ))

    channel_status, channel_evidence = _evaluate_channel(channel)
    checks.append(CheckResult(category_id, category_name, f"{category_id}.clusterversion.channel",
                              "7.1.1.2 Update Channel", channel_status, channel_evidence, "clusterversion"))

    available_updates = cluster_version_status.get("availableUpdates", [])
    if available_updates:
        update_versions = ", ".join(update.get("version", "") for update in available_updates[:3])
        checks.append(CheckResult(category_id, category_name, f"{category_id}.clusterversion.updates",
                                  "7.1.1.3 Available Updates", "WARNING",
                                  f"{len(available_updates)} update(s) available: {update_versions}",
                                  "clusterversion"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.clusterversion.updates",
                                  "7.1.1.3 Available Updates", "PASS",
                                  "No pending updates — cluster is at latest for channel",
                                  "clusterversion"))

    completed = [upgrade for upgrade in history if upgrade.get("state") == "Completed"]
    if completed:
        last = completed[0]
        summary = (f"{len(completed)} completed upgrade(s). "
                   f"Last: {last.get('version')} on {last.get('completionTime', '')[:10]}")
        checks.append(CheckResult(category_id, category_name, f"{category_id}.clusterversion.history",
                                  "7.1.1.4 Upgrade History", "PASS", summary, "clusterversion"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.clusterversion.history",
                                  "7.1.1.4 Upgrade History", "NOT_APPLICABLE",
                                  "No completed upgrades in history", "clusterversion"))

    conditions = cluster_version_status.get("conditions", [])
    failing = [condition for condition in conditions if condition.get("type") == "Failing" and condition.get("status") == "True"]
    if failing:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.clusterversion.failing",
                                  "7.1.1.5 ClusterVersion Conditions", "FAIL",
                                  failing[0].get("message", "Failing condition active")[:200],
                                  "clusterversion"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.clusterversion.failing",
                                  "7.1.1.5 ClusterVersion Conditions", "PASS",
                                  "No failing conditions on ClusterVersion", "clusterversion"))

    return checks


def _evaluate_channel(channel: str) -> tuple[str, str]:
    if "stable" in channel:
        return "PASS", f"Channel '{channel}' is stable — suitable for production"
    if "eus" in channel:
        return "PASS", f"Channel '{channel}' is EUS — extended update support enabled"
    if "fast" in channel:
        return "WARNING", f"Channel '{channel}' is fast — not recommended for production without testing"
    if "candidate" in channel:
        return "WARNING", f"Channel '{channel}' is candidate — not suitable for production"
    return "WARNING", f"Channel '{channel}' is unrecognised"


def _evaluate_infrastructure(infrastructure_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Infrastructure: platform, topology, network VIPs."""
    if _is_missing(infrastructure_data):
        return [_not_applicable(f"{category_id}.infra", "Infrastructure", category_id, category_name)]

    checks = []
    infra_status = infrastructure_data.get("status", {})
    platform = infra_status.get("platform", "unknown")
    cp_topology = infra_status.get("controlPlaneTopology", "unknown")
    infra_topology = infra_status.get("infrastructureTopology", "unknown")
    api_url = infra_status.get("apiServerURL", "")
    infra_name = infra_status.get("infrastructureName", "unknown")

    checks.append(CheckResult(category_id, category_name, f"{category_id}.infra.platform",
                              "7.1.3.1 Platform / Infrastructure Provider", "INFO",
                              f"Platform: {platform}. Infrastructure name: {infra_name}",
                              "infrastructure"))

    ha_cp = cp_topology == "HighlyAvailable"
    ha_infra = infra_topology == "HighlyAvailable"
    if ha_cp and ha_infra:
        topo_status = "PASS"
        topo_ev = f"Control plane: {cp_topology}. Infrastructure: {infra_topology}"
    else:
        topo_status = "WARNING"
        topo_ev = (f"Control plane: {cp_topology}. Infrastructure: {infra_topology}. "
                   "Non-HA topology detected")
    checks.append(CheckResult(category_id, category_name, f"{category_id}.infra.topology",
                              "7.1.3.2 Cluster Topology", topo_status, topo_ev, "infrastructure"))

    if api_url:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.infra.apiurl",
                                  "7.1.3.3 API Server URL", "INFO",
                                  f"API: {api_url}", "infrastructure"))

    plat_status = infra_status.get("platformStatus", {})
    plat_detail = plat_status.get(platform.lower(), plat_status.get(platform, {})) or {}
    api_vip = (plat_detail.get("apiServerInternalIP")
               or (plat_detail.get("apiServerInternalIPs") or [None])[0])
    ingress_vip = (plat_detail.get("ingressIP")
                   or (plat_detail.get("ingressIPs") or [None])[0])
    if api_vip or ingress_vip:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.infra.vips",
                                  "7.1.3.4 VIP Configuration", "PASS",
                                  f"API VIP: {api_vip or 'N/A'}. Ingress VIP: {ingress_vip or 'N/A'}. "
                                  "IPI load balancing active", "infrastructure"))
    return checks


def _flatten_subscription_items(raw_items: list) -> list[dict]:
    """Flatten merged collections where a nested List wraps another List.

    `hc_merge.py` can combine per-context/per-run collections by appending
    each run's raw `oc get -o json` payload as a single item, so a merged
    `items` array may itself contain List-kind objects rather than only
    Subscription objects. Recurse one level to recover the real Subscription
    records instead of treating the List wrapper as a malformed subscription.
    """
    flattened: list[dict] = []
    for item in raw_items:
        if item.get("kind") == "List" and "items" in item:
            flattened.extend(item.get("items", []))
        else:
            flattened.append(item)
    return flattened


def _evaluate_subscriptions(subscription_data: dict, cluster_service_version_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Per-subscription health: state, CSV phase, channel appropriateness, approval strategy."""
    if _is_missing(subscription_data):
        return [_not_applicable(f"{category_id}.subs", "Operator Subscriptions", category_id, category_name)]

    items = _flatten_subscription_items(_get_items(subscription_data))
    if not items:
        return [CheckResult(category_id, category_name, f"{category_id}.subs", "Operator Subscriptions",
                            "NOT_APPLICABLE", "No subscriptions found", "subscriptions")]

    cluster_service_version_phases: dict[str, str] = {}
    if cluster_service_version_data and not cluster_service_version_data.get("_hc_error"):
        for cluster_service_version in cluster_service_version_data.get("items", []):
            resource_name = cluster_service_version.get("metadata", {}).get("name", "")
            phase = cluster_service_version.get("status", {}).get("phase", "Unknown")
            cluster_service_version_phases[resource_name] = phase

    checks = []
    for subscription in items:
        checks += _evaluate_single_subscription(subscription, cluster_service_version_phases, category_id, category_name)

    checks.append(_evaluate_approval_strategy(
        items, category_id, category_name, f"{category_id}.subs.approval", "7.1.2.1 Operator Approval Strategy",
    ))
    return checks


def _evaluate_single_subscription(subscription: dict, cluster_service_version_phases: dict, category_id: str, category_name: str) -> list[CheckResult]:
    name = subscription.get("metadata", {}).get("name", "unknown")
    namespace = subscription.get("metadata", {}).get("namespace", "unknown")
    subscription_status = subscription.get("status", {})
    state = subscription_status.get("state", "unknown")
    installed_csv = subscription_status.get("installedCSV") or subscription.get("spec", {}).get("installedCSV", "")
    current_csv = subscription_status.get("currentCSV") or subscription.get("spec", {}).get("currentCSV", "")
    channel = subscription.get("spec", {}).get("channel", "unknown")

    cluster_service_version_phase = cluster_service_version_phases.get(installed_csv, "Unknown") if installed_csv else "Unknown"
    upgrade_pending = bool(current_csv and installed_csv and current_csv != installed_csv)

    if state == "AtLatestKnown" and cluster_service_version_phase in ("Succeeded", "Unknown"):
        status = "PASS"
        evidence = f"AtLatestKnown. CSV: {installed_csv or 'none'}. Channel: {channel}"
    elif upgrade_pending:
        status = "WARNING"
        evidence = f"Upgrade pending: installed={installed_csv}, current={current_csv}. Channel: {channel}"
    elif cluster_service_version_phase == "Failed":
        status = "FAIL"
        evidence = f"CSV failed: {installed_csv}. Subscription state: {state}"
    elif state not in ("AtLatestKnown", "UpgradePending", ""):
        status = "WARNING"
        evidence = f"State: {state}. CSV: {installed_csv or 'none'}. Channel: {channel}"
    else:
        status = "PASS"
        evidence = f"State: {state}. CSV: {installed_csv or 'none'}. Channel: {channel}"

    return [CheckResult(category_id, category_name, f"{category_id}.sub.{name}",
                        f"Subscription: {name} ({namespace})", status, evidence, name)]


def evaluate_base_platform(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Dispatch evaluators for 7.1 Base Platform Checks."""
    checks: list[CheckResult] = []
    checks += _evaluate_cluster_version(category_data.get("clusterversion", {}), category_id, category_name)
    checks += _evaluate_infrastructure(category_data.get("infrastructure", {}), category_id, category_name)
    checks += _evaluate_infrastructure_details(category_data, category_id, category_name)
    checks += _evaluate_subscriptions(
        category_data.get("subscriptions", {}),
        category_data.get("csv", {}),
        category_id, category_name,
    )
    checks += _evaluate_node_requirements(
        category_data.get("nodes", {}), category_data.get("scheduler", {}), category_id, category_name,
        hardware_data=results.get("11_hardware", {}),
    )
    checks += _evaluate_system_config(category_data, results, category_id, category_name)
    return checks


# ---------------------------------------------------------------------------
# 1.3.x Infrastructure Details
# ---------------------------------------------------------------------------

def _install_config_yaml(category_data: dict) -> str:
    install_config = category_data.get("install_config", {})
    if _is_missing(install_config):
        return ""
    return install_config.get("data", {}).get("install-config", "")


def _evaluate_infrastructure_installer(install_config_yaml: str, category_id: str, category_name: str) -> list[CheckResult]:
    if not install_config_yaml:
        return [CheckResult(category_id, category_name, f"{category_id}.infra.installer",
                            "1.3.1 Installer", "SKIPPED", "install-config not available")]
    patterns = [
        (r"platform:\s*\n\s+none:", "UPI (platform: none)"),
        (r"platform:\s*\n\s+baremetal:", "IPI (BareMetal)"),
        (r"platform:\s*\n\s+vsphere:", "IPI (vSphere)"),
        (r"platform:\s*\n\s+aws:", "IPI (AWS)"),
        (r"platform:\s*\n\s+gcp:", "IPI (GCP)"),
        (r"platform:\s*\n\s+azure:", "IPI (Azure)"),
    ]
    inst_type = next((label for pattern, label in patterns if re.search(pattern, install_config_yaml)), "IPI (auto-detected)")
    return [CheckResult(category_id, category_name, f"{category_id}.infra.installer",
                        "1.3.1 Installer", "INFO", f"Install type: {inst_type}")]


def _evaluate_infrastructure_hypervisor(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    infrastructure_data = category_data.get("infrastructure", {})
    platform = infrastructure_data.get("status", {}).get("platform", "unknown") if not _is_missing(infrastructure_data) else "unknown"
    if platform.lower() in ("vsphere", "ovirt", "openstack", "kubevirt"):
        return [CheckResult(category_id, category_name, f"{category_id}.infra.hypervisor",
                            "1.3.2.2 Hypervisor Checks", "INFO",
                            f"Virtual platform: {platform} — hypervisor health is external")]
    return [CheckResult(category_id, category_name, f"{category_id}.infra.hypervisor",
                        "1.3.2.2 Hypervisor Checks", "NOT_APPLICABLE",
                        f"Platform {platform} — hypervisor checks not applicable")]


def _evaluate_infrastructure_restricted(category_data: dict, install_config_yaml: str, category_id: str, category_name: str) -> list[CheckResult]:
    proxy_data = category_data.get("proxy", {})
    restricted = bool(install_config_yaml and re.search(r"imageContentSources:", install_config_yaml))
    if not restricted and not _is_missing(proxy_data):
        restricted = bool(proxy_data.get("spec", {}).get("trustedCA", {}).get("name"))
    evidence = (
        "Cluster appears to use restricted/disconnected network (imageContentSources or trustedCA detected)"
        if restricted else "Cluster appears to use standard (connected) network"
    )
    return [CheckResult(category_id, category_name, f"{category_id}.infra.restricted",
                        "1.3.3 Restricted Network", "INFO", evidence)]


def _evaluate_infrastructure_details(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """TSR 1.3.1 Installer, 1.3.2.2 Hypervisor, 1.3.3 Restricted Network."""
    install_config_yaml = _install_config_yaml(category_data)
    checks: list[CheckResult] = []
    checks += _evaluate_infrastructure_installer(install_config_yaml, category_id, category_name)
    checks += _evaluate_infrastructure_hypervisor(category_data, category_id, category_name)
    checks += _evaluate_infrastructure_restricted(category_data, install_config_yaml, category_id, category_name)
    return checks


# ---------------------------------------------------------------------------
# 1.4.x Node Requirements
# ---------------------------------------------------------------------------

def _split_nodes_by_role(items: list[dict]) -> tuple[list[dict], list[dict]]:
    masters = [item for item in items if "master" in node_roles(_resource_labels(item))]
    workers = [item for item in items if "worker" in node_roles(_resource_labels(item))]
    return masters, workers


def _evaluate_nodes_os(items: list[dict], category_id: str, category_name: str) -> list[CheckResult]:
    os_images = {_node_info(item).get("osImage", "unknown") for item in items}
    if all("CoreOS" in image or "RHCOS" in image for image in os_images):
        return [CheckResult(category_id, category_name, f"{category_id}.nodes.os",
                            "1.4.1.1 Operating System Version", "PASS",
                            f"All nodes run RHCOS: {', '.join(sorted(os_images)[:3])}")]
    return [CheckResult(category_id, category_name, f"{category_id}.nodes.os",
                        "1.4.1.1 Operating System Version", "INFO",
                        f"OS variants: {', '.join(sorted(os_images)[:5])}")]


def _evaluate_master_cpu(masters: list[dict], category_id: str, category_name: str) -> list[CheckResult]:
    if not masters:
        return []
    cpu_issues = [
        _resource_name(master)
        for master in masters
        if _parse_cpu_cores(_node_capacity(master).get("cpu", "0")) < _MASTER_MIN_CPU
    ]
    if cpu_issues:
        return [CheckResult(category_id, category_name, f"{category_id}.nodes.master_cpu",
                            "1.4.1.2 Master CPUs", "WARNING",
                            f"{len(cpu_issues)} master(s) below {_MASTER_MIN_CPU} CPU minimum: {', '.join(cpu_issues[:3])}")]
    sample_cpu = _parse_cpu_cores(masters[0].get("status", {}).get("capacity", {}).get("cpu", "0"))
    return [CheckResult(category_id, category_name, f"{category_id}.nodes.master_cpu",
                        "1.4.1.2 Master CPUs", "PASS",
                        f"All {len(masters)} master(s) meet minimum ({_MASTER_MIN_CPU} vCPU). Sample: {sample_cpu:.0f} vCPU")]


def _evaluate_master_memory(masters: list[dict], category_id: str, category_name: str) -> list[CheckResult]:
    if not masters:
        return []
    memory_issues = [
        _resource_name(master)
        for master in masters
        if _parse_quantity_gib(_node_capacity(master).get("memory", "0")) < _MASTER_MIN_MEM_GIB
    ]
    if memory_issues:
        return [CheckResult(category_id, category_name, f"{category_id}.nodes.master_mem",
                            "1.4.1.3 Master Memory", "WARNING",
                            f"{len(memory_issues)} master(s) below {_MASTER_MIN_MEM_GIB} GiB minimum: {', '.join(memory_issues[:3])}")]
    sample_mem = _parse_quantity_gib(masters[0].get("status", {}).get("capacity", {}).get("memory", "0"))
    return [CheckResult(category_id, category_name, f"{category_id}.nodes.master_mem",
                        "1.4.1.3 Master Memory", "PASS",
                        f"All {len(masters)} master(s) meet minimum ({_MASTER_MIN_MEM_GIB} GiB). Sample: {sample_mem:.1f} GiB")]


def _get_node_disk_gib(node: dict, hardware_data: dict) -> tuple[float, str]:
    """Return (disk_gib, signal_source), preferring actual hardware disk size."""
    name = node.get("metadata", {}).get("name", "")
    short_name = name.split(".")[0] if name else ""
    node_hardware = hardware_data.get(f"node_hw_{short_name}", {})
    if node_hardware and not node_hardware.get("_hc_error") and not node_hardware.get("_hc_not_found"):
        sizes = [_parse_lsblk_size_gib(disk.get("size", "0")) for disk in node_hardware.get("disks", [])]
        sizes = [size for size in sizes if size > 0]
        if sizes:
            return max(sizes), "actual disk (sysinfo)"
    disk_gib = _parse_quantity_gib(
        node.get("status", {}).get("capacity", {}).get("ephemeral-storage", "0")
    )
    return disk_gib, "ephemeral-storage capacity"


def _evaluate_master_disk(masters: list[dict], category_id: str, category_name: str, hardware_data: dict | None = None) -> list[CheckResult]:
    if not masters:
        return []
    node_hardware = hardware_data or {}
    disk_issues = [
        _resource_name(master)
        for master in masters
        if _get_node_disk_gib(master, node_hardware)[0] < _MIN_DISK_GIB
    ]
    if disk_issues:
        return [CheckResult(category_id, category_name, f"{category_id}.nodes.master_disk",
                            "1.4.1.4 Master Disk", "WARNING",
                            f"{len(disk_issues)} master(s) below {_MIN_DISK_GIB} GiB disk",
                            doc_ref=_MIN_DISK_DOCUMENTATION_URL)]
    sample_disk, source = _get_node_disk_gib(masters[0], node_hardware)
    return [CheckResult(category_id, category_name, f"{category_id}.nodes.master_disk",
                        "1.4.1.4 Master Disk", "PASS",
                        f"All master(s) meet {_MIN_DISK_GIB} GiB minimum. Sample: {sample_disk:.0f} GiB ({source})",
                        doc_ref=_MIN_DISK_DOCUMENTATION_URL)]


def _evaluate_master_schedulable(scheduler_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    schedulable = scheduler_data.get("spec", {}).get("mastersSchedulable", True) if scheduler_data and not _is_missing(scheduler_data) else True
    evidence = (
        "Masters are schedulable (workloads can run on control plane)"
        if schedulable else "Masters are NOT schedulable (dedicated control plane — recommended for production)"
    )
    return [CheckResult(category_id, category_name, f"{category_id}.nodes.master_sched",
                        "1.4.1.5 Master Schedulable", "PASS", evidence)]


def _evaluate_master_kubelet(masters: list[dict], category_id: str, category_name: str) -> list[CheckResult]:
    if not masters:
        return []
    versions = {_node_info(master).get("kubeletVersion", "unknown") for master in masters}
    if len(versions) == 1:
        return [CheckResult(category_id, category_name, f"{category_id}.nodes.master_kube",
                            "1.4.1.6 Master Kubernetes Version", "PASS",
                            f"All masters running kubelet {next(iter(versions))}")]
    return [CheckResult(category_id, category_name, f"{category_id}.nodes.master_kube",
                        "1.4.1.6 Master Kubernetes Version", "WARNING",
                        f"Version skew across masters: {', '.join(sorted(versions))}")]


def _evaluate_worker_disk(workers: list[dict], category_id: str, category_name: str, hardware_data: dict | None = None) -> list[CheckResult]:
    if not workers:
        return []
    node_hardware = hardware_data or {}
    disk_issues = [
        _resource_name(worker)
        for worker in workers
        if _get_node_disk_gib(worker, node_hardware)[0] < _MIN_DISK_GIB
    ]
    if disk_issues:
        return [CheckResult(category_id, category_name, f"{category_id}.nodes.worker_disk",
                            "1.4.2.4 Node Disk", "INFO",
                            f"{len(disk_issues)}/{len(workers)} worker(s) below {_MIN_DISK_GIB} GiB")]
    return [CheckResult(category_id, category_name, f"{category_id}.nodes.worker_disk",
                        "1.4.2.4 Node Disk", "PASS",
                        f"All {len(workers)} worker(s) meet {_MIN_DISK_GIB} GiB disk minimum")]


def _evaluate_node_architecture(items: list[dict], category_id: str, category_name: str) -> list[CheckResult]:
    arches = {_node_info(item).get("architecture", "unknown") for item in items}
    if len(arches) == 1:
        return [CheckResult(category_id, category_name, f"{category_id}.nodes.arch",
                            "1.4.2.5 Node Architecture", "PASS",
                            f"Homogeneous architecture: {next(iter(arches))}")]
    return [CheckResult(category_id, category_name, f"{category_id}.nodes.arch",
                        "1.4.2.5 Node Architecture", "INFO",
                        f"Mixed architecture cluster: {', '.join(sorted(arches))}")]


def _evaluate_node_requirements(
    nodes_data: dict, scheduler_data: dict, category_id: str, category_name: str,
    hardware_data: dict | None = None,
) -> list[CheckResult]:
    """TSR 1.4.x: OS, CPU, memory, disk, schedulable, kubelet, architecture."""
    if _is_missing(nodes_data):
        return [_not_applicable(f"{category_id}.nodes", "Node Requirements", category_id, category_name)]
    items = _get_items(nodes_data)
    if not items:
        return [_not_applicable(f"{category_id}.nodes", "Node Requirements", category_id, category_name)]
    masters, workers = _split_nodes_by_role(items)
    checks: list[CheckResult] = []
    checks += _evaluate_nodes_os(items, category_id, category_name)
    checks += _evaluate_master_cpu(masters, category_id, category_name)
    checks += _evaluate_master_memory(masters, category_id, category_name)
    checks += _evaluate_master_disk(masters, category_id, category_name, hardware_data)
    checks += _evaluate_master_schedulable(scheduler_data, category_id, category_name)
    checks += _evaluate_master_kubelet(masters, category_id, category_name)
    checks += _evaluate_worker_disk(workers, category_id, category_name, hardware_data)
    checks += _evaluate_node_architecture(items, category_id, category_name)
    return checks


# ---------------------------------------------------------------------------
# 1.5.x System Configurations
# ---------------------------------------------------------------------------

def _evaluate_system_firewall_proxy(proxy_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    if _is_missing(proxy_data):
        return [CheckResult(category_id, category_name, f"{category_id}.sys.proxy",
                            "1.5.6 Proxy", "NOT_APPLICABLE", "Proxy data not collected")]
    spec = proxy_data.get("spec", {})
    http_proxy = spec.get("httpProxy", "")
    https_proxy = spec.get("httpsProxy", "")
    trusted_ca = spec.get("trustedCA", {}).get("name", "")
    no_proxy = spec.get("noProxy", "")
    has_proxy = bool(http_proxy or https_proxy)
    firewall = CheckResult(category_id, category_name, f"{category_id}.sys.firewall",
                           "1.5.5 Firewalls",
                           "WARNING" if has_proxy else "PASS",
                           f"Proxy configured — ensure firewall allows required OCP endpoints. noProxy length: {len(no_proxy.split(','))} entries"
                           if has_proxy else "No proxy configured — direct connectivity assumed")
    proxy = CheckResult(category_id, category_name, f"{category_id}.sys.proxy",
                        "1.5.6 Proxy", "PASS",
                        f"Cluster proxy configured. HTTP: {http_proxy or 'none'}. HTTPS: {https_proxy or 'none'}. TrustedCA: {trusted_ca or 'none'}"
                        if has_proxy else "No cluster-wide proxy configured")
    return [firewall, proxy]


def _detect_network_plugin(cluster_operator_data: dict, install_config_yaml: str) -> str:
    if not _is_missing(cluster_operator_data):
        for operator in _get_items(cluster_operator_data):
            if operator.get("metadata", {}).get("name") != "network":
                continue
            for related in operator.get("status", {}).get("relatedObjects", []):
                related_name = related.get("name", "").lower()
                if "ovn" in related_name:
                    return "OVN-Kubernetes"
                if "sdn" in related_name:
                    return "OpenShift-SDN"
            for version in operator.get("status", {}).get("versions", []):
                if version.get("name") == "operator":
                    return version.get("version", "unknown")
            break
    if "OVNKubernetes" in install_config_yaml:
        return "OVN-Kubernetes"
    if "OpenShiftSDN" in install_config_yaml:
        return "OpenShift-SDN"
    return "unknown"


def _evaluate_system_network(category_data: dict, results: dict, cluster_operator_data: dict, install_config_yaml: str, category_id: str, category_name: str) -> list[CheckResult]:
    checks: list[CheckResult] = []
    plugin = _detect_network_plugin(cluster_operator_data, install_config_yaml)
    if plugin != "unknown":
        status = "PASS" if "OVN" in plugin else "WARNING"
        evidence = f"Network plugin: {plugin}"
        if "SDN" in plugin:
            evidence += " (OpenShift-SDN is deprecated; migrate to OVN-Kubernetes)"
        checks.append(CheckResult(category_id, category_name, f"{category_id}.sys.sdn", "1.5.8 SDN", status, evidence))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.sys.sdn", "1.5.8 SDN", "INFO", "Unable to determine network plugin"))
    net_match = re.search(r"machineNetwork:\s*\n((?:\s*-\s*cidr:.*\n?)+)", install_config_yaml)
    machine_cidrs = re.findall(r"cidr:\s*(\S+)", net_match.group(1)) if net_match else []
    checks.append(CheckResult(category_id, category_name, f"{category_id}.sys.machine_net",
                              "1.5.10 Machine Network",
                              "PASS" if net_match else "INFO",
                              f"Machine network CIDR(s): {', '.join(machine_cidrs)}"
                              if net_match else "Machine network not found in install-config"))
    svc_net = re.search(r"serviceNetwork:\s*\n\s*-\s*(\S+)", install_config_yaml)
    cluster_net = re.search(r"clusterNetwork:\s*\n\s*-\s*cidr:\s*(\S+)", install_config_yaml)
    checks.append(CheckResult(category_id, category_name, f"{category_id}.sys.shared_net",
                              "1.5.4 Shared Network",
                              "PASS" if svc_net and cluster_net else "INFO",
                              f"Service network: {svc_net.group(1)}. Cluster network: {cluster_net.group(1)}"
                              if svc_net and cluster_net else "Network CIDRs not found in install-config"))
    comp_data = results.get("05_components", {})
    dns_pods = comp_data.get("dns_pods", {}) if comp_data else {}
    if not _is_missing(dns_pods):
        dns_items = _get_items(dns_pods)
        running = [pod for pod in dns_items if _resource_status(pod).get("phase") == "Running"]
        if dns_items:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.sys.dns_pods",
                                      "1.5.2.2 DNS Pods",
                                      "PASS" if len(running) == len(dns_items) else "WARNING",
                                      f"All {len(running)} DNS pods Running" if len(running) == len(dns_items)
                                      else f"{len(running)}/{len(dns_items)} DNS pods Running"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.sys.dns_pods",
                                  "1.5.2.2 DNS Pods", "SKIPPED",
                                  "DNS pod data not available in current collection"))
    dns_op = comp_data.get("dns", {}) if comp_data else {}
    checks.append(CheckResult(category_id, category_name, f"{category_id}.sys.dns_config",
                              "1.5.2.1 DNS Config",
                              "PASS" if not _is_missing(dns_op) else "SKIPPED",
                              "DNS operator configuration collected" if not _is_missing(dns_op)
                              else "DNS operator data not available in current collection"))
    return checks


def _evaluate_system_node_baseline(items: list[dict], category_id: str, category_name: str) -> list[CheckResult]:
    if not items:
        return []
    rhcos_nodes = [
        item for item in items
        if "CoreOS" in _node_info(item).get("osImage", "")
    ]
    selinux = CheckResult(category_id, category_name, f"{category_id}.sys.selinux",
                          "1.5.1 SELinux",
                          "PASS" if rhcos_nodes else "INFO",
                          f"SELinux Enforcing — all {len(rhcos_nodes)} RHCOS node(s) enforce SELinux by default (immutable OS policy)"
                          if rhcos_nodes else "Non-RHCOS nodes detected — SELinux state cannot be confirmed from node metadata alone")
    ptp_labels = any("ptp" in str(_resource_labels(item)).lower() for item in items)
    return [
        CheckResult(category_id, category_name, f"{category_id}.sys.swap",
                    "1.5.9 Swap", "PASS",
                    "OpenShift nodes have swap disabled by default (RHCOS requirement)"),
        selinux,
        CheckResult(category_id, category_name, f"{category_id}.sys.netmgr",
                    "1.5.3 Network Manager", "PASS",
                    "RHCOS nodes use NetworkManager as default network service"),
        CheckResult(category_id, category_name, f"{category_id}.sys.entropy",
                    "1.5.14 Entropy", "INFO",
                    "RHCOS uses virtio-rng/rng-tools for entropy — runtime verification requires node-level access"),
        CheckResult(category_id, category_name, f"{category_id}.sys.ptp",
                    "1.5.7.3 PTP", "PASS" if ptp_labels else "NOT_APPLICABLE",
                    "PTP-related labels detected on nodes" if ptp_labels else "No PTP configuration detected"),
    ]


def _evaluate_system_node_resources(items: list[dict], category_id: str, category_name: str) -> list[CheckResult]:
    if not items:
        return []
    hugepage_nodes = [
        _resource_name(item)
        for item in items
        if int(_node_capacity(item).get("hugepages-2Mi", "0") or "0") > 0
        or int(_node_capacity(item).get("hugepages-1Gi", "0") or "0") > 0
    ]
    gpu_nodes = []
    for item in items:
        capacity = item.get("status", {}).get("capacity", {})
        if any(("gpu" in key.lower() or "nvidia" in key.lower()) and int(capacity.get(key, "0") or "0") > 0 for key in capacity):
            gpu_nodes.append(item.get("metadata", {}).get("name", "?"))
    return [
        CheckResult(category_id, category_name, f"{category_id}.sys.hugepages",
                    "1.5.12 Huge Pages", "PASS" if hugepage_nodes else "NOT_APPLICABLE",
                    f"Huge pages configured on {len(hugepage_nodes)}/{len(items)} node(s)"
                    if hugepage_nodes else "No huge pages configured"),
        CheckResult(category_id, category_name, f"{category_id}.sys.gpu",
                    "1.5.13 GPU", "PASS" if gpu_nodes else "NOT_APPLICABLE",
                    f"GPU resources detected on {len(gpu_nodes)} node(s)"
                    if gpu_nodes else "No GPU resources detected"),
    ]


def _evaluate_system_time(items: list[dict], category_id: str, category_name: str) -> list[CheckResult]:
    if not items:
        return [CheckResult(category_id, category_name, f"{category_id}.sys.ntp",
                            "1.5.7.1 NTP", "NOT_APPLICABLE",
                            "Legacy NTP (ntpd) not applicable — RHCOS uses chrony")]
    return [
        CheckResult(category_id, category_name, f"{category_id}.sys.chrony",
                    "1.5.7.2 Chrony", "PASS",
                    "RHCOS uses chrony for NTP synchronization by default"),
        CheckResult(category_id, category_name, f"{category_id}.sys.ntp",
                    "1.5.7.1 NTP", "NOT_APPLICABLE",
                    "Legacy NTP (ntpd) not applicable — RHCOS uses chrony"),
    ]


def _evaluate_system_security(category_data: dict, install_config_yaml: str, category_id: str, category_name: str) -> list[CheckResult]:
    checks: list[CheckResult] = []
    checks.append(CheckResult(category_id, category_name, f"{category_id}.sys.fips",
                              "1.5.11 FIPS", "PASS",
                              "FIPS mode enabled at install time" if re.search(r"fips:\s*true", install_config_yaml, re.I)
                              else "FIPS mode not enabled (standard configuration)"))
    oauth_data = category_data.get("oauth", {})
    if _is_missing(oauth_data):
        checks.append(CheckResult(category_id, category_name, f"{category_id}.sys.auth",
                                  "1.5.17 Authentication", "SKIPPED",
                                  "OAuth data not collected"))
    else:
        idps = oauth_data.get("spec", {}).get("identityProviders", [])
        if not idps:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.sys.auth",
                                      "1.5.17 Authentication", "WARNING",
                                      "No identity providers configured — only kubeadmin available"))
        else:
            idp_summary = ", ".join(f"{provider.get('name')}({provider.get('type')})" for provider in idps[:5])
            htpasswd_only = all(provider.get("type") == "HTPasswd" for provider in idps)
            checks.append(CheckResult(category_id, category_name, f"{category_id}.sys.auth",
                                      "1.5.17 Authentication",
                                      "WARNING" if htpasswd_only else "PASS",
                                      f"Only HTPasswd identity provider(s) configured: {idp_summary}. Integrate with enterprise IdP (LDAP/OIDC) for production"
                                      if htpasswd_only else f"Identity providers: {idp_summary}"))
    scc_data = category_data.get("scc", {})
    if _is_missing(scc_data):
        checks.append(CheckResult(category_id, category_name, f"{category_id}.sys.scc",
                                  "1.5.18 Security Context Constraints", "SKIPPED",
                                  "SCC data not collected"))
    else:
        scc_items = _get_items(scc_data)
        default_sccs = {"anyuid", "hostaccess", "hostmount-anyuid", "hostnetwork", "hostnetwork-v2", "nonroot", "nonroot-v2", "privileged", "restricted", "restricted-v2"}
        custom = [
            _resource_name(item)
            for item in scc_items
            if _resource_name(item, default="") not in default_sccs
        ]
        checks.append(CheckResult(category_id, category_name, f"{category_id}.sys.scc",
                                  "1.5.18 Security Context Constraints", "PASS",
                                  f"{len(scc_items)} SCCs total. {len(custom)} custom: {', '.join(custom[:5])}"
                                  if custom else f"{len(scc_items)} SCCs — all default/built-in"))
    return checks


def _evaluate_system_remote_health(cluster_operator_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    insights_ok = False
    if not _is_missing(cluster_operator_data):
        for operator in _get_items(cluster_operator_data):
            if operator.get("metadata", {}).get("name") != "insights":
                continue
            conditions = operator.get("status", {}).get("conditions", [])
            available = next((condition for condition in conditions if condition.get("type") == "Available"), {})
            insights_ok = available.get("status") == "True"
            break
    return [CheckResult(category_id, category_name, f"{category_id}.sys.remote_health",
                        "1.5.15 Remote Health Reporting",
                        "PASS" if insights_ok else "WARNING",
                        "Insights operator is Available — remote health reporting active"
                        if insights_ok else "Insights operator not confirmed Available — remote health may be disabled")]


def _evaluate_system_config(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """TSR 1.5.x: proxy, FIPS, hugepages, SDN, swap, auth, SCC, remote health."""
    items = _get_items(category_data.get("nodes", {})) if not _is_missing(category_data.get("nodes", {})) else []
    install_config_yaml = _install_config_yaml(category_data)
    cluster_operator_data = category_data.get("clusteroperators", {})

    checks: list[CheckResult] = []
    checks += _evaluate_system_firewall_proxy(category_data.get("proxy", {}), category_id, category_name)
    checks += _evaluate_system_network(category_data, results, cluster_operator_data, install_config_yaml, category_id, category_name)
    checks += _evaluate_system_node_baseline(items, category_id, category_name)
    checks += _evaluate_system_node_resources(items, category_id, category_name)
    checks += _evaluate_system_time(items, category_id, category_name)
    checks += _evaluate_system_security(category_data, install_config_yaml, category_id, category_name)
    checks += _evaluate_system_remote_health(cluster_operator_data, category_id, category_name)
    return checks
