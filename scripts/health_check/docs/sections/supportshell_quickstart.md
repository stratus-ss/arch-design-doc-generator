```
make setup CLIENT="..." PROJECT="HC"   → project.yaml            (fill in the health_check: section — case number, consultant, etc.)
     │
     ▼
make hc-push-scripts     → (once) stage collection scripts on the support shell server
make hc-collect-remote   → runs hc_collect_multi.sh against the must-gather, produces /home/remote/<username>/hc_results
make hc-fetch-results    → output/hc_collect/<YYYY-MM-DD>/       (dated staging dir; see HC_FETCH_STAGE)
     │
     ▼
[Place TSR HTML in output/tsr_html/]   (optional — download from access.redhat.com)
     │
     ▼
make hc-report           → output/Health_Check_Report/           (branded markdown report + audit JSON)
     │
     ▼
make workitems           → output/Work_Items/                    (Jira-importable CSV + per-story markdown)
     │
     ▼
make hc-pdf              → output/Health_Check_Report/PDFs/      (customer report PDF)
make hc-html             → output/Health_Check_Report/HTML/      (collapsible HTML report)
```

Optional `REPORT=path.md` on `hc-html`/`hc-pdf` exports that one markdown file. `FORCE=1` overwrites an existing basename dest (out-of-tree only).

`make hc-pdf` runs inside the project container (no host weasyprint needed). Container auto-builds on first use.
