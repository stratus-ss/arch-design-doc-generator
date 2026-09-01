# Health Check Report Engine (`hc-native-virt-cpu-flags` delta)

## ADDED Requirements

### Requirement: Native virt CPU flags from kubevirt labels
Core evaluation SHALL emit `7.4.cnv.cpu_virt_flag`. HyperConverged missing (`_is_missing` or `_hc_not_found`) SHALL be NOT_APPLICABLE. Nodes payload `_hc_error` SHALL be SKIPPED. A matching node SHALL be a schedulable node (`spec.unschedulable` is not true) whose labels include `cpu-feature.node.kubevirt.io/vmx` equal to `true` or `cpu-feature.node.kubevirt.io/svm` equal to `true`. Zero matching nodes SHALL be WARNING. Else the check SHALL PASS. The check SHALL NEVER FAIL. The check SHALL NOT require both vmx and svm. The check SHALL NOT read `/proc/cpuinfo`. The check SHALL NOT retarget `7.4.tsr.4_8_1_3_2_node_cpu`.

#### Scenario: svm label is PASS
- GIVEN HyperConverged present
- AND a schedulable node with label `cpu-feature.node.kubevirt.io/svm` equal to `true`
- WHEN core evaluation runs
- THEN `7.4.cnv.cpu_virt_flag` status is PASS

#### Scenario: no vmx or svm labels is WARNING
- GIVEN HyperConverged present
- AND nodes present without vmx or svm equal to `true`
- WHEN core evaluation runs
- THEN `7.4.cnv.cpu_virt_flag` status is WARNING

#### Scenario: HyperConverged missing is not applicable
- GIVEN HyperConverged `_hc_not_found`
- WHEN core evaluation runs
- THEN `7.4.cnv.cpu_virt_flag` status is NOT_APPLICABLE

#### Scenario: nodes error is SKIPPED
- GIVEN HyperConverged present
- AND nodes payload `_hc_error`
- WHEN core evaluation runs
- THEN `7.4.cnv.cpu_virt_flag` status is SKIPPED

### Requirement: Node CPU TSR stays on CNV state
KB row `7.4.tsr.4_8_1_3_2_node_cpu` SHALL keep `content_from` exact `7.4.cnv.state`. The row SHALL NOT use `content_from` `7.4.cnv.cpu_virt_flag`.

#### Scenario: node_cpu TSR is not retargeted
- GIVEN production `load_kb()`
- WHEN entry `7.4.tsr.4_8_1_3_2_node_cpu` is loaded
- THEN `content_from` is `7.4.cnv.state`
