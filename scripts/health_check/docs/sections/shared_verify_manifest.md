Before generating anything, confirm the collection was clean:

```bash
cat output/hc_collect/manifest.json
```

Check:
- `total_errors` is `0` (or only contains expected not-installed entries)
- `total_files` is non-zero and consistent with the categories you collected (it varies by cluster size and installed operators)
- `cluster_server` matches the API you expected

If you see a non-zero `total_errors`, scroll back through the collection output for `WARN` lines. They will tell you which commands failed and why.

> Results fetched from a supportshell/must-gather engagement (via `hc-fetch-results`) land one level deeper, at `output/hc_collect/<YYYY-MM-DD>/manifest.json` — see [Troubleshooting](#troubleshooting) if `hc-report` reports 0 files/categories.
