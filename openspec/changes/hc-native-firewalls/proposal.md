# Change Proposal: hc-native-firewalls

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_firewalls_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL emit native overlay-port posture `7.1.net.overlay_ports` from collected `05_components` `network` (`oc get network cluster`). ORIG `7.1.tsr.1_5_5_firewalls` SHALL be a sparse `content_from` alias with `include_in_findings = false`. The alias SHALL NOT target `7.1.sys.firewall`. Cluster-wide proxy WARNING on `7.1.sys.firewall` SHALL not be retuned. Ports SHALL NOT be probed. Status SHALL NEVER be FAIL.

## Why

ORIG Chapter 6 firewalls is Geneve/API/etcd/kubelet between nodes. Native `7.1.sys.firewall` is proxy presence, a different story. A CNI-typed overlay row covers the TSR without host iptables or security-group scrape.

Plan: `cursor_plans/hc_native_firewalls_2026-08-29.md`
