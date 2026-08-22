The report's default `advisory` profile cross-references a Red Hat Technical Summary Report (TSR) to expand check coverage beyond what the native evaluators implement. Without a TSR, these extra checks are marked `SKIPPED`; with a TSR, they carry the authoritative status from Red Hat's own analysis — significantly improving report completeness.

**Run this before generating the report.**

1. Log in to [access.redhat.com](https://access.redhat.com) → navigate to the support case for this cluster
2. Download the TSR as HTML (look for "Technical Summary Report" → "Download HTML")
3. Place it in the auto-discovery directory:

```bash
mkdir -p output/tsr_html
cp ~/Downloads/<tsr_filename>.html output/tsr_html/
```

The report generator matches each file's **Cluster ID** header to the cluster's `spec.clusterID` (filename and exact Cluster Name are not required). Cluster Name is a fallback, including OpenShift's infrastructureName suffix (`prod-ocp-01` vs `prod-ocp-01-abc12`).

**Alternatives to auto-discovery:**

```bash
# Explicit path via env var:
make hc-report HC_TSR_HTML=output/tsr_html/my_cluster_tsr.html

# Or set once in project.yaml:
# health_check:
#   tsr_html_path: "output/tsr_html/my_cluster_tsr.html"
```

**Multi-cluster cases:** Place one TSR HTML per cluster in `output/tsr_html/`. Each file is matched independently during report generation.

**If you skip this step:** The report still generates successfully — native deterministic checks run regardless. TSR-mapped checks appear as `SKIPPED` with a note to provide the TSR HTML for full coverage. You can always place the TSR later and re-run `make hc-report`.

