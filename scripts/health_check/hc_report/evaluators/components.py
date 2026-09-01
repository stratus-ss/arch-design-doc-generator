"""Evaluators for 7.3 Component Checks."""
from __future__ import annotations

from hc_report.evaluators._common import (
    _find_condition,
    _get_items,
    _is_missing,
    _not_applicable,
    _resource_annotations,
    _resource_metadata,
    _resource_name,
    _resource_spec,
)
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


def _cluster_operator_platform(
    per_operator_checks: list[CheckResult], category_id: str, category_name: str,
) -> CheckResult:
    fail_count = sum(1 for check in per_operator_checks if check.status == "FAIL")
    warning_count = sum(1 for check in per_operator_checks if check.status == "WARNING")
    pass_count = sum(1 for check in per_operator_checks if check.status == "PASS")
    if fail_count:
        status = "FAIL"
    elif warning_count:
        status = "WARNING"
    else:
        status = "PASS"
    return CheckResult(
        category_id, category_name, f"{category_id}.co.platform",
        "Platform operators", status,
        f"FAIL={fail_count} WARNING={warning_count} PASS={pass_count}",
    )


def _missing_cluster_operators(category_id: str, category_name: str) -> list[CheckResult]:
    return [
        _not_applicable(
            f"{category_id}.co", "Cluster Operators",
            category_id, category_name,
        ),
        _not_applicable(
            f"{category_id}.co.platform", "Platform operators",
            category_id, category_name,
        ),
    ]


def _evaluate_cluster_operators(data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """One check per cluster operator — Available, Degraded, Progressing."""
    if _is_missing(data):
        return _missing_cluster_operators(category_id, category_name)

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
    if not checks:
        return _missing_cluster_operators(category_id, category_name)
    checks.append(_cluster_operator_platform(checks, category_id, category_name))
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


_REGISTRY_OBJECT_BACKENDS = frozenset({"s3", "azure", "gcs", "ibmcos", "oss", "swift"})
_FILE_PROVISIONER_TOKENS = ("nfs", "efs", "azurefile", "cephfs")
_DEFAULT_STORAGE_CLASS_ANNOTATION = "storageclass.kubernetes.io/is-default-class"


def _registry_storage_backend(storage: dict) -> str:
    """Return the first spec.storage key other than managementState."""
    if not isinstance(storage, dict):
        return "none"
    remaining_keys = [key for key in storage if key != "managementState"]
    if not remaining_keys:
        return "none"
    return remaining_keys[0]


def _evaluate_registry_storage(
    registry_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    """Score emptyDir vs persistent/object registry backend (not management state)."""
    check_id = f"{category_id}.registry.storage"
    title = "Internal registry storage"
    if _is_missing(registry_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "INFO",
            "Image registry payload missing", "imageregistry",
        )]
    spec = _resource_spec(registry_data)
    management_state = spec.get("managementState", "unknown")
    storage = spec.get("storage", {})
    backend = _registry_storage_backend(storage if isinstance(storage, dict) else {})
    if management_state == "Removed":
        return [CheckResult(
            category_id, category_name, check_id, title, "INFO",
            f"Registry managementState is Removed; storage backend {backend} not scored",
            "imageregistry",
        )]
    if backend == "emptyDir" and management_state in ("Managed", "Unmanaged"):
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            f"Registry storage backend is emptyDir with managementState {management_state}",
            "imageregistry", scoring_basis="doc_backed",
        )]
    if backend in _REGISTRY_OBJECT_BACKENDS or backend == "pvc":
        return [CheckResult(
            category_id, category_name, check_id, title, "PASS",
            f"Registry storage backend is {backend}", "imageregistry",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "WARNING",
        f"Registry storage backend is {backend}", "imageregistry",
    )]


def _storage_class_provisioner(storage_classes: dict, class_name: str) -> str:
    """Look up a StorageClass provisioner by name, or the default class if name is empty."""
    items = _get_items(storage_classes, default_single=True)
    if class_name:
        for storage_class in items:
            if _resource_metadata(storage_class).get("name") == class_name:
                return str(storage_class.get("provisioner") or "")
        return ""
    for storage_class in items:
        annotations = _resource_annotations(storage_class)
        if annotations.get(_DEFAULT_STORAGE_CLASS_ANNOTATION) == "true":
            return str(storage_class.get("provisioner") or "")
    return ""


def _monitoring_item_storage_status(item: dict, storageclass_data: dict) -> str:
    """Classify one Prometheus or Alertmanager CR: FAIL, WARNING, PASS, or SKIP."""
    if not isinstance(item, dict):
        return "SKIP"
    spec = _resource_spec(item)
    storage = spec.get("storage")
    if not isinstance(storage, dict):
        return "FAIL"
    template = storage.get("volumeClaimTemplate")
    if not isinstance(template, dict) or not template:
        return "FAIL"
    template_spec = template.get("spec")
    if not isinstance(template_spec, dict):
        template_spec = {}
    access_modes = template_spec.get("accessModes") or []
    if not isinstance(access_modes, list):
        access_modes = []
    class_name = template_spec.get("storageClassName")
    if class_name is None:
        class_name = ""
    provisioner = _storage_class_provisioner(storageclass_data, str(class_name))
    if "ReadWriteMany" in access_modes:
        return "WARNING"
    lowered_provisioner = provisioner.lower()
    if any(token in lowered_provisioner for token in _FILE_PROVISIONER_TOKENS):
        return "WARNING"
    return "PASS"


def _evaluate_monitoring_storage(
    prometheus_data: dict,
    alertmanager_data: dict,
    storageclass_data: dict,
    category_id: str,
    category_name: str,
) -> list[CheckResult]:
    """Score Prometheus/Alertmanager PVC template, RWO, and file provisioner."""
    check_id = f"{category_id}.monitoring.storage"
    title = "Monitoring storage type"
    prometheus_missing = _is_missing(prometheus_data)
    alertmanager_missing = _is_missing(alertmanager_data)
    if prometheus_missing and alertmanager_missing:
        return [CheckResult(
            category_id, category_name, check_id, title, "INFO",
            "Prometheus and Alertmanager payloads missing", "monitoring_storage",
        )]
    items: list = []
    if not prometheus_missing:
        items.extend(_get_items(prometheus_data, default_single=True))
    if not alertmanager_missing:
        items.extend(_get_items(alertmanager_data, default_single=True))
    statuses = [
        _monitoring_item_storage_status(item, storageclass_data) for item in items
    ]
    if "FAIL" in statuses:
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            "Prometheus or Alertmanager lacks volumeClaimTemplate",
            "monitoring_storage", scoring_basis="doc_backed",
        )]
    if "WARNING" in statuses:
        return [CheckResult(
            category_id, category_name, check_id, title, "WARNING",
            "Monitoring storage uses ReadWriteMany or a file provisioner",
            "monitoring_storage",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        "Prometheus and Alertmanager use RWO non-file persistent storage",
        "monitoring_storage",
    )]


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


def _evaluate_olm_failed_csv(
    csv_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.olm.failed_csv"
    title = "OLM failed ClusterServiceVersions"
    if csv_data.get("_hc_error"):
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "csv payload collection error", "csv",
        )]
    if not csv_data or csv_data.get("_hc_not_found"):
        return [_not_applicable(
            check_id, title, category_id, category_name,
            evidence="csv payload missing",
        )]
    items = _get_items(csv_data)
    if not items:
        return [_not_applicable(
            check_id, title, category_id, category_name,
            evidence="No ClusterServiceVersion items",
        )]
    failed_names = []
    warning_entries = []
    for item in items:
        name = _resource_name(item, default="unknown")
        phase = item.get("status", {}).get("phase") or ""
        if not isinstance(phase, str):
            phase = ""
        if phase == "Failed":
            failed_names.append(name)
        elif phase and phase != "Succeeded":
            warning_entries.append(f"{name}={phase}")
    if failed_names:
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            f"Failed CSV(s): {', '.join(failed_names[:8])}", "csv",
        )]
    if warning_entries:
        return [CheckResult(
            category_id, category_name, check_id, title, "WARNING",
            f"Non-Succeeded CSV phase(s): {', '.join(warning_entries[:8])}", "csv",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"{len(items)} ClusterServiceVersion(s) Succeeded or empty phase", "csv",
    )]


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
    csv_data = results.get("03_base_platform", {}).get("csv", {})
    checks += _evaluate_olm_failed_csv(csv_data, category_id, category_name)
    checks += _evaluate_network(category_data.get("network", {}), category_id, category_name)
    checks += _evaluate_ingress(category_data.get("ingresscontroller", {}), category_id, category_name)
    checks += _evaluate_image_registry(category_data.get("imageregistry", {}), category_id, category_name)
    checks += _evaluate_registry_storage(category_data.get("imageregistry", {}), category_id, category_name)
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
    checks += _evaluate_monitoring_storage(
        category_data.get("prometheus", {}),
        category_data.get("alertmanager", {}),
        category_data.get("storageclass", {}),
        category_id, category_name,
    )
    return checks
