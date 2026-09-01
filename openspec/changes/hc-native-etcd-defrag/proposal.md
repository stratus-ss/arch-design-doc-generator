# Change Proposal: hc-native-etcd-defrag

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/archive/hc_native_etcd_defrag_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify living spec until Task 8. Do not modify unrelated `openspec/changes/`.

Live **core** SHALL emit cluster rollup `7.8.etcd.defrag` from existing Prometheus files `etcd_db_size_bytes` and `etcd_db_size_in_use`. Members SHALL be matched by pod label. Fragment ratio SHALL be `(size - used) / size` when size is greater than zero. Missing both files SHALL be SKIPPED. Present files with no matching samples SHALL be INFO. Any member ratio ≥ 0.70 SHALL be FAIL. Else any ≥ 0.50 SHALL be WARNING. Else PASS. The engine SHALL NOT retune per-member `7.8.etcd.db.*` 4GiB/8GiB bars. The engine SHALL NOT scrape etcd defrag log phrases. `7.3.tsr.3_5_6_etcd_defragmentation` SHALL be a sparse alias of `7.8.etcd.defrag` with `include_in_findings = false`.

## Why

TSR 3.5.6 warns on frequent defrag log lines. Host collect already has size vs in-use vectors; unused bytes over size is the API-safe defrag-candidate proxy. Coverage percent vs ORIG Chapter 6 is out of this change.

Plan: `cursor_plans/hc_native_etcd_defrag_2026-08-29.md`
