# Change Proposal: hc-kb-content-from

> **STATUS: ARCHIVED** (merged into `openspec/specs/hc-report-engine/spec.md`)
> Plan: `cursor_plans/hc_kb_content_from_2026-08-22.md`
> Parent: `cursor_plans/hc_kb_catalog_audit_2026-08-22.md`

Baseline: `openspec/specs/hc-report-engine/spec.md` (Chunks A–G). Chunk H remains a separate PROPOSED change and is not modified.

This change adds a single-hop `content_from` pointer on knowledge-base rows so alias `check_id`s inherit canonical recommendation, description, impact, and links at `load_kb()` time. Overlay is forbidden. Resolution is fail-closed (`ValueError`). Title and finding flags stay local.
