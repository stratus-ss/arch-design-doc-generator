# Health Check Report Engine (`hc-native-system-reserved` delta)

## ADDED Requirements

### Requirement: Native effective kubelet systemReserved scoring
Core evaluation SHALL emit `7.2.kubelet.system_reserved` with title `Effective kubelet systemReserved`. The engine SHALL read `results["08_day2"]["node_image_gc"]` members and `category_data` nodes. Per member, `system_reserved_memory` and `auto_sizing_reserved` SHALL come from kubeletconfig excerpts only. `_hc_error` with empty members SHALL be SKIPPED. Zero members SHALL be NOT_APPLICABLE. Any member missing reserved memory and not `auto_sizing_reserved` true SHALL be WARNING. Else any node with capacity ≥64 GiB whose reserved memory is exactly `1Gi` or `1G` SHALL be INFO. Else PASS. The check SHALL NOT FAIL. `_check_system_reserved` / `7.2.node.*.sysreserved` bars SHALL not change. Raw configz SHALL not be written to `hc_results`.

#### Scenario: default 1Gi on large node is INFO
- GIVEN a `node_image_gc` member with `system_reserved_memory` `1Gi`
- AND the matching node capacity is ≥64 GiB
- AND no member is missing reserved memory without auto-size
- WHEN core evaluation runs
- THEN `7.2.kubelet.system_reserved` status is INFO
- AND the status is not WARNING or FAIL

#### Scenario: 2Gi reserved is PASS
- GIVEN every member has parseable reserved memory `2Gi`
- AND no member hits the 1Gi-on-≥64-GiB bar
- WHEN core evaluation runs
- THEN `7.2.kubelet.system_reserved` status is PASS
- AND the status is not INFO

#### Scenario: missing reserved memory is WARNING
- GIVEN a member with empty `system_reserved_memory`
- AND `auto_sizing_reserved` is not true
- WHEN core evaluation runs
- THEN `7.2.kubelet.system_reserved` status is WARNING
- AND the status is not PASS

#### Scenario: per-node sysreserved bars stay CR-based
- GIVEN a node with ≥64 GiB RAM and no matching KubeletConfig `systemReserved`
- WHEN `_check_system_reserved` runs
- THEN that node's `7.2.node.*.sysreserved` status is WARNING

## MODIFIED Requirements

None. Per-node CR-based `sysreserved` scoring is unchanged.
