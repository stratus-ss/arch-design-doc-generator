**Multi-cluster cases:** Place one TSR HTML per cluster in `output/tsr_html/`. Each is matched independently during report generation.

**If you skip this step:** The report still generates successfully — native deterministic checks run regardless. TSR-mapped checks appear as `SKIPPED` with a note to provide the TSR HTML for full coverage. You can always place the TSR later and re-run `make hc-report`.

### Step 5 — Fetch results and generate report

There are two paths — pick one:

**Option A — Fetch first, then generate separately (more control):**

```bash
# Pull the results tarball from the support shell server
make hc-fetch-results HC_SSH_HOST=user@your-supportshell-server.example.com

# Verify the manifest before proceeding
cat output/hc_collect/<YYYY-MM-DD>/<cluster_name>/manifest.json

# Generate the report
make hc-report HC_COLLECT_OUT=output/hc_collect/<YYYY-MM-DD>/<cluster_name>
```

Results are staged into a dated directory at `output/hc_collect/<YYYY-MM-DD>/`. Under that dated directory, each selected cluster lands in its own subdirectory. Default `hc-fetch-results` is unchanged: it prefers the well-known `hc_results.tar.gz`, falls back to raw rsync, and shows transfer progress.

To re-download a previous cluster's salvage tarball (not the current well-known aggregate), set `HC_SSH_RESULTS` to that cluster stem — absolute path, no `~`:

```bash
make hc-fetch-results HC_SSH_HOST=user@your-supportshell-server.example.com HC_SSH_RESULTS=/home/remote/<username>/hc_results.prod-ocp-01
```

When verifying the manifest, check:
- `total_errors` is `0` (or only contains expected not-installed entries)
- `total_files` is non-zero and consistent with the categories you collected
- `cluster_server` matches the API you expected

> `hc-report` auto-detects the dated subdirectory when run against the parent path. If that dated directory contains exactly one cluster subdirectory, it auto-descends into it and prints a note. If it contains multiple cluster subdirectories, it stops with an explicit error telling you to pick `output/hc_collect/<YYYY-MM-DD>/<cluster_name>` yourself.

**Option B — Combined shortcut (fetch + report in one command):**

```bash
make hc-report-from-supportshell HC_SSH_HOST=user@your-supportshell-server.example.com

# With explicit TSR path:
make hc-report-from-supportshell HC_SSH_HOST=user@your-supportshell-server.example.com HC_TSR_HTML=output/tsr_html/my_cluster_tsr.html
```

This runs `hc-fetch-results` → `hc-report` back-to-back. Use this when you've already verified collection was clean on the server (Step 3 output had no unexpected errors), you placed your TSR HTML in Step 4, and the fetched dated directory contains only one selected cluster. If you fetched multiple clusters, use Option A and run one report per `output/hc_collect/<YYYY-MM-DD>/<cluster_name>/`.

---

**What `make hc-report` does:**

It runs `scripts/health_check/generate_report.py`, which:

1. Reads `manifest.json` to discover which files were collected
2. Loads all JSON files into memory, keyed by category and filename
3. Derives cluster metadata (OCP version, cluster name, install type) from the collected data — if any of these are missing from `project.yaml`, they are inferred from `clusterversion.json` and `infrastructure.json`
4. Evaluates every check deterministically using rules applied to the collected data — no AI is involved in the check evaluation; every PASS/FAIL/WARNING is computed from the JSON
5. Derives P0–P3 findings from the check results
6. Renders the report template (`templates/Health_Check/Template_HC_Report.md`) with all slots filled
7. Writes two files to `output/Health_Check_Report/`:
   - `<ClientPrefix>_OpenShift_Health_Check_<cluster>.md` — the customer-facing report
   - `<ClientPrefix>_HC_audit_<cluster>.json` — machine-readable check and finding data for audit purposes

The report covers:
- Executive summary with finding counts by priority
- Summary statistics table (PASS / WARNING / FAIL / N/A by category)
- Chapter 4: Purpose and engagement approach, plus how to interpret check results
- Chapter 6: Full observations and recommendations by priority (P0–P3)
- Chapter 7: Raw check tables, one per category — every individual check with its status and evidence string

**What the check statuses mean:**

| Status | Meaning |
|--------|---------|
| `PASS` | Check passed deterministically from collected data |
| `WARNING` | Condition detected that warrants review but is not a hard failure |
| `FAIL` | Definitive finding — deviation from Red Hat baseline |
| `INFO` | Informational — data captured for context, no pass/fail judgment |
| `NOT_APPLICABLE` | Operator or feature not installed on this cluster |
| `SKIPPED` | Data was not collected (collection error) |

**What the finding priorities mean:**

| Priority | Meaning |
|----------|---------|
| `P0` | Critical — immediate risk to cluster stability or security |
| `P1` | High — address within current sprint or next change window |
| `P2` | Medium — plan for remediation in the near term |
| `P3` | Low / informational — best practice gap, no immediate risk |

**How finding priority is determined:**

Priority isn't stored anywhere in the collected data — it's derived at report-generation time from two inputs: the check's status (`FAIL` or `WARNING`; `INFO` becomes a P3 finding only when the KB sets `finding_on_info`; `PASS`, `NOT_APPLICABLE`, and `SKIPPED` never become findings) and a keyword match against that check's plain-English description text. `FAIL` checks whose description mentions a small set of severity-signalling terms (node readiness, cluster operators, critical alerts, etc.) become `P0`; every other `FAIL` becomes `P1`. `WARNING` checks are split the same way into `P2` / `P3` using a different keyword list (resource utilization, upgrades, deprecated features, etc.).

This is a best-effort heuristic based on wording, not a guaranteed-correct severity rating — the keyword lists live in `scripts/health_check/hc_report/findings.py` if you want to see exactly what triggers each bucket. If a finding lands in a priority you disagree with for a given engagement, the generated report is just markdown: cut the `####` block under a different `### P0`–`### P3` heading in `output/Health_Check_Report/<ClientPrefix>_OpenShift_Health_Check_<cluster>.md` (or the `_pruned.md` sibling), then run `make hc-renumber-findings REPORT=<that-file>` so §6.2 numbers, §6.1, and `finding-*` anchors match the new order. `DRY_RUN=1` prints the mapping without writing. The original check status and description are preserved unedited in the companion `<ClientPrefix>_HC_audit_<cluster>.json` file if you need to double-check what drove a classification.

To supply your own executive summary text:

```bash
python3 scripts/health_check/generate_report.py \
  --results-dir output/hc_collect \
  --output-dir output/Health_Check_Report \
  --exec-summary "This cluster is in good health overall. Two P1 findings were identified relating to update channel configuration and missing limit ranges..."
```

### Draft Chapter 3 and Chapter 8 (optional, off by default)

Check evaluation and `make hc-report` without `HC_SUMMARY_CONCLUSION` stay deterministic. With `HC_SUMMARY_CONCLUSION=1`, the container drafts Chapter 3 and Chapter 8 **in the report file** after generate succeeds (Cursor only; needs `CURSOR_API_KEY` or `~/.config/arch-doc-gen/cursor_api_key`). Rebuild the toolkit image once so `cursor-sdk` is in the image.

```bash
make hc-report HC_SUMMARY_CONCLUSION=1
make hc-report-from-supportshell HC_SSH_HOST=user@host HC_SUMMARY_CONCLUSION=1
make hc-summary-conclusion REPORT=output/Health_Check_Report/<ClientPrefix>_OpenShift_Health_Check_<cluster>.md
```

`HC_DRY_RUN=1` is the generate-report placeholder executive summary. It is not the sidecar `--dry-run` prompt dump.

List descriptions from one report, or write the filled prompt without invoking a model:

```bash
python3 scripts/health_check/extract_finding_descriptions.py \
  output/Health_Check_Report/<ClientPrefix>_OpenShift_Health_Check_<cluster>.md

make hc-renumber-findings REPORT=output/Health_Check_Report/<ClientPrefix>_OpenShift_Health_Check_<cluster>.md
make hc-renumber-findings REPORT=output/Health_Check_Report/<ClientPrefix>_OpenShift_Health_Check_<cluster>.md DRY_RUN=1

python3 scripts/health_check/draft_summary_conclusion.py --dry-run \
  output/Health_Check_Report/<ClientPrefix>_OpenShift_Health_Check_<cluster>.md
```

After KB Level of Impact edits, refresh Chapter 6 on a **single** customized report without regenerating:

```bash
make hc-update-loi REPORT=output/Health_Check_Report/<ClientPrefix>_OpenShift_Health_Check_<cluster>.md
make hc-update-loi REPORT=output/Health_Check_Report/<ClientPrefix>_OpenShift_Health_Check_<cluster>.md DRY_RUN=1
python3 scripts/health_check/update_finding_loi.py --output UPDATED.md \
  output/Health_Check_Report/<ClientPrefix>_OpenShift_Health_Check_<cluster>.md
```
