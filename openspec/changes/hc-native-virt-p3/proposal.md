# Change Proposal: hc-native-virt-p3

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_virt_p3_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL emit nine natives: `7.4.cnv.subscription`, `7.4.cnv.nmstate_csv`, `7.4.cnv.sriov_csv`, `7.4.cnv.run_strategy`, `7.4.cnv.vmi_phase`, `7.4.cnv.migration_network`, `7.4.cnv.linux_bridge`, `7.4.cnv.node_placement`, and `7.4.cnv.cdi`. Matching ORIG P3 TSR IDs SHALL be sparse `content_from` aliases with `include_in_findings = false`. `7.4.tsr.4_8_3_1_1_storage_profiles` and `7.4.tsr.4_8_5_1_1_quota_and_resources` SHALL remain canonical TSR rows.

## Why

ORIG Chapter 6 still lists those nine virt P3 stories. Existing natives (`cnv.state`, `nncp`, `live_migratable`, `cnv.pods`) do not score them. Dumping those leaves onto identification-and-state is the wrong story.

Plan: `cursor_plans/hc_native_virt_p3_2026-08-29.md`
