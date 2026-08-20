```
make setup CLIENT="..." PROJECT="HC"   → project.yaml            (fill in the health_check: section — case number, consultant, etc.)
     │
     ▼
make hc-collect        → output/hc_collect/                    (raw JSON from cluster)
     │
     ▼
[Place TSR HTML in output/tsr_html/]   (optional — download from access.redhat.com)
     │
     ▼
make hc-report         → output/Health_Check_Report/           (branded markdown report + audit JSON)
     │
     ▼
make workitems         → output/Work_Items/                    (Jira-importable CSV + per-story markdown)
     │
     ▼
make hc-pdf            → output/Health_Check_Report/PDFs/      (customer report PDF)
make hc-html           → output/Health_Check_Report/HTML/      (collapsible HTML report)
```

`make hc-pdf` runs inside the project container (no host weasyprint needed). Container auto-builds on first use.
