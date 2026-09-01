# Design: 7.1/7.2 sparse aliases and CoreDNS alerts

Keep master memory as 16 GiB `status.capacity.memory` (`7.1.nodes.master_mem`). Keep auth as IdP list (`7.1.sys.auth`). Keep AZ as ≥3 zone labels (`7.2.topo.master_az`). Keep HAProxy as IngressController replica HA (`7.2.topo.haproxy_ha`). Do not retune those bars. Do not alias `7.1.tsr.1_5_5_firewalls` to `7.1.sys.firewall`.

Mint `7.1.dns.coredns_alerts` from existing `07_cluster_health` `firing_alerts`. FAIL if any alert with Prometheus `state` firing has `labels.alertname` exactly `CoreDNSErrorsHigh`, `CoreDNSHealthCheckSlow`, or `CoreDNSPanicking`. Missing payload SHALL be SKIPPED. Pending alerts SHALL not FAIL.

Sparse-alias memory, auth, AZ, HAProxy, and DNS TSR onto those natives (`include_in_findings = false`). Alias `7.7.ccx_internal.high_core_dns_errors_high_alerts` onto `7.1.dns.coredns_alerts`. Park other former DNS hops on `7.5.alerts.critical`. Alias rows SHALL NOT overlay inherited narrative keys.

Scoring matrix and alias targets are in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
