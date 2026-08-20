`hc_collect.sh` is a driver script. When you run it, the following happens in order:

### 1. Pre-flight checks

Before touching the cluster, the script:

- Verifies `oc` is in your `PATH`
- Calls `oc cluster-info` to confirm cluster connectivity — if this fails, it stops immediately with a clear error
- Prints the API server URL it connected to so you can confirm it's the right cluster

### 2. Category scripts run in sequence

Nine bash scripts run one after the other. Together they cover health check chapters HC-03 through HC-11. Each command produces one JSON file in the output directory.

For each `oc get` command, one of four things happens:

| Result | What gets written | Log line |
|--------|-------------------|----------|
| Success with resources | Raw `oc -o json` output | `collect: oc get ... → file.json` |
| Success but empty list | `{"_hc_not_found": true, ...}` | `not-found (empty list): ...` |
| CRD doesn't exist on cluster | `{"_hc_not_found": true, "note": "CRD not present"}` | `not-installed (CRD missing): ...` |
| Real error (permissions, network) | `{"_hc_error": true, "exit_code": N, ...}` | `WARN skipped (exit_code=N): ...` |

Text-format commands (`oc get nodes -o wide`, `oc adm top nodes`, etc.) are wrapped in a JSON envelope:
```json
{"_hc_text": true, "command": "...", "output": "...", "exit_code": 0, "timestamp": "..."}
```

The `not-installed` and `not-found` results are **expected and not errors**. They mean an optional operator (ACM, ACS, Logging, CNV, etc.) isn't deployed on this cluster. The report generator marks those checks as NOT APPLICABLE.

### 3. Manifest generation

After all scripts finish, `manifest.json` is written to the root of the output directory. It records the API server URL, timestamp, total file count, error count, and a full list of every file collected. The report generator reads this first.

Each captured result file now also has a metadata sidecar (`<name>.meta.json`) in the same category directory. Sidecars include:
- exact command string
- script name
- report chapter mapping
- capture timestamp

Sidecars are intentionally excluded from `manifest.json` and report-data ingestion (`hc_report/loader.py`) so they remain traceability-only artifacts.
