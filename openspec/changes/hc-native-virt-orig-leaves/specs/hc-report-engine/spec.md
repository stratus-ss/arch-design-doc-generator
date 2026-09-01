# Health Check Report Engine (`hc-native-virt-orig-leaves` delta)

## ADDED Requirements

### Requirement: Native CNV NNCP and NNCE health
Core evaluation SHALL emit `7.4.cnv.nncp`. The check SHALL be NOT_APPLICABLE when both NNCP and NNCE payloads are missing. Else the check SHALL be INFO when both item lists are empty. The check SHALL FAIL when any NNCP or NNCE item is not healthy. An item SHALL be healthy when `_find_condition` on `status.conditions` has `Available` status `True` or `SuccessfullyConfigured` status `True`. Else the check SHALL PASS when at least one item exists and every item is healthy. `scoring_basis` SHALL be `doc_backed` on NNCP FAIL. The check SHALL NOT score NAD count. The check SHALL NOT gate on CNV presence. `7.3.net.hwnet` SHALL remain independently scored.

#### Scenario: both payloads missing is not applicable
- GIVEN NNCP and NNCE payloads that `_is_missing` treats as missing
- WHEN core evaluation runs
- THEN `7.4.cnv.nncp` status is NOT_APPLICABLE

#### Scenario: zero policies is INFO
- GIVEN NNCP and NNCE payloads present with empty `items` lists
- WHEN core evaluation runs
- THEN `7.4.cnv.nncp` status is INFO

#### Scenario: degraded enactment fails
- GIVEN at least one NNCE item whose `Available` condition is not True and `SuccessfullyConfigured` is not True
- WHEN core evaluation runs
- THEN `7.4.cnv.nncp` status is FAIL
- AND `scoring_basis` is `doc_backed`

#### Scenario: all items healthy pass
- GIVEN at least one NNCP or NNCE item
- AND every item has `Available` True or `SuccessfullyConfigured` True
- WHEN core evaluation runs
- THEN `7.4.cnv.nncp` status is PASS

### Requirement: Native virt-default StorageClass
Core evaluation SHALL emit `7.4.cnv.virt_storageclass`. The native identifier SHALL NOT contain `node_disk`. TSR check_id `7.4.tsr.4_8_1_3_4_node_disk` MAY remain as an alias source. The check SHALL be NOT_APPLICABLE when HyperConverged is missing. The check SHALL be SKIPPED when CNV is present and the StorageClass payload is missing. Else the check SHALL PASS when exactly one StorageClass has annotation `storageclass.kubevirt.io/is-default-virt-class` equal to `"true"`. Else the check SHALL FAIL. VolumeSnapshotClass MAY appear in evidence and SHALL NOT change PASS/FAIL. The check SHALL NOT use cluster annotation `is-default-class`. `scoring_basis` SHALL be `doc_backed` on virt-default FAIL. `7.3.storage.default_sc` SHALL remain independently scored.

#### Scenario: CNV missing is not applicable
- GIVEN HyperConverged `_hc_not_found` or `_is_missing`
- WHEN core evaluation runs
- THEN `7.4.cnv.virt_storageclass` status is NOT_APPLICABLE

#### Scenario: CNV present and zero virt-default fails
- GIVEN HyperConverged present
- AND zero StorageClasses with virt-default annotation `"true"`
- WHEN core evaluation runs
- THEN `7.4.cnv.virt_storageclass` status is FAIL
- AND `scoring_basis` is `doc_backed`

#### Scenario: exactly one virt-default passes
- GIVEN HyperConverged present
- AND exactly one StorageClass with annotation `storageclass.kubevirt.io/is-default-virt-class` equal to `"true"`
- WHEN core evaluation runs
- THEN `7.4.cnv.virt_storageclass` status is PASS

### Requirement: Native OADP CSV DPA BSL state
Core evaluation SHALL emit `7.4.oadp.state`. The check SHALL be NOT_APPLICABLE when there are no CSV items, no DPA items, and no BackupStorageLocation items. The check SHALL FAIL when any CSV item in namespace `openshift-adp` has `status.phase` not equal to `Succeeded`, or any DPA is not Available (`Available=True`), or any BackupStorageLocation has `status.phase` not equal to `Available`. Else the check SHALL PASS. Absence SHALL NOT FAIL. Inventory check `7.4.OADP` SHALL remain independently scored.

#### Scenario: no OADP resources is not applicable
- GIVEN DPA, CSV, and BackupStorageLocation payloads with no items
- WHEN core evaluation runs
- THEN `7.4.oadp.state` status is NOT_APPLICABLE

#### Scenario: CSV not Succeeded fails
- GIVEN a CSV item in `openshift-adp` with `status.phase` equal to `Failed`
- WHEN core evaluation runs
- THEN `7.4.oadp.state` status is FAIL

#### Scenario: DPA and BSL healthy pass
- GIVEN at least one CSV, DPA, or BackupStorageLocation item
- AND every `openshift-adp` CSV phase is Succeeded
- AND every DPA is Available
- AND every BackupStorageLocation phase is Available
- WHEN core evaluation runs
- THEN `7.4.oadp.state` status is PASS

### Requirement: Sparse TSR aliases for ORIG virt leaves
KB rows `7.4.tsr.4_8_2_2_1_2_network_configuration`, `7.4.tsr.4_8_1_3_4_node_disk`, and `7.4.tsr.4_8_5_3_1_oadp_operator` SHALL be sparse aliases (`content_from` to the matching native, `include_in_findings = false`). Alias targets SHALL be `7.4.cnv.nncp`, `7.4.cnv.virt_storageclass`, and `7.4.oadp.state` respectively. Alias rows SHALL NOT overlay inherited narrative keys. `7.4.tsr.4_8_1_4_node_disk` SHALL remain `content_from` exact `7.4.cnv.state`.

#### Scenario: virt-default TSR id is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.4.tsr.4_8_1_3_4_node_disk` is loaded
- THEN `content_from` is `7.4.cnv.virt_storageclass`
- AND `include_in_findings` is false

#### Scenario: parent node_disk section stays on cnv.state
- GIVEN production `load_kb()`
- WHEN entry `7.4.tsr.4_8_1_4_node_disk` is loaded
- THEN `content_from` is `7.4.cnv.state`

### Requirement: Collect MAY write virt leaf evidence
Live and supportshell collect MAY write `nnce` and `volumesnapshotclass` under `05_components`. Live and supportshell collect MAY write `oadp_dpa`, `oadp_csv`, and `backupstoragelocation` under `06_layered`.

#### Scenario: collect names for virt leaves
- GIVEN live `05_components.sh` and `06_layered.sh`
- WHEN an operator inspects capture stems
- THEN `nnce`, `volumesnapshotclass`, `oadp_dpa`, `oadp_csv`, and `backupstoragelocation` are present as capture names
