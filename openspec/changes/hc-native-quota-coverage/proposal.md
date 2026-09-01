# Change Proposal: hc-native-quota-coverage

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_quota_coverage_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL emit native check `7.6.quota.coverage` that FAILs when any user namespace lacks both ResourceQuota and LimitRange. ORIG `7.6.tsr.6_1_1_1_quota_resources_project_assignment` SHALL be a sparse `content_from` alias onto that native (`include_in_findings = false`). Parent hops `7.6.tsr.6_1_1_quota_and_resources` and `7.6.tsr.6_1_1_2_cluster_quota_configuration` SHALL retarget the native in one hop. Inventory `7.6.rq` and `7.6.cluster_quota` SHALL remain independently scored and SHALL NOT be alias targets.

## Why

ORIG Chapter 6 quota coverage is uncovered user projects, not “any quota exists.” Live lab user namespaces can all lack RQ and LR. Sparse alias keeps the TSR `check_id` without overlay. Coverage percent vs ORIG Chapter 6 is out of this change.

Plan: `cursor_plans/hc_native_quota_coverage_2026-08-29.md`
