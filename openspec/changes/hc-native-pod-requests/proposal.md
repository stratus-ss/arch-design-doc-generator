# Change Proposal: hc-native-pod-requests

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_pod_requests_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL emit native check `7.6.pod.requests` that WARNINGs when any non-platform Running or Pending pod has a container without both CPU and memory requests. ORIG `7.6.tsr.6_1_2_requests_and_limits` SHALL be a sparse `content_from` alias onto that native (`include_in_findings = false`). LimitRange inventory checks `7.6.limitranges` and `7.6.req_limits` SHALL remain independently scored and SHALL NOT be alias targets. The native SHALL NOT FAIL.

## Why

ORIG Chapter 6 requests-and-limits is BestEffort user pods, not LimitRange inventory. Live clusters often have some BestEffort app pods; WARNING avoids drowning the report. Sparse alias keeps the TSR `check_id` without overlay. Coverage percent vs ORIG Chapter 6 is out of this change.

Plan: `cursor_plans/hc_native_pod_requests_2026-08-29.md`
