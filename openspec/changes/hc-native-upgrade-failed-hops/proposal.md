# Change Proposal: hc-native-upgrade-failed-hops

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_upgrade_failed_hops_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL emit native check `7.6.upgrade.failed_hops` that FAILs when ClusterVersion `status.history` contains any hop whose `state` is `Partial` or `Failed`. Else PASS when history exists. Empty or missing history is NOT_APPLICABLE. Collection `_hc_error` is SKIPPED. The check SHALL never emit WARNING. `7.6.upgrade.history` Completed-only bars SHALL not change. ORIG `7.6.tsr.6_2_1_update_history` SHALL remain a sparse alias of `7.6.upgrade.history` and SHALL NOT retarget this native.

Coverage percent vs ORIG Chapter 6 is out of this change.

Plan: `cursor_plans/hc_native_upgrade_failed_hops_2026-08-29.md`
