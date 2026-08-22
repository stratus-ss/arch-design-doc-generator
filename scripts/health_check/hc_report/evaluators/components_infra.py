"""Infrastructure-oriented component evaluator helpers."""
from __future__ import annotations

from collections import Counter

from hc_report.evaluators._common import (
    _cluster_version_object,
    _find_condition,
    _get_items,
    _is_missing,
    _not_applicable,
    _resource_annotations,
    _resource_metadata,
    _resource_name,
    _resource_spec,
    _resource_status,
)
from hc_report.models import CheckResult


def _evaluate_cluster_version(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """TSR 3.1: Cluster Version summary from clusterversion resource."""
    cluster_version_raw = results.get("03_base_platform", {}).get("clusterversion", {})
    cluster_version = _cluster_version_object(cluster_version_raw)
    if _is_missing(cluster_version):
        return [_not_applicable(f"{category_id}.version", "3.1 Cluster Version", category_id, category_name)]
    status = cluster_version.get("status", {})
    history = status.get("history", [])
    current = history[0] if history else {}
    version = current.get("version", status.get("desired", {}).get("version", "unknown"))
    state = current.get("state", "unknown")
    if state == "Completed":
        return [CheckResult(category_id, category_name, f"{category_id}.version",
                            "3.1 Cluster Version", "PASS",
                            f"Version {version}, state: Completed", "clusterversion")]
    return [CheckResult(category_id, category_name, f"{category_id}.version",
                        "3.1 Cluster Version", "WARNING",
                        f"Version {version}, state: {state}", "clusterversion")]


def _evaluate_etcd_endpoints(output: str, category_id: str, category_name: str) -> list[CheckResult]:
    etcd_members = [
        line for line in output.splitlines()
        if "etcd-" in line and "Running" in line and "guard" not in line
    ]
    total_etcd = len(etcd_members)
    if total_etcd >= 3:
        return [CheckResult(category_id, category_name, f"{category_id}.etcd.endpoints",
                            "3.5.1 ETCD Endpoints", "PASS",
                            f"{total_etcd} etcd members running", "etcd")]
    if total_etcd > 0:
        return [CheckResult(category_id, category_name, f"{category_id}.etcd.endpoints",
                            "3.5.1 ETCD Endpoints", "WARNING",
                            f"Only {total_etcd} etcd members detected (3 expected for HA)", "etcd")]
    if output:
        return [CheckResult(category_id, category_name, f"{category_id}.etcd.endpoints",
                            "3.5.1 ETCD Endpoints", "SKIPPED",
                            "etcd status output present but no member pods found", "etcd")]
    return [_not_applicable(f"{category_id}.etcd.endpoints", "3.5.1 ETCD Endpoints", category_id, category_name)]


def _evaluate_etcd_leader(results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    leader_output = results.get("04_topology", {}).get("etcd_status", {}).get("output", "")
    status = "PASS" if "leader" in leader_output.lower() else "SKIPPED"
    evidence = "Leader election data present" if status == "PASS" else "Leader election data not available in collection"
    return [CheckResult(category_id, category_name, f"{category_id}.etcd.leader",
                        "3.5.2 ETCD Leader", status, evidence, "etcd")]


def _evaluate_etcd_health(output: str, exit_code: int, category_id: str, category_name: str) -> list[CheckResult]:
    if exit_code != 0 or not output:
        return [CheckResult(category_id, category_name, f"{category_id}.etcd.health",
                            "3.5.3 ETCD Health", "SKIPPED",
                            "etcd health data not available", "etcd")]
    not_running = [
        line.strip() for line in output.splitlines()
        if "etcd-" in line and "guard" not in line and "Running" not in line
    ]
    if not_running:
        return [CheckResult(category_id, category_name, f"{category_id}.etcd.health",
                            "3.5.3 ETCD Health", "FAIL",
                            f"etcd pods not healthy: {not_running[0][:100]}", "etcd")]
    return [CheckResult(category_id, category_name, f"{category_id}.etcd.health",
                        "3.5.3 ETCD Health", "PASS",
                        "All etcd pods Running", "etcd")]


def _evaluate_etcd_metrics_placeholders(category_id: str, category_name: str) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for section_id, title in [
        ("3.5.4", "3.5.4 ETCD Database Size"),
        ("3.5.5", "3.5.5 ETCD Compaction"),
        ("3.5.6", "3.5.6 ETCD Defragmentation"),
        ("3.5.7", "3.5.7 ETCD Log Errors"),
        ("3.5.8.1", "3.5.8.1 ETCD Disk Performance"),
        ("3.5.8.2", "3.5.8.2 ETCD Network Performance"),
        ("3.5.8.3", "3.5.8.3 ETCD CPU Performance"),
        ("3.5.9", "3.5.9 ETCD Alerts"),
    ]:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.etcd.{section_id.replace('.', '_')}",
                                  title, "SKIPPED",
                                  "Requires etcdctl metrics/prometheus data not in standard collection",
                                  "etcd", tsr_ref=section_id))
    return checks


def _evaluate_etcd_aggregate(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """TSR 3.5.x: ETCD checks from etcd_status and etcd_pods."""
    etcd_status = category_data.get("etcd_status", {})
    output = etcd_status.get("output", "") if isinstance(etcd_status, dict) else ""
    exit_code = etcd_status.get("exit_code", -1) if isinstance(etcd_status, dict) else -1

    checks: list[CheckResult] = []
    checks += _evaluate_etcd_endpoints(output, category_id, category_name)
    checks += _evaluate_etcd_leader(results, category_id, category_name)
    checks += _evaluate_etcd_health(output, exit_code, category_id, category_name)
    checks += _evaluate_etcd_metrics_placeholders(category_id, category_name)
    return checks


def _evaluate_ingress_status(items: list[dict], category_id: str, category_name: str) -> list[CheckResult]:
    running = sum(
        1 for item in items
        if _find_condition(_resource_status(item).get("conditions", []), "Available").get("status") == "True"
    )
    return [CheckResult(category_id, category_name, f"{category_id}.haproxy.status",
                        "3.8.1 HAProxy Status", "PASS" if running == len(items) else "WARNING",
                        f"{running}/{len(items)} ingress controller(s) Available",
                        "ingresscontroller")]


def _evaluate_ingress_tuning(items: list[dict], category_id: str, category_name: str) -> list[CheckResult]:
    tuned = []
    for item in items:
        tuning = item.get("spec", {}).get("tuningOptions", {})
        if tuning and any(value for value in tuning.values() if value and value != "0s"):
            tuned.append(f"{item.get('metadata', {}).get('name', '?')}: {tuning}")
    if tuned:
        return [CheckResult(category_id, category_name, f"{category_id}.ingress.tuning",
                            "3.8.2 Ingress Controller Tuning", "INFO",
                            f"Custom tuning: {'; '.join(str(value) for value in tuned[:3])}",
                            "ingresscontroller")]
    return [CheckResult(category_id, category_name, f"{category_id}.ingress.tuning",
                        "3.8.2 Ingress Controller Tuning", "INFO",
                        "Default tuning (no custom tuningOptions set)",
                        "ingresscontroller")]


def _evaluate_ingress_sharding(items: list[dict], category_id: str, category_name: str) -> list[CheckResult]:
    sharded = [
        _resource_metadata(item).get("name")
        for item in items
        if _resource_spec(item).get("routeSelector") or _resource_spec(item).get("namespaceSelector")
    ]
    if len(items) > 1:
        return [CheckResult(category_id, category_name, f"{category_id}.ingress.sharding",
                            "3.8.3 Ingress Sharding", "WARNING" if not sharded else "PASS",
                            f"{len(items)} controllers, {len(sharded)} with route/namespace selectors"
                            + (" — consider sharding for traffic isolation" if not sharded else ""),
                            "ingresscontroller")]
    return [CheckResult(category_id, category_name, f"{category_id}.ingress.sharding",
                        "3.8.3 Ingress Sharding", "INFO",
                        "Single ingress controller — sharding not applicable",
                        "ingresscontroller")]


def _evaluate_ingress_aggregate(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """TSR 3.8.x: HAProxy status, tuning, sharding."""
    ingress_controller_data = category_data.get("ingresscontroller", {})
    if _is_missing(ingress_controller_data):
        return [_not_applicable(f"{category_id}.ingress.agg", "3.8 Ingress", category_id, category_name)]
    items = _get_items(ingress_controller_data, default_single=True)
    checks: list[CheckResult] = []
    checks += _evaluate_ingress_status(items, category_id, category_name)
    checks += _evaluate_ingress_tuning(items, category_id, category_name)
    checks += _evaluate_ingress_sharding(items, category_id, category_name)
    return checks


def _evaluate_storage_aggregate(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """TSR 3.9.5, 3.9.6: CSI drivers, flexvolumes."""
    checks: list[CheckResult] = []
    storage_class_data = category_data.get("storageclass", {})
    if not _is_missing(storage_class_data):
        items = _get_items(storage_class_data, default_single=True)
        provisioners = set(storage_class.get("provisioner", "") for storage_class in items)
        csi = [provider for provider in provisioners if ".csi." in provider or provider.endswith(".csi")]
        if csi:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.storage.csi",
                                      "StorageClass provisioners (engine)", "PASS",
                                      f"CSI provisioners: {', '.join(sorted(csi))}",
                                      "storageclass"))
        else:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.storage.csi",
                                      "StorageClass provisioners (engine)", "WARNING",
                                      f"No CSI drivers detected. Provisioners: {', '.join(sorted(provisioners))}",
                                      "storageclass"))
        flex = [provider for provider in provisioners if "flex" in provider.lower()]
        checks.append(CheckResult(category_id, category_name, f"{category_id}.storage.flexvolumes",
                                  "3.9.6 Storage Flexvolumes",
                                  "WARNING" if flex else "NOT_APPLICABLE",
                                  f"Flexvolume provisioners: {flex}" if flex
                                  else "No flexvolume provisioners (deprecated mechanism not in use)",
                                  "storageclass"))
    else:
        checks.append(_not_applicable(f"{category_id}.storage.csi", "StorageClass provisioners (engine)", category_id, category_name))
        checks.append(CheckResult(category_id, category_name, f"{category_id}.storage.flexvolumes",
                                  "3.9.6 Storage Flexvolumes", "NOT_APPLICABLE",
                                  "Storage class data unavailable", "storageclass"))
    return checks


def _evaluate_storage(storage_class_data: dict, pv_data: dict, pvc_data: dict,
                  category_id: str, category_name: str) -> list[CheckResult]:
    """Storage classes, PV count, PVC binding health."""
    checks = []
    checks += _evaluate_storage_classes(storage_class_data, category_id, category_name)
    checks += _evaluate_pvs(pv_data, category_id, category_name)
    checks += _evaluate_pvcs(pvc_data, category_id, category_name)
    return checks


def _evaluate_storage_classes(storage_class_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    if _is_missing(storage_class_data):
        return [_not_applicable(f"{category_id}.storage.default_sc", "Default StorageClass", category_id, category_name)]
    items = _get_items(storage_class_data, default_single=True)
    default_storage_classes = [
        _resource_metadata(storage_class).get("name")
        for storage_class in items
        if _resource_annotations(storage_class).get(
            "storageclass.kubernetes.io/is-default-class"
        ) == "true"
    ]
    if not default_storage_classes:
        return [CheckResult(category_id, category_name, f"{category_id}.storage.default_sc",
                            "Default StorageClass", "WARNING",
                            f"{len(items)} storage class(es) found but none is set as default",
                            "storageclass")]
    provisioners = [
        storage_class.get("provisioner", "unknown")
        for storage_class in items
        if _resource_metadata(storage_class).get("name") in default_storage_classes
    ]
    return [CheckResult(category_id, category_name, f"{category_id}.storage.default_sc",
                        "Default StorageClass", "PASS",
                        f"Default SC: {', '.join(str(class_name) for class_name in default_storage_classes)}. "
                        f"Provisioner(s): {', '.join(provisioners)}. Total SCs: {len(items)}",
                        "storageclass")]


def _evaluate_pvs(pv_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    if _is_missing(pv_data):
        return [_not_applicable(f"{category_id}.storage.pvs", "Persistent Volume Health", category_id, category_name)]
    pv_items = _get_items(pv_data)
    pv_phases: Counter = Counter(_resource_status(volume).get("phase") for volume in pv_items)
    failed_pvs = pv_phases.get("Failed", 0) + pv_phases.get("Pending", 0)
    if failed_pvs:
        return [CheckResult(category_id, category_name, f"{category_id}.storage.pvs",
                            "Persistent Volume Health", "WARNING",
                            f"{len(pv_items)} PVs: {dict(pv_phases)}. {failed_pvs} Failed/Pending",
                            "pv")]
    return [CheckResult(category_id, category_name, f"{category_id}.storage.pvs",
                        "Persistent Volume Health", "PASS",
                        f"{len(pv_items)} PVs: {dict(pv_phases)}", "pv")]


def _evaluate_pvcs(pvc_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    if _is_missing(pvc_data):
        return [_not_applicable(f"{category_id}.storage.pvcs", "PVC Binding Health", category_id, category_name)]
    pvc_items = _get_items(pvc_data)
    unbound = [
        _resource_metadata(volume).get("name")
        for volume in pvc_items
        if _resource_status(volume).get("phase") != "Bound"
    ]
    if unbound:
        return [CheckResult(category_id, category_name, f"{category_id}.storage.pvcs",
                            "PVC Binding Health", "WARNING",
                            f"{len(unbound)}/{len(pvc_items)} PVCs not Bound: "
                            f"{', '.join(str(pvc_name) for pvc_name in unbound[:5])}", "pvc")]
    return [CheckResult(category_id, category_name, f"{category_id}.storage.pvcs",
                        "PVC Binding Health", "PASS",
                        f"All {len(pvc_items)} PVCs are Bound", "pvc")]


def _evaluate_crds(crds_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """CRD count and inventory."""
    if _is_missing(crds_data):
        return [_not_applicable(f"{category_id}.crds", "Custom Resource Definitions", category_id, category_name)]
    items = _get_items(crds_data)
    groups: set[str] = set()
    for custom_resource in items:
        group = custom_resource.get("spec", {}).get("group", "")
        if group:
            groups.add(group.split(".")[0] if "." in group else group)
    status = "WARNING" if len(items) > 500 else "INFO"
    return [CheckResult(category_id, category_name, f"{category_id}.crds",
                        "7.3.3 Custom Resource Definitions", status,
                        f"{len(items)} CRDs installed across {len(groups)} API groups"
                        + (" — high CRD count may impact API server performance" if status == "WARNING" else ""),
                        "crd")]


def _evaluate_deprecated_apis(api_counts: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """APIs with non-zero request counts for removed/deprecated versions."""
    if _is_missing(api_counts):
        return [_not_applicable(f"{category_id}.deprecated_apis", "Deprecated API Usage", category_id, category_name)]
    items = _get_items(api_counts)
    deprecated = []
    for item in items:
        status = _resource_status(item)
        current_hour = status.get("currentHour", {})
        by_node = current_hour.get("byNode", [])
        removed_in = status.get("removedInRelease", "")
        count_total = sum(
            request_bucket.get("count", 0)
            for request_bucket in by_node
        )
        count_total += status.get("requestsInCurrentHour", 0)
        name = _resource_name(item, default="unknown")
        if removed_in and count_total > 0:
            deprecated.append(f"{name} (removed in {removed_in}, {count_total} req/h)")
    if deprecated:
        return [CheckResult(category_id, category_name, f"{category_id}.deprecated_apis",
                            "7.3.12 Deprecated API Usage", "WARNING",
                            f"{len(deprecated)} deprecated API(s) with active usage: "
                            f"{'; '.join(deprecated[:5])}",
                            "apirequestcounts")]
    return [CheckResult(category_id, category_name, f"{category_id}.deprecated_apis",
                        "7.3.12 Deprecated API Usage", "PASS",
                        "No deprecated API versions with active request counts detected",
                        "apirequestcounts")]
