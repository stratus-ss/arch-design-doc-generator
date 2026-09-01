"""Public-contract tests for 7.5/7.6 aliases and node-load rollup."""
from __future__ import annotations

from hc_report.evaluators.health import _evaluate_node_utilization
from hc_report.kb_loader import load_kb

_TOP_HEADER = "NAME CPU(cores) CPU% MEMORY(bytes) MEMORY%"

_PRUNING_HIDE_IDS = (
    "7.6.tsr.6_1_5_1_pod_pruning",
    "7.6.tsr.6_1_5_4_job_pruning",
    "7.6.tsr.6_1_5_6_pruning_namespaces",
    "7.6.tsr.6_1_5_pruning",
)


def _cluster_rollup(checks):
    match = next(
        (check for check in checks if check.check_id == "7.5.node.utilization"),
        None,
    )
    assert match is not None, "7.5.node.utilization not found in check list"
    return match


def test_node_utilization_rollup_warns_when_cpu_over_eighty() -> None:
    top_nodes_data = {"output": f"{_TOP_HEADER}\nworker-0 250m 81% 1000Mi 10%\n"}
    checks = _evaluate_node_utilization(top_nodes_data, "7.5", "Cluster Health")
    assert _cluster_rollup(checks).status == "WARNING"


def test_node_utilization_rollup_pass_when_all_nodes_ok() -> None:
    top_nodes_data = {"output": f"{_TOP_HEADER}\nworker-0 250m 10% 1000Mi 10%\n"}
    checks = _evaluate_node_utilization(top_nodes_data, "7.5", "Cluster Health")
    assert _cluster_rollup(checks).status == "PASS"


def test_node_utilization_rollup_info_when_cpu_over_sixty() -> None:
    top_nodes_data = {"output": f"{_TOP_HEADER}\nworker-0 500m 65% 1000Mi 10%\n"}
    checks = _evaluate_node_utilization(top_nodes_data, "7.5", "Cluster Health")
    assert _cluster_rollup(checks).status == "INFO"


def test_node_utilization_rollup_na_when_top_nodes_missing() -> None:
    checks = _evaluate_node_utilization({}, "7.5", "Cluster Health")
    rollup = _cluster_rollup(checks)
    assert rollup.status == "NOT_APPLICABLE"


def test_node_utilization_rollup_na_when_output_empty() -> None:
    checks = _evaluate_node_utilization({"output": ""}, "7.5", "Cluster Health")
    rollup = _cluster_rollup(checks)
    assert rollup.status == "NOT_APPLICABLE"


def test_node_utilization_rollup_na_when_output_unparseable() -> None:
    checks = _evaluate_node_utilization({"output": "garbage\n!!!"}, "7.5", "Cluster Health")
    rollup = _cluster_rollup(checks)
    assert rollup.status == "NOT_APPLICABLE"


def test_kubelet_and_restarts_aliases_target_natives() -> None:
    knowledge_base = load_kb()
    kubelet_alias = knowledge_base.get_entry("7.5.tsr.5_1_node_kubelet_health")
    assert kubelet_alias.content_from == "7.5.kubelet_health"
    assert kubelet_alias.include_in_findings is False
    restarts_alias = knowledge_base.get_entry("7.5.tsr.5_5_pod_frequent_restarts")
    assert restarts_alias.content_from == "7.5.pod_restarts"
    assert restarts_alias.include_in_findings is False


def test_update_history_alias_targets_native() -> None:
    knowledge_base = load_kb()
    alias = knowledge_base.get_entry("7.6.tsr.6_2_1_update_history")
    assert alias.content_from == "7.6.upgrade.history"
    assert alias.include_in_findings is False


def test_node_load_parent_and_leaf_alias_to_rollup() -> None:
    knowledge_base = load_kb()
    leaf = knowledge_base.get_entry("7.6.tsr.6_1_3_1_current_node_load")
    parent = knowledge_base.get_entry("7.6.tsr.6_1_3_node_load")
    assert leaf.content_from == "7.5.node.utilization"
    assert parent.content_from == "7.5.node.utilization"
    assert leaf.include_in_findings is False
    assert parent.include_in_findings is False


def test_existing_pruning_aliases_hide_findings() -> None:
    knowledge_base = load_kb()
    for check_id in _PRUNING_HIDE_IDS:
        entry = knowledge_base.get_entry(check_id)
        assert entry.include_in_findings is False


def test_quota_requests_netpol_images_remain_canonical() -> None:
    knowledge_base = load_kb()
    quota = knowledge_base.get_entry("7.6.tsr.6_1_1_1_quota_resources_project_assignment")
    requests = knowledge_base.get_entry("7.6.tsr.6_1_2_requests_and_limits")
    netpol = knowledge_base.get_entry("7.6.tsr.6_1_5_3_network_policy_pruning")
    image = knowledge_base.get_entry("7.6.tsr.6_2_3_images_patch_management")
    assert quota.content_from == "7.6.quota.coverage"
    assert requests.content_from == "7.6.pod.requests"
    assert netpol.content_from == "7.6.netpol.orphan"
    assert image.content_from == "7.6.image.registry_sources"
