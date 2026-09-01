# Health Check Report Engine (`hc-native-virt-p3-remainder` delta)

## ADDED Requirements

### Requirement: Native CDI StorageProfile clone strategy
Core evaluation SHALL emit `7.4.cnv.storageprofile`. Missing StorageProfile payload (`_is_missing`) SHALL be NOT_APPLICABLE. Zero items SHALL be INFO. Any item whose `status.cloneStrategy` equals `copy` SHALL be WARNING. Else the check SHALL PASS. The check SHALL read `status.cloneStrategy` only; `spec.cloneStrategy` and snapshotClass SHALL be evidence only. The check SHALL NOT alias to `7.4.cnv.virt_storageclass`. The check SHALL NOT retune virt-default StorageClass scoring.

#### Scenario: cloneStrategy copy is WARNING
- GIVEN a StorageProfile item whose `status.cloneStrategy` is `copy`
- WHEN core evaluation runs
- THEN `7.4.cnv.storageprofile` status is WARNING

#### Scenario: zero StorageProfile items is INFO
- GIVEN StorageProfile payload present with zero items
- WHEN core evaluation runs
- THEN `7.4.cnv.storageprofile` status is INFO

### Requirement: Native CNV VM-namespace ResourceQuota
Core evaluation SHALL emit `7.4.cnv.vm_quota`. HyperConverged missing SHALL be NOT_APPLICABLE. Zero VirtualMachine items SHALL be NOT_APPLICABLE. VM namespaces SHALL be the unique `metadata.namespace` values on VM items. If any VM namespace has zero ResourceQuota items SHALL be INFO. Else if any ResourceQuota in those namespaces has a key present in both `status.used` and `spec.hard` with equal string values SHALL be WARNING. Else the check SHALL PASS. `spec.hard` and `status.used` that are not dicts SHALL skip that quota for the exhausted check. The check SHALL NEVER FAIL. Missing ResourceQuota in a VM namespace SHALL NOT FAIL. The check SHALL NOT alias to `7.6.rq` or `7.6.cluster_quota`. The check SHALL NOT import or call `_evaluate_resource_quotas`.

#### Scenario: VM namespace without ResourceQuota is INFO
- GIVEN HyperConverged present
- AND at least one VirtualMachine
- AND that VM namespace has zero ResourceQuota items
- WHEN core evaluation runs
- THEN `7.4.cnv.vm_quota` status is INFO

#### Scenario: used equals hard is WARNING
- GIVEN every VM namespace has at least one ResourceQuota
- AND a ResourceQuota in a VM namespace has a shared key whose `status.used` string equals `spec.hard` string
- WHEN core evaluation runs
- THEN `7.4.cnv.vm_quota` status is WARNING

### Requirement: Sparse TSR aliases for StorageProfile and VM quota
KB row `7.4.tsr.4_8_3_1_1_storage_profiles` SHALL be a sparse alias (`content_from` exact `7.4.cnv.storageprofile`, `include_in_findings = false`). KB row `7.4.tsr.4_8_5_1_1_quota_and_resources` SHALL be a sparse alias (`content_from` exact `7.4.cnv.vm_quota`, `include_in_findings = false`). Alias rows SHALL NOT overlay inherited narrative keys. `7.4.tsr.4_8_5_1_1_quota_and_resources` SHALL NOT have `content_from` equal to `7.6.rq`. `7.4.tsr.4_8_3_1_1_storage_profiles` SHALL NOT have `content_from` equal to `7.4.cnv.virt_storageclass`.

#### Scenario: storage profiles TSR aliases the native
- GIVEN production `load_kb()`
- WHEN entry `7.4.tsr.4_8_3_1_1_storage_profiles` is loaded
- THEN `content_from` is `7.4.cnv.storageprofile`
- AND `include_in_findings` is false

#### Scenario: quota TSR aliases vm_quota not 7.6.rq
- GIVEN production `load_kb()`
- WHEN entry `7.4.tsr.4_8_5_1_1_quota_and_resources` is loaded
- THEN `content_from` is `7.4.cnv.vm_quota`
- AND `content_from` is not `7.6.rq`
- AND `include_in_findings` is false

### Requirement: Collect MAY write StorageProfile
Live and supportshell collect MAY write `storageprofile` under `05_components` using `oc get storageprofile || true`. Collect SHALL NOT add a new ResourceQuota capture for this native.

#### Scenario: collect name for StorageProfile
- GIVEN live `05_components.sh`
- WHEN an operator inspects capture stems
- THEN `storageprofile` is present as a capture name
