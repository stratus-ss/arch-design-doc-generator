# Change Proposal: hc-native-alias-7-5-7-6

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_alias_7_5_7_6_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL sparse-alias ORIG kubelet Ready, pod-restart, and update-history TSR ids onto existing natives; mint cluster rollup `7.5.node.utilization` from frozen per-node `oc adm top` bars; hide already-aliased pruning hops from Chapter 6. Wrong-story TSR rows (quota coverage, pod requests, netpol pruning, image patch management) SHALL stay canonical. `7.6.tsr.6_3_1_active_alerts` SHALL NOT be retargeted in this change.

## Why

ORIG Chapter 6 still lists those TSR ids. Native scorers already exist except a single cluster node-load id (`content_from` cannot target `7.5.node.*.utilization`). Sparse aliases keep TSR `check_id` strings without overlay. Coverage percent vs ORIG Chapter 6 is out of this change.

Plan: `cursor_plans/hc_native_alias_7_5_7_6_2026-08-29.md`
