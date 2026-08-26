Each target below runs one discrete step and can be re-run on its own — useful for resuming after a failure without repeating steps that already succeeded.

##### Prerequisite (not part of any HC target, but required before `hc-report` will run)

| Target | Purpose |
|--------|---------|
| `setup CLIENT="..." PROJECT="HC"` | Bootstrap `project.yaml` and client working files. `hc-report` fails with `Error: project.yaml not found.` if this hasn't been run. |

##### Individual (atomic) targets

| Target | Purpose |
|--------|---------|
| `hc-collect` | Collect cluster data via `oc` (live cluster) |
| `hc-push-scripts` | Push supportshell collection scripts to remote server (`HC_SSH_HOST=user@host`) |
| `hc-collect-remote` | Run `hc_collect_multi.sh` on the remote server via SSH (`HC_SSH_HOST=user@host HC_MG_INPUT=<case-or-must-gather-path>`) |
| `hc-fetch-results` | Fetch results from remote server — prefers `hc_results.tar.gz`, falls back to raw rsync (`HC_SSH_HOST=user@host`) |
| `hc-merge` | Merge multiple result dirs (`MERGE_INPUTS="dir1 dir2"`) |
| `hc-report` | Generate branded health check report (runs in container; requires `project.yaml`). Optional `HC_OMIT_CHECK_IDS` writes `{stem}_pruned.md`. Optional `HC_SUMMARY_CONCLUSION=1` drafts Chapter 3/8 in place after generate (prefers pruned) |
| `hc-summary-conclusion` | Cursor-draft Chapter 3/8 into an existing report (`REPORT=path.md`) |
| `hc-pdf` | Branded PDF from report markdown (optional `REPORT=path.md`; `FORCE=1` overwrites an existing basename dest) |
| `hc-html` | Collapsible HTML from report markdown (optional `REPORT=path.md`; `FORCE=1` overwrites an existing basename dest) |
| `hc-build-catalog` | Rebuild TSR/CCX catalog JSON from a TSR HTML export (`TSR_HTML=path`) |
| `hc-skip-summary` | Render `skipped_commands.jsonl` into readable YAML (`LEDGER=path`) |
| `hc-investigate` | Trace a finding/check back to raw evidence (`RESULTS_DIR=...`) |
| `hc-command-ref` | Generate static command reference markdown (`docs/HC_Command_Reference.md`) |
| `hc-link-review` | Suggest + HTTP-check KB documentation URLs (does not rewrite TOMLs) |
| `hc-docs` | Regenerate collect/supportshell READMEs from stitchmd sections |
| `hc-report-from-supportshell` | Fetch supportshell results, then generate the deterministic report |
| `clean-hc` | Remove health check pipeline output |
| `check-hc-sync` | Verify `collect/` and `supportshell/` shared scripts 03–09 are in sync |

**Report ID conventions:** Finding IDs (`6.2.x.y`) appear in §6.1/§6.2 headings and are used with `FINDING_ID=...`. Machine Check IDs (e.g. `7.3.etcd.log_errors`) appear under each §6.2 heading as `**Check ID:**` and are used with `CHECK_ID=...`. TSR ref (e.g. `3.5.7`) is the human-readable section label for cross-referencing the TSR report.

##### KB maintenance targets

| Target | Purpose |
|--------|---------|
| `hc-link-review` | Suggest + HTTP-check KB doc URLs (does not rewrite TOMLs) |
| `hc-link-apply` | Write accepted `REPLACE` rows from `kb_link_review.csv` into `[checks.links]` |

##### Combined (multi-step) targets

If one of these fails partway through, find the step that failed in the output and re-run just that individual target from the table above — do not re-run the whole combined target.

| Target | Expands to | Purpose |
|--------|-----------|---------|
| `hc-report-from-supportshell` | `hc-fetch-results` → `hc-report` | Fetch supportshell results, then generate the report (`HC_SUMMARY_CONCLUSION=1` drafts Chapter 3/8 after generate) |
