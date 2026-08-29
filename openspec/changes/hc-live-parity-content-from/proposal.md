# Change Proposal: hc-live-parity-content-from

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-28.
> Plan: `cursor_plans/hc_tsr_live_parity_content_from_2026-08-28.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify `hc-live-parity-collect` or `hc-live-parity-evaluate`.

Plan 1 `CONTENT_FROM` KB rows become sparse `content_from` aliases that inherit canonical prose. New aliases set `include_in_findings = false` so Chapter 6 findings come from the native row. Loader fail-closed rules are unchanged.

## Why

Without aliases, TSR leaves duplicate native recommendation text. With TSR HTML present, Chapter 6 also duplicates native findings. Native-without-TSR still needs one canonical narrative per family (virt uses `7.4.cnv.*`, not a dump onto identification-and-state).

## What Changes

- KB TOML: sparse aliases for CONTENT_FROM rows whose target exists.
- Distinct virt TSR prose rows stay canonical.
- Minimal stubs only for missing native targets.
- No `kb_loader.py` behavior change.

## Out of Scope

Collect scripts, evaluator scoring, html-unmapped CCX, TSR_ONLY host heuristics, full consultant-voice narratives.
