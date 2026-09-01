# Change Proposal: hc-native-virt-orig-leaves

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_virt_orig_leaves_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL emit natives `7.4.cnv.nncp`, `7.4.cnv.virt_storageclass`, and `7.4.oadp.state`. ORIG IDs `7.4.tsr.4_8_2_2_1_2_network_configuration`, `7.4.tsr.4_8_1_3_4_node_disk`, and `7.4.tsr.4_8_5_3_1_oadp_operator` SHALL be sparse `content_from` aliases with `include_in_findings = false`. Natives SHALL NOT be named `node_disk`. Parent `7.4.tsr.4_8_1_4_node_disk` SHALL stay aliased to `7.4.cnv.state`. `7.3.net.hwnet` and `7.3.storage.default_sc` SHALL stay independently scored.

## Why

ORIG Chapter 6 still lists NNCP/NNCE health, virt-default StorageClass, and OADP operator as distinct stories. Family `7.4.cnv.state` does not score those leaves. Sparse aliases keep TSR `check_id` strings without overlay.

Plan: `cursor_plans/hc_native_virt_orig_leaves_2026-08-29.md`
