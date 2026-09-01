# Change Proposal: hc-native-haproxy-keepalived

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_haproxy_keepalived_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Live **core** SHALL emit `7.2.topo.keepalived` from `07_cluster_health/pods_all`. Keepalived pods are those in namespace `openshift-kni-infra` whose names start with `keepalived-`. Missing or `_hc_error` `pods_all` SHALL be SKIPPED. Zero matching pods SHALL be INFO. Any matching pod whose phase is not Running or whose containers are not all Ready SHALL be FAIL. Else PASS. The engine SHALL NOT retune `7.2.topo.haproxy_ha`. `7.2.tsr.2_2_3_haproxy_ha` SHALL remain a sparse alias of `7.2.topo.haproxy_ha`.

## Why

Bare-metal API VIP health depends on kni-infra keepalived Ready, not IngressController replica count. Replica HA already has a native. Coverage percent vs ORIG Chapter 6 is out of this change.

Plan: `cursor_plans/hc_native_haproxy_keepalived_2026-08-29.md`
