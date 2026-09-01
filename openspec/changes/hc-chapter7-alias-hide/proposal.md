# Change Proposal: hc-chapter7-alias-hide

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_chapter7_alias_hide_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Chapter 7 check-result tables and category stats SHALL omit checks whose KB entry has a non-empty `content_from`. Natives (`content_from` empty) and checks with no KB entry SHALL remain. CCX rows without `content_from` SHALL remain. Chapter 6 findings derivation SHALL keep `include_in_findings` semantics unchanged. `--omit-check-ids` SHALL NOT change in this change.

## Why

Sparse TSR aliases duplicate native titles in the Chapter 7 appendix after Chapter 6 already hides them with `include_in_findings = false`. Filtering presentation on `content_from` removes the duplicate rows without retuning scorers.

Plan: `cursor_plans/hc_chapter7_alias_hide_2026-08-29.md`
