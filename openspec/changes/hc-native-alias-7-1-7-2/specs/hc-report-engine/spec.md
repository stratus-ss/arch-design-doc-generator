# Health Check Report Engine (`hc-native-alias-7-1-7-2` delta)

## ADDED Requirements

### Requirement: Sparse TSR aliases for master memory, authentication, AZ labels, and HAProxy HA
KB row `7.1.tsr.1_4_1_3_master_memory` SHALL be a sparse alias (`content_from` exact `7.1.nodes.master_mem`, `include_in_findings = false`). KB row `7.1.tsr.1_5_17_authentication` SHALL be a sparse alias (`content_from` exact `7.1.sys.auth`, `include_in_findings = false`). KB row `7.2.tsr.2_2_2_master_av_zone_labels` SHALL be a sparse alias (`content_from` exact `7.2.topo.master_az`, `include_in_findings = false`). KB row `7.2.tsr.2_2_3_haproxy_ha` SHALL be a sparse alias (`content_from` exact `7.2.topo.haproxy_ha`, `include_in_findings = false`). Alias rows SHALL NOT overlay inherited narrative keys. Master memory FAIL when any master capacity is less than 16 GiB SHALL not change in this change. Authentication WARNING when no IdP or all HTPasswd SHALL not change. AZ WARNING when fewer than 3 zones SHALL not change. HAProxy WARNING when replicas or availableReplicas are less than 2 SHALL not change.

#### Scenario: master-memory TSR is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.1.tsr.1_4_1_3_master_memory` is loaded
- THEN `content_from` is `7.1.nodes.master_mem`
- AND `include_in_findings` is false

#### Scenario: authentication TSR is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.1.tsr.1_5_17_authentication` is loaded
- THEN `content_from` is `7.1.sys.auth`
- AND `include_in_findings` is false

#### Scenario: AZ TSR is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.2.tsr.2_2_2_master_av_zone_labels` is loaded
- THEN `content_from` is `7.2.topo.master_az`
- AND `include_in_findings` is false

#### Scenario: HAProxy TSR is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.2.tsr.2_2_3_haproxy_ha` is loaded
- THEN `content_from` is `7.2.topo.haproxy_ha`
- AND `include_in_findings` is false

### Requirement: Native CoreDNS firing alerts
Core evaluation SHALL emit `7.1.dns.coredns_alerts` from `07_cluster_health` `firing_alerts`. Status SHALL be FAIL if any parsed alert has `state` equal to firing (case-insensitive) and `labels.alertname` exactly one of `CoreDNSErrorsHigh`, `CoreDNSHealthCheckSlow`, or `CoreDNSPanicking`. Pending alerts SHALL not FAIL. Missing or `_is_missing` `firing_alerts` SHALL emit SKIPPED. Else PASS. Non-CoreDNS alert names SHALL not FAIL this check.

#### Scenario: CoreDNSErrorsHigh firing is FAIL
- GIVEN a firing alert whose `alertname` is `CoreDNSErrorsHigh`
- WHEN core evaluation runs
- THEN `7.1.dns.coredns_alerts` status is FAIL

#### Scenario: no CoreDNS firing alerts is PASS
- GIVEN a parsed alert list with no matching CoreDNS names in firing state
- WHEN core evaluation runs
- THEN `7.1.dns.coredns_alerts` status is PASS

#### Scenario: missing firing_alerts is SKIPPED
- GIVEN `firing_alerts` is missing or `_is_missing`
- WHEN core evaluation runs
- THEN `7.1.dns.coredns_alerts` status is SKIPPED

### Requirement: Sparse aliases for DNS TSR and CoreDNS CCX
KB rows `7.1.tsr.1_5_2_3_dns_alerts` and `7.7.ccx_internal.high_core_dns_errors_high_alerts` SHALL be sparse aliases (`content_from` exact `7.1.dns.coredns_alerts`, `include_in_findings = false`). There SHALL NOT be a `content_from` chain through `7.1.tsr.1_5_2_3_dns_alerts`.

#### Scenario: DNS TSR and CoreDNS CCX alias the native
- GIVEN production `load_kb()`
- WHEN entries `7.1.tsr.1_5_2_3_dns_alerts` and `7.7.ccx_internal.high_core_dns_errors_high_alerts` are loaded
- THEN each `content_from` is `7.1.dns.coredns_alerts`
- AND each `include_in_findings` is false

### Requirement: Non-CoreDNS former hops park on critical alerts
KB rows `7.7.ccx_internal.high_severity_alerts`, `7.3.tsr.3_5_9_etcd_alerts`, `7.5.tsr.5_11_health_related_alerts`, `7.5.tsr.5_11_2_node_alerts`, `7.5.tsr.5_11_3_overcommit_alerts`, and `7.6.tsr.6_3_1_active_alerts` SHALL be sparse aliases (`content_from` exact `7.5.alerts.critical`, `include_in_findings = false`). Those rows SHALL NOT target `7.1.dns.coredns_alerts`.

#### Scenario: etcd alerts hop is not CoreDNS
- GIVEN production `load_kb()`
- WHEN entry `7.3.tsr.3_5_9_etcd_alerts` is loaded
- THEN `content_from` is `7.5.alerts.critical`
- AND `include_in_findings` is false

### Requirement: Firewalls TSR stays canonical
KB SHALL NOT set `content_from` on `7.1.tsr.1_5_5_firewalls`. `7.1.sys.firewall` proxy-present WARNING SHALL not change in this change.

#### Scenario: firewalls TSR is not an alias
- GIVEN production `load_kb()`
- WHEN entry `7.1.tsr.1_5_5_firewalls` is loaded
- THEN `content_from` is empty
