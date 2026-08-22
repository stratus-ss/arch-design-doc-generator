"""Evaluators for 7.5 Cluster Health."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from hc_report.evaluators._common import (
    _get_items,
    _is_missing,
    _node_info,
    _not_applicable,
    _resource_labels,
    _resource_metadata,
    _resource_status,
)
from hc_report.evaluators._shared_checks import check_mcp_degraded, find_degraded_operators, node_roles
from hc_report.models import CheckResult

_COMPACT_CLUSTER_DOC_REF = (
    "https://docs.openshift.com/container-platform/4.18/installing/installing_platform_agnostic/"
    "installing-platform-agnostic.html#configuring-a-three-node-cluster_installing-platform-agnostic"
)
_POD_KEY_RE = re.compile(r"\b([a-z0-9][a-z0-9.-]{0,61})/([a-z0-9][a-z0-9.-]{0,251})\b")


def _parse_alerts_list(alerts_data: dict) -> list[dict]:
    """Extract firing alert list from various data shapes."""
    if "data" in alerts_data and "alerts" in alerts_data.get("data", {}):
        return alerts_data["data"]["alerts"]
    if alerts_data.get("status") == "success":
        return alerts_data.get("data", {}).get("alerts", [])
    if "_hc_text" in alerts_data:
        try:
            parsed = json.loads(alerts_data.get("output", "{}"))
            return parsed.get("data", {}).get("alerts", [])
        except (json.JSONDecodeError, TypeError):
            pass
    return []


def _alert_name(alert: dict) -> str:
    return alert.get("labels", {}).get("alertname", "").lower()


def _alerts_matching(alerts_list: list[dict], keywords: tuple[str, ...]) -> list[dict]:
    matching = []
    for alert in alerts_list:
        name = _alert_name(alert)
        if any(keyword in name for keyword in keywords):
            matching.append(alert)
    return matching


def _evaluate_firing_alerts(alerts_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Parse firing alerts from prometheus JSON or text output."""
    if _is_missing(alerts_data):
        return [_not_applicable(f"{category_id}.alerts", "Firing Alerts", category_id, category_name)]

    alerts_list = _parse_alerts_list(alerts_data)
    if not alerts_list:
        return [CheckResult(category_id, category_name, f"{category_id}.alerts.firing",
                            "7.5.1 Firing Alerts", "PASS",
                            "No firing alerts detected", "firing_alerts")]

    by_severity: dict[str, list[str]] = defaultdict(list)
    for alert in alerts_list:
        labels = alert.get("labels", {})
        sev = labels.get("severity", "none").lower()
        by_severity[sev].append(labels.get("alertname", "unknown"))

    critical = by_severity.get("critical", [])
    warning = by_severity.get("warning", [])
    info_alerts = by_severity.get("info", [])

    checks = []
    if critical:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.alerts.critical",
                                  "7.5.1 Critical Alerts", "FAIL",
                                  f"{len(critical)} critical alert(s) firing: {', '.join(critical[:5])}",
                                  "firing_alerts"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.alerts.critical",
                                  "7.5.1 Critical Alerts", "PASS",
                                  "No critical alerts firing", "firing_alerts"))

    if warning:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.alerts.warning",
                                  "7.5.2 Warning Alerts", "WARNING",
                                  f"{len(warning)} warning alert(s) firing: {', '.join(warning[:5])}",
                                  "firing_alerts"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.alerts.warning",
                                  "7.5.2 Warning Alerts", "PASS",
                                  "No warning alerts firing", "firing_alerts"))

    if info_alerts:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.alerts.info",
                                  "7.5.3 Info Alerts", "INFO",
                                  f"{len(info_alerts)} info alert(s) active: {', '.join(info_alerts[:5])}",
                                  "firing_alerts"))
    return checks


def _evaluate_pod_health(pods_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Overall pod health: running vs failed."""
    if _is_missing(pods_data):
        return [_not_applicable(f"{category_id}.pods", "Pod Health", category_id, category_name)]

    items = _get_items(pods_data)
    phases: Counter = Counter(_resource_status(pod).get("phase") for pod in items)
    failed = [
        _resource_metadata(pod).get("name")
        for pod in items
        if _resource_status(pod).get("phase") in ("Failed", "Unknown")
    ]
    crash_loop = []
    for pod in items:
        container_statuses = _resource_status(pod).get("containerStatuses", [])
        for container_status in container_statuses:
            waiting = container_status.get("state", {}).get("waiting", {})
            if waiting.get("reason") == "CrashLoopBackOff":
                crash_loop.append(_resource_metadata(pod).get("name"))
                break

    checks = []
    if failed:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.pods.failed",
                                  "7.5.4 Pod Health", "WARNING",
                                  f"{len(failed)} Failed/Unknown pod(s): {', '.join(str(failed_name) for failed_name in failed[:5])}. "
                                  f"Running: {phases.get('Running', 0)}, "
                                  f"Succeeded: {phases.get('Succeeded', 0)}"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.pods.health",
                                  "7.5.4 Pod Health", "PASS",
                                  f"{phases.get('Running', 0)} Running, "
                                  f"{phases.get('Succeeded', 0)} Succeeded. "
                                  f"No Failed or Unknown pods across {len(items)} total pods"))

    if crash_loop:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.pods.crashloop",
                                  "7.5.5 CrashLoopBackOff Pods", "FAIL",
                                  f"{len(crash_loop)} pod(s) in CrashLoopBackOff: "
                                  f"{', '.join(str(pod) for pod in crash_loop[:5])}"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.pods.crashloop",
                                  "7.5.5 CrashLoopBackOff Pods", "PASS",
                                  "No pods in CrashLoopBackOff state"))
    return checks


def _evaluate_node_utilization(top_nodes_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Node CPU and memory utilization from oc adm top nodes."""
    if _is_missing(top_nodes_data):
        return [_not_applicable(f"{category_id}.node_util", "Node Resource Utilization", category_id, category_name)]

    text = top_nodes_data.get("output", "")
    if not text.strip():
        return [_not_applicable(f"{category_id}.node_util", "Node Resource Utilization", category_id, category_name,
                    "oc adm top nodes returned no output (metrics-server may not be running)")]

    checks = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("NAME"):
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        check = _parse_top_node_line(parts, category_id, category_name)
        if check:
            checks.append(check)

    return checks or [_not_applicable(f"{category_id}.node_util", "Node Resource Utilization", category_id, category_name,
                          "Could not parse top nodes output")]


def _parse_top_node_line(parts: list[str], category_id: str, category_name: str) -> CheckResult | None:
    node_name = parts[0]
    short_name = node_name.split(".")[0]
    cpu_cores, cpu_pct = parts[1], parts[2]
    mem_bytes, mem_pct = parts[3], parts[4]
    cpu_percent = int(cpu_pct.rstrip("%")) if cpu_pct.rstrip("%").isdigit() else 0
    memory_percent = int(mem_pct.rstrip("%")) if mem_pct.rstrip("%").isdigit() else 0

    if cpu_percent > 80 or memory_percent > 85:
        status = "WARNING"
    elif cpu_percent > 60 or memory_percent > 70:
        status = "INFO"
    else:
        status = "PASS"

    return CheckResult(category_id, category_name, f"{category_id}.node.{short_name}.utilization",
                       f"7.5.7 Node Utilization: {short_name}", status,
                       f"CPU: {cpu_cores} ({cpu_pct}). Memory: {mem_bytes} ({mem_pct})",
                       node_name)


def _is_compact_cluster(items: list[dict], masters: list[dict]) -> bool:
    """True when every node is a master and every master also carries the
    'worker' role label — the supported 3-node compact/SNO-style topology
    where schedulable control-plane nodes are expected, not a misconfiguration.
    """
    if not masters or len(masters) != len(items):
        return False
    return all("worker" in node_roles(_resource_labels(node)) for node in masters)


def _evaluate_master_taints(nodes_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Control plane nodes should have NoSchedule taint, unless this is a
    supported compact cluster (masters are also workers by design)."""
    if _is_missing(nodes_data):
        return [_not_applicable(f"{category_id}.master_taints", "Master Node Taints", category_id, category_name)]

    items = _get_items(nodes_data)
    masters = []
    for item in items:
        labels = _resource_labels(item)
        if any(
            role_label.startswith("node-role.kubernetes.io/master")
            or role_label.startswith("node-role.kubernetes.io/control-plane")
            for role_label in labels
        ):
            masters.append(item)
    missing_taint = []
    for node in masters:
        taints = node.get("spec", {}).get("taints", [])
        has_noschedule = any(taint.get("effect") == "NoSchedule" and
                             "master" in taint.get("key", "") for taint in taints)
        if not has_noschedule:
            missing_taint.append(node.get("metadata", {}).get("name", "unknown"))

    if not missing_taint:
        return [CheckResult(category_id, category_name, f"{category_id}.master_taints",
                            "7.5.8 Master Node NoSchedule Taints", "PASS",
                            f"All {len(masters)} control plane node(s) have NoSchedule taint",
                            "nodes")]
    if _is_compact_cluster(items, masters):
        return [CheckResult(category_id, category_name, f"{category_id}.master_taints",
                            "7.5.8 Master Node NoSchedule Taints", "INFO",
                            f"{len(missing_taint)} control plane node(s) missing NoSchedule taint, but this is a "
                            "compact cluster (all nodes are master+worker) — schedulable control plane is the "
                            "supported topology for this configuration",
                            "nodes", doc_ref=_COMPACT_CLUSTER_DOC_REF)]
    return [CheckResult(category_id, category_name, f"{category_id}.master_taints",
                        "7.5.8 Master Node NoSchedule Taints", "WARNING",
                        f"{len(missing_taint)} control plane node(s) missing NoSchedule taint: "
                        f"{', '.join(missing_taint[:3])}. "
                        "Workloads may be scheduled on control plane nodes",
                        "nodes")]


def _evaluate_k8s_version(nodes_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Kubelet version consistency across nodes."""
    if _is_missing(nodes_data):
        return [_not_applicable(f"{category_id}.k8s_version", "Kubernetes Version Consistency", category_id, category_name)]

    items = _get_items(nodes_data)
    versions: Counter = Counter(
        _node_info(item).get("kubeletVersion", "unknown")
        for item in items
    )
    if len(versions) > 1:
        ver_summary = ", ".join(f"{version}={count}" for version, count in versions.most_common())
        return [CheckResult(category_id, category_name, f"{category_id}.k8s_version",
                            "7.5.9 Kubernetes Version Consistency", "WARNING",
                            f"Mixed kubelet versions detected: {ver_summary}. "
                            "Ensure MachineConfigPool update is not stalled",
                            "nodes")]
    dominant = list(versions.keys())[0] if versions else "unknown"
    return [CheckResult(category_id, category_name, f"{category_id}.k8s_version",
                        "7.5.9 Kubernetes Version Consistency", "PASS",
                        f"All {len(items)} nodes running kubelet {dominant}", "nodes")]


def _evaluate_pruning(events_data: dict, jobs_data: dict, pods_data: dict,
                   category_id: str, category_name: str) -> list[CheckResult]:
    """Detect completed/failed pod accumulation and stale jobs."""
    checks = []

    if not _is_missing(pods_data):
        items = _get_items(pods_data)
        completed = [pod for pod in items if _resource_status(pod).get("phase") == "Succeeded"]
        failed_pods = [pod for pod in items if _resource_status(pod).get("phase") == "Failed"]
        if len(completed) > 200 or len(failed_pods) > 50:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.pruning.pods",
                                      "7.5.10 Pod Pruning", "WARNING",
                                      f"{len(completed)} Succeeded pods, {len(failed_pods)} Failed pods. "
                                      "Configure automatic pruning via openshift.io/build-prune annotation "
                                      "or CronJob-based cleanup",
                                      "pods"))
        else:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.pruning.pods",
                                      "7.5.10 Pod Pruning", "PASS",
                                      f"{len(completed)} Succeeded, {len(failed_pods)} Failed pods — "
                                      "accumulation within acceptable range",
                                      "pods"))

    if not _is_missing(jobs_data):
        job_items = _get_items(jobs_data)
        stale = [
            job for job in job_items
            if _resource_status(job).get("completionTime")
            and not _resource_metadata(job).get("ownerReferences")
        ]
        if len(stale) > 100:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.pruning.jobs",
                                      "7.5.11 Job Pruning", "WARNING",
                                      f"{len(stale)} orphaned completed Jobs. "
                                      "Set ttlSecondsAfterFinished on Jobs or use a cleanup CronJob",
                                      "jobs"))
        else:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.pruning.jobs",
                                      "7.5.11 Job Pruning", "PASS",
                                      f"{len(job_items)} Jobs total, {len(stale)} completed orphaned — acceptable",
                                      "jobs"))
    return checks


def _evaluate_health_kubelet(nodes_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    if _is_missing(nodes_data):
        return [CheckResult(category_id, category_name, f"{category_id}.kubelet_health",
                            "5.1 Node Kubelet Health", "SKIPPED",
                            "Node data not available", "nodes")]
    items = _get_items(nodes_data)
    not_ready = []
    for node in items:
        conditions = node.get("status", {}).get("conditions", [])
        ready = next((condition for condition in conditions if condition.get("type") == "Ready"), {})
        if ready.get("status") != "True":
            not_ready.append(node.get("metadata", {}).get("name", "?"))
    if not_ready:
        return [CheckResult(category_id, category_name, f"{category_id}.kubelet_health",
                            "5.1 Node Kubelet Health", "WARNING",
                            f"{len(not_ready)} node(s) not Ready: {', '.join(not_ready[:3])}",
                            "nodes")]
    return [CheckResult(category_id, category_name, f"{category_id}.kubelet_health",
                        "5.1 Node Kubelet Health", "PASS",
                        f"All {len(items)} nodes in Ready state", "nodes")]


def _evaluate_health_machine_config(results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    machine_config_pool_data = results.get("05_components", {}).get("machineconfig", {})
    if _is_missing(machine_config_pool_data):
        return [CheckResult(category_id, category_name, f"{category_id}.mcp_health",
                            "5.2 Machine Config", "SKIPPED",
                            "MachineConfig data not available", "machineconfig")]
    machine_config_items = _get_items(machine_config_pool_data, default_single=True)
    degraded, _ = check_mcp_degraded(machine_config_pool_data)
    return [CheckResult(category_id, category_name, f"{category_id}.mcp_health",
                        "5.2 Machine Config",
                        "FAIL" if degraded else "PASS",
                        f"Degraded MCPs: {', '.join(degraded)}" if degraded
                        else f"{len(machine_config_items)} MachineConfig(s) healthy",
                        "machineconfig")]


def _evaluate_health_operator_state(cluster_operator_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    if _is_missing(cluster_operator_data):
        return [CheckResult(category_id, category_name, f"{category_id}.operator_state",
                            "5.3 Operator State", "SKIPPED",
                            "Cluster operator data not available", "clusteroperators")]
    cluster_operator_items = _get_items(cluster_operator_data, default_single=True)
    degraded_ops = find_degraded_operators(cluster_operator_data)
    return [CheckResult(category_id, category_name, f"{category_id}.operator_state",
                        "5.3 Operator State",
                        "FAIL" if degraded_ops else "PASS",
                        f"Degraded: {', '.join(degraded_ops[:5])}" if degraded_ops
                        else f"All {len(cluster_operator_items)} cluster operators healthy",
                        "clusteroperators")]


def _evaluate_health_registry(results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    reg = results.get("05_components", {}).get("imageregistry", {})
    if _is_missing(reg):
        return [CheckResult(category_id, category_name, f"{category_id}.registry_health",
                            "5.4 Registry Health", "SKIPPED",
                            "Registry data unavailable", "imageregistry")]
    management_state = reg.get("spec", {}).get("managementState", "unknown")
    if management_state == "Managed":
        status = "PASS"
    elif management_state in ("Unmanaged", "Removed"):
        status = "INFO"
    else:
        status = "WARNING"
    return [CheckResult(category_id, category_name, f"{category_id}.registry_health",
                        "5.4 Registry Health", status,
                        f"Registry managementState: {management_state}", "imageregistry")]


def _evaluate_health_pod_restarts(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    pods_data = category_data.get("pods_all", {})
    if _is_missing(pods_data):
        return [CheckResult(category_id, category_name, f"{category_id}.pod_restarts",
                            "5.5 Pod Frequent Restarts", "SKIPPED",
                            "Pod data unavailable", "pods")]
    high_restart = []
    for pod in _get_items(pods_data):
        for status in pod.get("status", {}).get("containerStatuses", []):
            if status.get("restartCount", 0) > 10:
                high_restart.append(
                    f"{pod.get('metadata', {}).get('namespace', '?')}/"
                    f"{pod.get('metadata', {}).get('name', '?')} ({status['restartCount']})"
                )
                break
    if high_restart:
        return [CheckResult(category_id, category_name, f"{category_id}.pod_restarts",
                            "5.5 Pod Frequent Restarts", "WARNING",
                            f"{len(high_restart)} pod(s) with >10 restarts: "
                            f"{', '.join(high_restart[:3])}", "pods")]
    return [CheckResult(category_id, category_name, f"{category_id}.pod_restarts",
                        "5.5 Pod Frequent Restarts", "PASS",
                        "No pods with excessive restarts (>10)", "pods")]


def _pod_keys_from_text(text: str) -> set[str]:
    return {f"{match.group(1)}/{match.group(2)}" for match in _POD_KEY_RE.finditer(text)}


def _collected_pod_keys(results: dict) -> set[str]:
    pods_all = results.get("07_cluster_health", {}).get("pods_all")
    if not pods_all:
        return set()
    keys: set[str] = set()
    for pod in _get_items(pods_all):
        metadata = pod.get("metadata", {})
        namespace = metadata.get("namespace", "")
        name = metadata.get("name", "")
        if namespace and name:
            keys.add(f"{namespace}/{name}")
    return keys


def annotate_pod_restart_collection_gap(checks: list[CheckResult], results: dict) -> None:
    engine_check = None
    tsr_check = None
    for check in checks:
        if check.check_id == "7.5.pod_restarts":
            engine_check = check
        elif check.check_id == "7.5.tsr.5_5_pod_frequent_restarts":
            tsr_check = check
    if engine_check is None or tsr_check is None:
        return
    missing_count = len(_pod_keys_from_text(tsr_check.evidence) - _collected_pod_keys(results))
    if missing_count == 0:
        return
    engine_check.evidence += (
        f"\nTSR 5.5 names {missing_count} pod key(s) not present in collected pods_all "
        "(collect gap, not the engine restart filter)."
    )


def _evaluate_health_node_roles(nodes_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    if _is_missing(nodes_data):
        return [CheckResult(category_id, category_name, f"{category_id}.node_roles",
                            "5.6 Node-Role Values", "SKIPPED",
                            "Node data unavailable", "nodes")]
    roles_set: set[str] = set()
    no_role = []
    for node in _get_items(nodes_data):
        roles = node_roles(_resource_labels(node))
        if not roles:
            no_role.append(node.get("metadata", {}).get("name", "?"))
        roles_set.update(roles)
    if no_role:
        return [CheckResult(category_id, category_name, f"{category_id}.node_roles",
                            "5.6 Node-Role Values", "FAIL",
                            f"{len(no_role)} node(s) missing role labels: {', '.join(no_role[:3])}",
                            "nodes")]
    return [CheckResult(category_id, category_name, f"{category_id}.node_roles",
                        "5.6 Node-Role Values", "PASS",
                        f"All nodes have role labels. Roles: {', '.join(sorted(roles_set))}",
                        "nodes")]


def _evaluate_health_static_checks(category_id: str, category_name: str) -> list[CheckResult]:
    return [
        CheckResult(category_id, category_name, f"{category_id}.machineset",
                    "5.8 Machine Set", "SKIPPED",
                    "MachineSet data not in standard collection", "machineset"),
        CheckResult(category_id, category_name, f"{category_id}.pdb",
                    "5.9 Pod Disruption Budget", "SKIPPED",
                    "PDB data not in standard collection", "pdb"),
        CheckResult(category_id, category_name, f"{category_id}.vol_mount",
                    "5.10 Volume Mount Durations", "SKIPPED",
                    "Requires Prometheus metrics not in standard collection", "metrics"),
    ]


def _evaluate_health_alert_breakdown(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    alerts_data = category_data.get("firing_alerts", {})
    if _is_missing(alerts_data):
        return [
            CheckResult(category_id, category_name, f"{category_id}.alerts.cp",
                        "5.11.1 Control Plane Alerts", "SKIPPED", "Alert data unavailable", "alerts"),
            CheckResult(category_id, category_name, f"{category_id}.alerts.node",
                        "5.11.2 Node Alerts", "SKIPPED", "Alert data unavailable", "alerts"),
            CheckResult(category_id, category_name, f"{category_id}.alerts.overcommit",
                        "5.11.3 Overcommit Alerts", "SKIPPED", "Alert data unavailable", "alerts"),
        ]
    alerts_list = _parse_alerts_list(alerts_data)
    cp_alerts = _alerts_matching(
        alerts_list, ("etcd", "kube", "apiserver", "scheduler", "controller"),
    )
    node_alerts = _alerts_matching(
        alerts_list, ("node", "kubelet", "machine"),
    )
    overcommit = _alerts_matching(
        alerts_list, ("overcommit", "quota", "resource", "memory", "cpu"),
    )
    return [
        CheckResult(category_id, category_name, f"{category_id}.alerts.cp",
                    "5.11.1 Control Plane Alerts",
                    "WARNING" if cp_alerts else "PASS",
                    f"{len(cp_alerts)} control plane alert(s)" if cp_alerts
                    else "No control plane alerts firing", "alerts"),
        CheckResult(category_id, category_name, f"{category_id}.alerts.node",
                    "5.11.2 Node Alerts",
                    "WARNING" if node_alerts else "PASS",
                    f"{len(node_alerts)} node alert(s)" if node_alerts
                    else "No node alerts firing", "alerts"),
        CheckResult(category_id, category_name, f"{category_id}.alerts.overcommit",
                    "5.11.3 Overcommit Alerts",
                    "WARNING" if overcommit else "PASS",
                    f"{len(overcommit)} overcommit/resource alert(s)" if overcommit
                    else "No overcommit alerts firing", "alerts"),
    ]


def _evaluate_health_dns(results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    dns_op = results.get("05_components", {}).get("dns_operator", {})
    if _is_missing(dns_op):
        return [CheckResult(category_id, category_name, f"{category_id}.dns_health",
                            "5.12 DNS Health", "SKIPPED",
                            "DNS operator data unavailable", "dns")]
    conditions = dns_op.get("status", {}).get("conditions", [])
    dns_avail = next((condition for condition in conditions if condition.get("type") == "Available"), {})
    return [CheckResult(category_id, category_name, f"{category_id}.dns_health",
                        "5.12 DNS Health",
                        "PASS" if dns_avail.get("status") == "True" else "WARNING",
                        f"DNS Operator Available: {dns_avail.get('status', 'unknown')}",
                        "dns")]


def _evaluate_tsr_health_aggregate(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """TSR 5.x: Aggregate cluster health checks."""
    nodes_data = category_data.get("nodes", {})
    cluster_operator_data = category_data.get("clusteroperators", results.get("05_components", {}).get("cluster_operators", {}))

    checks: list[CheckResult] = []
    checks += _evaluate_health_kubelet(nodes_data, category_id, category_name)
    checks += _evaluate_health_machine_config(results, category_id, category_name)
    checks += _evaluate_health_operator_state(cluster_operator_data, category_id, category_name)
    checks += _evaluate_health_registry(results, category_id, category_name)
    checks += _evaluate_health_pod_restarts(category_data, category_id, category_name)
    checks += _evaluate_health_node_roles(nodes_data, category_id, category_name)
    checks += _evaluate_health_static_checks(category_id, category_name)
    checks += _evaluate_health_alert_breakdown(category_data, category_id, category_name)
    checks += _evaluate_health_dns(results, category_id, category_name)
    return checks


def evaluate_cluster_health(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Dispatch evaluators for 7.5 Cluster Health (de-duplicated from 7.2/7.3)."""
    checks: list[CheckResult] = []
    day2 = results.get("08_day2", {})
    # TSR 5.x aggregate checks
    checks += _evaluate_tsr_health_aggregate(category_data, results, category_id, category_name)
    # Existing detailed checks
    checks += _evaluate_firing_alerts(category_data.get("firing_alerts", {}), category_id, category_name)
    checks += _evaluate_pod_health(category_data.get("pods_all", {}), category_id, category_name)
    checks += _evaluate_node_utilization(day2.get("top_nodes", {}), category_id, category_name)
    checks += _evaluate_master_taints(category_data.get("nodes", {}), category_id, category_name)
    checks += _evaluate_k8s_version(category_data.get("nodes", {}), category_id, category_name)
    checks += _evaluate_pruning(
        category_data.get("events", {}),
        category_data.get("jobs", {}),
        category_data.get("pods_all", {}),
        category_id, category_name,
    )
    return checks
