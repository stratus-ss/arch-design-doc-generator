"""CNV P3 native evaluators dispatched from evaluate_layered."""
from __future__ import annotations

import json

from hc_report.evaluators._common import (
    _find_condition,
    _get_items,
    _is_missing,
    _parse_alerts_list,
    _resource_labels,
    _resource_metadata,
    _resource_name,
    _resource_spec,
    _resource_status,
    subscription_is_virtualization,
)
from hc_report.models import CheckResult

_CNV_OPERATOR_NAMESPACE = "openshift-cnv"
_NMSTATE_OPERATOR_NAMESPACE = "openshift-nmstate"
_SRIOV_OPERATOR_NAMESPACE = "openshift-sriov-network-operator"
_WARNING_VMI_PHASES = frozenset({"Pending", "Scheduling", "Failed", "Unknown"})
_BRIDGE_CNI_TYPES = frozenset({"cnv-bridge", "bridge"})
_CPU_VIRT_VMX_LABEL = "cpu-feature.node.kubevirt.io/vmx"
_CPU_VIRT_SVM_LABEL = "cpu-feature.node.kubevirt.io/svm"
_CNV_ALERT_TOKENS = frozenset({
    "kubevirt",
    "cdi",
    "ssp",
    "hco",
    "hyperconverged",
    "openshift-cnv",
    "nmstate",
})
_CNV_ALERT_ACTIVE_STATES = frozenset({"firing", "pending"})


def _hyperconverged_is_missing(hyperconverged_data: dict) -> bool:
    return bool(hyperconverged_data.get("_hc_not_found") or _is_missing(hyperconverged_data))


def _csv_items_in_namespace(csv_data: dict, namespace: str) -> list[dict]:
    return [
        item for item in _get_items(csv_data)
        if _resource_metadata(item).get("namespace") == namespace
    ]


def _evaluate_cnv_subscription(
    hyperconverged_data: dict,
    subscriptions_data: dict,
    category_id: str,
    category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.cnv.subscription"
    title = "CNV related subscriptions"
    if _hyperconverged_is_missing(hyperconverged_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "NOT_APPLICABLE",
            "OpenShift Virtualization not installed", "cnv",
        )]
    required = [
        item for item in _get_items(subscriptions_data)
        if _resource_metadata(item).get("namespace") == _CNV_OPERATOR_NAMESPACE
        and subscription_is_virtualization(item)
    ]
    unhealthy = []
    for item in required:
        status = _resource_status(item)
        if (
            status.get("state") != "AtLatestKnown"
            or status.get("installedCSV") != status.get("currentCSV")
        ):
            unhealthy.append(item)
    if not required or unhealthy:
        names = ", ".join(_resource_name(item) for item in (unhealthy or required)[:5]) or "none"
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            f"kubevirt-hyperconverged subscription in {_CNV_OPERATOR_NAMESPACE} not AtLatestKnown with matching CSVs: {names}",
            "cnv",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"{len(required)} kubevirt-hyperconverged subscription(s) AtLatestKnown",
        "cnv",
    )]


def _evaluate_cnv_nmstate_csv(
    csv_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.cnv.nmstate_csv"
    title = "NMState operator CSV"
    items = _csv_items_in_namespace(csv_data, _NMSTATE_OPERATOR_NAMESPACE)
    if not items:
        return [CheckResult(
            category_id, category_name, check_id, title, "NOT_APPLICABLE",
            f"No CSV items in {_NMSTATE_OPERATOR_NAMESPACE}", "cnv",
        )]
    failed = [item for item in items if _resource_status(item).get("phase") != "Succeeded"]
    if failed:
        names = ", ".join(_resource_name(item) for item in failed[:5])
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            f"{len(failed)} CSV(s) in {_NMSTATE_OPERATOR_NAMESPACE} not Succeeded: {names}",
            "cnv",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"{len(items)} CSV(s) in {_NMSTATE_OPERATOR_NAMESPACE} Succeeded",
        "cnv",
    )]


def _evaluate_cnv_sriov_csv(
    csv_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.cnv.sriov_csv"
    title = "SR-IOV operator CSV"
    items = _csv_items_in_namespace(csv_data, _SRIOV_OPERATOR_NAMESPACE)
    if not items:
        return [CheckResult(
            category_id, category_name, check_id, title, "NOT_APPLICABLE",
            f"No CSV items in {_SRIOV_OPERATOR_NAMESPACE}", "cnv",
        )]
    failed = [item for item in items if _resource_status(item).get("phase") != "Succeeded"]
    if failed:
        names = ", ".join(_resource_name(item) for item in failed[:5])
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            f"{len(failed)} CSV(s) in {_SRIOV_OPERATOR_NAMESPACE} not Succeeded: {names}",
            "cnv",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"{len(items)} CSV(s) in {_SRIOV_OPERATOR_NAMESPACE} Succeeded",
        "cnv",
    )]


def _evaluate_cnv_run_strategy(
    hyperconverged_data: dict,
    vm_data: dict,
    category_id: str,
    category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.cnv.run_strategy"
    title = "VM run strategy"
    if _hyperconverged_is_missing(hyperconverged_data) or _is_missing(vm_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "HyperConverged or VM payload missing", "cnv",
        )]
    items = _get_items(vm_data)
    if not items:
        return [CheckResult(
            category_id, category_name, check_id, title, "NOT_APPLICABLE",
            "No VirtualMachine items", "cnv",
        )]
    not_always = [
        item for item in items
        if _resource_spec(item).get("runStrategy") != "Always"
    ]
    if not_always:
        names = ", ".join(_resource_name(item) for item in not_always[:5])
        return [CheckResult(
            category_id, category_name, check_id, title, "INFO",
            f"{len(not_always)} VM(s) runStrategy is not Always: {names}",
            "cnv",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"{len(items)} VM(s) runStrategy Always",
        "cnv",
    )]


def _evaluate_cnv_vmi_phase(
    vmi_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.cnv.vmi_phase"
    title = "VMI phase"
    if _is_missing(vmi_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "VMI payload missing", "cnv",
        )]
    items = _get_items(vmi_data)
    if not items:
        return [CheckResult(
            category_id, category_name, check_id, title, "NOT_APPLICABLE",
            "No VirtualMachineInstance items", "cnv",
        )]
    warning_items = [
        item for item in items
        if _resource_status(item).get("phase") in _WARNING_VMI_PHASES
    ]
    if warning_items:
        names = ", ".join(_resource_name(item) for item in warning_items[:5])
        return [CheckResult(
            category_id, category_name, check_id, title, "WARNING",
            f"{len(warning_items)} VMI(s) Pending, Scheduling, Failed, or Unknown: {names}",
            "cnv",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"{len(items)} VMI(s) not in warning phases",
        "cnv",
    )]


def _evaluate_cnv_migration_network(
    hyperconverged_data: dict,
    nad_data: dict,
    category_id: str,
    category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.cnv.migration_network"
    title = "Live migration network"
    if _hyperconverged_is_missing(hyperconverged_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "NOT_APPLICABLE",
            "OpenShift Virtualization not installed", "cnv",
        )]
    items = _get_items(hyperconverged_data, default_single=True)
    hyperconverged = items[0] if items else {}
    network = (
        _resource_spec(hyperconverged).get("liveMigrationConfig", {}).get("network")
        if isinstance(_resource_spec(hyperconverged).get("liveMigrationConfig"), dict)
        else None
    )
    if network in (None, "", "<none>"):
        return [CheckResult(
            category_id, category_name, check_id, title, "PASS",
            "Live-migration network empty; default pod network", "cnv",
        )]
    nad_match = any(
        _resource_metadata(item).get("name") == network
        and _resource_metadata(item).get("namespace") == _CNV_OPERATOR_NAMESPACE
        for item in ([] if _is_missing(nad_data) else _get_items(nad_data))
    )
    if not nad_match:
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            f"Named live-migration network {network!r} has no NAD in {_CNV_OPERATOR_NAMESPACE}",
            "cnv",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"NAD {network} found in {_CNV_OPERATOR_NAMESPACE}",
        "cnv",
    )]


def _evaluate_cnv_linux_bridge(
    nad_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.cnv.linux_bridge"
    title = "Linux bridge network"
    if _is_missing(nad_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "NetworkAttachmentDefinition payload missing", "cnv",
        )]
    bridge_count = 0
    for item in _get_items(nad_data):
        config = _resource_spec(item).get("config")
        cni_type = None
        if isinstance(config, dict):
            cni_type = config.get("type")
        elif isinstance(config, str):
            try:
                parsed = json.loads(config)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                cni_type = parsed.get("type")
        if cni_type in _BRIDGE_CNI_TYPES:
            bridge_count += 1
    if bridge_count == 0:
        return [CheckResult(
            category_id, category_name, check_id, title, "INFO",
            "No NAD with cnv-bridge or bridge CNI type", "cnv",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"{bridge_count} NAD(s) with cnv-bridge or bridge CNI type",
        "cnv",
    )]


def _evaluate_cnv_node_placement(
    hyperconverged_data: dict,
    daemonset_data: dict,
    nodes_data: dict,
    category_id: str,
    category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.cnv.node_placement"
    title = "CNV operators node placement"
    if _hyperconverged_is_missing(hyperconverged_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "NOT_APPLICABLE",
            "OpenShift Virtualization not installed", "cnv",
        )]
    daemonset_items = [] if _is_missing(daemonset_data) else _get_items(
        daemonset_data, default_single=True,
    )
    if not daemonset_items:
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "virt-handler DaemonSet missing", "cnv",
        )]
    daemonset_status = _resource_status(daemonset_items[0])
    try:
        number_ready = int(daemonset_status.get("numberReady") or 0)
        desired_scheduled = int(daemonset_status.get("desiredNumberScheduled") or 0)
    except (TypeError, ValueError):
        number_ready = 0
        desired_scheduled = 0
    if number_ready != desired_scheduled:
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            f"virt-handler numberReady={number_ready} desiredNumberScheduled={desired_scheduled}",
            "cnv",
        )]
    unschedulable_workers = []
    for node in ([] if _is_missing(nodes_data) else _get_items(nodes_data)):
        labels = _resource_labels(node)
        if (
            "node-role.kubernetes.io/control-plane" in labels
            or "node-role.kubernetes.io/master" in labels
        ):
            continue
        if labels.get("kubevirt.io/schedulable") != "true":
            unschedulable_workers.append(node)
    if unschedulable_workers:
        names = ", ".join(_resource_name(item) for item in unschedulable_workers[:5])
        return [CheckResult(
            category_id, category_name, check_id, title, "WARNING",
            f"{len(unschedulable_workers)} non-control-plane node(s) lack kubevirt.io/schedulable=true: {names}",
            "cnv",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"virt-handler ready={number_ready}/{desired_scheduled}; workers schedulable or none",
        "cnv",
    )]


def _evaluate_cnv_cdi(
    cdi_data: dict,
    pods_data: dict,
    category_id: str,
    category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.cnv.cdi"
    title = "CDI image upload"
    if _is_missing(cdi_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "NOT_APPLICABLE",
            "CDI custom resource not present", "cnv",
        )]
    items = _get_items(cdi_data, default_single=True)
    if not items:
        return [CheckResult(
            category_id, category_name, check_id, title, "NOT_APPLICABLE",
            "CDI custom resource not present", "cnv",
        )]
    conditions = _resource_status(items[0]).get("conditions", [])
    if not isinstance(conditions, list):
        conditions = []
    available = _find_condition(conditions, "Available")
    progressing = _find_condition(conditions, "Progressing")
    degraded = _find_condition(conditions, "Degraded")
    conditions_ok = (
        available.get("status") == "True"
        and progressing.get("status") == "False"
        and degraded.get("status") == "False"
    )
    if not conditions_ok:
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            (
                f"CDI conditions Available={available.get('status', '?')} "
                f"Progressing={progressing.get('status', '?')} "
                f"Degraded={degraded.get('status', '?')}"
            ),
            "cnv",
        )]
    uploadproxy_pods = [
        item for item in ([] if _is_missing(pods_data) else _get_items(pods_data))
        if _resource_labels(item).get("app") == "cdi-uploadproxy"
    ]
    unready = [
        item for item in uploadproxy_pods
        if _find_condition(
            _resource_status(item).get("conditions", [])
            if isinstance(_resource_status(item).get("conditions"), list)
            else [],
            "Ready",
        ).get("status") != "True"
    ]
    if not uploadproxy_pods or unready:
        return [CheckResult(
            category_id, category_name, check_id, title, "WARNING",
            "cdi-uploadproxy missing or not Ready", "cnv",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        "CDI Available and cdi-uploadproxy Ready", "cnv",
    )]


def _evaluate_cnv_storageprofile(
    storageprofile_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.cnv.storageprofile"
    title = "CDI storage profiles"
    if _is_missing(storageprofile_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "NOT_APPLICABLE",
            "StorageProfile payload missing", "cnv",
        )]
    items = _get_items(storageprofile_data)
    if not items:
        return [CheckResult(
            category_id, category_name, check_id, title, "INFO",
            "No StorageProfile items", "cnv",
        )]
    copy_items = [
        item for item in items
        if _resource_status(item).get("cloneStrategy") == "copy"
    ]
    if copy_items:
        names = ", ".join(_resource_name(item) for item in copy_items[:5])
        return [CheckResult(
            category_id, category_name, check_id, title, "WARNING",
            f"{len(copy_items)} StorageProfile(s) cloneStrategy copy: {names}",
            "cnv",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"{len(items)} StorageProfile(s) without cloneStrategy copy",
        "cnv",
    )]


def _quota_used_equals_hard(item: dict) -> bool:
    spec_hard = _resource_spec(item).get("hard")
    status_used = _resource_status(item).get("used")
    if not isinstance(spec_hard, dict) or not isinstance(status_used, dict):
        return False
    for key, used_value in status_used.items():
        if key in spec_hard and str(used_value) == str(spec_hard[key]):
            return True
    return False


def _evaluate_cnv_vm_quota(
    hyperconverged_data: dict,
    vm_data: dict,
    resourcequota_data: dict,
    category_id: str,
    category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.cnv.vm_quota"
    title = "CNV quota and resources"
    if _hyperconverged_is_missing(hyperconverged_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "NOT_APPLICABLE",
            "OpenShift Virtualization not installed", "cnv",
        )]
    vm_items = _get_items(vm_data)
    if not vm_items:
        return [CheckResult(
            category_id, category_name, check_id, title, "NOT_APPLICABLE",
            "No VirtualMachine items", "cnv",
        )]
    vm_namespaces = {
        _resource_metadata(item).get("namespace") for item in vm_items
    }
    quota_items = [] if _is_missing(resourcequota_data) else _get_items(
        resourcequota_data,
    )
    quotas_by_namespace: dict[str | None, list[dict]] = {}
    for quota in quota_items:
        namespace = _resource_metadata(quota).get("namespace")
        quotas_by_namespace.setdefault(namespace, []).append(quota)
    missing_quota_namespaces = [
        namespace for namespace in vm_namespaces
        if not quotas_by_namespace.get(namespace)
    ]
    if missing_quota_namespaces:
        names = ", ".join(
            str(namespace) for namespace in list(missing_quota_namespaces)[:5]
        )
        return [CheckResult(
            category_id, category_name, check_id, title, "INFO",
            f"{len(missing_quota_namespaces)} VM namespace(s) have no ResourceQuota: {names}",
            "cnv",
        )]
    exhausted = [
        quota
        for namespace in vm_namespaces
        for quota in quotas_by_namespace.get(namespace, [])
        if _quota_used_equals_hard(quota)
    ]
    if exhausted:
        names = ", ".join(_resource_name(item) for item in exhausted[:5])
        return [CheckResult(
            category_id, category_name, check_id, title, "WARNING",
            f"{len(exhausted)} ResourceQuota(s) used equals hard: {names}",
            "cnv",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"{len(vm_namespaces)} VM namespace(s) have ResourceQuota without used-equals-hard",
        "cnv",
    )]


def _evaluate_cnv_cpu_virt_flag(
    nodes_data: dict,
    hyperconverged_data: dict,
    category_id: str,
    category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.cnv.cpu_virt_flag"
    title = "Node hardware virtualization flags"
    if _hyperconverged_is_missing(hyperconverged_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "NOT_APPLICABLE",
            "OpenShift Virtualization not installed", "cnv",
        )]
    if nodes_data.get("_hc_error"):
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "Nodes payload unreadable", "cnv",
        )]
    flagged_nodes = []
    for node in ([] if _is_missing(nodes_data) else _get_items(nodes_data)):
        if (_resource_spec(node) or {}).get("unschedulable") is True:
            continue
        labels = _resource_labels(node) or {}
        if (
            labels.get(_CPU_VIRT_VMX_LABEL) == "true"
            or labels.get(_CPU_VIRT_SVM_LABEL) == "true"
        ):
            flagged_nodes.append(node)
    if not flagged_nodes:
        return [CheckResult(
            category_id, category_name, check_id, title, "WARNING",
            "No schedulable node has cpu-feature vmx or svm true",
            "cnv",
        )]
    names = ", ".join(_resource_name(item) for item in flagged_nodes[:5])
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"{len(flagged_nodes)} schedulable node(s) have vmx or svm: {names}",
        "cnv",
    )]


def _evaluate_cnv_alerts(
    alerts_data: dict,
    category_id: str,
    category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.cnv.alerts"
    title = "CNV firing alerts"
    if _is_missing(alerts_data):
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "firing_alerts not collected", "cnv",
        )]
    matching_names: list[str] = []
    for alert in _parse_alerts_list(alerts_data):
        state = str(alert.get("state", "")).casefold()
        if state not in _CNV_ALERT_ACTIVE_STATES:
            continue
        labels = alert.get("labels") or {}
        alert_name = str(labels.get("alertname", "")).casefold()
        namespace = str(labels.get("namespace", "")).casefold()
        if any(token in alert_name or token in namespace for token in _CNV_ALERT_TOKENS):
            matching_names.append(str(labels.get("alertname", "unknown")))
    if matching_names:
        joined = ", ".join(matching_names[:5])
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            f"{len(matching_names)} virt alert(s) firing or pending: {joined}",
            "cnv",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        "No kubevirt, CDI, SSP, HCO, NMState, or openshift-cnv alerts firing or pending",
        "cnv",
    )]


def evaluate_cnv_p3(
    category_data: dict, results: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    base = results.get("03_base_platform", {})
    components = results.get("05_components", {})
    hyperconverged_data = category_data.get("cnv_hyperconverged", {})
    csv_data = base.get("csv", {})
    checks: list[CheckResult] = []
    checks += _evaluate_cnv_subscription(
        hyperconverged_data, base.get("subscriptions", {}), category_id, category_name,
    )
    checks += _evaluate_cnv_nmstate_csv(csv_data, category_id, category_name)
    checks += _evaluate_cnv_sriov_csv(csv_data, category_id, category_name)
    checks += _evaluate_cnv_run_strategy(
        hyperconverged_data, category_data.get("cnv_vm", {}), category_id, category_name,
    )
    checks += _evaluate_cnv_vmi_phase(
        category_data.get("cnv_vmi", {}), category_id, category_name,
    )
    checks += _evaluate_cnv_migration_network(
        hyperconverged_data, components.get("net_attach_def", {}), category_id, category_name,
    )
    checks += _evaluate_cnv_linux_bridge(
        components.get("net_attach_def", {}), category_id, category_name,
    )
    checks += _evaluate_cnv_node_placement(
        hyperconverged_data,
        category_data.get("cnv_virt_handler_ds", {}),
        base.get("nodes", {}),
        category_id,
        category_name,
    )
    checks += _evaluate_cnv_cdi(
        category_data.get("cnv_cdi", {}),
        category_data.get("cnv_pods", {}),
        category_id,
        category_name,
    )
    checks += _evaluate_cnv_storageprofile(
        components.get("storageprofile", {}),
        category_id,
        category_name,
    )
    checks += _evaluate_cnv_vm_quota(
        hyperconverged_data,
        category_data.get("cnv_vm", {}),
        results.get("08_day2", {}).get("resourcequota", {}),
        category_id,
        category_name,
    )
    checks += _evaluate_cnv_cpu_virt_flag(
        base.get("nodes", {}),
        hyperconverged_data,
        category_id,
        category_name,
    )
    checks += _evaluate_cnv_alerts(
        results.get("07_cluster_health", {}).get("firing_alerts", {}),
        category_id,
        category_name,
    )
    return checks
