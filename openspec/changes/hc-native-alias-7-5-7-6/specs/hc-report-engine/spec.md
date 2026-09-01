# Health Check Report Engine (`hc-native-alias-7-5-7-6` delta)

## ADDED Requirements

### Requirement: Sparse TSR aliases for kubelet, pod restarts, and update history
KB row `7.5.tsr.5_1_node_kubelet_health` SHALL be a sparse alias (`content_from` exact `7.5.kubelet_health`, `include_in_findings = false`). KB row `7.5.tsr.5_5_pod_frequent_restarts` SHALL be a sparse alias (`content_from` exact `7.5.pod_restarts`, `include_in_findings = false`). KB row `7.6.tsr.6_2_1_update_history` SHALL be a sparse alias (`content_from` exact `7.6.upgrade.history`, `include_in_findings = false`). Alias rows SHALL NOT overlay inherited narrative keys.

#### Scenario: kubelet TSR id is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.5.tsr.5_1_node_kubelet_health` is loaded
- THEN `content_from` is `7.5.kubelet_health`
- AND `include_in_findings` is false

#### Scenario: pod-restarts TSR id is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.5.tsr.5_5_pod_frequent_restarts` is loaded
- THEN `content_from` is `7.5.pod_restarts`
- AND `include_in_findings` is false

#### Scenario: update-history TSR id is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_2_1_update_history` is loaded
- THEN `content_from` is `7.6.upgrade.history`
- AND `include_in_findings` is false

### Requirement: Native cluster node-utilization rollup
Core evaluation SHALL emit `7.5.node.utilization` after per-node `7.5.node.{short}.utilization` rows when `oc adm top nodes` parses to a non-empty per-node list. Status SHALL be WARNING if any per-node row is WARNING; else INFO if any per-node row is INFO; else PASS. Per-node check_ids SHALL remain. Missing, empty, or unparseable `top_nodes` SHALL emit NOT_APPLICABLE on `7.5.node.utilization` and SHALL keep existing `7.5.node_util` NOT_APPLICABLE. CPU percent WARNING SHALL remain greater than 80; memory percent WARNING SHALL remain greater than 85; INFO SHALL remain CPU greater than 60 or memory greater than 70. The rollup SHALL NOT FAIL. The rollup SHALL NOT re-parse CPU or memory percents.

#### Scenario: any per-node WARNING rolls up to WARNING
- GIVEN at least one per-node utilization row with status WARNING
- WHEN core evaluation runs
- THEN `7.5.node.utilization` status is WARNING
- AND per-node utilization check_ids are still emitted

#### Scenario: all per-node rows PASS
- GIVEN every per-node utilization row is PASS
- WHEN core evaluation runs
- THEN `7.5.node.utilization` status is PASS

#### Scenario: missing top_nodes is NOT_APPLICABLE on both ids
- GIVEN `top_nodes` is missing or `_hc_error`
- WHEN core evaluation runs
- THEN `7.5.node.utilization` status is NOT_APPLICABLE
- AND `7.5.node_util` status is NOT_APPLICABLE

### Requirement: Sparse TSR aliases for current node load
KB rows `7.6.tsr.6_1_3_1_current_node_load` and `7.6.tsr.6_1_3_node_load` SHALL be sparse aliases (`content_from` exact `7.5.node.utilization`, `include_in_findings = false`). There SHALL NOT be a `content_from` chain through `7.6.tsr.6_1_3_1_current_node_load`.

#### Scenario: node-load leaf and parent alias the rollup
- GIVEN production `load_kb()`
- WHEN entries `7.6.tsr.6_1_3_1_current_node_load` and `7.6.tsr.6_1_3_node_load` are loaded
- THEN each `content_from` is `7.5.node.utilization`
- AND each `include_in_findings` is false

### Requirement: Existing pruning hops hidden from Chapter 6
KB rows `7.6.tsr.6_1_5_1_pod_pruning`, `7.6.tsr.6_1_5_4_job_pruning`, `7.6.tsr.6_1_5_6_pruning_namespaces`, and `7.6.tsr.6_1_5_pruning` SHALL set `include_in_findings = false`.

#### Scenario: pruning hops are hidden from findings
- GIVEN production `load_kb()`
- WHEN those four pruning entries are loaded
- THEN each `include_in_findings` is false

### Requirement: Wrong-story TSR rows stay canonical
KB SHALL NOT set `content_from` on `7.6.tsr.6_1_1_1_quota_resources_project_assignment`, `7.6.tsr.6_1_2_requests_and_limits`, `7.6.tsr.6_1_5_3_network_policy_pruning`, or `7.6.tsr.6_2_3_images_patch_management`.

#### Scenario: quota leaf is not an alias
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_1_1_1_quota_resources_project_assignment` is loaded
- THEN `content_from` is empty

### Requirement: Active-alerts hop is out of this change
KB row `7.6.tsr.6_3_1_active_alerts` SHALL NOT be retargeted by this change.

#### Scenario: active-alerts hop unchanged here
- GIVEN this change
- WHEN KB is loaded
- THEN `7.6.tsr.6_3_1_active_alerts` is not required to point at `7.5.node.utilization`

### Requirement: Kubelet Ready and upgrade Partial stay non-FAIL
`7.5.kubelet_health` SHALL remain WARNING when any node Ready is not True. `7.6.upgrade.history` SHALL NOT FAIL Partial or Failed hops in this change.

#### Scenario: kubelet not Ready is WARNING
- GIVEN a node whose Ready condition is not True
- WHEN core evaluation runs
- THEN `7.5.kubelet_health` status is WARNING
