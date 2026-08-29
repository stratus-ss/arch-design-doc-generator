"""Networking-focused component evaluator helpers."""
from __future__ import annotations

from hc_report.evaluators._common import (
    _get_items,
    _is_missing,
    _not_applicable,
    _resource_name,
    _resource_spec,
)
from hc_report.models import CheckResult


def _network_type(network_data: dict) -> str:
    if _is_missing(network_data):
        return ""
    spec = network_data.get("spec", {})
    status = network_data.get("status", {})
    return spec.get("networkType") or status.get("networkType", "")


def _ovn_kubernetes_config(network_operator: dict) -> dict:
    spec = _resource_spec(network_operator)
    default_network = spec.get("defaultNetwork", {})
    return default_network.get("ovnKubernetesConfig", {})


def _evaluate_net_plugin_type(net_type: str, category_id: str, category_name: str) -> list[CheckResult]:
    if not net_type:
        return [_not_applicable(f"{category_id}.net.kubeproxy", "3.10.1 KubeProxy", category_id, category_name)]
    kubeproxy_status = "NOT_APPLICABLE" if net_type == "OVNKubernetes" else "INFO"
    kubeproxy_evidence = (
        "OVNKubernetes in use — kube-proxy not deployed"
        if net_type == "OVNKubernetes"
        else f"Network type: {net_type} — kube-proxy may be in use"
    )
    checks = [CheckResult(category_id, category_name, f"{category_id}.net.kubeproxy",
                          "3.10.1 KubeProxy", kubeproxy_status, kubeproxy_evidence, "network")]
    if net_type == "OVNKubernetes":
        checks.append(CheckResult(category_id, category_name, f"{category_id}.net.ovnkube",
                                  "3.10.2 OVNKube", "PASS",
                                  "OVNKubernetes is the active network plugin",
                                  "network"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.net.ovnkube",
                                  "3.10.2 OVNKube", "NOT_APPLICABLE",
                                  f"Network type is {net_type}, not OVNKubernetes",
                                  "network"))
    return checks


def _evaluate_featuregate(category_data: dict, category_id: str, category_name: str) -> CheckResult:
    """Score FeatureGate spec.featureSet (TSR 3.10.3). Missing capture stays SKIPPED."""
    if "featuregate" not in category_data:
        return CheckResult(
            category_id, category_name, f"{category_id}.net.featuregates",
            "3.10.3 Featuregates", "SKIPPED",
            "FeatureGate status not collected — clusteroperators are not a TechPreview detector",
            "network",
        )
    featuregate_data = category_data.get("featuregate", {})
    if _is_missing(featuregate_data):
        return CheckResult(
            category_id, category_name, f"{category_id}.net.featuregates",
            "3.10.3 Featuregates", "SKIPPED",
            "FeatureGate capture missing or not found",
            "network",
        )
    items = _get_items(featuregate_data, default_single=True)
    feature_set = ""
    if items:
        feature_set = str(_resource_spec(items[0]).get("featureSet") or "")
    if feature_set in ("TechPreviewNoUpgrade", "CustomNoUpgrade"):
        return CheckResult(
            category_id, category_name, f"{category_id}.net.featuregates",
            "3.10.3 Featuregates", "FAIL",
            f"FeatureGate featureSet is {feature_set} (irreversible; blocks upgrades)",
            "network",
            scoring_basis="doc_backed",
        )
    return CheckResult(
        category_id, category_name, f"{category_id}.net.featuregates",
        "3.10.3 Featuregates", "PASS",
        f"FeatureGate featureSet is {feature_set or 'Default'}",
        "network",
    )


def _evaluate_net_config(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    checks: list[CheckResult] = [_evaluate_featuregate(category_data, category_id, category_name)]
    machine_config_pool_data = category_data.get("machineconfig", {})
    if _is_missing(machine_config_pool_data):
        checks.append(_not_applicable(f"{category_id}.net.kubelet_config", "3.10.4 Kubelet-Config", category_id, category_name))
        return checks
    kubelet_mcs = [
        _resource_name(item, default="")
        for item in _get_items(machine_config_pool_data, default_single=True)
        if "kubelet" in _resource_name(item, default="").lower()
    ]
    checks.append(CheckResult(category_id, category_name, f"{category_id}.net.kubelet_config",
                              "3.10.4 Kubelet-Config", "PASS",
                              f"{len(kubelet_mcs)} kubelet-related MachineConfig(s): "
                              f"{', '.join(kubelet_mcs[:5])}",
                              "machineconfig"))
    return checks


def _evaluate_net_ip_stack(network_data: dict, net_op: dict, category_id: str, category_name: str) -> list[CheckResult]:
    if not _is_missing(net_op):
        ovn_config = _ovn_kubernetes_config(net_op)
        has_v4 = ovn_config.get("ipv4") or True
        has_v6 = ovn_config.get("ipv6")
        if has_v6 and has_v4:
            stack = "Dual-stack (IPv4 + IPv6)"
        elif has_v6:
            stack = "IPv6 single-stack"
        else:
            stack = "IPv4 single-stack"
        return [CheckResult(category_id, category_name, f"{category_id}.net.ipstack",
                            "3.17.1 IP Stack", "PASS", stack, "network")]
    if _is_missing(network_data):
        return [_not_applicable(f"{category_id}.net.ipstack", "3.17.1 IP Stack", category_id, category_name)]
    cluster_nets = network_data.get("spec", {}).get("clusterNetwork") or network_data.get("status", {}).get("clusterNetwork", [])
    has_v6 = any(":" in (network.get("cidr", "") if isinstance(network, dict) else str(network)) for network in cluster_nets)
    has_v4 = any("." in (network.get("cidr", "") if isinstance(network, dict) else str(network)) for network in cluster_nets)
    if has_v4 and has_v6:
        stack = "Dual-stack"
    elif has_v6:
        stack = "IPv6"
    else:
        stack = "IPv4"
    return [CheckResult(category_id, category_name, f"{category_id}.net.ipstack",
                        "3.17.1 IP Stack", "PASS", f"IP Stack: {stack}", "network")]


def _ipsec_result_for_mode(mode: str, category_id: str, category_name: str) -> CheckResult:
    normalized = str(mode or "Disabled")
    status = "PASS" if normalized.lower() in {"full", "on"} else "INFO"
    return CheckResult(
        category_id, category_name, f"{category_id}.net.ipsec",
        "3.17.2 IPsec Encryption", status,
        f"IPsec mode: {normalized}", "network",
    )


def _ipsec_mode_from_cr(ipsec_config: dict) -> str:
    items = _get_items(ipsec_config)
    if not items:
        items = _get_items(ipsec_config, default_single=True)
    for item in items:
        spec = _resource_spec(item)
        mode = spec.get("mode") or spec.get("ipsecMode")
        if mode:
            return str(mode)
    return "Disabled"


def _evaluate_net_ipsec(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    ipsec_config = category_data.get("ipsecconfig", {})
    net_op = category_data.get("network_operator", {})
    if not _is_missing(ipsec_config):
        return [_ipsec_result_for_mode(_ipsec_mode_from_cr(ipsec_config), category_id, category_name)]
    if _is_missing(net_op):
        return [_not_applicable(
            f"{category_id}.net.ipsec", "3.17.2 IPsec Encryption", category_id, category_name,
        )]
    ovn_config = _ovn_kubernetes_config(net_op)
    ipsec = ovn_config.get("ipsecConfig", {})
    mode = ipsec.get("mode", "Disabled") if isinstance(ipsec, dict) else "Disabled"
    return [_ipsec_result_for_mode(str(mode), category_id, category_name)]


def _evaluate_net_additional(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    checks: list[CheckResult] = []
    nad_data = category_data.get("net_attach_def", {})
    if not _is_missing(nad_data):
        nad_items = _get_items(nad_data)
        checks.append(CheckResult(category_id, category_name, f"{category_id}.net.multinet",
                                  "3.17.3 Multiple Networks", "INFO",
                                  f"{len(nad_items)} NetworkAttachmentDefinition(s) present" if nad_items
                                  else "No additional networks configured (single network)",
                                  "net_attach_def"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.net.multinet",
                                  "3.17.3 Multiple Networks", "INFO",
                                  "NetworkAttachmentDefinition data not collected", "net_attach_def"))
    nncp_data = category_data.get("nncp", {})
    sriov_data = category_data.get("sriovnetwork", {})
    nncp_items = [] if _is_missing(nncp_data) else _get_items(nncp_data)
    sriov_items = [] if _is_missing(sriov_data) else _get_items(sriov_data)
    if nncp_items or sriov_items:
        evidence_parts = []
        if nncp_items:
            evidence_parts.append(f"{len(nncp_items)} NodeNetworkConfigurationPolicy(ies)")
        if sriov_items:
            evidence_parts.append(f"{len(sriov_items)} SriovNetwork(s)")
        checks.append(CheckResult(
            category_id, category_name, f"{category_id}.net.hwnet",
            "3.17.4 Hardware Networks", "INFO",
            "; ".join(evidence_parts),
            "nncp",
        ))
    else:
        checks.append(CheckResult(
            category_id, category_name, f"{category_id}.net.hwnet",
            "3.17.4 Hardware Networks", "NOT_APPLICABLE",
            "No NNCP or SriovNetwork resources (hardware networking not configured)",
            "nncp",
        ))
    return checks


def _evaluate_networking_features(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """TSR 3.10.x, 3.17.x: KubeProxy, OVNKube, featuregates, IP stack, IPsec, multi-net, HW nets."""
    network_data = category_data.get("network", {})
    net_op = category_data.get("network_operator", {})
    net_type = _network_type(network_data)

    checks: list[CheckResult] = []
    checks += _evaluate_net_plugin_type(net_type, category_id, category_name)
    checks += _evaluate_net_config(category_data, category_id, category_name)
    checks += _evaluate_net_ip_stack(network_data, net_op, category_id, category_name)
    checks += _evaluate_net_ipsec(category_data, category_id, category_name)
    checks += _evaluate_net_additional(category_data, category_id, category_name)
    return checks
