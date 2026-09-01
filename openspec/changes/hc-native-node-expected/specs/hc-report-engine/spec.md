# Health Check Report Engine (`hc-native-node-expected` delta)

## ADDED Requirements

### Requirement: Native node expected limits scoring
Core evaluation SHALL emit one cluster rollup `7.6.node.expected_limits`. The engine SHALL read `results["10_metrics"]["node_cpu_limits_pct"]` and `results["10_metrics"]["node_memory_limits_pct"]`. Missing both payloads (`_is_missing`) SHALL be SKIPPED. The engine SHALL parse Prometheus vectors; sample label `node` SHALL match PromQL `by (node)`. FAIL if any sample is ≥ 90. WARNING if any sample is ≥ 80 and none is ≥ 90. Else PASS. Evidence SHALL list node and percent. The engine SHALL NOT emit per-node check_ids. Stub `7.6.node_expected` SHALL remain SKIPPED. The engine SHALL NOT retune `7.8.node.*.alloc`. The engine SHALL NOT use `oc adm top`. Collect SHALL NOT add a new query.

#### Scenario: any sample at or above 90 is FAIL
- GIVEN a Prometheus vector sample with value 90
- WHEN evaluate_checks core
- THEN `7.6.node.expected_limits` is FAIL

#### Scenario: any sample at or above 80 with none at 90 is WARNING
- GIVEN a Prometheus vector sample with value 80 and no sample ≥ 90
- WHEN evaluate_checks core
- THEN `7.6.node.expected_limits` is WARNING

#### Scenario: all samples below 80 is PASS
- GIVEN Prometheus vector samples all below 80
- WHEN evaluate_checks core
- THEN `7.6.node.expected_limits` is PASS

#### Scenario: both payloads missing is SKIPPED
- GIVEN both `node_cpu_limits_pct` and `node_memory_limits_pct` missing
- WHEN evaluate_checks core
- THEN `7.6.node.expected_limits` is SKIPPED

### Requirement: Sparse TSR alias for node expected resource consumption
KB row `7.6.tsr.6_1_3_2_node_expected_resource_consumption` SHALL be a sparse alias (`content_from` exact `7.6.node.expected_limits`, `include_in_findings = false`). Alias rows SHALL NOT overlay inherited narrative keys.

#### Scenario: node expected TSR aliases native
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_1_3_2_node_expected_resource_consumption` is loaded
- THEN `content_from` is `7.6.node.expected_limits`

## MODIFIED Requirements

None. Stub `7.6.node_expected` remains SKIPPED. `7.8.node.*.alloc` bars are unchanged.
