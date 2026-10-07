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

## Engagement targets

Start at the repo [README](../../README.md#health-check). This is the full Health Check target list. How each one runs: [docs/CODEFLOW.md](../../docs/CODEFLOW.md) sections 6–8. Variables: [Make variables](../../docs/CODEFLOW.md#make-variables).

| Target | Runtime | Purpose |
|---|---|---|
| `make setup CLIENT="..." PROJECT="HC"` | Container | Bootstrap `project.yaml` from `project.example.hc.yaml` and scaffold `output/hc_collect` + `output/Health_Check_Report` |
| `make hc-collect KUBECONFIG=<path>` | Host | Collect cluster JSON via live `oc` CLI |
| `make hc-push-scripts HC_SSH_HOST=user@host` | Host | Push supportshell scripts to a remote server |
| `make hc-collect-remote HC_SSH_HOST=... HC_MG_INPUT=<path>` | Host | Run `hc_collect_multi.sh` on the remote via SSH |
| `make hc-fetch-results HC_SSH_HOST=...` | Host | Fetch results tarball from remote into `output/hc_collect/<date>` (optional salvage: `HC_SSH_RESULTS=/path/hc_results.<cluster>`) |
| `make hc-report-from-supportshell HC_SSH_HOST=user@host` | Host fetch, then container report | Fetch supportshell results, then run `hc-report` against the dated staging dir |
| `make hc-merge MERGE_INPUTS="dir1 dir2"` | Host | Merge multiple `hc_results` dirs on the host |
| `make hc-report` | Container | Generate markdown report + audit JSON from collected data (default profile `advisory`). Optional `HC_OMIT_CHECK_IDS` writes `{stem}_pruned.md`. Optional `HC_SUMMARY_CONCLUSION=1` drafts Chapter 3/8 in place (prefers pruned) |
| `make hc-summary-conclusion REPORT=path.md` | Container | Cursor-draft Chapter 3/8 into an existing report |
| `make hc-html` | Container | Collapsible HTML from report markdown (unset `REPORT` = discover-all; optional `REPORT=path.md`; `FORCE=1` overwrites an existing basename dest) |
| `make hc-pdf` | Container | Branded PDF from report markdown (same `REPORT=` / `FORCE=1` as `hc-html`) |
| `make hc-build-catalog TSR_HTML=<path>` | Host | Rebuild `tsr_ccx_crosswalk.json` from a TSR HTML export |
| `make hc-investigate RESULTS_DIR=… FINDING_ID=…` | Container | Trace a finding or check back to raw evidence (`CHECK_ID=` / `QUERY=` also work) |
| `make hc-skip-summary LEDGER=…` | Host | Summarize skipped collection commands from `skipped_commands.jsonl` (`RESULTS_DIR=` also works) |
| `make hc-command-ref` | Host | Write `docs/HC_Command_Reference.md` from collect scripts |
| `make hc-update-loi REPORT=path.md` | Host | Rewrite Chapter 6 Level of Impact from current KB TOML |
| `make hc-renumber-findings REPORT=path.md` | Host | Resequence §6.2 IDs after moving findings between P0–P3 |
| `make hc-link-review` | Container | Suggest KB doc URLs and HTTP-check pages with `curl_cffi` |
| `make hc-link-apply` | Host | Write accepted `REPLACE` URLs from `kb_link_review.csv` into KB `[checks.links]` |
| `make check-hc-sync` | Host | Diff collect/ vs supportshell/ shared scripts 03–09 |
| `make hc-docs` | Container | Regenerate collect/supportshell READMEs from stitchmd fragments |
| `make clean-hc` | Host | Remove `output/hc_collect` and `output/Health_Check_Report` |

`make hc-report` runs `generate_report.py` inside the toolkit container (`HC_CHECK_PROFILE` defaults to `advisory`). Place TSR HTML under `output/tsr_html/` or set `HC_TSR_HTML` to a repo-relative path so catalog rows get real statuses. Without matching HTML, those rows are SKIPPED. `HC_CHECK_PROFILE=core` still runs native evaluators only.

Rebuild the catalog with `make hc-build-catalog TSR_HTML=path/to/export.html`. Outputs land under `output/Health_Check_Report/`. Optional: `HC_DRY_RUN=1` for the generate-report placeholder executive summary. Optional: `HC_OMIT_CHECK_IDS=path/to/omit.txt` (repo-relative) to also write `{stem}_pruned.md` with those check IDs dropped from Chapter 6; `HC_OMIT_STRICT=1` exits 1 if an ID is not on any finding. Optional: `HC_SUMMARY_CONCLUSION=1` to Cursor-draft Chapter 3 and Chapter 8 in place after generate (requires `CURSOR_API_KEY` and an image rebuilt with `cursor-sdk`; drafts the pruned file when it exists).

`project.example.hc.yaml` is the HC template; never commit `project.yaml` or kubeconfigs.

## Packages (do not call modules as the primary UX)

| Path | Role |
|------|------|
| `collect/` | Live `oc` collection. Operator steps: `collect/README.md`. |
| `supportshell/` | Offline `omc` collection and merge. Operator steps: `supportshell/README.md`. |
| `hc_report/` | Report engine and `kb/*.toml`. Invoked via `generate_report.py` / `make hc-report`. |
| `docs/` | stitchmd fragments. Edit these, then `make hc-docs`. |
| `prompts/` | Prompt templates used by draft/extract helpers. |

## Knowledge Base (KB) for recommendations and notes

Report prose (description, recommendation, optional verification, documentation links, operational impact) lives in TOML under `scripts/health_check/hc_report/kb/` (`7_1`–`7_9` plus `versions.toml`). `kb_loader.py` loads it at report time. Thresholds, evidence paths, and live `oc`/`jq` validation stay in [`docs/HC_CHECK_RATIONALE.md`](../../docs/HC_CHECK_RATIONALE.md). Numbered `oc` commands belong in `verification`; `get_recommendation` joins that field into the Recommendation block at read. Verification English tells a non-expert how to read each command (healthy / fail / skip); it does not repeat the recommendation.

Each `[[checks]]` row is keyed by `check_id`. Typical fields: `title`, `description`, `recommendation`, optional `verification`, `impact` / `impact_scope` / `impact_detail`, `[checks.links]`, optional `summary_patterns`, `finding_group`, `include_in_findings`, and `finding_on_info`. Descriptions are mode-neutral (valid without TSR). Empty recommendation or impact renders `[NEEDS REVIEW]`. `get_recommendation` joins `recommendation` with optional `verification` using a bold `**Verification:**` line inside the Recommendation block; aliases inherit `verification` via `content_from`.

### Sparse rows (`content_from`)

Some `[[checks]]` entries look almost empty on purpose. When two `check_id`s tell the same operational story (a native check plus a TSR catalog twin, or a parent section that duplicates a child), the alias sets `content_from` to the canonical `check_id` and **omits** recommendation, verification, description, impact, and links:

```toml
[[checks]]
check_id = "7.6.tsr.6_1_5_1_pod_pruning"
title = "TSR pod pruning"
content_from = "7.5.pruning.pods"
```

`load_kb()` copies those inherited fields from the canonical row in a **single hop**. Title and finding flags (`include_in_findings`, `finding_group`, `finding_on_info`) stay on the alias so chapter 7 can still list every check while Chapter 4 / §6.2 may merge or hide duplicates.

Edit the **canonical** row to change report text. Do not copy inherited fields onto the alias — overlay is rejected. Chains, self-references, missing targets, glob targets, and `pattern = true` aliases also fail closed (`ValueError` at load).

## KB documentation link review

Produces a suggested-URL table comparing KB TOML links against a local documentation checkout. Does not modify TOMLs. Suggested URLs never invent `#` fragments (existing fragments are kept only when the book is unchanged). Unique suggested **page** URLs are HTTP GET-checked with `curl_cffi` Chrome TLS impersonation inside the toolkit container (same anti-bot approach as the sibling repo’s `validate_links.py`). Fragments are not sent to the server; a 200 means the page exists. After reviewing the CSV, `make hc-link-apply` writes `REPLACE` rows (HTTP 200) into `[checks.links]` only.

```bash
make hc-link-review
# optional: HC_DOCS_ROOT=/path/to/openshift_documentation HC_LINK_REVIEW_OUT=agent_planning/execution/hc_kb_link_precision
# skip live GET: append --no-validate-http via a direct python invocation
make hc-link-apply
```

Requires `make force-image` once so the image contains `curl_cffi`. Host urllib against `docs.redhat.com` is expected to 403.

Outputs `kb_link_review.md` and `kb_link_review.csv`.
