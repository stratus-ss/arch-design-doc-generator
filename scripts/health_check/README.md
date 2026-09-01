# Health Check scripts

Map of `scripts/health_check/`. Engagement how-to lives in `collect/README.md` and `supportshell/README.md` (`make hc-docs` regenerates those from `docs/`). Maintainer execution path: [docs/CODEFLOW.md](../../docs/CODEFLOW.md) sections 6–8.

## Pipeline (usually `make`)

| Script | Purpose | How to run |
|--------|---------|------------|
| `generate_report.py` | Deterministic report from collected JSON | `make hc-report` |
| `hc_investigate.py` | Trace a finding/check to raw evidence | `make hc-investigate` |
| `hc_fetch_results.sh` | Fetch results from a remote supportshell host | `make hc-fetch-results` |
| `hc_skip_summary.py` | Render `skipped_commands.jsonl` to YAML | `make hc-skip-summary` |
| `generate_command_reference.py` | Write `docs/HC_Command_Reference.md` | `make hc-command-ref` |
| `hc_link_review.py` | Suggest and HTTP-check KB documentation URLs | `make hc-link-review` |
| `hc_link_apply.py` | Write accepted `REPLACE` rows into `[checks.links]` | `make hc-link-apply` |
| `draft_summary_conclusion.py` | Cursor-draft Chapter 3/8 into one report | `make hc-summary-conclusion REPORT=path.md` or `HC_SUMMARY_CONCLUSION=1` on generate |

## Consultant, one report at a time

Name **one** markdown file. Do not glob.

| Script | Purpose | How to run |
|--------|---------|------------|
| `extract_finding_descriptions.py` | Print §6.2 descriptions and check IDs | `python3 scripts/health_check/extract_finding_descriptions.py REPORT.md` |
| `renumber_finding_sections.py` | After moving §6.2 blocks between P0–P3, rewrite numbers, §6.1, and anchors | `make hc-renumber-findings REPORT=path.md` (host; relative or absolute); `DRY_RUN=1` to preview |
| `update_finding_loi.py` | Rewrite Chapter 6 **Level of Impact** from current KB TOML | `make hc-update-loi REPORT=path.md` (in-place, `.loi.bak`); `DRY_RUN=1` to preview; sidecar: `python3 scripts/health_check/update_finding_loi.py --output UPDATED.md REPORT.md` |

## Packages (do not call modules as the primary UX)

| Path | Role |
|------|------|
| `collect/` | Live `oc` collection. Operator steps: `collect/README.md`. |
| `supportshell/` | Offline `omc` collection and merge. Operator steps: `supportshell/README.md`. |
| `hc_report/` | Report engine and `kb/*.toml`. Invoked via `generate_report.py` / `make hc-report`. |
| `docs/` | stitchmd fragments. Edit these, then `make hc-docs`. |
| `prompts/` | Prompt templates used by draft/extract helpers. |
