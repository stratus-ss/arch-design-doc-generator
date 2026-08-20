The `make hc-collect` target always runs a full collection and has no category filter, so recollecting a subset requires calling the script directly:

```bash
# Only base platform and security
bash hc_collect.sh --kubeconfig ~/.kube/config --categories 03,09

# Only cluster health
bash hc_collect.sh --kubeconfig ~/.kube/config --categories 07
```

You can also run a single script in isolation:

```bash
export HC_RESULTS_DIR=./hc_results
export KUBECONFIG=~/.kube/config
bash 07_cluster_health.sh
```

---

## Remote Collection — Transferring Results to Your Local Machine

In most engagements, `hc_collect.sh` runs on a remote machine (bastion host, jumpbox, or the customer's workstation) because that's where cluster access exists. The report generation pipeline runs locally in this repository. You need to get the collection output back.

### What to transfer

The entire output directory produced by `hc_collect.sh` — typically `./hc_results/` or wherever `--output-dir` pointed. It contains `manifest.json` plus all the category subdirectories.

### Option A — tar + scp (most common)

On the remote machine:

```bash
tar czf hc_results.tar.gz hc_results/
```

On your local machine:

```bash
scp user@bastion:/path/to/hc_results.tar.gz .
tar xzf hc_results.tar.gz -C output/hc_collect --strip-components=1
```

Or if you want to preserve the directory as-is:

```bash
scp -r user@bastion:/path/to/hc_results/ output/hc_collect/
```

### Option B — rsync

```bash
rsync -avz user@bastion:/path/to/hc_results/ output/hc_collect/
```

### Option C — Intermediate jump host

If the bastion doesn't have direct outbound access, chain the transfer:

```bash
# On bastion → jumpbox
scp hc_results.tar.gz user@jumpbox:/tmp/

# From your workstation → jumpbox
scp user@jumpbox:/tmp/hc_results.tar.gz .
tar xzf hc_results.tar.gz -C output/hc_collect --strip-components=1
```

### Where to place it locally

The report generator expects the results at `output/hc_collect/` by default (configured via `health_check.output_collect_path` in `project.yaml`). The directory must contain `manifest.json` at its root:

```
output/hc_collect/
├── manifest.json          ← must exist at this level
├── 03_base_platform/
├── 04_topology/
├── 05_components/
└── ...
```

If you used `--strip-components=1` during extraction, verify the structure is correct:

```bash
ls output/hc_collect/manifest.json
```

Once the results are in place, proceed with `make hc-report`.
