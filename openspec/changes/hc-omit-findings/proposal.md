# Change Proposal: hc-omit-findings

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-25.
> Plan: `cursor_plans/hc_omit_findings_2026-08-25.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`.

Optional check-ID omit list on generate writes `{stem}_pruned.md` with those findings removed from Chapter 6. Original markdown and audit JSON stay full. Chapter 7 is not filtered. `discover_report_markdown` prefers the pruned peer when it exists. `hc_report/cli.py` remains free of AI imports.
