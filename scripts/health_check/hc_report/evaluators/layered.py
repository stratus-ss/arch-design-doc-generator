"""Evaluators for 7.4 Layered Products."""
from __future__ import annotations

from hc_report.evaluators._common import (
    _find_condition,
    _get_items,
    _is_missing,
    _resource_metadata,
    _resource_name,
    _resource_status,
)
from hc_report.models import CheckResult

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
    return CheckResult(category_id, category_name, f"{category_id}.{name}", name, "INFO",
                       f"Installed. {len(items)} instance(s) found")


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
    checks += _evaluate_acm_aggregate(category_data, category_id, category_name)
    checks += _evaluate_logging_aggregate(category_data, category_id, category_name)
    return checks
