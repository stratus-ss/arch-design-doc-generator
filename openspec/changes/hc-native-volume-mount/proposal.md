# Change Proposal: hc-native-volume-mount

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/archive/hc_native_volume_mount_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify the living spec until Task 8. Do not modify unrelated `openspec/changes/`.

Live collect SHALL write `10_metrics/volume_mount_p99.json` from PromQL
`histogram_quantile(0.99, sum(rate(storage_operation_duration_seconds_bucket{operation=~"volume_mount|mount"}[15m])) by (le))`.
Core evaluation SHALL emit `7.5.volume.mount_p99`. Missing or `_hc_error` SHALL be SKIPPED. An empty Prometheus result vector SHALL be INFO. Max sample greater than 10 seconds SHALL be FAIL. Max sample greater than 2 seconds and at most 10 SHALL be WARNING. Else PASS. `7.5.tsr.5_10_volume_mount_durations` SHALL be a sparse alias of `7.5.volume.mount_p99` with `include_in_findings = false`. The engine SHALL NOT scrape host mount tables. The engine SHALL NOT retune PVC used-percent checks. The engine SHALL NOT emit SKIPPED stub `7.5.vol_mount`. Empty PromQL on lab SHALL count as INFO success.

## Why

TSR 5.10 is kubelet volume mount duration, not PVC used percent. Coverage percent vs ORIG Chapter 6 is out of this change.

Plan: `cursor_plans/hc_native_volume_mount_2026-08-29.md`
