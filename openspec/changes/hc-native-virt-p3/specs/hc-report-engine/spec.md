# Health Check Report Engine (`hc-native-virt-p3` delta)

## ADDED Requirements

### Requirement: Native CNV related subscriptions
Core evaluation SHALL emit `7.4.cnv.subscription`. The check SHALL be NOT_APPLICABLE when HyperConverged is missing. Else the check SHALL FAIL when no subscription in namespace `openshift-cnv` has `metadata.name` or `spec.name` equal to `kubevirt-hyperconverged` with `status.state` `AtLatestKnown` and `status.installedCSV` equal to `status.currentCSV`. Else the check SHALL PASS. The check SHALL NOT dump onto `7.4.cnv.state`.

#### Scenario: stalled subscription fails
- GIVEN HyperConverged present
- AND a kubevirt-hyperconverged subscription in `openshift-cnv` whose state is not `AtLatestKnown`
- WHEN core evaluation runs
- THEN `7.4.cnv.subscription` status is FAIL

#### Scenario: HyperConverged missing is not applicable
- GIVEN HyperConverged `_hc_not_found`
- WHEN core evaluation runs
- THEN `7.4.cnv.subscription` status is NOT_APPLICABLE

### Requirement: Native optional NMState and SR-IOV CSV
Core evaluation SHALL emit `7.4.cnv.nmstate_csv` and `7.4.cnv.sriov_csv`. Zero CSV items in `openshift-nmstate` or `openshift-sriov-network-operator` respectively SHALL be NOT_APPLICABLE. Any CSV in that namespace whose `status.phase` is not `Succeeded` SHALL FAIL. Else the check SHALL PASS. Missing operator SHALL NOT FAIL. The check SHALL NOT score NNCE or SriovNetworkNodePolicy.

#### Scenario: empty NMState namespace is not applicable
- GIVEN no CSV items in namespace `openshift-nmstate`
- WHEN core evaluation runs
- THEN `7.4.cnv.nmstate_csv` status is NOT_APPLICABLE

#### Scenario: failed SR-IOV CSV fails
- GIVEN a CSV in `openshift-sriov-network-operator` with phase `Failed`
- WHEN core evaluation runs
- THEN `7.4.cnv.sriov_csv` status is FAIL

### Requirement: Native VM runStrategy
Core evaluation SHALL emit `7.4.cnv.run_strategy`. HyperConverged missing or VM payload missing SHALL be SKIPPED. Zero VM items SHALL be NOT_APPLICABLE. Any VM whose `spec.runStrategy` is not exactly `Always` SHALL be INFO. All `Always` SHALL PASS. The check SHALL NEVER FAIL.

#### Scenario: Manual runStrategy is INFO
- GIVEN HyperConverged present
- AND a VM whose `spec.runStrategy` is not `Always`
- WHEN core evaluation runs
- THEN `7.4.cnv.run_strategy` status is INFO

### Requirement: Native VMI phase without PromQL
Core evaluation SHALL emit `7.4.cnv.vmi_phase` from `cnv_vmi` `.status.phase`. Missing VMI payload SHALL be SKIPPED. Zero items SHALL be NOT_APPLICABLE. Any phase in Pending, Scheduling, Failed, or Unknown SHALL be WARNING. Else PASS. The check SHALL NOT use PromQL.

#### Scenario: Failed VMI is WARNING
- GIVEN a VMI with phase `Failed`
- WHEN core evaluation runs
- THEN `7.4.cnv.vmi_phase` status is WARNING

### Requirement: Native live-migration network
Core evaluation SHALL emit `7.4.cnv.migration_network`. HyperConverged missing SHALL be NOT_APPLICABLE. Missing, empty, or `<none>` `spec.liveMigrationConfig.network` SHALL PASS. A named network SHALL FAIL unless some NetworkAttachmentDefinition has `metadata.name` equal to that string and `metadata.namespace` equal to `openshift-cnv`. The check SHALL NOT alias to `7.4.cnv.live_migratable`.

#### Scenario: named network without NAD fails
- GIVEN HyperConverged with a named live-migration network
- AND no matching NAD in `openshift-cnv`
- WHEN core evaluation runs
- THEN `7.4.cnv.migration_network` status is FAIL

### Requirement: Native Linux-bridge NAD inventory
Core evaluation SHALL emit `7.4.cnv.linux_bridge`. Missing NAD payload SHALL be SKIPPED. Zero items whose CNI `type` is `cnv-bridge` or `bridge` SHALL be INFO. Else PASS. Invalid `spec.config` JSON SHALL skip that item and SHALL NOT FAIL. Empty NAD lists SHALL NOT FAIL. The check SHALL NOT dump onto `7.4.cnv.nncp`.

#### Scenario: no bridge-type NAD is INFO
- GIVEN NAD payload present with no `cnv-bridge` or `bridge` CNI type
- WHEN core evaluation runs
- THEN `7.4.cnv.linux_bridge` status is INFO

### Requirement: Native CNV node placement
Core evaluation SHALL emit `7.4.cnv.node_placement`. HyperConverged missing SHALL be NOT_APPLICABLE. virt-handler DaemonSet missing SHALL be SKIPPED. `status.numberReady` not equal to `status.desiredNumberScheduled` SHALL FAIL. Else WARNING if any non-control-plane node lacks label `kubevirt.io/schedulable` equal to `"true"`. Control-plane is `node-role.kubernetes.io/control-plane` or `node-role.kubernetes.io/master` present. Zero non-control-plane nodes SHALL PASS after a ready DaemonSet. Empty HyperConverged `nodePlacement` SHALL NOT FAIL. The check SHALL NOT score CPU `vmx`/`svm` labels.

#### Scenario: handler not ready fails
- GIVEN HyperConverged present
- AND virt-handler `numberReady` not equal to `desiredNumberScheduled`
- WHEN core evaluation runs
- THEN `7.4.cnv.node_placement` status is FAIL

#### Scenario: unschedulable worker is WARNING
- GIVEN virt-handler ready equals desired
- AND a non-control-plane node without `kubevirt.io/schedulable` equal to `"true"`
- WHEN core evaluation runs
- THEN `7.4.cnv.node_placement` status is WARNING

### Requirement: Native CDI image upload
Core evaluation SHALL emit `7.4.cnv.cdi`. Missing CDI SHALL be NOT_APPLICABLE. Conditions not (`Available=True` and `Progressing=False` and `Degraded=False`) SHALL FAIL. Else WARNING if no `cnv_pods` item with label `app=cdi-uploadproxy` or any such pod is not Ready. Else PASS. The check SHALL NOT dump onto `7.4.cnv.pods`.

#### Scenario: missing CDI is not applicable
- GIVEN CDI `_hc_not_found`
- WHEN core evaluation runs
- THEN `7.4.cnv.cdi` status is NOT_APPLICABLE

#### Scenario: degraded CDI fails
- GIVEN CDI `Degraded=True`
- WHEN core evaluation runs
- THEN `7.4.cnv.cdi` status is FAIL

### Requirement: Sparse TSR aliases for virt P3 and parked rows
KB rows SHALL sparse-alias (`include_in_findings = false`): `7.4.tsr.4_8_1_1_2_related_subscriptions` → `7.4.cnv.subscription`; `7.4.tsr.4_8_1_5_1_1_cnv_operators_node_placement` → `7.4.cnv.node_placement`; `7.4.tsr.4_8_1_5_1_5_vm_run_strategy_and_availability` → `7.4.cnv.run_strategy`; `7.4.tsr.4_8_2_1_1_3_live_migration_network_readiness` → `7.4.cnv.migration_network`; `7.4.tsr.4_8_3_2_1_nmstate_operator` → `7.4.cnv.nmstate_csv`; `7.4.tsr.4_8_3_2_2_sr_iov_operator` → `7.4.cnv.sriov_csv`; `7.4.tsr.4_8_3_2_3_linux_bridge_network` → `7.4.cnv.linux_bridge`; `7.4.tsr.4_8_5_2_3_cnv_vmi_readiness_prometheus` → `7.4.cnv.vmi_phase`; `7.4.tsr.4_8_5_3_5_cdi_image_upload_posture` → `7.4.cnv.cdi`. Alias rows SHALL NOT overlay inherited narrative keys. `7.4.tsr.4_8_3_1_1_storage_profiles` and `7.4.tsr.4_8_5_1_1_quota_and_resources` SHALL NOT have `content_from`. IN leaves SHALL NOT alias to `7.4.cnv.state`, `7.4.cnv.nncp`, `7.4.cnv.live_migratable`, or `7.4.cnv.pods`.

#### Scenario: related subscriptions TSR is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.4.tsr.4_8_1_1_2_related_subscriptions` is loaded
- THEN `content_from` is `7.4.cnv.subscription`
- AND `include_in_findings` is false

#### Scenario: StorageProfile and quota stay canonical
- GIVEN production `load_kb()`
- WHEN entries `7.4.tsr.4_8_3_1_1_storage_profiles` and `7.4.tsr.4_8_5_1_1_quota_and_resources` are loaded
- THEN `content_from` is empty
