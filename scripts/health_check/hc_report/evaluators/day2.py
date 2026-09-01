"""Evaluators for 7.6 Day-2 Operations."""
from __future__ import annotations

from collections import Counter

from hc_report.evaluators._common import (
    _cluster_version_object,
    _evaluate_approval_strategy,
    _get_items,
    _is_missing,
    _not_applicable,
    _parse_prometheus_vector,
    _prometheus_value,
    _resource_labels,
    _resource_metadata,
    _resource_name,
    _resource_spec,
    _resource_status,
)
from hc_report.evaluators._shared_checks import check_csr_pending
from hc_report.evaluators.components_infra import _evaluate_storage
from hc_report.models import CheckResult

IMAGE_GC_HIGH_DEFAULT_PERCENT = 85
IMAGE_GC_EARLY_WARNING_PERCENT = 50
NODE_EXPECTED_LIMITS_FAIL_PERCENT = 90
NODE_EXPECTED_LIMITS_WARNING_PERCENT = 80
ALERTMANAGER_IGNORED_RECEIVER_NAMES = frozenset({
    "null",
    "Default",
    "default",
    "Watchdog",
    "watchdog",
})


def _image_gc_member_severity(member: dict) -> str:
    """Classify one collected node: FAIL, WARNING, PASS, or SKIP (no numeric used%)."""
    used_value = member.get("used_percent")
    if isinstance(used_value, bool) or not isinstance(used_value, (int, float)):
        return "SKIP"
    used_percent = int(used_value)
    high_value = member.get("high_percent")
    if isinstance(high_value, bool) or not isinstance(high_value, (int, float)):
        high_percent = IMAGE_GC_HIGH_DEFAULT_PERCENT
    else:
        high_percent = int(high_value)
    if used_percent >= high_percent:
        return "FAIL"
    if used_percent >= IMAGE_GC_EARLY_WARNING_PERCENT:
        return "WARNING"
    return "PASS"


def _evaluate_node_image_gc(
    image_gc_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.node.image_gc"
    title = "7.6 Node image garbage collection"
    if _is_missing(image_gc_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "INFO",
            "node_image_gc payload missing or collection error", "node_image_gc",
        )]
    members = image_gc_data.get("members")
    if not isinstance(members, list):
        members = []
    fail_nodes: list[str] = []
    warn_nodes: list[str] = []
    pass_count = 0
    for member in members:
        if not isinstance(member, dict):
            continue
        severity = _image_gc_member_severity(member)
        node_name = str(member.get("node", "?"))
        if severity == "SKIP":
            continue
        if severity == "FAIL":
            fail_nodes.append(node_name)
        elif severity == "WARNING":
            warn_nodes.append(node_name)
        else:
            pass_count += 1
    scored_count = len(fail_nodes) + len(warn_nodes) + pass_count
    if scored_count == 0:
        return [CheckResult(
            category_id, category_name, check_id, title, "INFO",
            "No member with numeric used_percent", "node_image_gc",
        )]
    if fail_nodes:
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            f"{len(fail_nodes)} node(s) at or above image-GC HIGH: {', '.join(fail_nodes[:5])}",
            "node_image_gc", scoring_basis="doc_backed",
        )]
    if warn_nodes:
        return [CheckResult(
            category_id, category_name, check_id, title, "WARNING",
            f"{len(warn_nodes)} node(s) at or above {IMAGE_GC_EARLY_WARNING_PERCENT}% imageFs used: "
            f"{', '.join(warn_nodes[:5])}",
            "node_image_gc",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"{pass_count} scored node(s) below {IMAGE_GC_EARLY_WARNING_PERCENT}% imageFs used",
        "node_image_gc",
    )]


def _evaluate_proxy(proxy_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Cluster-wide proxy configuration."""
    if _is_missing(proxy_data):
        return [_not_applicable(f"{category_id}.proxy", "Proxy Configuration", category_id, category_name)]

    spec = proxy_data.get("spec", {})
    http_proxy = spec.get("httpProxy", "")
    https_proxy = spec.get("httpsProxy", "")
    no_proxy = spec.get("noProxy", "")

    if http_proxy or https_proxy:
        return [CheckResult(category_id, category_name, f"{category_id}.proxy",
                            "7.6.4 Cluster Proxy", "INFO",
                            f"Proxy configured. HTTP: {http_proxy or 'none'}. "
                            f"HTTPS: {https_proxy or 'none'}. noProxy: {no_proxy or 'none'}",
                            "proxy")]
    return [CheckResult(category_id, category_name, f"{category_id}.proxy",
                        "7.6.4 Cluster Proxy", "PASS",
                        "No cluster-wide proxy configured — direct internet access", "proxy")]


def _evaluate_resource_quotas(resource_quota_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Resource quota presence.

    # OPTIONAL_FEATURE: ResourceQuota is an optional governance control. Data
    # collection failure is SKIPPED (we don't know); zero quotas defined is a
    # legitimate, common configuration and is INFO, not WARNING.
    """
    if _is_missing(resource_quota_data):
        return [CheckResult(category_id, category_name, f"{category_id}.rq",
                            "7.6.5 Resource Quotas", "SKIPPED",
                            "ResourceQuota data was not collected", "resourcequota")]
    items = _get_items(resource_quota_data, default_single=True)
    actual = [item for item in items if not item.get("_hc_not_found")]
    if not actual:
        return [CheckResult(category_id, category_name, f"{category_id}.rq",
                            "7.6.5 Resource Quotas", "INFO",
                            "No resource quotas defined on any namespace. Consider defining quotas "
                            "to prevent resource exhaustion if multi-tenant workloads are expected",
                            "resourcequota")]
    namespaces = [_resource_metadata(item).get("namespace") for item in actual]
    return [CheckResult(category_id, category_name, f"{category_id}.rq",
                        "7.6.5 Resource Quotas", "PASS",
                        f"{len(actual)} resource quota(s) in namespace(s): "
                        f"{', '.join(str(namespace_name) for namespace_name in namespaces[:5])}", "resourcequota")]


def _is_platform_project_namespace(name: str) -> bool:
    if name.startswith("openshift-") or name.startswith("kube-"):
        return True
    return name in {"default", "openshift"}


def _namespaced_coverage_namespaces(payload: dict) -> set[str]:
    covered: set[str] = set()
    for item in _get_items(payload, default_single=True):
        if not isinstance(item, dict):
            continue
        if item.get("_hc_not_found") or item.get("_hc_error"):
            continue
        namespace = _resource_metadata(item).get("namespace")
        if namespace:
            covered.add(str(namespace))
    return covered


def _evaluate_quota_coverage(
    namespaces_data: dict,
    resourcequota_data: dict,
    limitrange_data: dict,
    category_id: str,
    category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.quota.coverage"
    title = "User project quota coverage"
    if (
        namespaces_data.get("_hc_error")
        or resourcequota_data.get("_hc_error")
        or limitrange_data.get("_hc_error")
    ):
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "Namespace, ResourceQuota, or LimitRange payload collection error",
            "namespaces",
        )]
    if not namespaces_data:
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "Namespace payload missing",
            "namespaces",
        )]
    covered = _namespaced_coverage_namespaces(resourcequota_data)
    covered.update(_namespaced_coverage_namespaces(limitrange_data))
    uncovered: list[str] = []
    user_count = 0
    for item in _get_items(namespaces_data):
        if not isinstance(item, dict):
            continue
        name = _resource_name(item, default="")
        if _is_platform_project_namespace(name):
            continue
        user_count += 1
        if name not in covered:
            uncovered.append(name)
    if user_count == 0:
        return [_not_applicable(
            check_id, title, category_id, category_name,
            evidence="No user namespaces to score for quota coverage",
        )]
    if uncovered:
        preview = ", ".join(uncovered[:5])
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            f"{len(uncovered)} user namespace(s) with neither ResourceQuota nor LimitRange: {preview}",
            "namespaces",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"All {user_count} user namespace(s) have ResourceQuota or LimitRange",
        "namespaces",
    )]


def _evaluate_upgrade_history(cluster_version_raw: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Upgrade history from ClusterVersion."""
    cluster_version = _cluster_version_object(cluster_version_raw)
    if not cluster_version or cluster_version.get("_hc_error") or cluster_version.get("_hc_not_found"):
        return [_not_applicable(f"{category_id}.upgrade", "Upgrade History", category_id, category_name)]

    history = cluster_version.get("status", {}).get("history", [])
    completed = [history_entry for history_entry in history if history_entry.get("state") == "Completed"]
    if not completed:
        return [CheckResult(category_id, category_name, f"{category_id}.upgrade.history",
                            "7.6.6 Upgrade History", "NOT_APPLICABLE",
                            "No completed upgrades in history", "clusterversion")]

    last = completed[0]
    prev = completed[1] if len(completed) > 1 else {}
    summary = (
        f"{len(completed)} completed upgrade(s). "
        f"Latest: {last.get('version')} ({last.get('completionTime', '')[:10]})"
    )
    if prev:
        summary += f". Previous: {prev.get('version')} ({prev.get('completionTime', '')[:10]})"
    return [CheckResult(category_id, category_name, f"{category_id}.upgrade.history",
                        "7.6.6 Upgrade History", "PASS", summary, "clusterversion")]


_PARTIAL_OR_FAILED_STATES = frozenset({"Partial", "Failed"})


def _partial_or_failed_versions(history: list) -> list[str]:
    """Return version labels for hops whose state is Partial or Failed."""
    versions: list[str] = []
    for hop in history:
        if not isinstance(hop, dict):
            continue
        if hop.get("state") not in _PARTIAL_OR_FAILED_STATES:
            continue
        version = hop.get("version")
        versions.append(str(version) if version else str(hop.get("state")))
    return versions


def _evaluate_upgrade_failed_hops(
    cluster_version_raw: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    """FAIL when ClusterVersion history contains Partial or Failed hops."""
    check_id = f"{category_id}.upgrade.failed_hops"
    title = "ClusterVersion failed or partial hops"
    cluster_version = _cluster_version_object(cluster_version_raw)
    if cluster_version_raw.get("_hc_error") or cluster_version.get("_hc_error"):
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "clusterversion payload collection error", "clusterversion",
        )]
    if (
        not cluster_version
        or cluster_version_raw.get("_hc_not_found")
        or cluster_version.get("_hc_not_found")
    ):
        return [_not_applicable(
            check_id, title, category_id, category_name,
            evidence="clusterversion payload missing",
        )]
    status = cluster_version.get("status")
    if not isinstance(status, dict):
        status = {}
    history = status.get("history")
    if not isinstance(history, list) or not history:
        return [_not_applicable(
            check_id, title, category_id, category_name,
            evidence="No ClusterVersion history hops",
        )]
    failed_versions = _partial_or_failed_versions(history)
    if failed_versions:
        preview = ", ".join(failed_versions[:5])
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            f"{len(failed_versions)} Partial or Failed hop(s): {preview}",
            "clusterversion", scoring_basis="doc_backed",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"{len(history)} history hop(s) with no Partial or Failed state",
        "clusterversion",
    )]


def _evaluate_apiserver_config(apiserver_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """API server TLS profile and audit policy."""
    if _is_missing(apiserver_data):
        return [_not_applicable(f"{category_id}.apiserver", "API Server Configuration", category_id, category_name)]

    checks = []
    spec = apiserver_data.get("spec", {})
    tls = spec.get("tlsSecurityProfile", {})

    if not tls:
        tls_status, tls_ev = "PASS", "TLS security profile: default (Intermediate) — TLS 1.2+"
    elif tls.get("type") == "Old":
        tls_status = "WARNING"
        tls_ev = "TLS profile: Old — includes TLS 1.0/1.1, not recommended for production"
    elif tls.get("type") == "Custom":
        ciphers = tls.get("custom", {}).get("ciphers", [])
        tls_status, tls_ev = "INFO", f"TLS profile: Custom — {len(ciphers)} cipher(s) configured"
    else:
        tls_status, tls_ev = "PASS", f"TLS profile: {tls.get('type', 'Intermediate')}"
    checks.append(CheckResult(category_id, category_name, f"{category_id}.apiserver.tls",
                              "7.6.7 API Server TLS Profile", tls_status, tls_ev, "apiserver"))

    audit_profile = spec.get("audit", {}).get("profile", "Default")
    if audit_profile == "None":
        checks.append(CheckResult(category_id, category_name, f"{category_id}.apiserver.audit",
                                  "7.6.8 API Server Audit Policy", "WARNING",
                                  "Audit profile: None — audit logging is disabled. "
                                  "Red Hat recommends keeping audit logging enabled.",
                                  "apiserver"))
    elif audit_profile in {"WriteRequestBodies", "AllRequestBodies"}:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.apiserver.audit",
                                  "7.6.8 API Server Audit Policy", "PASS",
                                  f"Audit profile: {audit_profile} (enhanced auditing enabled)",
                                  "apiserver"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.apiserver.audit",
                                  "7.6.8 API Server Audit Policy", "PASS",
                                  f"Audit profile: {audit_profile} (RH-supported default). "
                                  "For enhanced compliance auditing, consider WriteRequestBodies.",
                                  "apiserver"))
    return checks


def _evaluate_namespaces(namespace_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Namespace count and user namespace sprawl check."""
    if _is_missing(namespace_data):
        return [_not_applicable(f"{category_id}.namespaces", "Namespace Inventory", category_id, category_name)]

    items = _get_items(namespace_data)
    system_prefixes = ("openshift-", "kube-", "openshift", "default", "kube")
    user_namespaces = []
    for item in items:
        name = _resource_name(item, default="")
        if not any(name.startswith(prefix) for prefix in system_prefixes):
            user_namespaces.append(name)
    total = len(items)

    if len(user_namespaces) > 50:
        status = "WARNING"
        evidence = (f"{total} total namespaces. {len(user_namespaces)} user namespaces — "
              f"review for namespace sprawl. Examples: {', '.join(user_namespaces[:5])}")
    else:
        status = "PASS"
        evidence = (f"{total} total namespaces ({total - len(user_namespaces)} platform, {len(user_namespaces)} user). "
              f"User namespaces: {', '.join(user_namespaces[:10]) if user_namespaces else 'none'}")
    return [CheckResult(category_id, category_name, f"{category_id}.namespaces",
                        "7.6.9 Namespace Inventory", status, evidence, "namespaces")]


def _evaluate_limit_ranges(limit_range_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Evaluate actual LimitRange content and coverage.

    # OPTIONAL_FEATURE: LimitRange is an optional governance control (see
    # ResourceQuota above for the same SKIPPED-vs-INFO rationale).
    """
    if _is_missing(limit_range_data):
        return [CheckResult(category_id, category_name, f"{category_id}.limitranges",
                            "7.6.10 LimitRanges", "SKIPPED",
                            "LimitRange data was not collected", "limitrange")]
    items = _get_items(limit_range_data, default_single=True)
    actual = [item for item in items if not item.get("_hc_not_found") and not item.get("_hc_error")]
    if not actual:
        return [CheckResult(category_id, category_name, f"{category_id}.limitranges",
                            "7.6.10 LimitRanges", "INFO",
                            "No LimitRanges defined on any namespace. Without LimitRanges, containers "
                            "can consume unlimited resources within a namespace if not otherwise constrained",
                            "limitrange")]
    namespaces = list({_resource_metadata(item).get("namespace", "unknown") for item in actual})
    return [CheckResult(category_id, category_name, f"{category_id}.limitranges",
                        "7.6.10 LimitRanges", "PASS",
                        f"{len(actual)} LimitRange(s) across namespace(s): "
                        f"{', '.join(namespaces[:5])}",
                        "limitrange")]


def _container_missing_cpu_or_memory_request(container: dict) -> bool:
    resources = container.get("resources")
    if not isinstance(resources, dict):
        return True
    requests = resources.get("requests")
    if not isinstance(requests, dict):
        return True
    cpu = requests.get("cpu")
    memory = requests.get("memory")
    if cpu is None or cpu == "":
        return True
    if memory is None or memory == "":
        return True
    return False


def _evaluate_pod_requests(
    pods_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.pod.requests"
    title = "Pod CPU and memory requests"
    if pods_data.get("_hc_error"):
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "pods_all payload collection error", "pods_all",
        )]
    if not pods_data or pods_data.get("_hc_not_found"):
        return [_not_applicable(
            check_id, title, category_id, category_name,
            evidence="pods_all payload missing",
        )]
    items = [item for item in _get_items(pods_data) if isinstance(item, dict)]
    if not items:
        return [_not_applicable(
            check_id, title, category_id, category_name,
            evidence="No pods in pods_all",
        )]
    missing: list[str] = []
    for pod in items:
        namespace = str(_resource_metadata(pod).get("namespace", ""))
        if _is_platform_project_namespace(namespace):
            continue
        phase = str(_resource_status(pod).get("phase", ""))
        if phase in {"Succeeded", "Failed"}:
            continue
        containers = _resource_spec(pod).get("containers")
        if not isinstance(containers, list):
            continue
        if any(
            isinstance(container, dict) and _container_missing_cpu_or_memory_request(container)
            for container in containers
        ):
            missing.append(f"{namespace}/{_resource_name(pod)}")
    if missing:
        preview = ", ".join(missing[:5])
        return [CheckResult(
            category_id, category_name, check_id, title, "WARNING",
            f"{len(missing)} user pod(s) missing CPU or memory requests: {preview}",
            "pods_all",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        "All scored user active pods have CPU and memory requests",
        "pods_all",
    )]


def _evaluate_operator_approval(subscriptions_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Flag subscriptions using Automatic installPlanApproval."""
    if _is_missing(subscriptions_data):
        return [_not_applicable(f"{category_id}.op_approval", "Operator Approval Strategy", category_id, category_name)]
    items = _get_items(subscriptions_data)
    return [_evaluate_approval_strategy(
        items, category_id, category_name, f"{category_id}.op_approval", "7.6.11 Operator Approval Strategy",
    )]


def _evaluate_deploymentconfigs(deployment_config_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """DeploymentConfigs are deprecated since OCP 4.14."""
    if _is_missing(deployment_config_data):
        return [CheckResult(category_id, category_name, f"{category_id}.deploymentconfigs",
                            "7.6.12 DeploymentConfig Usage", "NOT_APPLICABLE",
                            "No DeploymentConfigs found (or resource not available on this cluster). "
                            "This is expected if workloads have migrated to Deployments",
                            "deploymentconfig")]
    items = _get_items(deployment_config_data)
    if not items:
        return [CheckResult(category_id, category_name, f"{category_id}.deploymentconfigs",
                            "7.6.12 DeploymentConfig Usage", "PASS",
                            "No DeploymentConfigs in use. Workloads use modern Deployments",
                            "deploymentconfig")]
    namespace_names = [
        f"{_resource_metadata(item).get('namespace', 'unknown')}/"
        f"{_resource_name(item, default='unknown')}"
        for item in items[:5]
    ]
    return [CheckResult(category_id, category_name, f"{category_id}.deploymentconfigs",
                        "7.6.12 DeploymentConfig Usage", "WARNING",
                        f"{len(items)} DeploymentConfig(s) still in use: {', '.join(namespace_names)}. "
                        "DCs are deprecated in OCP 4.14+ — migrate to Deployments",
                        "deploymentconfig")]


def _evaluate_day2_quota_checks(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    checks: list[CheckResult] = []
    resource_quota = category_data.get("resourcequota", {})
    if not _is_missing(resource_quota):
        items = _get_items(resource_quota, default_single=True)
        checks.append(CheckResult(category_id, category_name, f"{category_id}.cluster_quota",
                                  "6.1.1.2 Cluster Quota Configuration",
                                  "PASS" if items else "NOT_APPLICABLE",
                                  f"{len(items)} quota(s) configured" if items
                                  else "No cluster-level quotas", "resourcequota"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.cluster_quota",
                                  "6.1.1.2 Cluster Quota Configuration", "NOT_APPLICABLE",
                                  "No resource quota data", "resourcequota"))
    limit_range = category_data.get("limitrange", {})
    if not _is_missing(limit_range):
        actual = [item for item in _get_items(limit_range, default_single=True) if not item.get("_hc_not_found")]
        # OPTIONAL_FEATURE: no LimitRanges is a legitimate configuration, not a defect.
        checks.append(CheckResult(category_id, category_name, f"{category_id}.req_limits",
                                  "6.1.2 Requests and Limits",
                                  "PASS" if actual else "INFO",
                                  f"{len(actual)} LimitRange(s) enforcing defaults" if actual
                                  else "No LimitRanges — pods can run without resource constraints "
                                  "unless requests/limits are set per-workload",
                                  "limitrange"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.req_limits",
                                  "6.1.2 Requests and Limits", "SKIPPED",
                                  "No LimitRange data collected", "limitrange"))
    return checks


def _node_expected_limit_samples(
    cpu_data: dict, memory_data: dict,
) -> list[tuple[str, str, float]]:
    samples: list[tuple[str, str, float]] = []
    for resource_kind, payload in (("cpu", cpu_data), ("memory", memory_data)):
        if _is_missing(payload):
            continue
        for item in _parse_prometheus_vector(payload):
            metric = item.get("metric", {}) if isinstance(item, dict) else {}
            node_name = str(metric.get("node") or "unknown")
            samples.append((node_name, resource_kind, _prometheus_value(item)))
    return samples


def _evaluate_node_expected_limits(
    cpu_data: dict, memory_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    """Cluster rollup of node CPU/memory limits vs allocatable from Prometheus."""
    check_id = f"{category_id}.node.expected_limits"
    title = "Node expected resource limits"
    cpu_payload = cpu_data if isinstance(cpu_data, dict) else {}
    memory_payload = memory_data if isinstance(memory_data, dict) else {}
    if _is_missing(cpu_payload) and _is_missing(memory_payload):
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "node_cpu_limits_pct and node_memory_limits_pct missing",
            "node_cpu_limits_pct",
        )]
    samples = _node_expected_limit_samples(cpu_payload, memory_payload)
    peak_percent = max((percent for _, _, percent in samples), default=0.0)
    if peak_percent >= NODE_EXPECTED_LIMITS_FAIL_PERCENT:
        status = "FAIL"
    elif peak_percent >= NODE_EXPECTED_LIMITS_WARNING_PERCENT:
        status = "WARNING"
    else:
        status = "PASS"
    if samples:
        shown = samples[:10]
        evidence = "; ".join(
            f"{node_name} {resource_kind} {percent:g}%"
            for node_name, resource_kind, percent in shown
        )
        if len(samples) > len(shown):
            evidence += f" (+{len(samples) - len(shown)} more)"
    else:
        evidence = "No Prometheus limit-percent samples"
    return [CheckResult(
        category_id, category_name, check_id, title, status, evidence,
        "node_cpu_limits_pct",
    )]


def _evaluate_day2_capacity_checks(results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    checks = [
        CheckResult(category_id, category_name, f"{category_id}.node_expected",
                    "6.1.3.2 Node Expected Resource Consumption", "SKIPPED",
                    "Requires capacity planning metrics not in standard collection", "metrics"),
    ]
    persistent_volume = results.get("05_components", {}).get("pv", {})
    if _is_missing(persistent_volume):
        checks.append(CheckResult(category_id, category_name, f"{category_id}.pv_usage",
                                  "6.1.4 Persistent Volume Usage", "SKIPPED",
                                  "PV data unavailable", "pv"))
        return checks
    pv_items = _get_items(persistent_volume)
    phases = Counter(_resource_status(item).get("phase") for item in pv_items)
    checks.append(CheckResult(category_id, category_name, f"{category_id}.pv_usage",
                              "6.1.4 Persistent Volume Usage", "PASS",
                              f"{len(pv_items)} PVs: {dict(phases)}", "pv"))
    return checks


def _evaluate_day2_pruning(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    namespace_data = category_data.get("namespaces", {})
    namespace_count = len(_get_items(namespace_data)) if not _is_missing(namespace_data) else 0
    namespace_status = "WARNING" if namespace_count > 100 else "PASS"
    namespace_evidence = (
        f"{namespace_count} namespaces — review for stale/unused namespaces"
        if namespace_status == "WARNING"
        else f"{namespace_count} namespaces — within manageable range"
    )
    return [
        CheckResult(category_id, category_name, f"{category_id}.prune.builds",
                    "6.1.5.2 Build Pruning", "PASS",
                    "Build pruning: OpenShift defaults handle this", "builds"),
        CheckResult(category_id, category_name, f"{category_id}.prune.netpol",
                    "6.1.5.3 Network Policy Pruning", "SKIPPED",
                    "NetworkPolicy audit not in standard collection", "networkpolicy"),
        CheckResult(category_id, category_name, f"{category_id}.prune.gc",
                    "6.1.5.5 Node Garbage Collection", "SKIPPED",
                    "Requires kubelet config inspection not in standard collection", "gc"),
        CheckResult(category_id, category_name, f"{category_id}.prune.ns",
                    "6.1.5.6 Pruning Namespaces", namespace_status, namespace_evidence, "namespaces"),
    ]


def _pod_labels_match_selector(pod: dict, match_labels: dict) -> bool:
    labels = _resource_labels(pod) or {}
    if not isinstance(labels, dict):
        return False
    for key, value in match_labels.items():
        if labels.get(key) != value:
            return False
    return True


def _labeled_selector_pod_count(
    pods: list, namespace: str, match_labels: dict,
) -> int:
    matched = 0
    for pod in pods:
        if str(_resource_metadata(pod).get("namespace", "")) != namespace:
            continue
        phase = str(_resource_status(pod).get("phase", ""))
        if phase in {"Succeeded", "Failed"}:
            continue
        if _pod_labels_match_selector(pod, match_labels):
            matched += 1
    return matched


def _evaluate_netpol_orphan(
    networkpolicy_data: dict,
    pods_data: dict,
    category_id: str,
    category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.netpol.orphan"
    title = "Orphan user NetworkPolicies"
    if _is_missing(networkpolicy_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "networkpolicy payload missing or collection error", "networkpolicy",
        )]
    if _is_missing(pods_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "pods_all payload missing or collection error — cannot evaluate orphan selectors",
            "networkpolicy",
        )]
    policies = [item for item in _get_items(networkpolicy_data) if isinstance(item, dict)]
    pods = [item for item in _get_items(pods_data) if isinstance(item, dict)]
    user_policy_count = 0
    orphans: list[str] = []
    for policy in policies:
        namespace = str(_resource_metadata(policy).get("namespace", ""))
        if _is_platform_project_namespace(namespace):
            continue
        user_policy_count += 1
        pod_selector = _resource_spec(policy).get("podSelector")
        if not isinstance(pod_selector, dict):
            continue
        match_labels = pod_selector.get("matchLabels")
        match_expressions = pod_selector.get("matchExpressions")
        if isinstance(match_expressions, list) and match_expressions:
            if not isinstance(match_labels, dict) or not match_labels:
                continue
        if not isinstance(match_labels, dict) or not match_labels:
            continue
        matched = _labeled_selector_pod_count(pods, namespace, match_labels)
        if matched == 0:
            orphans.append(f"{namespace}/{_resource_name(policy)}")
    if user_policy_count == 0:
        return [CheckResult(
            category_id, category_name, check_id, title, "INFO",
            "No user-namespace NetworkPolicies", "networkpolicy",
        )]
    if orphans:
        preview = ", ".join(orphans[:5])
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            f"{len(orphans)} orphan labeled NetworkPolicy selector(s): {preview}",
            "networkpolicy",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"{user_policy_count} user NetworkPolicy(s) with no orphan labeled selectors",
        "networkpolicy",
    )]


def _evaluate_day2_infra_nodes(results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    nodes_data = results.get("03_base_platform", {}).get("nodes", {})
    if _is_missing(nodes_data):
        return [CheckResult(category_id, category_name, f"{category_id}.infra_nodes",
                            "6.1.6 Infra Node Workloads", "SKIPPED",
                            "Node data unavailable", "nodes")]
    infra_nodes = [
        node for node in _get_items(nodes_data)
        if "node-role.kubernetes.io/infra" in _resource_labels(node)
    ]
    if infra_nodes:
        return [CheckResult(category_id, category_name, f"{category_id}.infra_nodes",
                            "6.1.6 Infra Node Workloads", "PASS",
                            f"{len(infra_nodes)} infra node(s) available for infrastructure workloads",
                            "nodes")]
    return [CheckResult(category_id, category_name, f"{category_id}.infra_nodes",
                        "6.1.6 Infra Node Workloads", "NOT_APPLICABLE",
                        "No dedicated infra nodes (infra workloads run on worker nodes)",
                        "nodes")]


def _evaluate_alert_receivers(
    receivers_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.alert_receivers"
    title = "Alert receivers"
    if not isinstance(receivers_data, dict) or _is_missing(receivers_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "alertmanager_receivers payload missing or collection error",
            "alertmanager_receivers",
        )]
    raw_names = receivers_data.get("receiver_names")
    if not isinstance(raw_names, list):
        raw_names = []
    kept_names: list[str] = []
    for raw_name in raw_names:
        if not isinstance(raw_name, str):
            continue
        if raw_name in ALERTMANAGER_IGNORED_RECEIVER_NAMES:
            continue
        kept_names.append(raw_name)
    if not kept_names:
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            "No Alertmanager receivers after ignoring null, Default, and Watchdog",
            "alertmanager_receivers",
        )]
    preview = ", ".join(kept_names[:8])
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"{len(kept_names)} configured receiver(s): {preview}",
        "alertmanager_receivers",
    )]


def _evaluate_day2_image_and_alert_checks(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    checks = [
        CheckResult(category_id, category_name, f"{category_id}.update_impact",
                    "6.2.2 Update Impacting Workloads", "SKIPPED",
                    "Requires upgrade history correlation not in standard collection",
                    "clusterversion"),
    ]
    checks += _evaluate_alert_receivers(
        category_data.get("alertmanager_receivers") or {},
        category_id,
        category_name,
    )
    checks.append(CheckResult(
        category_id, category_name, f"{category_id}.remote_health",
        "6.3.3 Retrieves Updates", "SKIPPED",
        "Remote health verification requires live API access",
        "insights",
    ))
    image_config_data = category_data.get("image_config", {})
    if _is_missing(image_config_data):
        checks.append(CheckResult(category_id, category_name, f"{category_id}.image_mgmt",
                                  "6.2.3 Images Patch Management", "SKIPPED",
                                  "Image configuration data was not collected", "image_config"))
        checks += _evaluate_image_registry_sources(image_config_data, category_id, category_name)
        return checks
    registries = image_config_data.get("spec", {}).get("registrySources") or {}
    if not isinstance(registries, dict):
        registries = {}
    allowed = registries.get("allowedRegistries", [])
    blocked = registries.get("blockedRegistries", [])
    checks.append(CheckResult(category_id, category_name, f"{category_id}.image_mgmt",
                              "6.2.3 Images Patch Management", "INFO",
                              f"Image policy: {len(allowed)} allowed, {len(blocked)} blocked registries",
                              "image_config"))
    checks += _evaluate_image_registry_sources(image_config_data, category_id, category_name)
    return checks


def _registry_source_list(value: object) -> list:
    if isinstance(value, list):
        return value
    return []


def _evaluate_image_registry_sources(
    image_config_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.image.registry_sources"
    title = "Image registry sources"
    if image_config_data.get("_hc_error"):
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "image_config payload collection error", "image_config",
        )]
    if not image_config_data or image_config_data.get("_hc_not_found"):
        return [_not_applicable(
            check_id, title, category_id, category_name,
            evidence="image_config payload missing",
        )]
    sources = _resource_spec(image_config_data).get("registrySources")
    if not isinstance(sources, dict):
        sources = {}
    allowed = _registry_source_list(sources.get("allowedRegistries"))
    blocked = _registry_source_list(sources.get("blockedRegistries"))
    insecure = _registry_source_list(sources.get("insecureRegistries"))
    if allowed and blocked:
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            "allowedRegistries and blockedRegistries are both non-empty",
            "image_config",
        )]
    if insecure:
        return [CheckResult(
            category_id, category_name, check_id, title, "WARNING",
            f"{len(insecure)} insecureRegistries entry(s)",
            "image_config",
        )]
    if not allowed and not blocked:
        return [CheckResult(
            category_id, category_name, check_id, title, "INFO",
            "allowedRegistries and blockedRegistries are empty (connected-cluster default)",
            "image_config",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        "allow-only or block-only registrySources with no insecureRegistries",
        "image_config",
    )]


def _evaluate_day2_cert_checks(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    checks: list[CheckResult] = []
    csr = results.get("03_base_platform", {}).get("csr", {})
    if not _is_missing(csr):
        csr_items = _get_items(csr)
        pending, _, _ = check_csr_pending(csr)
        checks.append(CheckResult(category_id, category_name, f"{category_id}.csr_pending",
                                  "6.4.1 Pending Certificate Requests",
                                  "WARNING" if pending else "PASS",
                                  f"{len(pending)} pending CSR(s)" if pending
                                  else f"All {len(csr_items)} CSR(s) processed", "csr"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.csr_pending",
                                  "6.4.1 Pending Certificate Requests", "SKIPPED",
                                  "CSR data unavailable", "csr"))
    certs = category_data.get("certificates", {})
    if not _is_missing(certs):
        cert_items = _get_items(certs, default_single=True)
        checks.append(CheckResult(category_id, category_name, f"{category_id}.custom_certs",
                                  "6.4.2 Custom Certificates", "PASS",
                                  f"{len(cert_items)} certificate resource(s) found", "certificates"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.custom_certs",
                                  "6.4.2 Custom Certificates", "PASS",
                                  "No custom certificate resources (using default)", "certificates"))
    checks.append(CheckResult(category_id, category_name, f"{category_id}.node_ssh",
                              "6.5 Node SSH Accessed", "SKIPPED",
                              "Not verifiable from standard collection",
                              "ssh"))
    return checks


def _evaluate_day2_mcp_checks(results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    machine_config_pool_data = results.get("05_components", {}).get("machineconfig", {})
    if _is_missing(machine_config_pool_data):
        return [CheckResult(category_id, category_name, f"{category_id}.mcp_max_unavailable",
                            "6.6.1 Machine Config Pool Max Unavailable", "SKIPPED",
                            "MCP data unavailable", "machineconfig")]
    max_unavailable = {
        str(_resource_spec(item).get("maxUnavailable"))
        for item in _get_items(machine_config_pool_data, default_single=True)
        if _resource_spec(item).get("maxUnavailable")
    }
    return [CheckResult(category_id, category_name, f"{category_id}.mcp_max_unavailable",
                        "6.6.1 Machine Config Pool Max Unavailable", "PASS",
                        f"maxUnavailable settings: {max_unavailable or 'default (1)'}",
                        "machineconfig")]


def _evaluate_tsr_day2_aggregate(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """TSR 6.x: Aggregate day-2 operations checks."""
    checks: list[CheckResult] = []
    checks += _evaluate_day2_quota_checks(category_data, category_id, category_name)
    checks += _evaluate_day2_capacity_checks(results, category_id, category_name)
    checks += _evaluate_day2_pruning(category_data, category_id, category_name)
    checks += _evaluate_day2_infra_nodes(results, category_id, category_name)
    checks += _evaluate_day2_image_and_alert_checks(category_data, category_id, category_name)
    checks += _evaluate_day2_cert_checks(category_data, results, category_id, category_name)
    checks += _evaluate_day2_mcp_checks(results, category_id, category_name)
    return checks


def evaluate_day2(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Dispatch evaluators for 7.6 Day-2 Operations."""
    checks: list[CheckResult] = []
    comp = results.get("05_components", {})
    # TSR 6.x aggregate checks
    checks += _evaluate_tsr_day2_aggregate(category_data, results, category_id, category_name)
    checks += _evaluate_node_image_gc(category_data.get("node_image_gc", {}), category_id, category_name)
    # Existing detailed checks
    checks += _evaluate_storage(
        comp.get("storageclass", {}),
        comp.get("pv", {}),
        comp.get("pvc", {}),
        category_id, category_name,
    )
    checks += _evaluate_proxy(category_data.get("proxy", {}), category_id, category_name)
    checks += _evaluate_resource_quotas(category_data.get("resourcequota", {}), category_id, category_name)
    checks += _evaluate_quota_coverage(
        category_data.get("namespaces", {}),
        category_data.get("resourcequota", {}),
        category_data.get("limitrange", {}),
        category_id, category_name,
    )
    checks += _evaluate_upgrade_history(category_data.get("clusterversion", {}), category_id, category_name)
    checks += _evaluate_upgrade_failed_hops(category_data.get("clusterversion", {}), category_id, category_name)
    checks += _evaluate_apiserver_config(category_data.get("apiserver", {}), category_id, category_name)
    checks += _evaluate_namespaces(category_data.get("namespaces", {}), category_id, category_name)
    checks += _evaluate_limit_ranges(category_data.get("limitrange", {}), category_id, category_name)
    checks += _evaluate_pod_requests(
        results.get("07_cluster_health", {}).get("pods_all", {}),
        category_id, category_name,
    )
    metrics_data = results.get("10_metrics") or {}
    checks += _evaluate_node_expected_limits(
        metrics_data.get("node_cpu_limits_pct") or {},
        metrics_data.get("node_memory_limits_pct") or {},
        category_id, category_name,
    )
    checks += _evaluate_netpol_orphan(
        category_data.get("networkpolicy", {}),
        results.get("07_cluster_health", {}).get("pods_all", {}),
        category_id, category_name,
    )
    checks += _evaluate_operator_approval(category_data.get("subscriptions", {}), category_id, category_name)
    checks += _evaluate_deploymentconfigs(category_data.get("deploymentconfig", {}), category_id, category_name)
    return checks
