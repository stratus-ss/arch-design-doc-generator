# Health Check Report Engine (`hc-native-pod-requests` delta)

## ADDED Requirements

### Requirement: Native user-pod request scoring
Core evaluation SHALL emit `7.6.pod.requests` with title `Pod CPU and memory requests`. `_hc_error` on `pods_all` SHALL be SKIPPED. Missing payload, `_hc_not_found`, or zero items SHALL be NOT_APPLICABLE. Platform namespaces (`openshift-*`, `kube-*`, `default`, `openshift`) SHALL not be scored. Succeeded and Failed pods SHALL not be scored. Only `spec.containers` SHALL be inspected. A pod SHALL be missing requests when any container lacks `resources.requests.cpu` or `resources.requests.memory` (empty string counts as missing). Any such user active pod SHALL be WARNING. Else PASS. The check SHALL NOT FAIL. `7.6.limitranges` and `7.6.req_limits` bars SHALL not change in this change.

#### Scenario: missing CPU request is WARNING
- GIVEN a user-namespace Running pod whose container has memory requests and no CPU requests
- WHEN core evaluation runs
- THEN `7.6.pod.requests` status is WARNING
- AND the status is not FAIL

#### Scenario: both CPU and memory requests PASS
- GIVEN every user active pod container has both CPU and memory requests
- WHEN core evaluation runs
- THEN `7.6.pod.requests` status is PASS

#### Scenario: openshift BestEffort is ignored
- GIVEN only platform-namespace pods lack requests
- AND every user active pod has both requests
- WHEN core evaluation runs
- THEN `7.6.pod.requests` status is PASS

### Requirement: Sparse TSR alias for pod requests
KB row `7.6.tsr.6_1_2_requests_and_limits` SHALL be a sparse alias (`content_from` exact `7.6.pod.requests`, `include_in_findings = false`). It SHALL NOT target `7.6.limitranges` or `7.6.req_limits`. Alias rows SHALL NOT overlay inherited narrative keys.

#### Scenario: requests TSR aliases 7.6.pod.requests
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_1_2_requests_and_limits` is loaded
- THEN `content_from` is `7.6.pod.requests`
- AND `include_in_findings` is false

## MODIFIED Requirements

### Requirement: Wrong-story TSR rows stay canonical
This requirement is replaced for the requests leaf. `7.6.tsr.6_1_2_requests_and_limits` SHALL alias `7.6.pod.requests`. Remaining wrong-story IDs not owned by this change SHALL follow their own change.

#### Scenario: requests TSR is not an alias
This scenario is withdrawn. Requests TSR SHALL alias `7.6.pod.requests` and SHALL NOT alias LimitRange inventory.
