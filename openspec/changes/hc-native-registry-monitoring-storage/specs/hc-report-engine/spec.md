# Health Check Report Engine (`hc-native-registry-monitoring-storage` delta)

## ADDED Requirements

### Requirement: Native registry storage scoring
Core evaluation SHALL emit `7.3.registry.storage`. The check SHALL FAIL when `spec.managementState` is Managed or Unmanaged and the storage backend (first `spec.storage` key other than `managementState`) is `emptyDir`. The check SHALL PASS when that backend is object storage (`s3`, `azure`, `gcs`, `ibmcos`, `oss`, `swift`) or `pvc`. The check SHALL be INFO when the registry payload is missing or has `_hc_error`, or when `managementState` is Removed. An unknown remaining storage key SHALL be WARNING, not FAIL. `scoring_basis` SHALL be `doc_backed` on emptyDir FAIL only. `7.3.registry.state` SHALL remain independently scored. Registry PVC access mode and file provisioner SHALL NOT be scored.

#### Scenario: emptyDir under Managed fails
- GIVEN Image Registry Operator `managementState` is Managed
- AND `spec.storage.emptyDir` is the storage backend
- WHEN core evaluation runs
- THEN `7.3.registry.storage` status is FAIL
- AND `scoring_basis` is `doc_backed`

#### Scenario: Removed is informational
- GIVEN Image Registry Operator `managementState` is Removed
- WHEN core evaluation runs
- THEN `7.3.registry.storage` status is INFO

#### Scenario: object or PVC backend passes
- GIVEN `managementState` is Managed
- AND the storage backend is `s3` or `pvc`
- WHEN core evaluation runs
- THEN `7.3.registry.storage` status is PASS

#### Scenario: unknown storage key is warning
- GIVEN `managementState` is Managed
- AND the remaining storage key is neither emptyDir, pvc, nor a listed object backend
- WHEN core evaluation runs
- THEN `7.3.registry.storage` status is WARNING
- AND the status is not FAIL

#### Scenario: registry.state stays independent
- GIVEN a scored registry payload
- WHEN core evaluation runs
- THEN `7.3.registry.state` is still emitted
- AND `7.3.registry.storage` does not replace its scoring

### Requirement: Native monitoring storage scoring
Core evaluation SHALL emit `7.3.monitoring.storage`. The check SHALL FAIL when any Prometheus or Alertmanager item lacks `spec.storage.volumeClaimTemplate`. The check SHALL WARNING when a template is present and any access mode is `ReadWriteMany` or the resolved StorageClass provisioner contains `nfs`, `efs`, `azurefile`, or `cephfs`. The check SHALL PASS when every item has a template and RWO (or empty class name equal to the default StorageClass) on a non-file provisioner. Empty class name with a template and no default StorageClass SHALL PASS on access mode only. The check SHALL be INFO when Prometheus and Alertmanager payloads are both missing. FAIL SHALL win over WARNING. `scoring_basis` SHALL be `doc_backed` on missing-template FAIL only. `7.3.monitoring.config` SHALL remain independently scored.

#### Scenario: missing volumeClaimTemplate fails
- GIVEN a Prometheus or Alertmanager item with no `spec.storage.volumeClaimTemplate`
- WHEN core evaluation runs
- THEN `7.3.monitoring.storage` status is FAIL
- AND `scoring_basis` is `doc_backed`

#### Scenario: ReadWriteMany warns
- GIVEN every scored item has a volumeClaimTemplate
- AND at least one access mode is `ReadWriteMany`
- WHEN core evaluation runs
- THEN `7.3.monitoring.storage` status is WARNING

#### Scenario: RWO block passes
- GIVEN every scored item has a volumeClaimTemplate
- AND access modes are not `ReadWriteMany`
- AND the resolved provisioner is not file (`nfs` / `efs` / `azurefile` / `cephfs`)
- WHEN core evaluation runs
- THEN `7.3.monitoring.storage` status is PASS

#### Scenario: both monitoring payloads missing is informational
- GIVEN Prometheus and Alertmanager payloads are missing or `_hc_error`
- WHEN core evaluation runs
- THEN `7.3.monitoring.storage` status is INFO

#### Scenario: monitoring.config stays independent
- GIVEN a scored cluster-monitoring-config ConfigMap
- WHEN core evaluation runs
- THEN `7.3.monitoring.config` is still emitted
- AND `7.3.monitoring.storage` does not replace its scoring

### Requirement: Sparse TSR aliases for ORIG storage stories
KB rows `7.3.tsr.3_6_2_registry_storage_type` and `7.3.tsr.3_7_2_monitoring_storage_type` SHALL be sparse aliases (`content_from` to the matching native, `include_in_findings = false`). Alias targets SHALL be `7.3.registry.storage` and `7.3.monitoring.storage` respectively. Alias rows SHALL NOT overlay inherited narrative keys. `7.3.tsr.3_6_2_registry_storage_type` SHALL NOT point at `7.3.tsr.3_6_1_registry_scaled`.

#### Scenario: registry storage TSR id is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.3.tsr.3_6_2_registry_storage_type` is loaded
- THEN `content_from` is `7.3.registry.storage`
- AND `include_in_findings` is false

#### Scenario: monitoring storage TSR id is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.3.tsr.3_7_2_monitoring_storage_type` is loaded
- THEN `content_from` is `7.3.monitoring.storage`
- AND `include_in_findings` is false

### Requirement: No new collect files for registry or monitoring storage
Collect SHALL NOT add new files for `7.3.registry.storage` or `7.3.monitoring.storage`. Scoring SHALL use existing `05_components` `imageregistry`, `prometheus`, `alertmanager`, and `storageclass` artifacts.

#### Scenario: collect files unchanged for these checks
- GIVEN live `05_components.sh`
- WHEN an operator runs collect
- THEN no additional gather is required to score registry or monitoring storage
