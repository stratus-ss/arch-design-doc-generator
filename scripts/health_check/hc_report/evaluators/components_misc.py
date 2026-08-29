"""Miscellaneous component evaluator helpers."""
from __future__ import annotations

from hc_report.evaluators._common import (
    _find_condition,
    _get_items,
    _is_missing,
    _not_applicable,
    _resource_name,
    _resource_spec,
)
from hc_report.evaluators._shared_checks import check_mcp_degraded
from hc_report.models import CheckResult


def _evaluate_misc_master_and_limits(results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    scheduler = results.get("03_base_platform", {}).get("scheduler", {})
    if _is_missing(scheduler):
        master_check = CheckResult(category_id, category_name, f"{category_id}.misc.master_config",
                                   "3.4 Master Configuration", "SKIPPED",
                                   "Scheduler data not available", "scheduler")
    else:
        profile = scheduler.get("spec", {}).get("profile", "")
        master_sched = scheduler.get("spec", {}).get("mastersSchedulable", True)
        master_check = CheckResult(category_id, category_name, f"{category_id}.misc.master_config",
                                   "3.4 Master Configuration", "PASS",
                                   f"Scheduler profile: {profile or 'default'}, mastersSchedulable: {master_sched}",
                                   "scheduler")
    return [
        master_check,
        CheckResult(category_id, category_name, f"{category_id}.misc.ocp_limits",
                    "3.11 OCP Limits", "SKIPPED",
                    "Subscription limit verification not available in collection",
                    "limits"),
    ]


def _evaluate_misc_loadbalancer(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    checks: list[CheckResult] = []
    infra = results.get("03_base_platform", {}).get("infrastructure", {})
    if _is_missing(infra):
        checks.append(_not_applicable(f"{category_id}.misc.lb", "3.14.1 Platform Load Balancer", category_id, category_name))
    else:
        platform_type = infra.get("spec", {}).get("platformSpec", {}).get("type", "") or infra.get("status", {}).get("platform", "")
        lb_type = infra.get("status", {}).get("platformStatus", {}).get("type", platform_type)
        checks.append(CheckResult(category_id, category_name, f"{category_id}.misc.lb",
                                  "3.14.1 Platform Load Balancer", "INFO",
                                  f"Platform: {lb_type}", "infrastructure"))
    cluster_operator_data = category_data.get("cluster_operators", category_data.get("clusteroperators", {}))
    metallb_installed = any(
        "metallb" in _resource_name(item, default="").lower()
        for item in _get_items(cluster_operator_data, default_single=True)
    ) if not _is_missing(cluster_operator_data) else False
    metallb_data = category_data.get("metallb")
    metallb_items = []
    if metallb_data is not None and not _is_missing(metallb_data):
        metallb_items = _get_items(metallb_data)
    if metallb_installed:
        checks.append(CheckResult(
            category_id, category_name, f"{category_id}.misc.metallb_installed",
            "3.14.2.1 MetalLB Installed", "PASS",
            "MetalLB operator detected in cluster operators", "metallb",
        ))
        if metallb_data is None:
            config_status, config_evidence = (
                "SKIPPED",
                "MetalLB configuration details require dedicated collection",
            )
        elif metallb_items:
            config_status, config_evidence = (
                "PASS",
                f"{len(metallb_items)} MetalLB CR(s) present",
            )
        else:
            config_status, config_evidence = (
                "WARNING",
                "MetalLB operator present but no MetalLB CRs",
            )
        checks.append(CheckResult(
            category_id, category_name, f"{category_id}.misc.metallb_config",
            "3.14.2.2 MetalLB Config", config_status, config_evidence, "metallb",
        ))
        checks.append(CheckResult(
            category_id, category_name, f"{category_id}.misc.metallb_l2",
            "3.14.2.3 MetalLB L2 ARP/NDP", "SKIPPED",
            "MetalLB L2 config requires dedicated collection", "metallb",
        ))
        return checks
    if metallb_items:
        checks.append(CheckResult(
            category_id, category_name, f"{category_id}.misc.metallb_installed",
            "3.14.2.1 MetalLB Installed", "PASS",
            "MetalLB CR(s) present", "metallb",
        ))
        checks.append(CheckResult(
            category_id, category_name, f"{category_id}.misc.metallb_config",
            "3.14.2.2 MetalLB Config", "PASS",
            f"{len(metallb_items)} MetalLB CR(s) present", "metallb",
        ))
        checks.append(CheckResult(
            category_id, category_name, f"{category_id}.misc.metallb_l2",
            "3.14.2.3 MetalLB L2 ARP/NDP", "SKIPPED",
            "MetalLB L2 config requires dedicated collection", "metallb",
        ))
        return checks
    for suffix, title in [
        ("metallb_installed", "3.14.2.1 MetalLB Installed"),
        ("metallb_config", "3.14.2.2 MetalLB Config"),
        ("metallb_l2", "3.14.2.3 MetalLB L2 ARP/NDP"),
    ]:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.misc.{suffix}",
                                  title, "NOT_APPLICABLE",
                                  "MetalLB not installed", "metallb"))
    return checks


def _evaluate_misc_mcp_and_sctp(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    machine_config_pool_data = category_data.get("machineconfig", {})
    if _is_missing(machine_config_pool_data):
        mcp_check = _not_applicable(f"{category_id}.misc.mcp", "3.15 Machine Config Pool", category_id, category_name)
    else:
        mc_items = _get_items(machine_config_pool_data, default_single=True)
        degraded_mcs, updating_mcs = check_mcp_degraded(machine_config_pool_data)
        if degraded_mcs:
            mcp_check = CheckResult(category_id, category_name, f"{category_id}.misc.mcp",
                                    "3.15 Machine Config Pool", "WARNING",
                                    f"Degraded MCPs: {', '.join(degraded_mcs[:3])}",
                                    "machineconfig")
        elif updating_mcs:
            mcp_check = CheckResult(category_id, category_name, f"{category_id}.misc.mcp",
                                    "3.15 Machine Config Pool", "WARNING",
                                    f"Updating MCPs: {', '.join(updating_mcs[:3])}",
                                    "machineconfig")
        else:
            mcp_check = CheckResult(category_id, category_name, f"{category_id}.misc.mcp",
                                    "3.15 Machine Config Pool", "PASS",
                                    f"{len(mc_items)} MachineConfig(s) — none degraded or updating",
                                    "machineconfig")
    return [
        mcp_check,
        CheckResult(category_id, category_name, f"{category_id}.misc.sctp",
                    "3.16 SCTP", "NOT_APPLICABLE",
                    "SCTP detection requires MachineConfig kernel module inspection",
                    "sctp"),
    ]


def _evaluate_misc_capabilities_and_workloads(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    checks: list[CheckResult] = []
    cluster_version = results.get("03_base_platform", {}).get("clusterversion", {})
    if _is_missing(cluster_version):
        checks.append(_not_applicable(f"{category_id}.misc.capabilities", "3.18 Cluster Capabilities", category_id, category_name))
    else:
        capabilities = cluster_version.get("spec", {}).get("capabilities", {})
        if capabilities:
            enabled = capabilities.get("additionalEnabledCapabilities", [])
            baseline = capabilities.get("baselineCapabilitySet", "")
            checks.append(CheckResult(category_id, category_name, f"{category_id}.misc.capabilities",
                                      "3.18 Cluster Capabilities", "PASS",
                                      f"Baseline: {baseline}, additional: {len(enabled)}",
                                      "clusterversion"))
        else:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.misc.capabilities",
                                      "3.18 Cluster Capabilities", "PASS",
                                      "Full capability set (no restrictions)",
                                      "clusterversion"))
    checks.append(CheckResult(category_id, category_name, f"{category_id}.misc.sandboxed",
                              "3.19 Sandboxed Containers", "NOT_APPLICABLE",
                              "Kata/sandboxed containers not detected in standard collection",
                              "kata"))
    nodes_data = results.get("03_base_platform", {}).get("nodes", {})
    if _is_missing(nodes_data):
        checks.append(_not_applicable(f"{category_id}.misc.cgroups", "3.20 Linux Cgroups Version", category_id, category_name))
    else:
        cgroup_versions = set()
        for node in _get_items(nodes_data):
            runtime_ver = node.get("status", {}).get("nodeInfo", {}).get("containerRuntimeVersion", "")
            os_image = node.get("status", {}).get("nodeInfo", {}).get("osImage", "")
            if "crun" in runtime_ver.lower() or "rhel 9" in os_image.lower() or "coreos" in os_image.lower():
                cgroup_versions.add("v2")
            else:
                cgroup_versions.add("v1/v2")
        status = "PASS" if cgroup_versions == {"v2"} else "INFO"
        evidence = "cgroups v2 (RHCOS 9.x / OCP 4.14+)" if status == "PASS" else f"cgroup versions detected: {cgroup_versions}"
        checks.append(CheckResult(category_id, category_name, f"{category_id}.misc.cgroups",
                                  "3.20 Linux Cgroups Version", status, evidence, "nodes"))
    checks.append(CheckResult(category_id, category_name, f"{category_id}.misc.deploymentconfig",
                              "3.21 Deployment Config Usage", "SKIPPED",
                              "DC detection requires dedicated API query not in standard collection",
                              "deploymentconfig"))
    checks += _evaluate_misc_performance_profiles(category_data, category_id, category_name)
    return checks


def _evaluate_misc_performance_profiles(
    category_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    performance_profile_data = category_data.get("performanceprofile", {})
    items = [] if _is_missing(performance_profile_data) else _get_items(performance_profile_data)
    names = [_resource_name(item) for item in items]
    checks = [CheckResult(
        category_id, category_name, f"{category_id}.misc.wp_enabled",
        "3.22.1 Workload Partitioning Enabled",
        "PASS" if items else "INFO",
        "Workload partitioning: " + (
            f"{len(items)} PerformanceProfile(s)" if items
            else "not detected (standard workload mode)"
        ),
        "performanceprofile",
    )]
    checks.append(CheckResult(
        category_id, category_name, f"{category_id}.misc.pp_mcp",
        "3.22.2 Performance Profile Match MCP",
        "SKIPPED" if items else "NOT_APPLICABLE",
        "Performance Profile MCP matching is not scored this release"
        if items else "Performance Profile not in use",
        "performanceprofile",
    ))
    if not items:
        checks.append(CheckResult(
            category_id, category_name, f"{category_id}.misc.pp_status",
            "3.22.3 Performance Profile Status", "NOT_APPLICABLE",
            "Performance Profile not in use", "performanceprofile",
        ))
        checks.append(CheckResult(
            category_id, category_name, f"{category_id}.misc.pp_config",
            "3.22.4 Performance Profile Configuration", "NOT_APPLICABLE",
            "Performance Profile not in use", "performanceprofile",
        ))
        return checks
    degraded_names = []
    available_names = []
    for item in items:
        conditions = item.get("status", {}).get("conditions", [])
        if _find_condition(conditions, "Degraded").get("status") == "True":
            degraded_names.append(_resource_name(item))
        if _find_condition(conditions, "Available").get("status") == "True":
            available_names.append(_resource_name(item))
    if degraded_names:
        status, evidence = "WARNING", f"Degraded PerformanceProfile(s): {', '.join(degraded_names[:5])}"
    else:
        status, evidence = "PASS", f"PerformanceProfile Available: {', '.join(available_names[:5]) or ', '.join(names[:5])}"
    checks.append(CheckResult(
        category_id, category_name, f"{category_id}.misc.pp_status",
        "3.22.3 Performance Profile Status", status, evidence, "performanceprofile",
    ))
    cpu_notes = []
    for item in items:
        cpu = _resource_spec(item).get("cpu", {})
        if isinstance(cpu, dict) and (cpu.get("isolated") or cpu.get("reserved")):
            cpu_notes.append(
                f"{_resource_name(item)} isolated={cpu.get('isolated', '')} reserved={cpu.get('reserved', '')}"
            )
    config_evidence = f"Profiles: {', '.join(names[:8])}"
    if cpu_notes:
        config_evidence = f"{config_evidence}; {'; '.join(cpu_notes[:3])}"
    checks.append(CheckResult(
        category_id, category_name, f"{category_id}.misc.pp_config",
        "3.22.4 Performance Profile Configuration", "INFO",
        config_evidence, "performanceprofile",
    ))
    return checks


def _evaluate_misc_components(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """TSR 3.4, 3.11, 3.13-3.16, 3.18-3.22."""
    checks: list[CheckResult] = []
    checks += _evaluate_misc_master_and_limits(results, category_id, category_name)
    checks += _evaluate_misc_loadbalancer(category_data, results, category_id, category_name)
    checks += _evaluate_misc_mcp_and_sctp(category_data, category_id, category_name)
    checks += _evaluate_misc_capabilities_and_workloads(category_data, results, category_id, category_name)
    return checks
