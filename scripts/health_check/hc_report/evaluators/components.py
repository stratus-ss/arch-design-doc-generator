"""Evaluators for 7.3 Component Checks."""
from __future__ import annotations

from hc_report.evaluators._common import _find_condition, _get_items, _is_missing, _not_applicable
from hc_report.evaluators._shared_checks import find_degraded_operators
from hc_report.evaluators.components_infra import (
    _evaluate_cluster_version,
    _evaluate_crds,
    _evaluate_deprecated_apis,
    _evaluate_etcd_aggregate,
    _evaluate_ingress_aggregate,
    _evaluate_storage,
    _evaluate_storage_aggregate,
    _evaluate_localvolume,
)
from hc_report.evaluators.components_misc import _evaluate_misc_components
from hc_report.evaluators.components_network import _evaluate_networking_features
from hc_report.models import CheckResult


def _evaluate_cluster_operators(data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """One check per cluster operator — Available, Degraded, Progressing."""
    if _is_missing(data):
        return [_not_applicable(f"{category_id}.co", "Cluster Operators", category_id, category_name)]

    items = _get_items(data, default_single=True)
    degraded_ops = set(find_degraded_operators(data))
    checks = []
    for item in items:
        name = item.get("metadata", {}).get("name", "unknown")
        conditions = item.get("status", {}).get("conditions", [])
        available = _find_condition(conditions, "Available")
        degraded = _find_condition(conditions, "Degraded")
        progressing = _find_condition(conditions, "Progressing")

        if name in degraded_ops:
            status, evidence = "FAIL", f"Degraded: {degraded.get('message', '')[:200]}"
        elif available.get("status") != "True":
            status, evidence = "WARNING", f"Not Available: {available.get('message', '')[:200]}"
        elif progressing.get("status") == "True":
            status, evidence = "WARNING", f"Progressing: {progressing.get('message', '')[:200]}"
        else:
            version = item.get("status", {}).get("versions", [{}])
            version_text = version[0].get("version", "") if version else ""
            evidence = f"Available, not degraded{('. Version: ' + version_text) if version_text else ''}"
            status = "PASS"

        checks.append(CheckResult(category_id, category_name, f"{category_id}.co.{name}",
                                  f"Cluster Operator: {name}", status, evidence, name))
    return checks


def _evaluate_network(network_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Network plugin, CIDR ranges, MTU."""
    if _is_missing(network_data):
        return [_not_applicable(f"{category_id}.network", "Network Configuration", category_id, category_name)]

    checks = []
    spec = network_data.get("spec", {})
    status = network_data.get("status", {})
    network_type = spec.get("networkType") or status.get("networkType", "unknown")
    cluster_nets = spec.get("clusterNetwork") or status.get("clusterNetwork", [])
    service_nets = spec.get("serviceNetwork") or status.get("serviceNetwork", [])

    if network_type == "OVNKubernetes":
        network_status, network_evidence = "PASS", "Plugin: OVNKubernetes (recommended for OCP 4.12+)"
    elif network_type == "OpenShiftSDN":
        network_status = "WARNING"
        network_evidence = "Plugin: OpenShiftSDN — deprecated in OCP 4.14+. Migration to OVNKubernetes recommended"
    else:
        network_status, network_evidence = "PASS", f"Plugin: {network_type}"
    checks.append(CheckResult(category_id, category_name, f"{category_id}.network.plugin",
                              "7.3.5 Network Plugin", network_status, network_evidence, "network"))

    if cluster_nets:
        cidrs = ", ".join(
            network_entry.get("cidr", str(network_entry)) if isinstance(network_entry, dict) else str(network_entry)
            for network_entry in cluster_nets
        )
        checks.append(CheckResult(category_id, category_name, f"{category_id}.network.cluster_cidr",
                                  "7.3.6 Cluster Network CIDR", "INFO",
                                  f"Cluster CIDR(s): {cidrs}", "network"))

    if service_nets:
        svc_cidrs = ", ".join(str(network_entry) for network_entry in service_nets)
        checks.append(CheckResult(category_id, category_name, f"{category_id}.network.service_cidr",
                                  "7.3.7 Service Network CIDR", "INFO",
                                  f"Service CIDR(s): {svc_cidrs}", "network"))
    return checks


def _evaluate_ingress(ingress_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Ingress controller health."""
    if _is_missing(ingress_data):
        return [_not_applicable(f"{category_id}.ingress", "Ingress Controller", category_id, category_name)]

    items = _get_items(ingress_data, default_single=True)
    checks = []
    for ingress_controller in items:
        name = ingress_controller.get("metadata", {}).get("name", "unknown")
        ingress_controller_status = ingress_controller.get("status", {})
        conditions = ingress_controller_status.get("conditions", [])
        available = _find_condition(conditions, "Available")
        replicas = ingress_controller_status.get("availableReplicas", 0)
        desired = ingress_controller.get("spec", {}).get("replicas", ingress_controller_status.get("replicas", 1))
        domain = ingress_controller.get("spec", {}).get("domain", "")

        if available.get("status") != "True":
            status = "FAIL"
            evidence = f"Ingress '{name}' not Available: {available.get('message', '')[:150]}"
        elif replicas < desired:
            status = "WARNING"
            evidence = f"Ingress '{name}': {replicas}/{desired} replicas available. Domain: {domain}"
        else:
            status = "PASS"
            evidence = f"Ingress '{name}': {replicas} replica(s) available. Domain: {domain}"
        checks.append(CheckResult(category_id, category_name, f"{category_id}.ingress.{name}",
                                  f"Ingress Controller: {name}", status, evidence, name))
    return checks


def _evaluate_image_registry(registry_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Image registry management state and storage."""
    if _is_missing(registry_data):
        return [_not_applicable(f"{category_id}.registry", "Image Registry", category_id, category_name)]

    spec = registry_data.get("spec", {})
    reg_status = registry_data.get("status", {})
    mgmt_state = spec.get("managementState", "unknown")
    storage = spec.get("storage", {})
    conditions = reg_status.get("conditions", [])
    available = _find_condition(conditions, "Available")

    if mgmt_state == "Removed":
        return [CheckResult(category_id, category_name, f"{category_id}.registry.state",
                            "7.3.8 Image Registry Management State", "WARNING",
                            "Image registry is set to 'Removed'. "
                            "Internal image registry is not available", "imageregistry")]
    if available.get("status") == "True":
        storage_type = list(storage.keys())[0] if storage else "none"
        return [CheckResult(category_id, category_name, f"{category_id}.registry.state",
                            "7.3.8 Image Registry Management State", "PASS",
                            f"Registry Managed and Available. Storage type: {storage_type}. "
                            f"State: {mgmt_state}", "imageregistry")]
    return [CheckResult(category_id, category_name, f"{category_id}.registry.state",
                        "7.3.8 Image Registry Management State", "WARNING",
                        f"Registry state: {mgmt_state}. "
                        f"Available: {available.get('status', 'unknown')}", "imageregistry")]


def _evaluate_dns(dns_op: dict, dns_config: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """DNS operator and cluster DNS config."""
    checks = []
    if _is_missing(dns_op):
        checks.append(_not_applicable(f"{category_id}.dns.operator", "DNS Operator", category_id, category_name))
    else:
        conditions = dns_op.get("status", {}).get("conditions", [])
        available = _find_condition(conditions, "Available")
        degraded = _find_condition(conditions, "Degraded")
        if degraded.get("status") == "True":
            checks.append(CheckResult(category_id, category_name, f"{category_id}.dns.operator",
                                      "7.3.17 DNS Operator", "FAIL",
                                      degraded.get("message", "DNS Operator degraded")[:200], "dns"))
        elif available.get("status") == "True":
            checks.append(CheckResult(category_id, category_name, f"{category_id}.dns.operator",
                                      "7.3.17 DNS Operator", "PASS",
                                      "DNS Operator Available", "dns"))
        else:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.dns.operator",
                                      "7.3.17 DNS Operator", "WARNING",
                                      f"DNS Operator not Available: "
                                      f"{available.get('message', 'unknown')[:150]}", "dns"))

    if not _is_missing(dns_config):
        spec = dns_config.get("spec", {})
        base_domain = dns_config.get("status", {}).get("clusterDomain", spec.get("baseDomain", ""))
        if base_domain:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.dns.config",
                                      "7.3.17 DNS Cluster Domain", "INFO",
                                      f"Cluster domain: {base_domain}", "dns"))
    return checks


_WEBHOOK_FAILPOLICY_DOC_REF = (
    "https://kubernetes.io/docs/reference/access-authn-authz/"
    "extensible-admission-controllers/#failure-policy"
)

# Prefixes considered "critical" OCP/system namespaces per TSR 3.13's
# Performance/Security/System API classification. A webhook that explicitly
# scopes itself to one of these AND uses a non-Ignore failurePolicy can block
# critical cluster operations if the webhook backend is unavailable.
_CRITICAL_NAMESPACE_PREFIXES = ("openshift-", "kube-system", "kube-public", "default")


def _webhook_targets_critical_namespace(webhook: dict) -> bool:
    """True only when the webhook's namespaceSelector explicitly names a
    critical/system namespace. An absent or empty selector means the webhook
    applies cluster-wide (the common case for most Red Hat-shipped operator
    webhooks) and is deliberately NOT treated as critical here, to avoid
    flagging the large volume of legitimate Fail-policy webhooks that ship
    with OLM/agent-install/virtualization operators.
    """
    selector = webhook.get("namespaceSelector") or {}
    match_labels = selector.get("matchLabels") or {}
    match_exprs = selector.get("matchExpressions") or []
    values = list(match_labels.values())
    for expression in match_exprs:
        values.extend(expression.get("values", []))
    return any(str(value).startswith(_CRITICAL_NAMESPACE_PREFIXES) for value in values)


def _is_critical_webhook(webhook: dict) -> bool:
    """Narrow TSR 3.13-aligned FAIL condition: non-Ignore failurePolicy on a
    webhook explicitly scoped to a critical OCP/system namespace."""
    return webhook.get("failurePolicy", "Ignore") == "Fail" and _webhook_targets_critical_namespace(webhook)


def _scan_risky_webhooks(items: list[dict]) -> tuple[list[str], list[str]]:
    """Return (risky_descriptions, critical_descriptions) across a webhook config list."""
    risky: list[str] = []
    critical: list[str] = []
    for item in items:
        webhook_name = item.get("metadata", {}).get("name", "unknown")
        for webhook in item.get("webhooks", []):
            timeout = webhook.get("timeoutSeconds", 10)
            failure = webhook.get("failurePolicy", "Ignore")
            if timeout > 10 or failure == "Fail":
                risky.append(f"{webhook_name}(timeout={timeout}s, failurePolicy={failure})")
            if _is_critical_webhook(webhook):
                critical.append(f"{webhook_name}(failurePolicy={failure})")
    return risky, critical


def _evaluate_webhooks(validating: dict, mutating: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Admission webhook inventory: count, timeout, failurePolicy.

    Two-tier severity: WARNING for general risky config (long timeout or Fail
    policy), FAIL for the narrow TSR 3.13-aligned condition of a Fail-policy
    webhook explicitly scoped to a critical OCP/system namespace.
    """
    checks = []
    for label, data, key in [
        ("Validating", validating, "validatingwebhooks"),
        ("Mutating", mutating, "mutatingwebhooks"),
    ]:
        if _is_missing(data):
            checks.append(_not_applicable(f"{category_id}.webhooks.{key}", f"{label} Webhooks", category_id, category_name))
            continue
        items = _get_items(data)
        risky, critical = _scan_risky_webhooks(items)
        if critical:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.webhooks.{key}",
                                      f"7.3.13 {label} Webhooks", "FAIL",
                                      f"{len(items)} {label.lower()} webhooks. "
                                      f"Fail-policy webhook(s) scoped to critical namespaces: "
                                      f"{'; '.join(critical[:3])}",
                                      key, doc_ref=_WEBHOOK_FAILPOLICY_DOC_REF))
        elif risky:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.webhooks.{key}",
                                      f"7.3.13 {label} Webhooks", "WARNING",
                                      f"{len(items)} {label.lower()} webhooks. "
                                      f"Risky config: {'; '.join(risky[:3])}",
                                      key))
        else:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.webhooks.{key}",
                                      f"7.3.13 {label} Webhooks", "PASS",
                                      f"{len(items)} {label.lower()} webhook(s). "
                                      "All within safe timeout and failurePolicy thresholds",
                                      key))
    return checks


_MONITORING_STORAGE_DOC_REF = (
    "https://docs.openshift.com/container-platform/4.18/monitoring/"
    "configuring-the-monitoring-stack.html"
    "#configuring-persistent-storage_configuring-the-monitoring-stack"
)


def _evaluate_monitoring_config(cm_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Check cluster-monitoring-config ConfigMap for persistent storage.

    Ephemeral (emptyDir) Prometheus storage is a FAIL, not a WARNING: Red Hat
    documentation states persistent storage is required for production
    monitoring, aligning with the TSR's 3.7.2 hard-fail on this condition.
    """
    if _is_missing(cm_data):
        return [CheckResult(category_id, category_name, f"{category_id}.monitoring.config",
                            "7.3.7 Monitoring Configuration", "FAIL",
                            "cluster-monitoring-config ConfigMap not found. "
                            "Prometheus uses emptyDir (data lost on pod restart). "
                            "Configure PVC-backed storage for production",
                            "monitoring_config", doc_ref=_MONITORING_STORAGE_DOC_REF)]
    data_field = cm_data.get("data", {})
    config_yaml_str = data_field.get("config.yaml", "")
    has_pvc = "volumeClaimTemplate" in config_yaml_str or "storage" in config_yaml_str
    if has_pvc:
        return [CheckResult(category_id, category_name, f"{category_id}.monitoring.config",
                            "7.3.7 Monitoring Configuration", "PASS",
                            "cluster-monitoring-config present with persistent storage configured",
                            "monitoring_config")]
    return [CheckResult(category_id, category_name, f"{category_id}.monitoring.config",
                        "7.3.7 Monitoring Configuration", "FAIL",
                        "cluster-monitoring-config found but no volumeClaimTemplate detected. "
                        "Prometheus data is ephemeral — configure PVC storage for production",
                        "monitoring_config", doc_ref=_MONITORING_STORAGE_DOC_REF)]


def evaluate_components(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Dispatch evaluators for 7.3 Component Checks."""
    checks: list[CheckResult] = []
    # TSR 3.x aggregate checks
    checks += _evaluate_cluster_version(category_data, results, category_id, category_name)
    checks += _evaluate_etcd_aggregate(category_data, results, category_id, category_name)
    checks += _evaluate_ingress_aggregate(category_data, category_id, category_name)
    checks += _evaluate_storage_aggregate(category_data, category_id, category_name)
    checks += _evaluate_localvolume(category_data, category_id, category_name)
    checks += _evaluate_networking_features(category_data, category_id, category_name)
    checks += _evaluate_misc_components(category_data, results, category_id, category_name)
    # Existing detailed checks
    checks += _evaluate_cluster_operators(
        category_data.get("cluster_operators", category_data.get("clusteroperators", {})),
        category_id, category_name,
    )
    checks += _evaluate_network(category_data.get("network", {}), category_id, category_name)
    checks += _evaluate_ingress(category_data.get("ingresscontroller", {}), category_id, category_name)
    checks += _evaluate_image_registry(category_data.get("imageregistry", {}), category_id, category_name)
    checks += _evaluate_storage(
        category_data.get("storageclass", {}),
        category_data.get("pv", {}),
        category_data.get("pvc", {}),
        category_id, category_name,
    )
    checks += _evaluate_dns(
        category_data.get("dns_operator", {}),
        category_data.get("dns_config", {}),
        category_id, category_name,
    )
    checks += _evaluate_crds(category_data.get("crds", {}), category_id, category_name)
    checks += _evaluate_deprecated_apis(category_data.get("apirequestcounts", {}), category_id, category_name)
    checks += _evaluate_webhooks(
        category_data.get("validatingwebhooks", {}),
        category_data.get("mutatingwebhooks", {}),
        category_id, category_name,
    )
    checks += _evaluate_monitoring_config(category_data.get("monitoring_config", {}), category_id, category_name)
    return checks
