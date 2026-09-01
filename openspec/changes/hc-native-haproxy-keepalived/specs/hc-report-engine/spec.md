# Health Check Report Engine (`hc-native-haproxy-keepalived` delta)

## ADDED Requirements

### Requirement: Native keepalived VIP pod scoring
Core evaluation SHALL emit `7.2.topo.keepalived` with title `Keepalived VIP pods`. The engine SHALL read `results["07_cluster_health"]["pods_all"]`. A keepalived pod SHALL be a pod whose namespace is `openshift-kni-infra` and whose `metadata.name` starts with `keepalived-`. Missing or `_hc_error` `pods_all` SHALL be SKIPPED. Zero matching pods SHALL be INFO. Any matching pod whose `status.phase` is not `Running` or whose `containerStatuses` are missing or not all `ready` true SHALL be FAIL. Else PASS. The engine SHALL NOT scrape VRRP config. The engine SHALL NOT retune `7.2.topo.haproxy_ha`.

#### Scenario: Ready keepalived pods are PASS
- GIVEN `pods_all` contains keepalived pods in `openshift-kni-infra`
- AND every matching pod phase is Running
- AND every matching pod container is Ready
- WHEN core evaluation runs
- THEN `7.2.topo.keepalived` status is PASS

#### Scenario: not Ready keepalived is FAIL
- GIVEN a keepalived pod in `openshift-kni-infra` whose phase is not Running or whose containers are not all Ready
- WHEN core evaluation runs
- THEN `7.2.topo.keepalived` status is FAIL

#### Scenario: zero keepalived pods is INFO
- GIVEN `pods_all` is present and not `_hc_error`
- AND no pod matches namespace `openshift-kni-infra` with name prefix `keepalived-`
- WHEN core evaluation runs
- THEN `7.2.topo.keepalived` status is INFO
- AND the status is not FAIL

### Requirement: HAProxy TSR stays on replica native
KB row `7.2.tsr.2_2_3_haproxy_ha` SHALL keep `content_from` exact `7.2.topo.haproxy_ha`. The row SHALL NOT use `content_from` `7.2.topo.keepalived`.

#### Scenario: HAProxy TSR is not retargeted
- GIVEN production `load_kb()`
- WHEN entry `7.2.tsr.2_2_3_haproxy_ha` is loaded
- THEN `content_from` is `7.2.topo.haproxy_ha`

## MODIFIED Requirements

None. Ingress replica scoring is unchanged.
