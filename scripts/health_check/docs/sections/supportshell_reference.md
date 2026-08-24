There are two collection paths in this project:

| Path | Tool | Input | When to use |
|------|------|-------|-------------|
| `collect/` | `oc` | Live cluster (kubeconfig) | You have direct or VPN access to the cluster API |
| `supportshell/` (this) | `omc` | Must-gather tarball | No cluster access — customer provided a must-gather via support case |

The category scripts (`03_base_platform.sh` through `12_ccx.sh`) are intentionally parallel between the two directories. They collect the same data and produce the same JSON output structure so the report generator (`generate_report.py`) works identically regardless of which path collected the data.

The scripts cannot be trivially shared because:

1. **CLI differences** — `omc` is a drop-in for most `oc get` commands but does not support `oc exec`, `oc adm top`, or live Prometheus queries. The supportshell scripts handle these gracefully.
2. **Category implementation differences** — both paths include `10_metrics.sh` and `11_hardware.sh`, but the supportshell versions collect static must-gather artifacts where the live path uses `oc exec` and `oc debug node`.
3. **Pre-flight** — The live path verifies cluster connectivity; the supportshell path verifies `omc` has a must-gather loaded.

The JSON output format is identical between both paths, making downstream tooling agnostic to the collection method.

### Category Scripts

| Script | Chapter | Notes |
|--------|---------|-------|
| `03_base_platform.sh` | 7.1 | Same as live path |
| `04_topology.sh` | 7.2 | Same as live path |
| `05_components.sh` | 7.3 | Same as live path |
| `06_layered.sh` | 7.4 | Same as live path |
| `07_cluster_health.sh` | 7.5 | No live alerts — `firing_alerts.json` will be `_hc_not_found` |
| `08_day2.sh` | 7.6 | No `oc adm top` — resource utilisation unavailable |
| `09_security.sh` | 7.7 | Same as live path |
| `10_metrics.sh` | 7.8 | Static Prometheus/etcd configs only (no live queries) |
| `11_hardware.sh` | 7.9 | Extracts DMI/CPU/memory from per-node `sysinfo.tgz` archives in the must-gather (no `oc debug node`). Disk rotational detection is unavailable offline — disk checks are omitted when disk data is absent |
| `12_ccx.sh` | Advisory | Optional CCX payload ingestion from `HC_CCX_RULES_FILE` |

### Skipped Commands Ledger (Debugging)

Every non-success command outcome — a real failure (`_hc_error`), a CRD-not-installed result, or an empty-result-list "not found" — is also appended as one JSON line to `skipped_commands.jsonl` at the root of the results directory, tagged with the must-gather subdirectory that was active (via `omc use`) when the command ran. When `hc_collect_multi.sh` collects from multiple must-gathers, every run's ledger lines are concatenated into one combined ledger in the final merged output, and it rides along in the `--tar` tarball automatically.

Fields per line: `timestamp`, `mg_source`, `category`, `check_name`, `command`, `exit_code`, `capture_type` (`json`/`text`), `outcome` (`error` / `not_found_crd_missing` / `not_found_empty`).

This is a debugging aid only — it is not read by the report generator.

```bash
# Only real errors, not expected not-found cases
jq -c 'select(.outcome == "error")' hc_results/skipped_commands.jsonl

# Group by which must-gather a command was skipped on
jq -c '.mg_source' hc_results/skipped_commands.jsonl | sort | uniq -c
```

#### Readable summary

```bash
make hc-skip-summary LEDGER=output/hc_collect/<date>/skipped_commands.jsonl
```

Renders the ledger as `must_gather: category: check: command` YAML, using short must-gather labels (e.g. `cnv`, `ocp`) from `scripts/health_check/mg_short_names.yaml` instead of the full registry/digest string. Unrecognized must-gather images fall back to a best-effort short name and print a `WARN:` — add a new entry to `mg_short_names.yaml` when that happens.

#### Investigating a report finding

```bash
make hc-investigate RESULTS_DIR=output/hc_collect/<date> FINDING_ID=6.2.3.1
# or: QUERY="Available Updates"   or: CHECK_ID=7.1.clusterversion.updates
```

Traces a finding or check from the generated report back to the exact raw collected JSON file(s) that produced it, and prints any matching `skipped_commands.jsonl` lines for that check.

#### Report ID conventions

The rendered report uses three identifier types:

| ID type | Example | Used by |
|---------|---------|---------|
| **Finding ID** | `6.2.2.3` | Report §6.1 table "Finding" column; `make hc-investigate FINDING_ID=6.2.2.3` |
| **Check ID** | `7.3.etcd.log_errors` | Evaluator-assigned machine key; `make hc-investigate CHECK_ID=7.3.etcd.log_errors` |
| **TSR ref** | `3.5.7` | Human/TSR section label shown under the finding heading for cross-reference |

In the §6.1 Critical Findings table, the Finding column format is `{finding_id} — {display_title}`. In §6.2 each finding heading is `#### {finding_id}. {display_title}` with **Check ID** and **TSR ref** lines immediately below.
