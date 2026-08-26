# Change Proposal: hc-html-pdf-report-file

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-26.
> Plan: `cursor_plans/hc_html_pdf_report_file_2026-08-26.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`.

Optional `REPORT=path.md` on `make hc-html` and `make hc-pdf` exports exactly that markdown file. Unset `REPORT` keeps discover-all (including pruned-peer preference). Named export never prefers `{stem}_pruned.md`. Out-of-tree sources map by basename under `HTML/` or `PDFs/` with a loud warning. Overwriting a non-regenerate destination requires TTY confirmation or `FORCE=1`.
