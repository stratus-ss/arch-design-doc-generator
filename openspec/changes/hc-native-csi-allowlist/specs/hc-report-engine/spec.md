# Health Check Report Engine (`hc-native-csi-allowlist` delta)

## ADDED Requirements

### Requirement: Native CSI CSO allow-list scoring
Core evaluation SHALL emit `7.3.storage.csi_cso` with title `CSI driver CSO allow-list`. `_hc_error` on CSIDriver or CRDs SHALL be SKIPPED. Missing CSIDriver list SHALL be NOT_APPLICABLE. Zero CSIDriver items SHALL be WARNING. CSO enum SHALL be extracted from CRD `clustercsidrivers.operator.openshift.io` by walking dict and list nodes and collecting `enum` lists that contain `ebs.csi.aws.com`. Empty enum SHALL be SKIPPED. A CSIDriver name SHALL be allowed when it is in that enum, starts with `openshift-storage.`, or equals `lvm.csi.topolvm.io`, `topolvm.io`, or `kubevirt.io.hostpath-provisioner`. Any other name SHALL be third-party. Any third-party SHALL be WARNING. All allowed SHALL be PASS. Third-party SHALL NOT be FAIL. `7.3.storage.csi` inventory bars SHALL not change in this change.

#### Scenario: nfs outside enum is WARNING
- GIVEN CSIDriver items include `nfs.csi.k8s.io`
- AND the ClusterCSIDriver enum includes `ebs.csi.aws.com` and does not include `nfs.csi.k8s.io`
- WHEN core evaluation runs
- THEN `7.3.storage.csi_cso` status is WARNING
- AND the status is not FAIL

#### Scenario: all names in enum is PASS
- GIVEN every CSIDriver name is in the ClusterCSIDriver enum
- WHEN core evaluation runs
- THEN `7.3.storage.csi_cso` status is PASS

#### Scenario: empty enum is SKIPPED
- GIVEN CSIDriver items are present
- AND no enum list containing `ebs.csi.aws.com` is found
- WHEN core evaluation runs
- THEN `7.3.storage.csi_cso` status is SKIPPED

#### Scenario: inventory CSI stays independent
- GIVEN a scored CSIDriver payload
- WHEN core evaluation runs
- THEN `7.3.storage.csi` is still emitted
- AND `7.3.storage.csi_cso` does not replace its scoring

### Requirement: Sparse TSR alias for CSI drivers
KB row `7.3.tsr.3_9_5_csi_drivers` SHALL be a sparse alias (`content_from` exact `7.3.storage.csi_cso`, `include_in_findings = false`). It SHALL NOT target `7.3.storage.csi`. Alias rows SHALL NOT overlay inherited narrative keys.

#### Scenario: CSI TSR aliases 7.3.storage.csi_cso
- GIVEN production `load_kb()`
- WHEN entry `7.3.tsr.3_9_5_csi_drivers` is loaded
- THEN `content_from` is `7.3.storage.csi_cso`
- AND `include_in_findings` is false

## MODIFIED Requirements

### Requirement: CSI TSR stays canonical
This requirement is replaced by sparse alias onto `7.3.storage.csi_cso`. Platform-operator TSR SHALL NOT alias `7.5.operator_state`.

#### Scenario: CSI TSR is not an alias
This scenario is withdrawn. CSI TSR SHALL alias `7.3.storage.csi_cso` and SHALL NOT alias `7.3.storage.csi`.
