# Change Proposal: hc-native-netpol-prune

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_netpol_prune_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL collect `networkpolicy` (`oc get networkpolicy -A`) and emit native check `7.6.netpol.orphan` that FAILs when a user NetworkPolicy with a labeled `podSelector` matches zero non-terminal pods. Empty `podSelector` SHALL NOT be an orphan. ORIG `7.6.tsr.6_1_5_3_network_policy_pruning` SHALL be a sparse `content_from` alias onto that native (`include_in_findings = false`). Stub `7.6.prune.netpol` SHALL remain SKIPPED and SHALL NOT be the alias target.

## Why

ORIG Chapter 6 netpol pruning is labeled selectors with MATCH=0, not “any NetworkPolicy exists.” The current prune stub is always SKIPPED. Sparse alias keeps the TSR `check_id` without overlay. Coverage percent vs ORIG Chapter 6 is out of this change.

Plan: `cursor_plans/hc_native_netpol_prune_2026-08-29.md`
