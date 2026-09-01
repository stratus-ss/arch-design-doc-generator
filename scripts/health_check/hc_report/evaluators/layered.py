"""Evaluators for 7.4 Layered Products."""
from __future__ import annotations

from hc_report.evaluators._common import (
    _find_condition,
    _get_items,
    _is_missing,
    _resource_annotations,
    _resource_metadata,
    _resource_name,
    _resource_spec,
    _resource_status,
)
from hc_report.evaluators.layered_cnv import evaluate_cnv_p3
from hc_report.models import CheckResult

_VIRT_DEFAULT_STORAGECLASS_ANNOTATION = "storageclass.kubevirt.io/is-default-virt-class"
_OADP_OPERATOR_NAMESPACE = "openshift-adp"

_LAYERED_PRODUCTS: list[tuple[str, str]] = [
    ("OpenShift Virtualization (CNV)", "cnv_hyperconverged"),
    ("ACM MultiClusterHub", "acm_multiclusterhub"),
    ("ACS Central", "acs_central"),
    ("Cluster Logging", "logging_clusterlogging"),
    ("OpenShift Pipelines", "pipelines_tektonconfig"),
    ("Service Mesh", "servicemesh_smcp"),
    ("Migration Toolkit (MTV)", "mtv_controller"),
    ("OADP", "oadp_dpa"),
    ("OpenShift Serverless (Knative Serving)", "serverless_knserving"),
    ("OpenShift Serverless (Knative Eventing)", "serverless_kneventing"),
    ("Quay Registry", "quay_registry"),
    ("OCP AI / Data Science", "datasciencecluster"),
]


def _evaluate_layered_product(name: str, category_id: str, category_name: str, data: dict) -> CheckResult:
    """Return check result for a single layered product."""
    if data.get("_hc_not_found"):
        return CheckResult(category_id, category_name, f"{category_id}.{name}", name, "NOT_APPLICABLE",
                           "Not installed on this cluster")
    if data.get("_hc_error"):
        return CheckResult(category_id, category_name, f"{category_id}.{name}", name, "SKIPPED",
                           "Collection failed — manual check required")
    items = _get_items(data, default_single=True)
    status, evidence = _product_condition_status(items, degraded_status="WARNING")
    if status == "INFO":
        evidence = f"Installed. {len(items)} instance(s) found"
    return CheckResult(category_id, category_name, f"{category_id}.{name}", name, status, evidence)


def _product_condition_status(items: list, *, degraded_status: str) -> tuple[str, str]:
    saw_degraded = False
    saw_available = False
    for item in items:
        status = item.get("status", {}) if isinstance(item.get("status"), dict) else {}
        conditions = status.get("conditions", [])
        if not isinstance(conditions, list):
            conditions = []
        if _find_condition(conditions, "Degraded").get("status") == "True":
            saw_degraded = True
        available = _find_condition(conditions, "Available")
        ready = _find_condition(conditions, "Ready")
        if available.get("status") == "True" or ready.get("status") == "True":
            saw_available = True
        phase = str(status.get("phase", "")).lower()
        if phase in {"failed", "error"}:
            saw_degraded = True
    if saw_degraded:
        return degraded_status, "Degraded or error conditions present"
    if saw_available:
        return "PASS", "Available/Ready is True"
    return "INFO", f"{len(items)} instance(s) found"


def _evaluate_cnv_aggregate(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """TSR 4.8.x: CNV/OCP-V checks from HyperConverged and KubeVirt."""
    checks: list[CheckResult] = []
    hco = category_data.get("cnv_hyperconverged", {})
    kubevirt = category_data.get("cnv_kubevirt", {})

    if hco.get("_hc_not_found") or _is_missing(hco):
        checks.append(CheckResult(category_id, category_name, f"{category_id}.cnv.state",
                                  "4.8.1.1.1 CNV Identification and State", "NOT_APPLICABLE",
                                  "OpenShift Virtualization not installed", "cnv"))
        return checks

    # 4.8.1.1.1 Identification and State
    hco_items = _get_items(hco, default_single=True)
    hco_obj = hco_items[0] if hco_items else hco
    conditions = hco_obj.get("status", {}).get("conditions", [])
    available = _find_condition(conditions, "Available")
    degraded = _find_condition(conditions, "Degraded")
    if degraded.get("status") == "True":
        checks.append(CheckResult(category_id, category_name, f"{category_id}.cnv.state",
                                  "4.8.1.1.1 CNV Identification and State", "FAIL",
                                  f"HyperConverged degraded: {degraded.get('message', '')[:150]}",
                                  "cnv"))
    elif available.get("status") == "True":
        checks.append(CheckResult(category_id, category_name, f"{category_id}.cnv.state",
                                  "4.8.1.1.1 CNV Identification and State", "PASS",
                                  "HyperConverged Available and not Degraded", "cnv"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.cnv.state",
                                  "4.8.1.1.1 CNV Identification and State", "WARNING",
                                  f"HyperConverged: Available={available.get('status', '?')}", "cnv"))

    # 4.8.1.2.1 Platform Hypervisor — KubeVirt status
    if not _is_missing(kubevirt):
        kv_items = _get_items(kubevirt, default_single=True)
        kv_obj = kv_items[0] if kv_items else kubevirt
        phase = kv_obj.get("status", {}).get("phase", "unknown")
        checks.append(CheckResult(category_id, category_name, f"{category_id}.cnv.kubevirt",
                                  "4.8.1.2.1 Platform Hypervisor", "PASS" if phase == "Deployed" else "WARNING",
                                  f"KubeVirt phase: {phase}", "cnv"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.cnv.kubevirt",
                                  "4.8.1.2.1 Platform Hypervisor", "SKIPPED",
                                  "KubeVirt data not collected", "cnv"))

    # 4.8 pod health
    pods_data = category_data.get("cnv_pods", {})
    if not _is_missing(pods_data):
        pod_items = _get_items(pods_data)
        not_running = [
            _resource_name(pod)
            for pod in pod_items
            if _resource_status(pod).get("phase") not in ("Running", "Succeeded")
        ]
        if not_running:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.cnv.pods",
                                      "4.8 CNV Pod Status", "WARNING",
                                      f"{len(not_running)} CNV pod(s) not Running: "
                                      f"{', '.join(not_running[:3])}", "cnv"))
        else:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.cnv.pods",
                                      "4.8 CNV Pod Status", "PASS",
                                      f"All {len(pod_items)} CNV pods Running/Succeeded", "cnv"))
    checks += _evaluate_cnv_live_migratable(category_data, category_id, category_name)
    return checks


def _live_migratable_vmi_lines(vmi_data: dict) -> list[str]:
    lines: list[str] = []
    for item in _get_items(vmi_data):
        metadata = _resource_metadata(item)
        namespace = metadata.get("namespace", "unknown")
        name = metadata.get("name", "unknown")
        conditions = item.get("status", {}).get("conditions", [])
        condition = _find_condition(conditions, "LiveMigratable")
        if condition.get("status") != "False":
            continue
        reason = condition.get("reason") or "unknown"
        message = condition.get("message") or "unknown"
        lines.append(f"{namespace}/{name}: {reason}: {message}")
    return lines


def _eviction_strategy_lines(vm_data: dict) -> list[str]:
    lines: list[str] = []
    for item in _get_items(vm_data):
        metadata = _resource_metadata(item)
        namespace = metadata.get("namespace", "unknown")
        name = metadata.get("name", "unknown")
        template = item.get("spec", {}).get("template", {})
        strategy = template.get("spec", {}).get("evictionStrategy")
        if strategy is not None and strategy != "LiveMigrateIfPossible":
            continue
        value = "None" if strategy is None else strategy
        lines.append(f"evictionStrategy {namespace}/{name}: {value}")
    return lines


def _evaluate_cnv_live_migratable(
    category_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.cnv.live_migratable"
    description = "VM live-migratable status (engine)"
    vmi_data = category_data.get("cnv_vmi", {})
    if vmi_data.get("_hc_not_found") or _is_missing(vmi_data):
        return [CheckResult(
            category_id, category_name, check_id, description, "SKIPPED",
            "VMI data not collected", "cnv",
        )]
    not_migratable = _live_migratable_vmi_lines(vmi_data)
    eviction_lines = _eviction_strategy_lines(category_data.get("cnv_vm", {}))
    if not_migratable:
        evidence_lines = [f"{len(not_migratable)} VMI(s) not LiveMigratable"]
        evidence_lines.extend(not_migratable)
        evidence_lines.extend(eviction_lines)
        return [CheckResult(
            category_id, category_name, check_id, description, "WARNING",
            "\n".join(evidence_lines), "cnv",
        )]
    if eviction_lines:
        return [CheckResult(
            category_id, category_name, check_id, description, "INFO",
            "\n".join(eviction_lines), "cnv",
        )]
    return [CheckResult(
        category_id, category_name, check_id, description, "PASS",
        "All collected VMIs report LiveMigratable=True", "cnv",
    )]


def _evaluate_acm_aggregate(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """TSR 4.7.x: RHACM checks."""
    checks: list[CheckResult] = []
    acm = category_data.get("acm_multiclusterhub", {})
    if acm.get("_hc_not_found") or _is_missing(acm):
        # Check if this is a managed cluster with ACM agent
        pods = category_data.get("acm_pods", {})
        if not _is_missing(pods):
            pod_items = _get_items(pods)
            agent_pods = [
                pod for pod in pod_items
                if "klusterlet" in _resource_name(pod, default="").lower()
            ]
            if agent_pods:
                checks.append(CheckResult(category_id, category_name, f"{category_id}.acm.agent",
                                          "4.7.1.2 RHACM Agent", "PASS",
                                          f"ACM agent (klusterlet): {len(agent_pods)} pod(s) running",
                                          "acm"))
                return checks
        checks.append(CheckResult(category_id, category_name, f"{category_id}.acm.state",
                                  "4.7 RHACM", "NOT_APPLICABLE",
                                  "RHACM Hub not installed on this cluster", "acm"))
        return checks

    # Hub is installed
    acm_items = _get_items(acm, default_single=True)
    acm_obj = acm_items[0] if acm_items else acm
    phase = acm_obj.get("status", {}).get("phase", "unknown")
    checks.append(CheckResult(category_id, category_name, f"{category_id}.acm.state",
                              "4.7.1.1 RHACM Supported Config",
                              "PASS" if phase in ("Running", "Available") else "WARNING",
                              f"MultiClusterHub phase: {phase}", "acm"))
    return checks


def _evaluate_logging_aggregate(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """TSR 4.1.x: Cluster Logging checks."""
    checks: list[CheckResult] = []
    logging = category_data.get("logging_clusterlogging", {})
    if logging.get("_hc_not_found") or _is_missing(logging):
        checks.append(CheckResult(category_id, category_name, f"{category_id}.logging.state",
                                  "4.1.1 Logging Supported Configuration", "NOT_APPLICABLE",
                                  "Cluster Logging not installed", "logging"))
        return checks

    log_items = _get_items(logging, default_single=True)
    log_obj = log_items[0] if log_items else logging
    conditions = log_obj.get("status", {}).get("conditions", [])
    ready = _find_condition(conditions, "Ready")
    if ready.get("status") == "True":
        checks.append(CheckResult(category_id, category_name, f"{category_id}.logging.state",
                                  "4.1.1 Logging Supported Configuration", "PASS",
                                  "ClusterLogging Ready", "logging"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.logging.state",
                                  "4.1.1 Logging Supported Configuration", "WARNING",
                                  f"ClusterLogging not Ready: {ready.get('message', 'unknown')[:100]}",
                                  "logging"))

    # 4.1.6 Log Forwarders
    loki = category_data.get("logging_loki", {})
    if not loki.get("_hc_not_found"):
        checks.append(CheckResult(category_id, category_name, f"{category_id}.logging.loki",
                                  "4.1.5.2 Loki Health", "INFO",
                                  "LokiStack resource present", "logging"))
    return checks


def _nmstate_item_is_healthy(item: dict) -> bool:
    conditions = _resource_status(item).get("conditions", [])
    if not isinstance(conditions, list):
        conditions = []
    available = _find_condition(conditions, "Available")
    configured = _find_condition(conditions, "SuccessfullyConfigured")
    return available.get("status") == "True" or configured.get("status") == "True"


def _evaluate_cnv_nncp(
    nncp_data: dict, nnce_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.cnv.nncp"
    title = "Node network configuration (NMState)"
    if _is_missing(nncp_data) and _is_missing(nnce_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "NOT_APPLICABLE",
            "NNCP and NNCE payloads missing", "nncp",
        )]
    nncp_items = [] if _is_missing(nncp_data) else _get_items(nncp_data)
    nnce_items = [] if _is_missing(nnce_data) else _get_items(nnce_data)
    if not nncp_items and not nnce_items:
        return [CheckResult(
            category_id, category_name, check_id, title, "INFO",
            "No NNCP or NNCE items; overlay-only networking is expected", "nncp",
        )]
    unhealthy_items = [
        item for item in nncp_items + nnce_items
        if not _nmstate_item_is_healthy(item)
    ]
    if unhealthy_items:
        names = ", ".join(_resource_name(item) for item in unhealthy_items[:5])
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            f"{len(unhealthy_items)} NNCP/NNCE item(s) not Available or SuccessfullyConfigured: {names}",
            "nncp", scoring_basis="doc_backed",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"{len(nncp_items)} NNCP and {len(nnce_items)} NNCE item(s) healthy",
        "nncp",
    )]


def _evaluate_cnv_virt_storageclass(
    hyperconverged_data: dict,
    storage_class_data: dict,
    snapshot_class_data: dict,
    category_id: str,
    category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.cnv.virt_storageclass"
    title = "Default virtualization StorageClass"
    if hyperconverged_data.get("_hc_not_found") or _is_missing(hyperconverged_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "NOT_APPLICABLE",
            "OpenShift Virtualization not installed", "cnv",
        )]
    if _is_missing(storage_class_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "StorageClass payload missing", "cnv",
        )]
    virt_defaults = [
        item for item in _get_items(storage_class_data)
        if _resource_annotations(item).get(_VIRT_DEFAULT_STORAGECLASS_ANNOTATION) == "true"
    ]
    snapshot_names = [
        _resource_name(item) for item in (
            [] if _is_missing(snapshot_class_data) else _get_items(snapshot_class_data)
        )
    ]
    snapshot_evidence = (
        f" VolumeSnapshotClass: {', '.join(snapshot_names[:5])}."
        if snapshot_names else " No VolumeSnapshotClass items."
    )
    if len(virt_defaults) == 1:
        return [CheckResult(
            category_id, category_name, check_id, title, "PASS",
            f"Exactly one virt-default StorageClass ({_resource_name(virt_defaults[0])}).{snapshot_evidence}",
            "cnv",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "FAIL",
        f"Virt-default StorageClass count is {len(virt_defaults)}, expected 1.{snapshot_evidence}",
        "cnv", scoring_basis="doc_backed",
    )]


def _evaluate_oadp_state(
    dpa_data: dict,
    csv_data: dict,
    backup_location_data: dict,
    category_id: str,
    category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.oadp.state"
    title = "OADP operator"
    csv_items = [
        item for item in ([] if _is_missing(csv_data) else _get_items(csv_data))
        if _resource_metadata(item).get("namespace", _OADP_OPERATOR_NAMESPACE)
        == _OADP_OPERATOR_NAMESPACE
    ]
    dpa_items = [] if _is_missing(dpa_data) else _get_items(dpa_data)
    backup_items = [] if _is_missing(backup_location_data) else _get_items(backup_location_data)
    if not csv_items and not dpa_items and not backup_items:
        return [CheckResult(
            category_id, category_name, check_id, title, "NOT_APPLICABLE",
            "No OADP CSV, DataProtectionApplication, or BackupStorageLocation items",
            "oadp",
        )]
    failed_csv = [
        item for item in csv_items
        if str(_resource_status(item).get("phase", "")) != "Succeeded"
    ]
    failed_dpa = []
    for item in dpa_items:
        conditions = _resource_status(item).get("conditions", [])
        if not isinstance(conditions, list):
            conditions = []
        if _find_condition(conditions, "Available").get("status") != "True":
            failed_dpa.append(item)
    failed_backup = [
        item for item in backup_items
        if str(_resource_status(item).get("phase", "")) != "Available"
    ]
    if failed_csv or failed_dpa or failed_backup:
        evidence = (
            f"CSV not Succeeded: {len(failed_csv)}; "
            f"DPA not Available: {len(failed_dpa)}; "
            f"BackupStorageLocation not Available: {len(failed_backup)}"
        )
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL", evidence, "oadp",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"{len(csv_items)} CSV, {len(dpa_items)} DPA, {len(backup_items)} BackupStorageLocation healthy",
        "oadp",
    )]


def _quay_registry_namespaces(registry_data: dict) -> list[str]:
    """Unique CR namespaces plus spec.targetNamespace when set."""
    if registry_data.get("_hc_not_found"):
        return []
    ordered: list[str] = []
    seen: set[str] = set()
    for item in _get_items(registry_data):
        metadata = _resource_metadata(item)
        spec = _resource_spec(item) or {}
        for candidate in (metadata.get("namespace"), spec.get("targetNamespace")):
            if candidate and candidate not in seen:
                seen.add(candidate)
                ordered.append(candidate)
    return ordered


def _is_quay_application_pod(pod: dict) -> bool:
    """True when the pod name is a Quay application workload."""
    name = _resource_name(pod, "")
    return "quay-app" in name or "registry-quay-app" in name


def _pod_is_running_ready(pod: dict) -> bool:
    """True when phase is Running and every container reports ready."""
    status = _resource_status(pod)
    if status.get("phase") != "Running":
        return False
    container_statuses = status.get("containerStatuses") or []
    if not container_statuses:
        return False
    return all(container.get("ready") is True for container in container_statuses)


def _namespace_has_running_quay_app(pods: list, namespace: str) -> bool:
    """True when the namespace has a matching Running application pod."""
    for pod in pods:
        if _resource_metadata(pod).get("namespace") != namespace:
            continue
        if _is_quay_application_pod(pod) and _pod_is_running_ready(pod):
            return True
    return False


def _evaluate_quay_pods(
    registry_data: dict,
    pods_data: dict,
    category_id: str,
    category_name: str,
) -> list[CheckResult]:
    """FAIL when a QuayRegistry namespace has no Running quay-app pod."""
    check_id = f"{category_id}.quay.pods"
    title = "Internal Quay application pods"
    if _is_missing(pods_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "quay_pods payload missing or collection error", "quay",
        )]
    registry_namespaces = _quay_registry_namespaces(registry_data)
    if not registry_namespaces:
        return [CheckResult(
            category_id, category_name, check_id, title, "NOT_APPLICABLE",
            "No QuayRegistry installed", "quay",
        )]
    pods = _get_items(pods_data)
    missing_namespaces = [
        namespace for namespace in registry_namespaces
        if not _namespace_has_running_quay_app(pods, namespace)
    ]
    if missing_namespaces:
        listed = ", ".join(missing_namespaces)
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            f"No Running quay-app pod in: {listed}", "quay",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"Running quay-app pod in {len(registry_namespaces)} registry namespace(s)",
        "quay",
    )]


def evaluate_layered(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Dispatch evaluators for 7.4 Layered Products."""
    checks: list[CheckResult] = []
    # Existing product detection
    for product, resource in _LAYERED_PRODUCTS:
        checks.append(_evaluate_layered_product(
            product, category_id, category_name,
            category_data.get(resource, {"_hc_not_found": True}),
        ))
    # TSR 4.x aggregate checks
    checks += _evaluate_cnv_aggregate(category_data, category_id, category_name)
    components = results.get("05_components", {})
    checks += _evaluate_cnv_nncp(
        components.get("nncp", {}),
        components.get("nnce", {}),
        category_id, category_name,
    )
    checks += _evaluate_cnv_virt_storageclass(
        category_data.get("cnv_hyperconverged", {}),
        components.get("storageclass", {}),
        components.get("volumesnapshotclass", {}),
        category_id, category_name,
    )
    checks += _evaluate_oadp_state(
        category_data.get("oadp_dpa", {}),
        category_data.get("oadp_csv", {}),
        category_data.get("backupstoragelocation", {}),
        category_id, category_name,
    )
    checks += evaluate_cnv_p3(category_data, results, category_id, category_name)
    checks += _evaluate_acm_aggregate(category_data, category_id, category_name)
    checks += _evaluate_logging_aggregate(category_data, category_id, category_name)
    checks += _evaluate_odf_state(category_data, category_id, category_name)
    checks += _evaluate_rhoso_state(category_data, category_id, category_name)
    checks += _evaluate_quay_pods(
        category_data.get("quay_registry", {}),
        category_data.get("quay_pods", {}),
        category_id,
        category_name,
    )
    return checks


def _evaluate_odf_state(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    data = category_data.get("odf_storagecluster", {})
    if data.get("_hc_error"):
        return [CheckResult(
            category_id, category_name, f"{category_id}.odf.state",
            "ODF StorageCluster", "SKIPPED",
            "ODF StorageCluster collection failed", "odf",
        )]
    items = [] if data.get("_hc_not_found") else _get_items(data)
    if not items:
        return [CheckResult(
            category_id, category_name, f"{category_id}.odf.state",
            "ODF StorageCluster", "NOT_APPLICABLE",
            "OpenShift Data Foundation StorageCluster not installed", "odf",
        )]
    status, evidence = _product_condition_status(items, degraded_status="FAIL")
    return [CheckResult(
        category_id, category_name, f"{category_id}.odf.state",
        "ODF StorageCluster", status, evidence, "odf",
    )]


def _evaluate_rhoso_state(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    data = category_data.get("rhoso_controlplane", {})
    if data.get("_hc_error"):
        return [CheckResult(
            category_id, category_name, f"{category_id}.rhoso.state",
            "RHOSO OpenStackControlPlane", "SKIPPED",
            "RHOSO OpenStackControlPlane collection failed", "rhoso",
        )]
    items = [] if data.get("_hc_not_found") else _get_items(data)
    if not items:
        return [CheckResult(
            category_id, category_name, f"{category_id}.rhoso.state",
            "RHOSO OpenStackControlPlane", "NOT_APPLICABLE",
            "RHOSO OpenStackControlPlane not installed", "rhoso",
        )]
    status, evidence = _product_condition_status(items, degraded_status="FAIL")
    return [CheckResult(
        category_id, category_name, f"{category_id}.rhoso.state",
        "RHOSO OpenStackControlPlane", status, evidence, "rhoso",
    )]
