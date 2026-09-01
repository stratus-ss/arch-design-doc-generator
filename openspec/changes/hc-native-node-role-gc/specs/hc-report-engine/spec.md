# Health Check Report Engine (`hc-native-node-role-gc` delta)

## ADDED Requirements

### Requirement: Node-roles missing-label scoring stays independent of taints
Core evaluation SHALL emit `7.5.node_roles`. The check SHALL FAIL when any node has an empty `node_roles(labels)` set (no `node-role.kubernetes.io/*` labels). The check SHALL PASS when every node has at least one role label. Payload missing SHALL remain SKIPPED (current engine status). `7.5.master_taints` SHALL remain independently scored. `7.5.node_roles` SHALL NOT absorb taint or compact-NoSchedule logic.

#### Scenario: unlabeled node fails node_roles
- GIVEN a node with no `node-role.kubernetes.io/*` labels
- WHEN core evaluation runs
- THEN `7.5.node_roles` status is FAIL

#### Scenario: every node has a role label
- GIVEN every node has at least one `node-role.kubernetes.io/*` label
- WHEN core evaluation runs
- THEN `7.5.node_roles` status is PASS

#### Scenario: master_taints is not folded into node_roles
- GIVEN a compact cluster with master NoSchedule taints
- WHEN core evaluation runs
- THEN `7.5.master_taints` is still emitted
- AND `7.5.node_roles` scoring does not use taint presence as its FAIL bar

### Requirement: Sparse TSR alias for ORIG node-role values
KB row `7.5.tsr.5_6_node_role_values` SHALL be a sparse alias (`content_from` exact `7.5.node_roles`, `include_in_findings = false`). Alias rows SHALL NOT overlay inherited narrative keys.

#### Scenario: node-role TSR id is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.5.tsr.5_6_node_role_values` is loaded
- THEN `content_from` is `7.5.node_roles`
- AND `include_in_findings` is false

### Requirement: Native node image garbage-collection aggregate
Core evaluation SHALL emit `7.6.node.image_gc`. Per member, `high_percent` SHALL be the collected `configz` `imageGCHighThresholdPercent` when present, else the named constant `IMAGE_GC_HIGH_DEFAULT_PERCENT` (85). Early warning SHALL use the named constant `IMAGE_GC_EARLY_WARNING_PERCENT` (50). FAIL when any member with numeric `used_percent` has `used_percent >= high_percent`. Else WARNING when any such member has `used_percent >= 50`. PASS when all scored members have `used_percent < 50`. INFO when the document is missing or has `_hc_error` at the root, or when no member has numeric `used_percent`. A member with missing `stats/summary` SHALL be omitted from FAIL and WARNING. `scoring_basis` SHALL be `doc_backed` on image_gc FAIL only. There SHALL be no per-node check_ids in this change.

#### Scenario: used percent at HIGH fails
- GIVEN a member with numeric `used_percent` equal to `high_percent` (including default 85)
- WHEN core evaluation runs
- THEN `7.6.node.image_gc` status is FAIL
- AND `scoring_basis` is `doc_backed`

#### Scenario: used percent at early warning
- GIVEN no member at or above HIGH
- AND at least one member with `used_percent` equal to 50 and `high_percent` equal to 85
- WHEN core evaluation runs
- THEN `7.6.node.image_gc` status is WARNING

#### Scenario: all scored members below 50
- GIVEN every member with numeric `used_percent` is below 50
- WHEN core evaluation runs
- THEN `7.6.node.image_gc` status is PASS

#### Scenario: all stats missing is INFO
- GIVEN every member has `_hc_error` true and no numeric `used_percent`
- WHEN core evaluation runs
- THEN `7.6.node.image_gc` status is INFO

### Requirement: Sparse TSR alias for ORIG node garbage collection
KB row `7.6.tsr.6_1_5_5_node_garbage_collection` SHALL be a sparse alias (`content_from` exact `7.6.node.image_gc`, `include_in_findings = false`). Alias rows SHALL NOT overlay inherited narrative keys.

#### Scenario: GC TSR id is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_1_5_5_node_garbage_collection` is loaded
- THEN `content_from` is `7.6.node.image_gc`
- AND `include_in_findings` is false

### Requirement: Live-only node image GC collect
Live collect MAY write `node_image_gc` under `08_day2`. Supportshell MAY omit that file. Supportshell SHALL NOT call node proxy `configz` or `stats/summary`. Collect SHALL NOT persist full kubelet `configz` or `stats/summary` documents; results SHALL contain counts, bytes, and percents only.

#### Scenario: supportshell omits live-only GC file
- GIVEN supportshell `08_day2.sh`
- WHEN an operator runs must-gather collect
- THEN `node_image_gc` is not produced via node proxy

#### Scenario: collect does not dump raw proxy bodies
- GIVEN live `hc_node_image_gc_stats`
- WHEN `node_image_gc.json` is written
- THEN the file does not contain a full `configz` or `stats/summary` document
