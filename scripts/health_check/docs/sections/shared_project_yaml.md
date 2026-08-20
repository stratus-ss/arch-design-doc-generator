`hc-report`, `hc-pdf`, and `hc-html` all require `project.yaml`. If it doesn't exist yet, create it once per engagement from the repo root:

```bash
make setup CLIENT="Your Client Name" PROJECT="HC"
```

`PROJECT="HC"` is just a label used for file naming — it doesn't need to match the cluster's actual product name. Skipping this step fails with `Error: project.yaml not found.`. After setup, fill in the `health_check:` section (case number, consultant name, etc.) before generating the report.
