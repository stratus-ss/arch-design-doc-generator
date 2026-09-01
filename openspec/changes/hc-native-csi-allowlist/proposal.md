# Change Proposal: hc-native-csi-allowlist

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_csi_allowlist_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL emit native check `7.3.storage.csi_cso` that classifies CSIDriver names against the ClusterCSIDriver CRD enum (CSO-managed) plus listed Red Hat products outside CSO. Third-party names SHALL be WARNING, not FAIL. ORIG `7.3.tsr.3_9_5_csi_drivers` SHALL be a sparse `content_from` alias onto that native (`include_in_findings = false`). Inventory check `7.3.storage.csi` SHALL remain independently scored and SHALL NOT be the alias target.

## Why

ORIG Chapter 6 CSI is CSO-managed vs third-party, not “any CSIDriver exists.” Live lab `nfs.csi.k8s.io` is outside the ClusterCSIDriver enum. Sparse alias keeps the TSR `check_id` without overlay. Coverage percent vs ORIG Chapter 6 is out of this change.

Plan: `cursor_plans/hc_native_csi_allowlist_2026-08-29.md`
