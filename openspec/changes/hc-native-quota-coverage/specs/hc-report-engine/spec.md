# Health Check Report Engine (`hc-native-quota-coverage` delta)

## ADDED Requirements

### Requirement: Native user-project quota coverage scoring
Core evaluation SHALL emit `7.6.quota.coverage` with title `User project quota coverage`. Missing namespace, ResourceQuota, or LimitRange payload SHALL be SKIPPED. A namespace SHALL be a user namespace when its name does not start with `openshift-` or `kube-` and is not `default` or `openshift`. A user namespace SHALL be covered when it has at least one ResourceQuota or at least one LimitRange. Zero user namespaces SHALL be NOT_APPLICABLE. Any uncovered user namespace SHALL be FAIL. All user namespaces covered SHALL be PASS. Platform namespaces SHALL NOT FAIL this check. The project-request template SHALL NOT be scored. `7.6.rq` bars SHALL not change in this change.

#### Scenario: uncovered user namespace fails
- GIVEN a user namespace with no ResourceQuota and no LimitRange
- WHEN core evaluation runs
- THEN `7.6.quota.coverage` status is FAIL

#### Scenario: ResourceQuota covers the user namespace
- GIVEN a user namespace with at least one ResourceQuota
- AND no LimitRange in that namespace
- WHEN core evaluation runs
- THEN `7.6.quota.coverage` status is PASS

#### Scenario: openshift namespace is not scored
- GIVEN only platform namespaces (`openshift-*`, `kube-*`, `default`, `openshift`) lack quotas
- AND every user namespace is covered
- WHEN core evaluation runs
- THEN `7.6.quota.coverage` status is PASS

### Requirement: Sparse TSR alias for quota coverage
KB row `7.6.tsr.6_1_1_1_quota_resources_project_assignment` SHALL be a sparse alias (`content_from` exact `7.6.quota.coverage`, `include_in_findings = false`). It SHALL NOT target `7.6.rq` or `7.6.cluster_quota`. Rows `7.6.tsr.6_1_1_quota_and_resources` and `7.6.tsr.6_1_1_2_cluster_quota_configuration` SHALL set `content_from` exact `7.6.quota.coverage`. Alias rows SHALL NOT overlay inherited narrative keys. There SHALL be no `content_from` chain through `7.6.tsr.6_1_1_1_quota_resources_project_assignment`.

#### Scenario: quota TSR aliases 7.6.quota.coverage
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_1_1_1_quota_resources_project_assignment` is loaded
- THEN `content_from` is `7.6.quota.coverage`
- AND `include_in_findings` is false

#### Scenario: parent hops retarget the native
- GIVEN production `load_kb()`
- WHEN entries `7.6.tsr.6_1_1_quota_and_resources` and `7.6.tsr.6_1_1_2_cluster_quota_configuration` are loaded
- THEN each `content_from` is `7.6.quota.coverage`

## MODIFIED Requirements

### Requirement: Wrong-story TSR rows stay canonical
This requirement is replaced for the quota leaf. `7.6.tsr.6_1_1_1_quota_resources_project_assignment` SHALL alias `7.6.quota.coverage`. `7.6.tsr.6_1_2_requests_and_limits`, `7.6.tsr.6_1_5_3_network_policy_pruning`, and `7.6.tsr.6_2_3_images_patch_management` SHALL remain without `content_from` in this change.

#### Scenario: quota leaf is not an alias
This scenario is withdrawn. Quota TSR SHALL alias `7.6.quota.coverage` and SHALL NOT alias `7.6.rq`.
