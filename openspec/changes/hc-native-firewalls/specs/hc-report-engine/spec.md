# Health Check Report Engine (`hc-native-firewalls` delta)

## ADDED Requirements

### Requirement: Native overlay-port posture
Core evaluation SHALL emit `7.1.net.overlay_ports` from `05_components` `network`. Status SHALL be SKIPPED when the payload has `_hc_error`. Status SHALL be NOT_APPLICABLE when the payload is missing or `_hc_not_found`. Status SHALL be PASS when `spec.networkType` is `OVNKubernetes`. PASS evidence SHALL name 6081/udp (all nodes), 6443/tcp (control-plane), 2379/tcp and 2380/tcp (control-plane), 10250/tcp (all nodes), and SHALL include the phrase `ports not probed`. Status SHALL be WARNING when `spec.networkType` is `OpenShiftSDN`. Status SHALL be INFO when `spec.networkType` is any other non-empty value. Status SHALL NEVER be FAIL. Collect SHALL NOT probe host iptables or cloud security groups for this check.

#### Scenario: OVNKubernetes is PASS
- GIVEN `network` with `spec.networkType` equal to `OVNKubernetes`
- WHEN core evaluation runs
- THEN `7.1.net.overlay_ports` status is PASS
- AND evidence contains `ports not probed`

#### Scenario: OpenShiftSDN is WARNING
- GIVEN `network` with `spec.networkType` equal to `OpenShiftSDN`
- WHEN core evaluation runs
- THEN `7.1.net.overlay_ports` status is WARNING

#### Scenario: collect error is SKIPPED
- GIVEN `network` with `_hc_error` set
- WHEN core evaluation runs
- THEN `7.1.net.overlay_ports` status is SKIPPED

#### Scenario: missing network is NOT_APPLICABLE
- GIVEN `network` missing or `_hc_not_found`
- WHEN core evaluation runs
- THEN `7.1.net.overlay_ports` status is NOT_APPLICABLE

#### Scenario: other CNI is INFO
- GIVEN `network` with a non-empty `spec.networkType` that is neither `OVNKubernetes` nor `OpenShiftSDN`
- WHEN core evaluation runs
- THEN `7.1.net.overlay_ports` status is INFO

#### Scenario: empty networkType is INFO
- GIVEN `network` with `spec.networkType` empty or missing
- AND no ClusterOperator plugin fallback of `OVNKubernetes` or `OpenShiftSDN`
- WHEN core evaluation runs
- THEN `7.1.net.overlay_ports` status is INFO

### Requirement: Firewalls TSR sparse-aliases overlay ports
KB row `7.1.tsr.1_5_5_firewalls` SHALL be a sparse alias (`content_from` exact `7.1.net.overlay_ports`, `include_in_findings = false`). The alias SHALL NOT set `content_from` to `7.1.sys.firewall`. Alias rows SHALL NOT overlay inherited narrative keys. `7.1.sys.firewall` proxy-present WARNING SHALL not change in this change.

#### Scenario: firewalls TSR aliases overlay ports
- GIVEN production `load_kb()`
- WHEN entry `7.1.tsr.1_5_5_firewalls` is loaded
- THEN `content_from` is `7.1.net.overlay_ports`
- AND `include_in_findings` is false
- AND `content_from` is not `7.1.sys.firewall`

### Requirement: Overlay ports are not probed
Evaluation SHALL NOT FAIL `7.1.net.overlay_ports` because ports were not probed. Host debug, iptables scrape, and security-group inventory SHALL stay out of this check.

#### Scenario: no FAIL for unprobed ports
- GIVEN `network` with `spec.networkType` equal to `OVNKubernetes`
- WHEN core evaluation runs
- THEN `7.1.net.overlay_ports` status is not FAIL
