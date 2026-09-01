# Change Proposal: hc-native-node-role-gc

> **STATUS: ARCHIVED** (merged into `openspec/specs/hc-report-engine/spec.md`)
> Plan: `cursor_plans/hc_native_node_role_gc_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL emit (1) KB plus a sparse alias so ORIG `7.5.tsr.5_6_node_role_values` canonicalizes to existing `7.5.node_roles` (missing `node-role.kubernetes.io/*` labels only), and (2) native `7.6.node.image_gc` from per-node kubelet `configz` HIGH and `stats/summary` imageFs used percent. `7.5.master_taints` SHALL stay independently scored. ORIG TSR IDs stay as sparse `content_from` aliases with `include_in_findings = false`. Collect SHALL NOT persist full `configz` or `stats/summary` documents.

## Why

ORIG Chapter 6 still lists node-role values and image garbage collection as distinct stories. Missing-label scoring already exists; it needs native KB and a legal alias. GC HIGH versus imageFs used percent is not scored today. Sparse aliases keep TSR `check_id` strings without overlay.

Plan: `cursor_plans/hc_native_node_role_gc_2026-08-29.md`
