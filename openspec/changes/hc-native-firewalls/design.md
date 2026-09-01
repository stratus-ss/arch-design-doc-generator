# Design: native overlay-port posture (firewalls TSR)

Mint `7.1.net.overlay_ports` from existing `05_components/network.json`. Read `spec.networkType` only. Do not `oc debug` nodes. Do not scrape iptables or cloud security groups. Do not alias `7.1.tsr.1_5_5_firewalls` to `7.1.sys.firewall`. Do not retune `_evaluate_system_firewall_proxy`.

`_hc_error` is SKIPPED. Missing or `_hc_not_found` is NOT_APPLICABLE. `OVNKubernetes` is PASS with evidence that names expected ports (6081/udp all nodes; 6443/tcp control-plane; 2379/2380/tcp control-plane; 10250/tcp all nodes) and `ports not probed`. `OpenShiftSDN` is WARNING. Any other non-empty type is INFO. Never FAIL.

Sparse-alias `7.1.tsr.1_5_5_firewalls` onto the native (`include_in_findings = false`). Alias rows SHALL NOT overlay inherited narrative keys.

Scoring matrix and STOP bans are in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
