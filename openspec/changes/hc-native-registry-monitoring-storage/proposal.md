# Change Proposal: hc-native-registry-monitoring-storage

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_registry_monitoring_storage_2026-08-28.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL emit native checks `7.3.registry.storage` (emptyDir vs persistent/object) and `7.3.monitoring.storage` (PVC template plus RWO vs RWX/file). Existing `7.3.registry.state` and `7.3.monitoring.config` SHALL remain independently scored. ORIG TSR IDs stay as sparse `content_from` aliases with `include_in_findings = false`. Collect SHALL NOT add new files for these checks.

## Why

ORIG Chapter 6 still lists registry storage type and monitoring storage type as distinct stories. Family-level `7.3.registry.state` and ConfigMap-string `7.3.monitoring.config` do not score those bars. Sparse aliases keep TSR `check_id` strings without overlay, including retargeting `7.3.tsr.3_6_2_registry_storage_type` off `7.3.tsr.3_6_1_registry_scaled`.

Plan: `cursor_plans/hc_native_registry_monitoring_storage_2026-08-28.md`
