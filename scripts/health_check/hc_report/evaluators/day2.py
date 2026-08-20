"""Evaluators for 7.6 Day-2 Operations."""
from __future__ import annotations

from collections import Counter

from hc_report.evaluators._common import (
    _cluster_version_object,
    _evaluate_approval_strategy,
    _get_items,
    _is_missing,
    _not_applicable,
    _resource_labels,
    _resource_metadata,
    _resource_name,
    _resource_spec,
    _resource_status,
)
from hc_report.evaluators._shared_checks import check_csr_pending
from hc_report.evaluators.components_infra import _evaluate_storage
from hc_report.models import CheckResult


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


def _evaluate_day2_image_and_alert_checks(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    checks = [
        CheckResult(category_id, category_name, f"{category_id}.update_impact",
                    "6.2.2 Update Impacting Workloads", "SKIPPED",
                    "Requires upgrade history correlation not in standard collection",
                    "clusterversion"),
        CheckResult(category_id, category_name, f"{category_id}.alert_receivers",
                    "6.3.2 Alert Receivers", "SKIPPED",
                    "Alertmanager receiver config not in standard collection",
                    "alertmanager"),
        CheckResult(category_id, category_name, f"{category_id}.remote_health",
                    "6.3.3 Retrieves Updates", "SKIPPED",
                    "Remote health verification requires live API access",
                    "insights"),
    ]
    image_config_data = category_data.get("image_config", {})
    if _is_missing(image_config_data):
        checks.append(CheckResult(category_id, category_name, f"{category_id}.image_mgmt",
                                  "6.2.3 Images Patch Management", "SKIPPED",
                                  "Image configuration data was not collected", "image_config"))
        return checks
    registries = image_config_data.get("spec", {}).get("registrySources", {})
    allowed = registries.get("allowedRegistries", [])
    blocked = registries.get("blockedRegistries", [])
    checks.append(CheckResult(category_id, category_name, f"{category_id}.image_mgmt",
                              "6.2.3 Images Patch Management", "INFO",
                              f"Image policy: {len(allowed)} allowed, {len(blocked)} blocked registries",
                              "image_config"))
    return checks


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
    # Existing detailed checks
    checks += _evaluate_storage(
        comp.get("storageclass", {}),
        comp.get("pv", {}),
        comp.get("pvc", {}),
        category_id, category_name,
    )
    checks += _evaluate_proxy(category_data.get("proxy", {}), category_id, category_name)
    checks += _evaluate_resource_quotas(category_data.get("resourcequota", {}), category_id, category_name)
    checks += _evaluate_upgrade_history(category_data.get("clusterversion", {}), category_id, category_name)
    checks += _evaluate_apiserver_config(category_data.get("apiserver", {}), category_id, category_name)
    checks += _evaluate_namespaces(category_data.get("namespaces", {}), category_id, category_name)
    checks += _evaluate_limit_ranges(category_data.get("limitrange", {}), category_id, category_name)
    checks += _evaluate_operator_approval(category_data.get("subscriptions", {}), category_id, category_name)
    checks += _evaluate_deploymentconfigs(category_data.get("deploymentconfig", {}), category_id, category_name)
    return checks
