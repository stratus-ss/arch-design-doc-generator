# Health Check Report Engine (`hc-live-parity-evaluate` delta)

## ADDED Requirements

### Requirement: Optional product CRs score NOT_APPLICABLE when absent
Native evaluation of optional product CRs SHALL treat `_hc_not_found` or empty `items` as NOT_APPLICABLE, not FAIL. This applies to ODF StorageCluster (`7.4.odf.state`), RHOSO OpenStackControlPlane (`7.4.rhoso.state`), LocalVolume (`7.3.storage.localvolume`), FileIntegrity (`7.7.file_integrity`), and MetalLB when the operator is not installed.

#### Scenario: ODF StorageCluster not found
- GIVEN `06_layered/odf_storagecluster.json` is `_hc_not_found` or has empty items
- WHEN core evaluation runs
- THEN `7.4.odf.state` status is NOT_APPLICABLE

#### Scenario: RHOSO control plane not found
- GIVEN `06_layered/rhoso_controlplane.json` is `_hc_not_found`
- WHEN core evaluation runs
- THEN `7.4.rhoso.state` status is NOT_APPLICABLE

#### Scenario: LocalVolume not found
- GIVEN `05_components/localvolume.json` is `_hc_not_found` or has empty items
- WHEN core evaluation runs
- THEN `7.3.storage.localvolume` status is NOT_APPLICABLE

#### Scenario: FileIntegrity not found
- GIVEN `09_security/fileintegrity.json` is `_hc_not_found` or has empty items
- WHEN core evaluation runs
- THEN `7.7.file_integrity` status is NOT_APPLICABLE

### Requirement: FeatureGate native scoring from collected CR
When FeatureGate is collected, native `7.3.net.featuregates` SHALL score `spec.featureSet`. Empty or `Default` SHALL be PASS. `TechPreviewNoUpgrade` or `CustomNoUpgrade` SHALL be FAIL with `scoring_basis=doc_backed`. Missing capture SHALL remain SKIPPED. Clusteroperators SHALL not be used as a TechPreview detector. There SHALL NOT be a second FeatureGate check_id.

#### Scenario: FeatureGate not collected
- GIVEN FeatureGate is not in the collection
- WHEN the check runs
- THEN status is SKIPPED

#### Scenario: FeatureGate Default or empty
- GIVEN FeatureGate `spec.featureSet` is empty or `Default`
- WHEN the check runs
- THEN status is PASS

#### Scenario: FeatureGate TechPreviewNoUpgrade
- GIVEN FeatureGate `spec.featureSet` is `TechPreviewNoUpgrade`
- WHEN the check runs
- THEN status is FAIL
- AND `scoring_basis` is `doc_backed`

### Requirement: PDB empty list is INFO
Native `7.5.pdb` SHALL be SKIPPED when the PDB capture envelope is missing. An empty items list SHALL be INFO, not FAIL. A PDB with `status.disruptionsAllowed==0` and `currentHealthy < desiredHealthy` SHALL be WARNING; otherwise PASS. There SHALL NOT be a second PDB check_id.

#### Scenario: PDB list empty
- GIVEN `07_cluster_health/pdb.json` has `items` equal to `[]`
- WHEN the check runs
- THEN status is INFO

#### Scenario: PDB envelope missing
- GIVEN PDB is not in the collection
- WHEN the check runs
- THEN status is SKIPPED

### Requirement: Core profile emits mapped CCX CVE IDs
Core evaluation SHALL emit the mapped CVE/external CCX check IDs. When `12_ccx/ccx_rules.json` has no matching title or id, status SHALL be SKIPPED. When a payload row matches, status SHALL come from that row. `source` SHALL be `ccx`. There SHALL NOT be a second check_id for DNS pods, IPsec, or FeatureGate.

#### Scenario: CCX CVE without Insights payload
- GIVEN no matching row in `12_ccx/ccx_rules.json`
- WHEN core evaluation runs
- THEN each mapped CVE/external ID is emitted
- AND status is SKIPPED
- AND `source` is `ccx`

#### Scenario: CCX CVE with payload status
- GIVEN a `12_ccx/ccx_rules.json` row whose title or id matches a mapped CVE ID
- WHEN core evaluation runs
- THEN that check uses the runtime status from the payload
- AND `source` is `ccx`
