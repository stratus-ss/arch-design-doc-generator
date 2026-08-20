```
output/hc_collect/
├── manifest.json                    ← collection summary (timestamp, file list, error count)
├── 03_base_platform/
│   ├── clusterversion.json
│   ├── clusteroperators.json
│   └── ...
├── 04_topology/
│   └── ...
├── 05_components/
│   └── ...
├── 06_layered/
│   └── ...
├── 07_cluster_health/
│   └── ...
├── 08_day2/
│   └── ...
├── 09_security/
│   └── ...
├── 10_metrics/
│   └── ...
├── 11_hardware/
│   └── ...
└── 12_ccx/
    └── ccx_rules.json (optional)
```

### File types in the output

Every file is valid JSON. The report generator identifies the type by checking for sentinel keys:

```json
// Normal resource — raw oc -o json output
{"kind": "List", "apiVersion": "v1", "items": [...]}

// Text/table capture — wrapped in an envelope
{"_hc_text": true, "command": "oc adm top nodes", "output": "...", "exit_code": 0}

// Resource not found / operator not installed — NOT an error
{"_hc_not_found": true, "note": "CRD not present — operator not installed", "exit_code": 1}

// Resource exists but returned empty list — also not an error
{"_hc_not_found": true, "note": "resource exists but returned empty list", "exit_code": 0}

// Real error (permissions, network failure, etc.)
{"_hc_error": true, "command": "...", "exit_code": 1}
```

### Command metadata sidecars

Each primary output (`<name>.json`) has a sidecar (`<name>.meta.json`) with command provenance:

```json
{
  "command": "oc get nodes -o json",
  "script": "07_cluster_health.sh",
  "chapter": "7.5",
  "category": "07_cluster_health",
  "check_name": "nodes",
  "timestamp": "2026-07-31T16:07:08Z"
}
```

Use `hc_investigate.py` to print this metadata alongside evidence.

### Static command reference

Generate a discoverable command map from source scripts:

```bash
make hc-command-ref
```

This writes `docs/HC_Command_Reference.md` and maps each `check_name` to the command that collected it.
