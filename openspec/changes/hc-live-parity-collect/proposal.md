# Change Proposal: hc-live-parity-collect

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-28.
> Plan: `cursor_plans/hc_tsr_live_parity_collect_2026-08-28.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Chunk H (`openspec/changes/hc-feedback-chunk-h/`) is unrelated and is not modified.

Without TSR HTML, `hc-collect` still writes one verbose JSON file (plus `.meta.json`) per missing live API that Plan 2a adds. Missing CRDs and empty lists use `_hc_not_found`; they do not fail collect. Evaluators and KB `content_from` are out of this change (Plans 2b / 2c).

## Why

Native Health Check scoring needs those JSON files on disk. Duplicate DNS cluster and NetworkAttachmentDefinition gathers are not added; those APIs already exist as `dns_config` and `net_attach_def`.
