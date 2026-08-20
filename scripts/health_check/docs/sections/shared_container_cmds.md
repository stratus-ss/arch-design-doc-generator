```bash
# via Makefile (preferred):
make hc-report
make hc-html
make hc-pdf
make hc-investigate FINDING_ARGS='...'

# container entrypoint subcommands (scripts/entrypoint.sh):
hc-report
hc-html
hc-pdf
hc-investigate
```

#### Templates

| File | Purpose |
|------|---------|
| `templates/Health_Check/Template_HC_Report.md` | Final branded report (customer deliverable) |
| `templates/Health_Check/Template_HC_LLD_Execution_Guide.md` | Procedural runbook for executing a health check |
| `templates/Health_Check/Template_HC_Drift_Analysis.md` | ADR drift analysis report |
