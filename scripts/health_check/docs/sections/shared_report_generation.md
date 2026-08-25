```bash
make hc-report
```

This runs `scripts/health_check/generate_report.py`. It:

1. Reads `manifest.json` to discover which files were collected
2. Loads all JSON files into memory, keyed by category and filename
3. Derives cluster metadata (OCP version, cluster name, install type) from the collected data — if any of these are missing from `project.yaml`, they are inferred from `clusterversion.json` and `infrastructure.json`
4. Evaluates every check deterministically using rules applied to the collected data — no AI is involved in the check evaluation; every PASS/FAIL/WARNING is computed from the JSON
5. Derives P0–P3 findings from the check results
6. Renders the report template (`templates/Health_Check/Template_HC_Report.md`) with all slots filled
7. Writes two files to `output/Health_Check_Report/` (plus an optional pruned sibling):
   - `<ClientPrefix>_OpenShift_Health_Check_<cluster>.md` — full report (all Chapter 6 findings)
   - `<ClientPrefix>_HC_audit_<cluster>.json` — machine-readable check and finding data for audit purposes (unfiltered)
   - `<ClientPrefix>_OpenShift_Health_Check_<cluster>_pruned.md` — only when `HC_OMIT_CHECK_IDS` is a non-empty check-ID list; Chapter 6 omits matched findings, Chapter 7 still lists every check. HTML, PDF, and `HC_SUMMARY_CONCLUSION` prefer this file when it exists.

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

This is a best-effort heuristic based on wording, not a guaranteed-correct severity rating — the keyword lists live in `scripts/health_check/hc_report/findings.py` if you want to see exactly what triggers each bucket. If a finding lands in a priority you disagree with for a given engagement, the generated report is just markdown: edit the finding's priority label or move it between chapters directly in `output/Health_Check_Report/<ClientPrefix>_OpenShift_Health_Check_<cluster>.md` before delivering it. The original check status and description are preserved unedited in the companion `<ClientPrefix>_HC_audit_<cluster>.json` file if you need to double-check what drove a classification.

### Omit Chapter 6 findings by check ID (optional)

Mass-drop Chapter 6 sections by **Check ID** (`**Check ID:**` under each §6.2 heading), not by volatile `6.2.x.y` finding IDs and not by deleting headings by hand. Generate still writes the full markdown and audit JSON. The delivery file is `{stem}_pruned.md`. Re-run generate (or `make hc-summary-conclusion REPORT=…_pruned.md`) after changing the omit list so Chapter 3/8 and HTML/PDF use the pruned file.

Omit file (UTF-8, one check ID per line; `#` comments and blanks skipped):

```
# Chapter 6 suppressions for this engagement (check IDs, not 6.2.x.y)
7.4.tsr.4_12_1_2_mtv_supported_configuration
```

```bash
make hc-report HC_OMIT_CHECK_IDS=path/to/omit.txt
make hc-report HC_OMIT_CHECK_IDS=path/to/omit.txt HC_OMIT_STRICT=1
make hc-report HC_OMIT_CHECK_IDS=path/to/omit.txt HC_SUMMARY_CONCLUSION=1
```

`HC_OMIT_STRICT=1` exits 1 if any listed ID is not on a derived finding (does not write `{stem}_pruned.md`). An empty omit file or omitting the flag deletes a stale `{stem}_pruned.md` for that cluster.

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

python3 scripts/health_check/draft_summary_conclusion.py --dry-run \
  output/Health_Check_Report/<ClientPrefix>_OpenShift_Health_Check_<cluster>.md
```

