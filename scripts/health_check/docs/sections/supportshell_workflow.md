Follow these steps top-to-bottom for a full supportshell engagement.

> **Note:** Use your actual home directory path (e.g. `/home/remote/<username>`) instead of `~` when specifying remote paths below. `~` does not reliably expand when passed through `make` variables over SSH in this environment — substitute your real home directory.

### Step 1 — Push the collection scripts to the server

Do this once (or after any script update):

```bash
make hc-push-scripts HC_SSH_HOST=user@your-supportshell-server.example.com
```

### Step 2 — Download the must-gather from the case

Log into the support shell server and run `yank` with the case number:

```bash
yank 04502902
```

`yank` downloads all case attachments and extracts them in place. The must-gather lands at a path like:

```
/home/remote/<username>/04502902/
  0010-must-gather-console.log
  0020-must-gather-20260724132027.tar.gz/       ← extracted in-place as a directory
    must-gather.local.3101912616506361300/       ← one must-gather type per subdir
    must-gather.local.8139364098167362569/
      quay-io-openshift-release-dev-ocp-v4-0-art-dev-.../
      quay-io-pg-next-pg-must-gather-.../
      registry-redhat-io-container-native-virtualization-cnv-.../
      timestamp
```

### Step 3 — Run collection

`hc_collect_multi.sh` recursively discovers all must-gather types nested anywhere under the given input path, groups them by cluster based on the extracted case-directory names left by `yank`, and runs `omc` against each selected cluster independently. This means you can still point it at the case directory itself (`/home/remote/<username>/04502902`) without needing to know the dated subdirectory name it extracted to, but the script no longer merges unrelated clusters together.

Run it remotely from your workstation (no need to `ssh` in yourself):

```bash
make hc-collect-remote HC_SSH_HOST=user@your-supportshell-server.example.com HC_MG_INPUT=/home/remote/<username>/04502902
```

If the case contains multiple clusters, the remote run prompts you to choose one cluster or `all`. For non-interactive runs, pass `--cluster <name|all>` when invoking `hc_collect_multi.sh` directly.

Or run it directly on the server:

```bash
bash /home/remote/<username>/hc_supportshell/hc_collect_multi.sh --input /home/remote/<username>/04502902 --output-dir /home/remote/<username>/hc_results --tar
bash /home/remote/<username>/hc_supportshell/hc_collect_multi.sh --input /home/remote/<username>/04502902 --output-dir /home/remote/<username>/hc_results --cluster nam-arl-01 --tar
```

This produces `/home/remote/<username>/hc_results/<cluster_name>/` for each selected cluster, plus `/home/remote/<username>/hc_results.tar.gz` as an aggregate tarball when `--tar` is used.

Each cluster output directory contains its own `skipped_commands.jsonl`, tagged with which must-gather subdirectory was active. This is useful for confirming a skip was expected rather than a collection bug. See [Skipped Commands Ledger (Debugging)](#skipped-commands-ledger-debugging) in Reference below for the full ledger format and readable-summary/investigation commands.

**Multi-cluster behavior:**
- Cluster names are parsed from the extracted case directory names, such as `0180-nam-arl-01-must-gather.tar.gz`
- If two extracted bundles map to the same cluster (for example an original plus a later `fixed_` re-pull), the script prints a large warning and keeps only the latest bundle
- Outputs are always nested per cluster so report generation and TSR matching stay explicit

> **Manual invocation:** You can also invoke the collection script directly — useful for running locally against a must-gather already on your workstation, for ad-hoc debugging, or for filtering to specific categories (which the Makefile targets don't expose):
>
> ```bash
> omc use /path/to/must-gather-unpacked/
> bash scripts/health_check/supportshell/hc_collect.sh --output-dir output/hc_collect
> bash scripts/health_check/supportshell/hc_collect.sh --output-dir output/hc_collect --categories 03,05,07
> ```
