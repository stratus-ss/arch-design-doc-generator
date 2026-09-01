# Health Check Report Engine (`hc-native-alias-7-3` delta)

## ADDED Requirements

### Requirement: Native cluster platform-operator rollup
Core evaluation SHALL emit `7.3.co.platform` after per-operator `7.3.co.{name}` rows when clusteroperators parse to a non-empty per-operator list. Status SHALL be FAIL if any per-operator row is FAIL; else WARNING if any per-operator row is WARNING; else PASS. Per-operator check_ids SHALL remain, including exact `7.3.co.kube-apiserver`. Missing clusteroperators SHALL emit NOT_APPLICABLE on `7.3.co.platform` and SHALL keep existing `7.3.co` NOT_APPLICABLE. The rollup SHALL NOT re-read operator conditions or call `find_degraded_operators`. Per-operator FAIL/WARNING/PASS bars SHALL not change in this change.

#### Scenario: any degraded operator rolls up to FAIL
- GIVEN at least one per-operator row with status FAIL
- WHEN core evaluation runs
- THEN `7.3.co.platform` status is FAIL
- AND per-operator check_ids are still emitted

#### Scenario: all per-operator rows PASS
- GIVEN every per-operator row is PASS
- WHEN core evaluation runs
- THEN `7.3.co.platform` status is PASS

#### Scenario: missing clusteroperators is NOT_APPLICABLE on both ids
- GIVEN clusteroperators payload is missing or empty
- WHEN core evaluation runs
- THEN `7.3.co.platform` status is NOT_APPLICABLE
- AND `7.3.co` status is NOT_APPLICABLE

### Requirement: Sparse TSR aliases for platform operators
KB rows `7.3.tsr.3_2_1_platform_operators` and `7.3.tsr.3_2_operators` SHALL be sparse aliases (`content_from` exact `7.3.co.platform`, `include_in_findings = false`). KB rows `7.3.tsr.3_2_2_additional_operators` and `7.7.ccx_internal.uninstalled_operators_with_leftover_resources` SHALL be sparse aliases (`content_from` exact `7.3.co.platform`, `include_in_findings = false`). There SHALL NOT be a `content_from` chain through `7.3.tsr.3_2_1_platform_operators`. Alias rows SHALL NOT overlay inherited narrative keys.

#### Scenario: 3.2.1 and 3.2 parent alias the rollup
- GIVEN production `load_kb()`
- WHEN entries `7.3.tsr.3_2_1_platform_operators` and `7.3.tsr.3_2_operators` are loaded
- THEN each `content_from` is `7.3.co.platform`
- AND each `include_in_findings` is false

#### Scenario: additional-operators and leftover CCX alias the rollup
- GIVEN production `load_kb()`
- WHEN entries `7.3.tsr.3_2_2_additional_operators` and `7.7.ccx_internal.uninstalled_operators_with_leftover_resources` are loaded
- THEN each `content_from` is `7.3.co.platform`
- AND each `include_in_findings` is false

### Requirement: CRD TSR aliases CRD count not operators
KB row `7.3.tsr.3_3_custom_resource_definitions` SHALL be a sparse alias (`content_from` exact `7.3.crds`, `include_in_findings = false`). It SHALL NOT target `7.3.co.platform` or `7.3.tsr.3_2_1_platform_operators`. CRD WARNING when count is greater than 500 SHALL not change in this change.

#### Scenario: CRD TSR aliases 7.3.crds
- GIVEN production `load_kb()`
- WHEN entry `7.3.tsr.3_3_custom_resource_definitions` is loaded
- THEN `content_from` is `7.3.crds`
- AND `include_in_findings` is false

### Requirement: Sparse TSR alias for ingress sharding
KB row `7.3.tsr.3_8_3_ingress_sharding` SHALL be a sparse alias (`content_from` exact `7.3.ingress.sharding`, `include_in_findings = false`). Ingress sharding bars SHALL not change in this change.

#### Scenario: sharding TSR aliases the native
- GIVEN production `load_kb()`
- WHEN entry `7.3.tsr.3_8_3_ingress_sharding` is loaded
- THEN `content_from` is `7.3.ingress.sharding`
- AND `include_in_findings` is false

### Requirement: Sparse TSR aliases for machine config pool
KB rows `7.3.tsr.3_15_machine_config_pool` and `7.5.tsr.5_2_machine_config` SHALL be sparse aliases (`content_from` exact `7.3.misc.mcp`, `include_in_findings = false`). There SHALL NOT be a `content_from` chain through `7.3.tsr.3_15_machine_config_pool`. MCP WARNING on degraded or updating SHALL not change in this change. These rows SHALL NOT alias `7.5.mcp_health`.

#### Scenario: MCP TSR and 5.2 alias 7.3.misc.mcp
- GIVEN production `load_kb()`
- WHEN entries `7.3.tsr.3_15_machine_config_pool` and `7.5.tsr.5_2_machine_config` are loaded
- THEN each `content_from` is `7.3.misc.mcp`
- AND each `include_in_findings` is false

### Requirement: CSI TSR stays canonical
KB SHALL NOT set `content_from` on `7.3.tsr.3_9_5_csi_drivers`. Platform-operator TSR SHALL NOT alias `7.5.operator_state`.

#### Scenario: CSI TSR is not an alias
- GIVEN production `load_kb()`
- WHEN entry `7.3.tsr.3_9_5_csi_drivers` is loaded
- THEN `content_from` is empty

### Requirement: Exact kube-apiserver KB remains
Exact KB row `7.3.co.kube-apiserver` SHALL remain. Exact `7.3.co.platform` SHALL win over glob `7.3.co.*`.

#### Scenario: kube-apiserver exact row still exists
- GIVEN production `load_kb()`
- WHEN entry `7.3.co.kube-apiserver` is loaded
- THEN the row is present as an exact check_id
