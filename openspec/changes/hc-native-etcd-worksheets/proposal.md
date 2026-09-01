# Change Proposal: hc-native-etcd-worksheets

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_etcd_worksheets_2026-08-28.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL emit native etcd worksheets: disk aggregate `7.8.etcd.disk`, compaction, log-phrase errors (6h), and heartbeat. ORIG TSR IDs stay as sparse `content_from` aliases with `include_in_findings = false`. Per-pod WAL FAIL bar is unchanged. Collect SHALL NOT compact etcd.

## Why

ORIG Chapter 6 still lists compaction, log errors, and disk as distinct stories. Family-level `7.8.etcd` / WAL-only scoring does not cover those rows. Sparse aliases keep TSR `check_id` strings without overlay.

Plan: `cursor_plans/hc_native_etcd_worksheets_2026-08-28.md`
